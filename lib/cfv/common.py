#! /usr/bin/env python

#    cfv - Command-line File Verify
#    Copyright (C) 2000-2013  Matthew Mueller <donut AT dakotacom DOT net>
#    Copyright (C) 2018-2019  David Gnedt <cfv-project AT davizone DOT at>
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

__version__ = '2.0.0.dev2'
__homepage__ = 'https://github.com/cfv-project/cfv'


import copy
import errno
import getopt
import os
import re
import struct
import sys
import time
from binascii import hexlify, unhexlify
from stat import S_ISDIR, S_ISREG

from cfv import caching
from cfv import cftypes
from cfv import fileutil
from cfv import hash
from cfv import osutil
from cfv import strutil
from cfv import ui
from cfv.BitTorrent import bencode, btformats


def cfencode(s, preferred=None):
    if config.encoding == 'raw':
        if isinstance(s, unicode):
            return s.encode(osutil.fsencoding)
        return s
    else:
        return s.encode(config.getencoding(preferred))


class FilenameError(ValueError):
    pass


def cfdecode(s, preferred=None):
    if config.encoding != 'raw':
        s = unicode(s, config.getencoding(preferred))
    return s


def cffndecode(s, preferred=None):
    s = cfdecode(s, preferred)
    if not osutil.fs_nullsok and '\0' in s:
        raise FilenameError('filename contains null characters')
    return s


class Data:
    def __init__(self, **kw):
        self.__dict__.update(kw)


curdir = osutil.getcwdu()
reldir = [u'']
prevdir = []


def chdir(d):
    global curdir
    os.chdir(d)
    prevdir.append((curdir, cache._path_key_cache))
    reldir.append(osutil.path_join(reldir[-1], d))
    curdir = osutil.getcwdu()
    cache._path_key_cache = {}


def cdup():
    global curdir
    reldir.pop()
    curdir, cache._path_key_cache = prevdir.pop()
    os.chdir(curdir)


class CFVException(Exception):
    pass


class CFVValueError(CFVException):
    # invalid argument in user input
    pass


class CFVNameError(CFVException):
    # invalid command in user input
    pass


class CFVSyntaxError(CFVException):
    # error in user input
    pass


class CFError(ValueError):
    # error in checksum file
    pass


class FileNameFilter:
    def __init__(self, testfiles=None):
        self.testfiles = set()
        if testfiles:
            self.set_testfiles(testfiles)

    def set_testfiles(self, testfiles):
        for fn in testfiles:
            fn = osutil.path_join(reldir[-1], fn)
            if config.ignorecase:
                fn = fn.lower()
            if config.encoding == 'raw' and isinstance(fn, unicode):
                try:
                    fn = fn.encode(osutil.fsencoding)
                except UnicodeError:
                    pass
            self.testfiles.add(fn)

    def should_test(self, fn):
        if not self.testfiles:
            return 1
        fn = osutil.path_join(reldir[-1], fn)
        if config.ignorecase:
            fn = fn.lower()
        return fn in self.testfiles


def getfilehash(filename, hashname, hashfunc):
    finfo = cache.getfinfo(filename)
    if hashname not in finfo:
        if view.progress:
            view.progress.init(filename)
        try:
            hash, size = hashfunc(filename, view.progress and view.progress.update or None)
        finally:
            if view.progress:
                view.progress.cleanup()
        finfo[hashname], finfo['size'] = hash, size
        stats.bytesread += size
    return finfo[hashname], finfo['size']


def getfilesha1(filename):
    return getfilehash(filename, 'sha1', hash.getfilesha1)


def getfilemd5(filename):
    return getfilehash(filename, 'md5', hash.getfilemd5)


def getfilecrc(filename):
    return getfilehash(filename, 'crc', hash.getfilecrc)


def rename(oldfn, newfn):
    os.rename(oldfn, newfn)
    cache.rename(oldfn, newfn)


class Stats:
    def __init__(self):
        self.num = 0
        self.ok = 0
        self.badsize = 0
        self.badcrc = 0
        self.notfound = 0
        self.ferror = 0
        self.cferror = 0
        self.bytesread = 0
        self.unverified = 0
        self.diffcase = 0
        self.misnamed = 0
        self.quoted = 0
        self.textmode = 0
        self.starttime = time.time()
        self.subcount = 0

    def make_sub_stats(self):
        b = copy.copy(self)
        b.starttime = time.time()
        return b

    def sub_stats_end(self, end):
        for v in 'badcrc', 'badsize', 'bytesread', 'cferror', 'diffcase', 'misnamed', 'ferror', 'notfound', 'num', 'ok', 'quoted', 'unverified', 'textmode':
            setattr(self, v, getattr(end, v) - getattr(self, v))
        end.subcount += 1

    def __str__(self):
        counts = [
            '%i files' % self.num,
            '%i OK' % self.ok,
        ]
        if self.badcrc:
            counts.append('%i badcrc' % self.badcrc)
        if self.badsize:
            counts.append('%i badsize' % self.badsize)
        if self.notfound:
            counts.append('%i not found' % self.notfound)
        if self.ferror:
            counts.append('%i file errors' % self.ferror)
        if self.unverified:
            counts.append('%i unverified' % self.unverified)
        if self.cferror:
            counts.append('%i chksum file errors' % self.cferror)
        if self.misnamed:
            counts.append('%i misnamed' % self.misnamed)
        if self.diffcase:
            counts.append('%i differing cases' % self.diffcase)
        if self.quoted:
            counts.append('%i quoted filenames' % self.quoted)
        if self.textmode:
            counts.append('%i tested in textmode' % self.textmode)
        s = ', '.join(counts)

        elapsed = time.time() - self.starttime
        s += '.  %.3f seconds, ' % elapsed
        if elapsed == 0.0:
            s += '%.1fK' % (self.bytesread / 1024.0)
        else:
            s += '%.1fK/s' % (self.bytesread / elapsed / 1024.0)

        return s


class Config:
    verbose = 0  # -1=quiet  0=norm  1=noisy
    docrcchecks = 1
    dirsort = 1
    cmdlinesort = 1
    cmdlineglob = 'a'
    recursive = 0
    showunverified = 0
    default_type_name = 'sfv'
    ignorecase = 0
    unquote = 0
    fixpaths = None
    strippaths = 0
    showpaths = 2
    showpathsabsolute = 0
    gzip = 0
    rename = 0
    search = 0
    renameformat = '%(name)s.bad-%(count)i%(ext)s'
    renameformatnocount = 0
    list = 0
    listsep = '\n'
    dereference = 1
    progress = 'a'
    announceurl = None
    piece_size_pow2 = 18
    private_torrent = False
    encoding = 'auto'

    def getencoding(self, preferred=None):
        return osutil.getencoding(self.encoding, preferred)

    def setencoding(self, v):
        if v in ('raw', 'auto'):
            pass
        else:
            try:
                u'a'.encode(v)
            except (UnicodeError, LookupError), e:
                raise CFVValueError('invalid encoding option: %s' % e)
        self.encoding = v

    def setdefault(self, typename):
        if cftypes.has_handler(typename):
            self.default_type_name = typename
        else:
            raise CFVValueError("invalid default type '%s'" % typename)

    def setintr(self, o, v, min, max):
        try:
            x = int(v)
            if x > max or x < min:
                raise CFVValueError("out of range int '%s' for %s" % (v, o))
            self.__dict__[o] = x
        except ValueError:
            raise CFVValueError("invalid int type '%s' for %s" % (v, o))

    def setbool(self, o, v):
        v = v.lower()
        if v in ('yes', 'on', 'true', '1'):
            x = 1
        elif v in ('no', 'off', 'false', '0'):
            x = 0
        else:
            raise CFVValueError("invalid bool type '%s' for %s" % (v, o))
        self.__dict__[o] = x

    def setyesnoauto(self, o, v):
        if 'yes'.startswith(v.lower()):
            self.__dict__[o] = 'y'
        elif 'auto'.startswith(v.lower()):
            self.__dict__[o] = 'a'
        elif 'no'.startswith(v.lower()):
            self.__dict__[o] = 'n'
        else:
            raise CFVValueError("invalid %s option '%s', must be 'no', 'auto', or 'yes'" % (o, v))

    def setstr(self, o, v):
        self.__dict__[o] = v

    def setx(self, o, v):
        if o == 'default':
            self.setdefault(v)
        elif o in ('dirsort', 'cmdlinesort', 'ignorecase', 'rename', 'search', 'dereference', 'unquote', 'private_torrent'):
            self.setbool(o, v)
        elif o in ('cmdlineglob', 'progress'):
            self.setyesnoauto(o, v)
        elif o == 'verbose':
            try:
                self.setintr(o, v, -3, 1)
            except CFVValueError:
                if v == 'v':
                    self.verbose = 1
                elif v == 'V':
                    self.verbose = 0
                elif v == 'VV':
                    self.verbose = -1
                elif v == 'q':
                    self.verbose = -2
                elif v == 'Q':
                    self.verbose = -3
                else:
                    raise CFVValueError("invalid verbose option '%s', must be 'v', 'V', 'VV', 'q', 'Q' or -3 - 1" % v)
        elif o in ('gzip',):
            self.setintr(o, v, -1, 1)
        elif o in ('recursive', 'showunverified'):
            self.setintr(o, v, 0, 2)
        elif o == 'showpaths':
            p = 0
            a = 0
            for v in v.split('-'):
                if not p:
                    if 'none'.startswith(v.lower()) or v == '0':
                        self.showpaths = 0
                        p = 1
                        continue
                    elif 'auto'.startswith(v.lower()) or v == '2':
                        self.showpaths = 2
                        p = 1
                        continue
                    elif 'yes'.startswith(v.lower()) or v == '1':
                        self.showpaths = 1
                        p = 1
                        continue
                if not a:
                    if 'absolute'.startswith(v.lower()):
                        self.showpathsabsolute = 1
                        a = 1
                        continue
                    elif 'relative'.startswith(v.lower()):
                        self.showpathsabsolute = 0
                        a = 1
                        continue
                raise CFVValueError("invalid showpaths option '%s', must be 'none', 'auto', 'yes', 'absolute', or 'relative'" % v)
        elif o == 'strippaths':
            if 'none'.startswith(v.lower()):
                self.strippaths = 'n'
            elif 'all'.startswith(v.lower()):
                self.strippaths = 'a'
            else:
                try:
                    x = int(v)
                    if x < 0:
                        raise ValueError
                    self.strippaths = x
                except ValueError:
                    raise CFVValueError("invalid strippaths option '%s', must be 'none', 'all', or int >=0" % v)
        elif o == 'fixpaths':
            self.fixpaths = v and re.compile('[' + re.escape(v) + ']') or None
        elif o == 'renameformat':
            testmap = make_rename_formatmap('1.2')
            testmapwc = make_rename_formatmap('1.2')
            testmapwc['count'] = 1
            v % testmapwc  # format_test
            try:
                v % testmap  # format_test
                self.renameformatnocount = 1  # if we can get here, it doesn't use the count param
            except KeyError:
                self.renameformatnocount = 0
            self.renameformat = v
        elif o == 'filename_type':
            typename, match = v.split('=', 1)
            if not cftypes.has_handler(typename):
                raise CFVValueError("filename_type: invalid type '%s'" % typename)
            cftypes.add_user_cf_fn_regex(match, typename)
        elif o == 'announceurl':
            self.setstr(o, v)
        elif o == 'piece_size_pow2':
            self.setintr(o, v, 1, 30)
        else:
            raise CFVNameError("invalid option '%s'" % o)

    def readconfig(self):
        filename = os.path.expanduser(os.path.join('~', '.cfvrc'))
        if not os.path.isfile(filename):
            filename = os.path.expanduser(os.path.join('~', '_cfvrc'))
        if os.path.isfile(filename):
            with open(filename, 'r') as f:
                line_number = 0
                while 1:
                    line_number += 1
                    s = f.readline()
                    if not s:
                        break  # end of file
                    if s[0] == '#':
                        continue  # ignore lines starting with #
                    s = strutil.chomp(s)
                    if not s:
                        continue  # ignore blank lines
                    x = s.split(' ', 1)
                    if len(x) != 2:
                        raise CFVSyntaxError("%s:%i: invalid line '%s'" % (filename, line_number, s))
                    else:
                        o, v = x
                        try:
                            self.setx(o, v)
                        except CFVException, err:
                            # reuse the traceback of the original exception, but add file and line numbers to the error
                            raise sys.exc_info()[0], '%s:%i: %s' % (filename, line_number, err), sys.exc_info()[2]

    def __init__(self):
        self.readconfig()

    # TODO: This really should go in View, but it depends on curdir/reldir.  So we'll just stuff it here for now. (ick)
    def perhaps_showpath(self, filename):
        if self.showpaths == 1 or (self.showpaths == 2 and self.recursive):
            if self.showpathsabsolute:
                dir = curdir
            else:
                dir = reldir[-1]
            return osutil.path_join(strutil.showfn(dir), strutil.showfn(filename))
        return strutil.showfn(filename)


