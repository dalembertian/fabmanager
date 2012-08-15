# encoding: utf-8
# Generic fabfile.py
#
# See README for instructions on how to use fabmanager.

import os
import datetime

from fabric.api import *
from fabric.contrib import django
from fabric.contrib import files
from fabric.contrib import console

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
MEDIA_DIR          = '%(workon)s/%(virtualenv)s/%(project)s/media'
STATIC_DIR         = '%(workon)s/%(virtualenv)s/%(project)s/static'
FAVICON_DIR        = '%(workon)s/%(virtualenv)s/%(project)s/static/img'
ROBOTS_DIR         = '%(workon)s/%(virtualenv)s/%(project)s/config'
WSGI_DIR           = '%(workon)s/%(virtualenv)s/%(project)s/%%s'

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
    with settings(hide('commands'), warn_only=True):
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

# Local commands

def apache(wsgi_file):
    """Generates Apache conf file. Requires: path to WSGI conf file."""
    _require_environment()

    # Dictionary for interpolating template
    wsgi_dir          = os.path.dirname(wsgi_file)
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
        'robots_dir':       _interpolate(ROBOTS_DIR),
        'wsgi_dir':         _interpolate(WSGI_DIR) % wsgi_dir,
        'wsgi_file':        _interpolate(WSGI_DIR) % wsgi_file,
    }

    with open(os.path.join(templates_dir, 'apache.conf'), 'r') as input:
        for line in input:
            print line % variables,

def wsgi():
    """Generates WSGI conf file"""
    _require_environment()

    # Dictionary for interpolating template
    variables = {
        'project': env.project['project'],
        'settings': env.project['settings'],
        'site_packages': SITE_PACKAGES_DIR % _python_version(),
    }

    with open(os.path.join(templates_dir, 'wsgi.py'), 'r') as input:
        for line in input:
            print line % variables,

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
    """
    _require_environment()

    # Uses local settings to extract username/password to access remote database
    django.settings_module(env.project['settings'])
    from django.conf import settings
    database = settings.DATABASES['default']

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

def setup():
    """Sets up a new environment"""
    _require_environment()
    _setup_virtualenv()
    _setup_gitrepo()

def _setup_virtualenv():
    """Creates virtualenv for environment"""
    if files.exists(_interpolate(VIRTUALENV_DIR)):
        print _interpolate('virtualenv %(virtualenv)s already exists')
    else:
        with prefix(_virtualenvwrapper_prefix()):
            run(_interpolate('mkvirtualenv %(virtualenv)s'))
            with hide('commands'):
                print 'virtualenv %s created with python %s\n' % (env.environment, run(GET_PYTHON_VERSION))

def _setup_gitrepo():
    """Clones project git repo into virtualenv"""
    if files.exists(_interpolate(DJANGO_PROJECT_DIR)):
        print _interpolate('project %(project)s already exists')
    else:
        with cd(_interpolate(VIRTUALENV_DIR)):
            run(_interpolate('git clone %(git_repo)s %(project)s'))
            branch = env.project.get('git_branch', 'master')
            if branch != 'master':
                with cd(env.project['project']):
                    run('git fetch origin %s:%s' % (branch, branch))
                    run('git checkout %s' % branch)
