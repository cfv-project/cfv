# cfv – Command-line File Verify

cfv is a utility to test and create a wide range of checksum verification files.
It currently supports testing and creating sfv, sfvmd5, csv, csv2, csv4, md5, bsdmd5, sha1, sha224,
sha256, sha384, sha512, torrent and crc files.
Test-only support is available for par, par2.

cfv was originally written by Matthew Mueller ([original project home](http://cfv.sourceforge.net/)).
This is a [friendly fork of cfv](https://github.com/cfv-project/cfv) maintained by David Gnedt.

[![Build Status](https://travis-ci.org/cfv-project/cfv.svg?branch=master)](https://travis-ci.org/cfv-project/cfv)
[![Supported Python versions](https://img.shields.io/pypi/pyversions/cfv.svg)](https://pypi.org/project/cfv/)
[![License](https://img.shields.io/pypi/l/cfv.svg)](https://pypi.org/project/cfv/)
[![Latest PyPI version](https://img.shields.io/pypi/v/cfv.svg)](https://pypi.org/project/cfv/)
[![Number of PyPI downloads](https://img.shields.io/pypi/dm/cfv.svg)](https://pypi.org/project/cfv/)

## Requirements

Python ≥ 2.7 – older versions might work, but are unsupported.
Python 3 is not supported yet, see [issue #8](https://github.com/cfv-project/cfv/issues/8).

### Optional

* [Python Imaging Library (PIL)](https://www.pythonware.com/products/pil/) or
  [Pillow](https://python-pillow.org/) – only needed if you want to create the
  dimensions column of .crc files.
* [python-fchksum](http://code.fluffytapeworm.com/projects) – may speed up checksumming
  speed a bit, especially if your python was not built with the mmap module.

## Install

You can get the latest releases via the [Python Package Index (PyPI)](https://pypi.org/project/cfv/)
or from the [Github releases page](https://github.com/cfv-project/cfv/releases).
Other distribution ways are work-in-progress, see [issue #4](https://github.com/cfv-project/cfv/issues/4).

### From PyPI

If you have a working Python installation with pip, you can follow these installation steps:

1. `pip install cfv`
2. read man page `man cfv` or read usage `cfv -h` and have fun ☺️

### From Source

Download a snapshot from the [Github releases page](https://github.com/cfv-project/cfv/releases)
or checkout the development version via Git.

1. `python setup.py install`
2. read man page `man cfv` or read usage `cfv -h` and have fun ☺️
3. optional: run tests to verify correct operation: `cd test; ./test.py`

## Contributions

Contributions are welcome, just open a pull request ☺️

## Copying

This program is free software; you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation; either version 2 of the License, or (at your option) any later
version.
See the file `COPYING` for more information.