def make_rename_formatmap(l_filename):
    sp = os.path.splitext(l_filename)
    return {'name': sp[0], 'ext': sp[1], 'fullname': l_filename}


_hassymlinks = hasattr(os, 'symlink')


def parse_commentline(comment, commentchars):
    if comment and comment[0] in commentchars:
        return comment[1:].strip()
    return None


class ChksumType:
    def test_chksumfile(self, file, filename):
        if config.showunverified:  # we can't expect the checksum file itself to be checksummed
            cache.set_verified(filename)
        try:
            cf_stats = stats.make_sub_stats()
            if not file:
                file = fileutil.open_read(filename, config)
            self.do_test_chksumfile(file)
            cf_stats.sub_stats_end(stats)
            view.ev_test_cf_done(filename, cf_stats)
        except EnvironmentError, a:
            stats.cferror += 1
            view.ev_cf_enverror(filename, a)

    def do_test_chksumfile_print_testingline(self, file, comment=None):
        view.ev_test_cf_begin(self.name, file.name, comment)

    def search_file(self, filename, filecrc, filesize, errfunc, errargs):
        if not config.search or (filesize < 0 and (not filecrc or not config.docrcchecks)):  # don't bother searching if we don't have anything to compare against
            errfunc(*errargs)
            return -2
        alreadyok = None
        fpath, filenametail = os.path.split(filename)
        try:
            if fpath:
                if config.ignorecase:
                    fpath = cache.nocase_finddir(fpath)
                    filename = osutil.path_join(fpath, filenametail)  # fix the dir the orig filename is in, so that the do_f_found can rename it correctly
            else:
                fpath = osutil.curdiru
            ftails = osutil.listdir(fpath)
        except EnvironmentError:
            ftails = []
        for ftail in ftails:
            fn = osutil.path_join(fpath, ftail)
            try:
                if filesize >= 0:
                    fs = os.path.getsize(fn)
                    if fs != filesize:
                        continue
                if config.docrcchecks and filecrc is not None:
                    c = self.do_test_file(fn, filecrc)
                    if c:
                        continue
                    filecrct = hexlify(filecrc)
                else:
                    if not os.path.isfile(fn):
                        continue
                    filecrct = 'exists'
            except EnvironmentError:
                continue
            if cache.has_flag(fn, '_ok'):
                alreadyok = (fn, filecrct)
                continue
            errfunc(foundok=1, *errargs)
            self.do_f_found(filename, fn, filesize, filecrct)
            return 0
        if alreadyok:
            errfunc(foundok=1, *errargs)
            self.do_f_found(filename, alreadyok[0], filesize, alreadyok[1], alreadyok=1)
            return 0
        errfunc(*errargs)
        return -1

    def test_file(self, filename, filecrc, filesize=-1):
        filename = self.mangle_filename(filename)
        if not filenamefilter.should_test(filename):
            return
        stats.num += 1
        l_filename = filename
        try:
            l_filename = self.find_local_filename(filename)
            if filesize >= 0:
                fs = os.path.getsize(l_filename)
                if fs != filesize:
                    self.search_file(filename, filecrc, filesize,
                                     self.do_f_badsize, (l_filename, filesize, fs))
                    return -2
            if config.docrcchecks and filecrc:
                c = self.do_test_file(l_filename, filecrc)
                filecrct = hexlify(filecrc)
                if c:
                    self.search_file(filename, filecrc, filesize,
                                     self.do_f_badcrc, (l_filename, 'crc does not match (%s!=%s)' % (filecrct, hexlify(c))))
                    return -2
            else:
                if not os.path.exists(l_filename):
                    raise EnvironmentError(errno.ENOENT, 'missing')
                if not os.path.isfile(l_filename):
                    raise EnvironmentError(errno.ENOENT, 'not a file')
                filecrct = 'exists'  # since we didn't actually test the crc, make verbose mode merely say it exists
        except (EnvironmentError, UnicodeError), a:  # UnicodeError can occur if python can't map the filename to the filesystem's encoding
            self.search_file(filename, filecrc, filesize,
                             self.do_f_enverror, (l_filename, a))
            return -1
        self.do_f_ok(l_filename, filesize, filecrct)

    def make_chksumfile_create(self, filename):
        return fileutil.open_write(filename, config)

    def make_writefile(self, data, file):
        if data:
            file.write(data)

    def make_chksumfile_finish(self, file):
        file.close()

    @staticmethod
    def filename_ok(fn):
        return 1

    def do_f_enverror(self, l_filename, ex, foundok=0):
        if ex[0] == errno.ENOENT:
            if foundok:
                return
            stats.notfound += 1
        else:
            # if not foundok:
            stats.ferror += 1
        view.ev_f_enverror(l_filename, ex)

    def do_f_badsize(self, l_filename, expected, actual, foundok=0):
        if not foundok:
            stats.badsize += 1
        self.do_f_verifyerror(l_filename, 'file size does not match (%s!=%i)' % (expected, actual), foundok=foundok)

    def do_f_badcrc(self, l_filename, msg, foundok=0):
        if not foundok:
            stats.badcrc += 1
        self.do_f_verifyerror(l_filename, msg, foundok=foundok)

    def do_f_verifyerror(self, l_filename, a, foundok=0):
        if config.rename:
            formatmap = make_rename_formatmap(l_filename)
            for count in xrange(0, sys.maxint):
                formatmap['count'] = count
                newfilename = config.renameformat % formatmap
                if config.renameformatnocount and count > 0:
                    newfilename = '%s-%i' % (newfilename, count)
                if l_filename == newfilename:
                    continue  # if the filenames are the same they would cmp the same and be deleted. (ex. when renameformat='%(fullname)s')
                if os.path.exists(newfilename):
                    if osutil.fcmp(l_filename, newfilename):
                        os.unlink(l_filename)
                        view.ev_f_verifyerror_dupe(l_filename, a, newfilename, foundok)
                        return
                else:
                    rename(l_filename, newfilename)
                    view.ev_f_verifyerror_renamed(l_filename, a, newfilename, foundok)
                    return
        view.ev_f_verifyerror(l_filename, a, foundok)

    def do_f_found(self, filename, found_fn, filesize, filecrct, alreadyok=0):
        l_filename = found_fn
        if config.rename:
            try:
                if os.path.exists(filename):
                    verb = None, 'fixing name'
                    prep = 'of'
                    raise EnvironmentError('File exists')
                if alreadyok:
                    verb = 'linked', 'linking'
                    prep = 'to'
                    try:
                        os.link(found_fn, filename)
                    except (EnvironmentError, AttributeError), e:
                        if isinstance(e, EnvironmentError) and e[0] not in (errno.EXDEV, errno.EPERM):
                            raise
                        verb = 'copied', 'copying'
                        prep = 'from'
                        import shutil
                        shutil.copyfile(found_fn, filename)
                else:
                    verb = 'renamed', 'renaming'
                    prep = 'from'
                    rename(found_fn, filename)
            except EnvironmentError, e:
                action = '%s %s' % (verb[1], prep)
                stats.ferror += 1
                view.ev_f_found_renameetcerror(filename, filesize, filecrct, found_fn, action, e)
            else:
                action = '%s %s' % (verb[0], prep)
                l_filename = filename
                view.ev_f_found_renameetc(filename, filesize, filecrct, found_fn, action)
        else:
            view.ev_f_found(filename, filesize, filecrct, found_fn)
        if config.showunverified:
            cache.set_verified(l_filename)
        cache.set_flag(l_filename, '_ok')
        stats.misnamed += 1
        stats.ok += 1

    def do_f_ok(self, filename, filesize, filecrct, msg='OK', l_filename=None):
        cache.set_flag(l_filename or filename, '_ok')
        stats.ok += 1
        view.ev_f_ok(filename, filesize, filecrct, msg)

    def nocase_findfile_updstats(self, filename):
        cur = cache.nocase_findfile(filename)
        if filename != cur:
            stats.diffcase += 1
        return cur

    _os_sep_escaped = os.sep.replace('\\', '\\\\')

    def fixpath(self, filename):
        if config.fixpaths:
            return config.fixpaths.sub(self._os_sep_escaped, filename)
        return filename

    def mangle_filename(self, filename):
        if config.unquote and len(filename) > 1 and filename[0] == '"' and filename[-1] == '"':
            filename = filename[1:-1]  # work around buggy sfv encoders that quote filenames
            stats.quoted += 1
        if config.fixpaths:
            filename = self.fixpath(filename)
        filename = os.path.normpath(filename)
        if config.strippaths != 'n':
            filename = osutil.strippath(filename, config.strippaths)
        return filename

    def find_local_filename(self, l_filename):
        if config.ignorecase:
            # we need to find the correct filename if using
            # showunverified, even if the filename we are given works,
            # since on FAT/etc filesystems the incorrect case will still
            # return true from os.path.exists, but it could be the
            # incorrect case to remove from the unverified files list.
            if config.showunverified or not os.path.exists(l_filename):
                l_filename = self.nocase_findfile_updstats(l_filename)
        if config.showunverified:
            cache.set_verified(l_filename)
        return l_filename


