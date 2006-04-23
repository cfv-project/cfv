PYTHON=python
prefix=/usr/local

foo:
	@echo 'To install cfv, you should now use the distutils setup script like:'
	@echo 'python setup.py install'
	@echo 'Or you can run "make install" which will do:'
	@echo 'python setup.py install --prefix=$(prefix)'


#back compatibility
install-wrapper: install

install:
	$(PYTHON) setup.py install --prefix=$(prefix)

clean:
	$(PYTHON) setup.py clean --all

distclean: clean
	-rm -r cfv.nsi tags test/test.log `find . -regex '.*~\|.*/\.#.*' -o -name CVS -o -name .cvsignore`

distclean-unixsrc: distclean
	-rm cfv.bat cfv.txt

cfv.txt: %.txt: %.1
	LANG=C man -l $< | sed -e 's/.//g' > $@

distclean-winsrc: distclean cfv.txt
	-rm Makefile cfv.1
	todos *.txt COPYING README Changelog bin/cfv.bat lib/cfv/*.py test/*.py

PY2EXEDIR=~/mnt/temp/cfv
nsis-prepare: cfv.txt
	#hahaha, ugly hardcodedhackness
	cp cfv.txt cfv.nsi setup*.py $(PY2EXEDIR)
	cp Changelog $(PY2EXEDIR)/Changelog.txt
	cp COPYING $(PY2EXEDIR)/COPYING.txt
	cp -r bin $(PY2EXEDIR)/
	cp -r lib $(PY2EXEDIR)/
	todos $(PY2EXEDIR)/*.txt

