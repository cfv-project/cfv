import os
import struct
import sys


def getscrwidth():
    w = -1
    try:
        from fcntl import ioctl
        try:
            from termios import TIOCGWINSZ
        except ImportError:
            from TERMIOS import TIOCGWINSZ
        tty = sys.stdin.isatty() and sys.stdin or sys.stdout.isatty() and sys.stdout or sys.stderr.isatty() and sys.stderr or None
        if tty:
            h, w = struct.unpack('h h', ioctl(tty.fileno(), TIOCGWINSZ, '\0' * struct.calcsize('h h')))
    except ImportError:
        pass
    if w > 0:
        return w
    c = os.environ.get('COLUMNS', 80)
    try:
        return int(c)
    except ValueError:
        return 80


scrwidth = getscrwidth()