class TextChksumType(ChksumType):
    def do_test_chksumfile(self, file):
        self.do_test_chksumfile_print_testingline(file)
        line_number = 0
        while 1:
            line_number += 1
            try:
                line = file.readline()
            except UnicodeError, e:
                stats.cferror += 1
                view.ev_test_cf_lineencodingerror(file.name, line_number, e)
                continue
            if not line:
                break
            if self.do_test_chksumline(line):
                stats.cferror += 1
                view.ev_test_cf_unrecognized_line(file.name, line_number)

    @staticmethod
    def filename_ok(fn):
        return len((fn + 'a').splitlines()) == 1


# Base class for md5sum/sha1sum style checksum file formats.
class FooSum_Base(TextChksumType):
    def do_test_chksumfile_print_testingline(self, file):
        TextChksumType.do_test_chksumfile_print_testingline(self, file, parse_commentline(file.peekline(512), ';#'))

    def do_test_chksumline(self, l):
        if l[0] in ';#':
            return
        x = self._foosum_rem.match(l)
        if not x:
            return -1
        if x.group(2) == ' ':
            if stats.textmode == 0:
                view.ev_generic_warning('file(s) tested in textmode')
            stats.textmode += 1
        self.test_file(x.group(3), unhexlify(x.group(1)))


def gnu_sum(algo):
    hasher, digestlen = hash.getfilechecksumgeneric(algo)
    hexlen = digestlen * 2

    class GnuSum_Base(FooSum_Base):
        name = algo
        description = 'GNU %ssum' % algo
        descinfo = '%s,name' % algo

        def do_test_file(self, filename, filecrc):
            c = getfilehash(filename, algo, hasher)[0]
            if c != filecrc:
                return c

        @staticmethod
        def auto_chksumfile_match(file, _autorem=re.compile(r'[0-9a-fA-F]{%d} [ *].' % hexlen)):
            line = file.peekline(4096)
            while line:
                if line[0] not in ';#':
                    return _autorem.match(line) is not None
                line = file.peeknextline(4096)

        auto_filename_match = algo

        _foosum_rem = re.compile(r'([0-9a-fA-F]{%s}) ([ *])([^\r\n]+)[\r\n]*$' % hexlen)

        @staticmethod
        def make_std_filename(filename):
            return '%s.%s' % (filename, algo)

        def make_addfile(self, filename):
            crc = hexlify(getfilehash(filename, algo, hasher)[0])
            return (crc, -1), '%s *%s' % (crc, filename) + os.linesep

    return GnuSum_Base


try:
    cftypes.register_cftype(gnu_sum('sha512'))
except (ImportError, ValueError):
    pass

try:
    cftypes.register_cftype(gnu_sum('sha384'))
except (ImportError, ValueError):
    pass

try:
    cftypes.register_cftype(gnu_sum('sha256'))
except (ImportError, ValueError):
    pass

try:
    cftypes.register_cftype(gnu_sum('sha224'))
except (ImportError, ValueError):
    pass


# ---------- sha1sum ----------

class SHA1_MixIn:
    def do_test_file(self, filename, filecrc):
        c = getfilesha1(filename)[0]
        if c != filecrc:
            return c


class SHA1(FooSum_Base, SHA1_MixIn):
    name = 'sha1'
    description = 'GNU sha1sum'
    descinfo = 'SHA1,name'

    @staticmethod
    def auto_chksumfile_match(file, _autorem=re.compile(r'[0-9a-fA-F]{40} [ *].')):
        line = file.peekline(4096)
        while line:
            if line[0] not in ';#':
                return _autorem.match(line) is not None
            line = file.peeknextline(4096)

    auto_filename_match = 'sha1'

    _foosum_rem = re.compile(r'([0-9a-fA-F]{40}) ([ *])([^\r\n]+)[\r\n]*$')

    @staticmethod
    def make_std_filename(filename):
        return filename + '.sha1'

    def make_addfile(self, filename):
        crc = hexlify(getfilesha1(filename)[0])
        return (crc, -1), '%s *%s' % (crc, filename) + os.linesep


cftypes.register_cftype(SHA1)


# ---------- md5 ----------

class MD5_MixIn:
    def do_test_file(self, filename, filecrc):
        c = getfilemd5(filename)[0]
        if c != filecrc:
            return c


class MD5(FooSum_Base, MD5_MixIn):
    name = 'md5'
    description = 'GNU md5sum'
    descinfo = 'MD5,name'

    @staticmethod
    def auto_chksumfile_match(file, _autorem=re.compile(r'[0-9a-fA-F]{32} [ *].')):
        line = file.peekline(4096)
        while line:
            if line[0] not in ';#':
                return _autorem.match(line) is not None
            line = file.peeknextline(4096)

    auto_filename_match = 'md5'

    _foosum_rem = re.compile(r'([0-9a-fA-F]{32}) ([ *])([^\r\n]+)[\r\n]*$')

    @staticmethod
    def make_std_filename(filename):
        return filename + '.md5'

    def make_addfile(self, filename):
        crc = hexlify(getfilemd5(filename)[0])
        return (crc, -1), '%s *%s' % (crc, filename) + os.linesep


cftypes.register_cftype(MD5)


# ---------- bsdmd5 ----------

class BSDMD5(TextChksumType, MD5_MixIn):
    name = 'bsdmd5'
    description = 'BSD md5'
    descinfo = 'name,MD5'

    @staticmethod
    def auto_chksumfile_match(file, _autorem=re.compile(r'MD5 \(.+\) = [0-9a-fA-F]{32}' + '[\r\n]*$')):
        return _autorem.match(file.peekline(4096)) is not None

    auto_filename_match = '^md5$'

    _bsdmd5rem = re.compile(r'MD5 \((.+)\) = ([0-9a-fA-F]{32})[\r\n]*$')

    def do_test_chksumline(self, l):
        x = self._bsdmd5rem.match(l)
        if not x:
            return -1
        self.test_file(x.group(1), unhexlify(x.group(2)))

    @staticmethod
    def make_std_filename(filename):
        return filename + '.md5'

    def make_addfile(self, filename):
        crc = hexlify(getfilemd5(filename)[0])
        return (crc, -1), 'MD5 (%s) = %s' % (filename, crc) + os.linesep


cftypes.register_cftype(BSDMD5)


# ---------- par ----------

def ver2str(v):
    vers = []
    while v or len(vers) < 3:
        vers.insert(0, str(v & 0xFF))
        v >>= 8
    return '.'.join(vers)


