"""#389 F3 calibration fixture (never merged): the same table typed, as the 7fbe537 fix
typed it; DeepSource reported nothing there."""

from __future__ import annotations

from typing import Any


def _forwarding_problems(caller: dict[str, Any], callee: dict[str, Any]) -> list[str]:
    return [] if caller == callee else ["differs"]


def check() -> None:
    caller: dict[str, Any] = {"uses": "readback"}
    callee: dict[str, Any] = {"on": "workflow_call"}
    variants: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {
        "no secrets": ({"uses": "readback"}, callee),
        "no declaration": (caller, {}),
    }
    for _label, (variant_caller, variant_callee) in variants.items():
        _forwarding_problems(variant_caller, variant_callee)
