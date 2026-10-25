from __future__ import annotations

import ast
import errno
import hashlib
import importlib
import importlib.util
import json
import os
import shutil
import signal
import subprocess  # nosec B404 -- test-only: drives git on temporary fixture repositories
import sys
import tempfile
import time
import unittest
from email.message import Message
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import ANY, Mock, patch

from quality_evidence_fixtures import (
    _DIAGNOSTIC_SAMPLE,
    _EVERY_FAMILY,
    _EXTRA_COMPLEX,
    _SOURCE_BINDING_GAP,
    _DiagnosticFixture,
    _DiagnosticInventoryFixture,
)

from tools.quality_evidence import (
    QualityEvidenceError,
    build_cyclonedx_sbom,
    build_license_inventory,
    collect_quality_evidence,
    dependency_audit_summary,
    file_evidence,
    json_array_diagnostic_count,
    json_lines_diagnostic_count,
    locked_requirements,
    secret_findings,
)
from tools.requirements_lock import LockFormatError
from tools.security_scan import SecretScanResult

ROOT = Path(__file__).resolve().parent.parent
TEST_ARTIFACT_HASH = "a" * 64
TEST_SELECTION_HASH = "b" * 64


def _hashed_example_lock() -> str:
    return (
        "--only-binary :all:\n"
        "--require-hashes\n"
        "\n"
        "example==1.0 \\\n"
        f"    --hash=sha256:{TEST_ARTIFACT_HASH}\n"
    )


def _artifact_selection(lock: Path, *, scope: str) -> dict:
    return {
        "schema_version": 1,
        "scope": scope,
        "lock": {
            "path": f"requirements/{lock.name}",
            **file_evidence(lock),
        },
        "installer": {"name": "pip", "version": "26.0.1", "report_version": "1"},
        "environment": {
            "implementation_name": "cpython",
            "platform_machine": "x86_64",
            "platform_system": "Linux",
            "python_version": "3.12",
            "sys_platform": "linux",
        },
        "packages": [
            {
                "name": "example",
                "normalized_name": "example",
                "version": "1.0",
                "filename": "example-1.0-py3-none-any.whl",
                "sha256": TEST_ARTIFACT_HASH,
                "source_host": "files.pythonhosted.org",
            }
        ],
        "selection_sha256": TEST_SELECTION_HASH,
        "summary": {
            "packages": 1,
            "selected_hashes_admitted": 1,
            "yanked_artifacts": 0,
        },
        "limits": [],
    }


def _pip_report() -> dict:
    return {
        "version": "1",
        "pip_version": "26.0.1",
        "install": [
            {
                "download_info": {
                    "url": (
                        "https://files.pythonhosted.org/packages/aa/"
                        "example-1.0-py3-none-any.whl"
                    ),
                    "archive_info": {"hashes": {"sha256": TEST_ARTIFACT_HASH}},
                },
                "is_direct": False,
                "is_yanked": False,
                "metadata": {"name": "example", "version": "1.0"},
                "requested": True,
            }
        ],
        "environment": {
            "implementation_name": "cpython",
            "platform_machine": "x86_64",
            "platform_system": "Linux",
            "python_version": "3.12",
            "sys_platform": "linux",
        },
    }


