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

