"""
Django settings for databridge project.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/5.2/ref/settings/
"""

import os
from pathlib import Path

import dj_database_url

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Optional: settings from a `.env` file next to manage.py (handy on
# PythonAnywhere, see README). Real environment variables win.
try:
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env", override=False)
except ImportError:
    pass


# SECURITY WARNING: keep the secret key used in production secret!
# In production (Render), DJANGO_SECRET_KEY is set as an env var — see render.yaml.
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or (
    "django-insecure-rthz^a19_8b&w3mt2t1h=dd054*$f3e8$y2x+=4)4e)=8x&gmy"
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get("DJANGO_DEBUG", "True") == "True"

ALLOWED_HOSTS = [h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if h.strip()]

# Render sets this automatically for the web service's own domain.
RENDER_EXTERNAL_HOSTNAME = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

CSRF_TRUSTED_ORIGINS = [f"https://{host}" for host in ALLOWED_HOSTS]

# Render terminates TLS at its proxy and forwards plain HTTP, so tell Django
# to trust the X-Forwarded-Proto header when deciding if a request is secure.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

if not DEBUG:
    # PythonAnywhere: tick "Force HTTPS" on the Web tab instead and set
    # DJANGO_SECURE_SSL_REDIRECT=False if pages keep redirecting to themselves.
    SECURE_SSL_REDIRECT = os.environ.get("DJANGO_SECURE_SSL_REDIRECT", "True") == "True"
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 7
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'accounts',
    'datasets',
    'core',
    'qda',
]

AUTH_USER_MODEL = 'accounts.User'

# Sign in with a username or an email address.
AUTHENTICATION_BACKENDS = ['accounts.backends.EmailOrUsernameBackend']

LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'datasets:catalog'
LOGOUT_REDIRECT_URL = 'core:home'

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'databridge.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'accounts.context_processors.account_features',
            ],
        },
    },
]

WSGI_APPLICATION = 'databridge.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases
# Render provides DATABASE_URL automatically when a Postgres database is
# attached to the web service; falls back to local SQLite when unset.

# (An empty DATABASE_URL, e.g. from a half-filled .env, counts as unset.)
DATABASES = {
    "default": dj_database_url.parse(
        os.environ.get("DATABASE_URL") or f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
    )
}


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Uploaded dataset files (MEDIA) go to Cloudinary in production when
# CLOUDINARY_URL is set (see render.yaml); locally they stay on disk.
# Static assets (CSS/JS/images shipped with the code) are always served by
# WhiteNoise — Cloudinary is only used for user-uploaded files.
CLOUDINARY_CONFIGURED = bool(os.environ.get("CLOUDINARY_URL"))

STORAGES = {
    "default": {
        "BACKEND": (
            "cloudinary_storage.storage.RawMediaCloudinaryStorage"
            if CLOUDINARY_CONFIGURED
            else "django.core.files.storage.FileSystemStorage"
        ),
    },
    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage.CompressedManifestStaticFilesStorage"
            if not DEBUG
            else "django.contrib.staticfiles.storage.StaticFilesStorage"
        ),
    },
}

# Logging
# By default Django only logs unhandled exceptions via "mail_admins", which
# does nothing without a configured mail backend/ADMINS. Send them to
# stderr/console unconditionally so they show up in Render's log stream too.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO"},
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
    },
}

# Email (password-reset links). Without DJANGO_EMAIL_HOST, emails are only
# printed to the console/log, and the "Forgot password?" links stay hidden
# in production. Any SMTP service works, e.g. Brevo or Resend.
EMAIL_HOST = os.environ.get("DJANGO_EMAIL_HOST", "")
if EMAIL_HOST:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_PORT = int(os.environ.get("DJANGO_EMAIL_PORT") or "587")
    EMAIL_HOST_USER = os.environ.get("DJANGO_EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = os.environ.get("DJANGO_EMAIL_HOST_PASSWORD", "")
    EMAIL_USE_TLS = os.environ.get("DJANGO_EMAIL_USE_TLS", "True") == "True"
    EMAIL_TIMEOUT = 20
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = os.environ.get("DJANGO_DEFAULT_FROM_EMAIL") or "Sustainable Solutions Tanzania <no-reply@localhost>"
EMAIL_CONFIGURED = bool(EMAIL_HOST) or DEBUG

# TakwimuBridge QDA (qda app)
# Let people use the tool without an account ("Continue without an account"
# on its sign-in page); their projects then stay in their browser only.
QDA_ALLOW_GUESTS = os.environ.get("DJANGO_QDA_ALLOW_GUESTS", "True") == "True"
# Largest single project upload (transcripts included), after unzipping.
QDA_MAX_UPLOAD_BYTES = int(os.environ.get("DJANGO_QDA_MAX_UPLOAD_MB") or "30") * 1024 * 1024

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
