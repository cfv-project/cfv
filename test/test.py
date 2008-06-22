#! /usr/bin/env python

#    test.py - tests for cfv (Command-line File Verify)
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

import re,os,sys,string,operator,shutil,getopt,gzip,zlib,stat,traceback,time
from glob import glob
try: # tempfile.mkdtemp is only in python 2.3+
	from tempfile import mkdtemp
except ImportError:
	import tempfile
	def mkdtemp():
		d = tempfile.mktemp()
		os.mkdir(d)
		return d
try: #zip only in python2.0+
	zip
except NameError:
	def zip(a,b):
		return map(None, a, b) #not exactly the same, but good enough for us.
	

try:
	try: import BitTorrent
	except ImportError: import BitTornado; BitTorrent = BitTornado
except ImportError: BitTorrent = None


fmt_info = {
	#name: (hascrc, hassize, cancreate, available)
	'sha1': (1,0,1,1),
	'md5': (1,0,1,1),
	'bsdmd5': (1,0,1,1),
	'sfv': (1,0,1,1),
	'sfvmd5': (1,0,1,1),
	'csv': (1,1,1,1),
	'csv2': (0,1,1,1),
	'csv4': (1,1,1,1),
	'crc': (1,1,1,1),
	'par': (1,1,0,1),
	'par2': (1,1,0,1),
	'torrent': (1,1,1,not not BitTorrent),
}
def fmt_hascrc(f):
	return fmt_info[f][0]
def fmt_hassize(f):
	return fmt_info[f][1]
def fmt_cancreate(f):
	return fmt_info[f][2]
def fmt_available(f):
	return fmt_info[f][3]
def allfmts():
	return fmt_info.keys()


if hasattr(operator,'gt'):
	op_gt=operator.gt
	op_eq=operator.eq
else:
	def op_gt(a,b): return a>b
	def op_eq(a,b): return a==b


class rcurry:
	def __init__(self, func, *args, **kw):
		self.curry_func = func
		self.curry_args = args
		self.curry_kw = kw
	def __call__(self, *_args, **_kwargs):
		kw = self.curry_kw.copy()
		kw.update(_kwargs)
		return apply(self.curry_func, (_args+self.curry_args), kw)

class NullFile:
	def isatty(self): return 0
	def write(self,s): pass
	def writelines(self,l): pass
	def flush(self): pass
	def close(self): pass
nullfile = NullFile()

def pathfind(p, path=string.split(os.environ.get('PATH',os.defpath),os.pathsep)):
	for d in path:
		if os.path.exists(os.path.join(d,p)):
			return 1

def pathjoin_and_mkdir(*components):
	"""Join components of a filename together and create directory to contain the file, if needed."""
	result = os.path.join(*components)
	path = os.path.split(result)[0]
	if not os.path.exists(path):
		os.makedirs(path)
	return result

def readfile(fn):
	f = open(fn,'rb')
	d = f.read()
	f.close()
	return d

def writefile_and_reopen(fn,data):
	"""Write data to file, close, and then reopen readonly, and return the fd.

	This is for the benefit of windows, where you need to close and reopen the
	file as readonly in order for it to be openable simultaneously.
	"""
	f = open(fn,'wb')
	if data:
		f.write(data)
	f.close()
	f = open(fn,'rb')
	return f

class stats:
	ok=0
	failed=0

def logr(text):
	logfile.write(text);
def log(text):
	logr(text+"\n");

def get_version_flags():
	global ver_fchksum, ver_mmap
	s,o=runcfv(cfvcmd+" --version")
	ver_fchksum = string.find(o,'fchksum')>=0
	ver_mmap = string.find(o,'mmap')>=0

def test_log_results(cmd,s,o,r,kw):
	"""
	cmd=command being tested (info only)
	s=return status
	o=output
	r=result (false=ok, anything else=fail (anything other than 1 will be printed))
	"""
	log("*** testing "+cmd + (kw and ' '+str(kw) or ''));
	log(o);
	if r:
		stats.failed=stats.failed+1
		print "failed test:",cmd
		result="FAILED";
		if type(r)!=type(1) or r!=1:
			result=result+" (%s)"%r
	else:
		stats.ok=stats.ok+1
		result="OK";
	log("%s (%s)"%(result,s));
	if r:
		log("\n".join(traceback.format_stack()))
	log("");
	

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
		runcmd = cfvenv+cfvexe+' '+cmd
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
		argv = [cfvexe]+expand_cmdline(cmd)
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
		sys.argv = [cfvexe] + expand_cmdline(cmd)
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
			import traceback
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

def test_external(cmd,test):
	from commands import getstatusoutput
	s,o = getstatusoutput(cmd)
	r=test(s,o)
	test_log_results(cmd,s,o,r, None)

def test_generic(cmd,test, **kw):
	#s,o=runcfv(cmd)
	s,o=apply(runcfv,(cmd,), kw)
	r=test(s,o)
	test_log_results(cfvenv+cfvexe+" "+cmd,s,o,r, kw)

class cst_err(Exception): pass
def cfv_stdin_test(cmd,file):
	s1=s2=None
	o1=o2=''
	r=0
	try:
		s1,o1=runcfv(cmd+' '+file)
		if s1: raise cst_err, 2
		s2,o2=runcfv(cmd+' -', stdin=file)
		if s2: raise cst_err, 3
		x=re.search('^([^\r\n]*)'+re.escape(file)+'(.*)$[\r\n]{0,2}^-: (\d+) files, (\d+) OK.  [\d.]+ seconds, [\d.]+K(/s)?$',o1,re.M|re.DOTALL)
		if not x: raise cst_err, 4
		x2=re.search('^'+re.escape(x.group(1))+'[\t ]*'+re.escape(x.group(2))+'$[\r\n]{0,2}^-: (\d+) files, (\d+) OK.  [\d.]+ seconds, [\d.]+K(/s)?$',o2,re.M)
		if not x2: raise cst_err, 5
	except cst_err, er:
		r=er
	test_log_results('stdin/out of '+cmd+' with file '+file,(s1,s2),o1+'\n'+o2,r, None)

def cfv_stdin_progress_test(t,file):
	s1=s2=None
	o1=o2=c1=c2=''
	r=0
	dir = mkdtemp()
	try:
		try:
			cf1=os.path.join(dir,'cf1.'+t)
			cf2=os.path.join(dir,'cf2.'+t)
			s1,o1=runcfv("%s --progress=yes -C -t %s -f %s %s"%(cfvcmd,t,cf1,file))
			if s1: raise cst_err, 2
			s2,o2=runcfv("%s --progress=yes -C -t %s -f %s -"%(cfvcmd,t,cf2),stdin=file)
			if s2: raise cst_err, 3
			if t!='csv2':#csv2 has only filesize, hence checksum never happens, so no progress
				x=re.match(re.escape(file)+r' : (\.{20}[-\b.#\\|/]*)[ \r\n]+'+re.escape(cf1)+': (\d+) files, (\d+) OK.  [\d.]+ seconds, [\d.]+K(/s)?$',o1,re.M|re.DOTALL)
				if not x: raise cst_err, 4
			x2=re.match(r' : (\.[-\b.#/|\\]*)[\t ]*[ \r\n]+'+re.escape(cf2)+': (\d+) files, (\d+) OK.  [\d.]+ seconds, [\d.]+K(/s)?$',o2,re.M)
			if not x2: raise cst_err, 5
			if t=='crc':
				c1 = readfile(cf1).replace(file,' '*len(file))
			else:
				c1 = readfile(cf1).replace(file,'')
			c2 = readfile(cf2)
			if c1!=c2: raise cst_err, 6
		except cst_err, er:
			r=er
		test_log_results('progress=yes stdin/out of '+t+' with file '+file,(s1,s2),o1+'\n'+o2+'\n--\n'+c1+'\n'+c2,r, None)
	finally:
		shutil.rmtree(dir)


def rx_test(pat,str):
	if re.search(pat,str): return 0
	return 1
def status_test(s,o,expected=0):
	if s==expected:
		return 0
	return 1

