#! /usr/bin/env python

from distutils.core import setup
try:
	import py2exe
	extrakws = dict(console=["bin/cfv"])
except ImportError:
	extrakws = {}

setup(name="cfv",
	package_dir = {'': 'lib'},
	packages = ['cfv'],
	scripts = ['bin/cfv'],
	data_files = [("man/man1", ["cfv.1"])],
	options={"py2exe": {"packages": ["encodings"]}},
	version="2.0.x",
	author="Matthew Mueller",
	license="GPL",
	url="http://cfv.sourceforge.net",
	**extrakws
)
