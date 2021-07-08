from future import standard_library
standard_library.install_aliases()
from builtins import object
import codecs
import sys
from io import BytesIO, TextIOWrapper

from cfv import osutil


_badbytesmarker = u'\ufffe'


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
        if encoding == 'raw':
            self.decodeobj = self.fileobj
        else:
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
            if not self._encoding:
                self._encoding = osutil.getencoding(encoding)
        self._reset_decodeobj()

    def _reset_decodeobj(self):
        self.fileobj.seek(self._decode_start)
        if self._encoding:
            self.decodeobj = codecs.getreader(self._encoding)(self.fileobj, errors='markbadbytes')
        self._prevlineend = None

    def _readline(self, *args):
        line = self.decodeobj.readline(*args)
        # work around corrupted files that have crcrlf line endings.  (With StreamReaders in python versions >= 2.4, you no longer get it all as one line.)
        if self._prevlineend == '\r' and line == '\r\n':
            self._prevlineend = None
            return self._readline(*args)
        self._prevlineend = line[-1:]
        if self._encoding:
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
            return u''

    def peekline(self, *args):
        self._reset_decodeobj()
        try:
            return self._readline(*args)
        except UnicodeError:
            self._decode_errs = 1
            return u''

    def peeknextline(self, *args):
        try:
            return self._readline(*args)
        except UnicodeError:
            self._decode_errs = 1
            return u''

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
        f = gzip.GzipFile(mode='rb', fileobj=sys.stdin)
    else:
        f = gzip.open(filename, 'rb')
    return PeekFile(f, filename, encoding)


class NoCloseFile(object):
    def __init__(self, fileobj):
        self.write = fileobj.write
        self.close = fileobj.flush


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
            return PeekFileNonseekable(sys.stdin, filename, config.encoding)
        return PeekFile(open(filename, mode), filename, config.encoding)


def open_write(filename, config, force_raw=False):
    if force_raw or config.encoding == 'raw':
        encoding = None
        mode = 'wb'  # write all files in binary mode. (Otherwise we can run into problems with some encodings, and also with binary files like torrent)
    else:
        encoding = config.getencoding()
        mode = 'wt'

    if config.gzip >= 2 or (config.gzip >= 0 and filename[-3:].lower() == '.gz'):
        import gzip
        kwargs = {
            'filename': filename,
            'mode': mode.replace('t', ''),
        }
        if filename == '-':
            kwargs['fileobj'] = sys.stdout

        binary_file = gzip.GzipFile(**kwargs)
        if 't' in mode:
            return TextIOWrapper(binary_file, encoding)
        else:
            return binary_file
    else:
        if filename == '-':
            return NoCloseFile(sys.stdout)
        return open(filename, mode, encoding=encoding)
