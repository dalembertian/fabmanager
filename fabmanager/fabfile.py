# encoding: utf-8
# Generic fabfile.py
#
# See README for instructions on how to use fabmanager.
import urllib

import os
import datetime
import cStringIO

from fabric.api import *
from fabric.contrib import django
from fabric.contrib import files
from fabric.contrib import console

try:
    from django.conf import settings as django_settings
except:
    django_settings = {}

# Paths related to fabmanager
fabmanager_dir = os.path.dirname(os.path.abspath(__file__))
templates_dir  = os.path.join(fabmanager_dir, 'templates/fabmanager/')

# Environments - to be extended with ENVS.update()
ENVS = {}

# Linux
REMOTE_USER_PASSWORD = '1ntr05p3ct10n'
GIT_VERSION          ='1.7.10.3'
GET_GIT_VERSION      = "git --version | cut -d ' ' -f 3"

# Python
GET_PYTHON_VERSION  = "python -V 2>&1 | cut -f2 -d' ' | cut -f-2 -d."

# virtualenvwrapper
VIRTUALENVWRAPPER_SCRIPT = '/usr/local/bin/virtualenvwrapper.sh'
VIRTUALENVWRAPPER_PREFIX = 'export WORKON_HOME=%(workon)s && source %(script)s'

# Django strings should be interpolated by ENVS[project]
VIRTUALENV_DIR      = '%(workon)s/%(virtualenv)s'
SITE_PACKAGES_DIR   = 'lib/python%s/site-packages'
DJANGO_PROJECT_DIR  = "%(workon)s/%(virtualenv)s/%(project)s"
DJANGO_PREFIX       = "export PYTHONPATH=%(workon)s/%(virtualenv)s:%(workon)s/%(virtualenv)s/%(project)s " \
                      "DJANGO_SETTINGS_MODULE=%(project)s.%(settings)s && " \
                      "source %(workon)s/%(virtualenv)s/bin/activate"

# Apache
CONFIG_DIR          = '%(workon)s/%(virtualenv)s/%(project)s/config'
MEDIA_DIR           = '%(workon)s/%(virtualenv)s/%(project)s/media'
STATIC_DIR          = '%(workon)s/%(virtualenv)s/%(project)s/static'
FAVICON_DIR         = '%(workon)s/%(virtualenv)s/%(project)s/static/images'
APACHE_CONF         = CONFIG_DIR+'/apache_%(environment)s.conf'
WSGI_CONF           = CONFIG_DIR+'/wsgi_%(environment)s.py'

# MySQL
MYSQL_ROOT_PASSWORD = '1ntr05p3ct10n'
MYSQL_PREFIX        = 'mysql -u root -p%s -e %%s' % MYSQL_ROOT_PASSWORD
PIP_INSTALL_PREFIX  = 'pip install -r config/required-packages.pip'

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

##################
# Setup commands #
##################

def _setup_environment(environment):
    """
    Sets up env variables for this session
    """
    env.environment = environment
    env.project     = ENVS[environment]
    env.hosts       = [env.project['host']]
    env.user        = env.project.get('user', env.local_user)
    env.password    = env.project.get('password', None)
    # Redundant, just to easy the interpolation later on
    env.project['environment'] = environment

def _require_environment():
    """Checks if env.environment and env.host exist"""
    require('environment', 'host', provided_by=ENVS.keys())

def _interpolate(string):
    """Interpolates string with dictionary provided by ENVS"""
    return string % env.project

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

##################
# Linux commands #
##################

def adduser():
    """Creates remote user with the same name as the local user, and uploads ~/.ssh/id_rsa*"""
    _require_environment()
    env.remote_home = '/home/%s' % env.local_user
    env.remote_password = REMOTE_USER_PASSWORD

    # Connects as root (or sudoer)
    user = prompt('Remote username?', default='root')
    env.user = user
    env.password = None

    # Creates user with same name as local_user, if it doesn't exist already
    if files.exists(env.remote_home):
        print 'User %(local_user)s already exists on %(environment)s!' % env
    else:
        # TODO: generate password -p%(remote_password)s with [m]crypt
        sudo('useradd -d%(remote_home)s -s/bin/bash -m -U %(local_user)s' % env)
        sudo('passwd rubens')
        # TODO: not all distributions use group sudo for sudoers (e.g.: old Ubuntu uses admin)
        # TODO: sudoers should not have to use password
        sudo('adduser %(local_user)s sudo' % env)
        sudo('mkdir %(remote_home)s/.ssh' % env)
        put('~/.ssh/id_rsa.pub', '%(remote_home)s/.ssh/authorized_keys' % env, use_sudo=True, mode=0644)
        put('~/.ssh/id_rsa', '%(remote_home)s/.ssh/id_rsa' % env, use_sudo=True, mode=0600)
        sudo('chown -R %(local_user)s:%(local_user)s %(remote_home)s/.ssh' % env)

    # Continues as newly created user
    env.user = env.local_user
    env.password = None

