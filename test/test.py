#! /usr/bin/env python

#    test.py - tests for cfv (Command-line File Verify)
#    Copyright (C) 2000-2013  Matthew Mueller <donut AT dakotacom DOT net>
#    Copyright (C) 2018-2024  David Lisa Gnedt <cfv-project AT davizone DOT at>
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

from builtins import chr
from builtins import zip
from builtins import map
from builtins import str
from builtins import filter
from builtins import range
from builtins import object

import getopt
import gzip
import locale
import operator
import os
import re
import shutil
import stat
import string
import sys
import tempfile
import time
import traceback
import zlib
from functools import reduce
from glob import glob

import cfvtest


if hasattr(locale, 'getpreferredencoding'):
    preferredencoding = locale.getpreferredencoding() or 'ascii'
else:
    preferredencoding = 'ascii'


def is_encodable(s, enc=preferredencoding):
    try:
        s.encode(enc)
        return True
    except UnicodeError:
        return False


fmt_info = {
    # name:
    #   (hascrc, hassize, cancreate, available, istext, preferredencoding, iscoreutils)
    'sha512':
        (1, 0, 1, 1, 1, preferredencoding, 1),
    'sha384':
        (1, 0, 1, 1, 1, preferredencoding, 1),
    'sha256':
        (1, 0, 1, 1, 1, preferredencoding, 1),
    'sha224':
        (1, 0, 1, 1, 1, preferredencoding, 1),
    'sha1':
        (1, 0, 1, 1, 1, preferredencoding, 1),
    'md5':
        (1, 0, 1, 1, 1, preferredencoding, 1),
    'bsdmd5':
        (1, 0, 1, 1, 1, preferredencoding, 0),
    'sfv':
        (1, 0, 1, 1, 1, preferredencoding, 0),
    'sfvmd5':
        (1, 0, 1, 1, 1, preferredencoding, 0),
    'csv':
        (1, 1, 1, 1, 1, preferredencoding, 0),
    'csv2':
        (0, 1, 1, 1, 1, preferredencoding, 0),
    'csv4':
        (1, 1, 1, 1, 1, preferredencoding, 0),
    'crc':
        (1, 1, 1, 1, 1, preferredencoding, 0),
    'par':
        (1, 1, 0, 1, 0, 'utf-16-le', 0),
    'par2':
        (1, 1, 0, 1, 0, preferredencoding, 0),
    'torrent':
        (1, 1, 1, 1, 0, 'utf-8', 0),
}


def fmt_hascrc(f):
    return fmt_info[f][0]


def fmt_hassize(f):
    return fmt_info[f][1]


def fmt_cancreate(f):
    return fmt_info[f][2]


def fmt_available(f):
    return fmt_info[f][3]


def fmt_istext(f):
    return fmt_info[f][4]


def fmt_preferredencoding(f):
    return fmt_info[f][5]


def fmt_iscoreutils(f):
    return fmt_info[f][6]


def allfmts():
    return list(fmt_info.keys())


def allavailablefmts():
    return list(filter(fmt_available, allfmts()))


def allcreatablefmts():
    return list(filter(fmt_cancreate, allavailablefmts()))


def coreutilsfmts():
    return list(filter(fmt_iscoreutils, allfmts()))


class rcurry(object):
    def __init__(self, func, *args, **kw):
        self.curry_func = func
        self.curry_args = args
        self.curry_kw = kw

    def __call__(self, *_args, **_kwargs):
        kw = self.curry_kw.copy()
        kw.update(_kwargs)
        return self.curry_func(*(_args + self.curry_args), **kw)


def pathfind(p, path=os.environ.get('PATH', os.defpath).split(os.pathsep)):
    for d in path:
        if os.path.exists(os.path.join(d, p)):
            return 1


def pathjoin_and_mkdir(*components):
    """Join components of a filename together and create directory to contain the file, if needed.
    """
    result = os.path.join(*components)
    path = os.path.split(result)[0]
    if not os.path.exists(path):
        os.makedirs(path)
    return result


def readfile(fn, textmode=False):
    if textmode:
        mode = 't'
    else:
        mode = 'b'
    with open(fn, 'r' + mode) as f:
        d = f.read()
    return d


def writefile(fn, data):
    with open(fn, 'wb') as f:
        if data:
            f.write(data)


def writefile_and_reopen(fn, data):
    """Write data to file, close, and then reopen readonly, and return the fd.

    This is for the benefit of windows, where you need to close and reopen the
    file as readonly in order for it to be openable simultaneously.
    """
    writefile(fn, data)
    f = open(fn, 'rb')
    return f


class stats(object):
    ok = 0
    failed = 0


def logr(text):
    logfile.write(text)


def log(text):
    logr(text + '\n')


def test_log_start(cmd, kw):
    log('*** testing ' + cmd + (kw and ' ' + str(kw) or ''))


def test_log_finish(cmd, s, r, output, kw):
    if r:
        stats.failed += 1
        print('\n>>> failed test:', cmd, (kw and ' ' + str(kw) or ''))
        if output is not None:
            print(output)
        result = 'FAILED'
        if not isinstance(r, int) or r != 1:
            result += ' (%s)' % r
    else:
        stats.ok += 1
        sys.stdout.write('.')
        sys.stdout.flush()
        result = 'OK'
    result_str = '%s (%s)' % (result, s)
    log(result_str)
    if r:
        print(result_str)
        traceback_str = '\n'.join(traceback.format_stack())
        log(traceback_str)
        print(traceback_str)
        if run_exit_early:
            sys.exit(1)
    log('')


def test_log_results(cmd, s, o, r, kw):
    """
    cmd=command being tested (info only)
    s=return status
    o=output
    r=result (false=ok, anything else=fail (anything other than 1 will be printed))
    """
    test_log_start(cmd, kw)
    log(o)
    test_log_finish(cmd, s, r, o, kw)


def test_external(cmd, test):
    # TODO: replace this with subprocess
    from subprocess import getstatusoutput
    s, o = getstatusoutput(cmd)
    r = test(s, o)
    test_log_results(cmd, s, o, r, None)


def test_generic(cmd, test, **kw):
    # s, o = cfvtest.runcfv(cmd)
    s, o = cfvtest.runcfv(*(cmd,), **kw)
    r = test(s, o)
    test_log_results(cfvtest.cfvenv + cfvtest.cfvfn + ' ' + cmd, s, o, r, kw)


class cst_err(Exception):
    pass


def cfv_stdin_test(cmd, file):
    s1 = s2 = None
    o1 = o2 = ''
    r = 0
    try:
        s1, o1 = cfvtest.runcfv(cmd + ' ' + file)
        if s1:
            raise cst_err(2)
        s2, o2 = cfvtest.runcfv(cmd + ' -', stdin=file)
        if s2:
            raise cst_err(3)
        x = re.search(r'^([^\r\n]*)' + re.escape(file) + r'(.*)$[\r\n]{0,2}^-: (\d+) files, (\d+) OK.  [\d.]+ seconds, [\d.]+K(/s)?$', o1, re.M | re.DOTALL)
        if not x:
            raise cst_err(4)
        x2 = re.search(r'^' + re.escape(x.group(1)) + r'[\t ]*' + re.escape(x.group(2)) + r'$[\r\n]{0,2}^-: (\d+) files, (\d+) OK.  [\d.]+ seconds, [\d.]+K(/s)?$', o2, re.M)
        if not x2:
            raise cst_err(5)
    except cst_err as er:
        r = er
    test_log_results('stdin/out of ' + cmd + ' with file ' + file, (s1, s2), o1 + '\n' + o2, r, None)


def cfv_stdin_progress_test(t, file):
    s1 = s2 = None
    o1 = o2 = c1 = c2 = ''
    r = 0
    dir = tempfile.mkdtemp()
    try:
        try:
            cf1 = os.path.join(dir, 'cf1.' + t)
            cf2 = os.path.join(dir, 'cf2.' + t)
            s1, o1 = cfvtest.runcfv('%s --progress=yes -C -t %s -f %s %s' % (cfvcmd, t, cf1, file))
            if s1:
                raise cst_err(2)
            s2, o2 = cfvtest.runcfv('%s --progress=yes -C -t %s -f %s -' % (cfvcmd, t, cf2), stdin=file)
            if s2:
                raise cst_err(3)
            if t != 'csv2':  # csv2 has only filesize, hence checksum never happens, so no progress
                x = re.match(re.escape(file) + r' : (\.{20}[-\b.#\\|/]*)[ \r\n]+' + '\x1b\\[K' + re.escape(cf1) + r': (\d+) files, (\d+) OK.  [\d.]+ seconds, [\d.]+K(/s)?$', o1, re.M | re.DOTALL)
                if not x:
                    raise cst_err(4)
            x2 = re.match(r' : (\.[-\b.#/|\\]*)[\t ]*[ \r\n]+' + '\x1b\\[K' + re.escape(cf2) + r': (\d+) files, (\d+) OK.  [\d.]+ seconds, [\d.]+K(/s)?$', o2, re.M)
            if not x2:
                raise cst_err(5)
            if t == 'crc':
                c1 = readfile(cf1, textmode=True).replace(file, ' ' * len(file))
            else:
                c1 = readfile(cf1, textmode=True).replace(file, '')
            c2 = readfile(cf2, textmode=True)
            c1 = remove_varying_comments(t, c1)
            c2 = remove_varying_comments(t, c2)
            if c1 != c2:
                raise cst_err(6)
        except cst_err as er:
            r = er
        test_log_results('progress=yes stdin/out of ' + t + ' with file ' + file, (s1, s2), o1 + '\n' + o2 + '\n--\n' + c1 + '\n' + c2, r, None)
    finally:
        shutil.rmtree(dir)


def rx_test(pat, str):
    if re.search(pat, str):
        return 0
    return 1


def status_test(s, o, expected=0):
    if s == expected:
        return 0
    return 1


rx_Begin = r'^(?:.* )?(\d+) files, (\d+) OK'
rx_unv = r', (\d+) unverified'
rx_notfound = r', (\d+) not found'
rx_ferror = r', (\d+) file errors'
rx_bad = r', (\d+) bad(crc|size)'
rx_badcrc = r', (\d+) badcrc'
rx_badsize = r', (\d+) badsize'
rx_cferror = r', (\d+) chksum file errors'
rx_misnamed = r', (\d+) misnamed'
rx_End = r'(, \d+ differing cases)?(, \d+ quoted filenames)?.  [\d.]+ seconds, [\d.]+K(/s)?$'
rxo_TestingFrom = re.compile(r'^testing from .* \((.+?)\b.*\)[\n\r]*$', re.M)


def optionalize(s):
    return '(?:%s)?' % s


rx_StatusLine = rx_Begin + ''.join(map(optionalize, [rx_badcrc, rx_badsize, rx_notfound, rx_ferror, rx_unv, rx_cferror, rx_misnamed])) + rx_End


