from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.extended_route import route_extended
from tools.security_scan import (
    SecurityScanError,
    evaluate_secret_report,
    scan_tracked_tree,
)

ROOT = Path(__file__).resolve().parents[1]
PROTECTED_BASELINE_PATH = "tasks/issue-11-r2a-current-advisory.json"
PUBLIC_HASH = "a" * 40
UNKNOWN_HASH = "b" * 40
STALE_HASH = "c" * 40
CANDIDATE_HASH = "d" * 40


def _report(results: dict[str, list[dict[str, object]]]) -> dict[str, object]:
    return {
        "version": "1.5.0",
        "plugins_used": [{"name": "HexHighEntropyString"}],
        "filters_used": [],
        "results": results,
    }


def _candidate(
    secret_hash: str,
    *,
    line: int = 1,
    false_positive: bool | None = None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "type": "Hex High Entropy String",
        "filename": "ignored-by-format",
        "hashed_secret": secret_hash,
        "line_number": line,
    }
    if false_positive is not None:
        result["is_secret"] = not false_positive
        result["is_verified"] = False
    return result


class SecretBaselineTests(unittest.TestCase):
    def test_exact_false_positive_suppresses_only_matching_path_and_hash(self) -> None:
        scan = _report(
            {
                PROTECTED_BASELINE_PATH: [_candidate(PUBLIC_HASH, line=12)],
                "tools/new.py": [_candidate(UNKNOWN_HASH, line=9)],
            }
        )
        baseline = _report(
            {
                PROTECTED_BASELINE_PATH: [
                    _candidate(PUBLIC_HASH, line=12, false_positive=True)
                ]
            }
        )

        result = evaluate_secret_report(scan, baseline)

        self.assertEqual(1, result.reviewed_false_positives)
        self.assertEqual(
            [
                {
                    "line": 9,
                    "path": "tools/new.py",
                    "type": "Hex High Entropy String",
                }
            ],
            result.unresolved_findings,
        )
        self.assertNotIn(UNKNOWN_HASH, repr(result))

    def test_same_hash_on_another_path_is_not_suppressed(self) -> None:
        scan = _report({"tools/new.py": [_candidate(PUBLIC_HASH, line=7)]})
        baseline = _report(
            {
                PROTECTED_BASELINE_PATH: [
                    _candidate(PUBLIC_HASH, line=12, false_positive=True)
                ]
            }
        )

        with self.assertRaisesRegex(SecurityScanError, "stale"):
            evaluate_secret_report(scan, baseline)

    def test_baseline_rejects_unreviewed_or_stale_entries(self) -> None:
        scan = _report({PROTECTED_BASELINE_PATH: [_candidate(PUBLIC_HASH, line=12)]})
        unreviewed = _report(
            {PROTECTED_BASELINE_PATH: [_candidate(PUBLIC_HASH, line=12)]}
        )
        with self.assertRaisesRegex(SecurityScanError, "false positive"):
            evaluate_secret_report(scan, unreviewed)

        stale = _report(
            {
                PROTECTED_BASELINE_PATH: [
                    _candidate(STALE_HASH, line=12, false_positive=True)
                ]
            }
        )
        with self.assertRaisesRegex(SecurityScanError, "stale"):
            evaluate_secret_report(scan, stale)

        unauthorized = _report(
            {
                "tools/example.py": [
                    _candidate(PUBLIC_HASH, line=12, false_positive=True)
                ]
            }
        )
        with self.assertRaisesRegex(SecurityScanError, "unauthorized"):
            evaluate_secret_report(
                _report({"tools/example.py": [_candidate(PUBLIC_HASH, line=12)]}),
                unauthorized,
            )

    def test_tracked_scan_excludes_only_its_manifest_and_writes_sanitized_evidence(
        self,
    ) -> None:
        filters = [
            {
                "path": "detect_secrets.filters.regex.should_exclude_file",
                "pattern": [r"^\.secrets\.baseline$"],
            }
        ]
        scan = _report({"tracked.txt": [_candidate(CANDIDATE_HASH, line=3)]})
        scan["filters_used"] = filters
        baseline = _report({})
        baseline["filters_used"] = filters

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "tracked.txt").write_text("candidate\n", encoding="utf-8")
            (root / ".secrets.baseline").write_text(
                json.dumps(baseline),
                encoding="utf-8",
            )
            evidence = root / "sanitized.json"
            completed = subprocess.CompletedProcess(
                ["detect-secrets"],
                0,
                json.dumps(scan).encode("utf-8"),
                b"",
            )

            with mock.patch(
                "tools.security_scan.subprocess.run",
                return_value=completed,
            ) as run:
                result = scan_tracked_tree(
                    root,
                    report_path=evidence,
                    tracked_paths=[Path(".secrets.baseline"), Path("tracked.txt")],
                )

            command = run.call_args.args[0]
            self.assertEqual(300, run.call_args.kwargs["timeout"])
            self.assertEqual(
                r"^\.secrets\.baseline$",
                command[command.index("--exclude-files") + 1],
            )
            self.assertIn(".secrets.baseline", command)
            self.assertEqual(1, len(result.unresolved_findings))
            rendered = evidence.read_text(encoding="utf-8")
            self.assertNotIn(CANDIDATE_HASH, rendered)
            self.assertIn('"path": "tracked.txt"', rendered)

    def test_tracked_scan_terminates_options_before_candidate_paths(self) -> None:
        baseline = _report({})

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".secrets.baseline").write_text(
                json.dumps(baseline),
                encoding="utf-8",
            )
            completed = subprocess.CompletedProcess(
                ["detect-secrets"],
                0,
                json.dumps(baseline).encode("utf-8"),
                b"",
            )
            adversarial_path = Path("--exclude-files=^secret.txt$")

            with mock.patch(
                "tools.security_scan.subprocess.run",
                return_value=completed,
            ) as run:
                scan_tracked_tree(
                    root,
                    tracked_paths=[adversarial_path, Path("secret.txt")],
                )

            command = run.call_args.args[0]
            separator = command.index("--")
            self.assertEqual(
                [adversarial_path.as_posix(), "secret.txt"],
                command[separator + 1 :],
            )


