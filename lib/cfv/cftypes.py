import re


_cftypes = {}
_user_cf_fn_regexs = []
_cf_fn_exts, _cf_fn_matches, _cf_fn_searches = [], [], []
_cf_matchers = []


def add_user_cf_fn_regex(match, typename):
    _user_cf_fn_regexs.append((re.compile(match, re.I).search, get_handler(typename)))


def auto_filename_match(*names):
    for searchfunc, cftype in _user_cf_fn_regexs + _cf_fn_matches + _cf_fn_exts + _cf_fn_searches:
        for name in names:
            if searchfunc(name):
                return cftype
    return None


def auto_chksumfile_match(file):
    for p, matchfunc, cftype in _cf_matchers:
        if matchfunc(file):
            return cftype
    return None


def register_cftype(cftype):
    _cftypes[cftype.name] = cftype

    if hasattr(cftype, 'auto_filename_match'):
        if cftype.auto_filename_match[-1] == '$' and cftype.auto_filename_match[0] == '^':
            _cf_fn_matches.append((re.compile(cftype.auto_filename_match, re.I).search, cftype))
        elif cftype.auto_filename_match[-1] == '$':
            _cf_fn_exts.append((re.compile(cftype.auto_filename_match, re.I).search, cftype))
        else:
            _cf_fn_searches.append((re.compile(cftype.auto_filename_match, re.I).search, cftype))

    _cf_matchers.append((getattr(cftype, 'auto_chksumfile_order', 0), cftype.auto_chksumfile_match, cftype))
    _cf_matchers.sort()
    _cf_matchers.reverse()


def get_handler_names():
    return sorted(_cftypes)


def get_handler(name):
    return _cftypes[name]


def has_handler(name):
    return name in _cftypes
