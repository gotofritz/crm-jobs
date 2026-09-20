"""Django settings — plan 001 §5.

Everything that differs between a laptop and the VPS is read from the
environment (AGENTS.md, "Data & Secrets"); the defaults are the laptop. Running
with `DJANGO_DEBUG=false` and no `DJANGO_SECRET_KEY` stops the process at boot
rather than serving traffic with a key that is in this file.

`manage.py check --deploy` is clean under production settings, and `poe qa`
runs it — see the `check-deploy` task in `Taskfile.toml`.

Reference: https://docs.djangoproject.com/en/6.1/howto/deployment/checklist/
"""

import os
from pathlib import Path

from config.env import as_bool, as_list, as_required

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = as_bool("DJANGO_DEBUG", default=True)

# The only secret in the project. Local development gets a key that announces
# itself as unusable; anything else has to supply a real one.
DEV_SECRET_KEY = "django-insecure-local-development-only-do-not-deploy"
if DEBUG:
    SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "").strip() or DEV_SECRET_KEY
else:
    SECRET_KEY = as_required("DJANGO_SECRET_KEY")

# Empty is correct with DEBUG on — Django allows localhost itself — and is an
# error with DEBUG off, which `check --deploy` reports as security.W020.
ALLOWED_HOSTS = as_list("DJANGO_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = as_list("DJANGO_CSRF_TRUSTED_ORIGINS")


# Security
# Caddy terminates TLS and redirects http to https one hop before Django, so
# Django redirecting as well would buy nothing and loop unless it were told to
# trust a proxy header (plan 001 §5). That is what security.W008 asks for, and
# the only check silenced here.
SECURE_SSL_REDIRECT = False
SILENCED_SYSTEM_CHECKS = ["security.W008"]

SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

# One year, the value the HSTS preload list requires. Lower it through the
# environment while a certificate or a domain is still being sorted out.
SECURE_HSTS_SECONDS = 0 if DEBUG else int(os.environ.get("DJANGO_HSTS_SECONDS", "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "jobs",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Directly after SecurityMiddleware, so a static file is answered before any
    # of the session, auth and CSRF work that serving one does not need.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Database
# https://docs.djangoproject.com/en/6.1/ref/settings/#databases

# The file lives outside the code: at the repository root locally, under
# /var/lib on the VPS (AGENTS.md, "Data & Secrets"). WAL lets a read run while
# a write is in flight, and IMMEDIATE takes the write lock up front so a busy
# database fails fast instead of half way through a transaction.
DATABASE_PATH = Path(os.environ.get("DJANGO_DB_PATH", BASE_DIR.parent / "db.sqlite3"))
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATABASE_PATH,
        "OPTIONS": {
            "init_command": "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;",
            "transaction_mode": "IMMEDIATE",
        },
    }
}


# Password validation
# https://docs.djangoproject.com/en/6.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.1/topics/i18n/

LANGUAGE_CODE = "en-gb"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.1/howto/static-files/

# `static/` holds what is served: the stylesheet Tailwind compiles from
# `assets/`, and later the vendored HTMX. `staticfiles/` is what collectstatic
# writes, and is not in the repository.
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR.parent / "staticfiles"
STATICFILES_DIRS = [BASE_DIR.parent / "static"]

# WhiteNoise serves them, so Caddy needs no static-file configuration at all.
#
# Compressed rather than CompressedManifest: hashed filenames would make every
# rendered `{% static %}` tag depend on collectstatic having run first, which
# means the test suite and any DEBUG-off run need a build step before they can
# render a page. The app is one page behind basic_auth, so far-future caching
# buys little; the gzip and brotli copies are the part worth having.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}


# Email
# https://docs.djangoproject.com/en/6.1/topics/email/#topic-email-configuration

# Nothing in the app sends mail. The console backend keeps an accidental send
# visible locally; in production Django's SMTP default stands, so the checklist
# has nothing to object to (mail.E001).
if DEBUG:
    MAILERS = {
        "default": {
            "BACKEND": "django.core.mail.backends.console.EmailBackend",
        },
    }