rx_Begin=r'^(?:.* )?(\d+) files, (\d+) OK'
rx_unv=r', (\d+) unverified'
rx_notfound=r', (\d+) not found'
rx_ferror=r', (\d+) file errors'
rx_bad=r', (\d+) bad(crc|size)'
rx_badcrc=r', (\d+) badcrc'
rx_badsize=r', (\d+) badsize'
rx_cferror=r', (\d+) chksum file errors'
rx_misnamed=r', (\d+) misnamed'
rx_End=r'(, \d+ differing cases)?(, \d+ quoted filenames)?.  [\d.]+ seconds, [\d.]+K(/s)?$'
rxo_TestingFrom=re.compile(r'^testing from .* \((.+?)\b.*\)[\n\r]*$', re.M)

def optionalize(s):
	return '(?:%s)?'%s
rx_StatusLine=rx_Begin+''.join(map(optionalize,[rx_badcrc,rx_badsize,rx_notfound,rx_ferror,rx_unv,rx_cferror,rx_misnamed]))+rx_End

class OneOf:
	def __init__(self, *possibilities):
		self.possible = possibilities
	def __cmp__(self, a):
		if a in self.possible: return 0
		return cmp(a,self.possible[0])
	def __repr__(self):
		return 'OneOf'+repr(self.possible)
		
def intize(s):
	return s and int(s) or 0
def icomp(foo):
	exp,act = foo
	if exp==-1: return 0
	return exp!=act

def tail(s):
	#the last line might not be what we want, since stdout and stderr can get mixed up in some cases.
	#return string.split(s,'\n')[-1]
	lines = s.splitlines()
	lines.reverse()
	for line in lines:
		if re.search(rx_StatusLine, line):
			return line
	return ''

def cfv_test(s,o, op=op_gt, opval=0):
	x=re.search(rx_Begin+rx_End,tail(o))
	if s==0 and x and x.group(1) == x.group(2) and op(int(x.group(1)),opval):
		return 0
	return 1

def cfv_status_test(s,o, unv=0, notfound=0, badcrc=0, badsize=0, cferror=0, ferror=0):
	expected_status = (badcrc and 2) | (badsize and 4) | (notfound and 8) | (ferror and 16) | (unv and 32) | (cferror and 64)
	if s==expected_status:
		return 0
	return 'bad status expected %s got %s'%(expected_status, s)

def cfv_all_test(s,o, files=-2, ok=0, unv=0, notfound=0, badcrc=0, badsize=0, cferror=0, ferror=0, misnamed=0):
	sresult = cfv_status_test(s,o,unv=unv,notfound=notfound,badcrc=badcrc,badsize=badsize,cferror=cferror,ferror=ferror)
	if sresult:
		return sresult
	x=re.search(rx_StatusLine,tail(o))
	if x:
		if files==-2:
			files = reduce(operator.add, [ok,badcrc,badsize,notfound,ferror])
		expected = [files,ok,badcrc,badsize,notfound,ferror,unv,cferror,misnamed]
		actual = map(intize, x.groups()[:9])
		if not filter(icomp, map(None,expected,actual)):
			return 0
		return 'expected %s got %s'%(expected,actual)
	return 'status line not found in output'

def cfv_unv_test(s,o,unv=1):
	x=re.search(rx_Begin+rx_unv+rx_End,tail(o))
	if s!=0 and x and x.group(1) == x.group(2) and int(x.group(1))>0:
		if unv and int(x.group(3))!=unv:
			return 1
		return 0
	return 1

def cfv_unvonly_test(s,o,unv=1):
	x=re.search(rx_Begin+rx_unv+rx_End,tail(o))
	if s!=0 and x and int(x.group(3))==unv:
		return 0
	return 1

def cfv_notfound_test(s,o,unv=1):
	x=re.search(rx_Begin+rx_notfound+rx_End,tail(o))
	if s!=0 and x and int(x.group(2))==0 and int(x.group(1))>0:
		if int(x.group(3))!=unv:
			return 1
		return 0
	return 1

def cfv_cferror_test(s,o,bad=1):
	x=re.search(rx_Begin+rx_cferror+rx_End,tail(o))
	if s!=0 and x and int(x.group(3))>0:
		if bad>0 and int(x.group(3))!=bad:
			return 1
		return 0
	return 1

def cfv_bad_test(s,o,bad=-1):
	x=re.search(rx_Begin+rx_bad+rx_End,tail(o))
	if s!=0 and x and int(x.group(1))>0 and int(x.group(3))>0:
		if bad>0 and int(x.group(3))!=bad:
			return 1
		return 0
	return 1

def cfv_typerestrict_test(s,o,t):
	matches = rxo_TestingFrom.findall(o)
	if not matches:
		return 1
	for match in matches:
		if match != t:
			return 1
	return 0

def cfv_listdata_test(s,o):
	if s==0 and re.search('^data1\0data2\0data3\0data4\0$',o,re.I):
		return 0
	return 1
def joincurpath(f):
	return os.path.join(os.getcwd(), f)
def cfv_listdata_abs_test(s,o):
	if s==0 and re.search('^'+re.escape('\0'.join(map(joincurpath, ['data1','data2','data3','data4'])))+'\0$',o,re.I):
		return 0
	return 1
def cfv_listdata_unv_test(s,o):
	if s==32 and re.search('^test.py\0testfix.csv\0$',o,re.I):
		return 0
	return 1
def cfv_listdata_bad_test(s,o):
	if s&6 and not s&~6 and re.search('^(d2.)?test4.foo\0test.ext.end\0test2.foo\0test3\0$',o,re.I):
		return 0
	return 1

def cfv_version_test(s,o):
	x=re.search(r'cfv v([\d.]+) -',o)
	x2=re.search(r'cfv ([\d.]+) ',open(os.path.join(os.pardir,"README")).readline())
	x3=re.search(r' v([\d.]+):',open(os.path.join(os.pardir,"Changelog")).readline())
	if x: log('cfv: '+x.group(1))
	if x2: log('README: '+x2.group(1))
	if x3: log('Changelog: '+x3.group(1))
	#if os.path.isdir(os.path.join(os.pardir,'debian')):
	#	x4=re.search(r'cfv \(([\d.]+)-\d+\) ',open(os.path.join(os.pardir,"debian","changelog")).readline())
	#	if x4: log('deb changelog: '+x4.group(1))
	#	if not x or not x4 or x4.group(1)!=x.group(1):
	#		return 1
	if x and x2 and x3 and x.group(1)==x2.group(1) and x.group(1)==x3.group(1):
		return 0
	return 1

def cfv_cftypehelp_test(s,o,expected):
	if s!=expected:
		return 1
	for tname in allfmts()+['auto']:
		if o.count(tname)<1:
			return 'type %s not found in output'%tname
	return 0

def cfv_nooutput_test(s,o,expected=0):
	if s!=expected:
		return 1
	if o:
		return 'output: %s'%(repr(o),)
	return 0

def T_test(f, extra=None):
	cmd=cfvcmd
	if extra:
		cmd=cmd+" "+extra
	test_generic(cmd+" -T -f test"+f,cfv_test)
	test_generic(cmd+" -i -T -f test"+f,cfv_test) #all tests should work with -i
	test_generic(cmd+" -m -T -f test"+f,cfv_test) #all tests should work with -m
	
	test_generic(cmd+" -T --list0=ok -f test"+f, cfv_listdata_test, stderr="/dev/null")
	test_generic(cmd+" -T --showpaths=n-r --list0=ok -f test"+f, cfv_listdata_test, stderr="/dev/null")
	test_generic(cmd+" -T --showpaths=n-a --list0=ok -f test"+f, cfv_listdata_test, stderr="/dev/null")
	test_generic(cmd+" -T --showpaths=a-a --list0=ok -f test"+f, cfv_listdata_test, stderr="/dev/null")
	test_generic(cmd+" -T --showpaths=2-a --list0=ok -f test"+f, cfv_listdata_test, stderr="/dev/null")
	test_generic(cmd+" -T --showpaths=y-r --list0=ok -f test"+f, cfv_listdata_test, stderr="/dev/null")
	test_generic(cmd+" -T --showpaths=y-a --list0=ok -f test"+f, cfv_listdata_abs_test, stderr="/dev/null")
	test_generic(cmd+" -T --showpaths=1-a --list0=ok -f test"+f, cfv_listdata_abs_test, stderr="/dev/null")
	#ensure all verbose stuff goes to stderr:
	test_generic(cmd+" -v -T --list0=ok -f test"+f, cfv_listdata_test, stderr="/dev/null")
	test_generic(cmd+" -v -T --list0=unverified -f test"+f+" test.py testfix.csv data1", cfv_listdata_unv_test, stderr="/dev/null")
	#test progress stuff.
	def progress_test(s,o):
		if cfv_test(s,o): return 1
		if o.find('.'*10)<0: return 2
		return 0
	def noprogress_test(s,o):
		if cfv_test(s,o): return 1
		if o.find('.'*10)>=0: return 2
		return 0
	if f.endswith('.csv2'): #csv2 has only filesize, hence checksum never happens, so no progress
		test_generic(cmd+" -T --progress=yes -f test"+f, noprogress_test)
	else:
		#test handling of COLUMNS env var #TODO: should actually check that the value is being respected...
		os.environ["COLUMNS"]="40"
		try:
			test_generic(cmd+" -T --progress=yes -f test"+f, progress_test)
			os.environ["COLUMNS"]="foobar"
			test_generic(cmd+" -T --progress=yes -f test"+f, progress_test)
		finally:
			del os.environ["COLUMNS"]
		test_generic(cmd+" -T --progress=yes -f test"+f, progress_test)
	test_generic(cmd+" -T --progress=auto -f test"+f, noprogress_test)
	test_generic(cmd+" -T --progress=no -f test"+f, noprogress_test)


