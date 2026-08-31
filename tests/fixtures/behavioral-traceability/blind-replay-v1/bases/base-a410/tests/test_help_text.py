import unittest

from src.help_text import HELP_TEXT

EXPECTED_HELP = """Move an item.

Destination:
  container identifier
"""


class HelpTextTests(unittest.TestCase):
    def test_move_help_snapshot(self) -> None:
        self.assertEqual(EXPECTED_HELP, HELP_TEXT)


if __name__ == "__main__":
    unittest.main()