class PAR(ChksumType, MD5_MixIn):
    name = 'par'
    description = 'Parchive v1 (test-only)'
    descinfo = 'name,size,MD5'

    @staticmethod
    def auto_chksumfile_match(file):
        return file.peek(8) == 'PAR\0\0\0\0\0'

    def do_test_chksumfile(self, file):
        def prog2str(v):
            return {0x01: 'Mirror', 0x02: 'PAR', 0x03: 'SmartPar', 0xFF: 'FSRaid'}.get(v, 'unknown(%x)' % v)

        par_header_fmt = '< 8s I I 16s 16s Q Q Q Q Q Q'
        par_entry_fmt = '< Q Q Q 16s 16s'
        par_entry_fmtsize = struct.calcsize(par_entry_fmt)

        d = file.read(struct.calcsize(par_header_fmt))
        magic, version, client, control_hash, set_hash, vol_number, num_files, file_list_ofs, file_list_size, data_ofs, data_size = struct.unpack(par_header_fmt, d)
        if config.docrcchecks:
            control_md5 = hash.md5_new()
            control_md5.update(d[0x20:])
            stats.bytesread += len(d)
        if version not in (0x00000900, 0x00010000):  # ver 0.9 and 1.0 are the same, as far as we care.  Future versions (if any) may very likey have incompatible changes, so don't accept them either.
            raise EnvironmentError(errno.EINVAL, "can't handle PAR version %s" % ver2str(version))

        view.ev_test_cf_begin('par v%s' % ver2str(version), file.name, 'created by %s v%s' % (prog2str(client >> 24), ver2str(client & 0xFFFFFF)))

        for i in range(0, num_files):
            d = file.read(par_entry_fmtsize)
            size, status, file_size, md5, md5_16k = struct.unpack(par_entry_fmt, d)
            if config.docrcchecks:
                control_md5.update(d)
            d = file.read(size - par_entry_fmtsize)
            if config.docrcchecks:
                control_md5.update(d)
                stats.bytesread += size
            try:
                filename = cffndecode(d, 'utf-16-le')
            except (UnicodeError, FilenameError), e:
                stats.cferror += 1
                view.ev_test_cf_filenameencodingerror(file.name, i, e)
                continue
            self.test_file(filename, md5, file_size)

        if config.docrcchecks:
            while 1:
                d = file.read(65536)
                if not d:
                    if control_md5.digest() != control_hash:
                        raise EnvironmentError(errno.EINVAL, 'corrupt par file - bad control hash')
                    break
                stats.bytesread += len(d)
                control_md5.update(d)

    # we don't support PAR in create mode, but add these methods so that we can get error messages that are probaby more user friendly.
    auto_filename_match = 'par$'

    @staticmethod
    def make_std_filename(filename):
        return filename + '.par'


cftypes.register_cftype(PAR)


class PAR2(ChksumType, MD5_MixIn):
    name = 'par2'
    description = 'Parchive v2 (test-only)'
    descinfo = 'name,size,MD5'

    @staticmethod
    def auto_chksumfile_match(file):
        return file.peek(8) == 'PAR2\0PKT'

    def do_test_chksumfile(self, file):
        pkt_header_fmt = '< 8s Q 16s 16s 16s'
        pkt_header_size = struct.calcsize(pkt_header_fmt)
        file_pkt_fmt = '< 16s 16s 16s Q'
        file_pkt_size = struct.calcsize(file_pkt_fmt)
        main_pkt_fmt = '< Q I'
        main_pkt_size = struct.calcsize(main_pkt_fmt)

        def get_creator(file):
            if not config.verbose > 0:
                return None  # avoid doing the work if we aren't going to use it anyway.
            while 1:
                d = file.read(pkt_header_size)
                if not d:
                    return None
                magic, pkt_len, pkt_md5, set_id, pkt_type = struct.unpack(pkt_header_fmt, d)
                if pkt_type == 'PAR 2.0\0Creator\0':
                    return strutil.chompnulls(file.read(pkt_len - pkt_header_size))
                else:
                    file.seek(pkt_len - pkt_header_size, 1)

        self.do_test_chksumfile_print_testingline(file, get_creator(file))
        file.seek(0)  # reset file position after looking for creator packet

        seen_file_ids = set()
        expected_file_ids = None

        while 1:
            d = file.read(pkt_header_size)
            if not d:
                break

            magic, pkt_len, pkt_md5, set_id, pkt_type = struct.unpack(pkt_header_fmt, d)

            if config.docrcchecks:
                control_md5 = hash.md5_new()
                control_md5.update(d[0x20:])
                stats.bytesread += len(d)
                d = file.read(pkt_len - pkt_header_size)
                control_md5.update(d)
                stats.bytesread += len(d)
                if control_md5.digest() != pkt_md5:
                    raise EnvironmentError(errno.EINVAL, 'corrupt par2 file - bad packet hash')

            if pkt_type == 'PAR 2.0\0FileDesc':
                if not config.docrcchecks:
                    d = file.read(pkt_len - pkt_header_size)
                file_id, file_md5, file_md5_16k, file_size = struct.unpack(file_pkt_fmt, d[:file_pkt_size])
                if file_id not in seen_file_ids:
                    seen_file_ids.add(file_id)
                    filename = strutil.chompnulls(d[file_pkt_size:])
                    try:
                        filename = cffndecode(filename)
                    except (UnicodeError, FilenameError), e:
                        stats.cferror += 1
                        view.ev_test_cf_filenameencodingerror(file.name, hexlify(file_id), e)
                        continue
                    self.test_file(filename, file_md5, file_size)
            elif pkt_type == 'PAR 2.0\0Main\0\0\0\0':
                if not config.docrcchecks:
                    d = file.read(pkt_len - pkt_header_size)
                if expected_file_ids is None:
                    expected_file_ids = []
                    slice_size, num_files = struct.unpack(main_pkt_fmt, d[:main_pkt_size])
                    num_nonrecovery = (len(d) - main_pkt_size) / 16 - num_files
                    for i in range(main_pkt_size, main_pkt_size + (num_files + num_nonrecovery) * 16, 16):
                        expected_file_ids.append(d[i:i + 16])
            else:
                if not config.docrcchecks:
                    file.seek(pkt_len - pkt_header_size, 1)

        if expected_file_ids is None:
            raise EnvironmentError(errno.EINVAL, 'corrupt or unsupported par2 file - no main packet found')
        for file_id in expected_file_ids:
            if file_id not in seen_file_ids:
                raise EnvironmentError(errno.EINVAL, 'corrupt or unsupported par2 file - expected file description packet not found')

    # we don't support PAR2 in create mode, but add these methods so that we can get error messages that are probaby more user friendly.
    auto_filename_match = 'par2$'

    @staticmethod
    def make_std_filename(filename):
        return filename + '.par2'


cftypes.register_cftype(PAR2)


# ---------- .torrent ----------