class QualityEvidenceParsingTests(unittest.TestCase):
    def test_exact_lock_parser_rejects_unpinned_or_duplicate_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lock = Path(directory) / "runtime.lock"
            lock.write_text(
                (
                    "--only-binary :all:\n"
                    "--require-hashes\n"
                    "Example_Name==1.0 \\\n"
                    f"    --hash=sha256:{TEST_ARTIFACT_HASH}\n"
                    "second==2.0 \\\n"
                    f"    --hash=sha256:{'c' * 64}\n"
                ),
                encoding="utf-8",
            )

            self.assertEqual(
                [
                    {
                        "name": "Example_Name",
                        "normalized_name": "example-name",
                        "version": "1.0",
                        "artifact_hashes": [TEST_ARTIFACT_HASH],
                    },
                    {
                        "name": "second",
                        "normalized_name": "second",
                        "version": "2.0",
                        "artifact_hashes": ["c" * 64],
                    },
                ],
                locked_requirements(lock),
            )

            lock.write_text(
                (
                    "--only-binary :all:\n"
                    "--require-hashes\n"
                    "example>=1.0 \\\n"
                    f"    --hash=sha256:{TEST_ARTIFACT_HASH}\n"
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(LockFormatError, "exact name==version"):
                locked_requirements(lock)

            lock.write_text(
                (
                    "--only-binary :all:\n"
                    "--require-hashes\n"
                    "example-name==1.0 \\\n"
                    f"    --hash=sha256:{TEST_ARTIFACT_HASH}\n"
                    "example_name==1.0 \\\n"
                    f"    --hash=sha256:{TEST_ARTIFACT_HASH}\n"
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(LockFormatError, "duplicate"):
                locked_requirements(lock)

    def test_license_inventory_binds_installed_versions_and_preserves_metadata(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lock = Path(directory) / "runtime.lock"
            lock.write_text(_hashed_example_lock(), encoding="utf-8")
            package_metadata = Message()
            package_metadata["Metadata-Version"] = "2.4"
            package_metadata["Name"] = "example"
            package_metadata["License-Expression"] = "MIT"
            package_metadata["License-File"] = "LICENSE"
            distribution = SimpleNamespace(version="1.0", metadata=package_metadata)

            with (
                patch(
                    "tools.quality_evidence.metadata.distribution",
                    return_value=distribution,
                ),
                patch(
                    "tools.quality_evidence._normalized_spdx_expression",
                    return_value="MIT",
                ),
            ):
                inventory = build_license_inventory(
                    lock,
                    lock_identity="requirements/runtime.lock",
                    scope="runtime",
                    artifact_selection=_artifact_selection(lock, scope="runtime"),
                )

            self.assertEqual(
                {
                    "legacy_declarations": 0,
                    "manual_review": 0,
                    "missing_declarations": 0,
                    "non_spdx_declarations": 0,
                    "packages": 1,
                    "spdx_expressions": 1,
                    "artifact_identities": 1,
                },
                inventory["summary"],
            )
            self.assertEqual(
                {
                    "declaration": "MIT",
                    "expression": "MIT",
                    "manual_review": False,
                    "source": "license-expression",
                },
                inventory["packages"][0]["license"],
            )
            self.assertEqual(["LICENSE"], inventory["packages"][0]["license_files"])
            self.assertNotIn(str(Path(directory)), json.dumps(inventory))

            distribution.version = "2.0"
            with patch(
                "tools.quality_evidence.metadata.distribution",
                return_value=distribution,
            ):
                with self.assertRaisesRegex(QualityEvidenceError, "version mismatch"):
                    build_license_inventory(
                        lock,
                        lock_identity="requirements/runtime.lock",
                        scope="runtime",
                        artifact_selection=_artifact_selection(lock, scope="runtime"),
                    )

    def test_license_inventory_fails_when_distribution_declares_no_license(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lock = Path(directory) / "runtime.lock"
            lock.write_text(_hashed_example_lock(), encoding="utf-8")
            package_metadata = Message()
            package_metadata["Metadata-Version"] = "2.3"
            package_metadata["Name"] = "example"
            distribution = SimpleNamespace(version="1.0", metadata=package_metadata)

            with patch(
                "tools.quality_evidence.metadata.distribution",
                return_value=distribution,
            ):
                with self.assertRaisesRegex(QualityEvidenceError, "no license"):
                    build_license_inventory(
                        lock,
                        lock_identity="requirements/runtime.lock",
                        scope="runtime",
                        artifact_selection=_artifact_selection(lock, scope="runtime"),
                    )

    def test_cyclonedx_sbom_is_deterministic_and_carries_declared_licenses(
        self,
    ) -> None:
        inventory = {
            "schema_version": 2,
            "scope": "runtime",
            "lock": {
                "path": "requirements/runtime.lock",
                "sha256": "a" * 64,
                "size_bytes": 20,
            },
            "artifact_selection": {
                "sha256": TEST_SELECTION_HASH,
                "environment": {
                    "implementation_name": "cpython",
                    "python_version": "3.12",
                },
                "installer": {
                    "name": "pip",
                    "version": "26.0.1",
                    "report_version": "1",
                },
            },
            "packages": [
                {
                    "name": "Example",
                    "normalized_name": "example",
                    "version": "1.0",
                    "artifact": {
                        "filename": "example-1.0-py3-none-any.whl",
                        "sha256": TEST_ARTIFACT_HASH,
                        "source_host": "files.pythonhosted.org",
                    },
                    "metadata_version": "2.4",
                    "license_files": ["LICENSE"],
                    "license": {
                        "declaration": "MIT",
                        "expression": "MIT",
                        "source": "license-expression",
                        "manual_review": False,
                    },
                }
            ],
            "summary": {},
            "limits": [],
        }

        first = build_cyclonedx_sbom(
            inventory,
            project_name="gnostoa",
            project_version="0.1.0",
            source_revision="abc123",
        )
        second = build_cyclonedx_sbom(
            inventory,
            project_name="gnostoa",
            project_version="0.1.0",
            source_revision="abc123",
        )

        self.assertEqual(first, second)
        self.assertEqual("CycloneDX", first["bomFormat"])
        self.assertEqual("1.6", first["specVersion"])
        self.assertTrue(first["serialNumber"].startswith("urn:uuid:"))
        self.assertNotIn("timestamp", first["metadata"])
        self.assertEqual(
            [{"expression": "MIT"}],
            first["components"][0]["licenses"],
        )
        self.assertEqual(
            "pkg:pypi/example@1.0",
            first["components"][0]["purl"],
        )
        self.assertEqual(
            [{"alg": "SHA-256", "content": TEST_ARTIFACT_HASH}],
            first["components"][0]["hashes"],
        )

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
        self.assertEqual(
            {
                "dependencies": 2,
                "vulnerabilities": 2,
                "vulnerability_ids": ["CVE-1", "PYSEC-2"],
                "lock_entries": 3,
                "reported_dependencies": 2,
                "unreported_dependencies": ["installer"],
            },
            dependency_audit_summary(
                report,
                expected_requirements=[
                    {
                        "name": "safe",
                        "normalized_name": "safe",
                        "version": "1.0",
                        "artifact_hashes": [TEST_ARTIFACT_HASH],
                    },
                    {
                        "name": "affected",
                        "normalized_name": "affected",
                        "version": "2.0",
                        "artifact_hashes": [TEST_ARTIFACT_HASH],
                    },
                    {
                        "name": "installer",
                        "normalized_name": "installer",
                        "version": "3.0",
                        "artifact_hashes": [TEST_ARTIFACT_HASH],
                    },
                ],
            ),
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
                    _hashed_example_lock(),
                    encoding="utf-8",
                )
            (root / "pyproject.toml").write_text(
                '[project]\nname = "gnostoa"\nversion = "0.1.0"\n',
                encoding="utf-8",
            )
            package_metadata = Message()
            package_metadata["Metadata-Version"] = "2.4"
            package_metadata["Name"] = "example"
            package_metadata["License-Expression"] = "MIT"
            distribution = SimpleNamespace(version="1.0", metadata=package_metadata)

            def fake_run(command, *, root, environment=None, stdout=None):
                if command[2:4] == ["pip", "install"]:
                    report = Path(command[command.index("--report") + 1])
                    report.write_text(json.dumps(_pip_report()), encoding="utf-8")
                elif command[2] == "ruff":
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
                return 0

            def fake_secret_scan(
                repository_root,
                *,
                report_path=None,
                baseline_path=None,
                tracked_paths=None,
            ):
                self.assertEqual(root.resolve(), repository_root.resolve())
                self.assertIn(
                    baseline_path,
                    (None, Path(".secrets.baseline")),
                )
                self.assertIsNone(tracked_paths)
                assert report_path is not None
                report_path.write_text('{"results": {}}\n', encoding="utf-8")
                return SecretScanResult(
                    reviewed_false_positives=4,
                    unresolved_findings=[],
                    # Deliberately different from the collector's own
                    # candidate_paths() result below: the summary must report
                    # the scope the scan actually covered, not a second
                    # enumeration that may describe a different tree state.
                    scanned_files=7,
                )

            with (
                patch("tools.quality_evidence._run", side_effect=fake_run),
                patch("tools.quality_evidence.test_suite.run", return_value=0) as suite,
                patch(
                    "tools.quality_evidence._git_state",
                    return_value={"revision": "abc123", "tracked_tree_dirty": False},
                ),
                patch(
                    "tools.quality_evidence._tool_versions",
                    return_value={
                        "coverage": "1",
                        "cyclonedx-python-lib": "1",
                        "detect-secrets": "1",
                        "license-expression": "1",
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
                patch(
                    "tools.quality_evidence.metadata.distribution",
                    return_value=distribution,
                ),
                patch(
                    "tools.quality_evidence._normalized_spdx_expression",
                    return_value="MIT",
                ),
                patch("tools.quality_evidence.validate_cyclonedx_document"),
                patch(
                    "tools.quality_evidence.scan_tracked_tree",
                    side_effect=fake_secret_scan,
                ),
            ):
                summary_path = collect_quality_evidence(root, output)
            # Coverage is measured through the test-suite owner, in parallel, with the
            # same measurement as before and its bound (Decision 0109).
            suite.assert_called_once_with(
                root.resolve(), coverage_source="tools", environment=ANY
            )
            # In the environment whose data file `coverage report` then reads.
            self.assertEqual(
                str(output.resolve() / ".coverage"),
                suite.call_args.kwargs["environment"]["COVERAGE_FILE"],
            )

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
                4,
                summary["results"]["secret_scan"]["reviewed_false_positives"],
            )
            self.assertEqual(
                {
                    "baseline": ".secrets.baseline",
                    "boundary": "current Git-tracked regular-file working tree only",
                    "tracked_files": 7,
                },
                summary["scope"]["secret_scan"],
            )
            self.assertEqual(
                {
                    "coverage.json",
                    "development-dependency-audit.json",
                    "development-artifact-selection.json",
                    "development-license-inventory.json",
                    "development-sbom.cdx.json",
                    "mypy.jsonl",
                    "ruff-format.json",
                    "ruff-lint.json",
                    "runtime-dependency-audit.json",
                    "runtime-artifact-selection.json",
                    "runtime-license-inventory.json",
                    "runtime-sbom.cdx.json",
                    "tracked-tree-secret-scan.json",
                },
                set(summary["reports"]),
            )
            self.assertEqual(
                1,
                summary["results"]["runtime_license_inventory"]["packages"],
            )
            self.assertEqual(
                0,
                summary["results"]["runtime_license_inventory"]["manual_review"],
            )

    def test_collector_fails_after_recording_secret_candidate_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repository"
            output = Path(directory) / "evidence"
            (root / "requirements").mkdir(parents=True)
            for name in ("runtime.lock", "development.lock"):
                (root / "requirements" / name).write_text(
                    _hashed_example_lock(),
                    encoding="utf-8",
                )
            (root / "pyproject.toml").write_text(
                '[project]\nname = "gnostoa"\nversion = "0.1.0"\n',
                encoding="utf-8",
            )
            package_metadata = Message()
            package_metadata["Metadata-Version"] = "2.4"
            package_metadata["Name"] = "example"
            package_metadata["License-Expression"] = "MIT"
            distribution = SimpleNamespace(version="1.0", metadata=package_metadata)

            def fake_run(command, *, root, environment=None, stdout=None):
                if command[2:4] == ["pip", "install"]:
                    report = Path(command[command.index("--report") + 1])
                    report.write_text(json.dumps(_pip_report()), encoding="utf-8")
                elif command[2] == "ruff":
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
                return 0

            def fake_secret_scan(
                repository_root,
                *,
                report_path=None,
                baseline_path=None,
                tracked_paths=None,
            ):
                self.assertEqual(root.resolve(), repository_root.resolve())
                self.assertIn(
                    baseline_path,
                    (None, Path(".secrets.baseline")),
                )
                self.assertIsNone(tracked_paths)
                assert report_path is not None
                report_path.write_text(
                    '{"results":{"tracked.txt":[]}}\n',
                    encoding="utf-8",
                )
                return SecretScanResult(
                    reviewed_false_positives=0,
                    unresolved_findings=[
                        {
                            "path": "tracked.txt",
                            "line": 3,
                            "type": "Secret Keyword",
                        }
                    ],
                )

            with (
                patch("tools.quality_evidence._run", side_effect=fake_run),
                patch("tools.quality_evidence.test_suite.run", return_value=0),
                patch(
                    "tools.quality_evidence._git_state",
                    return_value={"revision": "abc123", "tracked_tree_dirty": False},
                ),
                patch(
                    "tools.quality_evidence._tool_versions",
                    return_value={
                        "coverage": "1",
                        "cyclonedx-python-lib": "1",
                        "detect-secrets": "1",
                        "license-expression": "1",
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
                patch(
                    "tools.quality_evidence.metadata.distribution",
                    return_value=distribution,
                ),
                patch(
                    "tools.quality_evidence._normalized_spdx_expression",
                    return_value="MIT",
                ),
                patch("tools.quality_evidence.validate_cyclonedx_document"),
                patch(
                    "tools.quality_evidence.scan_tracked_tree",
                    side_effect=fake_secret_scan,
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
            "cyclonedx-python-lib==11.12.0",
            "detect-secrets==1.5.0",
            "license-expression==30.4.4",
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
        self.assertIn("./ci/style --check", verify)
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

    # The module imports where the diagnostic path's POSIX-only directory flags are
    # absent, so the default collection does not need them: they are read on that
    # path alone, never at import (Codex and Q on #451).
    def test_the_module_imports_without_the_diagnostic_directory_flags(self) -> None:
        path = ROOT / "tools" / "quality_evidence.py"
        spec = importlib.util.spec_from_file_location("quality_evidence_bare", path)
        if spec is None or spec.loader is None:
            self.fail("the module cannot be loaded from its path")
        module = importlib.util.module_from_spec(spec)
        package = sys.modules["tools"]
        # Registered for the load alone: dataclasses resolve their annotations
        # through the module's own entry.
        with (
            patch.dict(sys.modules, {spec.name: module}),
            patch.dict(package.__dict__),
            patch.dict(os.__dict__),
        ):
            # Either flag may already be absent, on the very platforms this is about
            # (cubic and CodeAnt on #451).
            for name in ("O_DIRECTORY", "O_NOFOLLOW"):
                os.__dict__.pop(name, None)
            # The staging owner is unloaded, as in a fresh interpreter, so an import of
            # it at module scope reads the flags again rather than finding it cached.
            sys.modules.pop("tools.exact_tree", None)
            package.__dict__.pop("exact_tree", None)
            spec.loader.exec_module(module)
            self.assertNotIn("tools.exact_tree", sys.modules)
        self.assertTrue(callable(module.collect_quality_evidence))


# #389 F3-S1: the explicit, offline diagnostic inventory (Router 6201584332). It is
# experimental qualification material: not an assurance receipt, not in the default
# collection, and never a filter. Most producers are faked here at `_bounded_run`, with
# their real report formats, because CI's runtime image has neither ruff nor mypy; the
# end-to-end tests run the real runner, whose producers may then be absent, and assert
# only what holds either way. The complexity metric always runs for real.


class DiagnosticInventoryTests(_DiagnosticInventoryFixture):
    """The inventory lists every emitted finding with its producer, code, mapping
    status, path and range, and is COMPLETE only over the whole tracked Python set.
    The producers are faked at `_bounded_run`."""

    def test_every_emitted_finding_is_listed_with_producer_rule_path_and_range(
        self,
    ) -> None:
        inventory = self._inventory()
        typing = self._find(
            inventory, "mypy", "arg-type", "tests/test_sample.py", self.lines["typing"]
        )
        self.assertEqual(1, len(typing))
        self.assertEqual(
            12, typing[0]["range"]["start_column"]
        )  # mypy's 0-based column, made 1-based
        self.assertEqual(
            {
                "producer_code": "arg-type",
                "deepsource_rule": "TYP-050",
                "mapping": "PROVISIONAL",
            },
            {
                k: typing[0]["native"][k]
                for k in ("producer_code", "deepsource_rule", "mapping")
            },
        )
        self.assertIs(True, typing[0]["native"]["tracked"])
        private = self._find(
            inventory, "ruff", "SLF001", "tests/test_sample.py", self.lines["private"]
        )
        self.assertEqual("PYL-W0212", private[0]["native"]["deepsource_rule"])
        self.assertEqual(12, private[0]["range"]["start_column"])
        complexity = self._find(
            inventory, "complexity", "cc", "tools/sample.py", self.lines["branchy"]
        )
        self.assertEqual(17, complexity[0]["native"]["value"])
        self.assertEqual("PY-R1000", complexity[0]["native"]["deepsource_rule"])
        self.assertEqual("gnostoa-diagnostic-inventory/v3", inventory["schema"])
        self.assertEqual("EXPERIMENTAL", inventory["status"])

    def test_a_non_mapped_diagnostic_and_a_second_rule_on_one_line_stay_distinct(
        self,
    ) -> None:
        inventory = self._inventory()
        line = self.lines["typing"]
        unmapped = self._find(
            inventory, "mypy", "union-attr", "tests/test_sample.py", line
        )
        self.assertEqual(1, len(unmapped))
        self.assertEqual(
            ("UNMAPPED", None),
            (
                unmapped[0]["native"]["mapping"],
                unmapped[0]["native"]["deepsource_rule"],
            ),
        )
        other = self._find(inventory, "ruff", "PLR6301", "tests/test_sample.py", line)
        self.assertEqual("PYL-R0201", other[0]["native"]["deepsource_rule"])
        self.assertEqual(
            1,
            len(
                self._find(inventory, "mypy", "arg-type", "tests/test_sample.py", line)
            ),
        )

    def test_an_emitted_finding_with_a_justified_marker_stays_listed(self) -> None:
        inventory = self._inventory()
        marked = self._find(
            inventory, "ruff", "SLF001", "tests/test_sample.py", self.lines["marked"]
        )
        self.assertEqual(1, len(marked))
        self.assertNotEqual("suppressed", marked[0].get("state"))
        self.assertNotIn("suppression", json.dumps(marked[0]))

    def test_an_unchanged_line_finding_is_full_but_not_diff(self) -> None:
        source = self.root / "tests" / "test_sample.py"
        source.write_text(
            source.read_text(encoding="utf-8").replace(
                '"""Diagnostic fixture: test side."""',
                '"""Diagnostic fixture: test side, changed."""',
            ),
            encoding="utf-8",
        )
        self._git("commit", "-q", "-am", "head")
        self.ruff_records.append(
            self._ruff(
                "tests/test_sample.py", 1, 1, "S106", "Possible hardcoded password"
            )
        )
        inventory = self._inventory(base=self.base)
        unchanged = self._find(
            inventory, "ruff", "SLF001", "tests/test_sample.py", self.lines["private"]
        )
        self.assertEqual([False], [f["native"]["in_diff"] for f in unchanged])
        changed = self._find(inventory, "ruff", "S106", "tests/test_sample.py", 1)
        self.assertEqual([True], [f["native"]["in_diff"] for f in changed])
        self.assertEqual(self.base, inventory["scope"]["diff"]["base"])
        self.assertEqual(
            ["tests/test_sample.py"], inventory["scope"]["diff"]["changed_paths"]
        )

    def test_coverage_counts_the_whole_tracked_python_set(self) -> None:
        # Every file analyzed, and still INCOMPLETE for the unverified source binding
        # alone (I3): the counts stay whole.
        self.mypy_records = {}
        self.mypy_exit = {".": 0, "tests/fixtures/one/": 0}
        inventory = self._inventory()
        expected = sorted(p for p in self.files if p.endswith(".py"))
        self.assertEqual(expected, inventory["scope"]["full"]["expected"])
        self.assertEqual(
            {
                "status": "INCOMPLETE",
                "pages": 4,
                "count": 4,
                "total": 4,
                "reason": _SOURCE_BINDING_GAP,
            },
            inventory["coverage"],
        )
        self.assertEqual([], inventory["scope"]["full"]["unanalyzed"])
        fixture = [
            c for c, cwd, _ in self.commands if "mypy" in c and cwd.name == "one"
        ]
        self.assertEqual(
            1, len(fixture), "each tests/fixtures/<name> directory is its own mypy root"
        )

    def test_an_aborted_typing_invocation_names_its_files_and_is_incomplete(
        self,
    ) -> None:
        self.mypy_exit["."] = 2
        self.mypy_records = {
            "tests/test_sample.py": [
                self._mypy(
                    "tests/test_sample.py",
                    -1,
                    -1,
                    None,
                    'Duplicate module named "baseline"',
                )
            ]
        }
        inventory = self._inventory()
        self.assertEqual("INCOMPLETE", inventory["coverage"]["status"])
        unanalyzed = {
            u["path"]: u["reason"] for u in inventory["scope"]["full"]["unanalyzed"]
        }
        self.assertIn("Duplicate module", unanalyzed["tests/test_sample.py"])
        self.assertIn("tools/sample.py", unanalyzed)
        # The reason names them too, not only the source-binding gap (I3 on #436).
        self.assertIn(
            "3 tracked Python files unanalyzed", inventory["coverage"]["reason"]
        )
        self.assertNotIn("tests/fixtures/one/baseline.py", unanalyzed)
        # The code-less record that aborted the group is listed too (Sourcery on #436).
        aborted = [
            f
            for f in inventory["findings"]
            if f["tool"]["id"] == "mypy" and "rule" not in f
        ]
        self.assertEqual(
            ['Duplicate module named "baseline"'], [f["message"] for f in aborted]
        )

    def test_a_code_less_note_is_a_finding_not_an_abort(self) -> None:
        self.mypy_records["tests/test_sample.py"].append(
            self._mypy(
                "tests/test_sample.py",
                self.lines["typing"],
                11,
                None,
                "See the docs",
                "note",
            )
        )
        inventory = self._inventory()
        self.assertEqual(
            [],
            [
                u
                for u in inventory["scope"]["full"]["unanalyzed"]
                if u["path"] == "tests/test_sample.py"
            ],
        )
        self.assertEqual(
            1, len([f for f in inventory["findings"] if f["message"] == "See the docs"])
        )

    def test_an_unresolved_or_untyped_import_is_partial_not_complete(self) -> None:
        self.mypy_records = {
            "tests/test_sample.py": [
                self._mypy(
                    "tests/test_sample.py",
                    3,
                    0,
                    "import-not-found",
                    'Cannot find implementation or library stub for module named "test_other"',
                ),
                self._mypy(
                    "tests/test_sample.py",
                    4,
                    0,
                    "import-untyped",
                    'Library stubs not installed for "requests"',
                ),
            ]
        }
        inventory = self._inventory()
        # PARTIAL by itself, and INCOMPLETE for the unverified source binding (I3).
        self.assertEqual("INCOMPLETE", inventory["coverage"]["status"])
        self.assertEqual(
            _SOURCE_BINDING_GAP
            + "; 1 files with unresolved imports"
            + "; family typing PARTIAL: 1 files with unresolved imports",
            inventory["coverage"]["reason"],
        )
        self.assertEqual(
            {"tests/test_sample.py": ["requests", "test_other"]},
            inventory["scope"]["full"]["partial"],
        )
        self.assertEqual(
            1,
            len(
                self._find(
                    inventory, "mypy", "import-untyped", "tests/test_sample.py", 4
                )
            ),
        )

    def test_mypy_output_that_is_not_records_is_incomplete(self) -> None:
        for text, status in (("not json\n", 1), ("", 1)):
            with self.subTest(text=text, status=status):
                self.mypy_text, self.mypy_exit = text, {".": status}
                inventory = self._inventory()
                self.assertEqual("INCOMPLETE", inventory["coverage"]["status"])
                reasons = {
                    u["reason"]
                    for u in inventory["scope"]["full"]["unanalyzed"]
                    if u["path"] == "tools/sample.py"
                }
                self.assertEqual(1, len(reasons))
                self.assertTrue(next(iter(reasons)).startswith("mypy:main "))

    def test_findings_read_before_a_parse_failure_stay_listed(self) -> None:
        good = json.dumps(
            self._mypy(
                "tests/test_sample.py", self.lines["typing"], 11, "arg-type", "typed"
            )
        )
        self.mypy_text = good + "\nnot json\n"
        inventory = self._inventory()
        self.assertEqual(
            1,
            len(
                self._find(
                    inventory,
                    "mypy",
                    "arg-type",
                    "tests/test_sample.py",
                    self.lines["typing"],
                )
            ),
        )
        self.assertIn(
            "tests/test_sample.py",
            {u["path"] for u in inventory["scope"]["full"]["unanalyzed"]},
        )

    def test_unparsable_ruff_output_or_source_is_incomplete(self) -> None:
        self.ruff_text = "not json"
        inventory = self._inventory()
        self.assertEqual("INCOMPLETE", inventory["coverage"]["status"])
        self.assertTrue(
            any(
                u["reason"].startswith("ruff:every-rule ")
                for u in inventory["scope"]["full"]["unanalyzed"]
            )
        )
        self.ruff_text = None
        (self.root / "tools" / "sample.py").write_text(
            "def broken(:\n", encoding="utf-8"
        )
        self._git("commit", "-q", "-am", "broken")
        inventory = self._inventory()
        self.assertEqual("INCOMPLETE", inventory["coverage"]["status"])
        self.assertIn(
            "tools/sample.py",
            {u["path"] for u in inventory["scope"]["full"]["unanalyzed"]},
        )

    def test_a_ruff_exit_1_without_a_record_is_a_gap(self) -> None:
        # Codex on #436: ruff exits 1 only when it reports a diagnostic, so an exit 1
        # with an empty report is contradictory evidence and a gap, as mypy's exit 1
        # without an error record already is. An exit 0 with none is clean.
        self.ruff_records = []
        for status, gap in ((1, True), (0, False)):
            with self.subTest(status=status):
                self.ruff_exit = status
                inventory = self._inventory()
                reasons = {
                    u["path"]: u["reason"]
                    for u in inventory["scope"]["full"]["unanalyzed"]
                    if u["reason"].startswith("ruff:every-rule ")
                }
                if gap:
                    self.assertEqual(
                        "ruff:every-rule exited 1 without a finding record",
                        reasons.get("tools/sample.py"),
                    )
                else:
                    self.assertEqual({}, reasons)

    def test_a_relative_ruff_filename_is_read_from_the_root(self) -> None:
        self.ruff_records = [
            {**self.ruff_records[0], "filename": "tests/test_sample.py"}
        ]
        inventory = self._inventory()
        self.assertEqual(
            1,
            len(
                self._find(
                    inventory,
                    "ruff",
                    "SLF001",
                    "tests/test_sample.py",
                    self.lines["private"],
                )
            ),
        )

    def test_an_untracked_source_s_diagnostic_is_marked_out_of_scope(self) -> None:
        self.mypy_records["tests/test_sample.py"].append(
            self._mypy(
                "tools/untracked.py", 2, 0, "arg-type", "an imported, untracked module"
            )
        )
        inventory = self._inventory()
        (outside,) = [
            f for f in inventory["findings"] if f["path"] == "tools/untracked.py"
        ]
        self.assertIs(False, outside["native"]["tracked"])

    def test_an_unexpected_subject_is_incomplete_and_a_dirty_one_is_not_read(
        self,
    ) -> None:
        # In v2 (Router #389 6325382720, D1, D4): an expected revision that names no
        # commit freezes nothing and analyzes nothing; a dirty checkout is not the
        # subject, so its expected commit is analyzed and no dirty state is recorded.
        inventory = self._inventory(expected_revision="0" * 40)
        self.assertEqual("INCOMPLETE", inventory["coverage"]["status"])
        self.assertIn(
            "cannot freeze the subject's commit", inventory["coverage"]["reason"]
        )
        self.assertIsNone(inventory["source"]["revision"])
        self.assertEqual([], inventory["producers"])
        (self.root / "tools" / "sample.py").write_text(
            _DIAGNOSTIC_SAMPLE + "\n# dirty\n", encoding="utf-8"
        )
        shutil.rmtree(self.output, ignore_errors=True)
        inventory = self._inventory(expected_revision=self.base)
        self.assertEqual("INCOMPLETE", inventory["coverage"]["status"])
        self.assertEqual(_SOURCE_BINDING_GAP, inventory["coverage"]["reason"])
        self.assertEqual(self.base, inventory["source"]["revision"])
        self.assertNotIn("tracked_tree_dirty", inventory["source"])

    def test_an_unread_subject_records_no_revision(self) -> None:
        # Octopus and CodeAnt on #436, routed by the Router (6225341677, V1), in v2:
        # a commit that cannot be frozen, here an unborn HEAD's, records no revision,
        # never the caller's KNOWLEDGE_KIT_REVISION, and the expected revision is kept
        # as asked (Router #389 6325382720, D4: no environment-revision fallback).
        claimed = "c" * 40
        shutil.rmtree(self.root / ".git")
        self._git("init", "-q")
        self._git("add", "-A")
        for label, caller in (("the caller's revision", claimed), ("none", None)):
            for expected in (claimed, None):
                with (
                    self.subTest(label, expected=expected),
                    patch.dict(os.environ),
                ):
                    os.environ.pop("KNOWLEDGE_KIT_REVISION", None)
                    if caller is not None:
                        os.environ["KNOWLEDGE_KIT_REVISION"] = caller
                    shutil.rmtree(self.output, ignore_errors=True)
                    inventory = self._inventory(expected_revision=expected)
                    self.assertIsNone(inventory["source"]["revision"])
                    self.assertIsNone(inventory["source"]["tree"])
                    self.assertEqual(expected, inventory["source"]["expected_revision"])
                    self.assertIn(
                        "cannot freeze the subject's commit",
                        inventory["coverage"]["reason"],
                    )
                    self.assertEqual([], inventory["producers"])

    def test_a_commit_read_before_a_failed_tree_read_is_dropped(self) -> None:
        # The Router's V1 (6225341677), its stated conservative loss, in v2: a commit
        # resolved just before its tree could not be read is dropped too; no commit is
        # recorded without the tree derived from it.
        real = self.module._diagnostic_git

        def no_tree(root, deadline, *arguments, **options):
            if arguments[-1].endswith("^{tree}"):
                raise OSError("read failed")
            return real(root, deadline, *arguments, **options)

        with patch.object(self.module, "_diagnostic_git", side_effect=no_tree):
            commit, tree, gaps = self.module._frozen_subject(
                self.root, None, time.monotonic() + 60
            )
        self.assertEqual((None, None), (commit, tree))
        self.assertEqual(["cannot freeze the subject's commit: OSError"], gaps)

    def test_a_frozen_subject_keeps_its_commit_and_tree(self) -> None:
        # The Router's V1 (6225341677), in v2: a completed freeze keeps its commit and
        # the tree derived from it, whatever the checkout's state, and a spent budget
        # freezes nothing (Router #389 6325382720, D4).
        tree = self._git("rev-parse", "HEAD^{tree}")
        self.assertEqual(
            (self.base, tree, []),
            self.module._frozen_subject(self.root, None, time.monotonic() + 60),
        )
        (self.root / "tools" / "sample.py").write_text(
            _DIAGNOSTIC_SAMPLE + "\n# dirty\n", encoding="utf-8"
        )
        self.assertEqual(
            (self.base, tree, []),
            self.module._frozen_subject(self.root, self.base, time.monotonic() + 60),
        )
        self.assertEqual(
            (None, None, ["the deadline passed before the subject was frozen"]),
            self.module._frozen_subject(self.root, self.base, time.monotonic() - 1),
        )

    def test_a_file_budget_or_a_producer_gap_is_explicit(self) -> None:
        limits = self.module.DiagnosticLimits(max_files=2)
        inventory = self._inventory(limits=limits)
        self.assertEqual("INCOMPLETE", inventory["coverage"]["status"])
        self.assertIn("budget", inventory["coverage"]["reason"])
        self.assertEqual(0, inventory["coverage"]["count"])

        def timing_out(command, **options):
            if "ruff" in command:
                options["report"].write_bytes(b"")
                return None, "timed out at the inventory deadline", False
            return self._fake_run(command, **options)

        with patch("tools.quality_evidence._bounded_run", side_effect=timing_out):
            inventory = self._read(self.collect(self.root, self.output))
        self.assertEqual("INCOMPLETE", inventory["coverage"]["status"])
        self.assertTrue(
            any(
                "timed out" in u["reason"]
                for u in inventory["scope"]["full"]["unanalyzed"]
            )
        )

    def test_the_complexity_metric_and_its_boundaries_are_recorded(self) -> None:
        inventory = self._inventory()
        listed = {
            f["range"]["start_line"]: f["native"]["value"]
            for f in inventory["findings"]
            if f["tool"]["id"] == "complexity"
        }
        self.assertEqual(17, listed[self.lines["branchy"]])
        self.assertEqual(16, listed[self.lines["sixteen"]])
        self.assertNotIn(self.lines["fifteen"], listed)
        # The outer function counts its nested function's decisions too (17 = 1 + 8 + 8).
        self.assertEqual(17, listed[self.lines["outer"]])
        self.assertEqual(
            {
                "metric": "cyclomatic-n-1/v1",
                "reported_above": 15,
                "qualification": "UNQUALIFIED",
                # The producers' declared grammar, best-effort as Python's own
                # feature_version is (Codex, the Router's 6242507671 on #436).
                "grammar": {"python": "3.11", "binding": "BEST_EFFORT"},
            },
            inventory["configuration"]["complexity"],
        )

    def test_producer_runs_are_bound_and_cannot_be_rerouted(self) -> None:
        with patch.dict(
            os.environ, {"PYTHONPATH": str(self.root), "PYTHONHOME": "/elsewhere"}
        ):
            inventory = self._inventory()
        self.assertEqual(self.base, inventory["source"]["revision"])
        self.assertEqual("EXACT_TREE_STAGED", inventory["source"]["tree_binding"])
        runs = {r["invocation"]: r for r in inventory["producers"]}
        self.assertEqual(
            {"mypy:main", "mypy:tests/fixtures/one", "ruff:every-rule", "complexity"},
            set(runs),
        )
        for name in ("mypy:main", "ruff:every-rule"):
            argv = runs[name]["argv"]
            # -I, the interpreter's own isolation: the PYTHON* variables are inherited
            # but ignored, and the user site is off (Codex and CodeAnt on #436).
            self.assertEqual([sys.executable, "-I", "-m"], argv[:3])
            self.assertLess(
                argv.index("--"), min(argv.index(p) for p in argv if p.endswith(".py"))
            )
            report = self.run_directory / runs[name]["report"]["path"]
            self.assertEqual(
                file_evidence(report)["sha256"], runs[name]["report"]["sha256"]
            )
        self.assertIn("--isolated", runs["ruff:every-rule"]["argv"])
        self.assertIn("--config-file=", runs["mypy:main"]["argv"])
        observation = self.module._environment_command()
        for command, _, _ in self.commands:
            # The environment observations run the same isolated interpreter with the
            # collector's own observer module, never a producer (#389 F3 S2-C).
            expected = observation[:3] if command == observation else None
            self.assertEqual(expected or [sys.executable, "-I", "-m"], command[:3])
        observer = Path(self.module.__file__).resolve().parent
        self.assertEqual(
            [sys.executable, "-I", str(observer / "python_environment_observation.py")],
            observation[:3],
        )

    def test_an_inventory_past_its_deadline_is_incomplete(self) -> None:
        # Every later reading of the clock is past the deadline: the subject and
        # scope reads are bounded or reported (Codex and the PAO's F3-BND-01 on #436),
        # and a spent budget freezes and lists nothing, so the result never depends on
        # whether Git happens to finish within a millisecond (Option A on #436).
        clock = iter([0.0])
        owner = importlib.import_module("tools.exact_tree")
        listing = Mock(side_effect=AssertionError("listed past the deadline"))
        with (
            patch(
                "tools.quality_evidence.time.monotonic",
                side_effect=lambda: next(clock, 10_000.0),
            ),
            patch.object(owner, "tree_paths", listing),
        ):
            inventory = self._inventory()
        reason = inventory["coverage"].get("reason", "")
        self.assertEqual("INCOMPLETE", inventory["coverage"]["status"])
        self.assertIn("ran past its deadline", reason)
        self.assertIn("the deadline passed before the subject was frozen", reason)
        self.assertEqual([], listing.call_args_list)
        self.assertIsNone(inventory["scope"]["full"]["expected"])
        self.assertEqual([], inventory["findings"])

    def test_a_source_over_the_byte_bound_is_never_parsed(self) -> None:
        # CodeAnt's round-2 nitpick on #436: the metric parses in this process, so a
        # source larger than max_source_bytes is unanalyzed, never read whole.
        size = len(_DIAGNOSTIC_SAMPLE.encode("utf-8"))
        limits = self.module.DiagnosticLimits(max_source_bytes=size - 1)
        inventory = self._inventory(limits=limits)
        unanalyzed = {
            u["path"]: u["reason"] for u in inventory["scope"]["full"]["unanalyzed"]
        }
        self.assertIn(f"larger than {size - 1} bytes", unanalyzed["tools/sample.py"])
        self.assertEqual(
            [],
            [
                f
                for f in inventory["findings"]
                if f["tool"]["id"] == "complexity" and f["path"] == "tools/sample.py"
            ],
        )
        self.assertNotIn("tools/__init__.py", unanalyzed)
        self.assertEqual(
            size - 1, inventory["configuration"]["limits"]["max_source_bytes"]
        )

    def test_a_checkout_path_that_is_not_a_regular_file_is_never_opened(self) -> None:
        # CodeAnt on #436, in v2: the producers read the frozen tree's staged bytes,
        # so a tracked path that the checkout replaced with a FIFO is never opened,
        # and the committed file is analyzed instead.
        done = self._tracked_fifo()
        fifo = os.path.realpath(self.root / "tools" / "sample.py")
        real_open, opened = os.open, []

        def opening(name, *args, **kwargs):
            opened.append(os.path.realpath(name))
            return real_open(name, *args, **kwargs)

        with patch.object(self.module.os, "open", side_effect=opening):
            inventory = self._inventory()
        done()
        self.assertTrue(opened)
        self.assertNotIn(fifo, opened)
        self.assertNotIn(
            "tools/sample.py",
            {u["path"] for u in inventory["scope"]["full"]["unanalyzed"]},
        )
        self.assertTrue(
            self._find(
                inventory, "complexity", "cc", "tools/sample.py", self.lines["branchy"]
            )
        )

    def test_a_file_deleted_from_the_checkout_is_still_the_frozen_trees(self) -> None:
        # Codex on #436, in v2: a tracked file the checkout no longer holds is no
        # missing input. The producers read the frozen tree, so it is analyzed, and a
        # finding on it is tracked-source evidence.
        (self.root / "tools" / "sample.py").unlink()
        inventory = self._inventory()
        self.assertNotIn(
            "tools/sample.py",
            {u["path"] for u in inventory["scope"]["full"]["unanalyzed"]},
        )
        (finding,) = self._find(
            inventory, "complexity", "cc", "tools/sample.py", self.lines["branchy"]
        )
        self.assertIs(True, finding["native"]["tracked"])
        self.assertTrue([c for c, _, _ in self.commands if "tools/sample.py" in c])

    def test_the_in_process_read_refuses_a_file_that_became_a_fifo(self) -> None:
        # After the check above, a FIFO can still be swapped in: the read itself must
        # neither wait for a writer nor parse what it is not.
        done = self._tracked_fifo()
        started = time.monotonic()
        result = self.module._run_complexity(
            self.root, ["tools/sample.py"], time.monotonic() + 30
        )
        waited = time.monotonic() - started
        done()
        self.assertLess(waited, 1.5, "the read waited for a writer")
        self.assertEqual(
            "complexity: not a regular file, not read",
            result.unanalyzed["tools/sample.py"],
        )

    def test_a_source_over_the_byte_bound_reaches_no_producer(self) -> None:
        # CodeAnt on #436: one bound for every producer, not only the in-process metric.
        size = len(_DIAGNOSTIC_SAMPLE.encode("utf-8"))
        limits = self.module.DiagnosticLimits(max_source_bytes=size - 1)
        inventory = self._inventory(limits=limits)
        unanalyzed = {
            u["path"]: u["reason"] for u in inventory["scope"]["full"]["unanalyzed"]
        }
        self.assertEqual(
            f"larger than {size - 1} bytes, never analyzed",
            unanalyzed["tools/sample.py"],
        )
        self.assertEqual([], [c for c, _, _ in self.commands if "tools/sample.py" in c])

    def test_an_oversized_source_reached_by_an_import_is_out_of_scope(self) -> None:
        # cubic on #436: mypy can follow an admitted file's import into the oversized
        # file. What it reports there stays listed, and is not tracked-source evidence,
        # since the inventory records the file as never analyzed.
        size = len(_DIAGNOSTIC_SAMPLE.encode("utf-8"))
        self.mypy_records = {
            "tests/test_sample.py": [
                self._mypy("tools/sample.py", 3, 1, "arg-type", "followed import")
            ]
        }
        limits = self.module.DiagnosticLimits(max_source_bytes=size - 1)
        inventory = self._inventory(limits=limits)
        (finding,) = [
            f for f in inventory["findings"] if f["path"] == "tools/sample.py"
        ]
        self.assertIs(False, finding["native"]["tracked"])

    def test_the_in_process_read_keeps_its_own_byte_bound(self) -> None:
        # A source that grows after the size check still meets the metric's own bound.
        size = len(_DIAGNOSTIC_SAMPLE.encode("utf-8"))
        result = self.module._run_complexity(
            self.root,
            ["tools/sample.py"],
            time.monotonic() + 30,
            max_source_bytes=size - 1,
        )
        self.assertEqual(
            f"complexity: larger than {size - 1} bytes, not parsed",
            result.unanalyzed["tools/sample.py"],
        )
        limits = self.module.DiagnosticLimits(max_source_bytes=size - 1)
        with patch("tools.quality_evidence._source_size", return_value=0):
            inventory = self._inventory(limits=limits)
        unanalyzed = {
            u["path"]: u["reason"] for u in inventory["scope"]["full"]["unanalyzed"]
        }
        self.assertEqual(
            f"complexity: larger than {size - 1} bytes, not parsed",
            unanalyzed["tools/sample.py"],
        )

    def test_a_source_read_that_raises_is_that_files_gap(self) -> None:
        # Codex on #436, by the Router's L2 (6228117951): read() raises OverflowError
        # for a size it cannot provide, as for a max_source_bytes of sys.maxsize. Like
        # the existing MemoryError, it makes that file unanalyzed by name, its stream is
        # closed, and the next file is read.
        (self.root / "tools" / "first.py").write_text(
            _DIAGNOSTIC_SAMPLE, encoding="utf-8"
        )
        for error in (MemoryError, OverflowError):
            with self.subTest(error.__name__):
                opening, wrapping, streams = self._read_raises(error, "tools/first.py")
                with opening, wrapping:
                    result = self.module._run_complexity(
                        self.root,
                        ["tools/first.py", "tools/sample.py"],
                        time.monotonic() + 30,
                    )
                self.assertEqual(
                    {"tools/first.py": f"complexity could not parse: {error.__name__}"},
                    result.unanalyzed,
                )
                self.assertIn("tools/sample.py", {f["path"] for f in result.findings})
                self.assertEqual(1, len(streams))
                self.assertTrue(streams[0].stream.closed)

    def test_a_source_read_overflow_leaves_a_written_incomplete_inventory(
        self,
    ) -> None:
        # The Router's L2, through the collector: the other producers' findings stay,
        # the file is that named gap, and the inventory is written INCOMPLETE.
        opening, wrapping, _streams = self._read_raises(
            OverflowError, "tools/sample.py"
        )
        with opening, wrapping:
            inventory = self._inventory()
        unanalyzed = {
            u["path"]: u["reason"] for u in inventory["scope"]["full"]["unanalyzed"]
        }
        self.assertEqual(
            "complexity could not parse: OverflowError", unanalyzed["tools/sample.py"]
        )
        self.assertEqual("INCOMPLETE", inventory["coverage"]["status"])
        typing = self.lines["typing"]
        for tool, rule in (("mypy", "arg-type"), ("ruff", "PLR6301")):
            self.assertEqual(
                1,
                len(self._find(inventory, tool, rule, "tests/test_sample.py", typing)),
            )

    def test_a_decorators_decision_is_inside_its_functions_range(self) -> None:
        # Codex on #436, by the Router's D-a (6233671174): the metric counts a
        # decorator's decisions, but the range began at `def`, so a change to the
        # decorator alone was not in_diff. The range starts at the earliest decorator
        # expression's line, in the function's column; an undecorated function keeps its
        # coordinates.
        body = "".join(f"    if a == {i}:\n        a += 1\n" for i in range(14))
        indented = "".join("    " + row for row in body.splitlines(keepends=True))
        for label, source, start, counted in (
            ("stacked", "@dec(1 if x else 2)\n@other\ndef f(a):\n" + body, (1, 1), 1),
            (
                "a method",
                "class C:\n    @dec(1 if x else 2)\n    def f(self, a):\n" + indented,
                (2, 5),
                2,
            ),
            ("async", "@dec(1 if x else 2)\nasync def f(a):\n" + body, (1, 1), 1),
            (
                "multiline",
                "@dec(\n    1 if x else 2\n)\ndef f(a):\n" + body,
                (1, 1),
                2,
            ),
            ("undecorated", "def f(a):\n    b = 1 if a else 2\n" + body, (1, 1), 2),
        ):
            with self.subTest(label):
                tree = ast.parse(source)
                (finding,) = self.module._function_findings(
                    tree, "tools/sample.py", source.splitlines()
                )
                self.assertEqual(16, finding["native"]["value"])
                found = (
                    finding["range"]["start_line"],
                    finding["range"]["start_column"],
                )
                self.assertEqual(start, found)
                end_line = finding["range"]["end_line"]
                self.assertEqual(len(source.splitlines()), end_line)
                self.assertTrue(
                    self.module._in_diff(finding, {"tools/sample.py": [counted]})
                )
                self.assertFalse(
                    self.module._in_diff(finding, {"tools/sample.py": [end_line + 1]})
                )

    def test_the_metric_stops_past_its_remaining_findings_allowance(self) -> None:
        # CodeAnt on #436, by the Router's C1 (6228830094): the metric's findings were
        # counted only after every file. Before each next file it stops once its count
        # is past what is left of max_findings. The file that passed it is kept whole,
        # and equality still lets the next file start.
        (self.root / "tools" / "zlater.py").write_text(
            _DIAGNOSTIC_SAMPLE, encoding="utf-8"
        )
        paths = ["tools/sample.py", "tools/zlater.py"]
        deadline = time.monotonic() + 30
        each = len(self.module._run_complexity(self.root, paths[:1], deadline).findings)
        self.assertGreater(each, 0)
        for label, allowance, visited in (
            ("past the allowance", each - 1, paths[:1]),
            ("no allowance left", 0, paths[:1]),
            ("exactly the allowance", each, paths),
            ("within the allowance", 2 * each, paths),
        ):
            with self.subTest(label):
                spy, opened = self._opened_sources()
                with spy:
                    result = self.module._run_complexity(
                        self.root, paths, deadline, max_findings=allowance
                    )
                self.assertEqual(visited, opened)
                self.assertEqual(each * len(visited), len(result.findings))
                self.assertEqual({}, result.unanalyzed)
        spy, opened = self._opened_sources()
        with spy:
            self.module._run_complexity(self.root, paths, deadline)
        self.assertEqual(paths, opened)

    def test_a_metric_past_the_findings_budget_starts_no_later_file(self) -> None:
        # The Router's C1, through the collector: what the earlier producers and files
        # left of max_findings is the metric's allowance. No later file is opened, and
        # the existing refusal follows, with the real count, no inventory and the raw
        # reports kept.
        (self.root / "tools" / "zlater.py").write_text(
            _DIAGNOSTIC_SAMPLE, encoding="utf-8"
        )
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "a later source")
        found = self._inventory()["findings"]
        earlier = len([f for f in found if f["tool"]["id"] != "complexity"])
        metric = [f["path"] for f in found if f["tool"]["id"] == "complexity"]
        prior = len([path for path in metric if path < "tools/sample.py"])
        each = metric.count("tools/sample.py")
        self.assertEqual(each, metric.count("tools/zlater.py"))
        limit = earlier + prior + each - 1
        limits = self.module.DiagnosticLimits(max_findings=limit)
        shutil.rmtree(self.output)
        spy, opened = self._opened_sources()
        with spy, self.assertRaises(QualityEvidenceError) as raised:
            self._inventory(limits=limits)
        self.assertIn("tools/sample.py", opened)
        self.assertNotIn("tools/zlater.py", opened)
        self.assertIn(
            f"budget: {limit + 1} findings exceed max_findings {limit}",
            str(raised.exception),
        )
        self.assertEqual([], list(self.output.rglob(self.module.DIAGNOSTIC_INVENTORY)))
        self.assertTrue(list(self.output.rglob("diagnostic-ruff-every-rule.json")))

    def test_a_negative_source_bound_is_refused(self) -> None:
        # cubic on #436: read() of a negative size reads the whole file, so such a
        # bound would fail open; every other limit fails closed.
        limits = self.module.DiagnosticLimits(max_source_bytes=-2)
        with self.assertRaisesRegex(QualityEvidenceError, "max_source_bytes"):
            self._inventory(limits=limits)

    def test_a_source_is_decoded_as_python_decodes_it(self) -> None:
        # Octopus on #436: a PEP 263 encoding cookie, or a UTF-8 BOM, is valid Python,
        # and the metric parses the bounded bytes as the interpreter would.
        branchy = _DIAGNOSTIC_SAMPLE.split("def fifteen")[0]
        sources = {
            "tools/latin.py": b"# -*- coding: latin-1 -*-\nNAME = '\xe9'\n"
            + branchy.encode("latin-1"),
            "tools/bom.py": b"\xef\xbb\xbf" + branchy.encode("utf-8"),
        }
        for path, data in sources.items():
            (self.root / path).write_bytes(data)
        result = self.module._run_complexity(
            self.root, sorted(sources), time.monotonic() + 30
        )
        self.assertEqual({}, result.unanalyzed)
        self.assertEqual(
            {"tools/bom.py", "tools/latin.py"},
            {f["path"] for f in result.findings if f["rule"] == "cc"},
        )

    def test_complexity_stops_at_the_deadline(self) -> None:
        # The metric runs in this process and checks the deadline before each file.
        result = self.module._run_complexity(
            self.root, ["tools/sample.py"], time.monotonic() - 1.0
        )
        self.assertIn("deadline", result.unanalyzed["tools/sample.py"])
        self.assertEqual([], result.findings)

    def test_the_subject_reads_get_the_remaining_time(self) -> None:
        # Both identity checks, at the freeze and after collection, get what is left;
        # the state reader, git status, never runs on this path (Router #389
        # 6325382720, D1).
        seen: list[object] = []
        original = self.module.has_git_metadata

        def recording(root, **options):
            seen.append(options.get("timeout"))
            return original(root, **options)

        with (
            patch.object(self.module, "has_git_metadata", side_effect=recording),
            patch.object(
                self.module, "_git_state", side_effect=AssertionError("git status")
            ),
        ):
            self._inventory()
        self.assertEqual(2, len(seen))
        self.assertTrue(all(isinstance(t, float) and t > 0 for t in seen), seen)

    def test_findings_emitted_before_a_timeout_stay_listed(self) -> None:
        def timing_out(command, **options):
            if "mypy" in command and "--explicit-package-bases" in command:
                record = self._mypy(
                    "tests/test_sample.py",
                    self.lines["typing"],
                    11,
                    "arg-type",
                    "typed",
                )
                options["report"].write_text(
                    json.dumps(record) + '\n{"file": "tests/te', encoding="utf-8"
                )
                return None, "timed out at the inventory deadline", False
            return self._fake_run(command, **options)

        with patch("tools.quality_evidence._bounded_run", side_effect=timing_out):
            inventory = self._read(self.collect(self.root, self.output))
        found = self._find(
            inventory, "mypy", "arg-type", "tests/test_sample.py", self.lines["typing"]
        )
        self.assertEqual(1, len(found))
        reasons = {
            u["path"]: u["reason"] for u in inventory["scope"]["full"]["unanalyzed"]
        }
        self.assertIn("timed out", reasons["tests/test_sample.py"])

    def test_a_subject_that_cannot_be_re_read_is_not_called_changed(self) -> None:
        # A read that could not finish is no evidence that the subject changed
        # (Claude's round-2 review on #436), either way round. In v2 only the
        # metadata identity is read twice (Router #389 6325382720, D1).
        reread = "the subject could not be re-read after collection"
        unfrozen = "the subject has no Git metadata of its own: no commit was frozen"
        for label, effect, gap, absent in (
            ("the recheck", [True, False], reread, unfrozen),
            ("the freeze", [False, True], unfrozen, reread),
        ):
            with self.subTest(label):
                shutil.rmtree(self.output, ignore_errors=True)
                with patch.object(self.module, "has_git_metadata", side_effect=effect):
                    inventory = self._inventory()
                reason = inventory["coverage"]["reason"]
                self.assertIn(gap, reason)
                self.assertNotIn(absent, reason)
                self.assertNotIn("changed during collection", reason)

    def test_the_enumeration_gets_the_remaining_shared_budget(self) -> None:
        # Option A on #436 (the owner's 6210613320), in v2: the frozen tree's listing
        # gets the inventory's one absolute deadline, however much of it the earlier
        # reads spent, never a fresh one (Router #389 6324876845).
        clock = [1000.0]
        seen: list[object] = []
        identity = self.module.has_git_metadata
        owner = importlib.import_module("tools.exact_tree")
        listing = owner.tree_paths

        def advancing(root, **options):
            clock[0] += 100.0
            return identity(root, **options)

        def recording(root, tree, *, limits):
            seen.append(limits.deadline)
            return listing(root, tree, limits=limits)

        with (
            patch(
                "tools.quality_evidence.time.monotonic", side_effect=lambda: clock[0]
            ),
            patch.object(self.module, "has_git_metadata", side_effect=advancing),
            patch.object(owner, "tree_paths", side_effect=recording),
        ):
            self._inventory()
        self.assertEqual([1900.0], seen)

    def test_an_enumeration_that_fails_is_an_incomplete_gap(self) -> None:
        # Never an empty COMPLETE inventory, and no producer runs on an unknown set.
        # In v2 the set is the frozen tree's listing, and its refusal is named by the
        # owner's code alone (Router #389 6325382720, D3).
        owner = importlib.import_module("tools.exact_tree")
        for code in ("git-failed", "deadline"):
            with self.subTest(code=code):
                self.commands.clear()
                with patch.object(
                    owner,
                    "tree_paths",
                    side_effect=owner.ExactTreeError(code, "private detail"),
                ):
                    inventory = self._inventory()
                coverage = inventory["coverage"]
                self.assertEqual("INCOMPLETE", coverage["status"])
                self.assertIn(
                    f"cannot enumerate the frozen tree: {code}", coverage["reason"]
                )
                self.assertNotIn("no tracked Python file", coverage["reason"])
                self.assertNotIn("total", coverage)
                self.assertNotIn("private detail", json.dumps(inventory))
                self.assertIsNone(inventory["scope"]["full"]["expected"])
                self.assertEqual([], inventory["findings"])
                self.assertEqual([], self.commands)

    def test_an_index_entry_hides_nothing_and_the_residual_stays(self) -> None:
        # assume-unchanged and skip-worktree hid an edit from `git status` (Codex on
        # #436). In v2 the producers read the frozen tree, never the checkout, so a
        # hidden edit is no input and the index gap is closed; the narrower residual,
        # the producers' environment and import graph, keeps the inventory INCOMPLETE,
        # and every emitted finding stays listed (Router #389 6325382720, D1).
        self.mypy_records = {}
        self.mypy_exit = {".": 0, "tests/fixtures/one/": 0}
        cases = (
            ("clean", None, None),
            ("assume-unchanged", "tools/sample.py", "--assume-unchanged"),
            ("skip-worktree", "tests/test_sample.py", "--skip-worktree"),
        )
        for name, path, flag in cases:
            with self.subTest(index=name):
                if path is not None:
                    target = self.root / path
                    target.write_text(
                        target.read_text(encoding="utf-8") + _EXTRA_COMPLEX,
                        encoding="utf-8",
                    )
                    self._git("update-index", flag, path)
                self.assertEqual(
                    "", self._git("status", "--porcelain", "--untracked-files=no")
                )
                inventory = self._inventory()
                self.assertEqual("INCOMPLETE", inventory["coverage"]["status"])
                self.assertEqual(_SOURCE_BINDING_GAP, inventory["coverage"]["reason"])
                self.assertEqual("UNVERIFIED", inventory["source"]["source_binding"])
                self.assertEqual(
                    "EXACT_TREE_STAGED", inventory["source"]["tree_binding"]
                )
                self.assertEqual(4, inventory["coverage"]["count"])
                self.assertEqual(
                    [],
                    [
                        f
                        for f in inventory["findings"]
                        if "extra" in f.get("message", "")
                    ],
                )
                self.assertTrue(
                    self._find(
                        inventory,
                        "complexity",
                        "cc",
                        "tools/sample.py",
                        self.lines["branchy"],
                    )
                )
                self.assertTrue(
                    [f for f in inventory["findings"] if f["tool"]["id"] == "ruff"]
                )

    def test_a_complete_ruff_report_is_read_even_after_a_gap(self) -> None:
        # Codex on #436: ruff can write its whole report and then outlive the deadline.
        # What it emitted stays listed, and the gap is kept.
        def late(command, **options):
            if "ruff" in command and "--version" not in command:
                options["report"].write_text(
                    self._staged_text(json.dumps(self.ruff_records), options["cwd"]),
                    encoding="utf-8",
                )
                return None, "timed out at the inventory deadline", False
            return self._fake_run(command, **options)

        with patch("tools.quality_evidence._bounded_run", side_effect=late):
            inventory = self._read(self.collect(self.root, self.output))
        self.assertEqual(
            len(self.ruff_records),
            len([f for f in inventory["findings"] if f["tool"]["id"] == "ruff"]),
        )
        unanalyzed = {
            u["path"]: u["reason"] for u in inventory["scope"]["full"]["unanalyzed"]
        }
        self.assertIn("ruff:every-rule timed out", unanalyzed["tests/test_sample.py"])

    def test_a_version_is_recorded_only_from_a_clean_answer(self) -> None:
        # A failed run, or output that does not name the producer, records no version.
        run = Path(self.directory.name) / "versions"
        run.mkdir()
        for name, (status, text) in {
            "failed": (1, "ruff 1.0.0\n"),
            "foreign": (0, "Python 3.12.0\n"),
            "clean": (0, "ruff 0.16.0\n"),
        }.items():

            def answer(command, *, report, status=status, text=text, **options):
                report.write_text(text, encoding="utf-8")
                return status, None, False

            with (
                self.subTest(answer=name),
                patch("tools.quality_evidence._bounded_run", side_effect=answer),
            ):
                version = self.module._producer_version(
                    self.root, run, "ruff", self.module.DiagnosticLimits(), 0.0
                )
                (run / "diagnostic-ruff-version.txt").unlink()
                self.assertEqual("0.16.0" if name == "clean" else None, version)

    def test_a_truncated_ruff_report_after_a_gap_keeps_the_gap(self) -> None:
        def cut(command, **options):
            if "ruff" in command and "--version" not in command:
                options["report"].write_text('[{"filename": "tes', encoding="utf-8")
                return None, "timed out at the inventory deadline", False
            return self._fake_run(command, **options)

        with patch("tools.quality_evidence._bounded_run", side_effect=cut):
            inventory = self._read(self.collect(self.root, self.output))
        unanalyzed = {
            u["path"]: u["reason"] for u in inventory["scope"]["full"]["unanalyzed"]
        }
        self.assertEqual(
            "ruff:every-rule timed out at the inventory deadline",
            unanalyzed["tests/test_sample.py"],
        )
        self.assertEqual(
            [], [f for f in inventory["findings"] if f["tool"]["id"] == "ruff"]
        )

    def test_producer_versions_come_from_the_producers_own_runs(self) -> None:
        self.inventory = self._inventory()
        versions = {
            r["producer"]: r["version"]
            for r in self.inventory["producers"]
            if r["producer"] in ("mypy", "ruff")
        }
        self.assertEqual({"mypy": "1.0.0", "ruff": "1.0.0"}, versions)
        asked = [c for c, _, _ in self.commands if "--version" in c]
        self.assertEqual(
            [[sys.executable, "-I", "-m", p, "--version"] for p in ("mypy", "ruff")],
            asked,
        )

    def test_a_finding_on_a_withheld_symlink_is_kept_but_out_of_scope(self) -> None:
        # Codex on #436: mypy can follow an accepted file's import into a tracked
        # symlink. Its findings are listed, never dropped, and are not tracked-source
        # evidence. In v2 a link staged from the tree stays inside it; one escaping
        # the tree is refused by the owner (test_a_tracked_symlink_is_never_analyzed).
        (self.root / "tools" / "link.py").symlink_to("sample.py")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "a tracked symlink")
        self.mypy_records = {
            "tools/sample.py": [
                self._mypy("tools/link.py", 1, 13, "assignment", "followed import")
            ]
        }
        inventory = self._inventory()
        (finding,) = [f for f in inventory["findings"] if f["path"] == "tools/link.py"]
        self.assertIs(False, finding["native"]["tracked"])
        self.assertEqual("EXACT_TREE_STAGED", inventory["source"]["tree_binding"])

    def test_ruff_reports_what_its_suppression_comments_would_hide(self) -> None:
        # Codex on #436: honoring ruff's suppression comments would hide a finding.
        self._inventory()
        (ruff,) = [c for c, _, _ in self.commands if "check" in c]
        flag = "--ignore-noqa"  # a flag, not a marker -- the option under test
        self.assertIn(flag, ruff[: ruff.index("--")])

    def test_every_producer_failure_of_a_file_is_named(self) -> None:
        # Codex on #436: a file that two producers failed names both failures.
        self.mypy_exit["."] = 2
        self.ruff_text = "not json"
        inventory = self._inventory()
        reasons = {
            u["path"]: u["reason"] for u in inventory["scope"]["full"]["unanalyzed"]
        }
        self.assertIn("mypy:main aborted", reasons["tests/test_sample.py"])
        self.assertIn(
            "ruff:every-rule unparsable report", reasons["tests/test_sample.py"]
        )

    def test_every_limit_is_checked_before_any_work(self) -> None:
        # CodeAnt on #436: a negative or non-finite limit is refused up front, before
        # any producer runs, rather than failing after all the work.
        cases = [
            self.module.DiagnosticLimits(max_files=-1),
            self.module.DiagnosticLimits(max_findings=-1),
            self.module.DiagnosticLimits(max_report_bytes=-1),
            self.module.DiagnosticLimits(max_report_bytes=float("inf")),
            self.module.DiagnosticLimits(max_files=1.5),
            self.module.DiagnosticLimits(timeout_seconds="900"),
            self.module.DiagnosticLimits(timeout_seconds=10**400),
            self.module.DiagnosticLimits(timeout_seconds=float("nan")),
            self.module.DiagnosticLimits(timeout_seconds=float("inf")),
            self.module.DiagnosticLimits(timeout_seconds=0.0),
        ]
        refused = AssertionError("work started")
        with (
            patch("tools.quality_evidence._bounded_run", side_effect=refused),
            patch("tools.quality_evidence._git_state", side_effect=refused),
            patch("tools.quality_evidence.candidate_paths", side_effect=refused),
            patch("tools.quality_evidence.tempfile.mkdtemp", side_effect=refused),
        ):
            for limits in cases:
                with self.subTest(limits=limits):
                    with self.assertRaises(QualityEvidenceError):
                        self.collect(self.root, self.output, limits=limits)

    def test_each_mypy_group_has_its_own_report(self) -> None:
        # Codex on #436: tests/fixtures/a-b and tests/fixtures/a:b named one report, so
        # the second group could read the first one's diagnostics.
        reports: list[Path] = []

        def recording(command, *, report, **options):
            reports.append(report)
            return 0, None, False

        paths = [
            "tests/fixtures/a-b/x.py",
            "tests/fixtures/a:b/y.py",
            "tools/sample.py",
        ]
        run = Path(self.directory.name) / "groups"
        run.mkdir()
        with patch("tools.quality_evidence._bounded_run", side_effect=recording):
            self.module._run_mypy(
                self.root, run, paths, self.module.DiagnosticLimits(), 0.0, None
            )
        self.assertEqual(3, len(reports))
        self.assertEqual(len(reports), len(set(reports)))

    def test_a_complexity_range_counts_characters_not_bytes(self) -> None:
        # CodeAnt on #436: the AST's columns are UTF-8 byte offsets.
        branches = "".join(f"    if a == {i}:\n        a += 1\n" for i in range(16))
        source = "def accented(a):\n" + branches + '    return "\u00e9\u00e9\u00e9"\n'
        (self.root / "tools" / "accented.py").write_text(source, encoding="utf-8")
        result = self.module._run_complexity(
            self.root, ["tools/accented.py"], time.monotonic() + 30
        )
        (finding,) = result.findings
        self.assertEqual(
            len(source.splitlines()[-1]) + 1, finding["range"]["end_column"]
        )

    def test_a_truncated_producer_report_writes_no_inventory(self) -> None:
        # Codex on #436: a report cut at max_report_bytes drops what followed, so, as
        # over max_findings, no inventory is written and the raw reports stay.
        def cut(command, **options):
            if "ruff" in command and "--version" not in command:
                options["report"].write_text('[{"filename": "tes', encoding="utf-8")
                return None, "budget: the output exceeds max_report_bytes", True
            return self._fake_run(command, **options)

        with (
            patch("tools.quality_evidence._bounded_run", side_effect=cut),
            self.assertRaisesRegex(QualityEvidenceError, "no inventory was written"),
        ):
            self.collect(self.root, self.output)
        # Nothing is published, and the cut report stays for inspection (cubic on #436).
        self.assertEqual([], list(self.output.glob("*/diagnostic-inventory.json")))
        self.assertEqual(
            1,
            len(list(self.output.glob("*/diagnostic-*-ruff.json")))
            + len(list(self.output.glob("*/diagnostic-ruff-every-rule.json"))),
        )

    def test_a_capture_that_fails_mid_report_writes_no_inventory(self) -> None:
        # Codex on #436, by the Router's V1 (6229993455): a read or write failure while
        # a report streams kept its valid prefix and published it with a gap. It is an
        # invalid capture, as a cut is: no inventory, and the raw prefix kept.
        script, first = self._two_batches()
        real_read = os.read
        reads: list[int] = []

        def failing_read(fd, size):
            if size != 65_536:
                return real_read(fd, size)
            reads.append(size)
            if len(reads) == 1:
                return real_read(fd, size)
            raise OSError(5, "Input/output error")

        real_new_file = self.module._new_file

        def failing_sink(path):
            stream = real_new_file(path)
            if not path.name.endswith("-mypy-main.jsonl"):
                return stream
            writes: list[bytes] = []
            real_write = stream.write

            def write(chunk):
                writes.append(chunk)
                if len(writes) > 1:
                    raise OSError(28, "No space left on device")
                return real_write(chunk)

            stream.write = write
            return stream

        def unexpected_sink(path):
            stream = failing_sink(path)
            if path.name.endswith("-mypy-main.jsonl"):
                real_write = stream.write

                def write(chunk):
                    try:
                        return real_write(chunk)
                    except OSError as exc:
                        raise ValueError("an unclassified sink failure") from exc

                stream.write = write
            return stream

        real_popen = self.module.subprocess.Popen

        def no_stdout(command, **options):
            process = real_popen(command, **options)
            if command[0] == sys.executable:
                process.stdout.close()
                process.stdout = None
            return process

        cases = (
            (
                "a read error",
                patch.object(self.module.os, "read", side_effect=failing_read),
            ),
            (
                "a write error",
                patch.object(self.module, "_new_file", side_effect=failing_sink),
            ),
            # The Router's G2 (6231894979): an unclassified failure, or no stdout pipe at
            # all, is an unknown capture too.
            (
                "an unexpected failure",
                patch.object(self.module, "_new_file", side_effect=unexpected_sink),
            ),
            (
                "no stdout pipe",
                patch.object(self.module.subprocess, "Popen", side_effect=no_stdout),
            ),
        )
        real_producers = self.module._run_producers

        def during_producers(failure):
            def run(*args, **kwargs):
                with failure:
                    return real_producers(*args, **kwargs)

            return patch.object(self.module, "_run_producers", side_effect=run)

        for label, failure in cases:
            with self.subTest(label):
                reads.clear()
                shutil.rmtree(self.output, ignore_errors=True)
                with self._with_a_real_main_mypy(script), during_producers(failure):
                    with self.assertRaisesRegex(
                        QualityEvidenceError, "no inventory was written"
                    ):
                        self.collect(self.root, self.output)
                self.assertEqual(
                    [], list(self.output.rglob(self.module.DIAGNOSTIC_INVENTORY))
                )
                (report,) = self.output.rglob("diagnostic-*-mypy-main.jsonl")
                kept = "" if label == "no stdout pipe" else first
                self.assertEqual(kept, report.read_text(encoding="utf-8"))

    def test_mypy_positions_without_a_location_are_kept(self) -> None:
        # The Router's P1 (6231894979): mypy writes line -1 and column -1 itself, for an
        # error without a location and for a whole-line one (measured on #436). They
        # stay listed, as no range and as column 1.
        nowhere = {
            **self._mypy("tools/sample.py", -1, -1, "misc", "no location"),
            "end_line": -1,
            "end_column": 0,
        }
        whole = {
            **self._mypy("tools/sample.py", 2, -1, "unused-ignore", "whole line"),
            "end_line": 2,
            "end_column": -1,
        }
        self.mypy_text = json.dumps(nowhere) + "\n" + json.dumps(whole) + "\n"
        inventory = self._inventory()
        found = {
            f["message"]: f.get("range")
            for f in inventory["findings"]
            if f["tool"]["id"] == "mypy"
        }
        self.assertIsNone(found["no location"])
        self.assertEqual(
            {"start_line": 2, "start_column": 1, "end_line": 2, "end_column": 1},
            found["whole line"],
        )

    def test_a_mypy_report_past_the_findings_budget_retains_only_the_allowance(
        self,
    ) -> None:
        # CodeAnt on #436, by the Router's M1 (6231894979): one report within
        # max_report_bytes built every record's finding before the refusal. Past the
        # allowance, each record is still validated and counted, never kept, and the
        # refusal names the real count.
        peak = [0]
        real = self.module._ProducerResult

        class Peaked(list):
            def append(self, item):
                super().append(item)
                peak[0] = max(peak[0], len(self))

            def __iadd__(self, other):
                result = super().__iadd__(other)
                peak[0] = max(peak[0], len(self))
                return result

        def make(*args, **kwargs):
            made = real(*args, **kwargs)
            made.findings = Peaked(made.findings)
            return made

        valid = [
            self._mypy("tools/sample.py", n, 1, "assignment", f"valid {n}")
            for n in range(1, 7)
        ]
        lines = [json.dumps(r) for r in valid]
        lines.insert(4, "{not json")
        self.mypy_text = "".join(line + "\n" for line in lines)
        limits = self.module.DiagnosticLimits(max_findings=3)
        with (
            patch.object(self.module, "_ProducerResult", side_effect=make),
            self.assertRaisesRegex(
                QualityEvidenceError, "budget: 6 findings exceed max_findings 3"
            ),
        ):
            self._inventory(limits=limits)
        self.assertLessEqual(peak[0], 4)

    def test_a_git_read_that_does_not_exit_cleanly_is_mapped_after_one_reap(
        self,
    ) -> None:
        # The Router's G1 and S-b (6232967571), and five mutants that survived on
        # 818812e6: a Git read stopped by its deadline is TimeoutExpired, a reaped read
        # error is that error, and every other outcome is the comparison's own reason
        # with the cleanup's detail. The child is reaped once, never by the mapper.
        drained = self.module.bounded_process.Drained
        refused = self.module._ComparisonRefused
        error = OSError(errno.EIO, "/host/private")
        failed = "its process could not be reaped: OSError"
        cases = (
            ("deadline", drained("deadline"), None, subprocess.TimeoutExpired, None),
            ("error", drained("error", error=error), None, OSError, None),
            (
                "cap, failed reap",
                drained("cap", stream="stdout"),
                failed,
                refused,
                f"the comparison's Git output exceeds max_report_bytes; {failed}",
            ),
            (
                "deadline, failed reap",
                drained("deadline"),
                failed,
                refused,
                f"the comparison's Git output was not read whole (deadline); {failed}",
            ),
        )
        for label, outcome, reaped, raised, reason in cases:
            with self.subTest(label):
                deadline = time.monotonic() + 30
                reap = Mock(
                    side_effect=lambda process, reaped=reaped: (process.wait(), reaped)[
                        1
                    ]
                )
                with (
                    patch.object(
                        self.module.bounded_process, "drain", return_value=outcome
                    ),
                    patch.object(self.module, "_reap", reap),
                    self.assertRaises(raised) as caught,
                ):
                    self.module._diagnostic_git(
                        self.root, deadline, "rev-parse", "HEAD", cap=4096
                    )
                self.assertEqual(1, reap.call_count)
                if label == "deadline":
                    self.assertEqual("git", caught.exception.cmd)
                if label == "error":
                    self.assertIs(error, caught.exception)
                if reason is not None:
                    self.assertEqual(reason, str(caught.exception))
        with self.subTest("an unavailable output, failed reap"):
            deadline = time.monotonic() + 30
            process = SimpleNamespace(stdout=None, returncode=None)
            with (
                patch("tools.quality_evidence.subprocess.Popen", return_value=process),
                patch.object(self.module, "_reap", Mock(return_value=failed)),
                self.assertRaises(refused) as caught,
            ):
                self.module._diagnostic_git(
                    self.root, deadline, "rev-parse", "HEAD", cap=4096
                )
            self.assertEqual(
                f"the comparison's Git output is unavailable; {failed}",
                str(caught.exception),
            )

    def test_an_interrupt_during_a_git_read_reaps_the_child_and_is_raised_again(
        self,
    ) -> None:
        # Codex on #436, the Router's K-b at the comparison's Git read: a cancellation
        # escaping the shared drain left the Git child running. It is reaped once,
        # through the existing owner, its pipe is closed, and the same exception is
        # raised again; a failed reap is noted on it.
        from tools import candidate_prepare

        slow = Path(self.directory.name) / "slow-git"
        slow.write_text("#!/bin/sh\nexec sleep 30\n", encoding="utf-8")
        slow.chmod(0o755)
        real_reap = self.module.bounded_process.reap

        def read(interrupt, reap):
            seen = {}

            def interrupted(process, *args, **kwargs):
                seen["process"] = process
                raise interrupt

            deadline = time.monotonic() + 30
            with (
                patch.object(
                    candidate_prepare, "_git_executable", return_value=str(slow)
                ),
                patch.object(
                    self.module.bounded_process, "drain", side_effect=interrupted
                ),
                patch.object(self.module.bounded_process, "reap", reap),
                self.assertRaises(type(interrupt)) as raised,
            ):
                self.module._diagnostic_git(
                    self.root, deadline, "rev-parse", "HEAD", cap=4096
                )
            return raised.exception, seen["process"]

        for kind in (KeyboardInterrupt, SystemExit):
            with self.subTest(kind.__name__):
                interrupt, reap = kind(), Mock(side_effect=real_reap)
                raised, process = read(interrupt, reap)
                self.assertIs(interrupt, raised)
                self.assertEqual([], getattr(raised, "__notes__", []))
                self.assertEqual(1, reap.call_count)
                self.assertIsNotNone(process.poll())
                self.assertTrue(process.stdout.closed)
        with self.subTest("a reap that fails"):
            interrupt = KeyboardInterrupt()
            reap = Mock(return_value=subprocess.TimeoutExpired("git", 5))
            raised, process = read(interrupt, reap)
            process.kill()
            process.wait()
            self.assertIs(interrupt, raised)
            self.assertEqual(
                ["its process could not be reaped within 5 seconds"], raised.__notes__
            )
        with self.subTest("a clean or a non-zero exit is not reaped again"):
            reap = Mock(side_effect=real_reap)
            deadline = time.monotonic() + 30
            with patch.object(self.module.bounded_process, "reap", reap):
                self.module._diagnostic_git(self.root, deadline, "rev-parse", "HEAD")
                with self.assertRaises(subprocess.CalledProcessError):
                    self.module._diagnostic_git(
                        self.root, deadline, "rev-parse", "--verify", "no-such-ref"
                    )
            self.assertEqual(0, reap.call_count)
        with self.subTest("a failed spawn reaps nothing"):
            reap = Mock(side_effect=real_reap)
            deadline = time.monotonic() + 30
            with (
                patch.object(self.module.bounded_process, "reap", reap),
                patch(
                    "tools.quality_evidence.subprocess.Popen",
                    side_effect=FileNotFoundError(errno.ENOENT, "/host/private"),
                ),
                self.assertRaises(FileNotFoundError),
            ):
                self.module._diagnostic_git(self.root, deadline, "rev-parse", "HEAD")
            self.assertEqual(0, reap.call_count)
        with self.subTest("an interrupted comparison writes no inventory"):
            reap = Mock(side_effect=real_reap)
            with (
                patch.object(
                    self.module.bounded_process, "drain", side_effect=KeyboardInterrupt
                ),
                patch.object(self.module.bounded_process, "reap", reap),
                self.assertRaises(KeyboardInterrupt),
            ):
                self._inventory(base=self.base)
            self.assertEqual(1, reap.call_count)
            self.assertEqual(
                [], list(self.output.rglob(self.module.DIAGNOSTIC_INVENTORY))
            )

    def test_ruff_keeps_only_what_the_earlier_producers_left(self) -> None:
        # The Router's R1, and the mutant that survived on 818812e6: ruff's allowance
        # is what mypy left of max_findings, so the producers keep at most
        # max_findings + 1 findings, the one witness, while the count stays raw.
        self.mypy_records = {
            "tools/sample.py": [
                self._mypy("tools/sample.py", 2, column, "assignment", f"m{column}")
                for column in (1, 2)
            ]
        }
        self.ruff_records = [
            self._ruff("tests/test_sample.py", n, 1, "F401", f"r{n}")
            for n in range(1, 11)
        ]
        limits = self.module.DiagnosticLimits(max_findings=3)
        run = Path(tempfile.mkdtemp(prefix="producers-", dir=self.directory.name))
        deadline = time.monotonic() + 30
        with patch("tools.quality_evidence._bounded_run", side_effect=self._fake_run):
            result = self.module._run_producers(
                self.root,
                run,
                ["tests/test_sample.py", "tools/sample.py"],
                limits,
                [],
                deadline,
                _EVERY_FAMILY,
                self.module._Changes(frozenset(), {}),
            )
        self.assertEqual(12, result.count())
        self.assertEqual(4, len(result.findings))

    def test_each_git_read_is_held_to_its_cap_exactly(self) -> None:
        # The Router's G1 (6231894979): rev-parse HEAD writes 41 bytes. A cap of 41
        # reads them whole; a cap of 40 is the comparison's own reason, never a prefix.
        deadline = time.monotonic() + 30
        head = self._git("rev-parse", "HEAD")
        answer = self.module._diagnostic_git(
            self.root, deadline, "rev-parse", "HEAD", cap=41
        )
        self.assertEqual(head + "\n", answer)
        with self.assertRaisesRegex(
            ValueError, "the comparison's Git output exceeds max_report_bytes"
        ):
            self.module._diagnostic_git(
                self.root, deadline, "rev-parse", "HEAD", cap=40
            )

    def test_a_spent_budget_spawns_no_git_and_a_failed_read_is_its_exit(self) -> None:
        # The Router's G1: past the deadline no Git starts, and a non-zero exit stays
        # CalledProcessError.
        spent, deadline = time.monotonic() - 1, time.monotonic() + 30
        with patch(
            "tools.quality_evidence.subprocess.Popen",
            side_effect=AssertionError("Git started past the deadline"),
        ):
            with self.assertRaisesRegex(
                subprocess.SubprocessError, "deadline had passed"
            ):
                self.module._diagnostic_git(
                    self.root, spent, "rev-parse", "HEAD", cap=4096
                )
        with self.assertRaises(subprocess.CalledProcessError):
            self.module._diagnostic_git(
                self.root,
                deadline,
                "rev-parse",
                "--verify",
                "--end-of-options",
                "f" * 40 + "^{commit}",
                cap=4096,
            )

    def test_the_base_check_and_the_name_list_each_meet_the_cap(self) -> None:
        # The Router's G1: every Git read is capped. The base check's 41 bytes cross a
        # cap of 40 before any diff is read; with a cap of 100, the check passes, and a
        # long name list crosses it before any patch is read.
        for n in range(8):
            (
                self.root / "tools" / f"a_long_module_name_for_the_list_{n}.py"
            ).write_text("VALUE = 1\n", encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "many changed names")
        real = self.module._diagnostic_git
        for cap, read_last, reads in ((40, "rev-parse", 1), (100, "diff", 2)):
            with self.subTest(cap=cap):
                spy = Mock(side_effect=real)
                deadline = time.monotonic() + 30
                with (
                    patch.object(self.module, "_diagnostic_git", spy),
                    self.assertRaisesRegex(
                        ValueError,
                        "the comparison's Git output exceeds max_report_bytes",
                    ),
                ):
                    self.module._diff_scope(
                        self.root, self.base, deadline, cap=cap, head=self._head()
                    )
                verbs = [call.args[2] for call in spy.call_args_list]
                self.assertEqual(reads, len(verbs), verbs)
                self.assertEqual(read_last, verbs[-1])

    def test_a_changed_name_that_is_not_utf8_survives_the_read(self) -> None:
        # The Router's G1: decoded only after a complete exit, with surrogateescape, as
        # before, so a name with a byte that is not UTF-8 is kept exactly.
        raw = os.fsencode(self.root / "tools") + b"/odd\xffname.py"
        with open(raw, "wb") as stream:
            stream.write(b"VALUE = 1\n")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "a name that is not UTF-8")
        diff, _lines = self.module._diff_scope(
            self.root, self.base, time.monotonic() + 30, head=self._head()
        )
        self.assertIn("tools/odd\udcffname.py", diff["changed_paths"])

    def test_a_comparison_whose_git_output_passes_the_cap_is_a_gap(self) -> None:
        # CodeAnt on #436, by the Router's G1 (6231894979): Git's output was read whole.
        # Each read is drained under max_report_bytes, and a crossing is the
        # comparison's named gap, never a prefix compared as if whole.
        sample = self.root / "tools" / "sample.py"
        sample.write_text(
            sample.read_text(encoding="utf-8")
            + "".join(f"# added line {n}\n" for n in range(2000)),
            encoding="utf-8",
        )
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "a large change")
        limits = self.module.DiagnosticLimits(max_report_bytes=8192)
        inventory = self._inventory(base=self.base, limits=limits)
        self.assertIsNone(inventory["scope"]["diff"])
        self.assertEqual(
            {None}, {f["native"]["in_diff"] for f in inventory["findings"]}
        )
        self.assertIn(
            f"cannot compare with base {self.base}: the comparison's Git output exceeds max_report_bytes",
            inventory["coverage"]["reason"],
        )

    def test_ruff_past_the_findings_budget_retains_only_the_allowance(self) -> None:
        # CodeAnt on #436, by the Router's R1 (6232786300): ruff kept every record's
        # finding before the refusal. As M1 for mypy, past the allowance a record is
        # validated and counted, never kept: the first above it is the one witness.
        def valid(n: int) -> dict[str, object]:
            return self._ruff("tests/test_sample.py", n, 1, "F401", f"r{n}")

        for label, records, allowance, kept, counted in (
            ("none", [], 3, 0, 0),
            ("exactly the allowance", [valid(n) for n in range(1, 4)], 3, 3, 3),
            ("one past it", [valid(n) for n in range(1, 5)], 3, 4, 4),
            ("many past it", [valid(n) for n in range(1, 41)], 3, 4, 40),
            ("duplicates", [valid(1)] * 6, 3, 4, 6),
        ):
            with self.subTest(label):
                result, _run = self._ruff_alone(records, allowance)
                self.assertEqual(kept, len(result.findings))
                self.assertEqual(counted, result.count())
        with self.subTest("a malformed record past the allowance, then valid ones"):
            records = [valid(n) for n in range(1, 5)] + [{"code": "F401"}] + [valid(9)]
            result, run = self._ruff_alone(records, 3)
            self.assertEqual(4, len(result.findings))
            self.assertEqual(5, result.count())
            self.assertIn(
                "ruff unparsable report", result.unanalyzed["tests/test_sample.py"]
            )
            self.assertEqual(
                json.dumps(records), (run / "diagnostic-ruff.json").read_text("utf-8")
            )

    def test_ruff_past_the_findings_budget_is_refused_with_its_real_count(self) -> None:
        # The Router's R1: the refusal names the raw count, no later producer starts,
        # and no inventory is written.
        self.mypy_records = {}
        self.ruff_records = [
            self._ruff("tests/test_sample.py", n, 1, "F401", f"r{n}")
            for n in range(1, 11)
        ]
        limits = self.module.DiagnosticLimits(max_findings=3)
        with (
            patch.object(
                self.module, "_run_complexity", side_effect=AssertionError("started")
            ),
            self.assertRaisesRegex(
                QualityEvidenceError, "budget: 10 findings exceed max_findings 3"
            ),
        ):
            self._inventory(limits=limits)
        self.assertEqual([], list(self.output.rglob(self.module.DIAGNOSTIC_INVENTORY)))

    def test_a_deadline_crossed_while_publishing_is_recorded(self) -> None:
        # Codex on #436, by the Router's T1 (6232786300): the last check preceded the
        # document and its serialization. The clock is now read after serialization,
        # with the output handle already open, and a late result is rebuilt once.
        for stage in ("serialization", "output"):
            with self.subTest(stage):
                shutil.rmtree(self.output, ignore_errors=True)
                clock, dumps, new_file = self._late_by(stage)
                with clock, dumps, new_file:
                    inventory = self._inventory()
                reason = inventory["coverage"]["reason"]
                self.assertEqual(
                    1, reason.count("the inventory ran past its deadline"), reason
                )

    def test_an_on_time_inventory_is_published_once_without_the_late_gap(self) -> None:
        # The Router's T1: an on-time inventory is unchanged, and every inventory is one
        # payload write to its one destination.
        writes: list[int] = []
        real_new_file = self.module._new_file

        def counting(path):
            stream = real_new_file(path)
            if path.name == self.module.DIAGNOSTIC_INVENTORY:
                real_write = stream.write

                def write(data):
                    writes.append(len(data))
                    return real_write(data)

                stream.write = write
            return stream

        with patch.object(self.module, "_new_file", side_effect=counting):
            inventory = self._inventory()
        self.assertNotIn("ran past its deadline", inventory["coverage"]["reason"])
        self.assertEqual(1, len(writes))

    def test_a_report_nested_past_the_decoders_recursion_is_a_gap(self) -> None:
        # Codex on #436: valid JSON nested past the decoder's recursion, well inside
        # max_report_bytes, raised RecursionError out of the parsers. It is the report's
        # or the line's existing unparsable gap, by its type.
        nested = "[" * 100_000 + "]" * 100_000
        self.assertLess(
            len(nested), self.module.DEFAULT_DIAGNOSTIC_LIMITS.max_report_bytes
        )
        with self.subTest("ruff"):
            self.ruff_text = nested
            result, _run = self._ruff_alone([], 3)
            self.assertEqual([], result.findings)
            self.assertIn(
                "ruff unparsable report: RecursionError",
                result.unanalyzed["tests/test_sample.py"],
            )
        self.ruff_text = None
        with self.subTest("mypy"):
            first = self._mypy("tools/sample.py", 2, 1, "assignment", "first")
            later = self._mypy("tools/sample.py", 2, 2, "assignment", "later")
            self.mypy_text = "\n".join(
                [json.dumps(first), nested, json.dumps(later), ""]
            )
            inventory = self._inventory()
            messages = {
                f["message"] for f in inventory["findings"] if f["tool"]["id"] == "mypy"
            }
            self.assertLessEqual({"first", "later"}, messages)
            reasons = {
                u["path"]: u["reason"] for u in inventory["scope"]["full"]["unanalyzed"]
            }
            self.assertIn(
                "unparsable mypy report: RecursionError", reasons["tools/sample.py"]
            )

    def test_a_failed_publication_leaves_no_inventory(self) -> None:
        # Codex on #436: a write or close failure left a partial inventory at its
        # canonical path. The file the collector created is removed, the error is
        # raised as before, and the raw reports stay.
        real = self.module._new_file

        def failing(path, stage):
            stream = real(path)
            if path.name != self.module.DIAGNOSTIC_INVENTORY:
                return stream
            if stage == "write":

                def write(data):
                    stream.raw.write(data[:100])
                    raise OSError(errno.ENOSPC, "no space")

                stream.write = write
            else:
                close = stream.close

                def fail() -> None:
                    close()
                    raise OSError(errno.ENOSPC, "no space")

                stream.close = fail
            return stream

        for stage in ("write", "close"):
            with self.subTest(stage):
                shutil.rmtree(self.output, ignore_errors=True)
                with (
                    patch.object(
                        self.module,
                        "_new_file",
                        side_effect=lambda path, stage=stage: failing(path, stage),
                    ),
                    self.assertRaises(OSError),
                ):
                    self._inventory()
                self.assertEqual(
                    [], list(self.output.rglob(self.module.DIAGNOSTIC_INVENTORY))
                )
                self.assertTrue(
                    list(self.output.rglob("diagnostic-ruff-every-rule.json"))
                )
        with self.subTest("the late branch's rebuild fails"):
            shutil.rmtree(self.output, ignore_errors=True)
            clock, dumps = [1000.0], json.dumps
            documents = [0]

            def failing_dumps(value, *args, **kwargs):
                if (
                    isinstance(value, dict)
                    and value.get("schema") == self.module.DIAGNOSTIC_SCHEMA
                ):
                    documents[0] += 1
                    if documents[0] == 2:
                        raise MemoryError
                return dumps(value, *args, **kwargs)

            def opening(path):
                if path.name == self.module.DIAGNOSTIC_INVENTORY:
                    clock[0] = 10_000.0
                return real(path)

            with (
                patch.object(
                    self.module.time, "monotonic", side_effect=lambda: clock[0]
                ),
                patch.object(self.module.json, "dumps", side_effect=failing_dumps),
                patch.object(self.module, "_new_file", side_effect=opening),
                self.assertRaises(MemoryError),
            ):
                self._inventory()
            self.assertEqual(
                [], list(self.output.rglob(self.module.DIAGNOSTIC_INVENTORY))
            )

    def test_a_publication_never_removes_what_it_did_not_create(self) -> None:
        # The Router's P-a: a destination that already exists is refused by the
        # exclusive creation and kept byte for byte; when removing the partial file
        # fails, the primary error is raised, the removal failure is named by its type,
        # and the file is honestly still there.
        run = Path(tempfile.mkdtemp(prefix="publish-", dir=self.directory.name))
        existing = run / self.module.DIAGNOSTIC_INVENTORY
        existing.write_bytes(b"not ours\n")
        arguments = dict(
            source={"revision": None},
            limits=self.module.DiagnosticLimits(),
            profile=_EVERY_FAMILY,
            origin="argument",
            result=self.module._ProducerResult(),
            expected=[],
            diff=None,
            findings=[],
            gaps=[],
        )
        deadline = time.monotonic() + 30
        with self.assertRaises(FileExistsError):
            self.module._publish(run, deadline, **arguments)
        self.assertEqual(b"not ours\n", existing.read_bytes())
        existing.unlink()
        real = self.module._new_file

        def partial(path):
            stream = real(path)

            def write(data):
                stream.raw.write(data[:10])
                raise OSError(errno.ENOSPC, "no space")

            stream.write = write
            return stream

        with (
            patch.object(self.module, "_new_file", side_effect=partial),
            patch.object(
                self.module.os, "unlink", side_effect=OSError(errno.EACCES, "denied")
            ),
            self.assertRaises(OSError) as raised,
        ):
            self.module._publish(run, deadline, **arguments)
        self.assertEqual(errno.ENOSPC, raised.exception.errno)
        notes = getattr(raised.exception, "__notes__", [])
        self.assertEqual(1, len(notes), notes)
        self.assertIn("could not be removed: PermissionError", notes[0])
        self.assertTrue(existing.exists())

    def test_a_record_that_names_no_file_is_a_malformed_record(self) -> None:
        # Codex on #436, by the Router's M2 (6241642961): a mypy file that names only
        # its group's root, or a ruff filename that resolves to the repository root,
        # names no file, and was published as a finding at the root. In the main and
        # the fixture groups alike it is its report's malformed record: the gap is
        # named, no finding is kept for it, the valid records after it are still read,
        # and a valid relative spelling stays a finding.
        groups = {
            "": ("tools/sample.py", "mypy:main"),
            "tests/fixtures/one/": (
                "tests/fixtures/one/baseline.py",
                "mypy:tests/fixtures/one",
            ),
        }
        # Ruff reports nothing and exits 0, so each reason is the mypy group's alone.
        self.ruff_records, self.ruff_exit = [], 0
        for name in ("", ".", "./", "./."):
            with self.subTest(producer="mypy", name=name):
                shutil.rmtree(self.output, ignore_errors=True)
                self.mypy_records = {
                    path: [
                        self._mypy(prefix + name, 1, 1, "misc", f"rootless {group}"),
                        self._mypy(path, 1, 1, "misc", f"later {group}"),
                    ]
                    for prefix, (path, group) in groups.items()
                }
                self.mypy_records["tools/sample.py"].append(
                    self._mypy("./tools/sample.py", 1, 1, "misc", "a dotted spelling")
                )
                self.mypy_exit = {".": 1, "tests/fixtures/one/": 1}
                inventory = self._inventory()
                messages = {
                    f["message"]
                    for f in inventory["findings"]
                    if f["tool"]["id"] == "mypy"
                }
                self.assertEqual(
                    {
                        "later mypy:main",
                        "later mypy:tests/fixtures/one",
                        "a dotted spelling",
                    },
                    messages,
                )
                unanalyzed = {
                    u["path"]: u["reason"]
                    for u in inventory["scope"]["full"]["unanalyzed"]
                }
                for path, group in groups.values():
                    self.assertEqual(
                        f"{group} unparsable mypy report: ValueError", unanalyzed[path]
                    )
        # Ruff exits 1 with its finding records again.
        self.ruff_exit = 1
        later_ruff = self._ruff("tests/test_sample.py", 3, 1, "F401", "later")
        for name in ("", ".", "./", str(self.root.resolve()), "tests/.."):
            with self.subTest(producer="ruff", name=name):
                rootless = {
                    **self._ruff("tests/test_sample.py", 2, 1, "F401", "rootless"),
                    "filename": name,
                }
                result, _run = self._ruff_alone([rootless, later_ruff], 10)
                self.assertEqual(["later"], [f["message"] for f in result.findings])
                self.assertIn(
                    "ruff unparsable report", result.unanalyzed["tests/test_sample.py"]
                )
        for name in ("tests/test_sample.py", "./tests/test_sample.py"):
            with self.subTest(producer="ruff", relative=name):
                relative = {
                    **self._ruff("tests/test_sample.py", 2, 1, "F401", "relative"),
                    "filename": name,
                }
                result, _run = self._ruff_alone([relative], 10)
                self.assertEqual(
                    [("tests/test_sample.py", "relative")],
                    [(f["path"], f["message"]) for f in result.findings],
                )
                self.assertNotIn("tests/test_sample.py", result.unanalyzed)

    def test_a_filename_with_a_nul_is_a_malformed_record(self) -> None:
        # Codex on #436, by the Router's M2: a mypy file holding a NUL names no file a
        # path can reach, and was published as a finding, with no gap. In the main and
        # the fixture groups it is the report's malformed record; ruff's resolution
        # already refuses one.
        groups = {
            "": ("tools/sample.py", "mypy:main"),
            "tests/fixtures/one/": (
                "tests/fixtures/one/baseline.py",
                "mypy:tests/fixtures/one",
            ),
        }
        self.ruff_records, self.ruff_exit = [], 0
        # The Router's 6244363609: valid records before and after it both survive, and
        # the raw report keeps the producer's own bytes.
        self.mypy_records = {
            path: [
                self._mypy(path, 1, 1, "misc", f"earlier {group}"),
                self._mypy(prefix + "bad\0.py", 1, 1, "misc", f"nul {group}"),
                self._mypy(path, 1, 1, "misc", f"later {group}"),
            ]
            for prefix, (path, group) in groups.items()
        }
        self.mypy_exit = {".": 1, "tests/fixtures/one/": 1}
        inventory = self._inventory()
        found = {
            f["message"]: (f["path"], f["native"]["tracked"])
            for f in inventory["findings"]
            if f["tool"]["id"] == "mypy"
        }
        self.assertEqual(
            {
                f"{when} {group}": (path, True)
                for path, group in groups.values()
                for when in ("earlier", "later")
            },
            found,
        )
        reports = "".join(
            report.read_text(encoding="utf-8")
            for report in self.run_directory.glob("diagnostic-*-mypy-*.jsonl")
        )
        self.assertEqual(2, reports.count('"file": "bad\\u0000.py"'))
        unanalyzed = {
            u["path"]: u["reason"] for u in inventory["scope"]["full"]["unanalyzed"]
        }
        for path, group in groups.values():
            self.assertEqual(
                f"{group} unparsable mypy report: ValueError", unanalyzed[path]
            )
        self.ruff_exit = 1
        nul = {
            **self._ruff("tests/test_sample.py", 2, 1, "F401", "nul"),
            "filename": "bad\0.py",
        }
        later = self._ruff("tests/test_sample.py", 3, 1, "F401", "later")
        result, _run = self._ruff_alone([nul, later], 10)
        self.assertEqual(["later"], [f["message"] for f in result.findings])
        self.assertIn(
            "ruff unparsable report", result.unanalyzed["tests/test_sample.py"]
        )

    def test_a_valid_mypy_spelling_is_keyed_by_its_canonical_path(self) -> None:
        # Claude on #436, by the Router's M2 (6242233401): a valid mypy file spelled
        # "./tools/sample.py" was kept verbatim, so a tracked file read as untracked and
        # its changed lines were looked up under the wrong key. In the main and the
        # fixture groups, the finding is keyed by its canonical relative path, the
        # report keeps the producer's own spelling, a later valid record is still
        # read, and a malformed path is still the report's gap.
        sample = self.root / "tools" / "sample.py"
        lines = sample.read_text(encoding="utf-8").split("\n")
        lines[0] += "  # changed"
        sample.write_text("\n".join(lines), encoding="utf-8")
        (self.root / "tests" / "fixtures" / "one" / "baseline.py").write_text(
            "VALUE = 2\n", encoding="utf-8"
        )
        self._git("commit", "-q", "-am", "head")
        self.ruff_records = []
        spellings = (
            ("./tools/sample.py", "./baseline.py"),
            ("tools//sample.py", ".//baseline.py"),
            ("tools/./sample.py", "././baseline.py"),
        )
        for main, fixture in spellings:
            with self.subTest(main=main, fixture=fixture):
                shutil.rmtree(self.output, ignore_errors=True)
                self.mypy_records = {
                    "tools/sample.py": [
                        self._mypy(main, 1, 1, "misc", "spelled main"),
                        self._mypy("tools/sample.py", 1, 1, "misc", "later main"),
                    ],
                    "tests/fixtures/one/baseline.py": [
                        self._mypy(
                            "tests/fixtures/one/" + fixture,
                            1,
                            1,
                            "misc",
                            "spelled fixture",
                        ),
                        self._mypy(
                            "tests/fixtures/one/baseline.py",
                            1,
                            1,
                            "misc",
                            "later fixture",
                        ),
                    ],
                }
                self.mypy_exit = {".": 1, "tests/fixtures/one/": 1}
                inventory = self._inventory(base=self.base)
                keyed = {
                    f["message"]: (
                        f["path"],
                        f["native"]["tracked"],
                        f["native"]["in_diff"],
                    )
                    for f in inventory["findings"]
                    if f["tool"]["id"] == "mypy"
                }
                self.assertEqual(
                    {
                        "spelled main": ("tools/sample.py", True, True),
                        "later main": ("tools/sample.py", True, True),
                        "spelled fixture": (
                            "tests/fixtures/one/baseline.py",
                            True,
                            True,
                        ),
                        "later fixture": ("tests/fixtures/one/baseline.py", True, True),
                    },
                    keyed,
                )
                reports = "".join(
                    report.read_text(encoding="utf-8")
                    for report in self.run_directory.glob("diagnostic-*-mypy-*.jsonl")
                )
                for spelling in (main, fixture):
                    self.assertIn(json.dumps({"file": spelling})[1:-1], reports)
        with self.subTest("a malformed path is still the gap"):
            shutil.rmtree(self.output, ignore_errors=True)
            self.mypy_records = {
                "tools/sample.py": [
                    self._mypy("tools/../tools/sample.py", 1, 1, "misc", "malformed"),
                    self._mypy("tools/sample.py", 1, 1, "misc", "later main"),
                ]
            }
            self.mypy_exit = {".": 1, "tests/fixtures/one/": 0}
            inventory = self._inventory(base=self.base)
            messages = {
                f["message"] for f in inventory["findings"] if f["tool"]["id"] == "mypy"
            }
            self.assertEqual({"later main"}, messages)
            unanalyzed = {
                u["path"]: u["reason"] for u in inventory["scope"]["full"]["unanalyzed"]
            }
            self.assertIn(
                "mypy:main unparsable mypy report", unanalyzed["tools/sample.py"]
            )

    def test_the_metric_parses_with_the_analyzers_declared_grammar(self) -> None:
        # Codex on #436: the metric parsed with the host's grammar while mypy and ruff
        # target Python 3.11, so a tracked file in 3.12 syntax had complexity findings
        # on a 3.12 host and was unanalyzed on a 3.11 one. The metric binds the declared
        # 3.11 grammar, best-effort as Python's own feature_version is: a type
        # parameter list or a type statement is that file's named gap on any host.
        sources = {
            "tools/generic.py": "def f[T](x: T) -> T:\n    return x\n",
            "tools/alias.py": "type Number = int\n",
        }

        def measured(inventory: dict) -> list[tuple]:
            return sorted(
                (f["range"]["start_line"], f["range"]["end_line"], f["native"]["value"])
                for f in inventory["findings"]
                if f["tool"]["id"] == "complexity" and f["path"] == "tools/sample.py"
            )

        before = measured(self._inventory())
        shutil.rmtree(self.output, ignore_errors=True)
        self.commands.clear()
        for path, source in sources.items():
            (self.root / path).write_text(source, encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "newer syntax")
        inventory = self._inventory()
        unanalyzed = {
            u["path"]: u["reason"] for u in inventory["scope"]["full"]["unanalyzed"]
        }
        for path in sources:
            with self.subTest(path):
                self.assertIn(
                    "complexity could not parse: SyntaxError", unanalyzed[path]
                )
        # The later 3.11 file is analyzed, its counts and ranges unchanged.
        self.assertNotIn("tools/sample.py", unanalyzed)
        self.assertTrue(before)
        self.assertEqual(before, measured(inventory))
        # One declared target: mypy's and ruff's arguments are the same bytes.
        commands = [command for command, _cwd, _env in self.commands]
        mypy = [c for c in commands if "mypy" in c and "--version" not in c]
        ruff = [c for c in commands if "ruff" in c and "--version" not in c]
        self.assertTrue(mypy and ruff)
        for command in mypy:
            index = command.index("--python-version")
            self.assertEqual("3.11", command[index + 1])
        for command in ruff:
            index = command.index("--target-version")
            self.assertEqual("py311", command[index + 1])
        self.assertEqual(
            {"python": "3.11", "binding": "BEST_EFFORT"},
            inventory["configuration"]["complexity"]["grammar"],
        )

    def test_an_unrepresentable_timeout_refuses_the_inventory(self) -> None:
        # Codex on #436, by the Router's 6243027809: a finite timeout_seconds of 1e20
        # passes validation, and the subject's Git read raised OverflowError out of the
        # collector. Here it is reproduced for real; it is a classified refusal with a
        # fixed reason and no inventory.
        if not self._timeouts_overflow():
            self.skipTest("this platform's subprocess represents a 1e20 timeout")
        limits = self.module.DiagnosticLimits(timeout_seconds=1e20)
        with self.assertRaises(QualityEvidenceError) as raised:
            self._inventory(limits=limits)
        self.assertIn("cannot be represented", str(raised.exception))
        self.assertNotIn("PyTime", str(raised.exception))
        self.assertEqual([], list(self.output.rglob(self.module.DIAGNOSTIC_INVENTORY)))

    def test_an_overflowing_git_read_is_refused_at_each_seam(self) -> None:
        # The Router's 6243027809, portable injected controls: an OverflowError from
        # the metadata check, the frozen tree's listing, its stage, its identity or
        # the recheck after collection is the same classified refusal. It names no raw
        # text and no revision, and writes no inventory. It is no evidence that the
        # deadline passed or that the metadata is absent. No state reader runs on this
        # path (Router #389 6325382720, D1).
        owner = importlib.import_module("tools.exact_tree")
        seams = {
            "the metadata check": (
                self.module,
                "has_git_metadata",
                OverflowError("raw detail"),
            ),
            "the tracked set": (owner, "tree_paths", OverflowError("raw detail")),
            "the stage": (owner, "materialize", OverflowError("raw detail")),
            "the identity": (owner, "observed_tree", OverflowError("raw detail")),
            "the identity after the producers": (
                owner,
                "observed_tree",
                self._then(owner.observed_tree, OverflowError("raw detail")),
            ),
            "the recheck": (
                self.module,
                "has_git_metadata",
                [True, OverflowError("raw detail")],
            ),
        }
        for label, (target, name, effect) in seams.items():
            with self.subTest(label):
                shutil.rmtree(self.output, ignore_errors=True)
                with (
                    patch.object(target, name, side_effect=effect),
                    self.assertRaises(QualityEvidenceError) as raised,
                ):
                    self._inventory()
                message = str(raised.exception)
                self.assertIn("cannot be represented", message)
                self.assertIn("no inventory was written", message)
                self.assertNotIn("raw detail", message)
                self.assertNotIn(self.base, message)
                self.assertEqual(
                    [], list(self.output.rglob(self.module.DIAGNOSTIC_INVENTORY))
                )
                self.assertEqual([], list(self.output.glob("*/source")))
        with self.subTest("an ordinary timeout publishes"):
            shutil.rmtree(self.output, ignore_errors=True)
            inventory = self._inventory(
                limits=self.module.DiagnosticLimits(timeout_seconds=600)
            )
            self.assertEqual(self.base, inventory["source"]["revision"])
        with self.subTest("a spent budget starts no Git read to overflow"):
            identity = Mock(side_effect=OverflowError("raw detail"))
            with patch.object(self.module, "has_git_metadata", identity):
                commit, tree, _gaps = self.module._frozen_subject(
                    self.root, None, time.monotonic() - 1
                )
            self.assertEqual([], identity.call_args_list)
            self.assertEqual((None, None), (commit, tree))

    def test_records_after_a_malformed_mypy_line_stay_listed(self) -> None:
        # Codex on #436: a malformed line is a gap, and the records after it are
        # still read, never dropped.
        first = self._mypy(
            "tests/test_sample.py", self.lines["typing"], 11, "arg-type", "first"
        )
        later = self._mypy("tools/sample.py", 2, 1, "assignment", "later")
        self.mypy_text = json.dumps(first) + "\n{not json\n" + json.dumps(later) + "\n"
        inventory = self._inventory()
        messages = {
            f["message"] for f in inventory["findings"] if f["tool"]["id"] == "mypy"
        }
        self.assertLessEqual({"first", "later"}, messages)
        reasons = {
            u["path"]: u["reason"] for u in inventory["scope"]["full"]["unanalyzed"]
        }
        self.assertIn("unparsable mypy report", reasons["tools/sample.py"])

    def test_an_unbound_mypy_path_is_a_malformed_record(self) -> None:
        # Codex on #436, routed by the Router (6224373564, M2): an absolute file, or
        # one with a .. segment, cannot be bound to the group's root. It is the
        # report's malformed record before any prefix, and the later records stay.
        later = self._mypy("tools/sample.py", 2, 1, "assignment", "later")
        for kind, unbound in (
            ("absolute", "/elsewhere/checkout/tests/common.py"),
            ("parent", "../outside.py"),
            ("nested parent", "tools/../../outside.py"),
        ):
            with self.subTest(kind=kind):
                record = self._mypy(unbound, 1, 1, "arg-type", "unbound")
                self.mypy_text = json.dumps(record) + "\n" + json.dumps(later) + "\n"
                inventory = self._inventory()
                mypy = [f for f in inventory["findings"] if f["tool"]["id"] == "mypy"]
                self.assertEqual(["later"], [f["message"] for f in mypy])
                reasons = {
                    u["path"]: u["reason"]
                    for u in inventory["scope"]["full"]["unanalyzed"]
                }
                self.assertIn("unparsable mypy report", reasons["tools/sample.py"])
                (report,) = self.run_directory.glob("diagnostic-*-mypy-main.jsonl")
                self.assertEqual(self.mypy_text, report.read_text(encoding="utf-8"))

    def test_a_fixture_record_that_climbs_out_of_its_root_is_not_prefixed(self) -> None:
        # The Router's M2 (6224373564): a fixture prefix must never hide a parent
        # segment as a tracked-looking path.
        climbing = self._mypy(
            "tests/fixtures/one/../../../outside.py", 1, 1, "arg-type", "climbing"
        )
        self.mypy_records["tests/fixtures/one/baseline.py"] = [climbing]
        inventory = self._inventory()
        self.assertEqual(
            [], [f for f in inventory["findings"] if f["message"] == "climbing"]
        )
        reasons = {
            u["path"]: u["reason"] for u in inventory["scope"]["full"]["unanalyzed"]
        }
        self.assertIn(
            "unparsable mypy report", reasons["tests/fixtures/one/baseline.py"]
        )

    def test_a_mypy_severity_that_is_not_text_is_a_malformed_record(self) -> None:
        # Codex on #436, by the Router's S1 (6228685377): json.loads takes NaN and
        # Infinity, which the inventory wrote back as bare tokens. A severity is a
        # text or null; any other value makes the record the report's malformed one,
        # and the later records stay.
        later = self._mypy("tools/sample.py", 2, 1, "assignment", "later")
        for label, value in (
            ("NaN", "NaN"),
            ("Infinity", "Infinity"),
            ("-Infinity", "-Infinity"),
            ("an object", '{"level": "error"}'),
            ("an array", '["error"]'),
            ("a boolean", "true"),
            ("an integer", "1"),
            ("a float", "1.5"),
        ):
            with self.subTest(label):
                bad = self._mypy(
                    "tests/test_sample.py", self.lines["typing"], 11, "arg-type", "bad"
                )
                line = json.dumps(bad).replace(
                    '"severity": "error"', f'"severity": {value}'
                )
                self.assertIn(f'"severity": {value}', line)
                self.mypy_text = line + "\n" + json.dumps(later) + "\n"
                inventory = self._inventory()
                mypy = [f for f in inventory["findings"] if f["tool"]["id"] == "mypy"]
                self.assertEqual(["later"], [f["message"] for f in mypy])
                reasons = {
                    u["path"]: u["reason"]
                    for u in inventory["scope"]["full"]["unanalyzed"]
                }
                self.assertIn("unparsable mypy report", reasons["tools/sample.py"])
                (report,) = self.run_directory.glob("diagnostic-*-mypy-main.jsonl")
                self.assertEqual(self.mypy_text, report.read_text(encoding="utf-8"))
                written = self._written()
                for token in ("NaN", "Infinity"):
                    self.assertNotIn(token, written)

    def test_a_text_null_or_missing_mypy_severity_is_kept(self) -> None:
        # The Router's S1 keeps every value mypy writes, and an absent one.
        for label, value in (("a text", "note"), ("null", None), ("missing", ...)):
            with self.subTest(label):
                record = self._mypy("tools/sample.py", 2, 1, "assignment", "kept")
                if value is ...:
                    del record["severity"]
                else:
                    record["severity"] = value
                self.mypy_text = json.dumps(record) + "\n"
                inventory = self._inventory()
                (kept,) = [f for f in inventory["findings"] if f["message"] == "kept"]
                self.assertEqual(
                    None if value is ... else value, kept["native"]["severity"]
                )
                reasons = {
                    u["path"]: u["reason"]
                    for u in inventory["scope"]["full"]["unanalyzed"]
                }
                self.assertNotIn(
                    "unparsable mypy report", reasons.get("tools/sample.py", "")
                )

    def test_a_written_gap_names_the_exception_type_never_its_text(self) -> None:
        # Octopus on #436, by the Router's X1 (6228685377): an exception's text can
        # carry the root, a file name, or Git's argv with safe.directory, and these
        # gaps are written into the inventory. Each keeps its fixed text and the
        # exception's type, as the metric's gap does.
        root = str(self.root.resolve())
        sentinel = f"{root}/safe.directory=sentinel"
        outside = f"/elsewhere/{sentinel.rsplit('/', 1)[1]}/outside.py"
        cases = {
            "an unreadable mypy report": (
                "diagnostic-*-mypy-main.jsonl",
                "tools/sample.py",
                "unreadable mypy report: PermissionError",
            ),
            "an unreadable ruff report": (
                "diagnostic-ruff-every-rule.json",
                "tests/test_sample.py",
                "ruff:every-rule unparsable report: PermissionError",
            ),
        }
        for label, (pattern, path, expected) in cases.items():
            with self.subTest(label):
                denied = PermissionError(13, "Permission denied", sentinel)
                with self._report_read_raises(pattern, denied):
                    inventory = self._inventory()
                reasons = {
                    u["path"]: u["reason"]
                    for u in inventory["scope"]["full"]["unanalyzed"]
                }
                self.assertIn(expected, reasons[path])
                self.assertNotIn(root, self._written())
        with self.subTest("a mypy record that names a file outside its root"):
            record = self._mypy(outside, 1, 1, "arg-type", "outside")
            later = self._mypy("tools/sample.py", 2, 1, "assignment", "later")
            self.mypy_text = json.dumps(record) + "\n" + json.dumps(later) + "\n"
            inventory = self._inventory()
            reasons = {
                u["path"]: u["reason"] for u in inventory["scope"]["full"]["unanalyzed"]
            }
            self.assertIn(
                "unparsable mypy report: ValueError", reasons["tools/sample.py"]
            )
            self.assertNotIn("/elsewhere/", self._written())
        self.mypy_text = None
        record = self._ruff("tests/test_sample.py", 1, 1, "F401", "outside")
        record["filename"] = outside
        self.ruff_records.insert(0, record)
        with self.subTest("a ruff record that names a file outside the root"):
            inventory = self._inventory()
            reasons = {
                u["path"]: u["reason"] for u in inventory["scope"]["full"]["unanalyzed"]
            }
            self.assertIn(
                "ruff:every-rule unparsable report: ValueError",
                reasons["tests/test_sample.py"],
            )
            written = self._written()
            self.assertNotIn("/elsewhere/", written)
            self.assertNotIn(root, written)
        self.ruff_records.remove(record)
        with self.subTest("a base Git cannot read"):
            inventory = self._inventory(base="c" * 40)
            self.assertIn(
                f"cannot compare with base {'c' * 40}: CalledProcessError",
                inventory["coverage"]["reason"],
            )
            written = self._written()
            self.assertNotIn("safe.directory", written)
            self.assertNotIn(root, written)

    def test_an_exit_0_with_findings_is_contradictory_evidence(self) -> None:
        # Codex on #436, by the Router's Z1 (6229410333): ruff without --exit-zero
        # exits 0 only with no diagnostic, and mypy only with no error. Each producer
        # exiting 0 with one is the run's gap; every finding stays listed, and the raw
        # report is kept as it was.
        with self.subTest("ruff, a valid finding"):
            self.ruff_exit = 0
            inventory = self._inventory()
            self.assertEqual(
                3, len([f for f in inventory["findings"] if f["tool"]["id"] == "ruff"])
            )
            self.assertIn(
                "ruff:every-rule exited 0 with a finding record",
                self._reasons(inventory).get("tests/test_sample.py", ""),
            )
            self.assertEqual("INCOMPLETE", inventory["coverage"]["status"])
            report = self.run_directory / "diagnostic-ruff-every-rule.json"
            self.assertEqual(
                json.dumps(self.ruff_records).replace(
                    str(self.root.resolve()), str(self.run_directory / "source")
                ),
                report.read_text("utf-8"),
            )
        self.ruff_exit = 1
        with self.subTest("mypy, a coded error"):
            self.mypy_exit["."] = 0
            inventory = self._inventory()
            self.assertEqual(
                2, len([f for f in inventory["findings"] if f["tool"]["id"] == "mypy"])
            )
            self.assertIn(
                "mypy:main exited 0 with an error record",
                self._reasons(inventory).get("tests/test_sample.py", ""),
            )
            self.assertEqual("INCOMPLETE", inventory["coverage"]["status"])
        del self.mypy_exit["."]

    def test_an_exit_0_without_a_contradiction_names_no_gap(self) -> None:
        # The Router's Z1 keeps every consistent run, and every stronger reason.
        with self.subTest("ruff, an empty report"):
            self.ruff_exit, self.ruff_records = 0, []
            reasons = self._reasons(self._inventory())
            self.assertNotIn("ruff", reasons.get("tests/test_sample.py", ""))
        with self.subTest("mypy, notes only"):
            self.mypy_exit["."] = 0
            note = self._mypy("tools/sample.py", 2, 1, None, "a note", "note")
            self.mypy_records = {"tools/sample.py": [note]}
            inventory = self._inventory()
            self.assertIn("a note", [f["message"] for f in inventory["findings"]])
            self.assertNotIn(
                "mypy", self._reasons(inventory).get("tools/sample.py", "")
            )
        with self.subTest("mypy, an aborting code-less error wins"):
            aborting = self._mypy("tools/sample.py", 2, 1, None, "cannot continue")
            self.mypy_records = {"tools/sample.py": [aborting]}
            reasons = self._reasons(self._inventory())
            self.assertIn(
                "mypy:main aborted: cannot continue", reasons["tools/sample.py"]
            )
            self.assertNotIn("exited 0", reasons["tools/sample.py"])
        with self.subTest("mypy, a malformed record wins"):
            later = self._mypy("tools/sample.py", 2, 1, "assignment", "later")
            self.mypy_text = "{not json\n" + json.dumps(later) + "\n"
            inventory = self._inventory()
            self.assertIn("later", [f["message"] for f in inventory["findings"]])
            reasons = self._reasons(inventory)
            self.assertIn("unparsable mypy report", reasons["tools/sample.py"])
            self.assertNotIn("exited 0", reasons["tools/sample.py"])
        self.mypy_text = None
        with self.subTest("ruff, a malformed record wins"):
            self.ruff_exit = 0
            valid = self._ruff("tests/test_sample.py", 1, 1, "F401", "valid")
            self.ruff_records = [{"code": "F401"}, valid]
            inventory = self._inventory()
            self.assertEqual(
                1, len([f for f in inventory["findings"] if f["tool"]["id"] == "ruff"])
            )
            reasons = self._reasons(inventory)
            self.assertIn(
                "ruff:every-rule unparsable report", reasons["tests/test_sample.py"]
            )
            self.assertNotIn("exited 0", reasons["tests/test_sample.py"])

    def test_local_work_past_the_deadline_is_reported(self) -> None:
        # Codex on #436: the deadline is checked after the inventory's own work, not
        # only before it.
        clock = [1000.0]
        dedupe = self.module.deduplicate_findings

        def slow(findings):
            clock[0] += 10_000.0
            return dedupe(findings)

        with (
            patch(
                "tools.quality_evidence.time.monotonic", side_effect=lambda: clock[0]
            ),
            patch("tools.quality_evidence.deduplicate_findings", side_effect=slow),
        ):
            inventory = self._inventory()
        self.assertIn(
            "the inventory ran past its deadline", inventory["coverage"]["reason"]
        )

    def test_an_infinite_location_is_a_gap_not_an_abort(self) -> None:
        # cubic on #436: json.loads accepts Infinity, and int() of it raises
        # OverflowError, which would abort the whole collection.
        valid = self._mypy("tools/sample.py", 2, 1, "assignment", "valid")
        self.mypy_text = (
            '{"file": "tests/test_sample.py", "line": Infinity, "column": 1, '
            '"message": "m", "code": "x", "severity": "error"}\n'
            + json.dumps(valid)
            + "\n"
        )
        # A record with an infinite start, one with an infinite end, then a valid one,
        # which stays listed (Codex on #436: one malformed record dropped the rest).
        start = self._ruff("tests/test_sample.py", 1, 1, "S106", "start")
        start["location"]["row"] = float("inf")
        end = self._ruff("tests/test_sample.py", 2, 1, "S106", "end")
        end["end_location"]["row"] = float("inf")
        good = self._ruff("tests/test_sample.py", 3, 1, "S106", "good")
        self.ruff_text = json.dumps([start, end, good])
        inventory = self._inventory()
        self.assertEqual(
            {"good"},
            {f["message"] for f in inventory["findings"] if f["tool"]["id"] == "ruff"},
        )
        reasons = {
            u["path"]: u["reason"] for u in inventory["scope"]["full"]["unanalyzed"]
        }
        self.assertIn("unparsable mypy report", reasons["tools/sample.py"])
        self.assertIn("ruff:every-rule unparsable report", reasons["tools/sample.py"])
        self.assertIn(
            "valid",
            {f["message"] for f in inventory["findings"] if f["tool"]["id"] == "mypy"},
        )

    def test_a_user_site_never_runs_in_a_producer(self) -> None:
        # Codex on #436: -P leaves the user site on, so a usercustomize.py under the
        # caller's user base ran inside every producer (IMPLEMENTER_RCA, probe 3).
        base = Path(self.directory.name) / "userbase"
        marker = Path(self.directory.name) / "usercustomize-ran"
        with patch.dict(os.environ, {"PYTHONUSERBASE": str(base)}):
            # The caller's own PYTHONNOUSERSITE is not the producer's isolation.
            os.environ.pop("PYTHONNOUSERSITE", None)
            site = subprocess.run(  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit  # nosec B603 -- test-only: this interpreter, a literal argv
                [
                    sys.executable,
                    "-c",
                    "import site; print(site.getusersitepackages())",
                ],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            Path(site).mkdir(parents=True)
            (Path(site) / "usercustomize.py").write_text(
                f"open({str(marker)!r}, 'w').close()\n", encoding="utf-8"
            )
            subprocess.run(  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit  # nosec B603 -- test-only: this interpreter, a literal argv
                [sys.executable, "-c", "pass"], check=True
            )
            if not marker.exists():
                self.skipTest("this interpreter keeps the user site off")
            marker.unlink()
            run = Path(self.directory.name) / "run"
            run.mkdir()
            self.module._producer_version(
                self.root,
                run,
                "gnostoa_no_such_producer",
                self.module.DEFAULT_DIAGNOSTIC_LIMITS,
                time.monotonic() + 60,
            )
        self.assertFalse(marker.exists(), "a user-site module ran inside a producer")

    def test_a_record_of_the_wrong_type_is_a_gap_not_a_coerced_finding(self) -> None:
        # cubic and Claude on #436: int() made a line of 2.5 into 2 and a column of
        # true into 1, and str() made a numeric field into text. Each such record is
        # its report's gap, and the valid records after it stay listed.
        valid = self._mypy("tools/sample.py", 2, 1, "assignment", "valid mypy")
        malformed = [
            {
                **self._mypy("tests/test_sample.py", 2, 1, "x", "fractional line"),
                "line": 2.5,
            },
            {
                **self._mypy("tests/test_sample.py", 2, 1, "x", "boolean column"),
                "column": True,
            },
            {
                **self._mypy("tests/test_sample.py", 2, 1, "x", "numeric file"),
                "file": 7,
            },
            {**self._mypy("tests/test_sample.py", 2, 1, "x", "unused"), "message": 7},
        ]
        self.mypy_text = "".join(json.dumps(r) + "\n" for r in (*malformed, valid))
        fractional = self._ruff("tests/test_sample.py", 1, 1, "S106", "fractional end")
        fractional["end_location"]["row"] = 1.5
        boolean = self._ruff("tests/test_sample.py", 2, 1, "S106", "boolean start")
        boolean["location"]["column"] = True
        numeric = self._ruff("tests/test_sample.py", 3, 1, "S106", "numeric code")
        numeric["code"] = 106
        good = self._ruff("tests/test_sample.py", 4, 1, "S106", "good ruff")
        self.ruff_text = json.dumps([fractional, boolean, numeric, good])
        inventory = self._inventory()
        listed = {(f["tool"]["id"], f["message"]) for f in inventory["findings"]}
        self.assertIn(("mypy", "valid mypy"), listed)
        self.assertIn(("ruff", "good ruff"), listed)
        for coerced in (
            ("mypy", "fractional line"),
            ("mypy", "boolean column"),
            ("mypy", "numeric file"),
            ("mypy", "7"),
            ("ruff", "fractional end"),
            ("ruff", "boolean start"),
            ("ruff", "numeric code"),
        ):
            self.assertNotIn(coerced, listed)
        reasons = {
            u["path"]: u["reason"] for u in inventory["scope"]["full"]["unanalyzed"]
        }
        self.assertIn("unparsable mypy report", reasons["tools/sample.py"])
        self.assertIn("ruff:every-rule unparsable report", reasons["tools/sample.py"])

    def test_a_malformed_position_the_clamp_would_erase_is_a_gap(self) -> None:
        # Round 12's mutants on #436: the clamps make a column of -0.5 into 1, drop the
        # range of a line of 0.5 and the end of a row before its start, and the 1-based
        # shift makes an end column of true into 2. Each is a gap, checked before them.
        valid = self._mypy("tools/sample.py", 2, 1, "assignment", "valid mypy")
        malformed = [
            {
                **self._mypy("tests/test_sample.py", 2, 1, "x", "negative fraction"),
                "column": -0.5,
            },
            {
                **self._mypy("tests/test_sample.py", 2, 1, "x", "line below one"),
                "line": 0.5,
            },
            {
                **self._mypy("tests/test_sample.py", 2, 1, "x", "boolean end"),
                "end_column": True,
            },
        ]
        self.mypy_text = "".join(json.dumps(r) + "\n" for r in (*malformed, valid))
        early = self._ruff("tests/test_sample.py", 2, 1, "S106", "end before start")
        early["end_location"]["row"] = 0.5
        good = self._ruff("tests/test_sample.py", 4, 1, "S106", "good ruff")
        self.ruff_text = json.dumps([early, good])
        listed = {f["message"] for f in self._inventory()["findings"]}
        self.assertLessEqual({"valid mypy", "good ruff"}, listed)
        self.assertEqual(
            set(),
            {"negative fraction", "line below one", "boolean end", "end before start"}
            & listed,
        )

    def test_a_ruff_record_without_a_code_is_listed_without_one(self) -> None:
        # Claude on #436: str() made a null code into the rule "None". Ruff 0.16.0 names
        # its syntax errors invalid-syntax, but a producer's null stays a null.
        record = self._ruff("tests/test_sample.py", 1, 1, "S106", "no code")
        record["code"] = None
        self.ruff_text = json.dumps([record])
        found = [f for f in self._inventory()["findings"] if f["message"] == "no code"]
        self.assertEqual(1, len(found))
        # The range owner's shape: a null rule is no key at all.
        self.assertIsNone(found[0].get("rule"))
        self.assertIsNone(found[0]["native"]["producer_code"])
        self.assertEqual("UNMAPPED", found[0]["native"]["mapping"])

    def test_no_producer_starts_once_the_findings_exceed_the_limit(self) -> None:
        # cubic on #436: every later group and producer still ran before the existing
        # refusal. Its predicate, the raw count above max_findings, now stops them.
        complexity = patch.object(
            self.module, "_run_complexity", wraps=self.module._run_complexity
        )
        limits = self.module.DiagnosticLimits(max_findings=1)
        with (
            complexity as metric,
            self.assertRaisesRegex(
                QualityEvidenceError, "2 findings exceed max_findings 1; no inventory"
            ),
        ):
            self._inventory(limits=limits)
        observation = self.module._environment_command()
        started = [
            c for c, _, _ in self.commands if "--version" not in c and c != observation
        ]
        self.assertEqual(
            [("mypy", ".")],
            [(c[3], self._group(cwd)) for c, cwd, _ in self.commands if c in started],
        )
        metric.assert_not_called()
        # Only the observation before the producers: none follows a refusal (#389 F3
        # S2-C).
        self.assertEqual(1, [c for c, _, _ in self.commands].count(observation))

    def test_an_inventory_at_exactly_the_findings_limit_is_written(self) -> None:
        # The other side of the same predicate: equality is within the limit.
        count = len(self._inventory()["findings"])
        inventory = self._inventory(
            limits=self.module.DiagnosticLimits(max_findings=count)
        )
        self.assertEqual(count, len(inventory["findings"]))

    def test_reaching_the_findings_limit_exactly_stops_no_producer(self) -> None:
        # The predicate is the raw count above the limit, never at it (Router on #436):
        # at the limit, every later group and producer still starts.
        limits = self.module.DiagnosticLimits(max_findings=2)
        with self.assertRaisesRegex(QualityEvidenceError, "exceed max_findings 2"):
            self._inventory(limits=limits)
        started = [
            (c[3], self._group(cwd))
            for c, cwd, _ in self.commands
            if "--version" not in c
        ]
        self.assertIn(("mypy", "tests/fixtures/one"), started)
        self.assertIn(("ruff", "."), started)
        complexity = patch.object(
            self.module, "_run_complexity", wraps=self.module._run_complexity
        )
        limits = self.module.DiagnosticLimits(max_findings=5)
        with (
            complexity as metric,
            self.assertRaisesRegex(QualityEvidenceError, "exceed max_findings 5"),
        ):
            self._inventory(limits=limits)
        metric.assert_called_once()

    def test_an_unavailable_git_is_a_comparison_gap(self) -> None:
        # The consumed owner refuses with its own PrepareError; the comparison keeps
        # the existing "git is unavailable" gap, never an aborted collection.
        candidate_prepare = importlib.import_module("tools.candidate_prepare")
        with patch.object(candidate_prepare, "_GIT", None):
            inventory = self._inventory(base=self.base)
        self.assertIn("git is unavailable", inventory["coverage"]["reason"])

    def test_a_callers_git_override_is_refused_before_any_work(self) -> None:
        # Codex and Claude, then cubic and CodeAnt on #436, routed by the Router
        # (6220963008, then 6223042901, R1): every variable that preparation's own
        # scrub removes, even empty, could rebind the subject, the scope or the
        # comparison. Each class, named here independently of the owner: routing,
        # object directories, discovery, configuration, and the config families
        # with and without GIT_CONFIG_COUNT.
        overrides = (
            "GIT_DIR",
            "GIT_WORK_TREE",
            "GIT_COMMON_DIR",
            "GIT_INDEX_FILE",
            "GIT_OBJECT_DIRECTORY",
            "GIT_ALTERNATE_OBJECT_DIRECTORIES",
            "GIT_CEILING_DIRECTORIES",
            "GIT_DISCOVERY_ACROSS_FILESYSTEM",
            "GIT_CONFIG",
            "GIT_CONFIG_PARAMETERS",
            "GIT_CONFIG_GLOBAL",
            "GIT_CONFIG_SYSTEM",
            "GIT_CONFIG_NOSYSTEM",
            "GIT_ATTR_NOSYSTEM",
            "GIT_EXTERNAL_DIFF",
            "GIT_TEMPLATE_DIR",
            "GIT_CONFIG_COUNT",
            "GIT_CONFIG_KEY_0",
            "GIT_CONFIG_VALUE_0",
            "GIT_CONFIG_KEY_12",
        )
        owner = importlib.import_module("tools.candidate_prepare")
        self.assertLessEqual(set(owner._GIT_ENVIRONMENT_VARIABLES), set(overrides))
        for key in overrides:
            for value in ("/elsewhere-value-marker", ""):
                with self.subTest(key=key, value=value):
                    refusal = self._refused({key: value})
                    self.assertIn(key, str(refusal))
                    if value:
                        self.assertNotIn(value, str(refusal), "a value was reported")

    def test_the_refusal_is_the_owners_rule(self) -> None:
        # The Router's R1 (6223042901): the refusal consumes candidate_prepare's
        # unchanged scrub as data, and keeps no list of its own.
        self.assertFalse(hasattr(self.module, "_CALLER_GIT_ROUTING"))
        owner = importlib.import_module("tools.candidate_prepare")
        scrub = owner._git_env_without_caller_overrides

        def stricter() -> dict[str, str]:
            kept = scrub()
            kept.pop("GNOSTOA_PROBE_OVERRIDE", None)
            return kept

        with patch.object(
            owner, "_git_env_without_caller_overrides", side_effect=stricter
        ) as consumed:
            refusal = self._refused({"GNOSTOA_PROBE_OVERRIDE": "1"})
        consumed.assert_called()
        self.assertIn("GNOSTOA_PROBE_OVERRIDE", str(refusal))

    def test_an_owner_that_cannot_be_imported_is_refused(self) -> None:
        # Claude on #436, with the Router's agreement (6224373564): the owner's
        # import sits inside the classified boundary, so a failed import is the
        # same refusal, never a raw ImportError.
        with patch.dict(sys.modules, {"tools.candidate_prepare": None}):
            refusal = self._refused({})
        self.assertIn("could not be checked", str(refusal))

    def test_an_owner_failure_is_refused_with_no_fallback(self) -> None:
        # The Router's R1 (6223042901): a failure to obtain the owner's result never
        # falls back to a local list or to a collection.
        owner = importlib.import_module("tools.candidate_prepare")
        with patch.object(
            owner,
            "_git_env_without_caller_overrides",
            side_effect=RuntimeError("owner unavailable"),
        ):
            refusal = self._refused({})
        self.assertIn("could not be checked", str(refusal))

    # The refusal tests' spies watch real work: an admitted collection runs every
    # piece of work they watch, and neither of D1's negatives (Amazon Q on #451).
    def test_the_refusal_spies_watch_the_work_a_collection_does(self) -> None:
        with self._watched_work() as watched:
            self.collect(self.root, self.output, base=self.base)
        for work in ("producer", "subject", "scope", "stage", "git_reads"):
            self.assertTrue(watched[work].called, f"no {work} work was watched")
        watched["v1_scope"].assert_not_called()
        watched["v1_subject"].assert_not_called()

    # An owner that no longer defines the no-fetch policy leaves the comparison
    # unavailable, never a crash: importing a missing name raises ImportError, which
    # the policy's own handler names (Amazon Q on #451).
    def test_a_missing_owner_policy_is_an_unavailable_comparison(self) -> None:
        owner = importlib.import_module("tools.exact_tree")
        with patch.dict(owner.__dict__):
            del owner.__dict__["_GIT_ENV"]
            with self.assertRaises(self.module._ComparisonUnavailable):
                self.module._no_fetch_policy()
        self.assertEqual(
            {"GIT_ALLOW_PROTOCOL": "", "GIT_NO_LAZY_FETCH": "1"},
            self.module._no_fetch_policy(),
        )

    def test_a_base_that_is_not_that_commit_is_a_comparison_gap(self) -> None:
        # Codex on #436, routed by the Router (6224373564, B1): exact_sha checks only
        # the form, and git diff takes any tree-ish, so a tree, a blob or a tag
        # published a comparison labelled as its commit base.
        self._git("tag", "-a", "-m", "a tag", "base-tag", self.base)
        bases = {
            "tree": self._git("rev-parse", f"{self.base}^{{tree}}"),
            "blob": self._git("rev-parse", f"{self.base}:tools/sample.py"),
            "tag peeling to another id": self._git("rev-parse", "base-tag"),
            "missing object": "f" * 40,
        }
        self._changed_once()
        for kind, base in bases.items():
            with self.subTest(kind=kind):
                self._uncompared(base)

    def test_a_failed_or_unusable_commit_check_is_a_comparison_gap(self) -> None:
        # The Router's B1 (6224373564): a read failure, an answer that is not exactly
        # the base, and a spent shared budget each take the comparison's gap.
        real = self.module._diagnostic_git

        def failing(root, deadline, *arguments, **options):
            if arguments[0] == "rev-parse":
                raise OSError("read failed")
            return real(root, deadline, *arguments, **options)

        def unusable(root, deadline, *arguments, **options):
            if arguments[0] == "rev-parse":
                return "not a commit id\n"
            return real(root, deadline, *arguments, **options)

        def doubled(root, deadline, *arguments, **options):
            if arguments[0] == "rev-parse":
                answer = real(root, deadline, *arguments, **options)
                return answer + answer
            return real(root, deadline, *arguments, **options)

        def spent(root, deadline, *arguments, **options):
            if arguments[0] == "rev-parse":
                return real(root, time.monotonic() - 1, *arguments, **options)
            return real(root, deadline, *arguments, **options)

        self._changed_once()
        for kind, reader in (
            ("read failure", failing),
            ("unusable answer", unusable),
            ("two answers", doubled),
            ("spent budget", spent),
        ):
            with self.subTest(kind=kind):
                self._uncompared(self.base, reader)

    def test_a_replaced_base_is_compared_by_its_own_objects(self) -> None:
        # Codex on #436, routed by the Router (6227604656, N1): with refs/replace/<base>,
        # Git read the replacement, so a base whose replacement has HEAD's tree showed
        # no changed path while diff.base still named the requested commit.
        self._changed_once()
        fake = self._git(
            "commit-tree", self._git("rev-parse", "HEAD^{tree}"), "-m", "fake"
        )
        for label, replaced in (("no replacement", False), ("a replaced base", True)):
            with self.subTest(label):
                if replaced:
                    self._git("replace", self.base, fake)
                inventory = self._inventory(base=self.base)
                diff = inventory["scope"]["diff"]
                self.assertEqual(self.base, diff["base"])
                self.assertIn("tools/sample.py", diff["changed_paths"])
                self.assertNotIn(
                    None, {f["native"]["in_diff"] for f in inventory["findings"]}
                )

    def test_every_comparison_read_ignores_replacement_objects(self) -> None:
        # The Router's N1 (6227604656): the fixed option reaches B1's commit check, the
        # name list and every patch, through the one comparison reader.
        self._changed_once()
        git = importlib.import_module("tools.candidate_prepare")._git_executable()
        # Git is spawned through Popen and drained by the shared owner (the Router's G1).
        with patch.object(
            self.module.subprocess, "Popen", wraps=self.module.subprocess.Popen
        ) as spawned:
            self._inventory(base=self.base)
        # The diagnostic reader's children name the subject's safe.directory; the
        # exact-tree owner's run under its own fixed environment (#389 F3 S2 B).
        bound = f"safe.directory={self.root.resolve()}"
        comparison = [
            call.args[0]
            for call in spawned.call_args_list
            if call.args[0][0] == git and bound in call.args[0]
        ]
        verbs = [argv[argv.index("-c") + 2] for argv in comparison]
        self.assertIn("rev-parse", verbs)
        self.assertEqual(2, verbs.count("diff"), verbs)
        for argv in comparison:
            self.assertEqual("--no-replace-objects", argv[1], argv)

    def test_a_base_commit_is_checked_by_the_existing_reader(self) -> None:
        # The Router's B1 (6224373564): the check is the existing reader's, with the
        # exact argv, and a commit base still compares.
        self._changed_once()
        with patch.object(
            self.module, "_diagnostic_git", wraps=self.module._diagnostic_git
        ) as git:
            inventory = self._inventory(base=self.base)
        self.assertIn(
            ("rev-parse", "--verify", "--end-of-options", f"{self.base}^{{commit}}"),
            [call.args[2:] for call in git.call_args_list],
        )
        self.assertEqual(self.base, inventory["scope"]["diff"]["base"])
        self.assertNotIn(None, {f["native"]["in_diff"] for f in inventory["findings"]})

    def test_a_changed_file_without_textual_hunks_is_a_comparison_gap(self) -> None:
        # The PAO (6220635618) and CodeAnt on #436, routed by the Router (6220963008):
        # a changed file that Git treats as binary has no hunk, and was reported as
        # in_diff false. It is a named comparison gap, and every finding stays listed.
        (self.root / ".gitattributes").write_text(
            "tests/test_sample.py -diff\n", encoding="utf-8"
        )
        sample = self.root / "tests" / "test_sample.py"
        sample.write_text(
            sample.read_text(encoding="utf-8") + "\n# changed\n", encoding="utf-8"
        )
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "a binary change")
        inventory = self._inventory(base=self.base)
        found = [
            f for f in inventory["findings"] if f["path"] == "tests/test_sample.py"
        ]
        self.assertTrue(found)
        self.assertEqual({None}, {f["native"]["in_diff"] for f in found})
        self.assertIn("cannot compare with base", inventory["coverage"]["reason"])
        self.assertIn("no textual hunk", inventory["coverage"]["reason"])

    def test_the_comparisons_own_reasons_stay_named(self) -> None:
        # The Router's Y2 (6228830094): the comparison's own reasons, fixed in this
        # module, are written as they are. X1's type alone would erase them.
        self._changed_once()
        with self.subTest("the base is not that commit"):
            self._git("tag", "-a", "-m", "a tag", "base-tag", self.base)
            tag = self._git("rev-parse", "base-tag")
            inventory = self._uncompared(tag)
            self.assertIn(
                f"cannot compare with base {tag}: the base is not that commit",
                inventory["coverage"]["reason"],
            )
        with self.subTest("not a sequence of hunks"):
            with patch("tools.merge_evidence_github._added_lines", return_value=None):
                inventory = self._inventory(base=self.base)
            self.assertIn(
                f"cannot compare with base {self.base}: the comparison of "
                "tools/sample.py is not a sequence of hunks",
                inventory["coverage"]["reason"],
            )

    def test_an_external_comparison_failure_is_written_by_its_type(self) -> None:
        # The Router's Y2 keeps X1 for every other failure: an OSError, a ValueError,
        # or Git's CalledProcessError or TimeoutExpired is written by its type alone,
        # so that no host path, argv or stderr reaches the inventory.
        root = str(self.root.resolve())
        argv = ["/usr/bin/git", "-c", f"safe.directory={root}", "rev-parse"]
        failures = (
            PermissionError(13, "Permission denied", f"{root}/.git/objects"),
            ValueError(f"an unusable answer from {root}"),
            subprocess.CalledProcessError(128, argv, stderr=f"fatal: {root}".encode()),
            subprocess.TimeoutExpired(argv, 5),
        )
        for failure in failures:
            with self.subTest(type(failure).__name__):
                inventory = self._uncompared(
                    self.base, reader=Mock(side_effect=failure)
                )
                self.assertIn(
                    f"cannot compare with base {self.base}: {type(failure).__name__}",
                    inventory["coverage"]["reason"],
                )
                written = self._written()
                self.assertNotIn(root, written)
                self.assertNotIn("safe.directory", written)

    def test_in_diff_tests_the_changed_lines_never_the_range(self) -> None:
        # Codex on #436, by the Router's W1 (6229993455): a range's end comes from a
        # producer record, so walking every line of it was unbounded. The changed lines
        # are tested against its endpoints instead, with the same answer.
        def bounded_range(*args):
            walked = range(*args)
            if len(walked) > 10_000:
                raise AssertionError(f"walked a range of {len(walked)} lines")
            return walked

        huge = 10**12
        cases = (
            (
                "a huge end, a sparse hit",
                {"start_line": 1, "end_line": huge},
                {5},
                True,
            ),
            (
                "a huge end, no change",
                {"start_line": 1, "end_line": huge},
                set(),
                False,
            ),
            (
                "a huge end, changes before it",
                {"start_line": 9, "end_line": huge},
                {3},
                False,
            ),
            ("the inclusive start", {"start_line": 4, "end_line": 9}, {4}, True),
            ("the inclusive end", {"start_line": 4, "end_line": 9}, {9}, True),
            ("an interior line", {"start_line": 4, "end_line": 9}, {6}, True),
            ("no overlap", {"start_line": 4, "end_line": 9}, {3, 10}, False),
            ("no end, its start", {"start_line": 4}, {4}, True),
            ("no end, another line", {"start_line": 4}, {5}, False),
            ("no start", {"end_line": 9}, {4}, False),
            ("no range", None, {4}, False),
        )
        with patch.object(self.module, "range", side_effect=bounded_range, create=True):
            for label, location, lines, expected in cases:
                with self.subTest(label):
                    finding = {"path": "tools/sample.py"}
                    if location is not None:
                        finding["range"] = location
                    changed = {"tools/sample.py": sorted(lines)}
                    self.assertIs(expected, self.module._in_diff(finding, changed))

    def test_each_paths_changed_lines_are_ordered_once_for_every_finding(self) -> None:
        # cubic on #436, by the Router's I1 (6231894979): each finding scanned the whole
        # changed-line set. The set is ordered once per path, and each finding is one
        # bisect, with the same answer.
        passes = [0]

        class Counted(set):
            def __iter__(self):
                passes[0] += 1
                return super().__iter__()

        lines = Counted(range(10, 2010, 2))
        findings = [
            {
                "path": "tools/sample.py",
                "range": {"start_line": n, "end_line": n},
                "native": {},
            }
            for n in range(1, 401)
        ]
        diff = {"base": self.base, "changed_paths": ["tools/sample.py"]}
        with patch.object(
            self.module, "_diff_scope", return_value=(diff, {"tools/sample.py": lines})
        ):
            self.module._annotate_diff(
                self.root,
                self.base,
                findings,
                [],
                time.monotonic() + 30,
                head=self._head(),
            )
        self.assertEqual(1, passes[0])
        # A set that iterates out of order, {8, 1} here, is still bisected in order.
        unordered = [
            {
                "path": "tools/other.py",
                "range": {"start_line": 1, "end_line": 1},
                "native": {},
            }
        ]
        with patch.object(
            self.module, "_diff_scope", return_value=(diff, {"tools/other.py": {8, 1}})
        ):
            self.module._annotate_diff(
                self.root,
                self.base,
                unordered,
                [],
                time.monotonic() + 30,
                head=self._head(),
            )
        self.assertIs(True, unordered[0]["native"]["in_diff"])
        self.assertEqual(
            [n % 2 == 0 and 10 <= n < 2010 for n in range(1, 401)],
            [f["native"]["in_diff"] for f in findings],
        )

    def test_a_deletion_only_change_is_a_known_empty_set(self) -> None:
        # The other side of the same gap (Router 6220963008): textual hunks that only
        # delete lines prove no line was added, so in_diff is false and no gap is named.
        sample = self.root / "tools" / "sample.py"
        sample.write_text(
            sample.read_text(encoding="utf-8") + "# removable\n", encoding="utf-8"
        )
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "a removable line")
        base = self._git("rev-parse", "HEAD")
        sample.write_text(
            sample.read_text(encoding="utf-8").replace("# removable\n", ""),
            encoding="utf-8",
        )
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "removed")
        inventory = self._inventory(base=base)
        found = [f for f in inventory["findings"] if f["path"] == "tools/sample.py"]
        self.assertTrue(found)
        self.assertEqual({False}, {f["native"]["in_diff"] for f in found})
        self.assertNotIn("cannot compare", inventory["coverage"]["reason"])

    def test_a_callers_git_dir_never_reroutes_the_comparison(self) -> None:
        # Measured on #436 (IMPLEMENTER_RCA, probe 2): the inventory's own Git
        # inherited a caller's GIT_DIR, as a Git hook sets it, and compared another
        # repository with the base.
        other = Path(self.directory.name) / "other"
        subprocess.run(  # nosec B603 B607 -- test-only: a literal git argv on temporary fixtures
            ["git", "clone", "-q", str(self.root), str(other)], check=True
        )
        (other / "tools" / "other_only.py").write_text("OTHER = 1\n", encoding="utf-8")
        for args in (["add", "-A"], ["commit", "-q", "-m", "other"]):
            subprocess.run(  # nosec B603 B607 -- test-only: a literal git argv on temporary fixtures
                [
                    "git",
                    "-c",
                    "user.email=t@example.invalid",
                    "-c",
                    "user.name=t",
                    *args,
                ],
                cwd=other,
                check=True,
            )
        (self.root / "tools" / "sample.py").write_text(
            _DIAGNOSTIC_SAMPLE + "\nCHANGED = 1\n", encoding="utf-8"
        )
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "subject")
        head = self._head()
        with patch.dict(os.environ, {"GIT_DIR": str(other / ".git")}):
            scope, _ = self.module._diff_scope(
                self.root, self.base, time.monotonic() + 60, head=head
            )
        self.assertEqual(["tools/sample.py"], scope["changed_paths"])

    def test_the_default_collection_never_runs_the_diagnostic_producers(self) -> None:
        source = (ROOT / "tools" / "quality_evidence.py").read_text(encoding="utf-8")
        default = source.split("def collect_quality_evidence(", 1)[1].split(
            "\ndef ", 1
        )[0]
        self.assertNotIn("collect_diagnostic_inventory", default)
        self.assertNotIn("diagnostic", self.module.build_parser().format_help().lower())


class DiagnosticInventoryEndToEndTests(_DiagnosticFixture):
    """The real runner: its producers may be absent in CI's runtime image, so these
    assert only what holds either way, and the complexity metric's findings."""

    def test_a_repository_module_cannot_shadow_a_producer(self) -> None:
        sentinel = Path(self.directory.name) / "hijacked"
        for producer in ("mypy", "ruff"):
            (self.root / f"{producer}.py").write_text(
                f"from pathlib import Path\nPath({str(sentinel)!r}).write_text('{producer}')\n",
                encoding="utf-8",
            )
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "shadowing modules")
        with patch.dict(os.environ, {"PYTHONPATH": str(self.root)}):
            self.collect(self.root, self.output)
        self.assertFalse(
            sentinel.exists(), "a tracked mypy.py or ruff.py ran as the producer"
        )

    def test_no_producer_cache_is_left_in_the_evidence(self) -> None:
        # CodeAnt on #436: each run's mypy cache stayed inside its retained run
        # directory, so repeated collections accumulated cache trees that are no part
        # of the evidence. A fresh run never reuses one, so none is written.
        path = Path(self.collect(self.root, self.output))
        ran = [
            producer
            for producer in self._read(path)["producers"]
            if producer["invocation"].split(":")[0] == "mypy"
            and producer.get("version")
        ]
        if not ran:
            # Claude on #436: where mypy is absent, as in CI's runtime image, no cache
            # can be written, so a pass would assert nothing.
            self.skipTest("mypy did not run here, so there was no cache to keep")
        run = path.parent
        self.assertEqual(
            [],
            sorted(
                str(p.relative_to(run)) for p in run.rglob("*") if "cache" in p.name
            ),
        )

    def test_a_tracked_symlink_is_never_analyzed(self) -> None:
        # In v2 a link the tree stages, inside it, is withheld from every producer; a
        # link escaping the tree is the owner's refusal of the whole stage, so every
        # tracked file is named unanalyzed and nothing runs (Router #389 6325382720,
        # D3).
        (self.root / "tools" / "link.py").symlink_to("sample.py")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "a tracked symlink")
        inventory = self._read(self.collect(self.root, self.output))
        unanalyzed = {
            u["path"]: u["reason"] for u in inventory["scope"]["full"]["unanalyzed"]
        }
        self.assertIn("symlink", unanalyzed["tools/link.py"])
        self.assertEqual(
            [], [f for f in inventory["findings"] if f["path"] == "tools/link.py"]
        )
        self.assertEqual("EXACT_TREE_STAGED", inventory["source"]["tree_binding"])
        with self.subTest("a link escaping the tree"):
            outside = Path(self.directory.name) / "outside.py"
            outside.write_text(_DIAGNOSTIC_SAMPLE, encoding="utf-8")
            (self.root / "tools" / "away.py").symlink_to(outside)
            self._git("add", "-A")
            self._git("commit", "-q", "-m", "an escaping symlink")
            inventory = self._read(self.collect(self.root, self.output))
            self.assertIn(
                "the source tree cannot be staged: escaping-link",
                inventory["coverage"]["reason"],
            )
            self.assertEqual([], inventory["findings"])
            self.assertEqual("NOT_STAGED", inventory["source"]["tree_binding"])
            self.assertIn(
                "tools/away.py",
                {u["path"] for u in inventory["scope"]["full"]["unanalyzed"]},
            )

    def test_a_failed_comparison_leaves_in_diff_unknown(self) -> None:
        inventory = self._read(self.collect(self.root, self.output, base="f" * 40))
        self.assertIn("cannot compare with base", inventory["coverage"]["reason"])
        complexity = [
            f for f in inventory["findings"] if f["tool"]["id"] == "complexity"
        ]
        self.assertTrue(complexity)
        self.assertEqual({None}, {f["native"]["in_diff"] for f in complexity})

    def test_an_option_like_base_is_refused_before_git(self) -> None:
        written = Path(self.directory.name) / "written-by-git"
        inventory = self._read(
            self.collect(self.root, self.output, base=f"--output={written}")
        )
        self.assertFalse(written.exists())
        self.assertIn("not a 40-hex commit id", inventory["coverage"]["reason"])

    def test_a_change_inside_a_function_puts_its_complexity_in_diff(self) -> None:
        source = self.root / "tools" / "sample.py"
        source.write_text(
            source.read_text(encoding="utf-8").replace(
                "    if a > 7:\n", "    if a > 70:\n", 1
            ),
            encoding="utf-8",
        )
        self._git("commit", "-q", "-am", "change one branch")
        inventory = self._read(self.collect(self.root, self.output, base=self.base))
        (branchy,) = self._find(
            inventory, "complexity", "cc", "tools/sample.py", self.lines["branchy"]
        )
        self.assertIs(True, branchy["native"]["in_diff"])

    def test_more_findings_than_the_budget_write_no_inventory(self) -> None:
        one = self.module.DiagnosticLimits(max_findings=1)
        with self.assertRaisesRegex(QualityEvidenceError, "no inventory was written"):
            self.collect(self.root, self.output, limits=one)
        bound = self.module.DiagnosticLimits(max_findings=10_001)
        with self.assertRaisesRegex(QualityEvidenceError, "normalization bound"):
            self.collect(self.root, self.output, limits=bound)

    def test_a_source_too_deep_to_parse_is_unanalyzed(self) -> None:
        # CPython 3.12 reports this as MemoryError, "Parser stack overflowed" (Claude on #436).
        (self.root / "tools" / "deep.py").write_text(
            "x = " + "-" * 100_000 + "1\n", encoding="utf-8"
        )
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "a source too deep to parse")
        inventory = self._read(self.collect(self.root, self.output))
        unanalyzed = {u["path"] for u in inventory["scope"]["full"]["unanalyzed"]}
        self.assertIn("tools/deep.py", unanalyzed)
        self.assertEqual("INCOMPLETE", inventory["coverage"]["status"])

    def test_a_pathspec_like_filename_is_compared_literally(self) -> None:
        magic = self.root / ":(glob)*.py"
        magic.write_text("A = 1\n", encoding="utf-8")
        (self.root / "other.py").write_text("B = 1\n", encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "two root files")
        base = self._git("rev-parse", "HEAD")
        magic.write_text("A = 2\n", encoding="utf-8")
        (self.root / "other.py").write_text("B = 2\nC = 3\n", encoding="utf-8")
        self._git("commit", "-q", "-am", "change both")
        _diff, lines = self.module._diff_scope(
            self.root, base, time.monotonic() + 30, head=self._head()
        )
        self.assertEqual({1}, lines[":(glob)*.py"])
        self.assertEqual({1, 2}, lines["other.py"])

    def test_a_tracked_dist_info_cannot_set_a_producer_version(self) -> None:
        # Codex on #436: the collector's own metadata search can include the analyzed
        # root, while each producer runs isolated with -I. The recorded version is the
        # producer's own, or none.
        for producer in ("mypy", "ruff"):
            info = self.root / f"{producer}-9.9.9.dist-info"
            info.mkdir()
            (info / "METADATA").write_text(
                f"Metadata-Version: 2.1\nName: {producer}\nVersion: 9.9.9\n",
                encoding="utf-8",
            )
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "tracked dist-info")
        with patch.object(sys, "path", [str(self.root), *sys.path]):
            inventory = self._read(self.collect(self.root, self.output))
        versions = [
            r["version"]
            for r in inventory["producers"]
            if r["producer"] in ("mypy", "ruff")
        ]
        self.assertTrue(versions)
        self.assertNotIn("9.9.9", versions)

    def test_a_spent_budget_starts_no_comparison(self) -> None:
        # CodeAnt on #436: each changed path would start Git with the 1 ms floor. The
        # spent deadline is read first, so the assertion holds one call (SonarCloud
        # S5778).
        spent = time.monotonic() - 1.0
        head = self._head()
        with (
            patch(
                "tools.quality_evidence.subprocess.run",
                side_effect=AssertionError("git started past the deadline"),
            ),
            self.assertRaisesRegex(subprocess.SubprocessError, "deadline had passed"),
        ):
            self.module._diff_scope(self.root, self.base, spent, head=head)

    def test_a_spent_budget_reads_no_subject(self) -> None:
        with (
            patch.object(
                self.module,
                "has_git_metadata",
                side_effect=AssertionError("git started past the deadline"),
            ),
            patch.object(
                self.module,
                "_diagnostic_git",
                side_effect=AssertionError("git started past the deadline"),
            ),
        ):
            commit, tree, gaps = self.module._frozen_subject(
                self.root, None, time.monotonic() - 1.0
            )
        self.assertEqual((None, None), (commit, tree))
        self.assertEqual(["the deadline passed before the subject was frozen"], gaps)

    def test_a_suppression_marked_violation_is_still_reported(self) -> None:
        marker = "# noqa: SLF001"  # fixture text, not a suppression -- the test needs a real marker
        (self.root / "tools" / "marked.py").write_text(
            f"class Box:\n    _hidden = 1\n\n\nVALUE = Box._hidden  {marker}\n",
            encoding="utf-8",
        )
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "a suppression-marked violation")
        inventory = self._read(self.collect(self.root, self.output))
        (ruff,) = [r for r in inventory["producers"] if r["producer"] == "ruff"]
        if ruff["version"] is None:
            self.skipTest("ruff is not installed in this image")
        self.assertTrue(self._find(inventory, "ruff", "SLF001", "tools/marked.py", 5))

    def test_only_the_paths_with_findings_are_compared_line_by_line(self) -> None:
        # CodeAnt on #436, its suggestion of 10:28:46Z: a changed path that no finding
        # names is listed, never read whole.
        (self.root / "data.txt").write_text("x" * 100_000, encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "a large data file")
        calls: list[tuple[str, ...]] = []
        git = self.module._diagnostic_git

        def recording(root, deadline, *arguments, **options):
            calls.append(arguments)
            return git(root, deadline, *arguments, **options)

        with patch("tools.quality_evidence._diagnostic_git", side_effect=recording):
            inventory = self._read(self.collect(self.root, self.output, base=self.base))
        self.assertEqual(["data.txt"], inventory["scope"]["diff"]["changed_paths"])
        self.assertEqual([], [a for a in calls if a[-1] == ":(literal)data.txt"])

    def test_a_configured_textconv_driver_never_runs(self) -> None:
        # CodeAnt on #436: git diff runs a configured textconv driver unless told not.
        sentinel = Path(self.directory.name) / "textconv-ran"
        script = Path(self.directory.name) / "textconv.sh"
        script.write_text(
            f'#!/bin/sh\ntouch "{sentinel}"\ncat "$1"\n', encoding="utf-8"
        )
        script.chmod(0o755)
        (self.root / ".gitattributes").write_text("*.py diff=probe\n", encoding="utf-8")
        self._git("config", "diff.probe.textconv", str(script))
        source = self.root / "tools" / "sample.py"
        source.write_text(
            source.read_text(encoding="utf-8").replace(
                "    if a > 7:\n", "    if a > 70:\n", 1
            ),
            encoding="utf-8",
        )
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "a change under a textconv driver")
        self.collect(self.root, self.output, base=self.base)
        self.assertFalse(sentinel.exists(), "a configured textconv driver ran")

    def test_a_changed_path_with_a_crlf_is_matched_exactly(self) -> None:
        # CodeAnt on #436: text mode turned a CRLF in a NUL-delimited name into LF.
        odd = self.root / "tools" / "odd\r\nname.py"
        odd.write_text(_DIAGNOSTIC_SAMPLE, encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "an odd name")
        base = self._git("rev-parse", "HEAD")
        odd.write_text(
            _DIAGNOSTIC_SAMPLE.replace("    if a > 7:\n", "    if a > 70:\n", 1),
            encoding="utf-8",
        )
        self._git("commit", "-q", "-am", "change it")
        inventory = self._read(self.collect(self.root, self.output, base=base))
        (branchy,) = self._find(
            inventory, "complexity", "cc", "tools/odd\r\nname.py", self.lines["branchy"]
        )
        self.assertIs(True, branchy["native"]["in_diff"])

    def test_each_run_writes_its_own_directory(self) -> None:
        first = self.collect(self.root, self.output)
        second = self.collect(self.root, self.output)
        self.assertNotEqual(Path(first).parent, Path(second).parent)
        self.assertTrue(Path(first).is_file() and Path(second).is_file())


