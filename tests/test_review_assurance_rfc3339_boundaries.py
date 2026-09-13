from __future__ import annotations

import unittest

from tools.review_model import RFC3339Timestamp, parse_rfc3339


class ReviewAssuranceRFC3339BoundaryTests(unittest.TestCase):
    def test_minimum_year_with_large_positive_offset_is_exact_and_bounded(self) -> None:
        parsed = parse_rfc3339("0001-01-01T00:00:00+23:59")

        self.assertIsInstance(parsed, RFC3339Timestamp)
        self.assertLess(parsed, parse_rfc3339("0001-01-01T00:00:00Z"))

    def test_maximum_year_with_large_negative_offset_is_exact_and_bounded(self) -> None:
        parsed = parse_rfc3339("9999-12-31T23:59:59-23:59")

        self.assertIsInstance(parsed, RFC3339Timestamp)
        self.assertGreater(parsed, parse_rfc3339("9999-12-31T23:59:59Z"))


if __name__ == "__main__":
    unittest.main()