def gzC_test(f,extra=None,verify=None,t=None,d=None):
	cmd=cfvcmd
	if not t:
		t=f
	f2='test.C.'+f+'.tmp.gz'
	f='test.C.'+f+'.gz'
	if extra:
		cmd=cmd+" "+extra
	try:
		test_generic("%s -q -C -t %s -zz -f - %s"%(cmd,t,d), status_test, stdout=f2)
		test_generic("%s -C -f %s %s"%(cmd,f,d),cfv_test)

		try:
			ifd1 = gzip.open(f)
			try:     if1 = ifd1.read()
			finally: ifd1.close()
		except (IOError,zlib.error), e:
			if1 = '%s: %s'%(f, e)
		try:
			ifd2 = gzip.open(f2)
			try:     if2 = ifd2.read()
			finally: ifd2.close()
		except (IOError,zlib.error), e:
			if2 = '%s: %s'%(f2, e)
		if t in ('sfv', 'sfvmd5'):
			commentre=re.compile("^; Generated by .* on .*$",re.M|re.I)
			if1 = commentre.sub('',if1,1)
			if2 = commentre.sub('',if2,1)
		elif t=='crc':
			commentre=re.compile("^Generated at: .*$",re.M|re.I)
			if1 = commentre.sub('',if1,1)
			if2 = commentre.sub('',if2,1)
		r = if1 != if2
		if r:
			o = "FILE1 %s:\n%s\nFILE2 %s:\n%s\n"%(f,if1,f2,if2)
		else:
			o = ''
		test_log_results('zcompare %s %s'%(f,f2),r,o,r, None)

		test_generic("%s -T -f %s"%(cmd,f),cfv_test)
		test_generic("%s -zz -T -f -"%(cmd),cfv_test,stdin=f)
		if verify:
			verify(f)
	finally:
		if os.path.exists(f2): os.unlink(f2)
		if os.path.exists(f): os.unlink(f)

def C_test(f,extra=None,verify=None,t=None,d='data?'):
	gzC_test(f,extra=extra,t=t,d=d)
	cmd=cfvcmd
	if not t:
		t=f
	cfv_stdin_test(cmd+" -t"+f+" -C -f-","data4")
	cfv_stdin_progress_test(f,'data4')
	f='test.C.'+f
	fgz=f+'.gz'
	try:
		if extra:
			cmd=cmd+" "+extra
		test_generic("%s -C -f %s %s"%(cmd,f,d),cfv_test)
		test_generic("%s -T -f %s"%(cmd,f),cfv_test)
		test_generic("%s -T -f -"%(cmd),cfv_test,stdin=f)
		of = gzip.open(fgz,mode='wb')
		of.write(open(f,'rb').read())
		of.close()
		test_generic("%s -zz -t%s -T -f -"%(cmd,t), cfv_test, stdin=fgz)
		if verify:
			verify(f)
	finally:
		os.unlink(f)
		os.unlink(fgz)

	dir='Ce.test'
	try:
		os.mkdir(dir)
		test_generic("%s -p %s -C -f %s"%(cmd,dir,f),rcurry(cfv_test,op_eq,0))
	finally:
		os.rmdir(dir)

def C_funkynames_test(t):
	d = mkdtemp()
	d2 = mkdtemp()
	try:
		num = 0
		for i in range(1,256):
			n = chr(i)
			if n in (os.sep, os.altsep, '\n', '\r'):
				continue
			if t == 'torrent' and n in ('/','\\'): continue # "ValueError: path \ disallowed for security reasons"
			if t == 'torrent' and n in ('~',): n = 'foo'+n #same
			if n == os.curdir: n = 'foo'+n # can't create a file of name '.', but 'foo.' is ok.
			if t in ('sfv','sfvmd5') and n==';': n = 'foo'+n # ';' is comment character in sfv files, filename cannot start with it.
			if t == 'crc' and n.isspace(): n = n + 'foo' # crc format can't handle trailing whitespace in filenames
			try:
				f = open(os.path.join(d,n),'wb')
				f.write(n)
				f.close()
				os.mkdir(os.path.join(d2,n))
				f = open(os.path.join(d2,n,n),'wb')
				f.write(n)
				f.close()
			except EnvironmentError:
				continue # stupid filesystem doesn't allow the character we wanted, oh well.
			num = num + 1
		cfn = os.path.join(d,'funky.'+t)
		test_generic(cfvcmd+" -v -C -p %s -t %s -f %s"%(d,t,cfn), rcurry(cfv_all_test,files=num,ok=num))
		test_generic(cfvcmd+" -v -T -p %s -f %s"%(d,cfn), rcurry(cfv_all_test,files=num,ok=num))
		test_generic(cfvcmd+" -v -u -T -p %s -f %s"%(d,cfn), rcurry(cfv_all_test,files=num,ok=num,unv=0))
		dcfn = os.path.join(d2,'funkydeep.'+t)
		test_generic(cfvcmd+" -v -rr -C -p %s -t %s -f %s"%(d2,t,dcfn), rcurry(cfv_all_test,files=num,ok=num))
		test_generic(cfvcmd+" -v -T -p %s -f %s"%(d2,dcfn), rcurry(cfv_all_test,files=num,ok=num))
		test_generic(cfvcmd+" -v -u -T -p %s -f %s"%(d2,dcfn), rcurry(cfv_all_test,files=num,ok=num,unv=0))
	finally:
		shutil.rmtree(d)
		shutil.rmtree(d2)

def ren_test(f,extra=None,verify=None,t=None):
	join=os.path.join
	dir='n.test'
	dir2=join('n.test','d2')
	basecmd=cfvcmd+' -r -p '+dir
	if extra:
		basecmd=basecmd+" "+extra
	cmd=basecmd+' --renameformat="%(name)s-%(count)i%(ext)s"'
	try:
		os.mkdir(dir)
		os.mkdir(dir2)
		fls=[join(dir,'test.ext.end'),
			join(dir,'test2.foo'),
			join(dir,'test3'),
			join(dir2,'test4.foo')]
		flsf=[join(dir,'test.ext-%i.end'),
			join(dir,'test2-%i.foo'),
			join(dir,'test3-%i'),
			join(dir2,'test4-%i.foo')]
		flsf_1=[join(dir,'test.ext.end-%i'),
			join(dir,'test2.foo-%i'),
			join(dir2,'test4.foo-%i')]
		flsf_2=[join(dir,'test3-%i')]
		def flsw(t,fls=fls):
			for fl in fls:
				open(fl,'wb').write(t)
		def flscmp(t,n,fls=flsf):
			for fl in fls:
				fn= n!=None and fl%n or fl
				try:
					o = open(fn,'rb').read()
					r = o!=t
				except IOError, e:
					r = 1
					o = str(e)
				test_log_results('cmp %s for %s'%(fn,t),r,o,r, None)
		flsw('hello')
		test_generic("%s -C -t %s"%(cmd,f),cfv_test)
		flsw('1')
		test_generic(basecmd+" --showpaths=0 -v -T --list0=bad",cfv_listdata_bad_test,stderr="/dev/null")
		test_generic(basecmd+" --showpaths=0 -q -T --list0=bad",cfv_listdata_bad_test)
		test_generic("%s -Tn"%(cmd),cfv_bad_test)
		flsw('11')
		test_generic("%s -Tn"%(cmd),cfv_bad_test)
		flsw('123')
		test_generic("%s -Tn"%(cmd),cfv_bad_test)
		flsw('63')
		test_generic(cmd+' --renameformat="%(fullname)s" -Tn',cfv_bad_test) #test for formats without count too
		flsw('hello')
		test_generic("%s -Tn"%(cmd),cfv_test)
		flscmp('1',0)
		flscmp('11',1)
		flscmp('123',2)
		flscmp('63',1,fls=flsf_1)
		flscmp('63',3,fls=flsf_2)
		flscmp('hello',None,fls=fls)
	finally:
		shutil.rmtree(dir)

