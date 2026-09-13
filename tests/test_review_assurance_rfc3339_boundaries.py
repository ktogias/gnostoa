from __future__ import annotations

import unittest

from tools.review_model import RFC3339Timestamp, parse_rfc3339


class ReviewAssuranceRFC3339BoundaryTests(unittest.TestCase):
    def test_year_zero_is_supported_as_rfc3339_current_era(self) -> None:
        start = parse_rfc3339("0000-01-01T00:00:00Z")
        leap_day = parse_rfc3339("0000-02-29T00:00:00Z")
        year_one = parse_rfc3339("0001-01-01T00:00:00Z")

        self.assertIsInstance(start, RFC3339Timestamp)
        self.assertLess(start, leap_day)
        self.assertLess(leap_day, year_one)
        self.assertEqual(366 * 86_400, (year_one - start).total_seconds())

    def test_year_zero_calendar_validation_remains_strict(self) -> None:
        with self.assertRaises(ValueError):
            parse_rfc3339("0000-02-30T00:00:00Z")

    def test_minimum_python_datetime_year_with_large_positive_offset_is_exact_and_bounded(
        self,
    ) -> None:
        parsed = parse_rfc3339("0001-01-01T00:00:00+23:59")

        self.assertIsInstance(parsed, RFC3339Timestamp)
        self.assertLess(parsed, parse_rfc3339("0001-01-01T00:00:00Z"))

    def test_maximum_year_with_large_negative_offset_is_exact_and_bounded(self) -> None:
        parsed = parse_rfc3339("9999-12-31T23:59:59-23:59")

        self.assertIsInstance(parsed, RFC3339Timestamp)
        self.assertGreater(parsed, parse_rfc3339("9999-12-31T23:59:59Z"))


if __name__ == "__main__":
    unittest.main()