class OneOf(object):
    def __init__(self, *possibilities):
        self.possible = possibilities

    def __eq__(self, a):
        return a in self.possible

    def __repr__(self):
        return 'OneOf' + repr(self.possible)


def intize(s):
    return s and int(s) or 0


def icomp(foo):
    exp, act = foo
    if exp == -1:
        return False
    return exp != act


def tail(s):
    # the last line might not be what we want, since stdout and stderr can get mixed up in some cases.
    # return string.split(s,'\n')[-1]
    lines = s.splitlines()
    lines.reverse()
    for line in lines:
        if re.search(rx_StatusLine, line):
            return line
    return ''


re_sfv_comment = re.compile('^; Generated by .* on .*$', re.M | re.I)
re_crc_comment = re.compile('^Generated at: .*$', re.M | re.I)


def remove_varying_comments(t, text):
    if t in ('sfv', 'sfvmd5'):
        text = re_sfv_comment.sub('', text, 1)
    elif t == 'crc':
        text = re_crc_comment.sub('', text, 1)
    return text


def cfv_test(s, o, op=operator.gt, opval=0):
    x = re.search(rx_Begin + rx_End, tail(o))
    if s == 0 and x and x.group(1) == x.group(2) and op(int(x.group(1)), opval):
        return 0
    return 1


def cfv_substatus_test(s, o, unv=0, notfound=0, badcrc=0, badsize=0, cferror=0, ferror=0):
    expected_status = (badcrc and 2) | (badsize and 4) | (notfound and 8) | (ferror and 16) | (unv and 32) | (cferror and 64)
    if s & expected_status == expected_status and not s & 1:
        return 0
    return 'bad status expected %s got %s' % (expected_status, s)


def cfv_status_test(s, o, unv=0, notfound=0, badcrc=0, badsize=0, cferror=0, ferror=0):
    expected_status = (badcrc and 2) | (badsize and 4) | (notfound and 8) | (ferror and 16) | (unv and 32) | (cferror and 64)
    if s == expected_status:
        return 0
    return 'bad status expected %s got %s' % (expected_status, s)


def cfv_all_test(s, o, files=-2, ok=0, unv=0, notfound=0, badcrc=0, badsize=0, cferror=0, ferror=0, misnamed=0):
    x = re.search(rx_StatusLine, tail(o))
    if x:
        if files == -2:
            files = reduce(operator.add, [ok, badcrc, badsize, notfound, ferror])
        expected = [files, ok, badcrc, badsize, notfound, ferror, unv, cferror, misnamed]
        actual = list(map(intize, x.groups()[:9]))
        if not list(filter(icomp, zip(expected, actual))):
            sresult = cfv_status_test(s, o, unv=unv, notfound=notfound, badcrc=badcrc, badsize=badsize, cferror=cferror, ferror=ferror)
            if sresult:
                return sresult
            return 0
        return 'expected %s got %s' % (expected, actual)
    return 'status line not found in output'


def cfv_unv_test(s, o, unv=1):
    x = re.search(rx_Begin + rx_unv + rx_End, tail(o))
    if s != 0 and x and x.group(1) == x.group(2) and int(x.group(1)) > 0:
        if unv and int(x.group(3)) != unv:
            return 1
        return 0
    return 1


def cfv_unvonly_test(s, o, unv=1):
    x = re.search(rx_Begin + rx_unv + rx_End, tail(o))
    if s != 0 and x and int(x.group(3)) == unv:
        return 0
    return 1


def cfv_notfound_test(s, o, unv=1):
    x = re.search(rx_Begin + rx_notfound + rx_End, tail(o))
    if s != 0 and x and int(x.group(2)) == 0 and int(x.group(1)) > 0:
        if int(x.group(3)) != unv:
            return 1
        return 0
    return 1


def cfv_cferror_test(s, o, bad=1):
    x = re.search(rx_Begin + rx_cferror + rx_End, tail(o))
    if s != 0 and x and int(x.group(3)) > 0:
        if bad > 0 and int(x.group(3)) != bad:
            return 1
        return 0
    return 1


def cfv_bad_test(s, o, bad=-1):
    x = re.search(rx_Begin + rx_bad + rx_End, tail(o))
    if s != 0 and x and int(x.group(1)) > 0 and int(x.group(3)) > 0:
        if bad > 0 and int(x.group(3)) != bad:
            return 1
        return 0
    return 1


def cfv_typerestrict_test(s, o, t):
    matches = rxo_TestingFrom.findall(o)
    if not matches:
        return 1
    for match in matches:
        if match != t:
            return 1
    return 0


def cfv_listdata_test(s, o):
    if s == 0 and re.search('^data1\0data2\0data3\0data4\0$', o, re.I):
        return 0
    return 1


def joincurpath(f):
    return os.path.join(os.getcwd(), f)


def cfv_listdata_abs_test(s, o):
    if s == 0 and re.search('^' + re.escape('\0'.join(map(joincurpath, ['data1', 'data2', 'data3', 'data4']))) + '\0$', o, re.I):
        return 0
    return 1


def cfv_listdata_unv_test(s, o):
    if s == 32 and re.search('^testfix.csv\0unchecked.dat\0$', o, re.I):
        return 0
    return 1


def cfv_listdata_bad_test(s, o):
    if s & 6 and not s & ~6 and re.search('^(d2.)?test4.foo\0test.ext.end\0test2.foo\0test3\0$', o, re.I):
        return 0
    return 1


def cfv_version_test(s, o):
    x = re.search(r'cfv v([\d.]+(?:\.dev\d+)?) -', o)
    with open(os.path.join(cfvtest.testpath, os.pardir, 'Changelog'), 'rt') as f:
        x3 = re.search(r' v([\d.]+(?:\.dev\d+)?):', f.readline())
    if x:
        log('cfv: ' + x.group(1))
    if x3:
        log('Changelog: ' + x3.group(1))
    # if os.path.isdir(os.path.join(os.pardir, 'debian')):
    #     with open(os.path.join(os.pardir, 'debian', 'changelog'), 'rt') as f:
    #         x4 = re.search(r'cfv \(([\d.]+)-\d+\) ', f.readline())
    #     if x4:
    #         log('deb changelog: ' + x4.group(1))
    #     if not x or not x4 or x4.group(1) != x.group(1):
    #         return 1
    if x and x3 and x.group(1) == x3.group(1):
        return 0
    return 1


def cfv_cftypehelp_test(s, o, expected):
    if s != expected:
        return 1
    for tname in allfmts() + ['auto']:
        if o.count(tname) < 1:
            return 'type %s not found in output' % tname
    return 0


def cfv_nooutput_test(s, o, expected=0):
    if s != expected:
        return 1
    if o:
        return 'output: %s' % (repr(o),)
    return 0


def T_test(f, extra=None):
    cmd = cfvcmd
    if extra:
        cmd += ' ' + extra
    test_generic(cmd + ' -T -f test' + f, cfv_test)
    test_generic(cmd + ' -i -T -f test' + f, cfv_test)  # all tests should work with -i
    test_generic(cmd + ' -m -T -f test' + f, cfv_test)  # all tests should work with -m

    test_generic(cmd + ' -T --list0=ok -f test' + f, cfv_listdata_test, stderr='/dev/null')
    test_generic(cmd + ' -T --showpaths=n-r --list0=ok -f test' + f, cfv_listdata_test, stderr='/dev/null')
    test_generic(cmd + ' -T --showpaths=n-a --list0=ok -f test' + f, cfv_listdata_test, stderr='/dev/null')
    test_generic(cmd + ' -T --showpaths=a-a --list0=ok -f test' + f, cfv_listdata_test, stderr='/dev/null')
    test_generic(cmd + ' -T --showpaths=2-a --list0=ok -f test' + f, cfv_listdata_test, stderr='/dev/null')
    test_generic(cmd + ' -T --showpaths=y-r --list0=ok -f test' + f, cfv_listdata_test, stderr='/dev/null')
    test_generic(cmd + ' -T --showpaths=y-a --list0=ok -f test' + f, cfv_listdata_abs_test, stderr='/dev/null')
    test_generic(cmd + ' -T --showpaths=1-a --list0=ok -f test' + f, cfv_listdata_abs_test, stderr='/dev/null')
    # ensure all verbose stuff goes to stderr:
    test_generic(cmd + ' -v -T --list0=ok -f test' + f, cfv_listdata_test, stderr='/dev/null')
    test_generic(cmd + ' -v -T --list0=unverified -f test' + f + ' unchecked.dat testfix.csv data1', cfv_listdata_unv_test, stderr='/dev/null')

    # test progress stuff.
    def progress_test(s, o):
        if cfv_test(s, o):
            return 1
        if o.find('.' * 10) < 0:
            return 2
        return 0

    def noprogress_test(s, o):
        if cfv_test(s, o):
            return 1
        if o.find('.' * 10) >= 0:
            return 2
        return 0

    if f.endswith('.csv2'):  # csv2 has only filesize, hence checksum never happens, so no progress
        test_generic(cmd + ' -T --progress=yes -f test' + f, noprogress_test)
    else:
        # test handling of COLUMNS env var #TODO: should actually check that the value is being respected...
        os.environ['COLUMNS'] = '40'
        try:
            test_generic(cmd + ' -T --progress=yes -f test' + f, progress_test)
            os.environ['COLUMNS'] = 'foobar'
            test_generic(cmd + ' -T --progress=yes -f test' + f, progress_test)
        finally:
            del os.environ['COLUMNS']
        test_generic(cmd + ' -T --progress=yes -f test' + f, progress_test)
    test_generic(cmd + ' -T --progress=auto -f test' + f, noprogress_test)
    test_generic(cmd + ' -T --progress=no -f test' + f, noprogress_test)


def gzC_test(f, extra=None, verify=None, t=None, d=None):
    cmd = cfvcmd
    if not t:
        t = f
    tmpd = tempfile.mkdtemp()
    try:
        f2 = os.path.join(tmpd, 'test.C.' + f + '.tmp.gz')
        f = os.path.join(tmpd, 'test.C.' + f + '.gz')
        if extra:
            cmd += ' ' + extra
        test_generic('%s -q -C -t %s -zz -f - %s' % (cmd, t, d), status_test, stdout=f2)
        test_generic('%s -C -f %s %s' % (cmd, f, d), cfv_test)

        try:
            with gzip.open(f, 'rt') as ifd1:
                if1 = ifd1.read()
        except (IOError, zlib.error) as e:
            if1 = '%s: %s' % (f, e)
        try:
            with gzip.open(f2, 'rt') as ifd2:
                if2 = ifd2.read()
        except (IOError, zlib.error) as e:
            if2 = '%s: %s' % (f2, e)
        if1 = remove_varying_comments(t, if1)
        if2 = remove_varying_comments(t, if2)
        r = if1 != if2
        if r:
            o = 'FILE1 %s:\n%s\nFILE2 %s:\n%s\n' % (f, if1, f2, if2)
        else:
            o = ''
        test_log_results('zcompare %s %s' % (f, f2), r, o, r, None)

        test_generic('%s -T -f %s' % (cmd, f), cfv_test)
        test_generic('%s -zz -T -f -' % cmd, cfv_test, stdin=f)
        if verify:
            verify(f)
    finally:
        shutil.rmtree(tmpd)