def search_test(t,test_nocrc=0,extra=None):
	cfn = os.path.join(os.getcwd(), 'test.'+t)
	hassize = fmt_hassize(t)
	if test_nocrc:
		hascrc = 0
		cmd = cfvcmd+" -m"
	else:
		hascrc = fmt_hascrc(t)
		cmd = cfvcmd
	if extra:
		cmd = cmd + " " + extra
	
	if not hascrc and not hassize:
		# if using -m and type doesn't have size, make sure -s doesn't do anything silly
		d = mkdtemp()
		try:
			for n,n2 in zip(range(1,5),range(4,0,-1)):
				shutil.copyfile('data%s'%n, os.path.join(d,'fOoO%s'%n2))
			test_generic(cmd+" -v -T -p %s -f %s"%(d,cfn), rcurry(cfv_all_test,notfound=4))
			test_generic(cmd+" -v -s -T -p %s -f %s"%(d,cfn), rcurry(cfv_all_test,notfound=4))
			test_generic(cmd+" -v -s -n -T -p %s -f %s"%(d,cfn), rcurry(cfv_all_test,notfound=4))
			test_generic(cmd+" -v -s -u -T -p %s -f %s"%(d,cfn), rcurry(cfv_all_test,notfound=4,unv=4))
		finally:
			shutil.rmtree(d)
		# then return, since all the following tests would be impossible.
		return


	d = mkdtemp()
	try:
		def dont_find_same_file_twice_test(s,o):
			if not (o.count('fOoO3')==1 and o.count('fOoO4')==1):
				return str((o.count('fOoO3'), o.count('fOoO4')))
			return cfv_all_test(s,o,ok=4,misnamed=4)

		test_generic(cmd+" -v -s -T -p %s -f %s"%(d,cfn), rcurry(cfv_all_test,notfound=4))
		for n,n2 in zip(range(1,5),range(4,0,-1)):
			shutil.copyfile('data%s'%n, os.path.join(d,'fOoO%s'%n2))
		test_generic(cmd+" -v -T -p %s -f %s"%(d,cfn), rcurry(cfv_all_test,notfound=4))
		test_generic(cmd+" -v -s -T -p %s -f %s"%(d,cfn), dont_find_same_file_twice_test)
		test_generic(cmd+" -v -T -p %s -f %s"%(d,cfn), rcurry(cfv_all_test,notfound=4))
		test_generic(cmd+" -v -n -s -T -p %s -f %s"%(d,cfn), rcurry(cfv_all_test,ok=4,misnamed=4))
		test_generic(cmd+" -v -u -T -p %s -f %s"%(d,cfn), rcurry(cfv_all_test,ok=4))
	finally:
		shutil.rmtree(d)

	#the following tests two things:
	# 1) that it will copy/link to a file that is already OK rather than just renaming it again
	# 2) that it doesn't use the old cached value of a file's checksum before it got renamed out of the way.
	d = mkdtemp()
	try:
		misnamed1=misnamed2=4
		if hassize and hascrc:
			experrs={'badcrc':1,'badsize':2}
		elif hassize:
			experrs={'badsize':2, 'ok':1}
			misnamed1=3
			misnamed2=OneOf(3,4) #this depends on what order os.listdir finds stuff. (could be 3 or 4)
		else:#if hascrc:
			experrs={'badcrc':3}

		test_generic(cmd+" -v -s -T -p %s -f %s"%(d,cfn), rcurry(cfv_all_test,notfound=4))
		for n,n2 in zip([1,3,4],[4,2,1]):
			shutil.copyfile('data%s'%n, os.path.join(d,'data%s'%n2))
		test_generic(cmd+" -v -T -p %s -f %s"%(d,cfn), rcurry(cfv_all_test,notfound=1,**experrs))
		test_generic(cmd+" -v -s -T -p %s -f %s"%(d,cfn), rcurry(cfv_all_test,ok=4,misnamed=misnamed1))
		test_generic(cmd+" -v -T -p %s -f %s"%(d,cfn), rcurry(cfv_all_test,notfound=1,**experrs))
		test_generic(cmd+" -v -n -s -T -p %s -f %s"%(d,cfn), rcurry(cfv_all_test,ok=4,misnamed=misnamed2))
		test_generic(cmd+" -v -u -T -p %s -f %s"%(d,cfn), rcurry(cfv_all_test,ok=4))
	finally:
		shutil.rmtree(d)
	
	#test whether ferrors during searching are ignored
	if hasattr(os, 'symlink'):
		d = mkdtemp()
		try:
			for n,n2 in zip([4],[2]):
				shutil.copyfile('data%s'%n, os.path.join(d,'foo%s'%n2))
			for n in string.lowercase:
				os.symlink('noexist', os.path.join(d,n))
			test_generic(cmd+" -v -s -T -p %s -f %s"%(d,cfn), rcurry(cfv_all_test,ok=1,misnamed=1,notfound=3))
			test_generic(cmd+" -v -T -p %s -f %s"%(d,cfn), rcurry(cfv_all_test,notfound=4))
			test_generic(cmd+" -v -n -s -T -p %s -f %s"%(d,cfn), rcurry(cfv_all_test,ok=1,misnamed=1,notfound=3))
			test_generic(cmd+" -v -T -p %s -f %s"%(d,cfn), rcurry(cfv_all_test,ok=1,notfound=3))
		finally:
			shutil.rmtree(d)

	#test if an error while renaming a misnamed file is properly handled
	d = mkdtemp()
	ffoo = fdata4 = None
	try:
		ffoo=writefile_and_reopen(os.path.join(d,'foo'), open('data4','rb').read())
		#note that we leave the file open.  This is because windows allows renaming of files in a readonly dir, but doesn't allow renaming of open files.  So if we do both the test will work on both nix and win.
		os.chmod(d,stat.S_IRUSR|stat.S_IXUSR)
		try:
			os.rename(os.path.join(d,'foo'),os.path.join(d,'foo2'))
			print 'rename of open file in read-only dir worked?  skipping this test.'
		except EnvironmentError:
			# if the rename failed, then we're good to go for these tests..
			test_generic(cmd+" -v -n -s -T -p %s -f %s"%(d,cfn), rcurry(cfv_all_test,files=4,ok=1,misnamed=1,ferror=1,notfound=3))
			os.chmod(d,stat.S_IRWXU)
			fdata4=writefile_and_reopen(os.path.join(d,'data4'),'')
			os.chmod(d,stat.S_IRUSR|stat.S_IXUSR)
			test_generic(cmd+" -v -n -s -T -p %s -f %s"%(d,cfn), rcurry(cfv_all_test,files=4,ok=1,misnamed=1,ferror=2,notfound=3))
	finally:
		os.chmod(d,stat.S_IRWXU)
		if ffoo: ffoo.close()
		if fdata4: fdata4.close()
		shutil.rmtree(d)

	#test if misnamed stuff and/or renaming stuff doesn't screw up the unverified file checking
	d = mkdtemp()
	try:
		shutil.copyfile('data4', os.path.join(d,'foo'))
		test_generic(cmd+" -v -uu -s -T -p %s -f %s"%(d,cfn), rcurry(cfv_all_test,files=4,ok=1,misnamed=1,notfound=3,unv=0))
		test_generic(cmd+" -v -uu -s -n -T -p %s -f %s"%(d,cfn), rcurry(cfv_all_test,files=4,ok=1,misnamed=1,notfound=3,unv=0))
		
		open(os.path.join(d,'data1'),'w').close()
		if hassize: experrs={'badsize':1}
		else:              experrs={'badcrc':1}
		test_generic(cmd+" -v -uu -s -T -p %s -f %s"%(d,cfn), rcurry(cfv_all_test,files=4,ok=1,misnamed=0,notfound=2,unv=0,**experrs))
		test_generic(cmd+" -v -uu -s -n -T -p %s -f %s"%(d,cfn), rcurry(cfv_all_test,files=4,ok=1,misnamed=0,notfound=2,unv=1,**experrs))
	finally:
		shutil.rmtree(d)

	if fmt_cancreate(t):
		#test deep handling
		d = mkdtemp()
		try:
			dcfn = os.path.join(d,'deep.'+t)
			os.mkdir(os.path.join(d, "aOeU.AoEu"))
			os.mkdir(os.path.join(d, "aOeU.AoEu", "boO.FaRr"))
			shutil.copyfile('data1', os.path.join(d, "aOeU.AoEu", "boO.FaRr", "DaTa1"))
			test_generic(cmd+" -v -rr -C -p %s -t %s -f %s"%(d,t,dcfn), rcurry(cfv_all_test,files=1,ok=1))
			os.rename(os.path.join(d, "aOeU.AoEu", "boO.FaRr", "DaTa1"), os.path.join(d, "aOeU.AoEu", "boO.FaRr", "Foo1"))
			shutil.copyfile('data4', os.path.join(d, "aOeU.AoEu", "boO.FaRr", "DaTa1"))
			test_generic(cmd+" -v -s -T -p %s -f %s"%(d,dcfn), rcurry(cfv_all_test,files=1,ok=1,misnamed=1))
			shutil.rmtree(os.path.join(d, "aOeU.AoEu"))
			os.mkdir(os.path.join(d, "AoEu.aOeU"))
			os.mkdir(os.path.join(d, "AoEu.aOeU", "BOo.fArR"))
			shutil.copyfile('data4', os.path.join(d, "AoEu.aOeU", "BOo.fArR","dAtA1"))
			shutil.copyfile('data1', os.path.join(d, "AoEu.aOeU", "BOo.fArR","Foo1"))
			test_generic(cmd+" -i -v -s -T -p %s -f %s"%(d,dcfn), rcurry(cfv_all_test,files=1,ok=1,misnamed=1))
			if hassize: experrs={'badsize':1}
			else:              experrs={'badcrc':1}
			test_generic(cmd+" -i -v -T -p %s -f %s"%(d,dcfn), rcurry(cfv_all_test,files=1,ok=0,**experrs))
			test_generic(cmd+" -i -v -s -n -T -p %s -f %s"%(d,dcfn), rcurry(cfv_all_test,files=1,ok=1,misnamed=1))
			test_generic(cmd+" -i -v -T -p %s -f %s"%(d,dcfn), rcurry(cfv_all_test,files=1,ok=1))
		finally:
			shutil.rmtree(d)

	if fmt_cancreate(t) and hassize:
		d = mkdtemp()
		try:
			dcfn = os.path.join(d,'foo.'+t)
			os.mkdir(os.path.join(d, "aoeu"))
			dirsize = os.path.getsize(os.path.join(d, "aoeu"))
			f=open(os.path.join(d,"idth"),'wb'); f.write('a'*dirsize); f.close()
			test_generic(cmd+" -v -C -p %s -t %s -f %s"%(d,t,dcfn), rcurry(cfv_all_test,files=1,ok=1))
			os.remove(os.path.join(d,"idth"))
			os.rename(os.path.join(d,"aoeu"), os.path.join(d,'idth'))
			def dont_find_dir_test(s,o):
				if not o.count('idth')==1:
					return str((o.count('idth'),))
				return cfv_all_test(s,o,ok=0,notfound=1)
			test_generic(cmd+" -v -m -T -p %s -f %s"%(d,dcfn), dont_find_dir_test) # test not finding non-file things in normal mode
			test_generic(cmd+" -v -m -s -T -p %s -f %s"%(d,dcfn), dont_find_dir_test) # test not finding non-file things in search mode
		finally:
			shutil.rmtree(d)

