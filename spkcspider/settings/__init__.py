"""
Django settings for spkcspider project.

Generated by 'django-admin startproject' using Django 1.11.2.

For more information on this file, see
https://docs.djangoproject.com/en/1.11/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.11/ref/settings/
"""

import os

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.11/howto/deployment/checklist/


ALLOWED_HOSTS = []

FILE_UPLOAD_HANDLERS = [
    'django.core.files.uploadhandler.MemoryFileUploadHandler',
    "spkcspider.apps.spider.functions.LimitedTemporaryFileUploadHandler",
]


# Application definition

INSTALLED_APPS = [
    'widget_tweaks',
    'spkcspider.apps.spider_accounts',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',  # for flatpages
    'django.contrib.flatpages',
    'spkcspider.apps.spider',
]
try:
    import django_extensions  # noqa: F401
    INSTALLED_APPS.append('django_extensions')
except ImportError:
    pass


MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.contrib.flatpages.middleware.FlatpageFallbackMiddleware',
]

ROOT_URLCONF = 'spkcspider.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'spkcspider.apps.spider_accounts.context_processors.'
                'is_registration_open',
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]
WSGI_APPLICATION = 'spkcspider.wsgi.application'

# Password validation
# https://docs.djangoproject.com/en/1.11/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',  # noqa: E501
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',  # noqa: E501
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',  # noqa: E501
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',  # noqa: E501
    },
]


# Internationalization
# https://docs.djangoproject.com/en/1.11/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


STATICFILES_DIRS = [
    # add node_modules as node_modules under static
    ("node_modules", os.path.join(BASE_DIR, "node_modules"))
]

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.11/howto/static-files/


STATIC_ROOT = 'static/'
STATIC_URL = '/static/'

MEDIA_ROOT = 'media/'
MEDIA_URL = '/media/'


CAPTCHA_CHALLENGE_FUNCT = 'captcha.helpers.math_challenge'
CAPTCHA_FONT_SIZE = 40

LOGIN_URL = "auth:login"
LOGIN_REDIRECT_URL = "auth:profile"
LOGOUT_REDIRECT_URL = "home"

AUTH_USER_MODEL = 'spider_accounts.SpiderUser'
SPIDER_HASH_ALGORITHM = "sha512"
# as hex digest
MAX_HASH_SIZE = 128
MIN_STRENGTH_EVELATION = 2
# change size of request token.
# Note: should be high to prevent token exhaustion
# TOKEN_SIZE = 30
# OPEN_FOR_REGISTRATION = True # allow registration
# ALLOW_USERNAME_CHANGE = True # allow users changing their username

## captcha field names (REQUIRED) # noqa: E266
SPIDER_CAPTCHA_FIELD_NAME = "sunglasses"

## required if using mysql  # noqa: E266
# MYSQL_HACK = True

## Update dynamic content, ... after migrations, default=true  # noqa: E266
# UPDATE_DYNAMIC_AFTER_MIGRATION = False

## Enable captchas  # noqa: E266
# INSTALLED_APPS.append('captcha')
# USE_CAPTCHAS = True

## Enable direct file downloads (handled by webserver)  # noqa: E266
# disadvantage: blocking access requires file name change
# DIRECT_FILE_DOWNLOAD = True

# ALLOWED_CONTENT_FILTER

# DELETION_PERIODS_COMPONENTS
# DELETION_PERIOD_CONTENTS
# RATELIMIT_FUNC_CONTENTS
# FILET_FILE_DIR
# FILE_NONCE_SIZE
# DEFAULT_QUOTA_USER
# TAG_LAYOUT_PATHES
# user fieldname of quota
FIELDNAME_QUOTA = "quota"


SPIDER_BLACKLISTED_MODULES = [
    # untested, will fail
    "spkcspider.apps.spider.models.contents.TravelProtection"
]

# how many user components per page
COMPONENTS_PER_PAGE = 25
# how many user contents per page
CONTENTS_PER_PAGE = 25
# how many raw/serialized results per page?
# Note: verifier doesn't support multi page contents yet, so put it higher
SERIALIZED_PER_PAGE = 50
# how many search parameters are allowed
MAX_SEARCH_PARAMETERS = 30

SITE_ID = 1
