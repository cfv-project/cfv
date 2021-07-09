from cfv.BitTorrent import bencode
from cfvtest import TestCase


class BencodeTestCase(TestCase):
    def test_bencode(self):
        bencode.test_bencode()

    def test_bdecode(self):
        bencode.test_bdecode()
