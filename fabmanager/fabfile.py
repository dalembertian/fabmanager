# encoding: utf-8
# Generic fabfile.py
#
# See README for instructions on how to use fabmanager.
import urllib

import os
import datetime
import io

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
NEWEST_GIT_VERSION  = "curl -s http://git-scm.com/ | python -c \"import sys; from bs4 import BeautifulSoup; soup=BeautifulSoup(''.join(sys.stdin.readlines())); print(soup.find(class_='version').text.strip())\""
LOCAL_GIT_VERSION   = "git --version | cut -d ' ' -f 3"

# Python
GET_PYTHON_VERSION  = "python -V 2>&1 | cut -f2 -d' ' | cut -f-2 -d."

# virtualenvwrapper
VIRTUALENVWRAPPER_SCRIPT = '/usr/local/bin/virtualenvwrapper.sh'
VIRTUALENVWRAPPER_PREFIX = 'export WORKON_HOME=%(workon)s && source %(script)s'

# Django strings should be interpolated by ENVS[project]
VIRTUALENV_DIR           = '%(workon)s/%(virtualenv)s'
SITE_PACKAGES_DIR        = 'lib/python%s/site-packages'
DJANGO_LATEST_VERSION    = '1.6'
DJANGO_PROJECT_DIR       = "%(workon)s/%(virtualenv)s/%(project)s"
DJANGO_PREFIX            = "export PYTHONPATH=%(workon)s/%(virtualenv)s:%(workon)s/%(virtualenv)s/%(project)s " \
                           "DJANGO_SETTINGS_MODULE=%(project)s.%(settings)s && " \
                           "source %(workon)s/%(virtualenv)s/bin/activate"

# Apache
CONFIG_DIR          = '%(workon)s/%(virtualenv)s/%(project)s/%(project)s'
MEDIA_DIR           = '%(workon)s/%(virtualenv)s/%(project)s/media'
STATIC_DIR          = '%(workon)s/%(virtualenv)s/%(project)s/static'
APACHE_CONF         = CONFIG_DIR+'/apache_%(environment)s.conf'
WSGI_CONF           = CONFIG_DIR+'/wsgi_%(environment)s.py'

# MySQL
MYSQL_PREFIX        = 'mysql -u root -p -e %s'

PIP_INSTALL_PREFIX  = 'pip install -r %(project)s/required-packages.pip'

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
    mng='django-admin',
)

##################
# Setup commands #
##################

