try:
	reversed #reversed(seq) only in python>=2.4
except NameError:
	def reversed(seq):
		l = list(seq)
		l.reverse()
		return l

try:
	sorted #sorted(seq) only in python>=2.4
except NameError:
	def sorted(seq):
		l = list(seq)
		l.sort()
		return l

try:
	staticmethod #new in python 2.2
except NameError:
	class staticmethod:
		def __init__(self, anycallable):
			self.__call__ = anycallable
