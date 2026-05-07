"""
Settings de testing — solo para correr los experimentos y la suite de
integración localmente cuando las DBs reales (AWS) no son alcanzables.

Uso:
    DJANGO_SETTINGS_MODULE=settings_test python manage.py migrate
    DJANGO_SETTINGS_MODULE=settings_test python manage.py runserver

Hereda TODO de `settings.py` y sólo sobrescribe:
  - DATABASES → SQLite en archivo (`db_test.sqlite3`) para que persista
    entre el proceso de seed y el de runserver.
  - MONGO_URI → localhost (donde casi seguro NO hay Mongo). Los servicios
    S3/EC2 fallarán con LookupError → el reporte combinado degrada limpio.
"""
from settings import *  # noqa: F401,F403

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME':   'db_test.sqlite3',
    }
}

MONGO_URI     = 'mongodb://127.0.0.1:27017/'
MONGO_DB_NAME = 'bite_telemetry_test'

# Apaga el ratelimit-evaluation log spam
import logging  # noqa: E402
logging.disable(logging.WARNING)