def _setup_environment(environment):
    """
    Sets up env variables for this session
    """
    env.forward_agent = True    
    env.environment   = environment
    env.project       = ENVS[environment]
    env.hosts         = [env.project['host']]
    env.user          = env.project.get('user', env.local_user)
    env.password      = env.project.get('password', None)
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
    dictionary, substitutes that word for the value found, and maintains the rest.
    """
    words = command.split(' ')
    if not words or words[0] not in ALIASES.keys():
        return command
    else:
        return '%s %s' % (ALIASES[words[0]], ' '.join(words[1:]))

def _generate_conf(conf_file, variables, django_version):
    """Generates conf file from template, and optionally saves it"""
    if not django_version:
        django_version = DJANGO_LATEST_VERSION

    # File names
    part = conf_file.split('.')
    input_file = os.path.join(templates_dir, '%s_django%s.%s' % (part[0], django_version, part[1]))
    output_file = '%s/%s_%s.%s' % (env.project['project'], part[0], env.environment, part[1])

    # Generate conf file from template
    conf = ''
    output = io.StringIO()
    try:
        with open(input_file, 'r') as input:
            for line in input:
                output.write(line % variables)
        conf = output.getvalue()
    finally:
        output.close()

    # Shows conf file and optionally saves it
    print(conf)
    if console.confirm('Save to %s?' % output_file, default=False):
        with open(output_file, 'w') as output:
            output.write(conf)


###########
# Vagrant #
###########

def _vagrant():
    """(work in progress)"""
    # change from the default user to 'vagrant'
    env.user = 'vagrant'
    # connect to the port-forwarded ssh
    env.hosts = ['127.0.0.1:2222']

    # use vagrant ssh key
    result = local('vagrant ssh_config | grep IdentityFile', capture=True)
    env.key_filename = result.split()[1]


##################
# Linux commands #
##################

def adduser(username, password):
    """Creates remote user (with required username/password) and uploads ~/.ssh/id_rsa.pub as authorized_keys"""
    _require_environment()

    # New user to be created
    env.remote_user = username
    env.remote_password = password
    env.remote_home = '/home/%(remote_user)s' % env

    # Needs to connect as root (or sudoer)
    env.user = prompt('Remote root or sudoer?', default=env.user)
    env.password = None

    # Creates user, if it doesn't exist already
    if files.exists(env.remote_home):
        print('User %(remote_user)s already exists on %(environment)s!' % env)
    else:
        sudo('useradd -d%(remote_home)s -s/bin/bash -m -U %(remote_user)s' % env)
        sudo('echo "%(remote_user)s:%(remote_password)s" | sudo chpasswd' % env)
        # TODO: not all distributions use group sudo for sudoers (e.g.: old Ubuntu uses admin)
        # TODO: sudoers should not have to use password
        sudo('adduser %(remote_user)s sudo' % env)
        sudo('mkdir %(remote_home)s/.ssh' % env)
        put('~/.ssh/id_rsa.pub', '%(remote_home)s/.ssh/authorized_keys' % env, use_sudo=True, mode=0o644)
        sudo('chown -R %(remote_user)s:%(remote_user)s %(remote_home)s/.ssh' % env)

    # Continues as newly created user
    env.user = env.remote_user
    env.password = None

def install_git():
    """Installs (most recent) git from source"""
    local_git_version = sudo(LOCAL_GIT_VERSION)
    newest_git_version = run(NEWEST_GIT_VERSION)
    if local_git_version != newest_git_version:
        git_file = 'git-%s' % newest_git_version
        apt_get_update()
        sudo('apt-get -y -qq install build-essential')
        sudo('apt-get -y -qq install git-core')
        sudo('apt-get -y -qq install libcurl4-gnutls-dev')
        sudo('apt-get -y -qq install libexpat1-dev')
        sudo('apt-get -y -qq install gettext')
        sudo('apt-get -y -qq install libz-dev')
        sudo('apt-get -y -qq install libssl-dev')
        sudo('wget --quiet https://www.kernel.org/pub/software/scm/git/%s.tar.gz' % git_file)
        sudo('tar -xzf %s.tar.gz' % git_file)
        with cd(git_file):
            sudo('make --silent prefix=/usr/local all > /dev/null')
            sudo('make --silent prefix=/usr/local install  > /dev/null')

def apt_get_update():
    """Updates apt-get repositories, if needed"""
    temp_dir = run('echo ${TMPDIR:-"/tmp/"}')
    temp_file = os.path.join(temp_dir, 'apt-get-update-done')
    today = datetime.date.today().strftime('%d/%m/%y')
    if files.exists(temp_file):
        last_date_run = run('cat %s' % temp_file)
    else:
        last_date_run = ''
    if last_date_run != today:
        sudo('apt-get update')
        run('echo %s > %s' % (today, temp_file))

def hostname(name):
    """Updates server /etc/hosts and /etc/hostname"""
    files.sed('/etc/hosts', '.*', '127.0.0.1 %s' % name, limit='^127.0.0.1 ', use_sudo=True)
    sudo('mv /etc/hostname /etc/hostname.bak && echo %s > /etc/hostname' % name)
    sudo('hostname %s' % name)

def check_cpu():
    """Check CPU usage"""
    with settings(warn_only=True):
        run('mpstat')
        run('ps -eo pcpu,pid,user,args | sort -k 1 -r | head -10')

def check_memory():
    """Check memory usage"""
    with settings(warn_only=True):
        run('free -m')

def check_disk():
    """Check disk usage"""
    with settings(warn_only=True):
        run('df -h')

def check_io():
    """Check I/O statistics"""
    with settings(warn_only=True):
        run('iostat')


##################
# MySQL commands #
##################

def install_mysql():
    """Installs MySQL"""
    password = prompt('Password for MySQL root?', default='')
    apt_get_update()
    sudo('DEBIAN_FRONTEND=noninteractive apt-get -y -qq install mysql-server libmysqlclient-dev')
    with settings(warn_only=True):
        sudo('mysqladmin -u root password %s' % password)
        sudo(MYSQL_PREFIX % "\"ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY '%s';\"" % password)

def _get_database_name():
    """Gets database dictionary either from ENVS or form Django settings.py"""
    _require_environment()
    database = env.project.get('database', None)
    if not database:
        django.settings_module(_interpolate('%(project)s.%(settings)s'))
        database = django_settings.DATABASES['default']
    return database

def _database_exists():
    """Checks for existence of database"""
    _require_environment()
    database = _get_database_name()
    with settings(hide('warnings'), warn_only=True):
        result = run(MYSQL_PREFIX % "\"SHOW DATABASES LIKE '%(NAME)s';\"" % database)
        if database['NAME'] in result:
            return True
        else:
            print('Database %(NAME)s does not exist' % database)
            return False

def drop_database():
    """CAREFUL! - Destroys (DROP) MySQL database according to env's settings.py"""
    _require_environment()
    database = _get_database_name()
    if _database_exists():
        if console.confirm('ATTENTION! This will destroy current database! Confirm?', default=False):
            with settings(hide('warnings'), warn_only=True):
                result = run(MYSQL_PREFIX % "\"DROP DATABASE %(NAME)s;\"" % database)

