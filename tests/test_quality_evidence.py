from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.quality_evidence import (
    QualityEvidenceError,
    collect_quality_evidence,
    dependency_audit_summary,
    file_evidence,
    json_array_diagnostic_count,
    json_lines_diagnostic_count,
    secret_findings,
)

ROOT = Path(__file__).resolve().parent.parent


class QualityEvidenceParsingTests(unittest.TestCase):
    def test_secret_findings_expose_location_and_type_but_not_secret_material(
        self,
    ) -> None:
        report = {
            "results": {
                "tracked.txt": [
                    {
                        "type": "Hex High Entropy String",
                        "filename": "tracked.txt",
                        "hashed_secret": "private-derived-value",  # pragma: allowlist secret -- derived parser fixture
                        "line_number": 7,
                    }
                ]
            }
        }

        self.assertEqual(
            [
                {
                    "path": "tracked.txt",
                    "line": 7,
                    "type": "Hex High Entropy String",
                }
            ],
            secret_findings(report),
        )

    def test_dependency_summary_counts_and_names_known_vulnerabilities(self) -> None:
        report = {
            "dependencies": [
                {"name": "safe", "version": "1.0", "vulns": []},
                {
                    "name": "affected",
                    "version": "2.0",
                    "vulns": [
                        {"id": "PYSEC-2", "fix_versions": ["2.1"]},
                        {"id": "CVE-1", "fix_versions": []},
                    ],
                },
            ],
            "fixes": [],
        }

        self.assertEqual(
            {
                "dependencies": 2,
                "vulnerabilities": 2,
                "vulnerability_ids": ["CVE-1", "PYSEC-2"],
            },
            dependency_audit_summary(report),
        )

    def test_file_evidence_is_content_addressed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            path.write_bytes(b"bounded evidence\n")

            self.assertEqual(
                {
                    "sha256": hashlib.sha256(b"bounded evidence\n").hexdigest(),
                    "size_bytes": 17,
                },
                file_evidence(path),
            )

    def test_static_diagnostic_counts_validate_machine_readable_reports(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ruff_report = root / "ruff.json"
            mypy_report = root / "mypy.jsonl"
            ruff_report.write_text('[{"code": "I001"}, {"code": "UP035"}]\n')
            mypy_report.write_text(
                '{"code": "assignment", "severity": "error"}\n',
                encoding="utf-8",
            )

            self.assertEqual(2, json_array_diagnostic_count(ruff_report, "ruff"))
            self.assertEqual(1, json_lines_diagnostic_count(mypy_report, "mypy"))

            mypy_report.write_text("not-json\n", encoding="utf-8")
            with self.assertRaisesRegex(QualityEvidenceError, "mypy"):
                json_lines_diagnostic_count(mypy_report, "mypy")

    def test_collector_writes_bounded_summary_from_successful_reports(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repository"
            output = Path(directory) / "evidence"
            (root / "requirements").mkdir(parents=True)
            for name in ("runtime.lock", "development.lock"):
                (root / "requirements" / name).write_text(
                    "example==1.0\n",
                    encoding="utf-8",
                )

            def fake_run(command, *, root, environment=None, stdout=None):
                if command[2] == "ruff":
                    json.dump([], stdout)
                elif command[2] == "mypy":
                    stdout.write("")
                elif command[2:4] == ["coverage", "json"]:
                    report = Path(command[command.index("-o") + 1])
                    report.write_text(
                        json.dumps({"totals": {"percent_covered": 72.5}}),
                        encoding="utf-8",
                    )
                elif command[2] == "pip_audit":
                    report = Path(command[command.index("--output") + 1])
                    report.write_text(
                        json.dumps(
                            {
                                "dependencies": [
                                    {
                                        "name": "example",
                                        "version": "1.0",
                                        "vulns": [],
                                    }
                                ],
                                "fixes": [],
                            }
                        ),
                        encoding="utf-8",
                    )
                elif command[2] == "detect_secrets":
                    json.dump({"results": {}}, stdout)
                return 0

            with (
                patch("tools.quality_evidence._run", side_effect=fake_run),
                patch(
                    "tools.quality_evidence._git_state",
                    return_value={"revision": "abc123", "tracked_tree_dirty": False},
                ),
                patch(
                    "tools.quality_evidence._tool_versions",
                    return_value={
                        "coverage": "1",
                        "detect-secrets": "1",
                        "mypy": "1",
                        "pip-audit": "1",
                        "ruff": "1",
                        "types-PyYAML": "1",
                        "types-jsonschema": "1",
                    },
                ),
                patch(
                    "tools.quality_evidence.candidate_paths",
                    return_value=[Path("tracked.txt")],
                ),
            ):
                summary_path = collect_quality_evidence(root, output)

            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual("abc123", summary["source"]["revision"])
            self.assertEqual(
                {
                    "format_diagnostics": 0,
                    "lint_diagnostics": 0,
                    "typing_diagnostics": 0,
                },
                summary["results"]["static_quality"],
            )
            self.assertEqual(72.5, summary["results"]["coverage"]["percent"])
            self.assertEqual(
                0,
                summary["results"]["secret_scan"]["candidates"],
            )
            self.assertEqual(
                {
                    "boundary": "current Git-tracked regular-file working tree only",
                    "tracked_files": 1,
                },
                summary["scope"]["secret_scan"],
            )
            self.assertEqual(
                {
                    "coverage.json",
                    "development-dependency-audit.json",
                    "mypy.jsonl",
                    "ruff-format.json",
                    "ruff-lint.json",
                    "runtime-dependency-audit.json",
                    "tracked-tree-secret-scan.json",
                },
                set(summary["reports"]),
            )

    def test_collector_fails_after_recording_secret_candidate_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repository"
            output = Path(directory) / "evidence"
            (root / "requirements").mkdir(parents=True)
            for name in ("runtime.lock", "development.lock"):
                (root / "requirements" / name).write_text(
                    "example==1.0\n",
                    encoding="utf-8",
                )

            def fake_run(command, *, root, environment=None, stdout=None):
                if command[2] == "ruff":
                    json.dump([], stdout)
                elif command[2] == "mypy":
                    stdout.write("")
                elif command[2:4] == ["coverage", "json"]:
                    Path(command[command.index("-o") + 1]).write_text(
                        json.dumps({"totals": {"percent_covered": 72.5}}),
                        encoding="utf-8",
                    )
                elif command[2] == "pip_audit":
                    Path(command[command.index("--output") + 1]).write_text(
                        json.dumps({"dependencies": [], "fixes": []}),
                        encoding="utf-8",
                    )
                elif command[2] == "detect_secrets":
                    json.dump(
                        {
                            "results": {
                                "tracked.txt": [
                                    {
                                        "type": "Secret Keyword",
                                        "line_number": 3,
                                        "hashed_secret": "not-exposed",  # pragma: allowlist secret -- derived parser fixture
                                    }
                                ]
                            }
                        },
                        stdout,
                    )
                return 0

            with (
                patch("tools.quality_evidence._run", side_effect=fake_run),
                patch(
                    "tools.quality_evidence._git_state",
                    return_value={"revision": "abc123", "tracked_tree_dirty": False},
                ),
                patch(
                    "tools.quality_evidence._tool_versions",
                    return_value={
                        "coverage": "1",
                        "detect-secrets": "1",
                        "mypy": "1",
                        "pip-audit": "1",
                        "ruff": "1",
                        "types-PyYAML": "1",
                        "types-jsonschema": "1",
                    },
                ),
                patch(
                    "tools.quality_evidence.candidate_paths",
                    return_value=[Path("tracked.txt")],
                ),
            ):
                with self.assertRaisesRegex(QualityEvidenceError, "secret_candidates"):
                    collect_quality_evidence(root, output)

            summary = json.loads(
                (output / "quality-summary.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                [
                    {
                        "line": 3,
                        "path": "tracked.txt",
                        "type": "Secret Keyword",
                    }
                ],
                summary["results"]["secret_scan"]["findings"],
            )
            self.assertNotIn("not-exposed", json.dumps(summary))

    def test_collector_refuses_an_empty_or_symlinked_tracked_scope(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repository"
            output = Path(directory) / "evidence"
            root.mkdir()

            with patch(
                "tools.quality_evidence.candidate_paths",
                return_value=[],
            ):
                with self.assertRaisesRegex(QualityEvidenceError, "no candidate files"):
                    collect_quality_evidence(root, output)

            external = Path(directory) / "external.txt"
            external.write_text("outside the tracked tree\n", encoding="utf-8")
            (root / "link.txt").symlink_to(external)
            with patch(
                "tools.quality_evidence.candidate_paths",
                return_value=[Path("link.txt")],
            ):
                with self.assertRaisesRegex(QualityEvidenceError, "refuses symlinks"):
                    collect_quality_evidence(root, output)


class QualityEvidenceIntegrationTests(unittest.TestCase):
    def test_extended_suite_uses_exact_tools_and_uploads_bounded_reports(self) -> None:
        lock = (ROOT / "requirements" / "development.lock").read_text(encoding="utf-8")
        for requirement in (
            "coverage==7.15.2",
            "detect-secrets==1.5.0",
            "mypy==2.3.0",
            "pip-audit==2.10.1",
            "ruff==0.16.0",
            "types-jsonschema==4.26.0.20260518",
            "types-PyYAML==6.0.12.20260518",
        ):
            self.assertIn(requirement, lock)

        project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("[tool.ruff]", project)
        self.assertIn('target-version = "py311"', project)
        self.assertIn("[tool.mypy]", project)
        self.assertIn("strict = true", project)

        verify = (ROOT / "ci" / "verify").read_text(encoding="utf-8")
        self.assertIn("ci/quality_evidence.py", verify)
        self.assertIn("GNOSTOA_QUALITY_OUTPUT", verify)

        workflow = (ROOT / ".github" / "workflows" / "verification.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("gnostoa-quality-evidence", workflow)
        self.assertIn(
            "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",
            workflow,
        )

        verification = (ROOT / "policy" / "verification.yaml").read_text(
            encoding="utf-8"
        )
        self.assertIn("evidence: [artifact, test-report]", verification)


if __name__ == "__main__":
    unittest.main()
