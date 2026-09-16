from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from tools import review_outer
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

    def test_daemon_private_runtime_is_not_shared_with_outer(self) -> None:
        image = "ghcr.io/ktogias/gnostoa@sha256:" + "a" * 64
        socket_volume = "gnostoa-r2a-socket-test"
        plan = review_outer._build_isolated_execution_plan(
            consumer={"runtime_image": image},
            input_dir=Path("/tmp/gnostoa-r2a-input-test"),
            socket_volume=socket_volume,
            tmp_volume="gnostoa-r2a-tmp-test",
            daemon_name="gnostoa-r2a-daemon-test",
            outer_name="gnostoa-r2a-outer-test",
        )
        daemon_args = [str(item) for item in plan["daemon"]]
        outer_args = [str(item) for item in plan["outer"]]

        self.assertIn(f"{socket_volume}:/gnostoa-docker", daemon_args)
        self.assertNotIn(f"{socket_volume}:/var/run", daemon_args)
        self.assertEqual(
            1, daemon_args.count("--host=unix:///gnostoa-docker/docker.sock")
        )
        self.assertEqual(1, daemon_args.count("--group=10001"))
        self.assertIn(f"{socket_volume}:/var/run", outer_args)
        self.assertNotIn("/gnostoa-docker", " ".join(outer_args))

    def test_daemon_readiness_targets_dedicated_socket(self) -> None:
        ready = mock.Mock(returncode=0)
        config_dir = Path("/tmp/gnostoa-r2a-config-test")
        with mock.patch.object(review_outer, "_run_docker", return_value=ready) as run:
            review_outer._wait_for_daemon("gnostoa-r2a-daemon-test", config_dir)

        run.assert_called_once_with(
            [
                "exec",
                "gnostoa-r2a-daemon-test",
                "docker",
                "--host",
                "unix:///gnostoa-docker/docker.sock",
                "info",
            ],
            config_dir=config_dir,
            timeout=5,
        )


if __name__ == "__main__":
    unittest.main()
