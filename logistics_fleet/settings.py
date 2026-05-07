"""
Django settings for logistics_fleet – LogiTracker SaaS Platform.
"""
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

# ──────────────────────────────────────────────────────────
#  SECURITY
# ──────────────────────────────────────────────────────────
SECRET_KEY = 'django-insecure-@=e60d%tkx6scp83qrx2z&u88@g5s-v2tg777(@jgq5mrslhst'
DEBUG = True

ALLOWED_HOSTS = ['127.0.0.1', 'localhost']

# ──────────────────────────────────────────────────────────
#  INSTALLED APPS
# ──────────────────────────────────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',          # required by allauth

    # Third-party
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'crispy_forms',
    'crispy_bootstrap5',

    # Local
    'fleet',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',   # allauth ≥ 0.56
]

ROOT_URLCONF = 'logistics_fleet.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',  # required by allauth
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'logistics_fleet.wsgi.application'

# ──────────────────────────────────────────────────────────
#  DATABASE  (MySQL / mysqlclient)
# ──────────────────────────────────────────────────────────
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'logistics_db',
        'USER': 'root',
        'PASSWORD': 'TvS@2511',
        'HOST': 'localhost',
        'PORT': '3306',
        'OPTIONS': {
            'charset': 'utf8mb4',
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}

# ──────────────────────────────────────────────────────────
#  AUTH
# ──────────────────────────────────────────────────────────
AUTH_USER_MODEL = 'fleet.User'
LOGIN_REDIRECT_URL = 'dashboard'
LOGIN_URL = 'login'

AUTHENTICATION_BACKENDS = [
    'fleet.backends.RoleBasedBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ──────────────────────────────────────────────────────────
#  DJANGO-ALLAUTH  (Google OAuth 2.0)
# ──────────────────────────────────────────────────────────
SITE_ID = 1

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
        'APP': {
            # ⚠ Replace with your real credentials from Google Cloud Console
            'client_id': 'YOUR_GOOGLE_CLIENT_ID',
            'secret': 'YOUR_GOOGLE_CLIENT_SECRET',
            'key': '',
        },
    }
}

ACCOUNT_LOGIN_METHODS = {'username', 'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'username*', 'password1*', 'password2*']
ACCOUNT_EMAIL_VERIFICATION = 'optional'
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_LOGIN_ON_GET = True

# ──────────────────────────────────────────────────────────
#  EMAIL  (console for dev; swap to SMTP in production)
# ──────────────────────────────────────────────────────────
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = 'noreply@logitracker.in'

# ──────────────────────────────────────────────────────────
#  CRISPY FORMS
# ──────────────────────────────────────────────────────────
CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap5'
CRISPY_TEMPLATE_PACK = 'bootstrap5'

# ──────────────────────────────────────────────────────────
#  INTERNATIONALISATION
# ──────────────────────────────────────────────────────────
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

# ──────────────────────────────────────────────────────────
#  STATIC & MEDIA FILES
# ──────────────────────────────────────────────────────────
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ──────────────────────────────────────────────────────────
#  MISC
# ──────────────────────────────────────────────────────────
BASE_URL = 'http://127.0.0.1:8000'   # used in invitation emails
