"""
Django settings for core project.

Experimentos Sprint 3 — ASR de Disponibilidad (Heartbeat + Active Redundancy)
y ASR de Seguridad (Rate Limiting / detección DoS).

Las credenciales se leen de variables de entorno; los valores por defecto
coinciden con los que configura `setups/setup-credentials.sh`.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure-$@+jmpv&75(*^h-l07s8a_a$1hk$fnoz+yshp%6nmab%(v+7mr',
)
DEBUG = os.environ.get('DJANGO_DEBUG', '1') == '1'
ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', '*').split(',')

# ---------------------------------------------------------------------------
# Apps & middleware
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'monitor_trafico',
    'monitor_servicios',
    'generador_reportes.apps.GeneradorReportesConfig',
    'recolector_inventarios',
    'api_gateway',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # Monitor de Tráfico — táctica de Rate Limiting / detección DoS
    'monitor_trafico.middleware.TrafficMonitorMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'
WSGI_APPLICATION = 'core.wsgi.application'
ASGI_APPLICATION = 'core.asgi.application'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# Bases de datos — leídas de variables de entorno con defaults consistentes
# con setups/setup-credentials.sh (PG_DB=bite_db, MONGO_DB=bite_telemetry).
# ---------------------------------------------------------------------------
DATABASES = {
    'default': {
        'ENGINE':   'django.db.backends.postgresql',
        'NAME':     os.environ.get('POSTGRES_DB',       'bite_db'),
        'USER':     os.environ.get('POSTGRES_USER',     'bite_user'),
        'PASSWORD': os.environ.get('POSTGRES_PASSWORD', 'Bite_KISS_2026!'),
        'HOST':     os.environ.get('POSTGRES_HOST',     '127.0.0.1'),
        'PORT':     os.environ.get('POSTGRES_PORT',     '5432'),
    }
}

MONGO_URI     = os.environ.get('MONGO_URI', 'mongodb://127.0.0.1:27017/')
MONGO_DB_NAME = os.environ.get('MONGO_DB_NAME', 'bite_telemetry')

# ---------------------------------------------------------------------------
# Validators / i18n / static
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE     = 'UTC'
USE_I18N      = True
USE_TZ        = True
STATIC_URL    = 'static/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ---------------------------------------------------------------------------
# Experimento ASR de disponibilidad — Heartbeat + Active Redundancy
# ---------------------------------------------------------------------------
# Instancias lógicas del Generador de Reportes que participan en el experimento.
# En AWS, cada nombre correspondería a una instancia EC2/ECS distinta.
REPORT_GENERATOR_INSTANCES = [
    'generador_reportes_1',
    'generador_reportes_2',
]

# Frecuencia de envío de heartbeats (segundos).
# Con 0.2 s de intervalo y umbral de 0.8 s → detección garantizada < 1 s (ASR1).
HEARTBEAT_INTERVAL_SECONDS = 0.2