def C_test(f, extra=None, verify=None, t=None, d='data?'):
    gzC_test(f, extra=extra, t=t, d=d)
    cmd = cfvcmd
    if not t:
        t = f
    cfv_stdin_test(cmd + ' -t' + f + ' -C -f-', 'data4')
    cfv_stdin_progress_test(f, 'data4')
    tmpd = tempfile.mkdtemp()
    try:
        f = os.path.join(tmpd, 'test.C.' + f)
        fgz = os.path.join(tmpd, f + '.gz')
        if extra:
            cmd += ' ' + extra
        test_generic('%s -C -f %s %s' % (cmd, f, d), cfv_test)
        test_generic('%s -T -f %s' % (cmd, f), cfv_test)
        test_generic('%s -T -f -' % cmd, cfv_test, stdin=f)
        with gzip.open(fgz, mode='wb') as of:
            with open(f, 'rb') as in_file:
                of.write(in_file.read())
        test_generic('%s -zz -t%s -T -f -' % (cmd, t), cfv_test, stdin=fgz)
        if verify:
            verify(f)
    finally:
        shutil.rmtree(tmpd)

    tmpd = tempfile.mkdtemp()
    try:
        test_generic('%s -p %s -C -f %s' % (cmd, tmpd, f), rcurry(cfv_test, operator.eq, 0))
    finally:
        os.rmdir(tmpd)

    def C_test_encoding(enc):
        d = tempfile.mkdtemp()
        try:
            with open(os.path.join(d, 'aoeu'), 'wt') as f2:
                f2.write('a')
            with open(os.path.join(d, 'kakexe'), 'wt') as f2:
                f2.write('ba')
            with open(os.path.join(d, 'foo bar.baz'), 'wt') as f2:
                f2.write('baz')
            test_generic(cfvcmd + ' --encoding=%s -v -C -p %s -t %s' % (enc, d, t), rcurry(cfv_all_test, ok=3))
            test_generic(cfvcmd + ' --encoding=%s -v -T -p %s' % (enc, d,), rcurry(cfv_all_test, ok=3))
        finally:
            shutil.rmtree(d)

    C_test_encoding('cp500')
    C_test_encoding('utf-16be')
    C_test_encoding('utf-16')


def create_funkynames(t, d, chr, deep):
    num = 0
    for i in range(1, 256):
        n = chr(i)
        if n in (os.sep, os.altsep):
            continue
        if fmt_istext(t) and len(('a' + n + 'a').splitlines()) > 1:  # if n is a line separator (note that in unicode, this is more than just \r and \n)
            continue
        if t == 'torrent' and n in ('/', '\\'):
            continue  # 'ValueError: path \ disallowed for security reasons'
        # if t == 'torrent' and n in ('~',): n = 'foo'+n; #same
        # if n == os.curdir: n = 'foo'+n # can't create a file of name '.', but 'foo.' is ok.
        # if t in ('sfv','sfvmd5') and n==';': n = 'foo'+n; # ';' is comment character in sfv files, filename cannot start with it.
        if t == 'crc' and n.isspace():
            n += 'foo'  # crc format can't handle trailing whitespace in filenames
        n = '%02x' % i + n
        try:
            if deep:
                os.mkdir(os.path.join(d, n))
                try:
                    f = open(os.path.join(d, n, n), 'wb')
                except Exception:
                    # if making the dir succeeded but making the file fails, remove the dir so it won't confuse the tests which count the number of items in the top dir.
                    os.rmdir(os.path.join(d, n))
                    raise
            else:
                f = open(os.path.join(d, n), 'wb')
            # important that all the funky files be two bytes long,
            # since that is the torrent piece size needed in order for
            # the undecodable filenames without raw test to work.
            # (If the piece size doesn't match the file size, then some
            # files that it can find will still be marked bad since it
            # can't find the rest of the piece.)
            f.write(b'%02x' % i)
            f.close()
        except (EnvironmentError, UnicodeError):
            pass  # stupid filesystem doesn't allow the character we wanted, oh well.
        else:
            num += 1
    return num


def C_funkynames_test(t):
    def fschr(i):
        return os.fsdecode(b'%c' % i)

    def is_fmtencodable(s, enc=fmt_preferredencoding(t)):
        return is_encodable(s, enc)

    def is_fmtokfn(s):
        if fmt_istext(t):
            return len(('a' + s + 'a').splitlines()) == 1
        return True

    for deep in (0, 1):
        d = tempfile.mkdtemp()
        try:
            num = create_funkynames(t, d, chr, deep=deep)
            # numencodable = len(filter(lambda fn: os.path.exists(os.path.join(d,fn)), os.listdir(d)))
            numencodable = len(list(filter(is_fmtencodable, os.listdir(d))))
            # cfv -C, unencodable filenames on disk, ferror on unencodable filename and ignore it
            numunencodable = num - numencodable
            cfn = os.path.join(d, 'funky%s.%s' % (deep and 'deep' or '', t))
            test_generic(cfvcmd + '%s -v -C -p %s -t %s -f %s' % (deep and ' -rr' or '', d, t, cfn), rcurry(cfv_all_test, files=num, ok=numencodable, ferror=numunencodable))
            test_generic(cfvcmd + ' -v -T -p %s -f %s' % (d, cfn), rcurry(cfv_all_test, files=numencodable, ok=numencodable))
            test_generic(cfvcmd + ' -v -u -T -p %s -f %s' % (d, cfn), rcurry(cfv_all_test, files=numencodable, ok=numencodable, unv=numunencodable))

            os.unlink(cfn)
            # cfv -C, unencodable filenames on disk, with --encoding=<something else> (eg, utf8), should work.
            cfn = os.path.join(d, 'funky%s.%s' % (deep and 'deep' or '', t))
            test_generic(cfvcmd + '%s --encoding=utf-8 -v -C -p %s -t %s -f %s' % (deep and ' -rr' or '', d, t, cfn), rcurry(cfv_all_test, files=num, ok=num))
            test_generic(cfvcmd + ' -v --encoding=utf-8 -T -p %s -f %s' % (d, cfn), rcurry(cfv_all_test, files=num, ok=num))
            test_generic(cfvcmd + ' -v --encoding=utf-8 -u -T -p %s -f %s' % (d, cfn), rcurry(cfv_all_test, files=num, ok=num, unv=0))
        finally:
            shutil.rmtree(d)

        d3 = tempfile.mkdtemp()
        try:
            cnum = create_funkynames(t, d3, fschr, deep=deep)
            ulist = os.listdir(d3)
            numundecodable = 0  # listdir always returns filenames of type str if we use a path of type str (and this is what we do)
            okcnum = len(ulist) - numundecodable
            dcfn = os.path.join(d3, 'funky3%s.%s' % (deep and 'deep' or '', t))
            # cfv -C, undecodable filenames on disk, with --encoding=raw just put everything in like before
            test_generic(cfvcmd + '%s --encoding=raw -v --piece_size_pow2=1 -C -p %s -t %s -f %s' % (deep and ' -rr' or '', d3, t, dcfn), rcurry(cfv_all_test, files=cnum, ok=cnum))
            # cfv -T, undecodable filenames on disk and in CF (same names), with --encoding=raw, read CF as raw strings and be happy
            test_generic(cfvcmd + ' --encoding=raw -v -T -p %s -f %s' % (d3, dcfn), rcurry(cfv_all_test, files=cnum, ok=cnum))
            test_generic(cfvcmd + ' --encoding=raw -v -u -T -p %s -f %s' % (d3, dcfn), rcurry(cfv_all_test, files=cnum, ok=cnum, unv=0))
            # cfv -T, undecodable filenames on disk and in CF (same names), without raw, cferrors
            test_generic(cfvcmd + ' -v -T -p %s -f %s' % (d3, dcfn), rcurry(cfv_substatus_test, cferror=1))  # rcurry(cfv_all_test,ok=okcnum,cferror=numundecodable))
            test_generic(cfvcmd + ' -v -u -T -p %s -f %s' % (d3, dcfn), rcurry(cfv_substatus_test, cferror=1, unv=1))  # rcurry(cfv_all_test,ok=okcnum,cferror=numundecodable,unv=numundecodable))
            test_generic(cfvcmd + ' -v -m -T -p %s -f %s' % (d3, dcfn), rcurry(cfv_substatus_test, cferror=1))  # rcurry(cfv_all_test,ok=okcnum,cferror=numundecodable))
            test_generic(cfvcmd + ' -v -m -u -T -p %s -f %s' % (d3, dcfn), rcurry(cfv_substatus_test, cferror=1, unv=1))  # rcurry(cfv_all_test,ok=okcnum,cferror=numundecodable,unv=numundecodable))

            # TODO: needs "deep" -s
            if not deep:
                renamelist = []
                numrenamed = 0
                for fn in os.listdir(d3):
                    if os.path.join(d3, fn) == dcfn:
                        continue
                    newfn = 'ren%3s' % numrenamed
                    renamelist.append((fn, newfn))
                    os.rename(os.path.join(d3, fn), os.path.join(d3, newfn))
                    if deep:
                        os.rename(os.path.join(d3, newfn, fn), os.path.join(d3, newfn, newfn))
                    numrenamed += 1
                # cfv -T, correct filenames on disk, undecodable filenames in CF: check with -s, with --encoding=raw, read CF as raw strings and be happy
                if t != 'torrent':
                    test_generic(cfvcmd + ' --encoding=raw -v -s -T -p %s -f %s' % (d3, dcfn), rcurry(cfv_all_test, ok=cnum, misnamed=numrenamed))
                if fmt_hassize(t):
                    test_generic(cfvcmd + ' --encoding=raw -v -m -s -T -p %s -f %s' % (d3, dcfn), rcurry(cfv_all_test, ok=cnum, misnamed=numrenamed))

                cnum += 1
                # okcnum += 1
                ulist = os.listdir(d3)
                okcnum = len(list(filter(is_fmtencodable, ulist)))
                numerr = len(ulist) - okcnum
                dcfn = os.path.join(d3, 'funky3%s2.%s' % (deep and 'deep' or '', t))
                test_generic(cfvcmd + '%s -v -C -p %s -t %s -f %s' % (deep and ' -rr' or '', d3, t, dcfn), rcurry(cfv_all_test, ok=okcnum, ferror=numerr))
                for fn, newfn in renamelist:
                    if deep:
                        os.rename(os.path.join(d3, newfn, newfn), os.path.join(d3, newfn, fn))
                    os.rename(os.path.join(d3, newfn), os.path.join(d3, fn))
                # cfv -T, undecodable filenames on disk, correct filenames in chksum file. want to check with -s, fix with -sn
                if fmt_hassize(t):
                    test_generic(cfvcmd + ' -v -m -s -T -p %s -f %s' % (d3, dcfn), rcurry(cfv_all_test, ok=okcnum, misnamed=numrenamed))
                if t != 'torrent':  # needs -s support on torrents
                    test_generic(cfvcmd + ' -v -s -T -p %s -f %s' % (d3, dcfn), rcurry(cfv_all_test, ok=okcnum, misnamed=numrenamed))
                    if fmt_hascrc(t):
                        test_generic(cfvcmd + ' -v -s -n -T -p %s -f %s' % (d3, dcfn), rcurry(cfv_all_test, ok=okcnum, misnamed=numrenamed))
                        test_generic(cfvcmd + ' -v -T -p %s -f %s' % (d3, dcfn), rcurry(cfv_all_test, ok=okcnum))
        finally:
            shutil.rmtree(d3)

        d3 = tempfile.mkdtemp()
        try:
            cnum = create_funkynames(t, d3, fschr, deep=deep)
            ulist = os.listdir(d3)
            okcnum = len(list(filter(is_fmtokfn, list(filter(is_fmtencodable, ulist)))))
            numerr = len(ulist) - okcnum
            dcfn = os.path.join(d3, 'funky3%s3.%s' % (deep and 'deep' or '', t))
            # cfv -C, undecodable(and/or unencodable) filenames on disk: without raw, ferror on undecodable filename and ignore it
            test_generic(cfvcmd + '%s -v -C -p %s -t %s -f %s' % (deep and ' -rr' or '', d3, t, dcfn), rcurry(cfv_all_test, files=cnum, ok=okcnum, ferror=numerr))
            test_generic(cfvcmd + ' -v -T -p %s -f %s' % (d3, dcfn), rcurry(cfv_all_test, ok=okcnum))
            test_generic(cfvcmd + ' -v -u -T -p %s -f %s' % (d3, dcfn), rcurry(cfv_all_test, ok=okcnum, unv=numerr))

        finally:
            shutil.rmtree(d3)


