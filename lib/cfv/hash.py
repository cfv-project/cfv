from builtins import object

import hashlib
import os
import struct
import sys
from zlib import crc32


try:
    if os.environ.get('CFV_NOMMAP'):
        raise ImportError
    import mmap

    def dommap(fileno, len):  # generic mmap.  ACCESS_* args work on both nix and win.
        if len == 0:
            return b''  # mmap doesn't like length=0
        return mmap.mmap(fileno, len, access=mmap.ACCESS_READ)

    _nommap = 0
except ImportError:
    _nommap = 1

_MAX_MMAP = 2 ** 32 - 1
_FALLBACK_MMAP = 2 ** 31 - 1


md5 = hashlib.md5
sha1 = hashlib.sha1


def _getfilechecksum(filename, hasher, callback):
    if filename == '':
        f = sys.stdin.buffer
    else:
        f = open(filename, 'rb')

    def finish(m, s):
        while 1:
            x = f.read(65536)
            if not x:
                return m.digest(), s
            s += len(x)
            m.update(x)
            if callback:
                callback(s)

    if f == sys.stdin.buffer or _nommap or callback:
        return finish(hasher(), 0)
    else:
        s = os.path.getsize(filename)
        try:
            if s > _MAX_MMAP:
                # Work around python 2.[56] problem with md5 of large mmap objects
                raise OverflowError
            m = hasher(dommap(f.fileno(), s))
        except OverflowError:
            # mmap size is limited by C's int type, which even on 64 bit
            # arches is often 32 bits, so we can't use sys.maxint
            # either.  If we get the error, just assume 32 bits.
            mmapsize = min(s, _FALLBACK_MMAP)
            m = hasher(dommap(f.fileno(), mmapsize))
            f.seek(mmapsize)
            # unfortunatly, python's mmap module doesn't support the
            # offset parameter, so we just have to do the rest of the
            # file the old fashioned way.
            return finish(m, mmapsize)
        return m.digest(), s


def getfilechecksumgeneric(algo):
    if hasattr(hashlib, algo):
        hasher = getattr(hashlib, algo)
    else:
        def hasher():
            return hashlib.new(algo)
    return lambda filename, callback: _getfilechecksum(filename, hasher, callback), hasher().digest_size


class CRC32(object):
    digest_size = 4

    def __init__(self, s=b''):
        self.value = crc32(s)

    def update(self, s):
        self.value = crc32(s, self.value)

    def digest(self):
        return struct.pack('>I', self.value & 0xFFFFFFFF)


def getfilecrc(filename, callback):
    return _getfilechecksum(filename, CRC32, callback)
