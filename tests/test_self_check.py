"""What `knowledge self-check` reports for each of its checks, and when it fails."""

from __future__ import annotations

import contextlib
import io
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import call, patch

from tools.knowledge_common import KnowledgeFormatError
from tools.self_check import self_check

ROOT = Path(__file__).resolve().parents[1]


def _run(**results: object) -> tuple[bool, list[str], list[str]]:
    """``self_check`` with each check's result replaced, without the suite; its
    verdict and its standard output and error, line by line."""
    out, err = io.StringIO(), io.StringIO()
    with (
        patch(
            "tools.self_check.validate_bundle",
            side_effect=results.get("bundles", lambda *_a, **_k: (None, [])),
        ),
        patch(
            "tools.self_check.check_guardrails",
            return_value=results.get("guardrails", []),
        ),
        patch(
            "tools.self_check.check_change_policy",
            side_effect=results.get("change", lambda _path: []),
        ),
        patch(
            "tools.self_check.check_ci_policy",
            side_effect=results.get("ci", lambda _policy, _verification: []),
        ),
        contextlib.redirect_stdout(out),
        contextlib.redirect_stderr(err),
    ):
        verdict = self_check(ROOT, run_tests=False)
    return verdict, out.getvalue().splitlines(), err.getvalue().splitlines()


class SelfCheckReportTests(unittest.TestCase):
    def test_every_check_passing_reports_each_and_passes(self) -> None:
        verdict, out, err = _run()
        self.assertTrue(verdict)
        self.assertEqual(
            [
                "OK: generic example",
                "OK: module example",
                "OK: reusable guidance",
                "OK: toolkit self-knowledge",
                "OK: guardrail coverage",
                "OK: generic change control",
                "OK: toolkit change control",
                "OK: generic CI policy",
                "OK: toolkit CI policy",
            ],
            out,
        )
        self.assertEqual([], err)

    def test_every_check_failing_reports_each_issue_and_fails(self) -> None:
        def bundles(_profile: Path, bundle: Path, **_kwargs: object) -> object:
            if bundle.name != "guidance":
                return None, []
            return None, [
                SimpleNamespace(severity="warning", path="a.md", message="soft"),
                SimpleNamespace(severity="error", path="b.md", message="hard"),
            ]

        def change(path: Path) -> list[str]:
            if path.parent.name == "core":
                raise KnowledgeFormatError("unreadable")
            return ["p1", "p2"]

        def ci(policy: Path, _verification: Path | None) -> list[str]:
            if policy.parent.name == "core":
                raise OSError("gone")
            raise ValueError("odd")

        verdict, out, err = _run(
            bundles=bundles, guardrails=["g1"], change=change, ci=ci
        )
        self.assertFalse(verdict)
        self.assertEqual(
            ["OK: generic example", "OK: module example", "OK: toolkit self-knowledge"],
            out,
        )
        self.assertEqual(
            [
                "ERROR: reusable guidance: b.md: hard",
                "ERROR: guardrails: g1",
                "ERROR: generic change control: unreadable",
                "ERROR: toolkit change control: p1",
                "ERROR: toolkit change control: p2",
                "ERROR: generic CI policy: gone",
                "ERROR: toolkit CI policy: odd",
            ],
            err,
        )

    def test_one_failing_check_fails_the_whole(self) -> None:
        for name, failure in (
            (
                "bundles",
                lambda *_a, **_k: (
                    None,
                    [SimpleNamespace(severity="error", path="x", message="y")],
                ),
            ),
            ("guardrails", ["g"]),
            ("change", lambda _path: ["c"]),
            ("ci", lambda _policy, _verification: ["c"]),
        ):
            with self.subTest(check=name):
                verdict, _, err = _run(**{name: failure})
                self.assertFalse(verdict)
                self.assertTrue(err)

    def test_a_failing_bundle_is_not_hidden_by_a_later_one(self) -> None:
        def first_fails(_profile: Path, bundle: Path, **_kwargs: object) -> object:
            if bundle.name != "generic":
                return None, []
            return None, [SimpleNamespace(severity="error", path="x", message="y")]

        verdict, _, err = _run(bundles=first_fails)
        self.assertFalse(verdict)
        self.assertEqual(["ERROR: generic example: x: y"], err)

    def test_each_policy_is_read_from_the_root(self) -> None:
        root = ROOT.resolve()
        with (
            patch("tools.self_check.validate_bundle", return_value=(None, [])),
            patch("tools.self_check.check_guardrails", return_value=[]) as guardrails,
            patch("tools.self_check.check_change_policy", return_value=[]) as change,
            patch("tools.self_check.check_ci_policy", return_value=[]) as ci,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertTrue(self_check(ROOT, run_tests=False))
        guardrails.assert_called_once_with(root / "policy" / "guardrails.yaml", root)
        self.assertEqual(
            [
                call(root / "core/change-control.yaml"),
                call(root / "policy/change-control.yaml"),
            ],
            change.call_args_list,
        )
        self.assertEqual(
            [
                call(root / "core/continuous-integration.yaml", None),
                call(
                    root / "policy/continuous-integration.yaml",
                    root / "policy/verification.yaml",
                ),
            ],
            ci.call_args_list,
        )


if __name__ == "__main__":
    unittest.main()