def ren_test(f, extra=None, verify=None, t=None):
    join = os.path.join
    dir = tempfile.mkdtemp()
    try:
        dir2 = join(dir, 'd2')
        basecmd = cfvcmd + ' -r -p ' + dir
        if extra:
            basecmd += ' ' + extra
        cmd = basecmd + ' --renameformat="%(name)s-%(count)i%(ext)s"'
        os.mkdir(dir2)
        fls = [join(dir, 'test.ext.end'),
               join(dir, 'test2.foo'),
               join(dir, 'test3'),
               join(dir2, 'test4.foo')]
        flsf = [join(dir, 'test.ext-%i.end'),
                join(dir, 'test2-%i.foo'),
                join(dir, 'test3-%i'),
                join(dir2, 'test4-%i.foo')]
        flsf_1 = [join(dir, 'test.ext.end-%i'),
                  join(dir, 'test2.foo-%i'),
                  join(dir2, 'test4.foo-%i')]
        flsf_2 = [join(dir, 'test3-%i')]

        def flsw(t):
            for fl in fls:
                with open(fl, 'wb') as f2:
                    f2.write(t)

        def flscmp(t, n, fls):
            for fl in fls:
                fn = n is not None and fl % n or fl
                try:
                    with open(fn, 'rb') as f2:
                        d = f2.read()
                    r = d != t
                    o = repr(d)
                except IOError as e:
                    r = 1
                    o = str(e)
                test_log_results('cmp %s for %s' % (fn, t.decode('ascii')), r, o, r, None)

        flsw(b'hello')
        test_generic('%s -C -t %s' % (cmd, f), cfv_test)
        flsw(b'1')
        test_generic(basecmd + ' --showpaths=0 -v -T --list0=bad', cfv_listdata_bad_test, stderr='/dev/null')
        test_generic(basecmd + ' --showpaths=0 -q -T --list0=bad', cfv_listdata_bad_test)
        test_generic('%s -Tn' % cmd, cfv_bad_test)
        flsw(b'11')
        test_generic('%s -Tn' % cmd, cfv_bad_test)
        flsw(b'123')
        test_generic('%s -Tn' % cmd, cfv_bad_test)
        flsw(b'63')
        test_generic(cmd + ' --renameformat="%(fullname)s" -Tn', cfv_bad_test)  # test for formats without count too
        flsw(b'hello')
        test_generic('%s -Tn' % cmd, cfv_test)
        flscmp(b'1', 0, flsf)
        flscmp(b'11', 1, flsf)
        flscmp(b'123', 2, flsf)
        flscmp(b'63', 1, flsf_1)
        flscmp(b'63', 3, flsf_2)
        flscmp(b'hello', None, fls)
    finally:
        shutil.rmtree(dir)


def search_test(t, test_nocrc=0, extra=None):
    cfn = os.path.join(os.getcwd(), 'test.' + t)
    hassize = fmt_hassize(t)
    if test_nocrc:
        hascrc = 0
        cmd = cfvcmd + ' -m'
    else:
        hascrc = fmt_hascrc(t)
        cmd = cfvcmd
    if extra:
        cmd += ' ' + extra

    if not hascrc and not hassize:
        # if using -m and type doesn't have size, make sure -s doesn't do anything silly
        d = tempfile.mkdtemp()
        try:
            for n, n2 in zip(list(range(1, 5)), list(range(4, 0, -1))):
                shutil.copyfile('data%s' % n, os.path.join(d, 'fOoO%s' % n2))
            test_generic(cmd + ' -v -T -p %s -f %s' % (d, cfn), rcurry(cfv_all_test, notfound=4))
            test_generic(cmd + ' -v -s -T -p %s -f %s' % (d, cfn), rcurry(cfv_all_test, notfound=4))
            test_generic(cmd + ' -v -s -n -T -p %s -f %s' % (d, cfn), rcurry(cfv_all_test, notfound=4))
            test_generic(cmd + ' -v -s -u -T -p %s -f %s' % (d, cfn), rcurry(cfv_all_test, notfound=4, unv=4))
        finally:
            shutil.rmtree(d)
        # then return, since all the following tests would be impossible.
        return

    d = tempfile.mkdtemp()
    try:
        def dont_find_same_file_twice_test(s, o):
            if not (o.count('fOoO3') == 1 and o.count('fOoO4') == 1):
                return str((o.count('fOoO3'), o.count('fOoO4')))
            return cfv_all_test(s, o, ok=4, misnamed=4)

        test_generic(cmd + ' -v -s -T -p %s -f %s' % (d, cfn), rcurry(cfv_all_test, notfound=4))
        for n, n2 in zip(list(range(1, 5)), list(range(4, 0, -1))):
            shutil.copyfile('data%s' % n, os.path.join(d, 'fOoO%s' % n2))
        test_generic(cmd + ' -v -T -p %s -f %s' % (d, cfn), rcurry(cfv_all_test, notfound=4))
        test_generic(cmd + ' -v -s -T -p %s -f %s' % (d, cfn), dont_find_same_file_twice_test)
        test_generic(cmd + ' -v -T -p %s -f %s' % (d, cfn), rcurry(cfv_all_test, notfound=4))
        test_generic(cmd + ' -v -n -s -T -p %s -f %s' % (d, cfn), rcurry(cfv_all_test, ok=4, misnamed=4))
        test_generic(cmd + ' -v -u -T -p %s -f %s' % (d, cfn), rcurry(cfv_all_test, ok=4))
    finally:
        shutil.rmtree(d)

    # the following tests two things:
    # 1) that it will copy/link to a file that is already OK rather than just renaming it again
    # 2) that it doesn't use the old cached value of a file's checksum before it got renamed out of the way.
    d = tempfile.mkdtemp()
    try:
        misnamed1 = misnamed2 = 4
        if hassize and hascrc:
            experrs = {'badcrc': 1, 'badsize': 2}
        elif hassize:
            experrs = {'badsize': 2, 'ok': 1}
            misnamed1 = 3
            misnamed2 = OneOf(3, 4)  # this depends on what order os.listdir finds stuff. (could be 3 or 4)
        else:  # if hascrc:
            experrs = {'badcrc': 3}

        test_generic(cmd + ' -v -s -T -p %s -f %s' % (d, cfn), rcurry(cfv_all_test, notfound=4))
        for n, n2 in zip([1, 3, 4], [4, 2, 1]):
            shutil.copyfile('data%s' % n, os.path.join(d, 'data%s' % n2))
        test_generic(cmd + ' -v -T -p %s -f %s' % (d, cfn), rcurry(cfv_all_test, notfound=1, **experrs))
        test_generic(cmd + ' -v -s -T -p %s -f %s' % (d, cfn), rcurry(cfv_all_test, ok=4, misnamed=misnamed1))
        test_generic(cmd + ' -v -T -p %s -f %s' % (d, cfn), rcurry(cfv_all_test, notfound=1, **experrs))
        test_generic(cmd + ' -v -n -s -T -p %s -f %s' % (d, cfn), rcurry(cfv_all_test, ok=4, misnamed=misnamed2))
        test_generic(cmd + ' -v -u -T -p %s -f %s' % (d, cfn), rcurry(cfv_all_test, ok=4))
    finally:
        shutil.rmtree(d)

    # test whether ferrors during searching are ignored
    if hasattr(os, 'symlink'):
        d = tempfile.mkdtemp()
        try:
            for n, n2 in zip([4], [2]):
                shutil.copyfile('data%s' % n, os.path.join(d, 'foo%s' % n2))
            for n in string.ascii_lowercase:
                os.symlink('noexist', os.path.join(d, n))
            test_generic(cmd + ' -v -s -T -p %s -f %s' % (d, cfn), rcurry(cfv_all_test, ok=1, misnamed=1, notfound=3))
            test_generic(cmd + ' -v -T -p %s -f %s' % (d, cfn), rcurry(cfv_all_test, notfound=4))
            test_generic(cmd + ' -v -n -s -T -p %s -f %s' % (d, cfn), rcurry(cfv_all_test, ok=1, misnamed=1, notfound=3))
            test_generic(cmd + ' -v -T -p %s -f %s' % (d, cfn), rcurry(cfv_all_test, ok=1, notfound=3))
        finally:
            shutil.rmtree(d)

    # test if an error while renaming a misnamed file is properly handled
    d = tempfile.mkdtemp()
    ffoo = fdata4 = None
    try:
        with open('data4', 'rb') as f:
            ffoo = writefile_and_reopen(os.path.join(d, 'foo'), f.read())
        # note that we leave the file open.  This is because windows
        # allows renaming of files in a readonly dir, but doesn't allow
        # renaming of open files.  So if we do both the test will work
        # on both nix and win.
        os.chmod(d, stat.S_IRUSR | stat.S_IXUSR)
        try:
            os.rename(os.path.join(d, 'foo'), os.path.join(d, 'foo2'))
            print('rename of open file in read-only dir worked?  skipping this test.')
        except EnvironmentError:
            # if the rename failed, then we're good to go for these tests..
            test_generic(cmd + ' -v -n -s -T -p %s -f %s' % (d, cfn), rcurry(cfv_all_test, files=4, ok=1, misnamed=1, ferror=1, notfound=3))
            os.chmod(d, stat.S_IRWXU)
            fdata4 = writefile_and_reopen(os.path.join(d, 'data4'), '')
            os.chmod(d, stat.S_IRUSR | stat.S_IXUSR)
            test_generic(cmd + ' -v -n -s -T -p %s -f %s' % (d, cfn), rcurry(cfv_all_test, files=4, ok=1, misnamed=1, ferror=2, notfound=3))
    finally:
        os.chmod(d, stat.S_IRWXU)
        if ffoo:
            ffoo.close()
        if fdata4:
            fdata4.close()
        shutil.rmtree(d)

    # test if misnamed stuff and/or renaming stuff doesn't screw up the unverified file checking
    d = tempfile.mkdtemp()
    try:
        shutil.copyfile('data4', os.path.join(d, 'foo'))
        test_generic(cmd + ' -v -uu -s -T -p %s -f %s' % (d, cfn), rcurry(cfv_all_test, files=4, ok=1, misnamed=1, notfound=3, unv=0))
        test_generic(cmd + ' -v -uu -s -n -T -p %s -f %s' % (d, cfn), rcurry(cfv_all_test, files=4, ok=1, misnamed=1, notfound=3, unv=0))

        open(os.path.join(d, 'data1'), 'wb').close()
        if hassize:
            experrs = {'badsize': 1}
        else:
            experrs = {'badcrc': 1}
        test_generic(cmd + ' -v -uu -s -T -p %s -f %s' % (d, cfn), rcurry(cfv_all_test, files=4, ok=1, misnamed=0, notfound=2, unv=0, **experrs))
        test_generic(cmd + ' -v -uu -s -n -T -p %s -f %s' % (d, cfn), rcurry(cfv_all_test, files=4, ok=1, misnamed=0, notfound=2, unv=1, **experrs))
    finally:
        shutil.rmtree(d)

    if fmt_cancreate(t):
        # test deep handling
        d = tempfile.mkdtemp()
        try:
            dcfn = os.path.join(d, 'deep.' + t)
            os.mkdir(os.path.join(d, 'aOeU.AoEu'))
            os.mkdir(os.path.join(d, 'aOeU.AoEu', 'boO.FaRr'))
            shutil.copyfile('data1', os.path.join(d, 'aOeU.AoEu', 'boO.FaRr', 'DaTa1'))
            test_generic(cmd + ' -v -rr -C -p %s -t %s -f %s' % (d, t, dcfn), rcurry(cfv_all_test, files=1, ok=1))
            os.rename(os.path.join(d, 'aOeU.AoEu', 'boO.FaRr', 'DaTa1'), os.path.join(d, 'aOeU.AoEu', 'boO.FaRr', 'Foo1'))
            shutil.copyfile('data4', os.path.join(d, 'aOeU.AoEu', 'boO.FaRr', 'DaTa1'))
            test_generic(cmd + ' -v -s -T -p %s -f %s' % (d, dcfn), rcurry(cfv_all_test, files=1, ok=1, misnamed=1))
            shutil.rmtree(os.path.join(d, 'aOeU.AoEu'))
            os.mkdir(os.path.join(d, 'AoEu.aOeU'))
            os.mkdir(os.path.join(d, 'AoEu.aOeU', 'BOo.fArR'))
            shutil.copyfile('data4', os.path.join(d, 'AoEu.aOeU', 'BOo.fArR', 'dAtA1'))
            shutil.copyfile('data1', os.path.join(d, 'AoEu.aOeU', 'BOo.fArR', 'Foo1'))
            test_generic(cmd + ' -i -v -s -T -p %s -f %s' % (d, dcfn), rcurry(cfv_all_test, files=1, ok=1, misnamed=1))
            if hassize:
                experrs = {'badsize': 1}
            else:
                experrs = {'badcrc': 1}
            test_generic(cmd + ' -i -v -T -p %s -f %s' % (d, dcfn), rcurry(cfv_all_test, files=1, ok=0, **experrs))
            test_generic(cmd + ' -i -v -s -n -T -p %s -f %s' % (d, dcfn), rcurry(cfv_all_test, files=1, ok=1, misnamed=1))
            test_generic(cmd + ' -i -v -T -p %s -f %s' % (d, dcfn), rcurry(cfv_all_test, files=1, ok=1))
        finally:
            shutil.rmtree(d)

    if fmt_cancreate(t) and hassize:
        d = tempfile.mkdtemp()
        try:
            dcfn = os.path.join(d, 'foo.' + t)
            os.mkdir(os.path.join(d, 'aoeu'))
            dirsize = os.path.getsize(os.path.join(d, 'aoeu'))
            with open(os.path.join(d, 'idth'), 'wb') as f:
                f.write(b'a' * dirsize)
            test_generic(cmd + ' -v -C -p %s -t %s -f %s' % (d, t, dcfn), rcurry(cfv_all_test, files=1, ok=1))
            os.remove(os.path.join(d, 'idth'))
            os.rename(os.path.join(d, 'aoeu'), os.path.join(d, 'idth'))

            def dont_find_dir_test(s, o):
                if not o.count('idth') == 1:
                    return str((o.count('idth'),))
                return cfv_all_test(s, o, ok=0, notfound=1)

            test_generic(cmd + ' -v -m -T -p %s -f %s' % (d, dcfn), dont_find_dir_test)  # test not finding non-file things in normal mode
            test_generic(cmd + ' -v -m -s -T -p %s -f %s' % (d, dcfn), dont_find_dir_test)  # test not finding non-file things in search mode
        finally:
            shutil.rmtree(d)


