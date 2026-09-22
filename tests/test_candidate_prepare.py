from __future__ import annotations

import json
import os
import shutil
import subprocess  # nosec B404 -- bounded fixture subprocess boundary
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from tools import candidate_prepare

ROOT = Path(__file__).resolve().parents[1]
GIT: str = shutil.which("git") or ""
if not GIT:
    raise RuntimeError("git is required for candidate preparation tests")

_GIT_ENVIRONMENT_VARIABLES = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_COMMON_DIR",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_INDEX_FILE",
    "GIT_CEILING_DIRECTORIES",
    "GIT_DISCOVERY_ACROSS_FILESYSTEM",
)


def _test_env() -> dict[str, str]:
    env = dict(os.environ)
    for name in _GIT_ENVIRONMENT_VARIABLES:
        env.pop(name, None)
    return env


class CandidatePreparationContractTests(unittest.TestCase):
    @staticmethod
    def _git(root: Path, *arguments: str) -> str:
        completed = subprocess.run(  # nosemgrep  # nosec B603
            [GIT, *arguments],
            cwd=root,
            env=_test_env(),
            check=True,
            shell=False,
            capture_output=True,
            text=True,
        )
        return completed.stdout.strip()

    @staticmethod
    def _repository(root: Path) -> str:
        CandidatePreparationContractTests._git(root, "init", "--quiet")
        CandidatePreparationContractTests._git(
            root, "config", "user.email", "candidate@example.invalid"
        )
        CandidatePreparationContractTests._git(
            root, "config", "user.name", "Candidate Test"
        )
        (root / "ci").mkdir()
        style = root / "ci" / "style"
        style.write_text(
            "#!/bin/sh\n"
            "set -eu\n"
            'case "$1" in\n'
            "  --fix) sed -i 's/value=1/value = 1/' candidate.py ;;\n"
            "  --check) grep -q '^value = 1$' candidate.py ;;\n"
            "  *) exit 2 ;;\n"
            "esac\n",
            encoding="utf-8",
        )
        style.chmod(0o755)
        verify = root / "ci" / "verify"
        verify.write_text(
            "#!/bin/sh\\n"
            "set -eu\\n"
            'test "$1" = "fast"\\n'
            'case "${GNOSTOA_TEST_FOCUSED_MODE:-pass}" in\\n'
            "  mutate) printf 'changed\\n' > candidate.py ;;\\n"
            "  fail) exit 7 ;;\\n"
            "  pass) grep -q '^value = 1$' candidate.py ;;\\n"
            "  *) exit 8 ;;\\n"
            "esac\\n",
            encoding="utf-8",
        )
        verify.chmod(0o755)
        (root / "base.txt").write_text("base\n", encoding="utf-8")
        CandidatePreparationContractTests._git(root, "add", ".")
        CandidatePreparationContractTests._git(root, "commit", "--quiet", "-m", "base")
        return CandidatePreparationContractTests._git(root, "rev-parse", "HEAD")

    def _receipt(self) -> Path:
        receipt_root = Path(tempfile.mkdtemp(prefix="gnostoa-receipt-test-"))
        self.addCleanup(shutil.rmtree, receipt_root, ignore_errors=True)
        return receipt_root / "receipt.json"

    @staticmethod
    def _prepare(
        root: Path,
        parent: str,
        receipt: Path,
        profile: str = "fast",
    ) -> dict[str, Any]:
        with (
            patch.object(candidate_prepare, "_repository_root", return_value=root),
            patch.object(
                candidate_prepare,
                "_ruff_version",
                return_value="ruff 0.16.0",
            ),
        ):
            return candidate_prepare.prepare(parent, receipt, profile)

    def test_raw_git_commit_characterizes_non_hook_escape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._repository(root)
            (root / "candidate.py").write_text("value=1\n", encoding="utf-8")
            style = subprocess.run(  # nosemgrep  # nosec B603
                [str(root / "ci" / "style"), "--check"],
                cwd=root,
                env=_test_env(),
                check=False,
                shell=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(0, style.returncode)
            self._git(root, "add", "candidate.py")
            self._git(root, "commit", "--quiet", "-m", "unprepared candidate")
            self.assertEqual(
                "value=1\n",
                (root / "candidate.py").read_text(encoding="utf-8"),
            )

    def test_prepare_binds_normalized_tree_and_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = self._repository(root)
            (root / "candidate.py").write_text("value=1\n", encoding="utf-8")
            receipt = self._receipt()
            payload = self._prepare(root, parent, receipt)
            self.assertEqual(parent, payload["parent_commit"])
            self.assertEqual(["candidate.py"], payload["changed_paths"])
            self.assertEqual("PRE_CANDIDATE_RUFF_CATCH", payload["metric_event"])
            self.assertTrue(receipt.is_file())
            self.assertEqual(
                payload,
                candidate_prepare.verify_receipt(
                    receipt,
                    parent,
                    payload["prepared_tree"],
                ),
            )

    def test_prepare_rejects_stale_parent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = self._repository(root)
            (root / "second.txt").write_text("second\n", encoding="utf-8")
            self._git(root, "add", "second.txt")
            self._git(root, "commit", "--quiet", "-m", "second")
            receipt = self._receipt()
            with self.assertRaisesRegex(candidate_prepare.PrepareError, "stale parent"):
                self._prepare(root, parent, receipt)
            self.assertFalse(receipt.exists())

    def test_receipt_verification_is_exact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = self._repository(root)
            (root / "candidate.py").write_text("value=1\n", encoding="utf-8")
            receipt = self._receipt()
            payload = self._prepare(root, parent, receipt)
            with self.assertRaisesRegex(
                candidate_prepare.PrepareError,
                "tree mismatch",
            ):
                candidate_prepare.verify_receipt(receipt, parent, "0" * 40)
            document = json.loads(receipt.read_text(encoding="utf-8"))
            document["prepared_tree"] = "0" * 40
            receipt.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(
                candidate_prepare.PrepareError,
                "digest mismatch",
            ):
                candidate_prepare.verify_receipt(
                    receipt,
                    parent,
                    payload["prepared_tree"],
                )

    def test_prepare_includes_untracked_addition_and_deletion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = self._repository(root)
            (root / "base.txt").unlink()
            (root / "candidate.py").write_text("value=1\n", encoding="utf-8")
            receipt = self._receipt()
            payload = self._prepare(root, parent, receipt)
            self.assertEqual(["base.txt", "candidate.py"], payload["changed_paths"])

    def test_prepare_rejects_focused_verifier_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = self._repository(root)
            (root / "candidate.py").write_text("value=1\n", encoding="utf-8")
            receipt = self._receipt()
            with (
                patch.dict(
                    os.environ,
                    {"GNOSTOA_TEST_FOCUSED_MODE": "mutate"},
                    clear=False,
                ),
                self.assertRaisesRegex(
                    candidate_prepare.PrepareError,
                    "focused verification mutated candidate",
                ),
            ):
                self._prepare(root, parent, receipt)
            self.assertFalse(receipt.exists())

    def test_prepare_rejects_failed_focused_verification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = self._repository(root)
            (root / "candidate.py").write_text("value=1\n", encoding="utf-8")
            receipt = self._receipt()
            with (
                patch.dict(
                    os.environ,
                    {"GNOSTOA_TEST_FOCUSED_MODE": "fail"},
                    clear=False,
                ),
                self.assertRaisesRegex(
                    candidate_prepare.PrepareError,
                    r"focused verification failed \(7\)",
                ),
            ):
                self._prepare(root, parent, receipt)
            self.assertFalse(receipt.exists())

    def test_prepare_rejects_unknown_focused_profile(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = self._repository(root)
            (root / "candidate.py").write_text("value=1\n", encoding="utf-8")
            receipt = self._receipt()
            with (
                patch.object(candidate_prepare, "_repository_root", return_value=root),
                self.assertRaisesRegex(
                    candidate_prepare.PrepareError,
                    "unsupported focused verification profile",
                ),
            ):
                candidate_prepare.prepare(parent, receipt, "unknown")

    def test_prepare_rejects_candidate_local_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = self._repository(root)
            (root / "candidate.py").write_text("value=1\n", encoding="utf-8")
            with self.assertRaisesRegex(
                candidate_prepare.PrepareError,
                "receipt path must be outside",
            ):
                self._prepare(root, parent, root / "receipt.json")

    def test_receipt_verification_does_not_require_preparation_executable(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = self._repository(root)
            (root / "candidate.py").write_text("value=1\n", encoding="utf-8")
            receipt = self._receipt()
            payload = self._prepare(root, parent, receipt)
            (root / "ci" / "verify").unlink()
            self.assertEqual(
                payload,
                candidate_prepare.verify_receipt(
                    receipt,
                    parent,
                    payload["prepared_tree"],
                ),
            )

    def test_cli_verify_consumes_exact_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = self._repository(root)
            (root / "candidate.py").write_text("value=1\n", encoding="utf-8")
            receipt = self._receipt()
            payload = self._prepare(root, parent, receipt)
            self.assertEqual(
                0,
                candidate_prepare.main(
                    [
                        "verify",
                        "--parent",
                        parent,
                        "--tree",
                        payload["prepared_tree"],
                        "--receipt",
                        str(receipt),
                    ]
                ),
            )

    def test_prepare_scrubs_inherited_git_repository_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = self._repository(root)
            (root / "candidate.py").write_text("value=1\n", encoding="utf-8")
            receipt = self._receipt()
            poisoned = {
                name: "poisoned-by-caller" for name in _GIT_ENVIRONMENT_VARIABLES
            }
            with patch.dict(os.environ, poisoned, clear=False):
                payload = self._prepare(root, parent, receipt)
            self.assertEqual(parent, payload["parent_commit"])
            self.assertEqual("PRE_CANDIDATE_RUFF_CATCH", payload["metric_event"])

    def test_cli_prepare_uses_allowlisted_focused_profile(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = self._repository(root)
            (root / "candidate.py").write_text("value=1\\n", encoding="utf-8")
            receipt = self._receipt()
            with (
                patch.object(candidate_prepare, "_repository_root", return_value=root),
                patch.object(
                    candidate_prepare,
                    "_ruff_version",
                    return_value="ruff 0.16.0",
                ),
            ):
                result = candidate_prepare.main(
                    [
                        "prepare",
                        "--parent",
                        parent,
                        "--receipt",
                        str(receipt),
                        "--focused-profile",
                        "fast",
                    ]
                )
            self.assertEqual(0, result)
            document = json.loads(receipt.read_text(encoding="utf-8"))
            self.assertEqual(
                ["ci/verify", "fast"],
                document["focused_command"],
            )

    def test_ci_wrapper_routes_to_candidate_prepare_module(self) -> None:
        wrapper = ROOT / "ci" / "prepare-candidate"
        self.assertTrue(wrapper.is_file())
        text = wrapper.read_text(encoding="utf-8")
        self.assertIn('cd "$(dirname "$0")/.."', text)
        self.assertIn("python -m tools.candidate_prepare", text)
        with tempfile.TemporaryDirectory() as directory:
            completed = subprocess.run(  # nosemgrep  # nosec B603
                [str(wrapper), "--help"],
                cwd=Path(directory),
                env=_test_env(),
                check=False,
                shell=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(0, completed.returncode, completed.stderr)


if __name__ == "__main__":
    unittest.main()
