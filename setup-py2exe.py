# NOTE:  This setup.py is ONLY for building the win32 .exe of cfv
# For all other purposes, install using the Makefile

from distutils.core import setup
import py2exe

setup(name="cfv",
	console=["cfv.py"],
	options={"py2exe": {"packages": ["encodings"]}},
	version="1.18.3",
	author="Matthew Mueller",
	license="GPL",
	url="http://cfv.sourceforge.net",
)
