from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from email.message import Message
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

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
