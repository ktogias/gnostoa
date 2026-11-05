"""What other test modules share from tests/test_quality_evidence_profile.py, outside the discovered test modules (#389 N1b; Decision 0128)."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch


def _original(module: object, name: str) -> Any:
    """`module`'s own `name`, as unittest.mock hands an original to new_callable under spec=True, so no private
    attribute is named (the fixtures' own pattern, #389 6480056885)."""
    found: list[object] = []

    def kept(*, spec: object) -> object:
        found.append(spec)
        return spec

    with patch.object(module, name, spec=True, new_callable=kept):
        pass
    return found[0]
