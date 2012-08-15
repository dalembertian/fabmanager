# encoding: utf-8
# Generic fabfile.py
#
# See README for instructions on how to use fabmanager.

import os
import datetime
import cStringIO

from fabric.api import *
from fabric.contrib import django
from fabric.contrib import files
from fabric.contrib import console

from django.conf import settings as django_settings


# Paths related to fabmanager
fabmanager_dir = os.path.dirname(os.path.abspath(__file__))
templates_dir  = os.path.join(fabmanager_dir, 'templates/fabmanager/')

# Environments - to be extended with ENVS.update()
ENVS = {}

# Python
GET_PYTHON_VERSION = "python -V 2>&1 | cut -f2 -d' ' | cut -f-2 -d."

# virtualenvwrapper
VIRTUALENVWRAPPER_SCRIPT = '/usr/local/bin/virtualenvwrapper.sh'
VIRTUALENVWRAPPER_PREFIX = 'export WORKON_HOME=%(workon)s && source %(script)s'

# Django strings should be interpolated by ENVS[project]
VIRTUALENV_DIR     = '%(workon)s/%(virtualenv)s'
SITE_PACKAGES_DIR  = 'lib/python%s/site-packages'
DJANGO_PROJECT_DIR = "%(workon)s/%(virtualenv)s/%(project)s"
DJANGO_PREFIX      = "export PYTHONPATH=%(workon)s/%(virtualenv)s:%(workon)s/%(virtualenv)s/%(project)s " \
                     "DJANGO_SETTINGS_MODULE=%(project)s.%(settings)s && " \
                     "source %(workon)s/%(virtualenv)s/bin/activate"

# Apache
CONFIG_DIR         = '%(workon)s/%(virtualenv)s/%(project)s/config'
MEDIA_DIR          = '%(workon)s/%(virtualenv)s/%(project)s/media'
STATIC_DIR         = '%(workon)s/%(virtualenv)s/%(project)s/static'
FAVICON_DIR        = '%(workon)s/%(virtualenv)s/%(project)s/static/img'
APACHE_CONF        = CONFIG_DIR+'/apache_%(virtualenv)s.conf'
WSGI_CONF          = CONFIG_DIR+'/wsgi_%(virtualenv)s.py'

# MySQL
MYSQL_PREFIX       = 'mysql -u root -p -e %s'

# Aliases for common tasks at server
ALIASES = dict(
    gs='git status',
    gd='git diff',
    gl='git pull',
    gp='git push',
    gc='git commit -v -a',
    gb='git branch',
    gk='git checkout',
    gm='git checkout master',
    glog='git log --oneline --decorate',
    glogg='git log --oneline --decorate --graph',
    mng='django-admin.py',
)

# Setup commands

def _setup_environment(environment):
    """
    Sets up env variables for this session
    """
    env.environment = environment
    env.project = ENVS[environment]
    env.hosts = [env.project['host']]

def _require_environment():
    """Checks if env.environment and env.host exist"""
    require('environment', 'host', provided_by=ENVS.keys())

def _interpolate(string):
    """Interpolates string with dictionary provided by ENVS"""
    return string % env.project

def _virtualenvwrapper_prefix():
    """Prefix to be able to invoke virtualenvwrapper commands"""
    return VIRTUALENVWRAPPER_PREFIX % {
        'workon': env.project['workon'],
        'script': VIRTUALENVWRAPPER_SCRIPT,
    }

def _python_version():
    """Checks python version on remote virtualenv"""
    with settings(hide('commands', 'warnings'), warn_only=True):
        with prefix(_django_prefix()):
            result = run(GET_PYTHON_VERSION)
            if result.failed:
                abort('Could not determine Python version at virtualenv %s' % env.environment)
    return result

def _django_prefix():
    """Prefix to wrap commands with necessary virtualenv and variables"""
    return _interpolate(DJANGO_PREFIX)

def _django_project_dir():
    """Path to current project' directory"""
    return _interpolate(DJANGO_PROJECT_DIR)

def _parse_alias(command):
    """
    Mimics a bash alias: if command starts with a word that is present in ALIASES
    dictionary, substitutes that word for the value found, and maintains te rest.
    """
    words = command.split(' ')
    if not words or words[0] not in ALIASES.keys():
        return command
    else:
        return '%s %s' % (ALIASES[words[0]], ' '.join(words[1:]))

# Remote commands

def remote(command='gs'):
    """
    Issues a generic command at project's directory
    """
    _require_environment()
    with prefix(_django_prefix()):
        with cd(_django_project_dir()):
            run(_parse_alias(command))

def update():
    """
    Updates server from git pull
    """
    branch = env.project.get('git_branch', 'master')
    with settings(hide('warnings'), warn_only=True):
        remote('git pull origin %s && django-admin.py migrate && touch config/wsgi*' % branch)

def status():
    """
    Checks git log and status
    """
    remote('glogg -n 20 && echo "" && git status')

def python():
    """Tries to figure out Python version on server side"""
    _require_environment()
    print 'Python version on virtualenv %s: %s' % (env.environment, _python_version())

