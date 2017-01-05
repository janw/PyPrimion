#!/usr/bin/env python3

from distutils.core import setup

setup(name='PyPrimion',
      version='0.1.1',
      description='Webinterface handler for the Primion Prime Web Systems time tracking',
      author='Jan Willhaus',
      author_email='mail@janwillhaus.de',
      license='MIT (X11) License',
      py_modules=['pyprimion'],
      url='https://github.com/Janwillhaus/PyPrimion',
      packages=None,
      install_requires=['beautifulsoup4', 'requests'],
      long_description=open('README.md').read(),
      )
