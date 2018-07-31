#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#
from setuptools import setup

setup(name='saarvv',
      version='0.0.1',
      description='Python client for the saarvv',
      author='Raphael Jacob (ski7777)',
      author_email='r.jacob2002@gmail.com',
      packages=['saarvv'],
      dependency_links=['https://github.com/ski7777/saarvv-client'],
      install_requires=['fptf', 'lxml', 'pytz']
      )