class BoundedRunTests(unittest.TestCase):
    """The producer runner, on real child processes."""

    def setUp(self) -> None:
        self.module = importlib.import_module("tools.quality_evidence")
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name)

    def _run(
        self, code: str, *, report: str = "report", limits=None, seconds: float = 30.0
    ):
        limits = limits or self.module.DiagnosticLimits()
        return self.module._bounded_run(
            [sys.executable, "-c", code],
            cwd=self.path,
            environment=dict(os.environ),
            report=self.path / report,
            deadline=time.monotonic() + seconds,
            limits=limits,
        )

    def test_a_clean_run_streams_its_output(self) -> None:
        self.assertEqual((0, None, False), self._run("print('done')"))
        self.assertEqual("done\n", (self.path / "report").read_text(encoding="utf-8"))

    def test_a_report_that_cannot_be_closed_is_an_invalid_capture(self) -> None:
        # Codex on #436: a flush or close failure of the report escaped _bounded_run.
        # The report's tail may be lost, so the capture is invalid, and the collector's
        # refusal follows; the gap names the error's type, never its text.
        real = self.module._new_file

        def failing(path):
            stream = real(path)
            close = stream.close

            def fail() -> None:
                close()
                raise OSError(errno.ENOSPC, "/host/private: no space")

            stream.close = fail
            return stream

        with patch.object(self.module, "_new_file", side_effect=failing):
            status, gap, invalid = self._run("print('x')")
        self.assertEqual(0, status)
        self.assertTrue(invalid)
        self.assertEqual("its report could not be closed: OSError", gap)
        closed = "its report could not be closed: OSError"
        reap = Mock(side_effect=self.module.bounded_process.reap)
        limits = self.module.DiagnosticLimits(max_report_bytes=16)
        with (
            patch.object(self.module, "_new_file", side_effect=failing),
            patch.object(self.module.bounded_process, "reap", reap),
        ):
            status, gap, invalid = self._run(
                "import sys, time; sys.stdout.write('x' * 8); sys.stdout.flush(); "
                "time.sleep(0.2); sys.stdout.write('y' * 4096)",
                report="cut",
                limits=limits,
            )
        self.assertTrue(invalid)
        self.assertEqual(f"{self.module._OUTPUT_CAP_GAP}; {closed}", gap)
        self.assertEqual(1, reap.call_count)
        # The prefix read before the cut stays: the shared drain never writes part of
        # the chunk that crosses the cap.
        self.assertEqual(b"x" * 8, (self.path / "cut").read_bytes())
        with (
            patch.object(self.module, "_new_file", side_effect=failing),
            patch(
                "tools.quality_evidence.subprocess.Popen",
                side_effect=FileNotFoundError(errno.ENOENT, "/host/private"),
            ),
        ):
            self.assertEqual(
                (None, f"could not run: FileNotFoundError; {closed}", True),
                self._run("print('x')", report="unlaunched"),
            )

    def test_an_interrupt_during_the_drain_reaps_the_child_and_is_raised_again(
        self,
    ) -> None:
        # Claude on #436, by the Router's K-b (6233671174): a cancellation escaping the
        # shared drain left the producer running. The child is reaped once, through the
        # existing owner, the pipe and the report are closed, and the same exception is
        # raised again; a failed reap is noted on it, never in its place.
        real_reap, real_new = self.module.bounded_process.reap, self.module._new_file

        def run(code, report, interrupt, reap):
            seen = {}

            def interrupted(process, *args, **kwargs):
                seen["process"] = process
                raise interrupt

            def opened(path):
                seen["stream"] = real_new(path)
                return seen["stream"]

            with (
                patch.object(
                    self.module.bounded_process, "drain", side_effect=interrupted
                ),
                patch.object(self.module.bounded_process, "reap", reap),
                patch.object(self.module, "_new_file", side_effect=opened),
                self.assertRaises(type(interrupt)) as raised,
            ):
                self._run(code, report=report)
            return raised.exception, seen

        for kind in (KeyboardInterrupt, SystemExit):
            with self.subTest(kind.__name__):
                interrupt, reap = kind(), Mock(side_effect=real_reap)
                raised, seen = run(
                    "import time; time.sleep(30)", kind.__name__, interrupt, reap
                )
                self.assertIs(interrupt, raised)
                self.assertEqual([], getattr(raised, "__notes__", []))
                self.assertEqual(1, reap.call_count)
                self.assertIsNotNone(seen["process"].poll())
                self.assertTrue(seen["process"].stdout.closed)
                self.assertTrue(seen["stream"].closed)
                self.assertTrue((self.path / kind.__name__).exists())
        with self.subTest("a reap that fails"):
            interrupt = KeyboardInterrupt()
            reap = Mock(return_value=subprocess.TimeoutExpired("producer", 5))
            raised, seen = run(
                "import time; time.sleep(30)", "unreaped", interrupt, reap
            )
            seen["process"].kill()
            seen["process"].wait()
            self.assertIs(interrupt, raised)
            self.assertEqual(1, reap.call_count)
            self.assertEqual(
                ["its process could not be reaped within 5 seconds"], raised.__notes__
            )
        with self.subTest("a clean exit is not reaped again"):
            # The drain's own exit waited for the child, so no second cleanup runs.
            reap = Mock(side_effect=real_reap)
            with patch.object(self.module.bounded_process, "reap", reap):
                self.assertEqual(
                    (0, None, False), self._run("print('x')", report="once")
                )
            self.assertEqual(0, reap.call_count)
        with self.subTest("a failed spawn reaps nothing"):
            reap = Mock(side_effect=real_reap)
            with (
                patch.object(self.module.bounded_process, "reap", reap),
                patch(
                    "tools.quality_evidence.subprocess.Popen",
                    side_effect=FileNotFoundError(errno.ENOENT, "/host/private"),
                ),
            ):
                self._run("print('x')", report="unspawned")
            self.assertEqual(0, reap.call_count)

    def test_output_past_the_budget_stops_the_producer(self) -> None:
        started = time.monotonic()
        _status, gap, _invalid = self._run(
            "import sys\nwhile True: sys.stdout.write('x' * 65536)",
            limits=self.module.DiagnosticLimits(max_report_bytes=200_000),
        )
        self.assertIn("max_report_bytes", gap)
        # The cut is an invalid capture, so the collector refuses it (the Router's V1).
        self.assertIs(True, _invalid)
        self.assertLessEqual((self.path / "report").stat().st_size, 200_000)
        self.assertLess(time.monotonic() - started, 20)

    def test_the_deadline_stops_the_producer(self) -> None:
        _status, gap, invalid = self._run("import time\ntime.sleep(60)", seconds=1.0)
        self.assertIn("timed out", gap)
        # A deadline keeps its named partial gap, and is no invalid capture (the
        # Router's G2 on #436).
        self.assertIs(False, invalid)

    def test_a_spent_budget_starts_no_producer(self) -> None:
        # Codex on #436: past the deadline, each remaining mypy group, and ruff, would
        # still start a process and might wait out its reap bound.
        with patch(
            "tools.quality_evidence.subprocess.Popen",
            side_effect=AssertionError("a producer started past the deadline"),
        ):
            status, gap, _invalid = self._run("print('x')", seconds=-1.0)
        self.assertIsNone(status)
        self.assertEqual("not started: the inventory deadline had passed", gap)

    def test_a_reap_that_cannot_wait_is_a_gap(self) -> None:
        # CodeAnt on #436: wait() raises ChildProcessError, an OSError, when the child
        # was already reaped elsewhere.
        def no_child(timeout=None):
            raise ChildProcessError(10, "No child processes")

        process = SimpleNamespace(poll=lambda: None, kill=lambda: None, wait=no_child)
        # The shared owner's reap, worded by the consumer (#365; the Router's X1).
        gap = self.module._reap(process)
        self.assertEqual("its process could not be reaped: ChildProcessError", gap)

    def test_a_producer_whose_output_cannot_be_read_is_a_gap(self) -> None:
        # The shared drain's own read fails: the child is killed and reaped, and the
        # capture is invalid (the Router's V1 on #436).
        real_read = os.read

        def failing_read(fd, size):
            if size != 65_536:
                return real_read(fd, size)
            raise OSError(5, "Input/output error")

        with patch.object(self.module.os, "read", side_effect=failing_read):
            status, gap, invalid = self._run(
                "import sys, time\nprint('x', flush=True)\ntime.sleep(60)"
            )
        self.assertIn("the producer could not be followed", gap)
        self.assertEqual(-signal.SIGKILL, status)
        self.assertIs(True, invalid)

    def test_a_wait_error_is_an_invalid_capture(self) -> None:
        # cubic on #436 named a wait failure apart from an output failure. The shared
        # drain returns either as its `error`, and the Router's V1 (6229993455) refuses
        # that report conservatively, even when its output had ended.
        def no_child(timeout=None):
            raise ChildProcessError(10, "No child processes")

        read_end, write_end = os.pipe()
        os.close(write_end)
        process = SimpleNamespace(
            stdout=os.fdopen(read_end, "rb"),
            poll=lambda: None,
            kill=lambda: None,
            wait=no_child,
            returncode=None,
        )
        with patch("tools.quality_evidence.subprocess.Popen", return_value=process):
            _status, gap, invalid = self._run("print('x')", report="no-child")
        self.assertTrue(
            gap.startswith("the producer could not be followed: ChildProcessError"), gap
        )
        self.assertIs(True, invalid)

    def test_a_lifecycle_gap_names_the_exception_type_never_its_text(self) -> None:
        # Octopus on #436, by the Router's X1 (6228685377), at the four lifecycle sites
        # that the consumer slice held: a failure's text can carry a host path or argv.
        sentinel = f"{self.path}/safe.directory=sentinel"
        real_read = os.read

        def failing_read(fd, size):
            if size != 65_536:
                return real_read(fd, size)
            raise OSError(5, "Input/output error", sentinel)

        cases = (
            (
                "its report cannot be created",
                patch.object(
                    self.module,
                    "_new_file",
                    side_effect=PermissionError(13, "Permission denied", sentinel),
                ),
                "cannot create its report: PermissionError",
            ),
            (
                "it cannot be started",
                patch(
                    "tools.quality_evidence.subprocess.Popen",
                    side_effect=FileNotFoundError(2, "No such file", sentinel),
                ),
                "could not run: FileNotFoundError",
            ),
            (
                "its output cannot be read",
                patch.object(self.module.os, "read", side_effect=failing_read),
                "the producer could not be followed: OSError",
            ),
        )
        for index, (label, failure, expected) in enumerate(cases):
            with self.subTest(label):
                with failure:
                    gap = self._run(
                        "import time\ntime.sleep(2)\nprint('x')", report=f"r{index}"
                    )[1]
                self.assertIn(expected, gap)
                self.assertNotIn(sentinel, gap)
        with self.subTest("it cannot be waited on or reaped"):
            read_end, write_end = os.pipe()
            os.close(write_end)

            def no_child(timeout=None):
                raise ChildProcessError(10, "No child processes", sentinel)

            process = SimpleNamespace(
                stdout=os.fdopen(read_end, "rb"),
                poll=lambda: None,
                kill=lambda: None,
                wait=no_child,
                returncode=None,
            )
            with patch("tools.quality_evidence.subprocess.Popen", return_value=process):
                gap = self._run("print('x')", report="unreaped")[1]
            self.assertIn("could not be reaped: ChildProcessError", gap)
            self.assertNotIn(sentinel, gap)
            # The primary failure first, then the cleanup's (the Router's G2).
            self.assertTrue(gap.startswith("the producer could not be followed: "), gap)

    def test_an_unknown_drain_outcome_is_an_invalid_capture(self) -> None:
        # The Router's G2: an outcome without the field its contract names is never a
        # clean capture; the child is still reaped.
        unknown = SimpleNamespace(
            outcome="unknown",
            returncode=None,
            error=None,
            exception=None,
            selector_closed=True,
        )
        with patch.object(self.module.bounded_process, "drain", return_value=unknown):
            _status, gap, invalid = self._run("print('x')", report="unknown")
        self.assertIn("unexpected drain outcome unknown", gap)
        self.assertIs(True, invalid)

    def test_a_selector_that_cannot_be_closed_is_named(self) -> None:
        # The Router's G2 (6231894979): the drain reports a selector it could not
        # close, and the run says so rather than declaring a clean capture.
        import selectors as real_selectors

        real_selector = real_selectors.DefaultSelector

        class Unclosable(real_selector):
            def close(self):
                super().close()
                raise OSError(9, "Bad file descriptor")

        with patch.object(real_selectors, "DefaultSelector", Unclosable):
            gap = self._run("print('done')", report="unclosable")[1]
        self.assertIn("its output selector could not be closed", gap or "")

    def test_an_unexpected_exit_is_named_before_a_cleanup_detail(self) -> None:
        # Octopus on #436, by the Router's O-a (6239259708): an exit of 2 whose
        # selector could not be closed was named by the cleanup detail alone. A
        # non-0/1 exit comes first, once; an already waited exit is not reaped again.
        import selectors as real_selectors

        real_selector = real_selectors.DefaultSelector
        selector = "its output selector could not be closed"

        class Unclosable(real_selector):
            def close(self):
                super().close()
                raise OSError(9, "Bad file descriptor")

        cases = (
            ("exit 0", "raise SystemExit(0)", 0, None, selector),
            ("exit 1", "raise SystemExit(1)", 1, None, selector),
            ("exit 2", "raise SystemExit(2)", 2, "exited 2", f"exited 2; {selector}"),
            (
                "a signal",
                "import os, signal; os.kill(os.getpid(), signal.SIGKILL)",
                -9,
                "exited -9",
                f"exited -9; {selector}",
            ),
        )
        real_reap = self.module.bounded_process.reap
        for label, code, status, plain, closed in cases:
            for broken in (False, True):
                with self.subTest(label, selector_fails=broken):
                    reap = Mock(side_effect=real_reap)
                    report = f"{label}-{broken}".replace(" ", "-")
                    with patch.object(self.module.bounded_process, "reap", reap):
                        if broken:
                            with patch.object(
                                real_selectors, "DefaultSelector", Unclosable
                            ):
                                result = self._run(code, report=report)
                        else:
                            result = self._run(code, report=report)
                    self.assertEqual(
                        (status, closed if broken else plain, False), result
                    )
                    self.assertEqual(0, reap.call_count)
        real_new = self.module._new_file

        def failing(path):
            stream = real_new(path)
            close = stream.close

            def fail() -> None:
                close()
                raise OSError(errno.ENOSPC, "no space")

            stream.close = fail
            return stream

        with (
            patch.object(real_selectors, "DefaultSelector", Unclosable),
            patch.object(self.module, "_new_file", side_effect=failing),
        ):
            self.assertEqual(
                (
                    2,
                    f"exited 2; {selector}; its report could not be closed: OSError",
                    True,
                ),
                self._run("raise SystemExit(2)", report="composed"),
            )

    def test_an_unexpected_exit_status_is_a_gap(self) -> None:
        self.assertEqual((3, "exited 3", False), self._run("raise SystemExit(3)"))

    def test_a_missing_stdout_pipe_is_a_gap_not_a_crash(self) -> None:
        # The child is still reaped, and its capture is invalid (the Router's G2).
        process = SimpleNamespace(
            stdout=None,
            poll=lambda: None,
            kill=lambda: None,
            wait=lambda timeout=None: 0,
            returncode=-9,
        )
        with patch("tools.quality_evidence.subprocess.Popen", return_value=process):
            _status, gap, invalid = self._run("print('x')", report="no-stdout")
        self.assertEqual("the producer's stdout pipe is unavailable", gap)
        self.assertIs(True, invalid)

    def test_a_subject_read_past_its_timeout_is_unknown(self) -> None:
        def slow(command, **options):
            raise subprocess.TimeoutExpired(["git"], options.get("timeout"))

        with patch("tools.quality_evidence.subprocess.run", side_effect=slow):
            state = self.module._git_state(self.path, timeout=0.5)
        self.assertIsNone(state["tracked_tree_dirty"])

    def test_the_two_subject_reads_share_one_budget(self) -> None:
        # The status read gets what the revision read left (cubic and CodeAnt on #436).
        clock = [100.0]
        seen: list[object] = []

        def run(command, **options):
            seen.append(options.get("timeout"))
            clock[0] += 0.75
            return SimpleNamespace(stdout="a" * 40)

        with (
            patch(
                "tools.quality_evidence.time.monotonic", side_effect=lambda: clock[0]
            ),
            patch("tools.quality_evidence.subprocess.run", side_effect=run),
        ):
            self.module._git_state(self.path, timeout=1.0)
            self.assertEqual([1.0, 0.25], seen)
            seen.clear()
            self.module._git_state(self.path)
        self.assertEqual([None, None], seen)

    def test_a_spent_budget_starts_no_second_subject_read(self) -> None:
        # Codex on #436: when the revision read spends the budget, the status read is
        # not started against the millisecond floor; the dirty state stays unknown.
        clock = [100.0]
        seen: list[object] = []

        def run(command, **options):
            seen.append(command[-1])
            clock[0] += 2.0
            return SimpleNamespace(stdout="a" * 40)

        with (
            patch(
                "tools.quality_evidence.time.monotonic", side_effect=lambda: clock[0]
            ),
            patch("tools.quality_evidence.subprocess.run", side_effect=run),
        ):
            state = self.module._git_state(self.path, timeout=1.0)
        self.assertEqual(["HEAD"], seen)
        self.assertIsNone(state["tracked_tree_dirty"])

    def test_each_subject_read_decides_its_check_and_timeout_with_one_reading(
        self,
    ) -> None:
        # CodeAnt on #436, by the Router's I-b ("no fresh millisecond allowance"):
        # each state read took its check and its timeout from two readings, and the
        # timeout was floored to a millisecond, so a deadline crossed in between, or
        # spent before the first read, still started Git. One reading now decides
        # both, unfloored.
        def clocked(readings, timeout):
            values = iter(readings)
            seen: list[object] = []

            def run(command, **options):
                seen.append(options.get("timeout"))
                return SimpleNamespace(stdout="a" * 40)

            with (
                patch(
                    "tools.quality_evidence.time.monotonic",
                    side_effect=lambda: next(values, readings[-1]),
                ),
                patch("tools.quality_evidence.subprocess.run", side_effect=run),
            ):
                state = self.module._git_state(self.path, timeout=timeout)
            return state, seen

        with self.subTest("crossed between the check and the timeout"):
            _state, seen = clocked([100.0, 100.0, 100.9995, 101.2], 1.0)
            self.assertEqual(2, len(seen))
            self.assertEqual(1.0, seen[0])
            self.assertAlmostEqual(0.0005, seen[1], places=9)
        with self.subTest("spent before the first read"):
            state, seen = clocked([100.0, 100.000002], 0.000001)
            self.assertEqual([], seen)
            self.assertIsNone(state["tracked_tree_dirty"])
        with self.subTest("barely open before the first read"):
            state, seen = clocked([100.0, 100.9996, 101.0], 1.0)
            self.assertEqual(1, len(seen))
            self.assertAlmostEqual(0.0004, seen[0], places=9)
            self.assertIsNone(state["tracked_tree_dirty"])

    def test_a_producer_that_cannot_be_reaped_is_a_gap_not_a_hang(self) -> None:
        # The wait after kill() is bounded (Amazon Q on #436, as security_scan's
        # _terminate_and_reap), and so is every wait on the way out.
        waits: list[object] = []

        class Unreapable:
            stdout = None
            returncode = None

            def poll(self):
                return None

            def kill(self):
                pass

            def wait(self, timeout=None):
                waits.append(timeout)
                if timeout is None:
                    raise RuntimeError(
                        "an unbounded wait on a child that cannot be reaped"
                    )
                raise subprocess.TimeoutExpired(["producer"], timeout)

            def __enter__(self):
                return self

            def __exit__(self, *exc_info):
                self.wait()  # as Popen's own __exit__, which waits without a bound

        with patch(
            "tools.quality_evidence.subprocess.Popen", return_value=Unreapable()
        ):
            status, gap, _invalid = self._run("print('x')")
        self.assertIsNone(status)
        self.assertIn("could not be reaped", gap)
        self.assertNotIn(None, waits)

    def test_a_stopped_producer_is_killed_reaped_and_its_pipe_closed(self) -> None:
        # Characterization of what `with process` and kill() did before round 3.
        started: list[subprocess.Popen[bytes]] = []
        real = subprocess.Popen

        def recording(*args, **options):
            started.append(real(*args, **options))
            return started[-1]

        with patch("tools.quality_evidence.subprocess.Popen", side_effect=recording):
            status, gap, _invalid = self._run(
                "import time\ntime.sleep(60)", seconds=1.0
            )
        self.assertIn("timed out", gap)
        self.assertEqual(-signal.SIGKILL, status)
        self.assertEqual(-signal.SIGKILL, started[0].returncode)
        self.assertTrue(started[0].stdout.closed)

    def test_a_report_is_never_an_existing_file_or_a_symlink(self) -> None:
        (self.path / "taken").write_text("kept", encoding="utf-8")
        _status, gap, _invalid = self._run("print('x')", report="taken")
        self.assertIn("cannot create its report", gap)
        self.assertEqual("kept", (self.path / "taken").read_text(encoding="utf-8"))
        target = self.path / "target"
        (self.path / "link").symlink_to(target)
        _status, gap, _invalid = self._run("print('x')", report="link")
        self.assertIn("cannot create its report", gap)
        self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