def quoted_search_test():
    d = tempfile.mkdtemp()
    try:
        join = os.path.join
        with open(join(d, 'foo.sfv'), 'w') as f:
            f.write(r""""data1" B2A9E441
"/data4" FA323C6D
"aa1/data1" B2A9E441
"c:/aa1/data4" FA323C6D
"aa3/data3" 841ADFA2
"\aa3\data4" FA323C6D
"c:\aa4\bb4\data1" B2A9E441
"aa4/bb4/data4" FA323C6D""")
        shutil.copyfile('data1', pathjoin_and_mkdir(d, 'foo1'))
        shutil.copyfile('data4', pathjoin_and_mkdir(d, 'foo4'))
        shutil.copyfile('data1', pathjoin_and_mkdir(d, 'aa1', 'foo1'))
        shutil.copyfile('data4', pathjoin_and_mkdir(d, 'aa1', 'foo4'))
        shutil.copyfile('data3', pathjoin_and_mkdir(d, 'aa3', 'foo3'))
        shutil.copyfile('data4', pathjoin_and_mkdir(d, 'aa3', 'foo4'))
        shutil.copyfile('data1', pathjoin_and_mkdir(d, 'aa4', 'bb4', 'foo1'))
        shutil.copyfile('data4', pathjoin_and_mkdir(d, 'aa4', 'bb4', 'foo4'))
        test_generic(cfvcmd + r' -v --unquote=yes --strippaths=0 --fixpaths \\/ -s -T -p ' + d, rcurry(cfv_all_test, ok=8, misnamed=8))
    finally:
        shutil.rmtree(d)


def symlink_test():
    dir = tempfile.mkdtemp()
    dir1 = 'd1'
    dir2 = 'd2'
    try:
        os.mkdir(os.path.join(dir, dir1))
        os.mkdir(os.path.join(dir, dir2))
        if hasattr(os, 'symlink'):
            os.symlink(os.path.join(os.pardir, dir2), os.path.join(dir, dir1, 'l2'))
            os.symlink(os.path.join(os.pardir, dir1), os.path.join(dir, dir2, 'l1'))
            test_generic(cfvcmd + ' -l -r -p ' + dir, rcurry(cfv_test, operator.eq, 0))
            test_generic(cfvcmd + ' -L -r -p ' + dir, rcurry(cfv_test, operator.eq, 0))
            test_generic(cfvcmd + ' -l -r -C -p ' + dir, rcurry(cfv_test, operator.eq, 0))
            test_generic(cfvcmd + ' -L -r -C -p ' + dir, rcurry(cfv_test, operator.eq, 0))

        open(os.path.join(dir, dir1, 'foo'), 'wb').close()
        open(os.path.join(dir, dir2, 'bar'), 'wb').close()

        def r_unv_test(s, o):
            if cfv_unvonly_test(s, o, 2):
                return 1
            if o.count('not verified') != 1:
                return 1
            return 0

        test_generic(cfvcmd + ' -l -r -u -p ' + dir, r_unv_test)
        test_generic(cfvcmd + ' -L -r -u -p ' + dir, r_unv_test)
        test_generic(cfvcmd + ' -l -u -p ' + dir, r_unv_test)
        test_generic(cfvcmd + ' -L -u -p ' + dir, r_unv_test)

        def r_unv_verbose_test(s, o):
            if cfv_unvonly_test(s, o, 2):
                return 1
            if o.count('not verified') != 2:
                return 1
            return 0

        test_generic(cfvcmd + ' -l -uu -p ' + dir, r_unv_verbose_test)
        test_generic(cfvcmd + ' -L -uu -p ' + dir, r_unv_verbose_test)
        test_generic(cfvcmd + ' -l -r -uu -p ' + dir, r_unv_verbose_test)
        test_generic(cfvcmd + ' -L -r -uu -p ' + dir, r_unv_verbose_test)
    finally:
        shutil.rmtree(dir)


