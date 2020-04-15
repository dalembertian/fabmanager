# -*- coding: utf-8 -*-

import sys
import os
import re

from setuptools import setup, find_packages

def read(fname):
    """Reads an entire file and returns it as a single string"""
    with open(os.path.join(os.path.dirname(__file__), fname)) as f:
        return f.read()

def get_version(package):
    """Return package version as listed in `__version__` in `__init__.py`."""
    init_py = read(os.path.join(package, '__init__.py'))
    return re.search(
        "^__version__ = ['\"]([^'\"]+)['\"]", 
        init_py,
        re.MULTILINE
    ).group(1)

# Setup parameters that depend on the Python version
extra = {}
if sys.version_info >= (3,):
    extra['use_2to3'] = True
    #extra['convert_2to3_doctests'] = ['src/your/module/README.txt']
    #extra['use_2to3_fixers'] = ['your.fixers']

setup(
    name='fabmanager',
    version=get_version('fabmanager'),
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,

    author='Rubens Altimari',
    author_email='rubens@altimari.com.br',
    description='Standard (fabric) fabfile.py to be used by Introspection Software projects',
    license='BSD',
    url='https://github.com/raltimari/fabmanager',
    long_description=read('README.rst'),
    install_requires = [
        'fabric',
    ],
    **extra
)
