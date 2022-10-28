# Written by Petru Paler
# see LICENSE.txt for license information

from builtins import object


def decode_int(x, f):
    f += 1
    newf = x.index(b'e', f)
    try:
        n = int(x[f:newf])
    except (OverflowError, ValueError):
        n = int(x[f:newf])
    if x[f:f + 1] == b'-':
        if x[f + 1:f + 2] == b'0':
            raise ValueError
    elif x[f:f + 1] == b'0' and newf != f + 1:
        raise ValueError
    return n, newf + 1


def decode_string(x, f):
    colon = x.index(b':', f)
    try:
        n = int(x[f:colon])
    except (OverflowError, ValueError):
        n = int(x[f:colon])
    if x[f:f + 1] == b'0' and colon != f + 1:
        raise ValueError
    colon += 1
    return x[colon:colon + n], colon + n


def decode_list(x, f):
    r, f = [], f + 1
    while x[f:f + 1] != b'e':
        v, f = decode_func[x[f:f + 1]](x, f)
        r.append(v)
    return r, f + 1


def decode_dict(x, f):
    r, f = {}, f + 1
    lastkey = None
    while x[f:f + 1] != b'e':
        k, f = decode_string(x, f)
        if lastkey is not None and lastkey >= k:
            raise ValueError
        lastkey = k
        r[k], f = decode_func[x[f:f + 1]](x, f)
    return r, f + 1


decode_func = {
    b'l': decode_list,
    b'd': decode_dict,
    b'i': decode_int,
    b'0': decode_string,
    b'1': decode_string,
    b'2': decode_string,
    b'3': decode_string,
    b'4': decode_string,
    b'5': decode_string,
    b'6': decode_string,
    b'7': decode_string,
    b'8': decode_string,
    b'9': decode_string,
}


def bdecode(x):
    try:
        r, pos = decode_func[x[0:1]](x, 0)
    except (IndexError, KeyError):
        raise ValueError
    if pos != len(x):
        raise ValueError
    return r


def test_bdecode():
    try:
        bdecode(b'0:0:')
        assert 0
    except ValueError:
        pass
    try:
        bdecode(b'ie')
        assert 0
    except ValueError:
        pass
    try:
        bdecode(b'i341foo382e')
        assert 0
    except ValueError:
        pass
    assert bdecode(b'i4e') == 4
    assert bdecode(b'i0e') == 0
    assert bdecode(b'i123456789e') == 123456789
    assert bdecode(b'i-10e') == -10
    try:
        bdecode(b'i-0e')
        assert 0
    except ValueError:
        pass
    try:
        bdecode(b'i123')
        assert 0
    except ValueError:
        pass
    try:
        bdecode(b'')
        assert 0
    except ValueError:
        pass
    try:
        bdecode(b'i6easd')
        assert 0
    except ValueError:
        pass
    try:
        bdecode(b'35208734823ljdahflajhdf')
        assert 0
    except ValueError:
        pass
    try:
        bdecode(b'2:abfdjslhfld')
        assert 0
    except ValueError:
        pass
    assert bdecode(b'0:') == b''
    assert bdecode(b'3:abc') == b'abc'
    assert bdecode(b'10:1234567890') == b'1234567890'
    try:
        bdecode(b'02:xy')
        assert 0
    except ValueError:
        pass
    try:
        bdecode(b'l')
        assert 0
    except ValueError:
        pass
    assert bdecode(b'le') == []
    try:
        bdecode(b'leanfdldjfh')
        assert 0
    except ValueError:
        pass
    assert bdecode(b'l0:0:0:e') == [b'', b'', b'']
    try:
        bdecode(b'relwjhrlewjh')
        assert 0
    except ValueError:
        pass
    assert bdecode(b'li1ei2ei3ee') == [1, 2, 3]
    assert bdecode(b'l3:asd2:xye') == [b'asd', b'xy']
    assert bdecode(b'll5:Alice3:Bobeli2ei3eee') == [[b'Alice', b'Bob'], [2, 3]]
    try:
        bdecode(b'd')
        assert 0
    except ValueError:
        pass
    try:
        bdecode(b'defoobar')
        assert 0
    except ValueError:
        pass
    assert bdecode(b'de') == {}
    assert bdecode(b'd3:agei25e4:eyes4:bluee') == {b'age': 25, b'eyes': b'blue'}
    assert bdecode(b'd8:spam.mp3d6:author5:Alice6:lengthi100000eee') == {b'spam.mp3': {b'author': b'Alice', b'length': 100000}}
    try:
        bdecode(b'd3:fooe')
        assert 0
    except ValueError:
        pass
    try:
        bdecode(b'di1e0:e')
        assert 0
    except ValueError:
        pass
    try:
        bdecode(b'd1:b0:1:a0:e')
        assert 0
    except ValueError:
        pass
    try:
        bdecode(b'd1:a0:1:a0:e')
        assert 0
    except ValueError:
        pass
    try:
        bdecode(b'i03e')
        assert 0
    except ValueError:
        pass
    try:
        bdecode(b'l01:ae')
        assert 0
    except ValueError:
        pass
    try:
        bdecode(b'9999:x')
        assert 0
    except ValueError:
        pass
    try:
        bdecode(b'l0:')
        assert 0
    except ValueError:
        pass
    try:
        bdecode(b'd0:0:')
        assert 0
    except ValueError:
        pass
    try:
        bdecode(b'd0:')
        assert 0
    except ValueError:
        pass
    try:
        bdecode(b'00:')
        assert 0
    except ValueError:
        pass
    try:
        bdecode(b'l-3:e')
        assert 0
    except ValueError:
        pass
    try:
        bdecode(b'i-03e')
        assert 0
    except ValueError:
        pass
    bdecode(b'd0:i3ee')


