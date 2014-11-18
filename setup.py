'''
Created on Feb 24, 2013
@author: nickmilon
see: https://docs.python.org/2/distutils/setupscript.html
'''
from setuptools import setup, find_packages
version = '0.1.1'

# work around since dependency_links seems don't work with newer versions of pip,
# needs to uninstall it manually on uninstall
import pip
pip.main(['install', "git+https://github.com/nickmilon/Hellas.git@master"])
# @TODO remove above when we upload Hellas to PyPi

print('installing packages:{!s}'.format(find_packages()))

setup(
    packages=find_packages(),
    package_data={'twtPyCurl': ['../data/*.json', '../data/*txt']},

    name="twtPyCurl",
    version=version,
    author="nickmilon",
    author_email="nickmilon/gmail/com",
    maintainer="nickmilon",
    url="https://github.com/nickmilon/twtPyCurl",
    description="python utilities",
    long_description="see: readme",
    download_url="https://github.com/nickmilon/twtPyCurl",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GPL3",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.4",
        "Topic :: HTTP"
        ],
    license="GPL3",
    keywords=["Twitter", "API", "REST", "STREAM" "HTTP", "python"],
    zip_safe=False,
    tests_require=["nose"],
    dependency_links=[],
    install_requires=[
        'oauthlib',
        'simplejson',
        'pycurl',
        'Hellas'
    ],
)