class Torrent(ChksumType):
    name = 'torrent'
    description = 'BitTorrent metainfo'
    descinfo = 'name,size,SHA1(piecewise)'

    @staticmethod
    def auto_chksumfile_match(file):
        return file.peek(1) == 'd' and file.peek(4096).find('8:announce') >= 0

    def do_test_chksumfile(self, file):
        try:
            metainfo = bencode.bdecode(file.read())
            btformats.check_message(metainfo)
        except ValueError, e:
            raise EnvironmentError(str(e) or 'invalid or corrupt torrent')

        encoding = metainfo.get('encoding')

        comments = []
        if 'creation date' in metainfo:
            try:
                comments.append('created ' + time.ctime(metainfo['creation date']))
            except TypeError:
                comments.append('created ' + repr(metainfo['creation date']))
        if 'comment' in metainfo:
            try:
                comments.append(cfdecode(metainfo['comment'], encoding))
            except UnicodeError:
                pass
        self.do_test_chksumfile_print_testingline(file, ', '.join(comments))

        def init_file(filenameparts, ftotpos, filesize):
            done = 0
            try:
                filenameparts = map(lambda p: cffndecode(p, encoding), filenameparts)
            except LookupError, e:  # lookup error is raised when specified encoding isn't found.
                raise EnvironmentError(str(e))
            except (UnicodeError, FilenameError), e:
                stats.cferror += 1
                view.ev_test_cf_filenameencodingerror(file.name, repr(filenameparts), e)
                done = 1
                l_filename = filename = None
            if not done:
                filename = osutil.path_join(*filenameparts)
                if not config.docrcchecks:  # if we aren't testing checksums, just use the standard test_file function, so that -s and such will work.
                    self.test_file(filename, None, filesize)
                    return
                filename = self.mangle_filename(filename)
                done = not filenamefilter.should_test(filename)  # if we don't want to test this file, just pretending its done already has the desired effect.
                if not done:
                    stats.num += 1
                try:
                    l_filename = self.find_local_filename(filename)
                    if not os.path.exists(l_filename):
                        raise EnvironmentError(errno.ENOENT, 'missing')
                    if not os.path.isfile(l_filename):
                        raise EnvironmentError(errno.ENOENT, 'not a file')
                    fs = os.path.getsize(l_filename)
                    if fs != filesize:
                        if not done:
                            self.do_f_badsize(l_filename, filesize, fs)
                            done = 1
                except (EnvironmentError, UnicodeError), e:  # UnicodeError can occur if python can't map the filename to the filesystem's encoding
                    if not done:
                        self.do_f_enverror(filename, e)
                        done = 1
                    l_filename = None
            return Data(totpos=ftotpos, size=filesize, filename=filename, l_filename=l_filename, done=done)

        info = metainfo['info']
        piecelen = info['piece length']
        hashes = re.compile('.' * 20, re.DOTALL).findall(info['pieces'])
        if 'length' in info:
            total_len = info['length']
            files = [init_file([info['name']], 0, total_len)]
        else:
            dirpart = [info['name']]
            if config.strippaths == 0:
                dirname = info['name']
                try:
                    dirname = cffndecode(dirname, encoding)
                except (LookupError, UnicodeError, FilenameError), e:  # lookup error is raised when specified encoding isn't found.
                    stats.cferror += 1
                    raise EnvironmentError(e)

                dirname = osutil.strippath(dirname, 0)
                if config.ignorecase:
                    try:
                        cache.nocase_finddir(dirname)
                    except EnvironmentError:
                        dirpart = []
                else:
                    try:
                        if not os.path.isdir(dirname):
                            dirpart = []
                    except UnicodeError:
                        dirpart = []
            # if not dirpart:
            #     pinfo('enabling .torrent path strip hack')
            files = []
            total_len = 0
            for finfo in info['files']:
                flength = finfo['length']
                files.append(init_file(dirpart + finfo['path'], total_len, flength))
                total_len += flength

        if not config.docrcchecks:
            return

        curfh = Data(fh=None, f=None)

        def readfpiece(f, pos, size):
            if f.l_filename is None:
                return None
            try:
                if not curfh.fh or curfh.f is not f:
                    if curfh.fh:
                        curfh.fh.close()
                    curfh.fh = open(f.l_filename, 'rb')
                    curfh.f = f
                curfh.fh.seek(pos)
                d = curfh.fh.read(size)
            except EnvironmentError, e:
                if not f.done:
                    if view.progress:
                        view.progress.cleanup()
                    self.do_f_enverror(f.l_filename, e)
                    f.done = 1
                return None
            stats.bytesread += len(d)
            if len(d) < size:
                return None
            return d

        curf = 0
        curpos = 0
        for piece in range(0, len(hashes)):
            if piece < len(hashes) - 1:
                curend = curpos + piecelen
            else:
                curend = total_len
            piecefiles = []
            wanttest = 0
            while curpos < curend:
                while curpos >= files[curf].totpos + files[curf].size:
                    curf += 1
                f = files[curf]
                fcurpos = curpos - f.totpos
                assert fcurpos >= 0
                fpiecelen = min(curend - curpos, f.size - fcurpos)
                piecefiles.append((f, fcurpos, fpiecelen))
                curpos += fpiecelen
                if not f.done:
                    wanttest = 1
            if wanttest:
                sh = hash.sha_new()
                for f, fcurpos, fpiecelen in piecefiles:
                    if view.progress and f.l_filename and f.l_filename != view.progress.filename:
                        view.progress.cleanup()
                        view.progress.init(f.l_filename, f.size, fcurpos)
                    d = readfpiece(f, fcurpos, fpiecelen)
                    if d is None:
                        break
                    sh.update(d)
                    if view.progress and f.l_filename:
                        view.progress.update(fcurpos + fpiecelen)
                if d is None:
                    if curfh.fh:
                        # close the file in case do_f_badcrc wants to try to rename it
                        curfh.fh.close()
                        curfh.fh = None
                    for f, fcurpos, fpiecelen in piecefiles:
                        if not f.done:
                            if view.progress:
                                view.progress.cleanup()
                            self.do_f_badcrc(f.l_filename, 'piece %i missing data' % piece)
                            f.done = 1
                elif sh.digest() != hashes[piece]:
                    if curfh.fh:
                        # close the file in case do_f_badcrc wants to try to rename it
                        curfh.fh.close()
                        curfh.fh = None
                    for f, fcurpos, fpiecelen in piecefiles:
                        if not f.done:
                            if view.progress:
                                view.progress.cleanup()
                            self.do_f_badcrc(f.l_filename, 'piece %i (at %i..%i) crc does not match (%s!=%s)' % (piece, fcurpos, fcurpos + fpiecelen, hexlify(hashes[piece]), sh.hexdigest()))
                            f.done = 1
                else:
                    for f, fcurpos, fpiecelen in piecefiles:
                        if not f.done:
                            if fcurpos + fpiecelen == f.size:
                                if view.progress:
                                    view.progress.cleanup()
                                self.do_f_ok(f.l_filename, f.size, 'all pieces ok')
                                f.done = 1

        if view.progress:
            view.progress.cleanup()

        if curfh.fh:
            curfh.fh.close()
        for f in files:
            if not f.done:
                self.do_f_ok(f.l_filename, f.size, 'all pieces ok')

    auto_filename_match = 'torrent$'

    @staticmethod
    def make_std_filename(filename):
        return filename + '.torrent'

    def make_chksumfile_create(self, filename):
        if config.announceurl is None:
            raise EnvironmentError('announce url required')
        file = fileutil.open_write_raw(filename, config)
        self.sh = hash.sha_new()
        self.files = []
        self.pieces = []
        self.piece_done = 0
        self.piece_length = 2 ** config.piece_size_pow2
        return file

    def make_addfile(self, filename):
        firstpiece = len(self.pieces)
        with open(filename, 'rb') as f:
            if view.progress:
                view.progress.init(filename)
            fs = 0
            while 1:
                piece_left = self.piece_length - self.piece_done
                d = f.read(piece_left)
                if not d:
                    break
                self.sh.update(d)
                s = len(d)
                stats.bytesread += s
                fs += s
                if view.progress:
                    view.progress.update(fs)
                self.piece_done += s
                if self.piece_done == self.piece_length:
                    self.pieces.append(self.sh.digest())
                    self.sh = hash.sha_new()
                    self.piece_done = 0
        if view.progress:
            view.progress.cleanup()

        def cfencode_utf8pref(s):
            return cfencode(s, 'UTF-8')

        self.files.append({'length': fs, 'path': map(cfencode_utf8pref, osutil.path_split(filename))})
        return ('pieces %i..%i' % (firstpiece, len(self.pieces)), fs), ''

    def make_chksumfile_finish(self, file):
        if self.piece_done > 0:
            self.pieces.append(self.sh.digest())

        info = {'pieces': ''.join(self.pieces), 'piece length': self.piece_length}
        if config.private_torrent:
            info['private'] = 1
        if len(self.files) == 1 and len(self.files[0]['path']) == 1:
            info['length'] = self.files[0]['length']
            info['name'] = self.files[0]['path'][0]
        else:
            commonroot = self.files[0]['path'][0]
            for fileinfo in self.files[1:]:
                if commonroot != fileinfo['path'][0]:
                    commonroot = None
                    break
            if commonroot:
                for fileinfo in self.files:
                    del fileinfo['path'][0]
            else:
                commonroot = cfencode(os.path.split(osutil.getcwdu())[1], 'UTF-8')
            info['files'] = self.files
            info['name'] = commonroot

        btformats.check_info(info)
        data = {'info': info, 'announce': cfencode(config.announceurl.strip(), 'UTF-8'), 'creation date': long(time.time())}
        if config.encoding != 'raw':
            data['encoding'] = str(config.getencoding('UTF-8'))
        # if comment:
        #     data['comment'] = comment
        file.write(bencode.bencode(data))
        file.close()


cftypes.register_cftype(Torrent)


# ---------- sfv ----------

class CRC_MixIn:
    def do_test_file(self, filename, filecrc):
        c = getfilecrc(filename)[0]
        if c != filecrc:
            return c


class SFV_Base(TextChksumType):
    description = 'Simple File Verify'

    def do_test_chksumfile_print_testingline(self, file):
        # override the default testing line to show first SFV comment line, if any
        TextChksumType.do_test_chksumfile_print_testingline(self, file, parse_commentline(file.peekline(512), ';'))

    def do_test_chksumline(self, l):
        if l[0] == ';':
            return
        x = self._sfvrem.match(l)
        if not x:
            return -1
        self.test_file(x.group(1), unhexlify(x.group(2)))

    def make_chksumfile_create(self, filename):
        file = TextChksumType.make_chksumfile_create(self, filename)
        file.write('; Generated by cfv v%s on %s' % (__version__, time.strftime('%Y-%m-%d at %H:%M.%S', time.gmtime(time.time()))) + os.linesep + ';' + os.linesep)
        return file


class SFV(SFV_Base, CRC_MixIn):
    name = 'sfv'
    descinfo = 'name,CRC32'

    @staticmethod
    def auto_chksumfile_match(file, _autorem=re.compile('.+ [0-9a-fA-F]{8}[\n\r]*$')):
        line = file.peekline(4096)
        while line:
            if line[0] != ';':
                return _autorem.match(line) is not None
            line = file.peeknextline(4096)

    auto_filename_match = 'sfv$'

    _sfvrem = re.compile(r'(.+) ([0-9a-fA-F]{8})[\r\n]*$')

    @staticmethod
    def make_std_filename(filename):
        return filename + '.sfv'

    def make_addfile(self, filename):
        crc = hexlify(getfilecrc(filename)[0])
        return (crc, -1), '%s %s' % (filename, crc) + os.linesep


cftypes.register_cftype(SFV)


class SFVMD5(SFV_Base, MD5_MixIn):
    name = 'sfvmd5'
    descinfo = 'name,MD5'

    @staticmethod
    def auto_chksumfile_match(file, _autorem=re.compile('.+ [0-9a-fA-F]{32}[\n\r]*$')):
        line = file.peekline(4096)
        while line:
            if line[0] != ';':
                return _autorem.match(line) is not None
            line = file.peeknextline(4096)

    auto_chksumfile_order = -1  # do -1 prio since we can mistakenly match a bsdmd5 file

    # auto_filename_match = 'md5$' #hm. People are probably used to .md5 making a md5sum format file, so we can't just do this.

    _sfvrem = re.compile(r'(.+) ([0-9a-fA-F]{32})[\r\n]*$')

    @staticmethod
    def make_std_filename(filename):
        return filename + '.md5'

    def make_addfile(self, filename):
        crc = hexlify(getfilemd5(filename)[0])
        return (crc, -1), '%s %s' % (filename, crc) + os.linesep


cftypes.register_cftype(SFVMD5)


# ---------- csv ----------

_csvstrautore = r'(?:".*"|[^,]*),'
_csvstrre = r'(?:"(.*)"|([^,]*)),'
_csvfnautore = _csvstrautore.replace('*', '+')
_csvfnre = _csvstrre.replace('*', '+')


