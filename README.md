# cfv - Command-line File Verify

cfv is a utility to test and create a wide range of checksum verification files.
It currently supports testing and creating sfv, sfvmd5, csv, csv2, csv4, md5, bsdmd5, sha1, sha224,
sha256, sha384, sha512, torrent and crc files.
Test-only support is available for par, par2.

cfv was originally written by Matthew Mueller ([original project home](http://cfv.sourceforge.net/)).
This is a [friendly fork of cfv](https://github.com/cfv-project/cfv) maintained by David Gnedt.

[![Build Status](https://travis-ci.org/cfv-project/cfv.svg?branch=master)](https://travis-ci.org/cfv-project/cfv)

## Requirements

Python ≥ 2.4 <https://www.python.org/>

### Optional

* Python Imaging Library (PIL) <https://www.pythonware.com/products/pil/> or
  Pillow <https://python-pillow.org/>
  (only needed if you want to create the dimensions column of .crc files)
* python-fchksum <http://code.fluffytapeworm.com/projects>
  (may speed up checksumming speed a bit, especially if your python was not built with the mmap module.)

## Install

You can get the latest release from the [Github releases page](https://github.com/cfv-project/cfv/releases).

### Unix

1. `make install` (which just runs `python setup.py install --prefix=/usr/local`)
2. read man page, `cfv -h`, etc. have fun
3. optional: run tests to verify correct operation: `cd test; ./test.py`

### Windows

1. maybe `python setup.py install` will do something useful? At least it should stick the
   libraries in the right place
2. move `cfv.bat` to somewhere in the path
3. edit the `cfv.bat` file if your Python is installed somewhere other than `C:\python24`

## Contributions

Contributions are welcome, just open a pull request ☺️

## Copying

This program is free software; you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation; either version 2 of the License, or (at your option) any later
version.
See the file `COPYING` for more information.