def deep_unverified_test():
    dir = tempfile.mkdtemp()
    try:
        join = os.path.join
        a = 'a'
        a_C = join(a, 'C')
        B = 'B'
        B_ushallow = join(B, 'ushallow')
        B_ushallow_d = join(B_ushallow, 'd')
        u = 'u'
        u_u2 = join(u, 'u2')
        e = 'e'
        e_es = join(e, 'es')
        e2 = 'e2'
        e2_e2s = join(e2, 'e2s')
        e2_e2u = join(e2, 'e2u')

        for d in a, a_C, B, B_ushallow, B_ushallow_d, u, u_u2, e, e_es, e2, e2_e2s, e2_e2u:
            os.mkdir(join(dir, d))
        datafns = ('DATa1', 'UnV1',
                   join(a, 'dAta2'), join(a, 'Unv2'), join(a_C, 'dATa4'), join(a_C, 'unV4'),
                   join(B, 'daTA3'), join(B, 'uNv3'),
                   join(B_ushallow, 'uNvs'), join(B_ushallow_d, 'unvP'), join(B_ushallow_d, 'datA5'),
                   join(u, 'uNVu'), join(u, 'UnvY'), join(u_u2, 'UNVX'),
                   join(e2_e2s, 'DaTaE'), join(e2_e2u, 'unVe2'),)
        lower_datafns = list(map(lambda s: s.lower(), datafns))
        for fn in datafns:
            open(join(dir, fn), 'wb').close()
        with open(join(dir, 'deep.md5'), 'wt') as f:
            s = ('d41d8cd98f00b204e9800998ecf8427e *%s\n' * 6) % (
                os.path.join('b', 'DaTa3'),
                os.path.join('B', 'ushAllOw', 'D', 'daTa5'),
                os.path.join('a', 'c', 'DatA4'),
                os.path.join('A', 'dATA2'),
                os.path.join('E2', 'e2S', 'DAtae'),
                'daTA1')
            f.write(s)

        def r_test(s, o):
            if cfv_test(s, o, operator.eq, 6):
                return 1
            if o.count('not verified') != 0:
                return 1
            return 0

        def r_unv_test(s, o):
            if cfv_unvonly_test(s, o, 10):
                return 1
            if o.count('not verified') != 8:
                return 1
            if o.find(os.path.join('e', '*')) >= 0:
                return 1
            if o.find(os.path.join('e2', '*')) >= 0:
                return 1
            return 0

        def r_unv_verbose_test(s, o):
            if cfv_unvonly_test(s, o, 10):
                return 1
            if o.count('not verified') != 10:
                return 1
            if o.find('*') >= 0:
                return 1
            return 0

        test_generic(cfvcmd + ' -i -U -p ' + dir, r_test)
        test_generic(cfvcmd + ' -i -u -p ' + dir, r_unv_test)
        test_generic(cfvcmd + ' -i -uu -p ' + dir, r_unv_verbose_test)
        test_generic(cfvcmd + ' -i -U -p ' + dir + ' ' + ' '.join(lower_datafns), r_test)
        test_generic(cfvcmd + ' -i -u -p ' + dir + ' ' + ' '.join(lower_datafns), r_unv_verbose_test)
        test_generic(cfvcmd + ' -i -uu -p ' + dir + ' ' + ' '.join(lower_datafns), r_unv_verbose_test)
    finally:
        shutil.rmtree(dir)


def test_encoding_detection():
    datad = tempfile.mkdtemp()
    d = tempfile.mkdtemp()
    try:
        datafns = ['data1', 'data3', 'data4']
        destfns = [
            '\u0061',  # LATIN SMALL LETTER A
            '\u00c4',  # LATIN CAPITAL LETTER A WITH DIAERESIS
            '\u03a0',  # GREEK CAPITAL LETTER PI
            '\u0470',  # CYRILLIC CAPITAL LETTER PSI
            '\u2605',  # BLACK STAR
            '\u3052',  # HIRAGANA LETTER GE
            '\u6708',  # CJK UNIFIED IDEOGRAPH-6708
        ]
        BOM = '\uFEFF'
        utfencodings = ['utf-8', 'utf-16le', 'utf-16be', 'utf-32le', 'utf-32be', ]
        fnerrs = fnok = 0
        for i, destfn in enumerate(destfns):
            srcfn = datafns[i % len(datafns)]
            try:
                shutil.copyfile(srcfn, os.path.join(datad, destfn))
            except (EnvironmentError, UnicodeError):
                fnerrs += 1
            else:
                fnok += 1
        for t in allcreatablefmts():
            if fmt_istext(t):
                utf8cfn = os.path.join(d, 'utf8nobom.' + t)
                test_generic(cfvcmd + ' -C --encoding=utf-8 -p %s -t %s -f %s' % (datad, t, utf8cfn), rcurry(cfv_all_test, ok=fnok))
                chksumdata = readfile(utf8cfn).decode('utf-8')
                for enc in utfencodings:
                    bommedcfn = os.path.join(d, enc + '.' + t)
                    try:
                        writefile(bommedcfn, (BOM + chksumdata).encode(enc))
                    except LookupError:
                        pass
                    else:
                        test_generic(cfvcmd + ' -T -p %s -t %s -f %s' % (datad, t, bommedcfn), rcurry(cfv_all_test, ok=fnok))
                        test_generic(cfvcmd + ' -T -p %s -f %s' % (datad, bommedcfn), rcurry(cfv_all_test, ok=fnok))
    finally:
        shutil.rmtree(d)
        shutil.rmtree(datad)


def test_encoding2():
    """Non-trivial (actual non-ascii characters) encoding test.
    These tests will probably always fail unless you use a unicode locale and python 2.3+.
    """
    d = tempfile.mkdtemp()
    d2 = tempfile.mkdtemp()
    try:
        cfn = os.path.join(d, '\u3070\u304B.torrent')
        shutil.copyfile('testencoding2.torrent.foo', cfn)

        datafns = [
            ('data1', '\u2605'),
            ('data2', '\u2606'),
            ('data3', '\u262E'),
            ('data4', '\u2600'),
        ]
        fnerrs = fnok = 0
        for srcfn, destfn in datafns:
            try:
                shutil.copyfile(srcfn, os.path.join(d2, destfn))
            except (EnvironmentError, UnicodeError):
                fnerrs += 1
            else:
                fnok += 1

        test_generic(cfvcmd + ' -q -T -p ' + d, rcurry(cfv_status_test, notfound=fnok, ferror=fnerrs))
        test_generic(cfvcmd + ' -v -T -p ' + d, rcurry(cfv_all_test, ok=0, notfound=fnok, ferror=fnerrs))
        bakad = os.path.join(d, '\u3070\u304B')
        os.mkdir(bakad)
        for srcfn, destfn in datafns:
            try:
                shutil.copyfile(srcfn, os.path.join(bakad, destfn))
            except (EnvironmentError, UnicodeError):
                pass
        test_generic(cfvcmd + ' -q -m -T -p ' + d, rcurry(cfv_status_test, ferror=fnerrs))
        test_generic(cfvcmd + ' -v -m -T -p ' + d, rcurry(cfv_all_test, ok=fnok, ferror=fnerrs))
        test_generic(cfvcmd + ' -v -m -u -T -p ' + d, rcurry(cfv_all_test, ok=fnok, ferror=fnerrs, unv=0))
        if not fnerrs:
            # if some of the files can't be found, checking of remaining files will fail due to missing pieces
            test_generic(cfvcmd + ' -q -T -p ' + d, rcurry(cfv_status_test))
            test_generic(cfvcmd + ' -v -T -p ' + d, rcurry(cfv_all_test, ok=4))
            test_generic(cfvcmd + ' -v -u -T -p ' + d, rcurry(cfv_all_test, ok=4, unv=0))

        raw_fnok = 0
        files_fnok = files_fnerrs = 0
        raw_files_fnok = raw_files_fnerrs = 0
        dirn = list(filter(lambda s: not s.endswith('torrent'), os.listdir(d)))[0]
        try:
            files = [os.path.join(dirn, s) for s in os.listdir(os.path.join(d, dirn))]
        except EnvironmentError:
            files = []
        else:
            for fn in files:
                flag_ok_raw = flag_ok_files = False
                for srcfn, destfn in datafns:
                    if os.path.join('\u3070\u304B', destfn) == fn:
                        raw_fnok += 1
                        flag_ok_raw = True
                try:
                    open(os.path.join(d, fn), 'rb').close()
                except (EnvironmentError, UnicodeError):
                    files_fnerrs += 1
                else:
                    files_fnok += 1
                    flag_ok_files = True
                if flag_ok_files and flag_ok_raw:
                    raw_files_fnok += 1
                else:
                    raw_files_fnerrs += 1

        raw_fnerrs = len(datafns) - raw_fnok
        # print(len(files), files)
        # print('raw', raw_fnok, raw_fnerrs)
        # print('files', files_fnok, files_fnerrs)
        # print('raw_files', raw_files_fnok, raw_files_fnerrs)

        if files:
            test_generic(cfvcmd + ' -v -m -T -p ' + d + ' ' + ' '.join(files), rcurry(cfv_all_test, ok=files_fnok, notfound=files_fnerrs))
            if files_fnok == len(datafns):
                test_generic(cfvcmd + ' -v -T -p ' + d + ' ' + ' '.join(files), rcurry(cfv_all_test, ok=files_fnok, notfound=files_fnerrs))
            test_generic(cfvcmd + ' --encoding=raw -v -m -T -p ' + d + ' ' + ' '.join(files), rcurry(cfv_all_test, ok=raw_files_fnok))
            if raw_files_fnok == len(datafns):
                test_generic(cfvcmd + ' --encoding=raw -v -T -p ' + d + ' ' + ' '.join(files), rcurry(cfv_all_test, ok=raw_files_fnok))

        test_generic(cfvcmd + ' --encoding=raw -m -v -T -p ' + d, rcurry(cfv_all_test, ok=raw_fnok, notfound=raw_fnerrs))
        test_generic(cfvcmd + ' --encoding=raw -m -v -u -T -p ' + d, rcurry(cfv_all_test, ok=raw_fnok, unv=fnok - raw_fnok, notfound=raw_fnerrs))
        if raw_fnok == len(datafns):
            test_generic(cfvcmd + ' --encoding=raw -v -T -p ' + d, rcurry(cfv_all_test, ok=raw_fnok, notfound=raw_fnerrs))
            test_generic(cfvcmd + ' --encoding=raw -v -u -T -p ' + d, rcurry(cfv_all_test, ok=raw_fnok, unv=fnok - raw_fnok, notfound=raw_fnerrs))
    except Exception:
        test_log_results('test_encoding2', 'foobar', ''.join(traceback.format_exception(*sys.exc_info())), 'foobar', {})  # yuck.  I really should switch this crap all to unittest ...
    # finally:
    shutil.rmtree(d2)
    shutil.rmtree(d)


def largefile2GB_test():
    # hope you have sparse file support ;)
    fn = os.path.join('bigfile2', 'bigfile')
    try:
        with open(fn, 'wb') as f:
            f.write(b'hi')
            f.seek(2 ** 30)
            f.write(b'foo')
            f.seek(2 ** 31)
            f.write(b'bar')
        test_generic(cfvcmd + ' -v -T -p %s' % 'bigfile2', rcurry(cfv_all_test, ok=6))
    finally:
        os.unlink(fn)


def largefile4GB_test():
    # hope you have sparse file support ;)
    fn = os.path.join('bigfile', 'bigfile')
    try:
        with open(fn, 'wb') as f:
            f.write(b'hi')
            f.seek(2 ** 30)
            f.write(b'foo')
            f.seek(2 ** 31)
            f.write(b'bar')
            f.seek(2 ** 32)
            f.write(b'baz')
        test_generic(cfvcmd + ' -v -T -p %s' % 'bigfile', rcurry(cfv_all_test, ok=10))
    finally:
        os.unlink(fn)


def manyfiles_test(t):
    try:
        max_open = os.sysconf('SC_OPEN_MAX')
    except (AttributeError, ValueError, OSError):
        max_open = 1024
    if not run_long_tests and max_open > 4096:
        print('max open files is big (%i)' % max_open, end=' ')
        max_open = 4096
        print('clipping to %i.  Use --long to try the real value' % max_open)
    num = max_open + 1
    d = tempfile.mkdtemp()
    try:
        for i in range(0, num):
            n = '%04i' % i
            with open(os.path.join(d, n), 'wt') as f:
                f.write(n)
        cfn = os.path.join(d, 'manyfiles.' + t)
        test_generic(cfvcmd + ' -C -p %s -t %s -f %s' % (d, t, cfn), rcurry(cfv_all_test, ok=num))
        test_generic(cfvcmd + ' -T -p %s -f %s' % (d, cfn), rcurry(cfv_all_test, ok=num))
    finally:
        shutil.rmtree(d)


