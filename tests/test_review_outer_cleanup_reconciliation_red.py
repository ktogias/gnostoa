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
                b"Error response from daemon: get gnostoa-r2a-test: "
                b"no such volume"
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


if __name__ == "__main__":
    unittest.main()