def install_git():
    """Installs (recent) git from source"""
    git_version = sudo(GET_GIT_VERSION)
    if git_version != GIT_VERSION:
        git_file = 'git-%s' % GIT_VERSION
        sudo('apt-get -y -qq install build-essential')
        sudo('apt-get -y -qq install git-core')
        sudo('apt-get -y -qq install libcurl4-gnutls-dev')
        sudo('apt-get -y -qq install libexpat1-dev')
        sudo('apt-get -y -qq install gettext')
        sudo('apt-get -y -qq install libz-dev')
        sudo('apt-get -y -qq install libssl-dev')
        sudo('wget --quiet http://git-core.googlecode.com/files/%s.tar.gz' % git_file)
        sudo('tar -xzf %s.tar.gz' % git_file)
        with cd(git_file):
            sudo('make --silent prefix=/usr/local all > /dev/null')
            sudo('make --silent prefix=/usr/local install  > /dev/null')

def apt_get_update():
    """Updates apt-get repositories"""
    sudo('apt-get update')

##################
# MySQL commands #
##################

def install_mysql():
    """Installs MySQL"""
    sudo('DEBIAN_FRONTEND=noninteractive apt-get -y -qq install mysql-server libmysqlclient-dev')
    with settings(warn_only=True):
        sudo('mysqladmin -u root password %s' % MYSQL_ROOT_PASSWORD)
#    sudo('mysqladmin -u root -p%s -h localhost password %s' % (MYSQL_ROOT_PASSWORD, MYSQL_ROOT_PASSWORD))

def _setup_project_mysql():
    """Creates MySQL database according to env's settings.py"""
    # Uses local Django settings to extract username/password to access remote database
    django.settings_module(env.project['settings'])
    database = django_settings.DATABASES['default']

    # Create database & user, if not already there
    with settings(hide('warnings'), warn_only=True):
        result = run(MYSQL_PREFIX % "\"CREATE DATABASE %(NAME)s DEFAULT CHARACTER SET utf8;\"" % database)
        if result.succeeded:
            run(MYSQL_PREFIX % "\"GRANT ALL ON %(NAME)s.* TO '%(USER)s'@'localhost' IDENTIFIED BY '%(PASSWORD)s';\"" % database)

###################
# Apache commands #
###################

def install_apache():
    """Installs Apache and mod_wsgi"""
    sudo ('apt-get -y -qq install apache2 apache2-mpm-worker libapache2-mod-wsgi')

def _setup_project_apache():
    """Configures Apache"""
    if files.exists(_interpolate('/etc/apache2/sites-enabled/%(virtualenv)s')):
        print 'Apache conf for %(environment)s already exists' % env
    else:
        sudo(_interpolate('ln -s %s /etc/apache2/sites-enabled/%%(virtualenv)s' % APACHE_CONF))
        sudo('apache2ctl restart')

def generate_apache_conf():
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
        'static_admin_dir': '%s/%s/django/contrib/admin/media' % (_interpolate(VIRTUALENV_DIR), SITE_PACKAGES_DIR % _get_python_version()),
        'media_dir':        _interpolate(MEDIA_DIR),
        'static_dir':       _interpolate(STATIC_DIR),
        'favicon_dir':      _interpolate(FAVICON_DIR),
        'config_dir':       config_dir,
        'wsgi_file':        '%s/wsgi_%s.py' % (config_dir, env.environment),
        }
    _generate_conf('apache.conf', variables)

