import os
import sys


def getscrwidth():
    tty = sys.stdin.isatty() and sys.stdin or sys.stdout.isatty() and sys.stdout or sys.stderr.isatty() and sys.stderr or None
    if tty:
        try:
            termsize = os.get_terminal_size(tty.fileno())
            if termsize.columns > 0:
                return termsize.columns
        except (AttributeError, ValueError, OSError):
            pass

    try:
        return int(os.environ['COLUMNS'])
    except (KeyError, ValueError):
        return 80


scrwidth = getscrwidth()
