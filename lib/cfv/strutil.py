import codecs
import unicodedata
from StringIO import StringIO

from cfv.compat import *

def is_unicode(s, _unitype=type(u'')):
	return type(s) == _unitype
def is_rawstr(s, _stype=type('')):
	return type(s) == _stype

def safesort(l):
	sl = filter(is_rawstr, l)
	ul = filter(lambda e: not is_rawstr(e), l)
	sl.sort()
	ul.sort()
	l[:] = ul+sl


def codec_supports_readline(e):
	"""Figure out whether the given codec's StreamReader supports readline.

	Some (utf-16) raise NotImplementedError(py2.3) or UnicodeError(py<2.3),
	others (cp500) are just broken.
	With recent versions of python (cvs as of 20050203), readline seems to
	work on all codecs.  Yay.
	"""
	testa=u'a'*80 + u'\n'
	testb=u'b'*80 + u'\n'
	test=testa+testb
	r=codecs.getreader(e)(StringIO(test.encode(e)))
	try:
		return r.readline(100)==testa and r.readline(100)==testb
	except (NotImplementedError, UnicodeError):
		return 0


def chomp(line):
	if line[-2:] == '\r\n': return line[:-2]
	elif line[-1:] in '\r\n': return line[:-1]
	return line

def chompnulls(line):
	p = line.find('\0')
	if p < 0: return line
	else:     return line[:p]

try:
	_unicodedata_east_asian_width = unicodedata.east_asian_width # unicodedata.east_asian_width only in python >= 2.4
except AttributeError:
	def _unicodedata_east_asian_width(c):
		# Not a true replacement, only suitable for our width calculations.
		# Adapted from http://www.cl.cam.ac.uk/~mgk25/ucs/wcwidth.c version 2003-05-20
		ucs = ord(c)
		if (ucs >= 0x1100 and
				(ucs <= 0x115f or                    # Hangul Jamo init. consonants */
					ucs == 0x2329 or ucs == 0x232a or
					(ucs >= 0x2e80 and ucs <= 0xa4cf and
						ucs != 0x303f) or                  # CJK ... Yi */
					(ucs >= 0xac00 and ucs <= 0xd7a3) or # Hangul Syllables */
					(ucs >= 0xf900 and ucs <= 0xfaff) or # CJK Compatibility Ideographs */
					(ucs >= 0xfe30 and ucs <= 0xfe6f) or # CJK Compatibility Forms */
					(ucs >= 0xff00 and ucs <= 0xff60) or # Fullwidth Forms */
					(ucs >= 0xffe0 and ucs <= 0xffe6) or
					(ucs >= 0x20000 and ucs <= 0x2fffd) or
					(ucs >= 0x30000 and ucs <= 0x3fffd))):
			return 'W'
		return 'Na'

def uwidth(u):
	#TODO: should it return -1 or something for control chars, like wcswidth?
	# see http://www.cl.cam.ac.uk/~mgk25/ucs/wcwidth.c for a sample implementation
	#if is_rawstr(u):
	#	return len(u)
	w = 0
	#for c in unicodedata.normalize('NFC', u):
	for c in u:
		if c in (u'\u0000', u'\u200B'): # null, ZERO WIDTH SPACE
			continue
		ccat = unicodedata.category(c)
		if ccat in ('Mn', 'Me', 'Cf'): # "Mark, nonspacing", "Mark, enclosing", "Other, format"
			continue
		cwidth = _unicodedata_east_asian_width(c)
		if cwidth in ('W', 'F'): # "East Asian Wide", "East Asian Full-width"
			w += 2
		else:
			w += 1
	return w

def lchoplen(line, max):
	"""Return line cut on left so it takes at most max character cells when printed, and width of result.

	>>> lchoplen(u'hello world',6)
	(u'...rld', 6)
	"""
	if is_rawstr(line):
		if len(line)>max:
			return '...'+line[-(max-3):], max
		return line, len(line)
	chars = ['']
	w = 0
	for c in reversed(line):
		cw = uwidth(c)
		if w+cw > max:
			while w > max - 3:
				w -= uwidth(chars.pop(0))
			w += 3
			chars.insert(0,'...')
			break
		w += cw
		chars[0] = c + chars[0]
		if cw != 0:
			chars.insert(0,'')
	return ''.join(chars), w

def rchoplen(line, max):
	"""Return line cut on right so it takes at most max character cells when printed, and width of result.

	>>> rchoplen(u'hello world',6)
	(u'hel...', 6)
	"""
	if is_rawstr(line):
		if len(line)>max:
			return line[:max-3]+'...', max
		return line, len(line)
	chars = ['']
	w = 0
	for c in line:
		cw = uwidth(c)
		if w+cw > max:
			while w > max - 3:
				w -= uwidth(chars.pop())
			chars.append('...')
			w += 3
			break
		w += cw
		if cw == 0:
			chars[-1] += c
		else:
			chars.append(c)
	return ''.join(chars), w


class CodecWriter:
	"""Similar to codecs.StreamWriter, but str objects are decoded (as ascii) before then being passed to the the output encoder.
	This is necessary as some codecs barf on trying to encode ascii strings.
	"""
	def __init__(self, encoding, stream, errors='strict'):
		self.__stream = codecs.getwriter(encoding)(stream, errors)
	def write(self, obj):
		if is_rawstr(obj):
			obj = unicode(obj,'ascii')
		self.__stream.write(obj)
	def writelines(self, list):
		self.write(''.join(list))
	def __getattr__(self, name, getattr=getattr):
		""" Inherit all other methods from the underlying stream.
		"""
		return getattr(self.__stream, name)

