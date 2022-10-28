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


if hasattr(sys, 'getfilesystemencodeerrors'):
    fsencodeerrors = sys.getfilesystemencodeerrors()
else:
    fsencodeerrors = 'surrogateescape'


def getencoding(encoding, preferred=None):
    if encoding == 'raw':
        return fsencoding
    elif encoding == 'auto':
        if preferred:
            return preferred
        return preferredencoding
    else:
        return encoding


def getencodeerrors(encoding, default=None):
    if encoding == 'raw':
        return fsencodeerrors
    else:
        return default


fsencode = os.fsencode


try:
    os.stat(os.curdir + '\0foobarbaz')
    fs_nullsok = False  # if os.stat succeeded, it means the filename was cut off at the null (or the user has funny files ;)
except EnvironmentError:
    fs_nullsok = True
except (TypeError, ValueError):
    fs_nullsok = False


getcwdu = os.getcwd
curdiru = os.curdir
listdir = os.listdir


def path_join(*paths):
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


def strippath(filename, num='a', _splitdrivere=re.compile(r'[a-z]:[/\\]', re.IGNORECASE)):
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
