#! /usr/bin/env python

#    test_caching.py - tests of cfv caching module
#    Copyright (C) 2013  Matthew Mueller <donut AT users DOT sourceforge DOT net>
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

import errno
import os
import shutil
import tempfile

from cfv.caching import FileInfoCache
from cfvtest import TestCase


class AbsTestCase(TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp()

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir)

    def mkpath(self, name):
        return os.path.join(self.tempdir, name)

    def mkfile(self, name, contents: str):
        head, tail = os.path.split(name)
        fullhead = os.path.join(self.tempdir, head)
        if head and not os.path.exists(fullhead):
            os.makedirs(fullhead)
        fullpath = os.path.join(fullhead, tail)
        with open(fullpath, 'wt') as f:
            f.write(contents)
        return fullpath


class RelTestCase(TestCase):
    def setUp(self) -> None:
        self.olddir = os.getcwd()
        self.tempdir = tempfile.mkdtemp()
        os.chdir(self.tempdir)

    def tearDown(self) -> None:
        os.chdir(self.olddir)
        shutil.rmtree(self.tempdir)

    def mkpath(self, name):
        return name

    def mkfile(self, name, contents: str):
        head, tail = os.path.split(name)
        if head and not os.path.exists(head):
            os.makedirs(head)
        with open(name, 'wt') as f:
            f.write(contents)
        return name


class AbsPathKeyTest(AbsTestCase):
    def test_get_path_key(self) -> None:
        cache = FileInfoCache()

        with self.assertRaises(OSError):
            cache.get_path_key(self.mkpath('non_existent'))

        a = self.mkfile('a', '')
        b = self.mkfile('b', '')
        c = self.mkpath('c')
        keya = cache.get_path_key(a)
        keyb = cache.get_path_key(b)
        self.assertNotEqual(keya, keyb)
        self.assertEqual(keyb, cache.get_path_key(b))

        os.rename(a, c)
        # due to path_key_cache, we should get the same key even if the file no longer exists
        self.assertEqual(keya, cache.get_path_key(a))

        keyc = cache.get_path_key(c)
        st = os.stat(c)
        if st.st_ino:
            self.assertEqual(keya, keyc)
        else:
            self.assertNotEqual(keya, keyc)

    def test_rename(self) -> None:
        cache = FileInfoCache()
        a = self.mkfile('a', 'a')
        b = self.mkfile('b', 'b')
        c = self.mkpath('c')

        cache.set_flag(a, 'f1')
        cache.set_flag(a, '_1')
        cache.set_flag(b, 'f2')
        cache.set_flag(b, '_2')

        self.assertDictEqual({'f1': 1, '_1': 1}, cache.getfinfo(a))

        cache.rename(a, c)
        cache.rename(b, a)

        self.assertTrue(cache.has_flag(a, 'f2'))
        self.assertFalse(cache.has_flag(a, '_2'))
        self.assertFalse(cache.has_flag(a, 'f1'))

        self.assertTrue(cache.has_flag(c, 'f1'))
        self.assertFalse(cache.has_flag(c, '_1'))
        self.assertFalse(cache.has_flag(c, 'f2'))

        self.assertFalse(cache.has_flag(b, 'f1'))
        self.assertFalse(cache.has_flag(b, '_1'))
        self.assertFalse(cache.has_flag(b, 'f2'))
        self.assertFalse(cache.has_flag(b, '_2'))

        self.assertDictEqual({'f1': 1}, cache.getfinfo(c))
        self.assertDictEqual({'f2': 1}, cache.getfinfo(a))
        self.assertDictEqual({}, cache.getfinfo(b))


class RelPathKeyTest(RelTestCase):
    def test_nocase_findfile(self) -> None:
        cache = FileInfoCache()
        a1 = self.mkfile('aAaA/AaA1', '1')
        self.mkfile('aAaA/Aaa2', '2')
        self.mkfile('aAaA/AAa2', '3')

        self.assertEqual(a1, cache.nocase_findfile(self.mkpath('aaAA/aaa1')))
        with self.assertRaises(IOError) as cm:
            cache.nocase_findfile(self.mkpath('aaAb/aaa1'))
        self.assertEqual(errno.ENOENT, cm.exception.errno)

        with self.assertRaises(IOError) as cm:
            cache.nocase_findfile(self.mkpath('aaAA/aab1'))
        self.assertEqual(errno.ENOENT, cm.exception.errno)

        with self.assertRaises(IOError) as cm:
            cache.nocase_findfile(self.mkpath('aaAA/aaa2'))
        self.assertEqual(errno.EEXIST, cm.exception.errno)

    def test_nocase_findfile_parent(self) -> None:
        cache = FileInfoCache()
        self.mkfile('aaaA/aaA1', '1')
        self.mkfile('aAaA/aaa2', '2')

        # right now we don't handle this case, though it would be possible
        # to generate all possible matches and see if the number is exactly
        # one.
        with self.assertRaises(IOError) as cm:
            cache.nocase_findfile(self.mkpath('aaAA/aaa2'))
        self.assertEqual(errno.EEXIST, cm.exception.errno)
