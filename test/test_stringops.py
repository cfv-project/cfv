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

# this initialization stuff should go in its own file somewhere, when I think of a good name for it.
import os,sys

import imp
_cfvfn = os.path.join(os.pardir,'cfv')
cfv = imp.load_source('cfv', _cfvfn+'.py', open(_cfvfn))
sys.modules['cfv'] = cfv

#sys.path.insert(0, os.path.abspath(os.pardir))
#import cfv


import unittest
from unittest import TestCase

from cfv import uwidth, lchoplen, rchoplen


class uwidthTestCase(TestCase):
	def test_simple(self):
		self.assertEqual(uwidth(u'hello world'), 11)
	
	def test_nonspacing(self):
		self.assertEqual(uwidth(u'\0'), 0)
		self.assertEqual(uwidth(u'\u200b'), 0)
		self.assertEqual(uwidth(u'\u3099'), 0)
		self.assertEqual(uwidth(u'\u0327'), 0)

	def test_wide(self):
		self.assertEqual(uwidth(u'\u3053\u3093\u306b\u3061\u306f'), 10)
		self.assertEqual(uwidth(u'\u304c\u304e\u3050\u3052\u3054'), 10)
		self.assertEqual(uwidth(u'\u304b\u3099\u304d\u3099\u304f\u3099\u3051\u3099\u3053\u3099'), 10)

	def test_halfwidth(self):
		self.assertEqual(uwidth(u'\uFF79'), 1)
		self.assertEqual(uwidth(u'\uFF73\uFF79\uFF79\uFF79'), 4)
		
	def test_compose_noprecombined(self):
		self.assertEqual(uwidth(u'\u01b5\u0327\u0308\u01b6\u0327\u0308\u01b7\u0327\u0308\u01b8\u0327\u0308\u01b9\u0327\u0308\u01ba\u0327\u0308'), 6)


