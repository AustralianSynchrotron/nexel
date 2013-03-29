from __future__ import with_statement
from distutils.core import setup


with open('README.md', 'r') as f:
    long_description = f.read()


setup(
    name='Nexel',
    version='0.1',
    description='RESTful web-service to create and launch remote VM sessions using the OpenStack-based NeCTAR cloud',
    long_description=long_description,
    url='https://github.com/AustralianSynchrotron/nexel',
    author='Jarrod Sinclair',
    author_email='jsinclair@vpac.org',
    packages=['nexel', 'nexel/config', 'nexel/util'],
    install_requires=[
        'argparse',
        'tornado >= 2.4.1',
        'paramiko >= 1.9.0',
        'pycrypto >= 2.5',
        'formencode >= 1.2.6',
        'requests >= 1.0.2',
    ],
    classifiers=[
        'Environment :: OpenStack',
        'Intended Audience :: Information Technology',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: Modified BSD License',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python',
    ],
    license='Modified BSD',
    scripts=['nexeld', 'nexelcl'],
)
