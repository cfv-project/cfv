#! /usr/bin/env python

import commands,re,os;

class stats:
	ok=0
	failed=0

def logr(text):
	logfile.write(text);
def log(text):
	logr(text+"\n");

def test_generic(cmd,test):
	global stats
	log("*** testing "+cmd);
	s,o=commands.getstatusoutput(cmd)
	log(o);
	if test(s,o):
		stats.failed=stats.failed+1
		print "failed test:",cmd
		result="FAILED";
	else:
		stats.ok=stats.ok+1
		result="OK";
	log("%s (%i)"%(result,s));
	log("");

def rx_test(pat,str):
	if re.search(pat,str): return 0
	return 1
def status_test(s,o):
	if s==0:
		return 0
	return 1

#set everything to default in case user has different in config file
cfvcmd="../cfv -VRMU"

def cfv_test(s,o):
	x=re.search(r'^(\d+) files, (\d+) OK.  [\d.]+ seconds, [\d.]+K(/s)?$',o)
	if s==0 and x and x.group(1) == x.group(2) and int(x.group(1))>0:
		return 0
	return 1

def cfv_unv_test(s,o):
	x=re.search(r'^(\d+) files, (\d+) OK, (\d)+ unverified.  [\d.]+ seconds, [\d.]+K(/s)?$',o,re.M)
	if s!=0 and x and x.group(1) == x.group(2) and int(x.group(1))>0 and int(x.group(3))==1:
		return 0
	return 1

def cfv_version_test(s,o):
	x=re.search(r'cfv v([\d.]+) -',o)
	x2=re.search(r'cfv ([\d.]+) ',open("../README").readline())
	x3=re.search(r' v([\d.]+):',open("../Changelog").readline())
	if x: log('cfv: '+x.group(1))
	if x2: log('README: '+x2.group(1))
	if x3: log('Changelog: '+x3.group(1))
	if os.path.isdir('../debian'):
		x4=re.search(r'cfv \(([\d.]+)-\d+\) ',open("../debian/changelog").readline())
		if x4: log('deb changelog: '+x4.group(1))
		if not x or not x4 or x4.group(1)!=x.group(1):
			return 1
	if x and x2 and x3 and x.group(1)==x2.group(1) and x.group(1)==x3.group(1):
		return 0
	return 1

def T_test(f):
	test_generic(cfvcmd+" -T -f test."+f,cfv_test)

def C_test(f,extra=None,verify=None):
	cmd=cfvcmd
	f='test.C.'+f
	if extra:
		cmd=cmd+" "+extra
	test_generic("%s -C -f %s"%(cmd,f),cfv_test)
	test_generic("%s -T -f %s"%(cmd,f),cfv_test)
	if verify:
		verify(f)
	os.unlink(f)
	
logfile=open("test.log","w")
T_test("md5")
T_test("csv")
T_test("sfv")
T_test("csv2")

C_test("md5",verify=lambda f: test_generic("md5sum -c "+f,status_test))
C_test("csv")
C_test("sfv")
C_test("csv2","-t csv2")
#test_generic("../cfv -V -T -f test.md5",cfv_test)
#test_generic("../cfv -V -tcsv -T -f test.md5",cfv_test)

test_generic(cfvcmd+" -u -f test.md5 data* test.py",cfv_unv_test)
test_generic(cfvcmd+" -u -f test.md5 data* test.py test.md5",cfv_unv_test)
test_generic(cfvcmd+" -h",cfv_version_test)

donestr="tests finished:  ok: %i  failed: %i"%(stats.ok,stats.failed)
log("\n"+donestr)
print donestr
