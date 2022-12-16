from cfv.BitTorrent import bencode
from cfvtest import TestCase


class BencodeTestCase(TestCase):
    def test_bencode(self) -> None:
        bencode.test_bencode()

    def test_bdecode(self) -> None:
        bencode.test_bdecode()
