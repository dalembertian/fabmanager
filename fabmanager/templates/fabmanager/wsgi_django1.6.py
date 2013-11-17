# encoding: utf-8
# https://docs.djangoproject.com/en/1.6/howto/deployment/wsgi/

import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', '%(project)s.%(settings)s')

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