def generate_wsgi_conf():
    """Generates WSGI conf file"""
    _require_environment()

    # Dictionary for interpolating template
    variables = {
        'project': env.project['project'],
        'settings': env.project['settings'],
        'site_packages': SITE_PACKAGES_DIR % _get_python_version(),
        }
    _generate_conf('wsgi.py', variables)

def apache_restart():
    """
    Restarts Apache
    """
    _require_environment()
    sudo('apache2ctl restart')


###################
# Python commands #
###################

def install_python():
    """Installs Python, setuptools, pip, virtualenv, virtualenvwrapper"""
    _require_environment()
    # TODO: find a better criteria for when to use apt-get update
    if not files.exists('/usr/bin/python'):
        apt_get_update()
    # TODO: Install Python 2.7.3 from source, regardless of Linux distribution
    sudo('apt-get -y -qq install python python2.6 python2.6-dev pkg-config gcc')
    sudo('apt-get -y -qq install python-setuptools')
    sudo('easy_install virtualenv')
    sudo('easy_install pip')
    sudo('pip install virtualenvwrapper')
    with settings(warn_only=True):
        sudo(_interpolate('mkdir %(workon)s && chmod g+w %(workon)s && chown %%(user)s:%%(user)s %(workon)s') % env)

def _get_python_version():
    """Checks python version on remote virtualenv"""
    with settings(hide('commands', 'warnings'), warn_only=True):
        # First tries to check python within virtualenv
        with prefix(_django_prefix()):
            result = run(GET_PYTHON_VERSION)
        # If that fails, checks global python
        if result.failed:
            result = run(GET_PYTHON_VERSION)
        # if it still fails, something is wrong!
        if result.failed:
            abort(_interpolate('Could not determine Python version at virtualenv %(virtualenv)s'))
    return result

def _virtualenvwrapper_prefix():
    """Prefix to be able to invoke virtualenvwrapper commands"""
    return VIRTUALENVWRAPPER_PREFIX % {
        'workon': env.project['workon'],
        'script': VIRTUALENVWRAPPER_SCRIPT,
        }

def _setup_virtualenv():
    """Creates virtualenv for environment"""
    if files.exists(_interpolate(VIRTUALENV_DIR)):
        print _interpolate('virtualenv %(virtualenv)s already exists')
    else:
        with prefix(_virtualenvwrapper_prefix()):
            run(_interpolate('mkvirtualenv --no-site-packages %(virtualenv)s'))
            with hide('commands'):
                print 'virtualenv %s created with python %s\n' % (env.project['virtualenv'], run(GET_PYTHON_VERSION))

def python_version():
    """Tries to figure out Python version on server side"""
    _require_environment()
    print 'Python version on virtualenv %s: %s' % (env.project['virtualenv'], _get_python_version())

#############################
# (Django) project commands #
#############################

def _django_prefix():
    """Prefix to wrap commands with necessary virtualenv and variables"""
    return _interpolate(DJANGO_PREFIX)

def _django_project_dir():
    """Path to current project' directory"""
    return _interpolate(DJANGO_PROJECT_DIR)

def _clone_gitrepo():
    """Clones project git repo into virtualenv"""
    # Puts git repo in ~/.ssh/config to avoid interaction due to missing known_hosts
    git_server = urllib.splituser(urllib.splittype(env.project['git_repo'])[0])[1]
    if not files.exists('~/.ssh/config') or not files.contains('~/.ssh/config', git_server):
        files.append('~/.ssh/config', ['host %s' % git_server, '    StrictHostKeyChecking no'])

    branch = env.project.get('git_branch', 'master')
    if files.exists(_interpolate(DJANGO_PROJECT_DIR)):
        print _interpolate('project %(project)s already exists, updating')
        remote('git pull origin %s' % branch)
    else:
        with cd(_interpolate(VIRTUALENV_DIR)):
            run(_interpolate('git clone %(git_repo)s %(project)s'))
            if branch != 'master':
                remote('git fetch origin %s:%s' % (branch, branch))
                remote('git checkout %s' % branch)

def remote(command):
    """
    Issues a generic command at project's directory level
    """
    _require_environment()
    with prefix(_django_prefix()):
        with cd(_django_project_dir()):
            if command.startswith('sudo '):
                sudo(_parse_alias(command[5:]))
            else:
                run(_parse_alias(command))

