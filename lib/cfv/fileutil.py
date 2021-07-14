from builtins import object

import codecs
import sys
from io import BytesIO, TextIOWrapper

from cfv import osutil


_badbytesmarker = '\ufffe'


def _markbadbytes(exc):
    return _badbytesmarker, exc.end


codecs.register_error('markbadbytes', _markbadbytes)


class PeekFile(object):
    def __init__(self, fileobj, filename=None, encoding='auto'):
        self.fileobj = fileobj
        self._init_decodeobj(encoding)
        self.name = filename or fileobj.name

    def _init_decodeobj(self, encoding):
        self._encoding = None
        self._decode_start = 0
        self._decode_errs = 0
        if encoding == 'auto':
            magic = self.fileobj.read(4)
            # utf32 are tested first, since utf-32le BOM starts the same as utf-16le's.
            if magic in (b'\x00\x00\xfe\xff', b'\xff\xfe\x00\x00'):
                self._encoding = 'UTF-32'
            elif magic[:2] in (b'\xfe\xff', b'\xff\xfe'):
                self._encoding = 'UTF-16'
            elif magic.startswith(b'\xef\xbb\xbf'):
                self._encoding = 'UTF-8'
                self._decode_start = 3
        if self._encoding is None:
            self._encoding = osutil.getencoding(encoding)
        self._encodeerrors = osutil.getencodeerrors(encoding, default='markbadbytes')
        self._reset_decodeobj()

    def _reset_decodeobj(self):
        self.fileobj.seek(self._decode_start)
        if self._encoding is not None:
            self.decodeobj = codecs.getreader(self._encoding)(self.fileobj, errors=self._encodeerrors)
        self._prevlineend = None

    def _readline(self, *args):
        line = self.decodeobj.readline(*args)
        # work around corrupted files that have crcrlf line endings.  (With StreamReaders in python versions >= 2.4, you no longer get it all as one line.)
        if self._prevlineend == '\r' and line == '\r\n':
            self._prevlineend = None
            return self._readline(*args)
        self._prevlineend = line[-1:]
        if self._encodeerrors == 'markbadbytes':
            badbytecount = line.count(_badbytesmarker)
            if badbytecount:
                raise UnicodeError('%r codec: %i decode errors' % (self._encoding, badbytecount))
        return line

    def peek(self, *args):
        self.fileobj.seek(0)
        return self.fileobj.read(*args)

    def peekdecoded(self, *args):
        self._reset_decodeobj()
        try:
            return self.decodeobj.read(*args)
        except UnicodeError:
            self._decode_errs = 1
            return ''

    def peekline(self, *args):
        self._reset_decodeobj()
        try:
            return self._readline(*args)
        except UnicodeError:
            self._decode_errs = 1
            return ''

    def peeknextline(self, *args):
        try:
            return self._readline(*args)
        except UnicodeError:
            self._decode_errs = 1
            return ''

    def _done_peeking(self, raw):
        if raw:
            fileobj = self.fileobj
            fileobj.seek(0)
            del self.decodeobj
        else:
            self._reset_decodeobj()
            fileobj = self.decodeobj
            del self.fileobj
        self.peeknextline = None
        self.peekdecoded = None
        self.peekline = None
        self.peek = None
        self.readline = self._readline
        self.read = fileobj.read
        self.seek = fileobj.seek

    def seek(self, *args):
        self._done_peeking(raw=1)
        return self.seek(*args)

    def readline(self, *args):
        self._done_peeking(raw=0)
        return self._readline(*args)

    def read(self, *args):
        self._done_peeking(raw=1)
        return self.read(*args)


def PeekFileNonseekable(fileobj, filename, encoding):
    return PeekFile(BytesIO(fileobj.read()), filename, encoding)


def PeekFileGzip(filename, encoding):
    import gzip
    if filename == '-':
        f = gzip.GzipFile(mode='rb', fileobj=sys.stdin.buffer)
    else:
        f = gzip.open(filename, 'rb')
    return PeekFile(f, filename, encoding)


class NoCloseFile(object):
    def __init__(self, fileobj):
        self.fileobj = fileobj

    def __getattr__(self, attr):
        if attr == 'close':
            attr = 'flush'
        return getattr(self.fileobj, attr)


def open_read(filename, config):
    # read all files in binary mode (since, pars are binary, and we
    # don't always know the filetype when opening, just open everything
    # binary.  The text routines should cope with all types of line
    # endings anyway, so this doesn't hurt us.)
    mode = 'rb'
    if config.gzip >= 2 or (config.gzip >= 0 and filename[-3:].lower() == '.gz'):
        return PeekFileGzip(filename, config.encoding)
    else:
        if filename == '-':
            return PeekFileNonseekable(sys.stdin.buffer, filename, config.encoding)
        return PeekFile(open(filename, mode), filename, config.encoding)


def open_write(filename, config, force_raw=False):
    if config.gzip >= 2 or (config.gzip >= 0 and filename[-3:].lower() == '.gz'):
        import gzip
        kwargs = {
            'filename': filename,
            'mode': 'wb',
        }
        if filename == '-':
            kwargs['fileobj'] = sys.stdout.buffer

        binary_file = gzip.GzipFile(**kwargs)
    else:
        if filename == '-':
            binary_file = NoCloseFile(sys.stdout.buffer)
        else:
            binary_file = open(filename, 'wb')

    if force_raw:
        return binary_file
    else:
        return TextIOWrapper(binary_file, config.getencoding(), errors=config.getencodeerrors())
