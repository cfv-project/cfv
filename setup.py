import re

from setuptools import setup


RE_VERSION = r"^__version__\s*=\s*'([^']*)'$"


def _read(path):
    with open(path, 'rt', encoding='utf8') as f:
        return f.read()


def _get_version(path):
    re_version = re.compile(RE_VERSION)
    with open(path, 'rt') as f:
        for line in f:
            m = re_version.match(line)
            if m is not None:
                return m.group(1)
    return None


version = _get_version('lib/cfv/common.py')

setup(
    version=version,
    author='Lisa Gnedt (Current Maintainer)',
    author_email='%s@%s' % ('cfv-project', 'davizone.at'),
    # license and license_expression is defined here and not in pyproject.toml
    # due to backward compatibility issues with older setuptools versions.
    # See: https://github.com/pypa/setuptools/issues/4903
    license='GPL-2.0-or-later AND MIT',
    license_expression='GPL-2.0-or-later AND MIT',
    license_files=('COPYING', 'lib/cfv/BitTorrent/LICENSE.txt'),
)