def setup_project():
    """Sets up a new environment"""
    _require_environment()

    # Checks if needed conf files for this environment already exist
    if not os.path.exists(_interpolate('%(settings)s.py')):
        abort(_interpolate('There is no settings.py for %(environment)s - create one, and commit'))
    if not os.path.exists(_interpolate('config/apache_%(environment)s.conf')):
        abort(_interpolate('There is no Apache conf for %(environment)s - use task "generate_apache_conf" to generate one, and commit'))
    if not os.path.exists(_interpolate('config/wsgi_%(environment)s.py')):
        abort(_interpolate('There is no WSGI conf for %(environment)s - use task "generate_wsgi_conf" to generate one, and commit'))

    # Configures virtualenv and clones git repo
    _setup_virtualenv()
    _clone_gitrepo()

    # Issues extra commands at project's level, if any
    extra_commands = env.project.get('extra_commands', [])
    with settings(hide('warnings'), warn_only=True):
        for command in extra_commands:
            remote(command)

    # Sets up Apache, MySQL
    _setup_project_apache()
    _setup_project_mysql()

    # Finish installation
    pip_install()
    update_project()

def pip_install():
    """
    Uses pip to install needed requirements
    """
    _require_environment()
    remote(PIP_INSTALL_PREFIX)

def status_project():
    """
    Checks git log and status
    """
    remote('glogg -n 20 && echo "" && git status')

def update_project():
    """
    Updates server from git pull
    """
    branch = env.project.get('git_branch', 'master')
    with settings(hide('warnings'), warn_only=True):
        remote(
            'git pull origin %s && '
            'django-admin.py syncdb --noinput && '
            'django-admin.py migrate && '
            'django-admin.py collectstatic --noinput && '
            'touch config/wsgi*'
        % branch)

def backup_project():
    """
    Backup server's database and copy tar.gz to local ../backup dir
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
            path = dirname
            index = 0
            while files.exists(path) or files.exists('%s.tar.gz' % path):
                index += 1
                path = '%s.%s' % (dirname, index)
            run('mkdir -p %s' % path)

            # Backup MySQL
            run('mysqldump -u %s -p%s %s > %s/%s.sql' % (
                database['USER'],
                database['PASSWORD'],
                database['NAME'],
                path,
                env.project['project'],
            ))

            # Backup extra files
            extra_backup_files = env.project.get('extra_backup_files', None)
            for file in extra_backup_files:
                run('cp -R %s %s/' % (file, path))

            # Create .tar.gz and removes uncompressed files
            with hide('stdout'):
                run('tar -czvf %s.tar.gz %s/' % (path, path))
            run('rm -rf %s/' % path)

            # Download backup?
            if console.confirm('Download backup?'):
                get('%s.tar.gz' % path, '../backup')

def restore_project(filename):
    """
    Restore server's database with .sql file contained in filename
    """
    _require_environment()

    # Uses local Django settings to extract username/password to access remote database
    django.settings_module(env.project['settings'])
    database = django_settings.DATABASES['default']

    # Remote side
    with prefix(_django_prefix()):
        with cd(_django_project_dir()):
            # Uploads tar file
            tarfile = os.path.basename(filename)
            basename = tarfile[:tarfile.index('.tar.gz')]
            put(filename, '../backup/%s' % tarfile)

            # Restore MySQL
            with cd('../'):
                run('tar -xzvf backup/%s' % tarfile)
                run('mysql -u %s -p%s %s < backup/%s/%s.sql' % (
                    database['USER'],
                    database['PASSWORD'],
                    database['NAME'],
                    basename,
                    env.project['project'],
                ))

            # Restore extra files
            extra_backup_files = env.project.get('extra_backup_files', None)
            for file in extra_backup_files:
                run('cp -R ../backup/%s/%s ./%s' % (basename, os.path.basename(file), os.path.dirname(file)))

            # Removes uncompressed files, but leaves .tar.gz
            run('rm -rf ../backup/%s' % basename)

#####################
# The Big Bootstrap #
#####################

def bootstrap():
    """Installs EVERYTHING from scratch!"""
    _require_environment()

    adduser()
    install_python()
    install_git()
    install_apache()
    install_mysql()
    setup_project()

