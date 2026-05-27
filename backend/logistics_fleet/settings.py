"""
Django settings for logistics_fleet – LogiTracker SaaS Platform.
"""
from pathlib import Path
import os
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ──────────────────────────────────────────────────────────
#  SECURITY
# ──────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-@=e60d%tkx6scp83qrx2z&u88@g5s-v2tg777(@jgq5mrslhst')

# Set DEBUG to False in production
DEBUG = 'RENDER' not in os.environ

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

ALLOWED_HOSTS = ['127.0.0.1', 'localhost']
RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

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
    'whitenoise.middleware.WhiteNoiseMiddleware',
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
#  DATABASE  (Render & TiDB via dj-database-url)
# ──────────────────────────────────────────────────────────
DATABASES = {
    'default': dj_database_url.config(
        default='mysql://root:TvS@2511@localhost:3306/logistics_db',
        conn_max_age=600,
        ssl_require=False  # TiDB Serverless usually requires this, dj-database-url parses ?ssl_mode=VERIFY_IDENTITY automatically
    )
}

# TiDB requires specific SQL mode
DATABASES['default']['OPTIONS'] = {
    'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
    'charset': 'utf8mb4',
}

# ──────────────────────────────────────────────────────────
#  AUTH
# ──────────────────────────────────────────────────────────
AUTH_USER_MODEL = 'fleet.User'
LOGIN_REDIRECT_URL = 'dashboard'
LOGIN_URL = 'login'

# ── Session Security ───────────────────────────────────────────────────
# Sessions expire when the browser is closed (no "keep me logged in" by default)
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
# Hard cap: even persistent sessions expire after 12 hours of inactivity
SESSION_COOKIE_AGE = 43200          # 12 hours in seconds
# Refresh the expiry on every request so active users aren't kicked out
SESSION_SAVE_EVERY_REQUEST = True

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
#  EMAIL  (SMTP Configuration)
# ──────────────────────────────────────────────────────────
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'albinssuresh1883@gmail.com'
EMAIL_HOST_PASSWORD = 'qpyf gpyz yqvu evmh' # Use Google App Passwords for security
DEFAULT_FROM_EMAIL = 'noreply@logicontrol.in'

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
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Enable WhiteNoise compression and caching
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ──────────────────────────────────────────────────────────
#  MISC
# ──────────────────────────────────────────────────────────
BASE_URL = 'http://127.0.0.1:8000'   # used in invitation emails

# ──────────────────────────────────────────────────────────
#  GOOGLE MAPS
# ──────────────────────────────────────────────────────────
MAPS_API_KEY = 'YOUR_GOOGLE_MAPS_API_KEY'   # Replace with your key
