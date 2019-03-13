import os
import time

from cfv import strutil


class INF:
    """object that is always larger than what it is compared to
    """

    def __cmp__(self, other):
        return 1

    def __mul__(self, other):
        return self

    def __div__(self, other):
        return self

    def __rdiv__(self, other):
        return 0


INF = INF()


# Escape code for clearing from current cursor position to end of line.
# This works on ANSI and vt100-descended terminals, so should be pretty portable.
# We could also use:
# import curses
# curses.setupterm()
# _CLR_TO_EOL = curses.tigetstr('el')
# But the curses module is not available on all systems, and this seems pretty
# heavy-weight when the ANSI code is going to work on (almost) all systems.
_CLR_TO_EOL = '\x1b[K'


class ProgressMeter:
    spinnerchars = r'\|/-'

    def __init__(self, fd, steps=20, scrwidth=80, frobfn=lambda x: x):
        self.wantsteps = steps
        self.needrefresh = 1
        self.filename = None
        self.fd = fd
        self.frobfn = frobfn
        self.scrwidth = scrwidth

    def init(self, name, size=None, cursize=0):
        self.steps = self.wantsteps
        self.filename = name
        if size is None:
            if name != '' and os.path.isfile(name):
                size = os.path.getsize(name)  # XXX this probably doesn't belong here..
        self.name = strutil.lchoplen(self.frobfn(name), self.scrwidth - self.steps - 4)
        if not size:  # if stdin or device file, we don't know the size, so just use a spinner.  If the file is actually zero bytes, it doesn't matter either way.
            self.stepsize = INF
            self.steps = 1
        elif size <= self.steps:
            self.stepsize = 1
        else:
            self.stepsize = size / self.steps
        self.nextstep = self.stepsize
        self.spinneridx = 0
        self.needrefresh = 1
        self.update(cursize)

    def update(self, cursize):
        if self.needrefresh:
            donesteps = cursize / self.stepsize
            stepsleft = self.steps - donesteps
            self.nextstep = self.stepsize * (donesteps + 1)
            self.fd.write('%s : %s' % (self.name, '#' * donesteps + '.' * stepsleft) + '\b' * stepsleft)
            self.fd.flush()
            self.needrefresh = 0
        elif self.nextstep < cursize:
            updsteps = (cursize - self.nextstep) / self.stepsize + 1
            self.nextstep += self.stepsize * updsteps
            self.fd.write('#' * updsteps)
            self.fd.flush()
        else:
            self.fd.write(self.spinnerchars[self.spinneridx] + '\b')
            self.fd.flush()
            self.spinneridx = (self.spinneridx + 1) % len(self.spinnerchars)

    def cleanup(self):
        if not self.needrefresh:
            self.fd.write('\r' + _CLR_TO_EOL)
            self.needrefresh = 1


class TimedProgressMeter(ProgressMeter):
    def __init__(self, *args, **kw):
        ProgressMeter.__init__(self, *args, **kw)
        self.nexttime = 0

    def update(self, cursize):
        curtime = time.time()
        if curtime > self.nexttime:
            self.nexttime = curtime + 0.06
            ProgressMeter.update(self, cursize)
