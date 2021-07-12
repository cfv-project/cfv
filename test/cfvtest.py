#! /usr/bin/env python

#    cfvtest.py - initialization and utility stuff for cfv testing
#    Copyright (C) 2000-2005  Matthew Mueller <donut AT dakotacom DOT net>
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

from __future__ import print_function

from builtins import map
from builtins import object

import fnmatch
import imp
import importlib
import os
import shlex
import sys
import traceback
import unittest
from doctest import DocTestSuite
from glob import glob
from unittest import TestCase  # noqa: F401
from unittest import main


cfvenv = ''

cfvfn = None
ver_cfv = ver_mmap = ver_fchksum = None
runcfv = None
testpath = os.path.split(__file__)[0] or os.curdir
datapath = os.path.join(testpath, 'testdata')


class NullFile(object):
    def isatty(self):
        return 0

    def write(self, s):
        pass

    def writelines(self, l):
        pass

    def flush(self):
        pass

    def close(self):
        pass


nullfile = NullFile()


def expand_cmdline(cmd):
    argv = []
    for arg in shlex.split(cmd):
        if '*' in arg or '?' in arg or '[' in arg:
            argv.extend(glob(arg))
        else:
            argv.append(arg)
    return argv


def runcfv_exe(cmd, stdin=None, stdout=None, stderr=None, need_reload=0):
    import subprocess  # subprocess module only in python >= 2.4, but it works on windows, unlike commands

    def open_output(fn):
        if fn == '/dev/null' and not os.path.exists(fn):
            fn = 'nul'
        return open(fn, 'wb')

    p_stdin = p_stdout = p_stderr = subprocess.PIPE
    if stdin:
        p_stdin = open(stdin, 'rb')
    if stdout:
        p_stdout = open_output(stdout)
    else:
        p_stderr = subprocess.STDOUT
    if stderr:
        p_stderr = open_output(stderr)
    argv = [cfvfn] + expand_cmdline(cmd)
    proc = subprocess.Popen(argv, stdin=p_stdin, stdout=p_stdout, stderr=p_stderr)
    for f in p_stdin, p_stdout, p_stderr:
        if f not in (subprocess.PIPE, subprocess.STDOUT, None):
            f.close()
    obuf, ebuf = proc.communicate()
    if ebuf or obuf is None:
        assert not obuf
        o = ebuf
    else:
        o = obuf
    s = proc.returncode
    if o:
        if o[-2:] == '\r\n':
            o = o[:-2]
        elif o[-1:] in '\r\n':
            o = o[:-1]
    return s, o


# TODO: make the runcfv_* functions (optionally?) take args as a list instead of a string
def runcfv_py(cmd, stdin=None, stdout=None, stderr=None, need_reload=0):
    if stdin is not None and ver_fchksum:
        fileno = os.open(stdin, os.O_RDONLY | getattr(os, 'O_BINARY', 0))
        assert fileno >= 0
        saved_stdin_fileno = os.dup(sys.stdin.fileno())
        os.dup2(fileno, sys.stdin.fileno())
        os.close(fileno)

    from io import BytesIO, TextIOWrapper
    obuf = BytesIO()
    obuftext = TextIOWrapper(obuf)
    saved = sys.stdin, sys.stdout, sys.stderr, sys.argv
    cwd = os.getcwd()

    def open_output(file):
        if file:
            if file == "/dev/null":
                return nullfile
            return open(file, 'wt')
        else:
            return obuftext

    try:
        if stdin:
            sys.stdin = open(stdin, 'rt')
        else:
            sys.stdin = TextIOWrapper(BytesIO())
        sys.stdout = open_output(stdout)
        sys.stderr = open_output(stderr)
        sys.argv = [cfvfn] + expand_cmdline(cmd)
        # TODO: make this work with cfv 1.x as well so that we can benchmark compare them in internal mode.
        import cfv.cftypes
        importlib.reload(cfv.cftypes)  # XXX
        import cfv.common
        importlib.reload(cfv.common)  # XXX: hack until I can get all the global state storage factored out.
        if need_reload:
            import cfv.hash
            importlib.reload(cfv.hash)  # XXX: hack for environment variable changing
        cfv_ns = {
            '__name__': '__main__',
            '__file__': cfvfn,
            '__doc__': None,
            '__package__': None,
        }
        try:
            exec (cfv_compiled, cfv_ns)
            s = 'no exit?'
        except SystemExit as e:
            s = e.code
            if stdin:
                sys.stdin.close()
            if stdout:
                sys.stdout.close()
            if stderr:
                sys.stderr.close()
        except KeyboardInterrupt:
            raise
        except Exception:
            traceback.print_exc(file=obuftext)
            s = 1
    finally:
        sys.stdin, sys.stdout, sys.stderr, sys.argv = saved
        if 'saved_stdin_fileno' in locals():
            os.dup2(saved_stdin_fileno, sys.stdin.fileno())
            os.close(saved_stdin_fileno)
        os.chdir(cwd)
    obuftext.flush()
    o = obuf.getvalue().decode()
    if o:
        if o[-2:] == '\r\n':
            o = o[:-2]
        elif o[-1:] in '\r\n':
            o = o[:-1]
    return s, o