def backup():
    """
    Backup server's database and copy tar.gz to local ../backup dir
    TODO: create a restore task
    """
    _require_environment()

    # Uses local Django settings to extract username/password to access remote database
    django.settings_module(env.project['settings'])
    database = django_settings.DATABASES['default']

    # Remote side
    with prefix(_django_prefix()):
        with cd(_django_project_dir()):
            # Creates dir to store backup, avoiding existing similar names
            dirname = '../backup/%s_%s' % (datetime.date.today().strftime('%Y%m%d'), env.environment)
            index = 0
            while files.exists(dirname) or files.exists('%s.tar.gz' % dirname):
                index += 1
                dirname += '.%s' % index
            run('mkdir -p %s' % dirname)

            # Backup
            run('mysqldump -u %s -p%s %s > %s/%s.sql' % (
                database['USER'],
                database['PASSWORD'],
                database['NAME'],
                dirname,
                database['NAME'],
            ))
            run('django-admin.py dumpdata auth > %s/auth.json' % dirname)
            run('cp -R media/uploads %s/' % dirname)
            run('cp -R media/newsletter %s/' % dirname)
            with hide('stdout'):
                run('tar -czvf %s.tar.gz %s/' % (dirname, dirname))
            run('rm -rf %s/' % dirname)

            # Download backup?
            if console.confirm('Download backup?'):
                get('%s.tar.gz' % dirname, '../backup')

def _generate_conf(conf_file, variables):
    """Generates conf file from template, and optionally saves it"""
    # File names
    filename_parts = conf_file.split('.')
    filename_parts.insert(1, env.environment)
    input_file = os.path.join(templates_dir, conf_file)
    output_file = 'config/%s_%s.%s' % tuple(filename_parts)

    # Generate conf file from template
    conf = ''
    output = cStringIO.StringIO()
    try:
        with open(input_file, 'r') as input:
            for line in input:
                output.write(line % variables)
        conf = output.getvalue()
    finally:
        output.close()

    # Shows conf file and optionally saves it
    print conf
    if console.confirm('Save to %s?' % output_file, default=False):
        with open(output_file, 'w') as output:
            output.write(conf)

def apache():
    """Generates Apache conf file. Requires: path to WSGI conf file."""
    _require_environment()

    # Dictionary for interpolating template
    config_dir        = _interpolate(CONFIG_DIR)
    host_aliases      = env.project.get('host_aliases', '')
    if host_aliases:
        host_aliases  = 'ServerAlias %s' % host_aliases

    variables = {
        'host':             env.project['host'],
        'host_aliases':     host_aliases,
        'static_admin_dir': '%s/%s/django/contrib/admin/media' % (_interpolate(VIRTUALENV_DIR), SITE_PACKAGES_DIR % _python_version()),
        'media_dir':        _interpolate(MEDIA_DIR),
        'static_dir':       _interpolate(STATIC_DIR),
        'favicon_dir':      _interpolate(FAVICON_DIR),
        'config_dir':       config_dir,
        'wsgi_file':        '%s/wsgi_%s.py' % (config_dir, env.environment),
    }
    _generate_conf('apache.conf', variables)

def wsgi():
    """Generates WSGI conf file"""
    _require_environment()

    # Dictionary for interpolating template
    variables = {
        'project': env.project['project'],
        'settings': env.project['settings'],
        'site_packages': SITE_PACKAGES_DIR % _python_version(),
        }
    _generate_conf('wsgi.py', variables)

def setup():
    """Sets up a new environment"""
    _require_environment()

    # Checks if needed conf files for this environment already exist
    if not os.path.exists('settings_%s.py' % env.environment):
        abort('There is no settings.py for %s - create one, and commit' % env.environment)
    if not os.path.exists('config/apache_%s.conf' % env.environment):
        abort('There is no Apache conf for %s - use task "apache" to generate one, and commit' % env.environment)
    if not os.path.exists('config/wsgi_%s.py' % env.environment):
        abort('There is no WSGI conf for %s - use task "wsgi" to generate one, and commit' % env.environment)

    # Configures remote server
    _setup_virtualenv()
    _clone_gitrepo()
    _setup_apache()
    _setup_mysql()
    # TODO: create more setup tasks:
    #   - create aux dirs (logs, etc.)
    #   - pip install
    #   - syncdb, migrate
    #   - collectstatic

def _setup_virtualenv():
    """Creates virtualenv for environment"""
    if files.exists(_interpolate(VIRTUALENV_DIR)):
        print 'virtualenv %s already exists' % env.environment
    else:
        with prefix(_virtualenvwrapper_prefix()):
            run(_interpolate('mkvirtualenv --no-site-packages %(virtualenv)s'))
            with hide('commands'):
                print 'virtualenv %s created with python %s\n' % (env.environment, run(GET_PYTHON_VERSION))

def _clone_gitrepo():
    """Clones project git repo into virtualenv"""
    if files.exists(_interpolate(DJANGO_PROJECT_DIR)):
        print _interpolate('project %(project)s already exists, updating')
        update()
    else:
        with cd(_interpolate(VIRTUALENV_DIR)):
            run(_interpolate('git clone %(git_repo)s %(project)s'))
            branch = env.project.get('git_branch', 'master')
            if branch != 'master':
                with cd(env.project['project']):
                    run('git fetch origin %s:%s' % (branch, branch))
                    run('git checkout %s' % branch)

def _setup_apache():
    """Configures Apache"""
    if files.exists(_interpolate('/etc/apache2/sites-enabled/%(virtualenv)s')):
        print 'Apache conf for %s already exists' % env.environment
    else:
        sudo(_interpolate('ln -s %s /etc/apache2/sites-enabled/%%(virtualenv)s' % APACHE_CONF))
        sudo('apache2ctl restart')

def _setup_mysql():
    """Creates MySQL database according to env's settings.py"""
    # Uses local Django settings to extract username/password to access remote database
    django.settings_module(env.project['settings'])
    database = django_settings.DATABASES['default']

    # Create database & user, if not already there
    with settings(hide('warnings'), warn_only=True):
        result = run(MYSQL_PREFIX % "\"CREATE DATABASE %(NAME)s DEFAULT CHARACTER SET utf8;\"" % database)
        if result.succeeded:
            run(MYSQL_PREFIX % "\"GRANT ALL ON %(NAME)s.* TO '%(USER)s'@'localhost' IDENTIFIED BY '%(PASSWORD)s';\"" % database)
