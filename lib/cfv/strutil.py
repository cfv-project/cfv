import codecs
import unicodedata
from StringIO import StringIO


def safesort(l):
    sl = []
    ul = []
    for s in l:
        if isinstance(s, str):
            sl.append(s)
        else:
            ul.append(s)
    sl.sort()
    ul.sort()
    l[:] = ul + sl


def showfn(s):
    if isinstance(s, str):
        return unicode(s, 'ascii', 'replace')
    return s


def codec_supports_readline(e):
    """Figure out whether the given codec's StreamReader supports readline.

    Some (utf-16) raise NotImplementedError(py2.3) or UnicodeError(py<2.3),
    others (cp500) are just broken.
    With recent versions of python (cvs as of 20050203), readline seems to
    work on all codecs.  Yay.
    """
    testa = u'a' * 80 + u'\n'
    testb = u'b' * 80 + u'\n'
    test = testa + testb
    r = codecs.getreader(e)(StringIO(test.encode(e)))
    try:
        return r.readline(100) == testa and r.readline(100) == testb
    except (NotImplementedError, UnicodeError):
        return 0


def chomp(line):
    if line[-2:] == '\r\n':
        return line[:-2]
    elif line[-1:] in '\r\n':
        return line[:-1]
    return line


def chompnulls(line):
    p = line.find('\0')
    if p < 0:
        return line
    else:
        return line[:p]


def uwidth(u):
    # TODO: should it return -1 or something for control chars, like wcswidth?
    # see http://www.cl.cam.ac.uk/~mgk25/ucs/wcwidth.c for a sample implementation
    # if isinstance(u, str):
    #     return len(u)
    w = 0
    # for c in unicodedata.normalize('NFC', u):
    for c in u:
        if c in (u'\u0000', u'\u200B'):  # null, ZERO WIDTH SPACE
            continue
        ccat = unicodedata.category(c)
        if ccat in ('Mn', 'Me', 'Cf'):  # 'Mark, nonspacing', 'Mark, enclosing', 'Other, format'
            continue
        cwidth = unicodedata.east_asian_width(c)
        if cwidth in ('W', 'F'):  # 'East Asian Wide', 'East Asian Full-width'
            w += 2
        else:
            w += 1
    return w


def lchoplen(line, max):
    """Return line cut on left so it takes at most max character cells when printed.

    >>> lchoplen(u'hello world',6)
    u'...rld'
    """
    if isinstance(line, str):
        if len(line) > max:
            return '...' + line[-(max - 3):], max
        return line
    elif len(line) * 2 <= max:
        return line
    chars = ['']
    w = 0
    for c in reversed(line):
        cw = uwidth(c)
        if w + cw > max:
            while w > max - 3:
                w -= uwidth(chars.pop(0))
            w += 3
            chars.insert(0, '...')
            break
        w += cw
        chars[0] = c + chars[0]
        if cw != 0:
            chars.insert(0, '')
    return ''.join(chars)


def rchoplen(line, max):
    """Return line cut on right so it takes at most max character cells when printed.

    >>> rchoplen(u'hello world',6)
    u'hel...'
    """
    if isinstance(line, str):
        if len(line) > max:
            return line[:max - 3] + '...', max
        return line
    elif len(line) * 2 <= max:
        return line
    chars = ['']
    w = 0
    for c in line:
        cw = uwidth(c)
        if w + cw > max:
            while w > max - 3:
                w -= uwidth(chars.pop())
            chars.append('...')
            w += 3
            break
        w += cw
        if cw == 0:
            chars[-1] += c
        else:
            chars.append(c)
    return ''.join(chars)


class CodecWriter:
    """Similar to codecs.StreamWriter, but str objects are decoded (as ascii) before then being passed to the the output encoder.
    This is necessary as some codecs barf on trying to encode ascii strings.
    """

    def __init__(self, encoding, stream, errors='strict'):
        self.__stream = codecs.getwriter(encoding)(stream, errors)

    def write(self, obj):
        if isinstance(obj, str):
            obj = unicode(obj, 'ascii')
        self.__stream.write(obj)

    def writelines(self, list):
        self.write(''.join(list))

    def __getattr__(self, name, getattr=getattr):
        """ Inherit all other methods from the underlying stream.
        """
        return getattr(self.__stream, name)
