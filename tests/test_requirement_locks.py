from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.quality_evidence import QualityEvidenceError, parse_pip_artifact_report
from tools.requirements_lock import (
    LockFormatError,
    locked_requirements,
    render_hashed_requirements,
    wheel_hashes_from_pypi_release,
)

ROOT = Path(__file__).resolve().parent.parent
HASH_A = "a" * 64
HASH_B = "b" * 64


def _lock_text(*, artifact_hash: str = HASH_A) -> str:
    return (
        "# exact wheel-only lock\n"
        "--only-binary :all:\n"
        "--require-hashes\n"
        "\n"
        "Example_Name==1.0 \\\n"
        f"    --hash=sha256:{artifact_hash}\n"
    )


def _pip_report(*, artifact_hash: str = HASH_A, yanked: bool = False) -> dict:
    return {
        "version": "1",
        "pip_version": "26.0.1",
        "install": [
            {
                "download_info": {
                    "url": (
                        "https://files.pythonhosted.org/packages/aa/example-1.0-"
                        "py3-none-any.whl"
                    ),
                    "archive_info": {"hashes": {"sha256": artifact_hash}},
                },
                "is_direct": False,
                "is_yanked": yanked,
                "metadata": {"name": "Example_Name", "version": "1.0"},
                "requested": True,
            }
        ],
        "environment": {
            "implementation_name": "cpython",
            "python_version": "3.12",
            "platform_machine": "x86_64",
            "platform_system": "Linux",
            "sys_platform": "linux",
            "platform_release": "host-specific-and-excluded",
        },
    }


class RequirementLockParsingTests(unittest.TestCase):
    def test_parser_requires_canonical_global_controls_and_sha256_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lock = Path(directory) / "runtime.lock"
            lock.write_text(_lock_text(), encoding="utf-8")

            self.assertEqual(
                [
                    {
                        "name": "Example_Name",
                        "normalized_name": "example-name",
                        "version": "1.0",
                        "artifact_hashes": [HASH_A],
                    }
                ],
                locked_requirements(lock),
            )

            lock.write_text("Example_Name==1.0\n", encoding="utf-8")
            with self.assertRaisesRegex(LockFormatError, "--require-hashes"):
                locked_requirements(lock)

            lock.write_text(_lock_text().replace("sha256", "sha512"), encoding="utf-8")
            with self.assertRaisesRegex(LockFormatError, "SHA-256"):
                locked_requirements(lock)

            lock.write_text(
                _lock_text() + _lock_text().split("\n\n", maxsplit=1)[1],
                encoding="utf-8",
            )
            with self.assertRaisesRegex(LockFormatError, "duplicates"):
                locked_requirements(lock)

    def test_renderer_is_deterministic_and_round_trips(self) -> None:
        rendered = render_hashed_requirements(
            [("Example_Name", "1.0")],
            {"example-name": [HASH_B, HASH_A, HASH_A]},
            header=["# exact wheel-only lock"],
        )
        self.assertEqual(
            (
                "# exact wheel-only lock\n"
                "--only-binary :all:\n"
                "--require-hashes\n"
                "\n"
                "Example_Name==1.0 \\\n"
                f"    --hash=sha256:{HASH_A} \\\n"
                f"    --hash=sha256:{HASH_B}\n"
            ),
            rendered,
        )
        with tempfile.TemporaryDirectory() as directory:
            lock = Path(directory) / "runtime.lock"
            lock.write_text(rendered, encoding="utf-8")
            self.assertEqual(
                [HASH_A, HASH_B], locked_requirements(lock)[0]["artifact_hashes"]
            )

    def test_pypi_release_filter_keeps_only_non_yanked_wheels(self) -> None:
        document = {
            "urls": [
                {
                    "digests": {"sha256": HASH_B},
                    "filename": "example-1.0.tar.gz",
                    "packagetype": "sdist",
                    "yanked": False,
                },
                {
                    "digests": {"sha256": HASH_A},
                    "filename": "example-1.0-py3-none-any.whl",
                    "packagetype": "bdist_wheel",
                    "yanked": False,
                },
                {
                    "digests": {"sha256": HASH_B},
                    "filename": "example-1.0-cp312-manylinux.whl",
                    "packagetype": "bdist_wheel",
                    "yanked": "withdrawn",
                },
            ]
        }
        self.assertEqual(
            [HASH_A],
            wheel_hashes_from_pypi_release(document, "example", "1.0"),
        )


class PipArtifactSelectionTests(unittest.TestCase):
    def test_report_binds_selected_wheel_to_committed_hash_allowlist(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lock = root / "runtime.lock"
            report = root / "pip-report.json"
            lock.write_text(_lock_text(), encoding="utf-8")
            report.write_text(json.dumps(_pip_report()), encoding="utf-8")

            selection = parse_pip_artifact_report(
                lock,
                report,
                lock_identity="requirements/runtime.lock",
                scope="runtime",
            )

            self.assertEqual(1, selection["summary"]["packages"])
            self.assertEqual(HASH_A, selection["packages"][0]["sha256"])
            self.assertEqual(
                "example-1.0-py3-none-any.whl",
                selection["packages"][0]["filename"],
            )
            self.assertEqual(
                {
                    "implementation_name": "cpython",
                    "platform_machine": "x86_64",
                    "platform_system": "Linux",
                    "python_version": "3.12",
                    "sys_platform": "linux",
                },
                selection["environment"],
            )
            self.assertNotIn("platform_release", selection["environment"])
            self.assertNotIn(str(root), json.dumps(selection))

            report.write_text(
                json.dumps(_pip_report(artifact_hash=HASH_B)), encoding="utf-8"
            )
            with self.assertRaisesRegex(
                QualityEvidenceError, "not admitted by the committed lock"
            ):
                parse_pip_artifact_report(
                    lock,
                    report,
                    lock_identity="requirements/runtime.lock",
                    scope="runtime",
                )

            report.write_text(json.dumps(_pip_report(yanked=True)), encoding="utf-8")
            with self.assertRaisesRegex(QualityEvidenceError, "yanked"):
                parse_pip_artifact_report(
                    lock,
                    report,
                    lock_identity="requirements/runtime.lock",
                    scope="runtime",
                )


class RepositoryRequirementLockTests(unittest.TestCase):
    def test_repository_locks_and_install_routes_are_fail_closed(self) -> None:
        parsed_locks = {}
        for name in ("runtime.lock", "development.lock"):
            requirements = locked_requirements(ROOT / "requirements" / name)
            parsed_locks[name] = requirements
            self.assertGreater(len(requirements), 0)
            self.assertTrue(
                all(requirement["artifact_hashes"] for requirement in requirements)
            )
        self.assertIn(
            "pip",
            {
                requirement["normalized_name"]
                for requirement in parsed_locks["development.lock"]
            },
            "pip-api's pip dependency must remain exact in clean resolutions",
        )

        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertGreaterEqual(dockerfile.count("--require-hashes"), 2)
        self.assertGreaterEqual(dockerfile.count("--only-binary=:all:"), 2)
        self.assertGreaterEqual(dockerfile.count("--report"), 2)


if __name__ == "__main__":
    unittest.main()
