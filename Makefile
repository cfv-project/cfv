PYTHON=python
prefix=/usr/local
exec_prefix=${prefix}

#finds the site-packages dir that matches the selected prefix, or if none do, falls back to wherever it can find one..
pkgdir=`$(PYTHON) -c 'import sys,re; x=filter(lambda x: re.match("$(prefix).*site-packages",x),sys.path); y=filter(lambda y: re.search("site-packages",y),sys.path); x.sort(lambda x,y: cmp(len(x),len(y))); y.sort(lambda x,y: cmp(len(x),len(y))); x.extend(y); print x[0]'`
#nice little expression, huh? ;)

bindir=${exec_prefix}/bin
mandir=${prefix}/man
install=/usr/bin/install -c
install_dir=${install} -d
install_data=${install} -m 0644
install_script=${install} -m 0755

foo:
	@echo 'to install cfv, type make install or install-wrapper.'
	@echo "manpage will be installed to: $(mandir)/man1"
	@echo ""
	@echo '"make install" will install like a standard script in'
	@echo "$(bindir)"
	@echo ""
	@echo '"make install-wrapper" will install a byte-compiled version in'
	@echo "$(pkgdir)"
	@echo 'with a small wrapper script in $(bindir)'
	@echo 'this allows for faster loading time since python does not need'
	@echo 'to parse the entire script every load.'
	@echo ""
	@echo 'You may edit the Makefile if you want to install somewhere else.'
	@echo ""
	@echo "Note that this method does not change how fast cfv actually runs,"
	@echo "merely the time it takes from when you hit enter till it actually"
	@echo "starts doing something.  For processing lots of files, this amount"
	@echo "of time will be inconsequential."


#this will create a wrapper script that calls python directly (if we can find it), or using the bin/env trick.
#we don't need to check for PYTHON being set to something, since os.path.join handles the case of the component being an absolute path
cfv.wrapper:
	$(PYTHON) -c 'import string,os; py=filter(lambda x: os.path.isfile(x),map(lambda x: os.path.join(x,"$(PYTHON)"),string.split(os.environ["PATH"],":"))); py.append(" /usr/bin/env $(PYTHON)"); open("cfv.wrapper","w").write("#!%s\nimport cfv\ncfv.main()\n"%py[0])'

$(DESTDIR)$(mandir)/man1 $(DESTDIR)$(bindir):
	$(install_dir) $@

install-wrapper-only: $(DESTDIR)$(bindir) cfv.wrapper install_man
	$(install_data) cfv $(DESTDIR)$(pkgdir)/cfv.py
	$(install_script) cfv.wrapper $(DESTDIR)$(bindir)/cfv

install-wrapper: install-wrapper-only
	$(PYTHON) -c "import py_compile; py_compile.compile('$(DESTDIR)$(pkgdir)/cfv.py')" 
	$(PYTHON) -O -c "import py_compile; py_compile.compile('$(DESTDIR)$(pkgdir)/cfv.py')" 

install: $(DESTDIR)$(bindir) install_man
	$(install_script) cfv $(DESTDIR)$(bindir)/cfv

install_man: $(DESTDIR)$(mandir)/man1
	$(install_data) cfv.1 $(DESTDIR)$(mandir)/man1/cfv.1

clean:
	-rm *.py[co] cfv.wrapper

distclean: clean
	-rm -r cfv.nsi tags test/test.log `find . -regex '.*~\|.*/\.#.*' -o -name CVS -o -name .cvsignore`

distclean-unixsrc: distclean
	-rm cfv.bat cfv.txt

cfv.txt: %.txt: %.1
	LANG=C man -l $< | sed -e 's/.//g' > $@

distclean-winsrc: distclean cfv.txt
	-rm Makefile cfv.1
	mv cfv cfv.py
	todos *.txt COPYING README Changelog cfv.bat cfv.py test/*.py

PY2EXEDIR=~/mnt/temp/cfv
nsis-prepare: cfv.txt
	#hahaha, ugly hardcodedhackness
	cp cfv.txt cfv.nsi setup*.py $(PY2EXEDIR)
	cp Changelog $(PY2EXEDIR)/Changelog.txt
	cp COPYING $(PY2EXEDIR)/COPYING.txt
	cp cfv $(PY2EXEDIR)/cfv.py
	todos $(PY2EXEDIR)/*.txt