def csvquote(s):
    if ',' in s or '"' in s:
        return '"%s"' % (s.replace('"', '""'))
    return s


def csvunquote(g1, g2):
    if g1 is not None:
        return g1.replace('""', '"')
    return g2


class CSV(TextChksumType, CRC_MixIn):
    name = 'csv'
    description = 'Comma Separated Values'
    descinfo = 'name,size,CRC32'

    @staticmethod
    def auto_chksumfile_match(file, _autorem=re.compile(_csvfnautore + '[0-9]+,[0-9a-fA-F]{8},[\n\r]*$')):
        return _autorem.match(file.peekline(4096)) is not None

    auto_filename_match = 'csv$'

    _csvrem = re.compile(_csvfnre + r'([0-9]+),([0-9a-fA-F]{8}),')

    def do_test_chksumline(self, l):
        x = self._csvrem.match(l)
        if not x:
            return -1
        self.test_file(csvunquote(x.group(1), x.group(2)), unhexlify(x.group(4)), int(x.group(3)))

    @staticmethod
    def make_std_filename(filename):
        return filename + '.csv'

    def make_addfile(self, filename):
        c, s = getfilecrc(filename)
        c = hexlify(c)
        return (c, s), '%s,%i,%s,' % (csvquote(filename), s, c) + os.linesep


cftypes.register_cftype(CSV)


# ---------- csv with 4 fields ----------

class CSV4(TextChksumType, CRC_MixIn):
    name = 'csv4'
    description = 'Comma Separated Values'
    descinfo = 'name,size,CRC32,path'

    @staticmethod
    def auto_chksumfile_match(file, _autorem=re.compile(r'%s[0-9]+,[0-9a-fA-F]{8},%s[\n\r]*$' % (_csvfnautore, _csvstrautore))):
        return _autorem.match(file.peekline(4096)) is not None

    _csv4rem = re.compile(r'%s([0-9]+),([0-9a-fA-F]{8}),%s' % (_csvfnre, _csvstrre))

    def do_test_chksumline(self, l):
        x = self._csv4rem.match(l)
        if not x:
            return -1
        name = csvunquote(x.group(1), x.group(2))
        path = csvunquote(x.group(5), x.group(6))
        self.test_file(osutil.path_join(self.fixpath(path), name), unhexlify(x.group(4)), int(x.group(3)))  # we need to fixpath before path.join since osutil.path_join looks for path.sep

    @staticmethod
    def make_std_filename(filename):
        return filename + '.csv'

    def make_addfile(self, filename):
        c, s = getfilecrc(filename)
        c = hexlify(c)
        p = os.path.split(filename)
        return (c, s), '%s,%i,%s,%s,' % (csvquote(p[1]), s, c, csvquote(p[0])) + os.linesep


cftypes.register_cftype(CSV4)


# ---------- csv with only 2 fields ----------

class CSV2(TextChksumType):
    name = 'csv2'
    description = 'Comma Separated Values'
    descinfo = 'name,size'

    @staticmethod
    def auto_chksumfile_match(file, _autorem=re.compile(_csvfnautore + '[0-9]+,[\n\r]*$')):
        return _autorem.match(file.peekline(4096)) is not None

    _csv2rem = re.compile(_csvfnre + r'([0-9]+),')

    def do_test_chksumline(self, l):
        x = self._csv2rem.match(l)
        if not x:
            return -1
        self.test_file(csvunquote(x.group(1), x.group(2)), None, int(x.group(3)))

    @staticmethod
    def make_std_filename(filename):
        return filename + '.csv'

    def make_addfile(self, filename):
        if filename == '':
            s = getfilecrc(filename)[1]  # no way to get size of stdin other than to read it
        else:
            s = os.path.getsize(filename)
        return (None, s), '%s,%i,' % (csvquote(filename), s) + os.linesep


cftypes.register_cftype(CSV2)


# ---------- jpegsheriff .crc ----------

def getimagedimensions(filename):
    if filename == '':
        return '0', '0'
    try:
        from PIL import Image
        im1 = Image.open(filename)
        return map(str, im1.size)
    except (ImportError, IOError):
        return '0', '0'


def commaize(n):
    n = str(n)
    s = n[-3:]
    n = n[:-3]
    while n:
        s = n[-3:] + ',' + s
        n = n[:-3]
    return s


class JPEGSheriff_CRC(TextChksumType, CRC_MixIn):
    name = 'crc'
    description = 'JPEGSheriff'
    descinfo = 'name,size,dimensions,CRC32'

    @staticmethod
    def auto_chksumfile_match(file, _autorem=re.compile(r'^Filename\s+(Filesize\s+)?.*?CRC-?32.*^-+(\s+-+){1,4}\s*$', re.DOTALL | re.IGNORECASE | re.MULTILINE)):
        return _autorem.search(file.peekdecoded(1024)) is not None

    auto_filename_match = 'crc$'

    def do_test_chksumfile_print_testingline(self, file):
        x = re.search(r'^Filename\s+(Filesize\s+)?(.+?)??CRC-?32.*^-+(\s+-+){1,4}\s*$', file.peekdecoded(1024), re.DOTALL | re.IGNORECASE | re.MULTILINE)
        self.has_size = x.group(1) is not None
        self.has_dimensions = x.group(2) is not None

        crcre = r'(?P<name>.*\S)\s+'
        if self.has_size:
            crcre += r'(?P<size>[0-9.,]+)\s+'
        if self.has_dimensions:
            crcre += r'\S+\s*x\s*\S+\s+'
        crcre += r'(?P<crc>[0-9a-fA-F]{8})\b'
        self._crcrem = re.compile(crcre, re.I)

        self.in_comments = 1

        # override the default testing line to show first comment line, if any
        comment = file.peekline().strip()
        view.ev_test_cf_begin('crc', file.name, comment)

    _commentboundary = re.compile(r'^-+(\s+-+){1,4}\s*$')
    _nstrip = re.compile(r'[.,]')

    def do_test_chksumline(self, l):
        if self._commentboundary.match(l):
            self.in_comments = not self.in_comments
            return
        x = self._crcrem.match(l)
        if not x:
            if self.in_comments:
                return
            return -1
        if self.has_size:
            size = int(self._nstrip.sub('', x.group('size')))
        else:
            size = -1
        self.test_file(x.group('name'), unhexlify(x.group('crc')), size)

    @staticmethod
    def make_std_filename(filename):
        return filename + '.crc'

    def make_chksumfile_create(self, filename):
        file = TextChksumType.make_chksumfile_create(self, filename)
        file.write('Generated by: cfv (v%s)' % __version__ + os.linesep)
        file.write('Generated at: %s' % (time.strftime('%a, %d %b %Y %H:%M:%S', time.gmtime(time.time()))) + os.linesep)
        file.write('Find  it  at: ' + __homepage__ + os.linesep + os.linesep)
        try:
            from PIL import Image  # noqa: F401
            self.use_dimensions = 1  # TODO: should this be made optional somehow?
        except ImportError:
            self.use_dimensions = 0
        self._flist = []
        self._fieldlens = [0] * 6
        self._ftotal = 0
        return file

    def make_chksumfile_finish(self, file):
        flens = self._fieldlens

        def writedata(data):
            file.write(data[0].ljust(flens[0]) + '  ' + data[1].rjust(flens[1]))
            if self.use_dimensions:
                file.write('  ' + data[2].rjust(flens[2]) + ' x ' + data[3].rjust(flens[3]))
            file.write('  ' + data[4].rjust(flens[4]) + '  ' + data[5] + os.linesep)

        header = ('Filename', ' Filesize ', ' W', 'H '.ljust(flens[3]), ' CRC-32 ', 'Description')
        for i in range(0, len(header) - 1):
            self._fieldlens[i] = max(self._fieldlens[i], len(header[i]))

        boundary = '-' * flens[0] + '  ' + '-' * flens[1] + '  '
        if self.use_dimensions:
            boundary += '-' * (flens[2] + flens[3] + 3) + '  '
        boundary += '-' * flens[4] + '  ' + '-' * flens[5] + os.linesep

        writedata(header)
        file.write(boundary)
        for fdata in self._flist:
            try:
                writedata(fdata)
            except UnicodeError, e:
                stats.ferror += 1
                stats.ok -= 1  # ugly hack, since this is incremented after make_addfile returns, since we don't know then that it will cause an error
                view.ev_make_filenameencodingerror(fdata[0], e)
        file.write(boundary)
        file.write(os.linesep + 'Count of files: %i' % len(self._flist) + os.linesep)
        file.write('Total of sizes: %s' % commaize(self._ftotal) + os.linesep)
        TextChksumType.make_chksumfile_finish(self, file)

    def make_addfile(self, filename):
        crc, size = getfilecrc(filename)
        crc = hexlify(crc)
        if self.use_dimensions:
            w, h = getimagedimensions(filename)
        else:
            w = h = ''
        fdata = (filename, commaize(size), w, h, crc, '')
        for i in range(0, len(fdata)):
            self._fieldlens[i] = max(self._fieldlens[i], len(fdata[i]))
        self._flist.append(fdata)
        self._ftotal += size

        # we cheat and do all writing in make_chksumfile_finish since it needs to be properly formatted, and we can't do that until we have seen the max lengths for all fields
        return (crc, size), ''


cftypes.register_cftype(JPEGSheriff_CRC)


# ---------- generic ----------

_visited_dirs = set()


