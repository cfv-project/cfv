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

default_ns = globals().copy()
default_ns['__name__']='__main__'

import os,sys
import traceback
from glob import glob

import unittest
from unittest import TestCase, main
import doctest

import imp

cfvenv=''

cfvfn=None
ver_mmap=ver_fchksum=None
runcfv=None


class NullFile:
	def isatty(self): return 0
	def write(self,s): pass
	def writelines(self,l): pass
	def flush(self): pass
	def close(self): pass
nullfile = NullFile()


def expand_cmdline(cmd):
	argv = []
	for arg in cmd.split(' '): #bad.  shlex.split would be perfect, but its only in python >=2.3
		arg = arg.replace('"','') # hack so --foo="bar" works.
		if '*' in arg or '?' in arg or '[' in arg:
			argv.extend(glob(arg))
		else:
			argv.append(arg)
	return argv


def runcfv_exe(cmd, stdin=None, stdout=None, stderr=None):
	try:
		import subprocess # subprocess module only in python >= 2.4, but it works on windows, unlike commands
	except ImportError:
		from commands import getstatusoutput
		runcmd = cfvenv+cfvfn+' '+cmd
		if stdin:
			runcmd = 'cat '+stdin+' | '+runcmd
		if stdout:
			runcmd = runcmd + ' > '+stdout
		if stderr:
			runcmd = runcmd + ' 2> '+stderr
		s,o = getstatusoutput(runcmd)
		if os.WIFSIGNALED(s):
			s = -os.WTERMSIG(s)
		else:
			s = os.WEXITSTATUS(s)
		return s,o
	else:
		def open_output(fn):
			if fn=='/dev/null' and not os.path.exists(fn):
				fn='nul'
			return open(fn,'wb')
		p_stdin = p_stdout = p_stderr = subprocess.PIPE
		if stdin:
			p_stdin = open(stdin,'rb')
		if stdout:
			p_stdout = open_output(stdout)
		else:
			p_stderr = subprocess.STDOUT
		if stderr:
			p_stderr = open_output(stderr)
		argv = [cfvfn]+expand_cmdline(cmd)
		proc = subprocess.Popen(argv, stdin=p_stdin, stdout=p_stdout, stderr=p_stderr)
		for f in p_stdin, p_stdout, p_stderr:
			if f not in (subprocess.PIPE, subprocess.STDOUT, None):
				f.close()
		obuf,ebuf = proc.communicate()
		if ebuf or obuf is None:
			assert not obuf
			o = ebuf
		else:
			o = obuf
		s = proc.returncode
		if o:
			if o[-2:] == '\r\n': o = o[:-2]
			elif o[-1:] in '\r\n': o = o[:-1]
		return s, o

def runcfv_py(cmd, stdin=None, stdout=None, stderr=None):
	if stdin is not None and ver_fchksum:
		fileno =  os.open(stdin, os.O_RDONLY | getattr(os,'O_BINARY', 0))
		assert fileno >= 0
		saved_stdin_fileno = os.dup(sys.stdin.fileno())
		os.dup2(fileno, sys.stdin.fileno())
		os.close(fileno)
	try:
		from cStringIO import StringIO
		StringIO().write(u'foo') # cStringIO with unicode doesn't work in python 1.6
	except (ImportError, SystemError):
		from StringIO import StringIO
	obuf = StringIO()
	saved = sys.stdin,sys.stdout,sys.stderr,sys.argv
	cwd = os.getcwd()
	def open_output(file,obuf=obuf):
		if file:
			if file=="/dev/null":
				return nullfile
			return open(file,'wb')
		else:
			return obuf
	try:
		if stdin:  sys.stdin = open(stdin,'rb')
		else:      sys.stdin = StringIO()
		sys.stdout = open_output(stdout)
		sys.stderr = open_output(stderr)
		sys.argv = [cfvfn] + expand_cmdline(cmd)
		cfv_ns = default_ns.copy()
		try:
			exec cfv_compiled in cfv_ns
			s = 'no exit?'
		except SystemExit, e:
			s = e.code
			if stdin:  sys.stdin.close()
			if stdout: sys.stdout.close()
			if stderr: sys.stderr.close()
		except KeyboardInterrupt:
			raise
		except:
			traceback.print_exc(file=obuf)
			s = 1
	finally:
		sys.stdin,sys.stdout,sys.stderr,sys.argv = saved
		if locals().has_key('saved_stdin_fileno'):
			os.dup2(saved_stdin_fileno, sys.stdin.fileno())
			os.close(saved_stdin_fileno)
		os.chdir(cwd)
	o = obuf.getvalue()
	if o:
		if o[-2:] == '\r\n': o = o[:-2]
		elif o[-1:] in '\r\n': o = o[:-1]
	return s, o


def get_version_flags():
	global ver_fchksum, ver_mmap
	s,o=runcfv("--version")
	ver_fchksum = o.find('fchksum')>=0
	ver_mmap = o.find('mmap')>=0

def setcfv(fn=None,internal=None):
	global cfvfn, cfv_compiled, cfv, runcfv

	if internal is not None:
		runcfv = internal and runcfv_py or runcfv_exe

	if fn is not None:
		assert os.path.exists(fn)
		try:
			del sys.modules['cfv']
		except KeyError:
			pass
		cfvfn = fn
		_cfv_code = open(cfvfn,'r').read().replace('\r\n','\n').replace('\r','\n')
		cfv_compiled = compile(_cfv_code,cfvfn,'exec')

		#if sys.modules.has_key('cfv'):
		#	cfv = sys.modules['cfv']
		#else:
		# don't load it unless it looks like it is actually the source.  (Avoid accidentally importing the wrapper script and causing it to run cfv..)
		if os.path.getsize(fn) > 1000:
			cfv = imp.load_source('cfv', cfvfn+'.py', open(cfvfn))
		else:
			cfv = imp.new_module('cfv')
		sys.modules['cfv'] = cfv

	get_version_flags()
			
def setenv(k,v):
	global cfvenv
	cfvenv="%s=%s %s"%(k,v,cfvenv)
	os.environ[k]=v
	get_version_flags()



def all_unittests_suite():
	testpath = os.path.split(__file__)[0] or os.curdir
	modules_to_test = [os.path.splitext(f)[0] for f in os.listdir(testpath) if f.lower().startswith("test_") and f.lower().endswith(".py")]
	alltests = unittest.TestSuite()
	for module in map(__import__, modules_to_test):
		alltests.addTest(unittest.findTestCases(module))
	for module in cfv,:
		alltests.addTest(doctest.DocTestSuite(module))
	return alltests



# initialize with default options
setcfv(fn=os.path.join(os.pardir,'cfv'), internal=1)

if __name__ == '__main__':
	main(defaultTest='all_unittests_suite')