def quoted_search_test():
	d = mkdtemp()
	try:
		join = os.path.join
		f = open(join(d,'foo.sfv'),'w')
		f.write(r""""data1" B2A9E441
"/data4" FA323C6D
"aa1/data1" B2A9E441
"c:/aa1/data4" FA323C6D
"aa3/data3" 841ADFA2
"\aa3\data4" FA323C6D
"c:\aa4\bb4\data1" B2A9E441
"aa4/bb4/data4" FA323C6D""")
		f.close()
		shutil.copyfile('data1', pathjoin_and_mkdir(d, "foo1"))
		shutil.copyfile('data4', pathjoin_and_mkdir(d, "foo4"))
		shutil.copyfile('data1', pathjoin_and_mkdir(d, "aa1", "foo1"))
		shutil.copyfile('data4', pathjoin_and_mkdir(d, "aa1", "foo4"))
		shutil.copyfile('data3', pathjoin_and_mkdir(d, "aa3", "foo3"))
		shutil.copyfile('data4', pathjoin_and_mkdir(d, "aa3", "foo4"))
		shutil.copyfile('data1', pathjoin_and_mkdir(d, "aa4","bb4", "foo1"))
		shutil.copyfile('data4', pathjoin_and_mkdir(d, "aa4","bb4", "foo4"))
		test_generic(cfvcmd+r" -v --unquote=yes --strippaths=0 --fixpaths \\/ -s -T -p "+d,rcurry(cfv_all_test,ok=8,misnamed=8))
	finally:
		shutil.rmtree(d)

def symlink_test():
	dir='s.test'
	dir1='d1'
	dir2='d2'
	try:
		os.mkdir(dir)
		os.mkdir(os.path.join(dir, dir1))
		os.mkdir(os.path.join(dir, dir2))
		if hasattr(os, 'symlink'):
			os.symlink(os.path.join(os.pardir, dir2), os.path.join(dir, dir1, 'l2'))
			os.symlink(os.path.join(os.pardir, dir1), os.path.join(dir, dir2, 'l1'))
			test_generic(cfvcmd+" -l -r -p "+dir, rcurry(cfv_test,op_eq,0))
			test_generic(cfvcmd+" -L -r -p "+dir, rcurry(cfv_test,op_eq,0))
			test_generic(cfvcmd+" -l -r -C -p "+dir, rcurry(cfv_test,op_eq,0))
			test_generic(cfvcmd+" -L -r -C -p "+dir, rcurry(cfv_test,op_eq,0))

		open(os.path.join(dir,dir1,'foo'),'w').close()
		open(os.path.join(dir,dir2,'bar'),'w').close()
		def r_unv_test(s,o):
			if cfv_unvonly_test(s,o,2): return 1
			if string.count(o,'not verified')!=1: return 1
			return 0
		test_generic(cfvcmd+" -l -r -u -p "+dir, r_unv_test)
		test_generic(cfvcmd+" -L -r -u -p "+dir, r_unv_test)
		test_generic(cfvcmd+" -l -u -p "+dir, r_unv_test)
		test_generic(cfvcmd+" -L -u -p "+dir, r_unv_test)
		def r_unv_verbose_test(s,o):
			if cfv_unvonly_test(s,o,2): return 1
			if string.count(o,'not verified')!=2: return 1
			return 0
		test_generic(cfvcmd+" -l -uu -p "+dir, r_unv_verbose_test)
		test_generic(cfvcmd+" -L -uu -p "+dir, r_unv_verbose_test)
		test_generic(cfvcmd+" -l -r -uu -p "+dir, r_unv_verbose_test)
		test_generic(cfvcmd+" -L -r -uu -p "+dir, r_unv_verbose_test)
	finally:
		shutil.rmtree(dir)