def create_database():
    """Creates MySQL database according to env's settings.py, if not already there"""
    database = _get_database_name()
    with settings(hide('warnings'), warn_only=True):
        result = run(MYSQL_PREFIX % "\"CREATE DATABASE %(NAME)s DEFAULT CHARACTER SET utf8;\"" % database)
        if result.succeeded:
            run(MYSQL_PREFIX % "\"CREATE USER '%(USER)s'@'localhost' IDENTIFIED BY '%(PASSWORD)s';\"" % database)
            run(MYSQL_PREFIX % "\"GRANT ALL ON %(NAME)s.* TO '%(USER)s'@'localhost';\"" % database)
            # run(MYSQL_PREFIX % "\"ALTER USER '%(USER)s'@'localhost' IDENTIFIED WITH mysql_native_password BY '%(PASSWORD)s';\"" % database)

def backup_database():
    """
    Backup server's database and copy tar.gz to local ../backup dir
    """
    _require_environment()
    database = _get_database_name()
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
            run('mysqldump %s -u %s -p%s %s > %s/%s.sql' % (
                '-h %s' % database['HOST'] if database.get('HOST', None) else '',
                database['USER'],
                database['PASSWORD'],
                database['NAME'],
                path,
                env.project['project'],
            ))

            # Backup extra files
            extra_backup_files = env.project.get('extra_backup_files', [])
            for file in extra_backup_files:
                run('cp -R %s %s/' % (file, path))

            # Create .tar.gz and removes uncompressed files
            with hide('stdout'):
                run('tar -czvf %s.tar.gz %s/' % (path, path))
            run('rm -rf %s/' % path)

            # Download backup?
            if console.confirm('Download backup?'):
                return get('%s.tar.gz' % path, '../backup')

