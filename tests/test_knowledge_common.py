"""Small shared primitives of the toolkit's common module (#365)."""

from __future__ import annotations

import datetime
import pathlib
import re
import shutil
import unittest
from unittest import mock

from tools import knowledge_common


class UtcTimestampTests(unittest.TestCase):
    """One timestamp format for every command, instead of a copy in each (#365, I7)."""

    def test_the_timestamp_is_utc_to_the_second_with_a_z(self) -> None:
        before = datetime.datetime.now(datetime.UTC).replace(microsecond=0)
        stamp = knowledge_common.utc_timestamp()
        after = datetime.datetime.now(datetime.UTC)
        self.assertRegex(stamp, r"\A\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")
        moment = datetime.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        self.assertLessEqual(before, moment)
        self.assertLessEqual(moment, after)
        self.assertIsNone(re.search(r"\.\d", stamp))


class TrustedExecutableTests(unittest.TestCase):
    """A host tool is resolved from root-owned system directories only (#364)."""

    def test_the_directories_are_the_preparation_wrapper_s(self) -> None:
        """`ci/prepare-candidate` is shell and cannot import this; the two lists are
        held equal here instead of drifting apart."""
        wrapper = (
            pathlib.Path(__file__).resolve().parents[1] / "ci" / "prepare-candidate"
        ).read_text(encoding="utf-8")
        declared = re.search(r"^PATH=(\S+)$", wrapper, re.MULTILINE)
        if declared is None:
            self.fail("the preparation wrapper declares no trusted PATH")
        self.assertEqual(declared.group(1), knowledge_common.TRUSTED_EXECUTABLE_PATH)

    def test_the_caller_s_path_is_never_searched(self) -> None:
        with mock.patch.object(shutil, "which", return_value="/x/gh") as which:
            self.assertEqual("/x/gh", knowledge_common.trusted_executable("gh"))
        which.assert_called_once_with(
            "gh", path=knowledge_common.TRUSTED_EXECUTABLE_PATH
        )


if __name__ == "__main__":
    unittest.main()
