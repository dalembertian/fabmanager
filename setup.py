# -*- coding: utf-8 -*-

import sys
import os
import re

import setuptools

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

with open("README.rst", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name='fabmanager',
    version=get_version('fabmanager'),
    author='Rubens Altimari',
    author_email='rubens@altimari.nl',
    description='Extra commands on top of Fabric to help managing Django projects in production environments',
    long_description=long_description,
    # long_description_content_type="text/markdown",
    url='https://github.com/dalembertian/fabmanager',

    packages=setuptools.find_packages(),
    include_package_data=True,
    zip_safe=False,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
     ],
    install_requires = [
        'fabric',
    ],
    python_requires='>=3.6',
)