def restore_database(filename):
    """
    Restore server's database with .sql file contained in filename
    """
    _require_environment()
    database = _get_database_name()
    with prefix(_django_prefix()):
        with cd(_django_project_dir()):
            # Uploads tar file
            tarfile = os.path.basename(filename)
            basename = tarfile[:tarfile.index('.tar.gz')]
            if console.confirm('Upload backup?'):
                put(filename, '../backup/%s' % tarfile)

            # Drop and recreate current database
            drop_database()
            create_database()

            # Restore MySQL
            # To avoid silly mistakes, instead of using project's user & password, uses root's
            with cd('../'):
                run('tar -xzvf backup/%s' % tarfile)
                run('mysql -u root -p %s < backup/%s/%s.sql' % (
                    #database['USER'],
                    #database['PASSWORD'],
                    database['NAME'],
                    basename,
                    env.project['project'],
                ))

            # Restore extra files
            extra_backup_files = env.project.get('extra_backup_files', [])
            for file in extra_backup_files:
                run('cp -R ../backup/%s/%s ./%s' % (basename, os.path.basename(file), os.path.dirname(file)))

            # Removes uncompressed files, but leaves .tar.gz
            run('rm -rf ../backup/%s' % basename)


###################
# Apache commands #
###################

def install_apache():
    """Installs Apache and mod_wsgi"""
    apt_get_update()
    sudo ('apt-get -y -qq install apache2 apache2-mpm-worker libapache2-mod-wsgi')

def setup_apache():
    """Configures Apache"""
    if files.exists(_interpolate('/etc/apache2/sites-enabled/%(virtualenv)s.conf')):
        print('Apache conf for %(environment)s already exists' % env)
    else:
        sudo(_interpolate('ln -s %s /etc/apache2/sites-enabled/%%(virtualenv)s.conf' % APACHE_CONF))
        sudo('apache2ctl restart')

def generate_apache_conf(django_version=None):
    """Generates Apache conf file. Requires: path to WSGI conf file."""
    _require_environment()

    site_packages_dir = '%s/%s' % (_interpolate(VIRTUALENV_DIR), SITE_PACKAGES_DIR % _get_python_version())
    config_dir        = _interpolate(CONFIG_DIR)
    host_aliases      = env.project.get('host_aliases', '')
    if host_aliases:
        host_aliases  = 'ServerAlias %s' % host_aliases

    _generate_conf('apache.conf', {
        'host':              env.project['host'],
        'host_aliases':      host_aliases,
        'site_packages_dir': site_packages_dir,
        'static_admin_dir':  '%s/django/contrib/admin/media' % site_packages_dir,
        'project_dir':       _interpolate(DJANGO_PROJECT_DIR),
        'media_dir':         _interpolate(MEDIA_DIR),
        'static_dir':        _interpolate(STATIC_DIR),
        'config_dir':        config_dir,
        'wsgi_file':         'wsgi_%s.py' % env.environment,
    }, django_version)

def generate_wsgi_conf(django_version=None):
    """Generates WSGI conf file"""
    _require_environment()
    _generate_conf('wsgi.py', {
        'project': env.project['project'],
        'settings': env.project['settings'],
        'site_packages': SITE_PACKAGES_DIR % _get_python_version(),
    }, django_version)
    local(_interpolate('cp %(project)s/wsgi_%(environment)s.py %(project)s/wsgi.py'))

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
    """Installs Python 2.7, setuptools, pip, virtualenv, virtualenvwrapper"""
    _require_environment()
    # TODO: Install Python from source, regardless of Linux distribution
    apt_get_update()
    sudo('apt-get -y -qq install python python2.7 python2.7-dev pkg-config gcc')
    sudo('apt-get -y -qq install python-setuptools python-bs4')
    sudo('easy_install pip')
    sudo('pip install virtualenv')
    sudo('pip install virtualenvwrapper')
    with settings(warn_only=True):
        sudo(_interpolate('mkdir -p %(workon)s'))
        sudo(_interpolate('chmod g+w %(workon)s'))
        sudo(_interpolate('chown %%(user)s:%%(user)s %(workon)s') % env)

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
        print(_interpolate('virtualenv %(virtualenv)s already exists'))
    else:
        with prefix(_virtualenvwrapper_prefix()):
            run(_interpolate('mkvirtualenv --no-site-packages %(virtualenv)s'))
            with hide('commands'):
                print('virtualenv %s created with python %s\n' % (env.project['virtualenv'], run(GET_PYTHON_VERSION)))

