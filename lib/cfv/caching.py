import errno
import os

from cfv import osutil


# TODO: do some benchmarking of how useful _path_key_cache is on different OS's
# TODO: To handle hard-linked files efficiently, size and hash attributes should stored by <path key>, not by filename.  (Other attributes should still be stored by filename.)
# TODO: Only set _verified, _ok attributes when we actually will need them.
# TODO: stop common.py mucking with _path_key_cache member.  (Move chdir/cdup functions here, or even better don't chang directories at all.)
# TODO: make nocase_* functions not depend on current dir
class FileInfoCache:
    def __init__(self):
        # data is a mapping of <path key> -> <path cache>
        # <path key> is either a (dev, inode) pair or a full pathname (from os.path.realpath)
        # <path cache> is map from filename(without path, relative to path key) -> <finfo>
        # <finfo> is a map of <attr> -> <value>
        # <attr> can be '_verified', '_ok', 'size', <any hash name>
        self.data = {}
        # map from <path key> -> <nocase map>
        # <nocase map> is a map from <lowercase> -> [<orig name1>, <orig name2>, ...]
        self._nocase_dir_cache = {}
        # the <finfo> map for stdin
        self.stdin_finfo = {}
        # map of <path> (relative to curdir) -> <path key>
        # this member is saved/cleared/restored by chdir and cdup functions in common.py
        self._path_key_cache = {}

    def set_verified(self, fn):
        self.getfinfo(fn)['_verified'] = 1

    def is_verified(self, fn):
        return self.getfinfo(fn).get('_verified', 0)

    def set_flag(self, fn, flag):
        self.getfinfo(fn)[flag] = 1

    def has_flag(self, fn, flag):
        return flag in self.getfinfo(fn)

    def get_path_key(self, path):
        dk = self._path_key_cache.get(path)
        if dk is not None:
            return dk
        st = os.stat(path or osutil.curdiru)
        if st.st_ino:
            dk = (st.st_dev, st.st_ino)
        else:
            dk = os.path.realpath(path)
        self._path_key_cache[path] = dk
        return dk

    def getpathcache(self, path):
        pathkey = self.get_path_key(path)
        pathcache = self.data.get(pathkey)
        if pathcache is None:
            self.data[pathkey] = pathcache = {}
        return pathcache

    def getfinfo(self, fn):
        if fn == '':
            return self.stdin_finfo
        else:
            fpath, ftail = os.path.split(fn)
            pathdata = self.getpathcache(fpath)
            finfo = pathdata.get(ftail)
            if finfo is None:
                pathdata[ftail] = finfo = {}
            return finfo

    def rename(self, oldfn, newfn):
        ofinfo = self.getfinfo(oldfn)
        nfinfo = self.getfinfo(newfn)
        nfinfo.clear()
        for k, v in ofinfo.items():
            if k[0] != '_':  # don't preserve flags
                nfinfo[k] = v
        # nfinfo.update(ofinfo)
        ofinfo.clear()

    def nocase_dirfiles(self, dir, match):
        """return list of filenames in dir whose lowercase value equals match
        """
        dirkey = self.get_path_key(dir)
        if dirkey not in self._nocase_dir_cache:
            d = {}
            self._nocase_dir_cache[dirkey] = d
            for a in osutil.listdir(dir):
                a_lower = a.lower()
                if a_lower in d:
                    d[a_lower].append(a)
                else:
                    d[a_lower] = [a]
        else:
            d = self._nocase_dir_cache[dirkey]
        if match in d:
            return d[match]
        return []

    _FINDFILE = 1
    _FINDDIR = 0

    def nocase_findfile(self, filename, find=_FINDFILE):
        cur = osutil.curdiru
        parts = osutil.path_split(filename.lower())
        # print 'nocase_findfile:',filename,parts,len(parts)
        for i in range(0, len(parts)):
            p = parts[i]
            # matches = filter(lambda f, p=p: string.lower(f) == p, dircache.listdir(cur))  # too slooow, even with dircache (though not as slow as without it ;)
            matches = self.nocase_dirfiles(cur, p)  # nice and speedy :)
            # print 'i:', i, ' cur:', cur, ' p:', p, ' matches:', matches
            if i == len(parts) - find:  # if we are on the last part of the path and using FINDFILE, we want to match a file
                matches = filter(lambda f: os.path.isfile(osutil.path_join(cur, f)), matches)
            else:  # otherwise, we want to match a dir
                matches = filter(lambda f: os.path.isdir(osutil.path_join(cur, f)), matches)
            if not matches:
                raise IOError(errno.ENOENT, os.strerror(errno.ENOENT))
            if len(matches) > 1:
                raise IOError(errno.EEXIST, 'More than one name matches %s' % osutil.path_join(cur, p))
            if cur == osutil.curdiru:
                cur = matches[0]  # don't put the ./ on the front of the name
            else:
                cur = osutil.path_join(cur, matches[0])
        return cur

    def nocase_finddir(self, filename):
        return self.nocase_findfile(filename, self._FINDDIR)
