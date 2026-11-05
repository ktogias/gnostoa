"""What other test modules share from tests/test_security_gates.py, outside the discovered test modules (#389 N1b; Decision 0128)."""

from __future__ import annotations


def _report(results: dict[str, list[dict[str, object]]]) -> dict[str, object]:
    return {
        "version": "1.5.0",
        "plugins_used": [{"name": "HexHighEntropyString"}],
        "filters_used": [],
        "results": results,
        "generated_at": "2026-09-17T14:33:10Z",
    }
