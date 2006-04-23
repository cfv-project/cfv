import locale
import os
import sys

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
			return unicode(d,osutil.fsencoding)
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


def fcmp(f1, f2):
	import filecmp
	return filecmp.cmp(f1, f2, shallow=0)

