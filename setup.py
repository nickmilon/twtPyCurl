# -*- coding: UTF-8 -*-

import re
import os
from setuptools import setup, find_packages

cur_path = os.path.dirname(os.path.realpath(__file__))
read_init = open(cur_path+'/twtPyCurl/__init__.py').read()

__version__ = re.search("__version__\s*=\s*'(.*)'", read_init, re.M).group(1)
__author__ = re.search("__author__\s*=\s*'(.*)'", read_init, re.M).group(1)

readme_content = ""
with open("README.rst") as f:
    for line in range(0, 4):  # just a few lines coz pypi does not fully  support ResT
        readme_content += f.readline()

assert __version__ is not None and __author__ is not None
setup(
    packages=find_packages(),
    package_data={'twtPyCurl': ['../twt_data/*.*']},

    name="twtPyCurl",
    version=__version__,
    author=__author__,
    author_email="nickmilon/gmail/com",
    maintainer="@nickmilon",
    url="https://github.com/nickmilon/twtPyCurl",
    description="A pycurl interface to Twitter’s rest and streaming API’s",
    long_description=readme_content,
    download_url="https://github.com/nickmilon/twtPyCurl/tarball/master",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.4",
        "Topic :: Software Development :: Libraries"
        ],
    license="GPL3",
    keywords=["Twitter", "API", "REST", "STREAM", "HTTP", "python"],
    zip_safe=False,
    tests_require=["nose"],
    dependency_links=[],
    install_requires=[
        'oauthlib',
        'simplejson',
        'pycurl'
    ],
)
