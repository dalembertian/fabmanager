==========
fabmanager
==========

.. image:: https://secure.travis-ci.org/raltimari/fabmanager.png?branch=master
   :target: http://travis-ci.org/#!/raltimari/fabmanager

.. _fabmanager-synopsis:

fabmanager is a set of useful tasks to be used with Fabric, a Python tool for application deployment and systems administration over SSH, to manage Django projects. It provides the backbone for commands such as::

    setup   Sets up a new environment
    status  Checks git log and status
    python  Tries to figure out Python version on server side
    update  Updates server from git pull
    apache  Generates Apache conf file. Requires: path to WSGI conf file.
    wsgi    Generates WSGI conf file
    backup  Backup server's database and copy tar.gz to local ../backup dir
    remote  Issues a generic command at project's directory


fabmanager currently depends on Django, fabric, virtualenv, virtualenvwrapper, git, MySQL.


.. _fabmanager-contents:

Contents
========

.. contents::
    :local:


.. _fabmanager-installation:

Installation
============

Currently fabmanager should be installed from source. The easiest way is using pip::

    $ pip install [-e] git+git://github.com/raltimari/fabmanager.git

The option -e asks pip to install the complete source files. It can also be installed by first cloning the repository and then running setup.py, or even pip::

    $ git clone git://github.com/raltimari/fabmanager.git
    $ cd fabmanager
    $ python setup.py install
      or
    $ pip install .


.. _fabmanager-instructions:


Instructions
============


* Create a fabfile.py at the Django project's directory (e.g.: $VIRTUAL_ENV/project), with the following imports::

    from fabmanager import fabfile
    from fabmanager.fabfile import *

* Extend (do not replace!) the ENVS dictionary. See below for a complete description of all possible entries.

* Define tasks for each environment, that can be specified in the command line (e.g.: fab myenv update)::

    def myenv():
        fabfile._setup_environment('myenv')

* Revise other configuration strings, and override them if needed

* That's it!

.. _fabmanager-reference:


Reference
=========

ENVS dictionary

An empty ENVS dictionary is defined by fabmanager/fabfile.py. Each project's fabfile.py must extend (not replace!) this dictionary with an update() command::

    ENVS.update({
        'myenv': {
            'host': 'servername.domain.com',
            'workon': '/opt/python',
            'virtualenv': 'myvirtualenv',
            'project': 'myproject',
            'settings': 'settings',
            etc.

Below is a complete list of parameters. Starred items are usually mandatory::

  * host                Name or IP of the remote server
    host_alias          Host alias(es), separated by ' ', for Apache conf file
  * workon              Parent of the virtualenv directory (equals virtualenvwrapper WORKON_HOME)
  * virtualenv          Virtualenv name
  * project             Project name. Actual project location is thus given by $workon/$virtualenv/$project
  * settings            settings.py being used (e.g.: 'settings', 'settings_custom')
    git_repo            Git repo, mandatory if setup is being made by fabmanager
    git_branch          If not provided, 'master' is assumed
    extra_commands      List of commands to be issued at the project's dir level, during setup, after git clone
    extra_backup_files  List of extra files, besides the database SQL dump, that should go into a backup (from project' dir level)


.. _fabmanager-todo:


To Do List
==========

* Remove dependency on virtualenvwrapper
* Replace use of __file__ to locate templates (not PEP-302 compliant) with calls to pkg_resources

.. _fabmanager-license:


License
=======

This software is licensed under the `New BSD License`. See the ``LICENSE``
file in the top distribution directory for the full license text.
