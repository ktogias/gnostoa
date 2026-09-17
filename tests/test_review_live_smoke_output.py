from __future__ import annotations

import contextlib
import importlib.util
import io
import unittest
from pathlib import Path
from types import ModuleType
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SMOKE_PATH = ROOT / "ci" / "review_live_smoke.py"
PAYLOAD_SENTINEL = "review-payload-marker-7f4e19"


def _load_smoke_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "gnostoa_review_live_smoke_output_test", SMOKE_PATH
    )
    if spec is None or spec.loader is None:
        raise AssertionError("cannot load protected current-advisory smoke module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _successful_payload() -> dict[str, object]:
    return {
        "outcome": "INCOMPLETE",
        "reason": "QUORUM_UNMET",
        "binding": False,
        "evaluation_context": {
            "mode": "current_advisory",
            "as_of": "2026-09-17T00:00:00Z",
            "judge_relation": "prior_integrated",
            "fixture_only": False,
        },
        "diagnostics": [
            "semantic predicates executed by protected prior-integrated OCI",
            PAYLOAD_SENTINEL,
        ],
        "retained_review_material": PAYLOAD_SENTINEL,
    }


class ReviewLiveSmokeOutputTests(unittest.TestCase):
    def test_success_emits_only_static_pass_marker(self) -> None:
        smoke = _load_smoke_module()
        output = io.StringIO()
        with (
            mock.patch.object(
                smoke,
                "evaluate_gnostoa_current_advisory",
                return_value=(3, _successful_payload()),
            ),
            contextlib.redirect_stdout(output),
        ):
            code = smoke.main()

        self.assertEqual(0, code)
        self.assertEqual("protected current-advisory smoke: PASS\n", output.getvalue())
        self.assertNotIn(PAYLOAD_SENTINEL, output.getvalue())

    def test_failures_preserve_safe_category_without_payload_material(self) -> None:
        smoke = _load_smoke_module()
        cases = (
            (2, {"retained_review_material": PAYLOAD_SENTINEL}, "got 2"),
            (
                3,
                {
                    **_successful_payload(),
                    "outcome": "BLOCKED",
                    "reason": PAYLOAD_SENTINEL,
                },
                "truthful quorum state",
            ),
        )

        for code, payload, expected_message in cases:
            with self.subTest(code=code, expected_message=expected_message):
                with mock.patch.object(
                    smoke,
                    "evaluate_gnostoa_current_advisory",
                    return_value=(code, payload),
                ):
                    with self.assertRaises(RuntimeError) as caught:
                        smoke.main()
                message = str(caught.exception)
                self.assertIn(expected_message, message)
                self.assertNotIn(PAYLOAD_SENTINEL, message)


if __name__ == "__main__":
    unittest.main()