def specialfile_test(cfpath):
    try:
        import threading
    except ImportError:
        return
    d = tempfile.mkdtemp()
    cfn = os.path.split(cfpath)[1]
    try:
        fpath = os.path.join(d, 'foo.bar')
        try:
            os.mkfifo(fpath)
        except (AttributeError, EnvironmentError):
            return
        shutil.copyfile(cfpath, os.path.join(d, cfn))

        def pusher(fpath):
            with open(fpath, 'wb') as f:
                f.write(b'a' * 0x4000)
                f.flush()
                time.sleep(0.1)
                f.write(b'b' * 0x4000)
                f.flush()
                time.sleep(0.1)
                f.write(b'c' * 0x4000)

        t = threading.Thread(target=pusher, args=(fpath,))
        t.start()
        s, o = cfvtest.runcfv('%s --progress=yes -T -p %s -f %s' % (cfvcmd, d, cfn))
        t.join()
        r = 0
        if s:
            r = 1
        elif o.count('#') > 1:
            r = 'count(#) = %s' % (o.count('#'))
        elif o.count('..'):
            r = 3
        test_log_results('specialfile_test(%s)' % cfn, s, o, r, None)
    finally:
        shutil.rmtree(d)


def unrecognized_cf_test():
    def cfv_unrectype(s, o):
        r = cfv_all_test(s, o, cferror=1)
        if r:
            return r
        if not o.count('type'):
            return "'type' not found in output"
        if o.count('encoding'):
            return "'encoding' found in output"
        return 0

    def cfv_unrecenc(s, o):
        r = cfv_all_test(s, o, cferror=1)
        if r:
            return r
        if not o.count('type'):
            return "'type' not found in output"
        if not o.count('encoding'):
            return "'encoding' not found in output"
        return 0

    # data1 is not a valid checksum file, but it is valid latin1, so it should only generate an unrecognized type error
    test_generic(cfvcmd + ' -T --encoding=latin1 -f data1', cfv_unrectype)
    # data1 is not a valid checksum file, nor is it valid utf-16 (no bom, odd number of bytes), so it should generate an unrecognized type or encoding error
    test_generic(cfvcmd + ' -T --encoding=utf-16 -f data1', cfv_unrecenc)


def private_torrent_test():
    cmd = cfvcmd
    tmpd = tempfile.mkdtemp()
    try:
        needle = b'7:privatei1'
        f = os.path.join(tmpd, 'test.torrent')
        test_generic('%s -C -f %s data1' % (cmd, f), cfv_test)
        data = readfile(f)
        test_log_results('should not contain private flag', 0, repr(data), needle in data, None)

        f = os.path.join(tmpd, 'test2.torrent')
        test_generic('%s --private_torrent -C -f %s data1' % (cmd, f), cfv_test)
        data = readfile(f)
        test_log_results('should contain private flag', 0, repr(data), needle not in data, None)
    finally:
        shutil.rmtree(tmpd)


