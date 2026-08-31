from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class Item:
    id: int
    parent_id: int | None
    label: str


def relocate(
    item: Item,
    destination_id: int | None,
    mutate: Callable[[int, int | None, str], None],
) -> None:
    normalized_label = item.label.strip()
    mutate(item.id, destination_id, normalized_label)
