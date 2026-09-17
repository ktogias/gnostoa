from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import security_scan
from tools.extended_route import route_extended
from tools.repository_scope import RepositoryScopeError
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
                "tools.security_scan._run_bounded_scan",
                return_value=completed,
            ) as run:
                result = scan_tracked_tree(
                    root,
                    report_path=evidence,
                    tracked_paths=[Path(".secrets.baseline"), Path("tracked.txt")],
                )

            command = run.call_args.args[0]
            self.assertEqual(300, run.call_args.kwargs["timeout"])
            self.assertEqual(1, command.count("--exclude-files"))
            self.assertEqual(
                r"^\.secrets\.baseline$",
                command[command.index("--exclude-files") + 1],
            )
            separator = command.index("--")
            self.assertEqual(
                [".secrets.baseline", "tracked.txt"],
                command[separator + 1 :],
            )
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
            (root / adversarial_path).write_text("marker\n", encoding="utf-8")
            (root / "secret.txt").write_text("candidate\n", encoding="utf-8")

            with mock.patch(
                "tools.security_scan._run_bounded_scan",
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

    def test_invalid_utf8_scanner_output_is_normalized(self) -> None:
        baseline = _report({})

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".secrets.baseline").write_text(
                json.dumps(baseline),
                encoding="utf-8",
            )
            (root / "tracked.txt").write_text("candidate\n", encoding="utf-8")
            completed = subprocess.CompletedProcess(
                ["detect-secrets"],
                0,
                b"\xff",
                b"",
            )

            with mock.patch(
                "tools.security_scan._run_bounded_scan",
                return_value=completed,
            ):
                with self.assertRaisesRegex(SecurityScanError, "invalid JSON"):
                    scan_tracked_tree(root, tracked_paths=[Path("tracked.txt")])

    def test_scanner_reads_an_immutable_private_snapshot(self) -> None:
        baseline = _report({})

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = root / "tracked.txt"
            candidate.write_text("original candidate\n", encoding="utf-8")
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
            observed_snapshot: Path | None = None

            def run_from_snapshot(
                command: list[str],
                *,
                cwd: Path,
                timeout: int,
            ) -> subprocess.CompletedProcess[bytes]:
                nonlocal observed_snapshot
                observed_snapshot = cwd
                self.assertNotEqual(root, cwd)
                self.assertEqual(
                    "original candidate\n",
                    (cwd / "tracked.txt").read_text(encoding="utf-8"),
                )
                candidate.write_text("concurrent replacement\n", encoding="utf-8")
                self.assertEqual(
                    "original candidate\n",
                    (cwd / "tracked.txt").read_text(encoding="utf-8"),
                )
                return completed

            with mock.patch(
                "tools.security_scan._run_bounded_scan",
                side_effect=run_from_snapshot,
            ):
                scan_tracked_tree(root, tracked_paths=[Path("tracked.txt")])

            self.assertIsNotNone(observed_snapshot)
            assert observed_snapshot is not None
            self.assertFalse(observed_snapshot.exists())

    @unittest.skipUnless(
        hasattr(os, "mkfifo") and hasattr(os, "O_NONBLOCK"),
        "FIFO race regression requires POSIX non-blocking opens",
    )
    def test_fifo_replacement_before_snapshot_open_fails_without_blocking(
        self,
    ) -> None:
        baseline = _report({})

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate_path = Path("tracked.txt")
            candidate = root / candidate_path
            candidate.write_text("candidate\n", encoding="utf-8")
            (root / ".secrets.baseline").write_text(
                json.dumps(baseline),
                encoding="utf-8",
            )
            real_validate = security_scan._validated_candidate_paths
            real_open = os.open
            replaced = False

            def validate_then_replace(
                candidate_root: Path,
                paths: list[Path],
            ) -> list[Path]:
                nonlocal replaced
                validated = real_validate(candidate_root, paths)
                if (
                    candidate_root == root
                    and paths == [candidate_path]
                    and not replaced
                ):
                    candidate.unlink()
                    os.mkfifo(candidate)
                    replaced = True
                return validated

            def require_nonblocking_open(
                path: str | bytes | Path,
                flags: int,
                mode: int = 0o777,
                *,
                dir_fd: int | None = None,
            ) -> int:
                if path == candidate_path.name and dir_fd is not None:
                    self.assertTrue(flags & os.O_NONBLOCK)
                return real_open(path, flags, mode, dir_fd=dir_fd)

            with (
                mock.patch(
                    "tools.security_scan._validated_candidate_paths",
                    side_effect=validate_then_replace,
                ),
                mock.patch(
                    "tools.security_scan.os.open",
                    side_effect=require_nonblocking_open,
                ),
                self.assertRaisesRegex(SecurityScanError, "not a regular file"),
            ):
                scan_tracked_tree(root, tracked_paths=[candidate_path])

    def test_candidate_scope_errors_are_reported_as_security_scan_errors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with mock.patch(
                "tools.security_scan.candidate_paths",
                side_effect=RepositoryScopeError("candidate enumeration failed"),
            ):
                with self.assertRaisesRegex(
                    SecurityScanError,
                    "cannot enumerate tracked-tree candidates",
                ):
                    scan_tracked_tree(root)

    def test_caller_paths_must_be_repository_relative_regular_files(self) -> None:
        baseline = _report({})

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".secrets.baseline").write_text(
                json.dumps(baseline),
                encoding="utf-8",
            )
            (root / "directory").mkdir()

            for candidate, expected in (
                (Path("/outside-repository"), "unsafe candidate path"),
                (Path("directory"), "not a regular file"),
                (Path("missing.txt"), "cannot inspect candidate path"),
            ):
                with self.subTest(candidate=candidate):
                    with self.assertRaisesRegex(SecurityScanError, expected):
                        scan_tracked_tree(root, tracked_paths=[candidate])

    def test_protected_baseline_file_identity_is_bound(self) -> None:
        relative = Path(PROTECTED_BASELINE_PATH)
        baseline = _report(
            {
                relative.as_posix(): [
                    _candidate(PUBLIC_HASH, line=1, false_positive=True)
                ]
            }
        )
        approved = b"approved protected authority\n"

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / relative).parent.mkdir(parents=True)
            (root / relative).write_bytes(b"modified protected authority\n")
            (root / ".secrets.baseline").write_text(
                json.dumps(baseline),
                encoding="utf-8",
            )
            expected = hashlib.sha256(approved).hexdigest()

            with mock.patch.dict(
                security_scan._PROTECTED_BASELINE_FILE_SHA256,
                {relative.as_posix(): expected},
                clear=True,
            ):
                with self.assertRaisesRegex(
                    SecurityScanError,
                    "protected baseline file identity changed",
                ):
                    scan_tracked_tree(root, tracked_paths=[relative])

    def test_scanner_output_is_bounded_while_it_is_read(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            for stream, expected in (
                ("stdout", "report exceeds the bound"),
                ("stderr", "diagnostics exceeds the bound"),
            ):
                script = f"import sys; sys.{stream}.buffer.write(b'x' * 65)"
                with self.subTest(stream=stream):
                    with mock.patch.object(security_scan, "_MAX_REPORT_BYTES", 64):
                        with self.assertRaisesRegex(SecurityScanError, expected):
                            security_scan._run_bounded_scan(
                                [sys.executable, "-c", script],
                                cwd=Path(directory),
                                timeout=5,
                            )

    def test_baseline_input_is_bounded_and_invalid_utf8_is_normalized(self) -> None:
        bounded_stream = mock.MagicMock()
        bounded_stream.__enter__.return_value = bounded_stream
        bounded_stream.read.return_value = b"x" * 65
        with (
            mock.patch.object(Path, "open", return_value=bounded_stream),
            mock.patch.object(security_scan, "_MAX_REPORT_BYTES", 64),
        ):
            with self.assertRaisesRegex(SecurityScanError, "exceeds the bounded size"):
                security_scan._read_document(Path("baseline.json"), "baseline")
        bounded_stream.read.assert_called_once_with(65)

        with tempfile.TemporaryDirectory() as directory:
            baseline = Path(directory) / "baseline.json"
            baseline.write_bytes(b'{{"results":"\xff"}}')
            with self.assertRaisesRegex(SecurityScanError, "cannot read baseline"):
                security_scan._read_document(baseline, "baseline")


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
            ".github/CODEOWNERS",
            ".gitlab-ci.yml",
            ".secrets.baseline",
            "requirements/development.lock",
            "knowledge/decisions/example.md",
            "policy/guardrails.yaml",
            "tasks/protected.json",
            "docs/status.md",
            "Dockerfile",
            "pyproject.toml",
        ):
            with self.subTest(path=path):
                result = route_extended("pull_request", (path,))
                self.assertEqual("RUN", result.decision)
                self.assertEqual("applicable high-risk changed path", result.reason)

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
    def test_retained_secret_triage_evidence_is_sanitized_and_complete(self) -> None:
        evidence = json.loads(
            (
                ROOT
                / "knowledge"
                / "assessments"
                / "0082-secret-scan-triage-evidence.json"
            ).read_text(encoding="utf-8")
        )

        self.assertEqual(21, evidence["source"]["finding_count"])
        self.assertEqual(21, len(evidence["findings"]))
        self.assertEqual(
            "gnostoa-secret-scan-triage-evidence/v2",
            evidence["manifest_schema"],
        )
        self.assertEqual(
            "".join(("e071ab60", "a418eddd", "a5bf0080", "04ee96fa", "afbf1e7c")),
            "".join(evidence["source_binding"]["head_commit_hex_chunks"]),
        )
        self.assertEqual(
            "".join(("46df4deb", "2b73579c", "fd4e8d43", "678ed002", "4722fe0e")),
            "".join(evidence["source_binding"]["head_tree_hex_chunks"]),
        )
        self.assertEqual("schedule", evidence["source_binding"]["event"])
        self.assertEqual(1, evidence["source_binding"]["run_attempt"])
        self.assertLessEqual(
            evidence["observation_cut"]["started_at"],
            evidence["observation_cut"]["completed_at"],
        )
        self.assertEqual(
            ["path", "line", "type"],
            evidence["extraction"]["sort_order"],
        )
        self.assertEqual(
            evidence["findings"],
            sorted(
                evidence["findings"],
                key=lambda item: (item["path"], item["line"], item["type"]),
            ),
        )
        self.assertEqual(
            {"line", "path", "type"},
            set().union(*(finding.keys() for finding in evidence["findings"])),
        )
        rendered = json.dumps(evidence)
        self.assertNotIn("hashed_secret", rendered)
        self.assertNotIn("candidate_text", rendered)

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
