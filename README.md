# cfv – Command-line File Verify

cfv is a utility to test and create a wide range of checksum verification files.
It currently supports testing and creating sfv, sfvmd5, csv, csv2, csv4, md5, bsdmd5, sha1, sha224,
sha256, sha384, sha512, torrent and crc files.
Test-only support is available for par, par2.

cfv was originally written by Matthew Mueller ([original project home](http://cfv.sourceforge.net/)).
This is a [friendly fork of cfv](https://github.com/cfv-project/cfv) maintained by David Gnedt.

[![Build Status](https://img.shields.io/github/checks-status/cfv-project/cfv/python3)](https://github.com/cfv-project/cfv/actions?query=branch%3Apython3)
[![Supported Python versions](https://img.shields.io/pypi/pyversions/cfv.svg)](https://pypi.org/project/cfv/)
[![License](https://img.shields.io/pypi/l/cfv.svg)](https://pypi.org/project/cfv/)
[![Latest PyPI version](https://img.shields.io/pypi/v/cfv.svg)](https://pypi.org/project/cfv/)
[![Number of PyPI downloads](https://img.shields.io/pypi/dm/cfv.svg)](https://pypi.org/project/cfv/)

## Requirements

Python ≥ 3.5 – older versions might work, but are unsupported.
For Python 2 support, see the [python2 branch](https://github.com/cfv-project/cfv/tree/python2).

### Optional

* [Python Imaging Library (PIL)](https://www.pythonware.com/products/pil/) or
  [Pillow](https://python-pillow.org/) – only needed if you want to create the
  dimensions column of .crc files.

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

## Alternative Tools

Here is a community-compiled list of alternative tools that cover some of cfv's functionality (without warranty):

* GNU coreutils \*sum: md5sum, sha1sum, sha224sum, sha256sum, sha384sum, sha512sum, ...
* cksfv
* [rhash](https://github.com/rhash/RHash) (with `-rc` does more or less the same thing as cfv, performance is good and it supports most hash formats including bittorrent. It lacks cfv's `-m` though.)
* aria2c (to verify torrent checksums)
* bsdsfv (limited to 1024 files for some reason)
* pure-sfv (doesn't seem to display progress information, even with `-v`)
* [bcfv](https://github.com/jarppiko/bcfv) (a Bash frontend to checksum programs (SHA, Blake3, MD5))

## Copying

This program is free software; you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation; either version 2 of the License, or (at your option) any later
version.
See the file `COPYING` for more information.
