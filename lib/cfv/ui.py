from builtins import object
from builtins import str

import errno
import os
import sys

from cfv import osutil
from cfv import strutil
from cfv import term
from cfv.progress import TimedProgressMeter


LISTOK = 512
LISTBAD = 1024
LISTNOTFOUND = 2048
LISTUNVERIFIED = 4096
LISTARGS = {'ok': LISTOK, 'bad': LISTBAD, 'notfound': LISTNOTFOUND, 'unverified': LISTUNVERIFIED}

_codec_error_handler = 'backslashreplace'


class View(object):
    def __init__(self, config) -> None:
        self.stdout = sys.stdout
        self.stderr = sys.stderr
        self._stdout_special = 0
        self.stdinfo = sys.stdout
        self.progress = None
        self.config = config
        self.perhaps_showpath = config.perhaps_showpath

    def set_stdout_special(self) -> None:
        """If stdout is being used for special purposes, redirect informational messages to stderr.
        """
        self._stdout_special = 1
        self.stdinfo = self.stderr

    def setup_output(self) -> None:
        self.stdinfo = self._stdout_special and self.stderr or self.stdout
        # if one of stdinfo (usually stdout) or stderr is a tty, use it.  Otherwise use stdinfo.
        progressfd = self.stdinfo.isatty() and self.stdinfo or self.stderr.isatty() and self.stderr or self.stdinfo
        doprogress = not self.config.verbose == -2 and (
            self.config.progress == 'y' or (
                self.config.progress == 'a' and progressfd.isatty()
            )
        )
        if doprogress:
            self.progress = TimedProgressMeter(fd=progressfd, scrwidth=term.scrwidth, frobfn=self.perhaps_showpath)
        else:
            self.progress = None

    def pverbose(self, s, nl='\n') -> None:
        if self.config.verbose > 0:
            self.stdinfo.write(s + nl)

    def pinfo(self, s, nl='\n') -> None:
        if self.config.verbose >= 0 or self.config.verbose == -3:
            self.stdinfo.write(s + nl)

    def perror(self, s, nl='\n') -> None:
        # import traceback;traceback.print_stack()####
        if self.config.verbose >= -1:
            self.stdout.flush()  # avoid inconsistent screen state if stdout has unflushed data
            self.stderr.write(s + nl)

    def plistf(self, filename) -> None:
        self.stdout.write(self.perhaps_showpath(filename) + self.config.listsep)

    def ev_test_cf_begin(self, cftypename, filename, comment) -> None:
        if comment:
            comment = ', ' + comment
            comment = strutil.rchoplen(comment, 102)  # limit the length in case its a really long one.
        else:
            comment = ''
        self.pverbose('testing from %s (%s%s)' % (strutil.showfn(filename), cftypename.lower(), comment))

    def ev_test_cf_done(self, filename, cf_stats) -> None:
        self.pinfo('%s: %s' % (self.perhaps_showpath(filename), cf_stats))

    ev_make_cf_done = ev_test_cf_done

    def ev_test_cf_unrecognized_line(self, filename, lineno) -> None:
        self.perror('%s : unrecognized line %i (CF)' % (self.perhaps_showpath(filename), lineno))

    def ev_test_cf_lineencodingerror(self, filename, lineno, ex) -> None:
        self.perror('%s : line %i: %s (CF)' % (self.perhaps_showpath(filename), lineno, ex))

    def ev_test_cf_filenameencodingerror(self, filename, fileid, ex) -> None:
        self.perror('%s : file %s: %s (CF)' % (self.perhaps_showpath(filename), fileid, ex))

    def ev_test_cf_invaliddata(self, filename, e) -> None:
        self.perror('%s : %s (CF)' % (self.perhaps_showpath(filename), e))

    def ev_test_cf_unrecognized(self, filename, decode_errors) -> None:
        if decode_errors:
            self.perror("I don't recognize the type or encoding of %s" % strutil.showfn(filename))
        else:
            self.perror("I don't recognize the type of %s" % strutil.showfn(filename))

    def ev_cf_enverror(self, filename, e) -> None:
        self.perror('%s : %s (CF)' % (self.perhaps_showpath(filename), enverrstr(e)))

    def ev_make_filenameencodingerror(self, filename, e) -> None:
        self.perror('%s : unencodable filename: %s' % (self.perhaps_showpath(filename), e))

    def ev_make_filenamedecodingerror(self, filename, e) -> None:
        self.perror('%s : undecodable filename: %s' % (self.perhaps_showpath(filename), e))

    def ev_make_filenameinvalid(self, filename) -> None:
        self.perror('%s : filename invalid for this cftype' % (self.perhaps_showpath(filename)))

    def ev_make_cf_typenotsupported(self, filename, cftype) -> None:
        self.perror('%s : %s not supported in create mode' % (strutil.showfn(filename), cftype.__name__.lower()))

    def ev_make_cf_alreadyexists(self, filename) -> None:
        self.perror('%s already exists' % self.perhaps_showpath(filename))

    def ev_d_enverror(self, path, ex) -> None:
        self.perror('%s%s : %s' % (strutil.showfn(path), os.sep, enverrstr(ex)))

    def ev_f_enverror(self, l_filename, ex) -> None:
        if isinstance(ex, EnvironmentError) and ex.errno == errno.ENOENT:
            if self.config.list & LISTNOTFOUND:
                self.plistf(l_filename)
        self.perror('%s : %s' % (self.perhaps_showpath(l_filename), enverrstr(ex)))

    def ev_f_verifyerror(self, l_filename, msg, foundok) -> None:
        if not foundok:
            if self.config.list & LISTBAD:
                self.plistf(l_filename)
        self.perror('%s : %s' % (self.perhaps_showpath(l_filename), msg))

    def ev_f_verifyerror_dupe(self, filename, msg, dupefilename, foundok) -> None:
        self.ev_f_verifyerror(filename, msg + ' (dupe of %s removed)' % strutil.showfn(dupefilename), foundok)

    def ev_f_verifyerror_renamed(self, filename, msg, newfilename, foundok) -> None:
        self.ev_f_verifyerror(filename, msg + ' (renamed to %s)' % strutil.showfn(newfilename), foundok)

    def ev_f_found_renameetcerror(self, filename, filesize, filecrc, found_fn, action, e) -> None:
        eaction = 'but error %r occured %s' % (enverrstr(e), action)
        self.ev_f_found(filename, filesize, filecrc, found_fn, eaction)

    def ev_f_found_renameetc(self, filename, filesize, filecrc, found_fn, action) -> None:
        self.ev_f_found(filename, filesize, filecrc, found_fn, action)

    def ev_f_found(self, filename, filesize, filecrc, found_fn, action='found') -> None:
        self.ev_f_ok(filename, filesize, filecrc, 'OK(%s %s)' % (action, strutil.showfn(found_fn)))

    def ev_f_ok(self, filename, filesize, filecrc, msg) -> None:
        if self.config.list & LISTOK:
            self.plistf(filename)
        if filesize >= 0:
            self.pverbose('%s : %s (%i,%s)' % (self.perhaps_showpath(filename), msg, filesize, filecrc))
        else:
            self.pverbose('%s : %s (%s)' % (self.perhaps_showpath(filename), msg, filecrc))

    def ev_generic_warning(self, msg) -> None:
        self.perror('warning: %s' % msg)

    def ev_unverified_file(self, filename) -> None:
        self.perror('%s : not verified' % self.perhaps_showpath(filename))

    def ev_unverified_dir(self, path) -> None:
        self.ev_unverified_file(osutil.path_join(path, '*'))

    def ev_unverified_dirrecursive(self, path) -> None:
        self.ev_unverified_file(osutil.path_join(path, '**'))

    def ev_unverified_file_plistf(self, filename) -> None:
        if self.config.list & LISTUNVERIFIED:
            self.plistf(filename)


def enverrstr(e) -> bool:
    return getattr(e, 'strerror', None) or str(e)