def visit_dir(name, st=None, noisy=1):
    if not config.dereference and os.path.islink(name):
        return 0
    if st is None:
        try:
            st = os.stat(name)
        except os.error:
            return 0
    if S_ISDIR(st.st_mode):
        # the inode check is kinda a hack, but systems that don't have inode numbers probably don't have symlinks either.
        if config.dereference and st.st_ino:
            dir_key = (st.st_dev, st.st_ino)
            if dir_key in _visited_dirs:
                if noisy:
                    view.ev_generic_warning('skipping already visited dir %s %s' % (view.perhaps_showpath(name), dir_key))
                return 0
            _visited_dirs.add(dir_key)
        return 1
    return 0


def test(filename, typename, restrict_typename='auto'):
    if typename != 'auto':
        cf = cftypes.get_handler(typename)()
        cf.test_chksumfile(None, filename)
        return

    try:
        file = fileutil.open_read(filename, config)
        cftype = cftypes.auto_chksumfile_match(file)
        if restrict_typename != 'auto' and cftypes.get_handler(restrict_typename) != cftype:
            return
        if cftype:
            cf = cftype()
            cf.test_chksumfile(file, filename)
            return
    except EnvironmentError, a:
        stats.cferror += 1
        view.ev_cf_enverror(filename, a)
        return -1
    view.ev_test_cf_unrecognized(filename, file._decode_errs)
    stats.cferror += 1


def make(cftype, ifilename, testfiles):
    file = None
    if ifilename:
        filename = ifilename
    else:
        filename = cftype.make_std_filename(os.path.basename(curdir))
        if config.gzip == 1 and filename[-3:] != '.gz':  # if user does -zz, perhaps they want to force the filename to be kept?
            filename += '.gz'
    if not hasattr(cftype, 'make_addfile'):
        view.ev_make_cf_typenotsupported(filename, cftype)
        stats.cferror += 1
        return
    if os.path.exists(filename):
        view.ev_make_cf_alreadyexists(filename)
        stats.cferror += 1
        file = IOError  # just need some special value to indicate a cferror so that recursive mode still continues to work, IOError seems like a good choice ;)
    if not testfiles:
        tfauto = 1
        testfiles = osutil.listdir(osutil.curdiru)
        if config.dirsort:
            strutil.safesort(testfiles)
    else:
        tfauto = 0
    testdirs = []

    cf_stats = stats.make_sub_stats()

    i = 0
    while i < len(testfiles):
        f = testfiles[i]
        i += 1
        if not tfauto and f == '-':
            f = u''
        elif not os.path.isfile(f):
            if config.recursive and visit_dir(f):
                if config.recursive == 1:
                    testdirs.append(f)
                elif config.recursive == 2:
                    try:
                        rfiles = osutil.listdir(f)
                        if config.dirsort:
                            strutil.safesort(rfiles)
                        testfiles[:i] = map(lambda x, p=f: osutil.path_join(p, x), rfiles)
                        i = 0
                    except EnvironmentError, a:
                        view.ev_d_enverror(f, a)
                        stats.ferror += 1
                continue
            if tfauto:  # if user isn't specifying files, don't even try to add dirs and stuff, and don't print errors about it.
                continue
        stats.num += 1
        if file is IOError:
            continue
        if config.encoding != 'raw':
            if isinstance(f, str):
                stats.ferror += 1
                view.ev_make_filenamedecodingerror(f)
                continue
        else:
            if isinstance(f, unicode):
                try:
                    f = f.encode(osutil.fsencoding)
                except UnicodeError, e:
                    stats.ferror += 1
                    view.ev_make_filenameencodingerror(f, e)
                    continue
        if not cftype.filename_ok(f):
            stats.ferror += 1
            view.ev_make_filenameinvalid(f)
            continue
        if file is None:
            try:
                cf = cftype()
                file = cf.make_chksumfile_create(filename)
            except EnvironmentError, a:
                stats.cferror += 1
                view.ev_cf_enverror(filename, a)
                file = IOError
                continue
        try:
            (filecrc, filesize), dat = cf.make_addfile(f)
        except EnvironmentError, a:
            if a[0] == errno.ENOENT:
                stats.notfound += 1
            else:
                stats.ferror += 1
            view.ev_f_enverror(f, a)
            continue
        try:
            cf.make_writefile(dat, file)
        except EnvironmentError, a:
            stats.cferror += 1
            view.ev_cf_enverror(filename, a)
            file = IOError
            continue
        except UnicodeError, e:
            stats.ferror += 1
            view.ev_make_filenameencodingerror(f, e)
            continue
        view.ev_f_ok(f, filesize, filecrc, 'OK')
        stats.ok += 1
    if file and file is not IOError:
        try:
            cf.make_chksumfile_finish(file)
        except EnvironmentError, a:
            stats.cferror += 1
            view.ev_cf_enverror(filename, a)
        else:
            cf_stats.sub_stats_end(stats)
            view.ev_make_cf_done(filename, cf_stats)

    for f in testdirs:
        try:
            chdir(f)
        except EnvironmentError, a:
            view.ev_d_enverror(f, a)
            stats.ferror += 1
        else:
            make(cftype, ifilename, None)
            cdup()


def show_unverified_file(filename):
    unverified_file(filename)
    view.ev_unverified_file(filename)


def unverified_file(filename):
    view.ev_unverified_file_plistf(filename)
    stats.unverified += 1


def show_unverified_dir(path, unvchild=0):
    pathcache = cache.getpathcache(path)
    pathfiles = osutil.listdir(path or osutil.curdiru)
    vsub = 0
    unvsave = stats.unverified
    unv = 0
    unv_sub_dirs = []
    for fn in pathfiles:
        sfn = fn
        if config.encoding == 'raw' and isinstance(fn, unicode):
            try:
                sfn = fn.encode(osutil.fsencoding)
            except UnicodeError:
                pass
        filename = osutil.path_join(path, fn)
        try:
            st = os.stat(filename)
            if S_ISDIR(st.st_mode) and visit_dir(filename, st, noisy=0):
                dunvsave = stats.unverified
                dv = show_unverified_dir(filename, not pathcache)
                vsub += dv
                if stats.unverified - dunvsave and not dv:  # if this directory (and its subdirs) had unverified files and no verified files
                    unv_sub_dirs.append(filename)
            elif pathcache:
                if not (pathcache.get(fn, {}).get('_verified') or pathcache.get(sfn, {}).get('_verified')):
                    if S_ISREG(st.st_mode):
                        show_unverified_file(filename)
            else:
                if S_ISREG(st.st_mode):
                    unverified_file(filename)
                    unv += 1
        except OSError:
            pass
    if not pathcache and pathfiles:
        if vsub:  # if sub directories do have verified files
            if unv:  # and this directory does have unverified files
                view.ev_unverified_dir(path)
            for unvpath in unv_sub_dirs:  # print sub dirs that had unverified files and no verified files
                view.ev_unverified_dirrecursive(unvpath)
        elif not unvchild:  # if this is the root of a tree with no verified files
            if stats.unverified - unvsave:  # and there were unverified files in the tree
                view.ev_unverified_dirrecursive(path)
    return vsub + (not not pathcache)


def show_unverified_dir_verbose(path):
    pathcache = cache.getpathcache(path)
    pathfiles = osutil.listdir(path or osutil.curdiru)
    for fn in pathfiles:
        sfn = fn
        if config.encoding == 'raw' and isinstance(fn, unicode):
            try:
                sfn = fn.encode(osutil.fsencoding)
            except UnicodeError:
                pass
        filename = osutil.path_join(path, fn)
        try:
            st = os.stat(filename)
            if S_ISDIR(st.st_mode) and visit_dir(filename, st, noisy=0):
                show_unverified_dir_verbose(filename)
            elif not (pathcache.get(fn, {}).get('_verified') or pathcache.get(sfn, {}).get('_verified')):
                if S_ISREG(st.st_mode):
                    show_unverified_file(filename)
        except OSError:
            pass


def show_unverified_files(filelist):
    if not config.showunverified:
        return
    if filelist:
        for filename in filelist:
            if config.ignorecase:
                try:
                    filename = cache.nocase_findfile(filename)
                except IOError:
                    continue
            else:
                if not os.path.isfile(filename):
                    continue
            if not cache.is_verified(filename):
                show_unverified_file(filename)
    else:
        _visited_dirs.clear()
        if config.showunverified == 2:
            show_unverified_dir_verbose(u'')
        else:
            show_unverified_dir(u'')


# md5sum/sha1sum files have no standard extension, so just search for
# files with md5/sha1 in the name anywhere, and let the test func see
# if it really is one.
atrem = re.compile(r'md5|sha1|sha224|sha256|sha384|sha512|\.(csv|sfv|par|p[0-9][0-9]|par2|torrent|crc)(\.gz)?$', re.IGNORECASE)


def autotest(typename):
    files = osutil.listdir(osutil.curdiru)
    if config.dirsort:
        strutil.safesort(files)
    for a in files:
        if config.recursive and visit_dir(a):
            try:
                chdir(a)
            except EnvironmentError, e:
                view.ev_d_enverror(a, e)
                stats.ferror += 1
            else:
                autotest(typename)
                cdup()
        if atrem.search(a):
            test(a, 'auto', typename)


