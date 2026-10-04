"""Small shared primitives of the toolkit's common module (#365)."""

from __future__ import annotations

import datetime
import re
import unittest

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


if __name__ == "__main__":
    unittest.main()
