#! /usr/bin/env python

#    test_stringops.py - tests of cfv string operations
#    Copyright (C) 2005  Matthew Mueller <donut AT dakotacom DOT net>
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

import cfvtest
from cfv.strutil import uwidth, lchoplen, rchoplen
from cfvtest import TestCase


class uwidthTestCase(TestCase):
    def test_simple(self) -> None:
        self.assertEqual(uwidth('hello world'), 11)

    def test_nonspacing(self) -> None:
        self.assertEqual(uwidth('\0'), 0)
        self.assertEqual(uwidth('\u200b'), 0)
        self.assertEqual(uwidth('\u3099'), 0)
        self.assertEqual(uwidth('\u0327'), 0)

    def test_wide(self) -> None:
        self.assertEqual(uwidth('\u3053\u3093\u306b\u3061\u306f'), 10)
        self.assertEqual(uwidth('\u304c\u304e\u3050\u3052\u3054'), 10)
        self.assertEqual(uwidth('\u304b\u3099\u304d\u3099\u304f\u3099\u3051\u3099\u3053\u3099'), 10)

    def test_halfwidth(self) -> None:
        self.assertEqual(uwidth('\uFF79'), 1)
        self.assertEqual(uwidth('\uFF73\uFF79\uFF79\uFF79'), 4)

    def test_compose_noprecombined(self) -> None:
        self.assertEqual(uwidth('\u01b5\u0327\u0308\u01b6\u0327\u0308\u01b7\u0327\u0308\u01b8\u0327\u0308\u01b9\u0327\u0308\u01ba\u0327\u0308'), 6)