def printusage(err=0):
    phelp = err and view.perror or view.pinfo
    phelp('Usage: cfv [opts] [-p dir] [-T|-C] [-t type] [-f file] [files...]')
    phelp('  -r       recursive mode 1 (make seperate chksum files for each dir)')
    phelp('  -rr      recursive mode 2 (make a single file with deep listing in it)')
    phelp('  -R       not recursive (default)')
    if _hassymlinks:
        phelp('  -l       follow symlinks (default)')
        phelp('  -L       don\'t follow symlinks')
    phelp('  -T       test mode (default)')
    phelp('  -C       create mode')
    phelp('  -t <t>   set type to <t> (%s, or auto(default))' % ', '.join(sorted(cftypes.get_handler_names())))
    phelp('  -f <f>   use <f> as list file')
    phelp('  -m       check only for missing files (don\'t compare checksums)')
    phelp('  -M       check checksums (default)')
    phelp('  -n       rename bad files')
    phelp('  -N       don\'t rename bad files (default)')
    phelp('  -s       search for correct file')
    phelp('  -S       don\'t search for correct file (default)')
    phelp('  -p <d>   change to directory <d> before doing anything')
    phelp('  -i       ignore case')
    phelp('  -I       don\'t ignore case (default)')
    phelp('  -u       show unverified files')
    phelp('  -uu      show each unverified file individually, no special directory handling')
    phelp('  -U       don\'t show unverified files (default)')
    phelp('  -v       verbose')
    phelp('  -V       not verbose (default)')
    phelp('  -VV      don\'t print status line at end either')
    phelp('  -q       quiet mode.  check exit code for success.')
    phelp('  -Q       mostly quiet mode.  only prints status lines.')
    phelp('  -zz      force making gzipped files, even if not ending in .gz')
    phelp('  -z       make gzipped files in auto create mode')
    phelp('  -Z       don\'t create gzipped files automatically. (default)')
    phelp('  -ZZ      never use gzip, even if file ends in .gz')
    phelp(' --list=<l> raw list files of type <l> (%s)' % ', '.join(ui.LISTARGS))
    phelp(' --list0=<l> same as list, but seperate files with nulls (useful for xargs -0)')
    phelp(' --encoding=<e>  encoding of checksum files (raw, auto(default), or...)')
    phelp(' --unquote=VAL  handle checksum files with quoted filenames (yes or no(default))')
    phelp(' --fixpaths=<s>  replace any chars in <s> with %s' % os.sep)
    phelp(' --strippaths=VAL  strip leading components from file names.')
    phelp(' --showpaths=<p> show full paths (none/auto/yes-absolute/relative)')
    phelp(' --renameformat=<f> format string to use with -n option')
    phelp(' --progress=VAL  show progress meter (yes, no, or auto(default))')
    phelp(' --help/-h show help')
    phelp(' --version show cfv and module versions')
    phelp('torrent creation options:')
    phelp(' --announceurl=URL    tracker announce url')
    phelp(' --piece_size_pow2=N  power of two to set the piece size to (default 18)')
    phelp(' --private_torrent    set private flag in torrent')
    sys.exit(err)


def printhelp():
    view.pinfo('cfv v%s - Copyright (C) 2000-2013 Matthew Mueller - Copyright (C) 2018-2019 David Gnedt - GPL license' % __version__)
    printusage()


def printcftypehelp(err):
    phelp = err and view.perror or view.pinfo
    phelp('Valid types:')

    def printtypeinfo(typename, info, desc):
        phelp(' %-8s %-26s %s' % (typename, desc, info))

    printtypeinfo('TYPE', 'FILE INFO STORED', 'DESCRIPTION')
    printtypeinfo('auto', '', 'autodetect type (default)')
    for typename in sorted(cftypes.get_handler_names()):
        printtypeinfo(typename, cftypes.get_handler(typename).descinfo, cftypes.get_handler(typename).description)
    sys.exit(err)


stats = Stats()
config = Config()
cache = caching.FileInfoCache()
view = ui.View(config)
filenamefilter = FileNameFilter()


def decode_arg(a):
    if isinstance(a, unicode):
        return a
    try:
        return unicode(a, osutil.preferredencoding)
    except UnicodeError:
        return a


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    manual = []
    mode = 0
    typename = 'auto'

    try:
        optlist, args = getopt.getopt(argv, 'rRlLTCt:f:mMnNsSp:uUiIvVzZqQh?',
                                      ['list=', 'list0=', 'fixpaths=', 'strippaths=', 'showpaths=', 'renameformat=', 'progress=', 'unquote=', 'help', 'version',
                                       'encoding=',
                                       'announceurl=', 'piece_size_pow2=', 'private_torrent', 'noprivate_torrent',  # torrent options
                                       ])
    except getopt.error, a:
        view.perror('cfv: %s' % a)
        printusage(1)
    args = map(decode_arg, args)

    try:
        if config.cmdlineglob == 'y' or (config.cmdlineglob == 'a' and os.name in ('os2', 'nt', 'dos')):
            from glob import glob
            globbed = []
            for arg in args:
                if '*' in arg or '?' in arg or '[' in arg:
                    g = glob(arg)
                    if not g:
                        raise CFVValueError('no matches for %s' % arg)
                    globbed.extend(g)
                else:
                    globbed.append(arg)
            args = globbed

        if config.cmdlinesort:
            strutil.safesort(args)

        prevopt = ''
        for o, a in optlist:
            a = decode_arg(a)
            if o == '-T':
                mode = 0
            elif o == '-C':
                mode = 1
            elif o == '-t':
                if a == 'help':
                    printcftypehelp(err=0)
                if a != 'auto' and not cftypes.has_handler(a):
                    view.perror('cfv: type %s not recognized' % a)
                    printcftypehelp(err=1)
                typename = a
            elif o == '-f':
                manual.append(a)  # filename selected manually, don't try to autodetect
            elif o == '-U':
                config.showunverified = 0
            elif o == '-u':
                if prevopt == '-u':
                    config.showunverified = 2
                else:
                    config.showunverified = 1
            elif o == '-I':
                config.ignorecase = 0
            elif o == '-i':
                config.ignorecase = 1
            elif o == '-n':
                config.rename = 1
            elif o == '-N':
                config.rename = 0
            elif o == '-s':
                config.search = 1
            elif o == '-S':
                config.search = 0
            elif o == '--renameformat':
                config.setx('renameformat', a)
            elif o == '-m':
                config.docrcchecks = 0
            elif o == '-M':
                config.docrcchecks = 1
            elif o == '-p':
                chdir(a)
            elif o == '-r':
                if prevopt == '-r':
                    config.recursive = 2
                else:
                    config.recursive = 1
            elif o == '-R':
                config.recursive = 0
            elif o == '-l':
                config.dereference = 1
            elif o == '-L':
                config.dereference = 0
            elif o == '-v':
                config.setx('verbose', 'v')
            elif o == '-V':
                if prevopt == '-V':
                    config.setx('verbose', 'VV')
                else:
                    config.setx('verbose', 'V')
            elif o == '-q':
                config.setx('verbose', 'q')
            elif o == '-Q':
                config.setx('verbose', 'Q')
            elif o == '--progress':
                config.setx('progress', a)
            elif o == '-z':
                if prevopt == '-z':
                    config.gzip = 2
                else:
                    config.gzip = 1
            elif o == '-Z':
                if prevopt == '-Z':
                    config.gzip = -1
                else:
                    config.gzip = 0
            elif o == '--list' or o == '--list0':
                if a not in ui.LISTARGS:
                    raise CFVValueError('list arg must be one of: ' + ', '.join(ui.LISTARGS))
                config.list = ui.LISTARGS[a]
                config.listsep = o == '--list0' and '\0' or '\n'
                if config.list == ui.LISTUNVERIFIED:
                    config.showunverified = 1
                view.set_stdout_special()  # redirect all messages to stderr so only the list gets on stdout
            elif o == '--showpaths':
                config.setx('showpaths', a)
            elif o == '--strippaths':
                config.setx('strippaths', a)
            elif o == '--fixpaths':
                config.setx('fixpaths', a)
            elif o == '--unquote':
                config.setx('unquote', a)
            elif o == '--encoding':
                config.setencoding(a)
            elif o == '--announceurl':
                config.setx('announceurl', a)
            elif o == '--piece_size_pow2':
                config.setx('piece_size_pow2', a)
            elif o == '--private_torrent':
                config.private_torrent = True
            elif o == '--noprivate_torrent':
                config.private_torrent = False
            elif o == '-h' or o == '-?' or o == '--help':
                printhelp()
            elif o == '--version':
                print 'cfv %s' % __version__
                try:
                    if not hash._nommap:
                        print '+mmap'
                except NameError:
                    pass
                try:
                    print 'fchksum %s' % fchksum.version()
                except NameError:
                    pass
                print 'python %08x-%s' % (sys.hexversion, sys.platform)
                sys.exit(0)
            prevopt = o
    except CFVValueError, e:
        view.perror('cfv: %s' % e)
        sys.exit(1)

    view.setup_output()

    if not manual:
        if mode == 0:
            filenamefilter.set_testfiles(args)
            autotest(typename)
        else:
            if typename == 'auto':
                typename = config.default_type_name
            make(cftypes.get_handler(typename), None, args)
    else:
        for a in manual:
            if mode == 0:
                filenamefilter.set_testfiles(args)
                test(a, typename)
            else:
                if typename != 'auto':
                    make(cftypes.get_handler(typename), a, args)
                else:
                    testa = ''
                    if config.gzip >= 0 and a[-3:] == '.gz':
                        testa = a[:-3]
                    cftype = cftypes.auto_filename_match(a, testa)
                    if not cftype:
                        raise CFVValueError('specify a filetype with -t, or use standard extension')
                    make(cftype, a, args)

    if mode == 0:
        show_unverified_files(args)

    # only print total stats if more than one checksum file has been checked. (or if none have)
    # We must also print stats here if there are unverified files or checksum file errors, since those conditions occur outside of the cf_stats section.
    if stats.subcount != 1 or stats.unverified or stats.cferror:
        view.pinfo(str(stats))

    sys.exit((stats.badcrc and 2) | (stats.badsize and 4) | (stats.notfound and 8) | (stats.ferror and 16) | (stats.unverified and 32) | (stats.cferror and 64))


if __name__ == '__main__':
    main()
