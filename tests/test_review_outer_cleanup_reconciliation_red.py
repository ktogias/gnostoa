from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from tools import review_outer


class ReviewOuterCleanupReconciliationTests(unittest.TestCase):
    def test_lowercase_missing_volume_is_successful_reconciliation(self) -> None:
        absent = mock.Mock(
            returncode=1,
            stderr=(
                b"Error response from daemon: get gnostoa-r2a-test: no such volume"
            ),
        )

        with mock.patch.object(review_outer, "_run_docker", return_value=absent) as run:
            issue = review_outer._remove_volume(
                "gnostoa-r2a-test", Path("/tmp/docker-config")
            )

        self.assertIsNone(issue)
        run.assert_called_once_with(
            ["volume", "rm", "gnostoa-r2a-test"],
            config_dir=Path("/tmp/docker-config"),
            timeout=30,
        )

    def test_lowercase_missing_container_is_successful_reconciliation(self) -> None:
        absent = mock.Mock(
            returncode=1,
            stderr=b"Error response from daemon: no such container: gnostoa-r2a-test",
        )

        with mock.patch.object(review_outer, "_run_docker", return_value=absent) as run:
            issue = review_outer._remove_container(
                "gnostoa-r2a-test", Path("/tmp/docker-config")
            )

        self.assertIsNone(issue)
        run.assert_called_once_with(
            ["rm", "-f", "gnostoa-r2a-test"],
            config_dir=Path("/tmp/docker-config"),
            timeout=30,
        )

    def test_nonmissing_volume_failure_retries_and_fails_closed(self) -> None:
        busy = mock.Mock(returncode=1, stderr=b"volume is in use")
        with (
            mock.patch.object(review_outer, "_run_docker", return_value=busy) as run,
            mock.patch.object(review_outer.time, "sleep") as sleep,
        ):
            issue = review_outer._remove_volume(
                "gnostoa-r2a-test", Path("/tmp/docker-config")
            )

        self.assertIsNotNone(issue)
        assert issue is not None
        self.assertIn("volume is in use", issue)
        self.assertEqual(review_outer._CLEANUP_ATTEMPTS, run.call_count)
        self.assertEqual(review_outer._CLEANUP_ATTEMPTS - 1, sleep.call_count)


if __name__ == "__main__":
    unittest.main()
