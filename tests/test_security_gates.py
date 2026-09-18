from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path, PurePosixPath
from unittest import mock

from tools import security_scan
from tools.extended_route import route_extended
from tools.knowledge_common import load_yaml
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
        "generated_at": "2026-09-17T14:33:10Z",
    }


def _candidate(
    secret_hash: str,
    *,
    line: int = 1,
    filename: str = PROTECTED_BASELINE_PATH,
    false_positive: bool | None = None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "type": "Hex High Entropy String",
        "filename": filename,
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
                "tools/new.py": [
                    _candidate(UNKNOWN_HASH, line=9, filename="tools/new.py")
                ],
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
        scan = _report(
            {"tools/new.py": [_candidate(PUBLIC_HASH, line=7, filename="tools/new.py")]}
        )
        baseline = _report(
            {
                PROTECTED_BASELINE_PATH: [
                    _candidate(PUBLIC_HASH, line=12, false_positive=True)
                ]
            }
        )

        with self.assertRaisesRegex(SecurityScanError, "stale"):
            evaluate_secret_report(scan, baseline)

    def test_false_positive_identity_binds_the_exact_bounded_line(self) -> None:
        scan = _report({PROTECTED_BASELINE_PATH: [_candidate(PUBLIC_HASH, line=12)]})
        wrong_line = _report(
            {
                PROTECTED_BASELINE_PATH: [
                    _candidate(PUBLIC_HASH, line=13, false_positive=True)
                ]
            }
        )
        with self.assertRaisesRegex(SecurityScanError, "stale"):
            evaluate_secret_report(scan, wrong_line)

        oversized_line = _report(
            {
                PROTECTED_BASELINE_PATH: [
                    _candidate(
                        PUBLIC_HASH,
                        line=security_scan._MAX_SNAPSHOT_FILE_BYTES + 1,
                        false_positive=True,
                    )
                ]
            }
        )
        with self.assertRaisesRegex(SecurityScanError, "identity is malformed"):
            evaluate_secret_report(scan, oversized_line)

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
                    _candidate(
                        PUBLIC_HASH,
                        line=12,
                        filename="tools/example.py",
                        false_positive=True,
                    )
                ]
            }
        )
        with self.assertRaisesRegex(SecurityScanError, "unauthorized"):
            evaluate_secret_report(
                _report(
                    {
                        "tools/example.py": [
                            _candidate(
                                PUBLIC_HASH,
                                line=12,
                                filename="tools/example.py",
                            )
                        ]
                    }
                ),
                unauthorized,
            )

    def test_baseline_schema_rejects_unvalidated_content(self) -> None:
        scan = _report({})
        for field, value in (
            ("unvalidated_extra", "candidate-controlled content"),
            ("generated_at", "not-a-timestamp"),
        ):
            with self.subTest(field=field):
                baseline = _report({})
                baseline[field] = value
                with self.assertRaisesRegex(SecurityScanError, "baseline schema"):
                    evaluate_secret_report(scan, baseline)

        candidate = _candidate(PUBLIC_HASH, line=12, false_positive=True)
        candidate["unvalidated_extra"] = "candidate-controlled content"
        baseline = _report({PROTECTED_BASELINE_PATH: [candidate]})
        with self.assertRaisesRegex(SecurityScanError, "baseline schema"):
            evaluate_secret_report(
                _report({PROTECTED_BASELINE_PATH: [_candidate(PUBLIC_HASH, line=12)]}),
                baseline,
            )

        candidate = _candidate(PUBLIC_HASH, line=12, false_positive=True)
        candidate["is_verified"] = "candidate-controlled content"
        baseline = _report({PROTECTED_BASELINE_PATH: [candidate]})
        with self.assertRaisesRegex(SecurityScanError, "baseline schema"):
            evaluate_secret_report(
                _report({PROTECTED_BASELINE_PATH: [_candidate(PUBLIC_HASH, line=12)]}),
                baseline,
            )

    def test_json_reader_rejects_duplicate_fields_at_every_depth(self) -> None:
        documents = {
            "top-level": '{"version":"1","version":"2"}',
            "result-path": '{"results":{"tracked.py":[],"tracked.py":[]}}',
            "candidate": (
                '{"results":{"tracked.py":[{"hashed_secret":"a","hashed_secret":"b"}]}}'
            ),
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "document.json"
            for label, content in documents.items():
                with self.subTest(label=label):
                    path.write_text(content, encoding="utf-8")
                    with self.assertRaisesRegex(SecurityScanError, "duplicate"):
                        security_scan._read_document(path, "test document")

    def test_json_reader_normalizes_excessive_nesting(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "document.json"
            depth = 10_000
            path.write_text(
                '{"results":' + "[" * depth + "0" + "]" * depth + "}",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(SecurityScanError, "cannot read"):
                security_scan._read_document(path, "test document")

    def test_baseline_rejects_every_non_finite_json_number(self) -> None:
        template = (
            '{"version":"1.5.0","plugins_used":['
            '{"name":"HexHighEntropyString","limit":%s}],'
            '"filters_used":[],"results":{},'
            '"generated_at":"2026-09-17T14:33:10Z"}'
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "document.json"
            for value in ("NaN", "Infinity", "-Infinity", "1e999"):
                with self.subTest(value=value):
                    path.write_text(template % value, encoding="utf-8")
                    with self.assertRaisesRegex(
                        SecurityScanError,
                        "non-finite|plugin limit",
                    ):
                        document = security_scan._read_document(
                            path,
                            "test document",
                        )
                        security_scan._validate_baseline_schema(document)

    def test_arbitrary_size_integer_limit_fails_closed_without_overflow(self) -> None:
        huge_integer = 10**10_000
        scan = _report({})
        baseline = _report({})
        for document in (scan, baseline):
            document["plugins_used"] = [
                {
                    "name": "HexHighEntropyString",
                    "limit": huge_integer,
                }
            ]

        with self.assertRaisesRegex(SecurityScanError, "plugin limit"):
            evaluate_secret_report(scan, baseline)

    def test_json_integer_parser_limit_fails_closed(self) -> None:
        content = (
            '{"version":"1.5.0","plugins_used":['
            '{"name":"HexHighEntropyString","limit":1'
            + "0"
            * 100_000
            + '}],"filters_used":[],"results":{},'
            '"generated_at":"2026-09-17T14:33:10Z"}'
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "document.json"
            path.write_text(content, encoding="utf-8")

            with self.assertRaisesRegex(SecurityScanError, "cannot read"):
                security_scan._read_document(path, "test document")

    def test_scanner_child_reaping_is_bounded(self) -> None:
        process = mock.Mock(spec=subprocess.Popen)
        process.poll.return_value = None
        process.wait.return_value = 0

        security_scan._terminate_and_reap(process)

        process.kill.assert_called_once_with()
        process.wait.assert_called_once_with(
            timeout=security_scan._PROCESS_REAP_TIMEOUT_SECONDS
        )

    def test_scanner_child_reap_timeout_fails_closed(self) -> None:
        process = mock.Mock(spec=subprocess.Popen)
        process.poll.return_value = None
        process.wait.side_effect = subprocess.TimeoutExpired(["scanner"], 1)

        with self.assertRaisesRegex(SecurityScanError, "could not be reaped"):
            security_scan._terminate_and_reap(process)

        process.kill.assert_called_once_with()
        process.wait.assert_called_once_with(
            timeout=security_scan._PROCESS_REAP_TIMEOUT_SECONDS
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
        scan = _report(
            {
                "tracked.txt": [
                    _candidate(CANDIDATE_HASH, line=3, filename="tracked.txt")
                ]
            }
        )
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
            self.assertEqual(
                [sys.executable, "-I", "-m", "detect_secrets"],
                command[:4],
            )
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

    def test_scanner_output_uses_strict_closed_json_decoder(self) -> None:
        baseline = _report({})
        finding_report = _report(
            {
                "tracked.txt": [
                    _candidate(
                        CANDIDATE_HASH,
                        line=1,
                        filename="tracked.txt",
                    )
                ]
            }
        )
        duplicate_results = (
            json.dumps(finding_report)[:-1] + ', "results": {}}'
        ).encode("utf-8")
        non_finite_report = _report({})
        non_finite_report["generated_at"] = float("nan")
        overflowing_float = (
            json.dumps(_report({}))
            .replace(
                '"2026-09-17T14:33:10Z"',
                "1e999",
                1,
            )
            .encode("utf-8")
        )
        unknown_field_report = _report({})
        unknown_field_report["candidate_owned"] = "ignored"
        excessive_nesting = (
            '{"results":' + "[" * 10_000 + "0" + "]" * 10_000 + "}"
        ).encode("utf-8")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".secrets.baseline").write_text(
                json.dumps(baseline),
                encoding="utf-8",
            )
            (root / "tracked.txt").write_text("candidate\n", encoding="utf-8")
            for label, stdout, pattern in (
                ("duplicate", duplicate_results, "duplicate"),
                (
                    "non-finite",
                    json.dumps(non_finite_report).encode("utf-8"),
                    "non-finite",
                ),
                ("overflowing float", overflowing_float, "non-finite"),
                ("excessive nesting", excessive_nesting, "invalid JSON"),
                (
                    "unknown field",
                    json.dumps(unknown_field_report).encode("utf-8"),
                    "report schema",
                ),
            ):
                with self.subTest(label=label):
                    completed = subprocess.CompletedProcess(
                        ["detect-secrets"],
                        0,
                        stdout,
                        b"",
                    )
                    with mock.patch(
                        "tools.security_scan._run_bounded_scan",
                        return_value=completed,
                    ):
                        with self.assertRaisesRegex(SecurityScanError, pattern):
                            scan_tracked_tree(
                                root,
                                tracked_paths=[Path("tracked.txt")],
                            )

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

    def test_snapshot_rejects_per_file_and_cumulative_size_overflow(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "first.txt").write_bytes(b"a" * 40)
            (root / "second.txt").write_bytes(b"b" * 40)

            with (
                mock.patch.object(
                    security_scan,
                    "_MAX_SNAPSHOT_FILE_BYTES",
                    32,
                    create=True,
                ),
                self.assertRaisesRegex(SecurityScanError, "snapshot file size"),
            ):
                with security_scan._immutable_candidate_snapshot(
                    root,
                    [Path("first.txt")],
                ):
                    pass

            with (
                mock.patch.object(
                    security_scan,
                    "_MAX_SNAPSHOT_FILE_BYTES",
                    64,
                    create=True,
                ),
                mock.patch.object(
                    security_scan,
                    "_MAX_SNAPSHOT_TOTAL_BYTES",
                    64,
                    create=True,
                ),
                self.assertRaisesRegex(SecurityScanError, "snapshot total size"),
            ):
                with security_scan._immutable_candidate_snapshot(
                    root,
                    [Path("first.txt"), Path("second.txt")],
                ):
                    pass

    def test_snapshot_acquisition_has_its_own_deadline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "tracked.txt").write_text("candidate\n", encoding="utf-8")

            with (
                mock.patch.object(
                    security_scan,
                    "_SNAPSHOT_TIMEOUT_SECONDS",
                    0,
                    create=True,
                ),
                self.assertRaisesRegex(SecurityScanError, "snapshot timed out"),
            ):
                with security_scan._immutable_candidate_snapshot(
                    root,
                    [Path("tracked.txt")],
                ):
                    pass

    def test_ancestor_replacement_during_copy_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original_parent = root / "nested"
            detached_parent = root / "detached"
            original_parent.mkdir()
            (original_parent / "tracked.txt").write_text(
                "benign before swap\n",
                encoding="utf-8",
            )
            real_read = os.read
            swapped = False

            def swap_parent_then_read(descriptor: int, size: int) -> bytes:
                nonlocal swapped
                if not swapped:
                    original_parent.rename(detached_parent)
                    original_parent.mkdir()
                    (original_parent / "tracked.txt").write_text(
                        "secret after swap\n",
                        encoding="utf-8",
                    )
                    swapped = True
                return real_read(descriptor, size)

            with (
                mock.patch(
                    "tools.security_scan.os.read", side_effect=swap_parent_then_read
                ),
                self.assertRaisesRegex(SecurityScanError, "changed while snapshotting"),
            ):
                with security_scan._immutable_candidate_snapshot(
                    root,
                    [Path("nested/tracked.txt")],
                ):
                    pass

            self.assertTrue(swapped)

    def test_in_place_change_during_copy_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = root / "tracked.txt"
            candidate.write_bytes(b"a" * (security_scan._SNAPSHOT_CHUNK_BYTES + 1))
            real_read = os.read
            changed = False

            def change_after_first_read(descriptor: int, size: int) -> bytes:
                nonlocal changed
                chunk = real_read(descriptor, size)
                if chunk and not changed:
                    candidate.write_bytes(
                        b"b" * (security_scan._SNAPSHOT_CHUNK_BYTES + 1)
                    )
                    changed = True
                return chunk

            with (
                mock.patch(
                    "tools.security_scan.os.read",
                    side_effect=change_after_first_read,
                ),
                self.assertRaisesRegex(SecurityScanError, "changed while snapshotting"),
            ):
                with security_scan._immutable_candidate_snapshot(
                    root,
                    [Path("tracked.txt")],
                ):
                    pass

            self.assertTrue(changed)

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

    def test_canonical_scan_refuses_an_untracked_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "tracked.txt").write_text("candidate\n", encoding="utf-8")
            (root / ".secrets.baseline").write_text(
                json.dumps(_report({})),
                encoding="utf-8",
            )

            with (
                mock.patch(
                    "tools.security_scan.candidate_paths",
                    return_value=[Path("tracked.txt")],
                ),
                mock.patch("tools.security_scan._run_bounded_scan") as run,
                self.assertRaisesRegex(
                    SecurityScanError,
                    "baseline is outside the canonical candidate set",
                ),
            ):
                scan_tracked_tree(root)

            run.assert_not_called()

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
            "LICENSE",
            "LICENSING.md",
            "NOTICE",
            "SUPPORT.md",
            "THIRD_PARTY_NOTICES",
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
        for paths in ((), ("notes.txt",), (".github/ISSUE_TEMPLATE/question.yml",)):
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
        for finding in evidence["findings"]:
            self.assertEqual({"line", "path", "type"}, set(finding))
            path = finding["path"]
            line = finding["line"]
            finding_type = finding["type"]
            self.assertIsInstance(path, str)
            self.assertTrue(path)
            self.assertTrue(path.isprintable())
            self.assertFalse(PurePosixPath(path).is_absolute())
            self.assertNotIn("..", PurePosixPath(path).parts)
            self.assertIsInstance(line, int)
            self.assertNotIsInstance(line, bool)
            self.assertGreater(line, 0)
            self.assertIsInstance(finding_type, str)
            self.assertTrue(finding_type)
            self.assertTrue(finding_type.isprintable())
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
        self.assertIn("git diff --no-renames --name-only -z", workflow)
        self.assertNotIn("git diff --name-only -z", workflow)
        self.assertIn(
            'if ! git diff --quiet "${BASE_SHA}" HEAD -- tools/extended_route.py; then',
            workflow,
        )
        self.assertIn(
            'force_reason="${GITHUB_EVENT_NAME} requires full evidence"',
            workflow,
        )
        self.assertIn('force_reason="extended router changed"', workflow)
        self.assertIn(
            'git show "${BASE_SHA}:tools/extended_route.py" > "${router_file}"',
            workflow,
        )
        self.assertIn(
            "Restricted native path: execute only comparison-base router bytes",
            workflow,
        )
        self.assertIn('python -I "${router_file}"', workflow)
        self.assertNotIn("python -m tools.extended_route", workflow)
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
        self.assertIn("  push:\n    branches: [main]", workflow)
        self.assertNotIn(
            "(github.event_name != 'push' || github.ref == 'refs/heads/main')",
            workflow,
        )

    def test_extended_router_fails_closed_without_a_verifiable_base(self) -> None:
        workflow = load_yaml(ROOT / ".github" / "workflows" / "verification.yml")
        route_steps = workflow["jobs"]["extended-route"]["steps"]
        route_script = next(
            step["run"]
            for step in route_steps
            if step.get("name") == "Classify extended verification applicability"
        )
        cases = (
            ("pull_request", "", "comparison base unavailable"),
            ("pull_request", "0" * 40, "comparison base unavailable"),
            ("pull_request", "f" * 40, "comparison base unavailable"),
            ("schedule", "", "schedule requires full evidence"),
            (
                "workflow_dispatch",
                "",
                "workflow_dispatch requires full evidence",
            ),
        )

        for event, base_sha, reason in cases:
            with self.subTest(event=event, base_sha=base_sha or "missing"):
                with tempfile.TemporaryDirectory() as directory:
                    temporary = Path(directory)
                    fake_bin = temporary / "bin"
                    fake_bin.mkdir()
                    router_marker = temporary / "candidate-router-invoked"
                    fake_python = fake_bin / "python"
                    fake_python.write_text(
                        '#!/bin/sh\n: > "${ROUTER_MARKER}"\nexit 97\n',
                        encoding="utf-8",
                    )
                    fake_python.chmod(0o700)
                    fake_git = fake_bin / "git"
                    fake_git.write_text(
                        "#!/bin/sh\n"
                        'case "${1:-}" in\n'
                        "  cat-file) exit 1 ;;\n"
                        "  ls-files) exit 0 ;;\n"
                        "  *) exit 98 ;;\n"
                        "esac\n",
                        encoding="utf-8",
                    )
                    fake_git.chmod(0o700)
                    output = temporary / "github-output"
                    environment = os.environ.copy()
                    environment.update(
                        {
                            "BASE_SHA": base_sha,
                            "GITHUB_EVENT_NAME": event,
                            "GITHUB_OUTPUT": str(output),
                            "GITHUB_REF": "refs/pull/278/head",
                            "PATH": f"{fake_bin}{os.pathsep}{environment['PATH']}",
                            "ROUTER_MARKER": str(router_marker),
                            "RUNNER_TEMP": str(temporary),
                        }
                    )

                    completed = subprocess.run(
                        ["bash", "-c", route_script],
                        cwd=ROOT,
                        env=environment,
                        check=False,
                        capture_output=True,
                        text=True,
                    )

                    self.assertEqual(0, completed.returncode, completed.stderr)
                    self.assertFalse(router_marker.exists())
                    self.assertEqual(
                        {
                            "decision": "RUN",
                            "run_extended": "true",
                            "reason": reason,
                        },
                        dict(
                            line.split("=", maxsplit=1)
                            for line in output.read_text(encoding="utf-8").splitlines()
                        ),
                    )

    def test_valid_base_uses_isolated_trusted_router_source(self) -> None:
        workflow = load_yaml(ROOT / ".github" / "workflows" / "verification.yml")
        route_steps = workflow["jobs"]["extended-route"]["steps"]
        route_script = next(
            step["run"]
            for step in route_steps
            if step.get("name") == "Classify extended verification applicability"
        )

        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            fake_bin = temporary / "bin"
            fake_bin.mkdir()
            fake_git = fake_bin / "git"
            fake_git.write_text(
                "#!/bin/sh\n"
                'case "${1:-}" in\n'
                "  cat-file) exit 0 ;;\n"
                "  diff)\n"
                '    if test "${2:-}" = "--no-renames"; then\n'
                "      printf 'notes.txt\\0'\n"
                "      exit 0\n"
                "    fi\n"
                '    test "${2:-}" = "--quiet" && exit 0\n'
                "    exit 98\n"
                "    ;;\n"
                '  show) cat "${TRUSTED_ROUTER_SOURCE}" ;;\n'
                "  *) exit 98 ;;\n"
                "esac\n",
                encoding="utf-8",
            )
            fake_git.chmod(0o700)
            candidate_package = temporary / "tools"
            candidate_package.mkdir()
            package_marker = temporary / "candidate-package-imported"
            (candidate_package / "__init__.py").write_text(
                "from pathlib import Path\n"
                f"Path({str(package_marker)!r}).write_text('imported')\n",
                encoding="utf-8",
            )
            startup_marker = temporary / "candidate-startup-imported"
            (temporary / "sitecustomize.py").write_text(
                "from pathlib import Path\n"
                f"Path({str(startup_marker)!r}).write_text('imported')\n",
                encoding="utf-8",
            )
            output = temporary / "github-output"
            environment = os.environ.copy()
            environment.update(
                {
                    "BASE_SHA": "b" * 40,
                    "GITHUB_EVENT_NAME": "pull_request",
                    "GITHUB_OUTPUT": str(output),
                    "GITHUB_REF": "refs/pull/278/head",
                    "PATH": f"{fake_bin}{os.pathsep}{environment['PATH']}",
                    "RUNNER_TEMP": str(temporary),
                    "TRUSTED_ROUTER_SOURCE": str(ROOT / "tools" / "extended_route.py"),
                }
            )

            completed = subprocess.run(
                ["bash", "-c", route_script],
                cwd=temporary,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertFalse(package_marker.exists())
            self.assertFalse(startup_marker.exists())
            self.assertEqual(
                {
                    "decision": "NOT_APPLICABLE",
                    "run_extended": "false",
                    "reason": "candidate changes no declared extended-evidence surface",
                },
                dict(
                    line.split("=", maxsplit=1)
                    for line in output.read_text(encoding="utf-8").splitlines()
                ),
            )


if __name__ == "__main__":
    unittest.main()
