import locale
import os
import sys

from cfv import strutil

if hasattr(locale,'getpreferredencoding'):
	preferredencoding = locale.getpreferredencoding() or 'ascii'
else:
	preferredencoding = 'ascii'

if hasattr(sys,'getfilesystemencoding'):
	fsencoding = sys.getfilesystemencoding()
else:
	fsencoding = preferredencoding

try:
	os.stat(os.curdir+u'\0foobarbaz')
	fs_nullsok=0 #if os.stat succeeded, it means the filename was cut off at the null (or the user has funny files ;)
except EnvironmentError:
	fs_nullsok=1
except TypeError:
	fs_nullsok=0


if hasattr(os,'getcwdu'):
	def getcwdu():
		try:
			return os.getcwdu()
		except UnicodeError:
			return os.getcwd()
else:
	def getcwdu():
		d = os.getcwd()
		try:
			return unicode(d, fsencoding)
		except UnicodeError:
			return d

curdiru=unicode(os.curdir)

if sys.hexversion>=0x020300f0:
	listdir = os.listdir
else:
	def listdir(path):
		r = []
		for fn in os.listdir(path):
			try:
				r.append(unicode(fn, fsencoding))
			except UnicodeError:
				r.append(fn)
		return r

def path_join(*paths):
	#The assumption here is that the only reason a raw string path component can get here is that it cannot be represented in unicode (Ie, it is not a valid encoded string)
	#In that case, we convert the parts that are valid back to raw strings and join them together.  If the unicode can't be represented in the fsencoding, then there's nothing that can be done, and this will blow up.  Oh well.
	if filter(strutil.is_rawstr, paths):
		#import traceback;traceback.print_stack() ####
		#perror("path_join: non-unicode args "+repr(paths))

		npaths = []
		for p in paths:
			if strutil.is_unicode(p):
				npaths.append(p.encode(fsencoding))
			else:
				npaths.append(p)
		paths = npaths
	return os.path.join(*paths)


def fcmp(f1, f2):
	import filecmp
	return filecmp.cmp(f1, f2, shallow=0)

