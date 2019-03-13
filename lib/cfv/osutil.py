import locale
import os
import re
import sys


if hasattr(locale, 'getpreferredencoding'):
    preferredencoding = locale.getpreferredencoding() or 'ascii'
else:
    preferredencoding = 'ascii'

if hasattr(sys, 'getfilesystemencoding'):
    fsencoding = sys.getfilesystemencoding()
else:
    fsencoding = preferredencoding


def getencoding(encoding, preferred=None):
    assert encoding != 'raw'
    if encoding == 'auto':
        if preferred:
            return preferred
        return preferredencoding
    else:
        return encoding


try:
    os.stat(os.curdir + u'\0foobarbaz')
    fs_nullsok = 0  # if os.stat succeeded, it means the filename was cut off at the null (or the user has funny files ;)
except EnvironmentError:
    fs_nullsok = 1
except TypeError:
    fs_nullsok = 0

if hasattr(os, 'getcwdu'):
    def getcwdu():
        try:
            return os.getcwdu()
        except UnicodeError:
            return os.getcwd()
else:
    def getcwdu():
        d = os.getcwd()
        try:
            return unicode(d, fsencoding)
        except UnicodeError:
            return d

curdiru = unicode(os.curdir)

if sys.hexversion >= 0x020300f0:
    listdir = os.listdir
else:
    def listdir(path):
        r = []
        for fn in os.listdir(path):
            try:
                r.append(unicode(fn, fsencoding))
            except UnicodeError:
                r.append(fn)
        return r


def path_join(*paths):
    # The assumption here is that the only reason a raw string path
    # component can get here is that it cannot be represented in unicode
    # (Ie, it is not a valid encoded string)
    # In that case, we convert the parts that are valid back to raw
    # strings and join them together.  If the unicode can't be
    # represented in the fsencoding, then there's nothing that can be
    # done, and this will blow up.  Oh well.
    # TODO: try not using list compr here?
    if [p for p in paths if isinstance(p, str)]:
        # import traceback
        # traceback.print_stack()
        # perror('path_join: non-unicode args ' + repr(paths))

        npaths = []
        for p in paths:
            if isinstance(p, unicode):
                npaths.append(p.encode(fsencoding))
            else:
                npaths.append(p)
        paths = npaths
    return os.path.join(*paths)


def path_split(filename):
    """Split a path into a list of path components.

    >>> path_split(os.path.join('a1','b2','c3','d4'))
    ['a1', 'b2', 'c3', 'd4']
    >>> path_split(os.path.join('a1','b2','c3',''))
    ['a1', 'b2', 'c3', '']
    >>> path_split('a1')
    ['a1']
    """
    head, tail = os.path.split(filename)
    parts = [tail]
    while 1:
        head, tail = os.path.split(head)
        if tail:
            parts.insert(0, tail)
        else:
            if head:
                parts.insert(0, head)
            break
    return parts


def strippath(filename, num='a', _splitdrivere=re.compile(r'[a-z]:[/\\]', re.I)):
    """Strip off path components from the left side of the filename.

    >>> strippath(os.path.join('c:','foo','bar','baz'))
    'baz'
    >>> path_split(strippath(os.path.join('c:','foo','bar','baz'), 'n'))
    ['c:', 'foo', 'bar', 'baz']
    >>> path_split(strippath(os.path.join('c:','foo','bar','baz'), 0))
    ['foo', 'bar', 'baz']
    >>> path_split(strippath(os.path.join(os.sep,'foo','bar','baz'), 0))
    ['foo', 'bar', 'baz']
    >>> path_split(strippath(os.path.join('c:','foo','bar','baz'), 1))
    ['bar', 'baz']
    >>> strippath(os.path.join('c:','foo','bar','baz'), 2)
    'baz'
    >>> strippath(os.path.join('c:','foo','bar','baz'), 3)
    'baz'
    """
    if num == 'a':  # split all the path off
        return os.path.split(filename)[1]
    if num == 'n':  # split none of the path
        return filename

    if _splitdrivere.match(filename, 0, 3):  # we can't use os.path.splitdrive, since we want to get rid of it even if we are not on a dos system.
        filename = filename[3:]
    if filename[0] == os.sep:
        filename = filename.lstrip(os.sep)

    if num == 0:  # only split drive letter/root slash off
        return filename

    parts = path_split(filename)
    if len(parts) <= num:
        return parts[-1]
    return os.path.join(*parts[num:])


def fcmp(f1, f2):
    import filecmp
    return filecmp.cmp(f1, f2, shallow=0)
