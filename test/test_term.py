import contextlib
import fcntl
import os
import pty
import struct
import sys
import termios

from cfv import term
from cfvtest import TestCase


@contextlib.contextmanager
def redirect_stdio_to_pty():
    orig_stdin = sys.stdin
    orig_stdout = sys.stdout
    master, slave = pty.openpty()
    try:
        sys.stdin = open(slave, 'rt')
        sys.stdout = open(os.dup(slave), 'wt')
        yield
    finally:
        os.close(master)
        sys.stdout.close()
        sys.stdout = orig_stdout
        sys.stdin.close()
        sys.stdin = orig_stdin


def set_terminal_size(termsize: os.terminal_size):
    fcntl.ioctl(sys.stdout.fileno(), termios.TIOCSWINSZ, struct.pack('HHHH', termsize.lines, termsize.columns, 0, 0))


class TermTestCase(TestCase):
    def test_getscrwidth(self):
        with redirect_stdio_to_pty():
            self.assertTrue(sys.stdin.isatty())
            self.assertTrue(sys.stdout.isatty())
            self.assertEqual(term.getscrwidth(), 80)
            set_terminal_size(os.terminal_size((123, 24)))
            self.assertEqual(term.getscrwidth(), 123)
