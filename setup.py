#! /usr/bin/env python3
# -*- coding: UTF-8 -*-

from setuptools import setup, find_packages

install_requirements = [
    "django",
    "django-extensions",
    "swapper",
    "jsonfield"

    #"pillow",
]

debug_requirements = [
    "werkzeug",
    "PyOpenSSL",
]

install_requirements += debug_requirements

version=0.1

setup(name='spkbspider',
      version=version,
      license="MIT",
      zip_safe=False,
      platforms='Platform Independent',
      install_requires=install_requirements,
      extra_requires={
        "debug": debug_requirements
      }
      data_files=[('spkbspider', ['bm/LICENSE']),
      packages=["spkbspider", "spkbspider.apps.spideraccounts", "spkbspider.apps.spiderbroker", "spkbspider.apps.spiderpk"],
      package_data={
        '': ['templates/**.*'],
      },
      #ext_modules=distributions,
      test_suite="tests")