class chopTestCase(TestCase):
	def test_lchoplen_simple(self):
		self.assertEqual(lchoplen(u'hello world', 12), (u'hello world', 11))
		self.assertEqual(lchoplen(u'hello world', 11), (u'hello world', 11))
		self.assertEqual(lchoplen(u'hello world', 10), (u'...o world', 10))
		self.assertEqual(lchoplen(u'hello world', 3), (u'...', 3))

	def test_rchoplen_simple(self):
		self.assertEqual(rchoplen(u'hello world', 12), (u'hello world', 11))
		self.assertEqual(rchoplen(u'hello world', 11), (u'hello world', 11))
		self.assertEqual(rchoplen(u'hello world', 10), (u'hello w...', 10))
		self.assertEqual(rchoplen(u'hello world', 3), (u'...', 3))
	
	def test_lchoplen_wide(self):
		self.assertEqual(lchoplen(u'\u3053\u3093\u306b\u3061\u306f',11), (u'\u3053\u3093\u306b\u3061\u306f', 10))
		self.assertEqual(lchoplen(u'\u3053\u3093\u306b\u3061\u306f',10), (u'\u3053\u3093\u306b\u3061\u306f', 10))
		self.assertEqual(lchoplen(u'\u3053\u3093\u306b\u3061\u306f',9), (u'...\u306b\u3061\u306f', 9))
		self.assertEqual(lchoplen(u'\u3053\u3093\u306b\u3061\u306f',8), (u'...\u3061\u306f', 7))
		self.assertEqual(lchoplen(u'\u3053\u3093\u306b\u3061\u306f',4), (u'...', 3))
		self.assertEqual(lchoplen(u'\u3053\u3093\u306b\u3061\u306f',3), (u'...', 3))
	
	def test_rchoplen_wide(self):
		self.assertEqual(rchoplen(u'\u3053\u3093\u306b\u3061\u306f',11), (u'\u3053\u3093\u306b\u3061\u306f', 10))
		self.assertEqual(rchoplen(u'\u3053\u3093\u306b\u3061\u306f',10), (u'\u3053\u3093\u306b\u3061\u306f', 10))
		self.assertEqual(rchoplen(u'\u3053\u3093\u306b\u3061\u306f',9), (u'\u3053\u3093\u306b...', 9))
		self.assertEqual(rchoplen(u'\u3053\u3093\u306b\u3061\u306f',8), (u'\u3053\u3093...', 7))
		self.assertEqual(rchoplen(u'\u3053\u3093\u306b\u3061\u306f',4), (u'...', 3))
		self.assertEqual(rchoplen(u'\u3053\u3093\u306b\u3061\u306f',3), (u'...', 3))
	
	def test_lchoplen_compose(self):
		self.assertEqual(lchoplen(u'\u01b5\u0327\u0308\u01b6\u0327\u0308\u01b7\u0327\u0308\u01b8\u0327\u0308\u01b9\u0327\u0308\u01ba\u0327\u0308',7),
				(u'\u01b5\u0327\u0308\u01b6\u0327\u0308\u01b7\u0327\u0308\u01b8\u0327\u0308\u01b9\u0327\u0308\u01ba\u0327\u0308', 6))
		self.assertEqual(lchoplen(u'\u01b5\u0327\u0308\u01b6\u0327\u0308\u01b7\u0327\u0308\u01b8\u0327\u0308\u01b9\u0327\u0308\u01ba\u0327\u0308',6),
				(u'\u01b5\u0327\u0308\u01b6\u0327\u0308\u01b7\u0327\u0308\u01b8\u0327\u0308\u01b9\u0327\u0308\u01ba\u0327\u0308', 6))
		self.assertEqual(lchoplen(u'\u01b5\u0327\u0308\u01b6\u0327\u0308\u01b7\u0327\u0308\u01b8\u0327\u0308\u01b9\u0327\u0308\u01ba\u0327\u0308',5),
				(u'...\u01b9\u0327\u0308\u01ba\u0327\u0308', 5))
		self.assertEqual(lchoplen(u'\u01b5\u0327\u0308\u01b6\u0327\u0308\u01b7\u0327\u0308\u01b8\u0327\u0308\u01b9\u0327\u0308\u01ba\u0327\u0308',4),
				(u'...\u01ba\u0327\u0308', 4))
		self.assertEqual(lchoplen(u'\u01b5\u0327\u0308\u01b6\u0327\u0308\u01b7\u0327\u0308\u01b8\u0327\u0308\u01b9\u0327\u0308\u01ba\u0327\u0308',3),
				(u'...', 3))

	def test_rchoplen_compose(self):
		self.assertEqual(rchoplen(u'\u01b5\u0327\u0308\u01b6\u0327\u0308\u01b7\u0327\u0308\u01b8\u0327\u0308\u01b9\u0327\u0308\u01ba\u0327\u0308',7),
				(u'\u01b5\u0327\u0308\u01b6\u0327\u0308\u01b7\u0327\u0308\u01b8\u0327\u0308\u01b9\u0327\u0308\u01ba\u0327\u0308', 6))
		self.assertEqual(rchoplen(u'\u01b5\u0327\u0308\u01b6\u0327\u0308\u01b7\u0327\u0308\u01b8\u0327\u0308\u01b9\u0327\u0308\u01ba\u0327\u0308',6),
				(u'\u01b5\u0327\u0308\u01b6\u0327\u0308\u01b7\u0327\u0308\u01b8\u0327\u0308\u01b9\u0327\u0308\u01ba\u0327\u0308', 6))
		self.assertEqual(rchoplen(u'\u01b5\u0327\u0308\u01b6\u0327\u0308\u01b7\u0327\u0308\u01b8\u0327\u0308\u01b9\u0327\u0308\u01ba\u0327\u0308',5),
				(u'\u01b5\u0327\u0308\u01b6\u0327\u0308...', 5))
		self.assertEqual(rchoplen(u'\u01b5\u0327\u0308\u01b6\u0327\u0308\u01b7\u0327\u0308\u01b8\u0327\u0308\u01b9\u0327\u0308\u01ba\u0327\u0308',4),
				(u'\u01b5\u0327\u0308...', 4))
		self.assertEqual(rchoplen(u'\u01b5\u0327\u0308\u01b6\u0327\u0308\u01b7\u0327\u0308\u01b8\u0327\u0308\u01b9\u0327\u0308\u01ba\u0327\u0308',3),
				(u'...', 3))


if __name__ == '__main__':
	unittest.main()