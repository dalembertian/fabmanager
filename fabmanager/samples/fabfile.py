# encoding: utf-8
# Sample project fabfile.py (should be on the same level as manage.py, see README)

from fabmanager import fabfile
from fabmanager.fabfile import *

# Environments
WORKON_HOME = '/opt/python'
GIT_REPO    = 'git@git.assembla.com:myproject.git'
PROJECT     = 'myproject'

ENVS.update({
    'production': {
        'host': 'www.mysite.com.br',
        'git_repo': GIT_REPO,
        'workon': WORKON_HOME,
        'project': PROJECT,
        'virtualenv': 'prod',
        'settings': 'settings_production',
        },
    'beta': {
        'host': 'beta.mysite.com.br',
        'git_repo': GIT_REPO,
        'workon': WORKON_HOME,
        'project': PROJECT,
        'virtualenv': 'beta',
        'git_branch': 'beta',
        'settings': 'settings_beta',
        },
    })

def prod():
    fabfile._setup_environment('production')

def beta():
    fabfile._setup_environment('beta')