def deep_unverified_test():
	dir='dunv.test'
	try:
		join = os.path.join
		os.mkdir(dir)
		a = 'a'
		a_C = join(a, 'C')
		B = 'B'
		B_ushallow = join(B,'ushallow')
		B_ushallow_d = join(B_ushallow, 'd')
		u = 'u'
		u_u2 = join(u, 'u2')
		e = 'e'
		e_es = join(e, 'es')
		e2 = 'e2'
		e2_e2s = join(e2, 'e2s')
		e2_e2u = join(e2, 'e2u')
		
		for d in a, a_C, B, B_ushallow, B_ushallow_d, u, u_u2, e, e_es, e2, e2_e2s, e2_e2u:
			os.mkdir(join(dir,d))
		datafns = ('DATa1', 'UnV1',
				join(a,'dAta2'), join(a, 'Unv2'), join(a_C,'dATa4'), join(a_C,'unV4'),
				join(B,'daTA3'), join(B,'uNv3'),
				join(B_ushallow,'uNvs'), join(B_ushallow_d,'unvP'), join(B_ushallow_d,'datA5'),
				join(u,'uNVu'), join(u,'UnvY'), join(u_u2,'UNVX'),
				join(e2_e2s,'DaTaE'),join(e2_e2u,'unVe2'),)
		lower_datafns = map(string.lower, datafns)
		for fn in datafns:
			open(join(dir,fn),'w').close()
		f = open(join(dir,'deep.md5'),'w')
		f.write("""d41d8cd98f00b204e9800998ecf8427e *b/DaTa3
d41d8cd98f00b204e9800998ecf8427e *B/ushAllOw/D/daTa5
d41d8cd98f00b204e9800998ecf8427e *a/c/DatA4
d41d8cd98f00b204e9800998ecf8427e *A/dATA2
d41d8cd98f00b204e9800998ecf8427e *E2/e2S/DAtae
d41d8cd98f00b204e9800998ecf8427e *daTA1""")
		f.close()
			
		def r_test(s,o):
			if cfv_test(s,o,op_eq,6): return 1
			if string.count(o,'not verified')!=0: return 1
			return 0
		def r_unv_test(s,o):
			if cfv_unvonly_test(s,o,10): return 1
			if string.count(o,'not verified')!=8: return 1
			if string.find(o,os.path.join('e','*'))>=0: return 1
			if string.find(o,os.path.join('e2','*'))>=0: return 1
			return 0
		def r_unv_verbose_test(s,o):
			if cfv_unvonly_test(s,o,10): return 1
			if string.count(o,'not verified')!=10: return 1
			if string.find(o,'*')>=0: return 1
			return 0
		test_generic(cfvcmd+" -i -U -p "+dir, r_test)
		test_generic(cfvcmd+" -i -u -p "+dir, r_unv_test)
		test_generic(cfvcmd+" -i -uu -p "+dir, r_unv_verbose_test)
		test_generic(cfvcmd+" -i -U -p "+dir+" "+' '.join(lower_datafns), r_test)
		test_generic(cfvcmd+" -i -u -p "+dir+" "+' '.join(lower_datafns), r_unv_verbose_test)
		test_generic(cfvcmd+" -i -uu -p "+dir+" "+' '.join(lower_datafns), r_unv_verbose_test)
	finally:
		shutil.rmtree(dir)


def test_encoding2():
	"""Non-trivial (actual non-ascii characters) encoding test.
	These tests will probably always fail unless you use a unicode locale and python 2.3+."""
	if not BitTorrent:
		return
	d = mkdtemp()
	d2 = mkdtemp()
	try:
		cfn = os.path.join(d,u'\u3070\u304B.torrent')
		shutil.copyfile('testencoding2.torrent.foo', cfn)
		
		datafns = [
			('data1',u'\u2605'),
			('data2',u'\u2606'),
			('data3',u'\u262E'),
			('data4',u'\u2600'),
		]
		fnerrs=fnok=0
		for srcfn,destfn in datafns:
			try:
				shutil.copyfile(srcfn, os.path.join(d2,destfn))
			except (EnvironmentError,UnicodeError):
				fnerrs=fnerrs+1
			else:
				fnok=fnok+1
		
		test_generic(cfvcmd+" -q -T -p "+d, rcurry(cfv_status_test,notfound=fnok,ferror=fnerrs))
		test_generic(cfvcmd+" -v -T -p "+d, rcurry(cfv_all_test,ok=0,notfound=fnok,ferror=fnerrs))
		bakad = os.path.join(d,u'\u3070\u304B')
		os.mkdir(bakad)
		for srcfn,destfn in datafns:
			try:
				shutil.copyfile(srcfn, os.path.join(bakad,destfn))
			except (EnvironmentError,UnicodeError):
				pass
		test_generic(cfvcmd+" -q -m -T -p "+d, rcurry(cfv_status_test,ferror=fnerrs))
		test_generic(cfvcmd+" -v -m -T -p "+d, rcurry(cfv_all_test,ok=fnok,ferror=fnerrs))
		if not fnerrs:
			#if some of the files can't be found, checking of remaining files will fail due to missing pieces
			test_generic(cfvcmd+" -q -T -p "+d, rcurry(cfv_status_test))
			test_generic(cfvcmd+" -v -T -p "+d, rcurry(cfv_all_test,ok=4))
	except:
		import traceback
		test_log_results('test_encoding2','foobar',''.join(traceback.format_exception(*sys.exc_info())),'foobar',{}) #yuck.  I really should switch this crap all to unittest ...
	#finally:
	shutil.rmtree(unicode(d2))
	shutil.rmtree(unicode(d))
	

def largefile2GB_test():
	# hope you have sparse file support ;)
	fn = os.path.join('bigfile2','bigfile')
	f = open(fn,'wb')
	try:
		f.write('hi')
		f.seek(2**30)
		f.write('foo')
		f.seek(2**31)
		f.write('bar')
		f.close()
		test_generic(cfvcmd+" -v -T -p %s"%('bigfile2'), rcurry(cfv_all_test,ok=6))
	finally:
		os.unlink(fn)

def largefile4GB_test():
	# hope you have sparse file support ;)
	fn = os.path.join('bigfile','bigfile')
	f = open(fn,'wb')
	try:
		f.write('hi')
		f.seek(2**30)
		f.write('foo')
		f.seek(2**31)
		f.write('bar')
		f.seek(2**32)
		f.write('baz')
		f.close()
		test_generic(cfvcmd+" -v -T -p %s"%('bigfile'), rcurry(cfv_all_test,ok=10))
	finally:
		os.unlink(fn)


def manyfiles_test(t):
	try:
		max_open = os.sysconf('SC_OPEN_MAX')
	except (AttributeError, ValueError, OSError):
		max_open = 1024
	if not run_long_tests and max_open > 4096:
		print 'max open files is big (%i)'%max_open,
		max_open = 4096
		print 'clipping to %i.  Use --full to try the real value'%max_open
	num = max_open + 1
	d = mkdtemp()
	try:
		for i in range(0,num):
			n = '%04i'%i
			f = open(os.path.join(d, n), 'w')
			f.write(n)
			f.close()
		cfn = os.path.join(d,'manyfiles.'+t)
		test_generic(cfvcmd+" -C -p %s -t %s -f %s"%(d,t,cfn), rcurry(cfv_all_test,ok=num))
		test_generic(cfvcmd+" -T -p %s -f %s"%(d,cfn), rcurry(cfv_all_test,ok=num))
	finally:
		shutil.rmtree(d)

def specialfile_test(cfpath):
	if run_internal and ver_fchksum: #current versions of fchksum don't release the GIL, so this deadlocks if doing internal testing and using fchksum.
		return
	try:
		import threading
	except ImportError:
		return
	d = mkdtemp()
	cfn = os.path.split(cfpath)[1]
	try:
		fpath = os.path.join(d,'foo.bar')
		try:
			os.mkfifo(fpath)
		except (AttributeError, EnvironmentError):
			return
		shutil.copyfile(cfpath, os.path.join(d, cfn))
		def pusher(fpath):
			f=open(fpath,'wb')
			f.write('a'*0x4000)
			f.flush()
			time.sleep(0.1)
			f.write('b'*0x4000)
			f.flush()
			time.sleep(0.1)
			f.write('c'*0x4000)
			f.close()
		t=threading.Thread(target=pusher,args=(fpath,))
		t.start()
		s,o=runcfv("%s --progress=yes -T -p %s -f %s"%(cfvcmd,d,cfn))
		t.join()
		r=0
		if s:
			r=1
		elif o.count('#')>1:
			r='count(#) = %s'%(o.count('#'))
		elif o.count('..'):
			r=3
		test_log_results('specialfile_test(%s)'%cfn,s,o,r,None)
	finally:
		shutil.rmtree(d)
	

