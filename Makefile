prefix=/usr/local
exec_prefix=${prefix}
bindir=${exec_prefix}/bin
mandir=${prefix}/man
install=/usr/bin/install -c
user=root
group=root

foo:
	@echo 'to install cfv, type "make install".'
	@echo 'you may edit the Makefile if you want to install somewhere other than'
	@echo "$(prefix)/{bin,man}"

install:
	$(install) -o $(user) -g $(group) -m 0755 cfv $(bindir)
	$(install) -o $(user) -g $(group) -m 0644 cfv.1 $(mandir)/man1

clean:
	#nothing

distclean:
	-rm *~
