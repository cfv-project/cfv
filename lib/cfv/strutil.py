from builtins import str

import binascii
import unicodedata

from cfv import osutil


def safesort(seq):
    sl = []
    ul = []
    for s in seq:
        if isinstance(s, str):
            sl.append(s)
        else:
            ul.append(s)
    sl.sort()
    ul.sort()
    seq[:] = ul + sl


def showfn(s):
    return osutil.fsencode(s).decode(osutil.fsencoding, errors='replace')


def chomp(line):
    if line[-2:] == '\r\n':
        return line[:-2]
    elif line[-1:] in '\r\n':
        return line[:-1]
    return line


def chompnulls(line):
    p = line.find(b'\0')
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
        if c in ('\u0000', '\u200B'):  # null, ZERO WIDTH SPACE
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

    >>> lchoplen('hello world',6)
    '...rld'
    """
    if isinstance(line, bytes):
        if len(line) > max:
            return b'...' + line[-(max - 3):]
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

    >>> rchoplen('hello world',6)
    'hel...'
    """
    if isinstance(line, bytes):
        if len(line) > max:
            return line[:max - 3] + b'...'
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


def hexlify(data):
    return binascii.hexlify(data).decode('ascii')


def unhexlify(data):
    return binascii.unhexlify(data)