class chopTestCase(TestCase):
    def test_lchoplen_simple(self) -> None:
        self.assertEqual(lchoplen('hello world', 12), 'hello world')
        self.assertEqual(lchoplen('hello world', 11), 'hello world')
        self.assertEqual(lchoplen('hello world', 10), '...o world')
        self.assertEqual(lchoplen('hello world', 3), '...')

    def test_rchoplen_simple(self) -> None:
        self.assertEqual(rchoplen('hello world', 12), 'hello world')
        self.assertEqual(rchoplen('hello world', 11), 'hello world')
        self.assertEqual(rchoplen('hello world', 10), 'hello w...')
        self.assertEqual(rchoplen('hello world', 3), '...')

    def test_lchoplen_wide(self) -> None:
        self.assertEqual(lchoplen('\u3053\u3093\u306b\u3061\u306f', 11), '\u3053\u3093\u306b\u3061\u306f')
        self.assertEqual(lchoplen('\u3053\u3093\u306b\u3061\u306f', 10), '\u3053\u3093\u306b\u3061\u306f')
        self.assertEqual(lchoplen('\u3053\u3093\u306b\u3061\u306f', 9), '...\u306b\u3061\u306f')
        self.assertEqual(lchoplen('\u3053\u3093\u306b\u3061\u306f', 8), '...\u3061\u306f')
        self.assertEqual(lchoplen('\u3053\u3093\u306b\u3061\u306f', 4), '...')
        self.assertEqual(lchoplen('\u3053\u3093\u306b\u3061\u306f', 3), '...')

    def test_rchoplen_wide(self) -> None:
        self.assertEqual(rchoplen('\u3053\u3093\u306b\u3061\u306f', 11), '\u3053\u3093\u306b\u3061\u306f')
        self.assertEqual(rchoplen('\u3053\u3093\u306b\u3061\u306f', 10), '\u3053\u3093\u306b\u3061\u306f')
        self.assertEqual(rchoplen('\u3053\u3093\u306b\u3061\u306f', 9), '\u3053\u3093\u306b...')
        self.assertEqual(rchoplen('\u3053\u3093\u306b\u3061\u306f', 8), '\u3053\u3093...')
        self.assertEqual(rchoplen('\u3053\u3093\u306b\u3061\u306f', 4), '...')
        self.assertEqual(rchoplen('\u3053\u3093\u306b\u3061\u306f', 3), '...')

    def test_lchoplen_compose(self) -> None:
        self.assertEqual(lchoplen(
            '\u01b5\u0327\u0308\u01b6\u0327\u0308\u01b7\u0327\u0308\u01b8\u0327\u0308\u01b9\u0327\u0308\u01ba\u0327\u0308', 7),
            '\u01b5\u0327\u0308\u01b6\u0327\u0308\u01b7\u0327\u0308\u01b8\u0327\u0308\u01b9\u0327\u0308\u01ba\u0327\u0308')
        self.assertEqual(lchoplen(
            '\u01b5\u0327\u0308\u01b6\u0327\u0308\u01b7\u0327\u0308\u01b8\u0327\u0308\u01b9\u0327\u0308\u01ba\u0327\u0308', 6),
            '\u01b5\u0327\u0308\u01b6\u0327\u0308\u01b7\u0327\u0308\u01b8\u0327\u0308\u01b9\u0327\u0308\u01ba\u0327\u0308')
        self.assertEqual(lchoplen(
            '\u01b5\u0327\u0308\u01b6\u0327\u0308\u01b7\u0327\u0308\u01b8\u0327\u0308\u01b9\u0327\u0308\u01ba\u0327\u0308', 5),
            '...\u01b9\u0327\u0308\u01ba\u0327\u0308')
        self.assertEqual(lchoplen(
            '\u01b5\u0327\u0308\u01b6\u0327\u0308\u01b7\u0327\u0308\u01b8\u0327\u0308\u01b9\u0327\u0308\u01ba\u0327\u0308', 4),
            '...\u01ba\u0327\u0308')
        self.assertEqual(lchoplen(
            '\u01b5\u0327\u0308\u01b6\u0327\u0308\u01b7\u0327\u0308\u01b8\u0327\u0308\u01b9\u0327\u0308\u01ba\u0327\u0308', 3),
            '...')

    def test_rchoplen_compose(self) -> None:
        self.assertEqual(rchoplen(
            '\u01b5\u0327\u0308\u01b6\u0327\u0308\u01b7\u0327\u0308\u01b8\u0327\u0308\u01b9\u0327\u0308\u01ba\u0327\u0308', 7),
            '\u01b5\u0327\u0308\u01b6\u0327\u0308\u01b7\u0327\u0308\u01b8\u0327\u0308\u01b9\u0327\u0308\u01ba\u0327\u0308')
        self.assertEqual(rchoplen(
            '\u01b5\u0327\u0308\u01b6\u0327\u0308\u01b7\u0327\u0308\u01b8\u0327\u0308\u01b9\u0327\u0308\u01ba\u0327\u0308', 6),
            '\u01b5\u0327\u0308\u01b6\u0327\u0308\u01b7\u0327\u0308\u01b8\u0327\u0308\u01b9\u0327\u0308\u01ba\u0327\u0308')
        self.assertEqual(rchoplen(
            '\u01b5\u0327\u0308\u01b6\u0327\u0308\u01b7\u0327\u0308\u01b8\u0327\u0308\u01b9\u0327\u0308\u01ba\u0327\u0308', 5),
            '\u01b5\u0327\u0308\u01b6\u0327\u0308...')
        self.assertEqual(rchoplen(
            '\u01b5\u0327\u0308\u01b6\u0327\u0308\u01b7\u0327\u0308\u01b8\u0327\u0308\u01b9\u0327\u0308\u01ba\u0327\u0308', 4),
            '\u01b5\u0327\u0308...')
        self.assertEqual(rchoplen(
            '\u01b5\u0327\u0308\u01b6\u0327\u0308\u01b7\u0327\u0308\u01b8\u0327\u0308\u01b9\u0327\u0308\u01ba\u0327\u0308', 3),
            '...')


if __name__ == '__main__':
    cfvtest.main()