class Bencached(object):
    __slots__ = ['bencoded']

    def __init__(self, s):
        self.bencoded = s


def encode_bencached(x, r):
    r.append(x.bencoded)


def encode_int(x, r):
    r.extend((b'i', b'%d' % x, b'e'))


def encode_string(x, r):
    r.extend((b'%d' % len(x), b':', x))


def encode_list(x, r):
    r.append(b'l')
    for i in x:
        encode_func[type(i)](i, r)
    r.append(b'e')


def encode_dict(x, r):
    r.append(b'd')
    ilist = list(x.items())
    ilist.sort()
    for k, v in ilist:
        r.extend((b'%d' % len(k), b':', k))
        encode_func[type(v)](v, r)
    r.append(b'e')


encode_func = {
    type(Bencached(0)): encode_bencached,
    bool: encode_int,
    int: encode_int,
    bytes: encode_string,
    list: encode_list,
    tuple: encode_list,
    dict: encode_dict,
}


def bencode(x):
    r = []
    encode_func[type(x)](x, r)
    return b''.join(r)


def test_bencode():
    assert bencode(4) == b'i4e'
    assert bencode(0) == b'i0e'
    assert bencode(-10) == b'i-10e'
    assert bencode(12345678901234567890) == b'i12345678901234567890e'
    assert bencode(b'') == b'0:'
    assert bencode(b'abc') == b'3:abc'
    assert bencode(b'1234567890') == b'10:1234567890'
    assert bencode([]) == b'le'
    assert bencode([1, 2, 3]) == b'li1ei2ei3ee'
    assert bencode([[b'Alice', b'Bob'], [2, 3]]) == b'll5:Alice3:Bobeli2ei3eee'
    assert bencode({}) == b'de'
    assert bencode({b'age': 25, b'eyes': b'blue'}) == b'd3:agei25e4:eyes4:bluee'
    assert bencode({b'spam.mp3': {b'author': b'Alice', b'length': 100000}}) == b'd8:spam.mp3d6:author5:Alice6:lengthi100000eee'
    assert bencode(Bencached(bencode(3))) == b'i3e'
    try:
        bencode({1: b'foo'})
    except TypeError:
        return
    assert 0