def all_unittest_tests():
    if not run_internal:
        return 0
    test_log_start('all_unittests_suite', None)
    from unittest import TextTestRunner
    suite = cfvtest.all_unittests_suite()
    runner = TextTestRunner(stream=logfile, descriptions=1, verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        r = '%i failures, %i errors' % tuple(map(len, (result.failures, result.errors)))
    else:
        r = 0
    test_log_finish('all_unittests_suite', not result.wasSuccessful(), r, None, None)

    return len(result.failures) + len(result.errors)


run_internal = 1
run_long_tests = 0
run_unittests_only = 0
run_exit_early = 0


def show_help_and_exit(err=None):
    if err:
        print('error:', err)
        print()
    print('usage: test.py [-i|-e] [--long] [--unit] [--exit-early] [cfv]')
    print(' -i      run tests internally')
    print(' -e      launch separate cfv process for each test')
    print(' --long  include tests that may use large amounts of CPU or disk')
    print(' --unit  run only unittests, no integration tests')
    print(' --exit-early exit after first error')
    print(' --help  show this help')
    print()
    print('default [cfv] is:', cfvtest.cfvfn)
    print('default run mode is:', run_internal and 'internal' or 'external')
    sys.exit(1)


try:
    optlist, args = getopt.getopt(sys.argv[1:], 'ie', ['long', 'help', 'unit', 'exit-early'])
except getopt.error as e:
    show_help_and_exit(e)

if len(args) > 1:
    show_help_and_exit('too many arguments')

for o, a in optlist:
    if o == '--help':
        show_help_and_exit()
    elif o == '--long':
        run_long_tests = 1
    elif o == '--unit':
        run_unittests_only = 1
    elif o == '--exit-early':
        run_exit_early = 1
    elif o == '-i':
        run_internal = 1
    elif o == '-e':
        run_internal = 0
    else:
        show_help_and_exit('bad opt %r' % o)


cfvtest.setcfv(fn=args and args[0] or None, internal=run_internal)

if run_unittests_only:
    logfile = sys.stdout
    all_unittest_tests()
    sys.exit()

# set everything to default in case user has different in config file
cfvcmd = '-ZNVRMUI --unquote=no --fixpaths="" --strippaths=0 --showpaths=auto-relative --progress=no --announceurl=url --noprivate_torrent'

logfile = open(os.path.join(tempfile.gettempdir(), 'cfv_%s_test-%s.log' % (cfvtest.ver_cfv, time.strftime('%Y%m%dT%H%M%S'))), 'wt')


def all_tests():
    stats.ok = stats.failed = 0

    symlink_test()
    deep_unverified_test()

    for fmt in coreutilsfmts():
        ren_test(fmt)
    ren_test('md5', extra='-rr')
    ren_test('bsdmd5')
    ren_test('sfv')
    ren_test('sfvmd5')
    ren_test('csv')
    ren_test('csv2')
    ren_test('csv4')
    ren_test('crc')
    ren_test('torrent')

    for t in allavailablefmts():
        if t != 'torrent':
            search_test(t)
        search_test(t, test_nocrc=1)
    # search_test('torrent',test_nocrc=1,extra='--strip=1')
    quoted_search_test()

    for fmt in coreutilsfmts():
        T_test('.' + fmt)
    T_test('.md5.gz')
    T_test('comments.md5')
    T_test('.bsdmd5')
    # test par spec 1.0 files:
    T_test('.par')
    T_test('.p01')
    # test par spec 0.9 files:
    T_test('v09.par')
    T_test('v09.p01')
    T_test('.par2')
    T_test('.vol0+1.par2')
    T_test('.csv')
    T_test('.sfv')
    T_test('noheader.sfv')
    T_test('.sfvmd5')
    T_test('.csv2')
    T_test('.csv4')
    T_test('.crc')
    T_test('nosize.crc')
    T_test('nodims.crc')
    T_test('nosizenodimsnodesc.crc')
    for fmt in coreutilsfmts():
        T_test('crlf.' + fmt)
    T_test('crlf.bsdmd5')
    T_test('crlf.csv')
    T_test('crlf.csv2')
    T_test('crlf.csv4')
    T_test('crlf.sfv')
    T_test('noheadercrlf.sfv')
    T_test('crlf.crc')
    for fmt in coreutilsfmts():
        T_test('crcrlf.' + fmt)
    T_test('crcrlf.bsdmd5')
    T_test('crcrlf.csv')
    T_test('crcrlf.csv2')
    T_test('crcrlf.csv4')
    T_test('crcrlf.sfv')
    T_test('noheadercrcrlf.sfv')
    T_test('crcrlf.crc')
    for strip in (0, 1):
        T_test('.torrent', extra='--strip=%s' % strip)
        T_test('smallpiece.torrent', extra='--strip=%s' % strip)
        T_test('encoding.torrent', extra='--strip=%s' % strip)

    def cfv_torrentcommentencoding_test(s, o):
        r = cfv_all_test(s, o, ok=1)
        if r:
            return r
        tcount = o.count('Test_Comment-Text.')
        if tcount != 1:
            return 'encoded text count: %s' % tcount
        return 0

    test_generic(cfvcmd + ' -T -v -f testencodingcomment.torrent', cfv_torrentcommentencoding_test)
    test_encoding2()
    test_encoding_detection()
    unrecognized_cf_test()

    # test handling of directory args in recursive testmode. (Disabled since this isn't implemented, and I'm not sure if it should be.  It would change the meaning of cfv *)
    # test_generic(cfvcmd + ' -r a', cfv_test)
    # test_generic(cfvcmd + ' -ri a', cfv_test)
    # test_generic(cfvcmd + ' -ri A', cfv_test)
    # test_generic(cfvcmd + ' -rm a', cfv_test)
    # test_generic(cfvcmd + ' -rim a', cfv_test)
    # test_generic(cfvcmd + ' -r a/C', cfv_test)
    # test_generic(cfvcmd + ' -ri A/c', cfv_test)

    # test handling of testfile args in recursive testmode
    test_generic(cfvcmd + ' -r -p a ' + os.path.join('C', 'foo.bar'), cfv_test)
    test_generic(cfvcmd + ' -ri -p a ' + os.path.join('c', 'fOo.BaR'), cfv_test)
    test_generic(cfvcmd + ' -r -u -p a ' + os.path.join('C', 'foo.bar'), cfv_test)
    test_generic(cfvcmd + ' -ri -u -p a ' + os.path.join('c', 'fOo.BaR'), cfv_test)

    def cfv_notfound_or_bad_test(path):
        if os.path.exists(path):
            return cfv_bad_test
        else:
            return cfv_notfound_test

    test_generic(cfvcmd + ' --strippaths=0 -T -f teststrip0.csv4', cfv_test)
    test_generic(cfvcmd + ' --strippaths=1 -T -f teststrip1.csv4', cfv_test)
    test_generic(cfvcmd + ' --strippaths=2 -T -f teststrip2.csv4', cfv_test)
    test_generic(cfvcmd + ' --strippaths=all -T -f teststrip-1.csv4', cfv_test)
    test_generic(cfvcmd + ' --strippaths=none -T -f teststrip-none.csv4', cfv_notfound_or_bad_test('/data1'))
    test_generic(cfvcmd + r' --strippaths=0 --fixpaths \\/ -T -f testdrivestrip.md5', rcurry(cfv_all_test, ok=4))
    test_generic(cfvcmd + r' --strippaths=0 --unquote=yes --fixpaths \\/ -T -f testdrivestripquoted.md5', rcurry(cfv_all_test, ok=4))
    test_generic(cfvcmd + r' --strippaths=0 --unquote=yes --fixpaths \\/ -T -f testdrivestripquoted.md5 data1 data3 data4', rcurry(cfv_all_test, ok=3))

    test_generic(cfvcmd + ' -i -T -f testcase.csv', cfv_test)
    test_generic(cfvcmd + ' -T --unquote=yes -f testquoted.sfv', cfv_test)
    test_generic(cfvcmd + ' -i --unquote=yes -T -f testquotedcase.sfv', cfv_test)
    test_generic(cfvcmd + ' -i --unquote=yes -T -f testquotedcase.sfv DaTa1 ' + os.path.join('a', 'C', 'Foo.bar'), rcurry(cfv_all_test, ok=2))
    test_generic(cfvcmd + ' -i -T -f testquoted.csv4', cfv_test)
    test_generic(cfvcmd + r' --fixpaths \\/ -T -f testfix.csv', cfv_test)
    test_generic(cfvcmd + r' --fixpaths \\/ -T -f testfix.csv4', cfv_test)
    test_generic(cfvcmd + r' -i --fixpaths \\/ -T -f testfix.csv4', cfv_test)

    C_test('bsdmd5', '-t bsdmd5')  # ,verify=lambda f: test_generic('md5 -c ' + f, status_test)) #bsd md5 seems to have no way to check, only create
    for fmt in coreutilsfmts():
        if pathfind(fmt + 'sum'):  # don't report pointless errors on systems that don't have e.g. sha1sum
            def coreutils_verify(f):
                test_external(fmt + 'sum -c ' + f, status_test)
        else:
            print('skipping %s verify using external tool %ssum, as it is not installed.' % (fmt, fmt))
            coreutils_verify = None
        C_test(fmt, verify=coreutils_verify)
    C_test('csv')
    if pathfind('cksfv'):  # don't report pointless errors on systems that don't have cksfv
        def sfvverify(f):
            test_external('cksfv -f ' + f, status_test)
    else:
        print('skipping sfv verify using external tool cksfv, as it is not installed.')
        sfvverify = None
    C_test('sfv', verify=sfvverify)
    C_test('sfvmd5', '-t sfvmd5')
    C_test('csv2', '-t csv2')
    C_test('csv4', '-t csv4')
    C_test('crc')
    private_torrent_test()
    # test_generic('../cfv -V -T -f test.md5', cfv_test)
    # test_generic('../cfv -V -tcsv -T -f test.md5', cfv_test)
    for t in allavailablefmts():
        if fmt_istext(t):
            test_generic(cfvcmd + ' --encoding=cp500 -T -f test.' + t, rcurry(cfv_all_test, cferror=1))
        else:
            if t == 'par':
                try:
                    open('data1'.encode('utf-16le').decode('utf-16be'), 'rb').close()
                except UnicodeError:
                    nf = 0
                    err = 4
                except Exception:
                    nf = 4
                    err = 0
                test_generic(cfvcmd + ' --encoding=utf-16be -T -f test.' + t, rcurry(cfv_all_test, notfound=nf, ferror=err))
                test_generic(cfvcmd + ' --encoding=cp500 -T -f test.' + t, rcurry(cfv_all_test, cferror=4))
                test_generic(cfvcmd + ' --encoding=cp500 -i -T -f test.' + t, rcurry(cfv_all_test, cferror=4))
            else:
                try:
                    open(b'data1'.decode('cp500'), 'rb').close()
                except UnicodeError:
                    nf = 0
                    err = 4
                except Exception:
                    nf = 4
                    err = 0
                test_generic(cfvcmd + ' --encoding=cp500 -T -f test.' + t, rcurry(cfv_all_test, notfound=nf, ferror=err))
                test_generic(cfvcmd + ' --encoding=cp500 -i -T -f test.' + t, rcurry(cfv_all_test, notfound=nf, ferror=err))

        if fmt_cancreate(t):
            C_funkynames_test(t)
            manyfiles_test(t)
    for fn in glob(os.path.join('fifotest', 'fifo.*')):
        specialfile_test(fn)

    test_generic(cfvcmd + ' -m -v -T -t sfv', lambda s, o: cfv_typerestrict_test(s, o, 'sfv'))
    test_generic(cfvcmd + ' -m -v -T -t sfvmd5', lambda s, o: cfv_typerestrict_test(s, o, 'sfvmd5'))
    test_generic(cfvcmd + ' -m -v -T -t bsdmd5', lambda s, o: cfv_typerestrict_test(s, o, 'bsdmd5'))
    for fmt in coreutilsfmts():
        test_generic(cfvcmd + ' -m -v -T -t ' + fmt, lambda s, o: cfv_typerestrict_test(s, o, fmt))
    test_generic(cfvcmd + ' -m -v -T -t csv', lambda s, o: cfv_typerestrict_test(s, o, 'csv'))
    test_generic(cfvcmd + ' -m -v -T -t par', lambda s, o: cfv_typerestrict_test(s, o, 'par'))
    test_generic(cfvcmd + ' -m -v -T -t par2', lambda s, o: cfv_typerestrict_test(s, o, 'par2'))

    test_generic(cfvcmd + ' -u -t md5 -f test.md5 data* unchecked.dat test.md5', cfv_unv_test)
    test_generic(cfvcmd + ' -u -f test.md5 data* unchecked.dat', cfv_unv_test)
    test_generic(cfvcmd + ' -u -f test.md5 data* unchecked.dat test.md5', cfv_unv_test)
    test_generic(cfvcmd + r' -i -tcsv --fixpaths \\/ -Tu', lambda s, o: cfv_unv_test(s, o, None))
    test_generic(cfvcmd + ' -T -t md5 -f non_existent_file', cfv_cferror_test)
    test_generic(cfvcmd + ' -T -f ' + os.path.join('corrupt', 'missingfiledesc.par2'), cfv_cferror_test)
    test_generic(cfvcmd + ' -T -f ' + os.path.join('corrupt', 'missingmain.par2'), cfv_cferror_test)
    test_generic(cfvcmd + ' -T -m -f ' + os.path.join('corrupt', 'missingfiledesc.par2'), cfv_cferror_test)
    test_generic(cfvcmd + ' -T -m -f ' + os.path.join('corrupt', 'missingmain.par2'), cfv_cferror_test)

    test_generic(cfvcmd + ' -T -f foo.torrent', cfv_test)
    test_generic(cfvcmd + ' -T --strip=none -p foo -f ../foo.torrent', rcurry(cfv_all_test, notfound=7))
    for strip in (0, 1):
        test_generic(cfvcmd + ' -T --strippaths=%s -p foo -f %s' % (strip, os.path.join(os.pardir, 'foo.torrent')), rcurry(cfv_all_test, ok=7))
        test_generic(cfvcmd + ' -T --strippaths=%s -p foo2err -f %s' % (strip, os.path.join(os.pardir, 'foo.torrent')), rcurry(cfv_all_test, ok=4, badcrc=3))
        test_generic(cfvcmd + ' -T --strippaths=%s -p foo2err -f %s foo1 foo4' % (strip, os.path.join(os.pardir, 'foo.torrent')), rcurry(cfv_all_test, ok=0, badcrc=2))
        test_generic(cfvcmd + ' -T --strippaths=%s -p foo2err1 -f %s' % (strip, os.path.join(os.pardir, 'foo.torrent')), rcurry(cfv_all_test, ok=6, badcrc=1))
        test_generic(cfvcmd + ' -T --strippaths=%s -p foo2err1 -f %s foo1 foo4' % (strip, os.path.join(os.pardir, 'foo.torrent')), rcurry(cfv_all_test, ok=2))
        test_generic(cfvcmd + ' -T --strippaths=%s -p foo2badsize -f %s' % (strip, os.path.join(os.pardir, 'foo.torrent')), rcurry(cfv_all_test, ok=5, badsize=1, badcrc=1))
        test_generic(cfvcmd + ' -T --strippaths=%s -p foo2badsize -f %s foo1 foo4' % (strip, os.path.join(os.pardir, 'foo.torrent')), rcurry(cfv_all_test, ok=1, badcrc=1))
        test_generic(cfvcmd + ' -T --strippaths=%s -p foo2missing -f %s' % (strip, os.path.join(os.pardir, 'foo.torrent')), rcurry(cfv_all_test, ok=4, badcrc=2, notfound=1))
        test_generic(cfvcmd + ' -T --strippaths=%s -p foo2missing -f %s foo1 foo4' % (strip, os.path.join(os.pardir, 'foo.torrent')), rcurry(cfv_all_test, ok=0, badcrc=2))
    d = tempfile.mkdtemp()
    try:
        open(os.path.join(d, 'foo'), 'wb').close()
        cmd = cfvcmd.replace(' --announceurl=url', '')
        test_generic(cmd + ' -C -p %s -f foo.torrent' % d, rcurry(cfv_all_test, files=1, cferror=1))
        test_log_results('non-creation of empty torrent on missing announceurl?', '', repr(os.listdir(d)), len(os.listdir(d)) > 1, {})
    finally:
        shutil.rmtree(d)

    if run_long_tests:
        largefile2GB_test()
        largefile4GB_test()

    test_generic(cfvcmd + ' -t aoeu', rcurry(cfv_cftypehelp_test, 1), stdout='/dev/null')
    test_generic(cfvcmd + ' -t aoeu', rcurry(cfv_nooutput_test, 1), stderr='/dev/null')
    test_generic(cfvcmd + ' -t help', rcurry(cfv_cftypehelp_test, 0), stderr='/dev/null')
    test_generic(cfvcmd + ' -t help', rcurry(cfv_nooutput_test, 0), stdout='/dev/null')

    test_generic(cfvcmd + ' -h', cfv_nooutput_test, stdout='/dev/null')
    test_generic(cfvcmd + ' -h', cfv_version_test, stderr='/dev/null')

    donestr = '\n>>> tests finished:  ok: %i  failed: %i' % (stats.ok, stats.failed)
    log(donestr)
    print(donestr)

    return stats.failed


def copytree(src, dst, ignore=None):
    if ignore is None:
        ignore = []
    for name in os.listdir(src):
        if name in ignore:
            continue
        srcname = os.path.join(src, name)
        dstname = os.path.join(dst, name)
        if os.path.islink(srcname):
            continue
        elif os.path.isfile(srcname):
            shutil.copy(srcname, dstname)
        elif os.path.isdir(srcname):
            os.mkdir(dstname)
            copytree(srcname, dstname, ignore)
        else:
            print('huh?', srcname)


# copy the testdata into a temp dir in order to avoid .svn dirs breaking some tests
tmpdatapath = tempfile.mkdtemp()
try:
    copytree(cfvtest.datapath, tmpdatapath, ignore=['.svn'])
    os.chdir(tmpdatapath)  # do this after the setcfv, since the user may have specified a relative path

    failed = 0
    print('>>> testing...')
    failed += all_unittest_tests()
    failed += all_tests()
    if cfvtest.ver_mmap:
        print('>>> testing without mmap...')
        cfvtest.setenv('CFV_NOMMAP', 'x')
        assert not cfvtest.ver_mmap
        failed += all_tests()
    sys.exit(failed)
finally:
    shutil.rmtree(tmpdatapath)
    logfile.close()
