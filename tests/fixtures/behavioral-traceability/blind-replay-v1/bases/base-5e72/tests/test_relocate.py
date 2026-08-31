import unittest
from unittest.mock import Mock

from src.relocate import Item, relocate


class RelocateTests(unittest.TestCase):
    def test_different_destination(self) -> None:
        item = Item(id=7, parent_id=4, label="Reports")
        mutate = Mock()

        relocate(item, 9, mutate)

        mutate.assert_called_once_with(item.id, 9, item.label)


if __name__ == "__main__":
    unittest.main()