def python_version():
    """Tries to figure out Python version on server side"""
    _require_environment()
    print('Python version on virtualenv %s: %s' % (env.project['virtualenv'], _get_python_version()))

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
        print(_interpolate('project %(project)s already exists, updating'))
        remote('git pull origin %s' % branch)
    else:
        with cd(_interpolate(VIRTUALENV_DIR)):
            run(_interpolate('git clone %(git_repo)s %(project)s'))
            if branch != 'master':
                remote('git fetch origin %s:%s' % (branch, branch))
                remote('git checkout %s' % branch)

def extra_commands():
    """Issue commands contained in env.project['EXTRA_COMMANDS']"""
    _require_environment()
    extra_commands = env.project.get('extra_commands', [])
    with settings(hide('warnings'), warn_only=True):
        for command in extra_commands:
            remote(command)

def remote(command):
    """Issues a generic command at project's directory level"""
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
    settings_file = _interpolate('%(project)s/%(settings)s.py')
    apache_file   = _interpolate('%(project)s/apache_%(environment)s.conf')
    wsgi_file     = _interpolate('%(project)s/wsgi_%(environment)s.py')
    if not os.path.exists(settings_file):
        abort('There is no %s - create one, and commit' % settings_file)
    if not os.path.exists(apache_file):
        abort('There is no Apache conf %s - use task "generate_apache_conf" to generate one, and commit' % apache_file)
    if not os.path.exists(wsgi_file):
        abort('There is no WSGI conf %s - use task "generate_wsgi_conf" to generate one, and commit' % wsgi_file)

    # Configures virtualenv and clones git repo
    _setup_virtualenv()
    _clone_gitrepo()

    # Issues extra commands at project's level, if any
    extra_commands()

    # Sets up Apache, MySQL
    setup_apache()
    if _database_exists():
        database = _get_database_name()
        print('Database %(NAME)s already exists' % database)
    else:
        drop_database()
        create_database()

    # Install Python packages & Django
    pip_install()
    update_project()

def pip_install():
    """Uses pip to install needed requirements"""
    _require_environment()
    remote(_interpolate(PIP_INSTALL_PREFIX))

def touch_project():
    """Touches WSGI file to reset Apache"""
    remote(_interpolate('touch %s' % WSGI_CONF))

def status_project():
    """Checks git log and status"""
    remote('glogg -n 20 && echo "" && git status')

def update_project():
    """Updates server from git pull"""
    _require_environment()

    # Grants write rights on log dir for the admin group
    log_dir = '%s/log' % _interpolate(VIRTUALENV_DIR)
    if files.exists(log_dir):
        sudo('chmod -R g+w %s' % log_dir)

    # Updates from git, issues Django syncdb, South migrate, Collecstatic and resets Apache
    branch = env.project.get('git_branch', 'master')
    with prefix(_django_prefix()):
        with cd(_django_project_dir()):
            with settings(hide('warnings'), warn_only=True):
                run('git fetch origin %s:%s' % (branch, branch))
            run('git checkout %s' % branch)
            with settings(hide('warnings'), warn_only=True):
                run('git pull origin %s' % branch)
                # run('django-admin syncdb') deprecated since Django 1.9
                run('django-admin migrate')
                run(_interpolate('touch %s' % WSGI_CONF))
                run('django-admin collectstatic --noinput')

def check_log():
    """Tails Django log"""
    _require_environment()
    with prefix(_django_prefix()):
        with cd(_django_project_dir()):
            logfile = '../log/%s.log' % env.project['project']
            run('tail -100f %s' % logfile)


def find_in_log(string):
    """Finds string parameter in Django logs"""
    _require_environment()
    with prefix(_django_prefix()):
        with cd(_django_project_dir()):
            run('grep -i %s ../log/*' % string)


#####################
# The Big Bootstrap #
#####################

def bootstrap(username, password):
    """Installs EVERYTHING from scratch! Requires username/password definition for remote user"""
    _require_environment()

    adduser(username, password)
    hostname(env.project['project'])
    install_python()
    install_git()
    install_apache()
    install_mysql()
    setup_project()