class ExtendedRoutingTests(unittest.TestCase):
    def test_schedule_and_manual_dispatch_always_run(self) -> None:
        for event in ("schedule", "workflow_dispatch"):
            with self.subTest(event=event):
                result = route_extended(event, ())
                self.assertEqual("RUN", result.decision)

    def test_high_risk_candidate_paths_run(self) -> None:
        for path in (
            "tools/review_current.py",
            "ci/verify",
            ".github/workflows/verification.yml",
            "requirements/development.lock",
            "knowledge/decisions/example.md",
            "tasks/protected.json",
            "docs/status.md",
            "Dockerfile",
            "pyproject.toml",
        ):
            with self.subTest(path=path):
                result = route_extended("pull_request", (path,))
                self.assertEqual("RUN", result.decision)
                self.assertIn(path, result.reason)

    def test_only_protected_integration_push_runs(self) -> None:
        protected = route_extended(
            "push",
            ("tools/review_current.py",),
            ref_name="refs/heads/main",
        )
        topic = route_extended(
            "push",
            ("tools/review_current.py",),
            ref_name="refs/heads/topic",
        )

        self.assertEqual("RUN", protected.decision)
        self.assertEqual("NOT_APPLICABLE", topic.decision)
        self.assertIn("protected integration", topic.reason)

    def test_low_risk_or_empty_change_is_explicitly_not_applicable(self) -> None:
        for paths in ((), ("LICENSE",), (".github/ISSUE_TEMPLATE/question.yml",)):
            with self.subTest(paths=paths):
                result = route_extended("pull_request", paths)
                self.assertEqual("NOT_APPLICABLE", result.decision)
                self.assertTrue(result.reason)

    def test_unknown_event_is_not_silently_run(self) -> None:
        result = route_extended("unexpected", ("tools/example.py",))
        self.assertEqual("NOT_APPLICABLE", result.decision)
        self.assertIn("unsupported", result.reason)

    def test_unsafe_changed_path_fails_closed(self) -> None:
        for path in (
            "../tools/review_current.py",
            "/tools/review_current.py",
            "bad\npath",
            "bad\tpath",
        ):
            with self.subTest(path=path):
                with self.assertRaisesRegex(ValueError, "unsafe"):
                    route_extended("pull_request", (path,))


class ProviderSecurityGateTests(unittest.TestCase):
    def test_pr_security_gate_and_extended_router_are_explicit(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "verification.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("\n  security-fast:\n", workflow)
        self.assertIn("./ci/verify security-fast", workflow)
        self.assertIn(
            "needs: [policy, security-fast, fast, python-compatibility, "
            "extended-route, extended]",
            workflow,
        )
        self.assertIn('test "${SECURITY_FAST_RESULT}" = success', workflow)
        self.assertIn("\n  extended-route:\n", workflow)
        self.assertIn("git diff --name-only -z", workflow)
        self.assertIn("python -m tools.extended_route", workflow)
        self.assertIn("needs: [policy, extended-route]", workflow)
        self.assertIn(
            "needs.extended-route.outputs.run_extended == 'true'",
            workflow,
        )
        self.assertIn('case "${EXTENDED_DECISION}" in', workflow)
        self.assertIn('test "${EXTENDED_RESULT}" = success', workflow)
        self.assertIn('test "${EXTENDED_RESULT}" = skipped', workflow)
        self.assertNotIn(
            "if: github.event_name == 'schedule' || "
            "github.event_name == 'workflow_dispatch'",
            workflow,
        )


if __name__ == "__main__":
    unittest.main()
