import os, sys, site

#Calculate the path based on the location of the WSGI script.
apache_configuration = os.path.dirname(os.path.abspath(__file__))
project              = os.path.dirname(apache_configuration)
workspace            = os.path.dirname(project)
site_packages        = os.path.dirname(os.path.join(workspace, '%(site_packages)s/'))

# Directories to add to sys.path
ALLDIRS = [site_packages, workspace, project]

# Remember original sys.path.
prev_sys_path = list(sys.path)

# Add each new site-packages directory.
for directory in ALLDIRS:
  site.addsitedir(directory)

# Reorder sys.path so new directories are at the front.
new_sys_path = []
for item in list(sys.path):
    if item not in prev_sys_path:
        new_sys_path.append(item)
        sys.path.remove(item)
sys.path[:0] = new_sys_path

print >> sys.stderr, sys.path

os.environ['DJANGO_SETTINGS_MODULE'] = '%(project)s.%(settings)s'

import django.core.handlers.wsgi
application = django.core.handlers.wsgi.WSGIHandler()