def private_torrent_test():
	cmd=cfvcmd
	tmpd = mkdtemp()
	try:
		needle = '7:privatei1'
		f = os.path.join(tmpd, 'test.torrent')
		test_generic("%s -C -f %s data1"%(cmd,f),cfv_test)
		data = readfile(f)
		test_log_results('should not contain private flag', 0, repr(data), needle in data, None)

		f = os.path.join(tmpd, 'test2.torrent')
		test_generic("%s --private_torrent -C -f %s data1"%(cmd,f),cfv_test)
		data = readfile(f)
		test_log_results('should contain private flag', 0, repr(data), needle not in data, None)
	finally:
		shutil.rmtree(tmpd)


cfvenv=''
cfvexe=os.path.join(os.pardir,'cfv')
run_internal = 1
run_long_tests = 0

def show_help_and_exit(err=None):
	if err:
		print 'error:',err
		print
	print 'usage: test.py [-i|-e] [--full] [cfv]'
	print ' -i      run tests internally'
	print ' -e      launch seperate cfv process for each test'
	print ' --long  include tests that may use large amounts of CPU or disk'
	print ' --help  show this help'
	print
	print 'default [cfv] is:', cfvexe
	print 'default run mode is:', run_internal and 'internal' or 'external'
	sys.exit(1)

try:
	optlist, args = getopt.getopt(sys.argv[1:], 'ie',['long','help'])
except getopt.error, e:
	show_help_and_exit(e)

if len(args)>1:
	show_help_and_exit("too many arguments")

for o,a in optlist:
	if o=='--help':
		show_help_and_exit()
	elif o=='--long':
		run_long_tests = 1
	elif o=='-i':
		run_internal = 1
	elif o=='-e':
		run_internal = 0
	else:
		show_help_and_exit("bad opt %r"%o)

if args:
	cfvexe=args[0]

#set everything to default in case user has different in config file
cfvcmd='-ZNVRMUI --unquote=no --fixpaths="" --strippaths=0 --showpaths=auto-relative --progress=no --announceurl=url --noprivate_torrent'

if run_internal:
	runcfv = runcfv_py
	_cfv_code = open(cfvexe,'r').read().replace('\r\n','\n').replace('\r','\n')
	cfv_compiled = compile(_cfv_code,cfvexe,'exec')
else:
	runcfv = runcfv_exe

logfile=open("test.log","w")

