"""What other test modules share from tests/test_exact_tree_reuse.py, outside the discovered test modules (#389 N1b; Decision 0128)."""

from __future__ import annotations

import os
import unittest


def _open_descriptors(case: unittest.TestCase) -> int:
    """This process's open descriptors, as Linux and macOS both list them."""
    for listing in ("/dev/fd", "/proc/self/fd"):
        if os.path.isdir(listing):
            return len(os.listdir(listing))
    case.skipTest("this platform lists no open descriptors")
