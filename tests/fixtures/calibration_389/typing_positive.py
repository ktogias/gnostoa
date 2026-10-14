"""#389 F3 calibration fixture (never merged): the 2bcb622 shape DeepSource reported as
TYP-050, an untyped variant table passed to a typed checker."""

from __future__ import annotations

from typing import Any


def _forwarding_problems(caller: dict[str, Any], callee: dict[str, Any]) -> list[str]:
    return [] if caller == callee else ["differs"]


def check() -> None:
    caller: dict[str, Any] = {"uses": "readback"}
    callee: dict[str, Any] = {"on": "workflow_call"}
    variants = {
        "no secrets": ({"uses": "readback"}, callee),
        "no declaration": (caller, None),
    }
    for _label, (variant_caller, variant_callee) in variants.items():
        _forwarding_problems(variant_caller, variant_callee)