def get_version_flags():
    global ver_cfv, ver_fchksum, ver_mmap
    s, o = runcfv("--version", need_reload=1)
    if o.find('cfv ') >= 0:
        ver_cfv = o[o.find('cfv ') + 4:].splitlines()[0]
    else:
        ver_cfv = None
    ver_fchksum = o.find('fchksum') >= 0
    ver_mmap = o.find('mmap') >= 0


def setcfv(fn=None, internal=None):
    global cfvfn, cfv_compiled, runcfv

    if internal is not None:
        runcfv = internal and runcfv_py or runcfv_exe

    if fn is None:
        fn = os.path.join(testpath, 'cfv')

    assert os.path.isfile(fn)
    cfvfn = os.path.abspath(fn)
    _cfv_code = open(cfvfn, 'r').read().replace('\r\n', '\n').replace('\r', '\n')
    cfv_compiled = compile(_cfv_code, cfvfn, 'exec')

    # This is so that the sys.path modification of the wrapper (if it has one) will be executed..
    imp.load_source('cfvwrapper', cfvfn + '.py', open(cfvfn))

    get_version_flags()


def setenv(k, v):
    global cfvenv
    cfvenv = "%s=%s %s" % (k, v, cfvenv)
    os.environ[k] = v
    get_version_flags()


def my_import(name):
    mod = __import__(name)
    components = name.split('.')
    for comp in components[1:]:
        mod = getattr(mod, comp)
    return mod


def rfind(root, match):
    root = os.path.join(root, '')
    for path, dirs, files in os.walk(root):
        subpath = path.replace(root, '', 1)
        for file in files:
            if fnmatch.fnmatch(file, match):
                yield os.path.join(subpath, file)


def all_unittests_suite():
    modules_to_test = [os.path.splitext(f)[0].replace(os.sep, '.') for f in rfind(testpath, 'test_*.py')]
    assert modules_to_test
    alltests = unittest.TestSuite()
    for module in map(my_import, modules_to_test):
        alltests.addTest(unittest.findTestCases(module))

    import cfv.common
    libdir = os.path.split(cfv.common.__file__)[0]
    modules_to_doctest = ['cfv.' + os.path.splitext(f)[0].replace(os.sep, '.') for f in rfind(libdir, '*.py')]
    # TODO: better way to add files in test/ dir to doctest suite?
    modules_to_doctest.append('benchmark')
    assert 'cfv.common' in modules_to_doctest
    for name in modules_to_doctest:
        module = my_import(name)
        assert module.__name__ == name, (module, name)
        try:
            suite = DocTestSuite(module)
        except ValueError as e:
            if len(e.args) != 2 or e[1] != 'has no docstrings':
                print(e)
        else:
            alltests.addTest(suite)

    return alltests


if __name__ == '__main__':
    # initialize with default options
    setcfv(internal=1)

    main(defaultTest='all_unittests_suite')