def all_tests():
	stats.ok = stats.failed = 0

	symlink_test()
	deep_unverified_test()
	
	ren_test('sha1')
	ren_test('md5')
	ren_test('md5',extra='-rr')
	ren_test('bsdmd5')
	ren_test('sfv')
	ren_test('sfvmd5')
	ren_test('csv')
	ren_test('csv2')
	ren_test('csv4')
	ren_test('crc')
	if BitTorrent:
		ren_test('torrent')

	for t in 'sha1', 'md5', 'bsdmd5', 'sfv', 'sfvmd5', 'csv', 'csv2', 'csv4', 'crc', 'par', 'par2':
		search_test(t)
		search_test(t,test_nocrc=1)
	if BitTorrent:
		search_test('torrent',test_nocrc=1)
		#search_test('torrent',test_nocrc=1,extra="--strip=1")
	quoted_search_test()

	T_test(".sha1")
	T_test(".md5")
	T_test(".md5.gz")
	T_test("comments.md5")
	T_test(".bsdmd5")
	#test par spec 1.0 files:
	T_test(".par")
	T_test(".p01")
	#test par spec 0.9 files:
	T_test("v09.par")
	T_test("v09.p01")
	T_test(".par2")
	T_test(".vol0+1.par2")
	T_test(".csv")
	T_test(".sfv")
	T_test("noheader.sfv")
	T_test(".sfvmd5")
	T_test(".csv2")
	T_test(".csv4")
	T_test(".crc")
	T_test("nosize.crc")
	T_test("nodims.crc")
	T_test("nosizenodimsnodesc.crc")
	T_test("crlf.sha1")
	T_test("crlf.md5")
	T_test("crlf.bsdmd5")
	T_test("crlf.csv")
	T_test("crlf.csv2")
	T_test("crlf.csv4")
	T_test("crlf.sfv")
	T_test("noheadercrlf.sfv")
	T_test("crlf.crc")
	T_test("crcrlf.sha1")
	T_test("crcrlf.md5")
	T_test("crcrlf.bsdmd5")
	T_test("crcrlf.csv")
	T_test("crcrlf.csv2")
	T_test("crcrlf.csv4")
	T_test("crcrlf.sfv")
	T_test("noheadercrcrlf.sfv")
	T_test("crcrlf.crc")
	if BitTorrent:
		for strip in (0,1):
			T_test(".torrent",extra='--strip=%s'%strip)
			T_test("smallpiece.torrent",extra='--strip=%s'%strip)
			T_test("encoding.torrent",extra='--strip=%s'%strip)
		test_encoding2()

	#test handling of directory args in recursive testmode. (Disabled since this isn't implemented, and I'm not sure if it should be.  It would change the meaning of cfv *)
	#test_generic(cfvcmd+" -r a",cfv_test)
	#test_generic(cfvcmd+" -ri a",cfv_test)
	#test_generic(cfvcmd+" -ri A",cfv_test)
	#test_generic(cfvcmd+" -rm a",cfv_test)
	#test_generic(cfvcmd+" -rim a",cfv_test)
	#test_generic(cfvcmd+" -r a/C",cfv_test)
	#test_generic(cfvcmd+" -ri A/c",cfv_test)

	#test handling of testfile args in recursive testmode
	test_generic(cfvcmd+" -r -p a "+os.path.join("C","foo.bar"),cfv_test)
	test_generic(cfvcmd+" -ri -p a "+os.path.join("c","fOo.BaR"),cfv_test)
	test_generic(cfvcmd+" -r -u -p a "+os.path.join("C","foo.bar"),cfv_test)
	test_generic(cfvcmd+" -ri -u -p a "+os.path.join("c","fOo.BaR"),cfv_test)
	
	test_generic(cfvcmd+" --strippaths=0 -T -f teststrip0.csv4",cfv_test)
	test_generic(cfvcmd+" --strippaths=1 -T -f teststrip1.csv4",cfv_test)
	test_generic(cfvcmd+" --strippaths=2 -T -f teststrip2.csv4",cfv_test)
	test_generic(cfvcmd+" --strippaths=all -T -f teststrip-1.csv4",cfv_test)
	test_generic(cfvcmd+" --strippaths=none -T -f teststrip-none.csv4",cfv_notfound_test)
	test_generic(cfvcmd+r" --strippaths=0 --fixpaths \\/ -T -f testdrivestrip.md5",rcurry(cfv_all_test,ok=4))
	test_generic(cfvcmd+r" --strippaths=0 --unquote=yes --fixpaths \\/ -T -f testdrivestripquoted.md5",rcurry(cfv_all_test,ok=4))
	test_generic(cfvcmd+r" --strippaths=0 --unquote=yes --fixpaths \\/ -T -f testdrivestripquoted.md5 data1 data3 data4",rcurry(cfv_all_test,ok=3))

	test_generic(cfvcmd+" -i -T -f testcase.csv",cfv_test)
	test_generic(cfvcmd+" -T --unquote=yes -f testquoted.sfv",cfv_test)
	test_generic(cfvcmd+" -i --unquote=yes -T -f testquotedcase.sfv",cfv_test)
	test_generic(cfvcmd+" -i --unquote=yes -T -f testquotedcase.sfv DaTa1 "+os.path.join('a','C','Foo.bar'),rcurry(cfv_all_test,ok=2))
	test_generic(cfvcmd+" -i -T -f testquoted.csv4",cfv_test)
	test_generic(cfvcmd+r" --fixpaths \\/ -T -f testfix.csv",cfv_test)
	test_generic(cfvcmd+r" --fixpaths \\/ -T -f testfix.csv4",cfv_test)
	test_generic(cfvcmd+r" -i --fixpaths \\/ -T -f testfix.csv4",cfv_test)

	C_test("bsdmd5","-t bsdmd5")#,verify=lambda f: test_generic("md5 -c "+f,status_test)) #bsd md5 seems to have no way to check, only create
	if pathfind('sha1sum'): #don't report pointless errors on systems that don't have sha1sum
		sha1verify=lambda f: test_external("sha1sum -c "+f,status_test)
	else:
		sha1verify=None
	C_test("sha1",verify=sha1verify)
	if pathfind('md5sum'): #don't report pointless errors on systems that don't have md5sum
		md5verify=lambda f: test_external("md5sum -c "+f,status_test)
	else:
		md5verify=None
	C_test("md5",verify=md5verify)
	C_test("csv")
	if pathfind('cksfv'): #don't report pointless errors on systems that don't have cksfv
		sfvverify=lambda f: test_external("cksfv -f "+f,status_test)
	else:
		sfvverify=None
	C_test("sfv",verify=sfvverify)
	C_test("sfvmd5","-t sfvmd5")
	C_test("csv2","-t csv2")
	C_test("csv4","-t csv4")
	C_test("crc")
	private_torrent_test()
	#test_generic("../cfv -V -T -f test.md5",cfv_test)
	#test_generic("../cfv -V -tcsv -T -f test.md5",cfv_test)
	for t in allfmts():
		if fmt_cancreate(t) and fmt_available(t):
			C_funkynames_test(t)
			manyfiles_test(t)
	for fn in glob(os.path.join('fifotest','fifo.*')):
		specialfile_test(fn)

	test_generic(cfvcmd+" -m -v -T -t sfv", lambda s,o: cfv_typerestrict_test(s,o,'sfv'))
	test_generic(cfvcmd+" -m -v -T -t sfvmd5", lambda s,o: cfv_typerestrict_test(s,o,'sfvmd5'))
	test_generic(cfvcmd+" -m -v -T -t bsdmd5", lambda s,o: cfv_typerestrict_test(s,o,'bsdmd5'))
	test_generic(cfvcmd+" -m -v -T -t sha1", lambda s,o: cfv_typerestrict_test(s,o,'sha1'))
	test_generic(cfvcmd+" -m -v -T -t md5", lambda s,o: cfv_typerestrict_test(s,o,'md5'))
	test_generic(cfvcmd+" -m -v -T -t csv", lambda s,o: cfv_typerestrict_test(s,o,'csv'))
	test_generic(cfvcmd+" -m -v -T -t par", lambda s,o: cfv_typerestrict_test(s,o,'par'))
	test_generic(cfvcmd+" -m -v -T -t par2", lambda s,o: cfv_typerestrict_test(s,o,'par2'))

	test_generic(cfvcmd+" -u -t md5 -f test.md5 data* test.py test.md5",cfv_unv_test)
	test_generic(cfvcmd+" -u -f test.md5 data* test.py",cfv_unv_test)
	test_generic(cfvcmd+" -u -f test.md5 data* test.py test.md5",cfv_unv_test)
	test_generic(cfvcmd+r" -i -tcsv --fixpaths \\/ -Tu",lambda s,o: cfv_unv_test(s,o,None))
	test_generic(cfvcmd+" -T -t md5 -f non_existant_file",cfv_cferror_test)
	test_generic(cfvcmd+" -T -f "+os.path.join("corrupt","missingfiledesc.par2"),cfv_cferror_test)
	test_generic(cfvcmd+" -T -f "+os.path.join("corrupt","missingmain.par2"),cfv_cferror_test)
	test_generic(cfvcmd+" -T -m -f "+os.path.join("corrupt","missingfiledesc.par2"),cfv_cferror_test)
	test_generic(cfvcmd+" -T -m -f "+os.path.join("corrupt","missingmain.par2"),cfv_cferror_test)

	if BitTorrent:
		test_generic(cfvcmd+" -T -f foo.torrent",cfv_test)
		test_generic(cfvcmd+" -T --strip=none -p foo -f ../foo.torrent",rcurry(cfv_all_test,notfound=7))
		for strip in (0,1):
			test_generic(cfvcmd+" -T --strippaths=%s -p foo -f %s"%(strip,os.path.join(os.pardir,"foo.torrent")),rcurry(cfv_all_test,ok=7))
			test_generic(cfvcmd+" -T --strippaths=%s -p foo2err -f %s"%(strip,os.path.join(os.pardir,"foo.torrent")), rcurry(cfv_all_test,ok=4,badcrc=3))
			test_generic(cfvcmd+" -T --strippaths=%s -p foo2err -f %s foo1 foo4"%(strip,os.path.join(os.pardir,"foo.torrent")), rcurry(cfv_all_test,ok=0,badcrc=2))
			test_generic(cfvcmd+" -T --strippaths=%s -p foo2err1 -f %s"%(strip,os.path.join(os.pardir,"foo.torrent")), rcurry(cfv_all_test,ok=6,badcrc=1))
			test_generic(cfvcmd+" -T --strippaths=%s -p foo2err1 -f %s foo1 foo4"%(strip,os.path.join(os.pardir,"foo.torrent")), rcurry(cfv_all_test,ok=2))
			test_generic(cfvcmd+" -T --strippaths=%s -p foo2badsize -f %s"%(strip,os.path.join(os.pardir,"foo.torrent")), rcurry(cfv_all_test,ok=5,badsize=1,badcrc=1))
			test_generic(cfvcmd+" -T --strippaths=%s -p foo2badsize -f %s foo1 foo4"%(strip,os.path.join(os.pardir,"foo.torrent")), rcurry(cfv_all_test,ok=1,badcrc=1))
			test_generic(cfvcmd+" -T --strippaths=%s -p foo2missing -f %s"%(strip,os.path.join(os.pardir,"foo.torrent")), rcurry(cfv_all_test,ok=4,badcrc=2,notfound=1))
			test_generic(cfvcmd+" -T --strippaths=%s -p foo2missing -f %s foo1 foo4"%(strip,os.path.join(os.pardir,"foo.torrent")), rcurry(cfv_all_test,ok=0,badcrc=2))
		d = mkdtemp()
		try:
			open(os.path.join(d,'foo'),'w').close()
			cmd = cfvcmd.replace(' --announceurl=url','')
			test_generic(cmd+" -C -p %s -f foo.torrent"%d,rcurry(cfv_all_test,files=1,cferror=1))
			test_log_results("non-creation of empty torrent on missing announceurl?",'',repr(os.listdir(d)),len(os.listdir(d))>1,{})
		finally:
			shutil.rmtree(d)

	if run_long_tests:
		largefile2GB_test()
		largefile4GB_test()
	
	test_generic(cfvcmd+" -t aoeu",rcurry(cfv_cftypehelp_test,1),stdout='/dev/null')
	test_generic(cfvcmd+" -t aoeu",rcurry(cfv_nooutput_test,1),stderr='/dev/null')
	test_generic(cfvcmd+" -t help",rcurry(cfv_cftypehelp_test,0),stderr='/dev/null')
	test_generic(cfvcmd+" -t help",rcurry(cfv_nooutput_test,0),stdout='/dev/null')

	test_generic(cfvcmd+" -h",cfv_nooutput_test,stdout='/dev/null')
	test_generic(cfvcmd+" -h",cfv_version_test,stderr='/dev/null')

	donestr="tests finished:  ok: %i  failed: %i"%(stats.ok,stats.failed)
	log("\n"+donestr)
	print donestr

print 'testing...'
get_version_flags()
all_tests()
if ver_fchksum:
	print 'testing without fchksum...'
	cfvenv="CFV_NOFCHKSUM=x "+cfvenv
	os.environ["CFV_NOFCHKSUM"]="x"
	get_version_flags()
	all_tests()
if ver_mmap:
	print 'testing without mmap...'
	cfvenv="CFV_NOMMAP=x "+cfvenv
	os.environ["CFV_NOMMAP"]="x"
	get_version_flags()
	all_tests()

