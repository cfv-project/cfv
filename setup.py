#! /usr/bin/env python

import re
from setuptools import setup, find_packages


RE_VERSION = r"^__version__\s*=\s*'([^']*)'$"


def _read(path):
    with open(path, 'r') as f:
        return f.read()


def _get_version(path):
    re_version = re.compile(RE_VERSION)
    with open(path, 'r') as f:
        for line in f:
            m = re_version.match(line)
            if m is not None:
                return m.group(1)
    return None


version = _get_version('lib/cfv/common.py')

setup(
    name='cfv',
    version=version,
    description='Command-line File Verify - versatile file checksum creator and verifier',
    long_description=_read('README.md'),
    long_description_content_type='text/markdown',
    url='https://github.com/cfv-project/cfv',
    author='David Gnedt (Current Maintainer)',
    author_email='%s@%s' % ('cfv-project', 'davizone.at'),
    license='GPL',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Topic :: System :: Archiving',
        'Topic :: Utilities',
        'License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
    ],
    keywords='cfv checksum verify sfv csv crc bsdmd5 md5sum sha1sum sha224sum sha256sum sha384sum sha512sum torrent par par2',
    project_urls={
        'Bug Tracker': 'https://github.com/cfv-project/cfv/issues',
        'Source Code': 'https://github.com/cfv-project/cfv',
        'Original Project': 'http://cfv.sourceforge.net/',
    },
    python_requires='>=2.7, <3',
    packages=find_packages('lib'),
    package_dir={'': 'lib'},
    include_package_data=True,
    data_files=[('man/man1', ['cfv.1'])],
    entry_points={
        'console_scripts': [
            'cfv=cfv.common:main',
        ],
    },
)
