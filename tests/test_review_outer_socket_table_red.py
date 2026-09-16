from __future__ import annotations

import unittest

from tools.review_outer import PriorEffectiveOuterUnavailable, _listening_tcp_ports


class ReviewOuterSocketTableTests(unittest.TestCase):
    def test_accepts_canonical_tcp_and_tcp6_header_spellings(self) -> None:
        socket_tables = (
            b"  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode\n"
            b"   0: 0100007F:0016 00000000:0000 0A 00000000:00000000 00:00000000 00000000 0 0 123 1 0000000000000000 100 0 0 10 0\n"
            b"  sl  local_address                         remote_address                        st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode\n"
            b"   0: 00000000000000000000000000000000:0948 00000000000000000000000000000000:0000 0A 00000000:00000000 00:00000000 00000000 0 0 124 1 0000000000000000 100 0 0 10 0\n"
        )

        self.assertEqual({22, 2376}, _listening_tcp_ports(socket_tables))

    def test_empty_or_headerless_socket_tables_fail_closed(self) -> None:
        headerless_row = b"   0: 0100007F:0016 00000000:0000 0A\n"
        for raw in (b"", b"\n", headerless_row):
            with self.subTest(raw=raw):
                with self.assertRaisesRegex(
                    PriorEffectiveOuterUnavailable,
                    "socket table is malformed",
                ):
                    _listening_tcp_ports(raw)


if __name__ == "__main__":
    unittest.main()
