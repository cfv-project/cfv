import os
import sys

from cfv import osutil


try:
    if os.environ.get('CFV_NOMMAP'):
        raise ImportError
    # mmap is broken in python 2.4.2 and leaks file descriptors
    if sys.version_info[:3] == (2, 4, 2):
        raise ImportError
    import mmap

    def dommap(fileno, len):  # generic mmap.  ACCESS_* args work on both nix and win.
        if len == 0:
            return ''  # mmap doesn't like length=0
        return mmap.mmap(fileno, len, access=mmap.ACCESS_READ)

    _nommap = 0
except ImportError:
    _nommap = 1

_MAX_MMAP = 2 ** 32 - 1
_FALLBACK_MMAP = 2 ** 31 - 1


def _getfilechecksum(filename, hasher, callback):
    if filename == '':
        f = sys.stdin
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

    if f == sys.stdin or _nommap or callback:
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


try:
    from hashlib import sha1 as sha_new
except ImportError:
    from sha import new as sha_new
try:
    from hashlib import md5 as md5_new
except ImportError:
    from md5 import new as md5_new


def getfilechecksumgeneric(algo):
    import hashlib
    if hasattr(hashlib, algo):
        hasher = getattr(hashlib, algo)
    else:
        def hasher():
            return hashlib.new(algo)
    return lambda filename, callback: _getfilechecksum(filename, hasher, callback), hasher().digest_size


def getfilesha1(filename, callback):
    return _getfilechecksum(filename, sha_new, callback)


try:
    if os.environ.get('CFV_NOFCHKSUM'):
        raise ImportError
    import fchksum

    try:
        if fchksum.version() < 5:
            raise ImportError
    except Exception:
        # can't use perror yet since config hasn't been done..
        sys.stderr.write('old fchksum version installed, using std python modules. please update.\n')
        raise ImportError

    def getfilemd5(filename, callback):
        if filename == '':
            f = sys.stdin
        else:
            f = open(filename, 'rb')
        if isinstance(filename, unicode):
            sname = filename.encode(osutil.fsencoding, 'replace')
        else:
            sname = filename
        c, s = fchksum.fmd5(sname, callback, 0.03, fileno=f.fileno())
        return c, s

    def getfilecrc(filename, callback):
        if filename == '':
            f = sys.stdin
        else:
            f = open(filename, 'rb')
        if isinstance(filename, unicode):
            sname = filename.encode(osutil.fsencoding, 'replace')
        else:
            sname = filename
        c, s = fchksum.fcrc32d(sname, callback, 0.03, fileno=f.fileno())
        return c, s
except ImportError:
    import struct

    try:
        from zlib import crc32 as _crc32
    except ImportError:
        from binascii import crc32 as _crc32

    class CRC32:
        digest_size = 4

        def __init__(self, s=''):
            self.value = _crc32(s)

        def update(self, s):
            self.value = _crc32(s, self.value)

        def digest(self):
            return struct.pack('>I', self.value & 0xFFFFFFFF)

    def getfilemd5(filename, callback):
        return _getfilechecksum(filename, md5_new, callback)

    def getfilecrc(filename, callback):
        return _getfilechecksum(filename, CRC32, callback)
