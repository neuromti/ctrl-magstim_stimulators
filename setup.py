#!/usr/bin/env python

from setuptools import setup

setup(
    name='horizonmagpy',
    version='1',
    description='A Python toolbox for controlling Magstim TMS stimulators via serial communication',
    classifiers=['Development Status :: 5 - Production/Stable',
                 'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
                 'Programming Language :: Python :: 2.7',
                 'Programming Language :: Python :: 3'],
    keywords='TMS Magstim',
    packages=find_packages()
    package_data={'horizonmagpy':['*.yaml']},
    python_requires='>=2.7, !=3.0.*, !=3.1.*, !=3.2.*',
    install_requires=['pyserial']
)
