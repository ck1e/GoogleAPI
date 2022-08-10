from pathlib import Path, PurePath
from django.conf import settings

SECRET_KEY = 'django-insecure-oz@9(%1c7=ik7_^6-p5skz)tc-jbsnb8invg%9^-mb4%5-)x%p'

DEBUG = True

ALLOWED_HOSTS = [
    '.ngrok.io',
    '.127.0.0.1',
    '.localhost',
]

STATICFILES_DIRS = [
    Path(PurePath(settings.BASE_DIR, 'static')),
]
