from __future__ import annotations

import importlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class CandidatePreparationContractTests(unittest.TestCase):
    def _module(self):
        return importlib.import_module("tools.candidate_prepare")

    def _git(self, root: Path, *arguments: str) -> str:
        completed = subprocess.run(
            ["git", *arguments],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout.strip()

    def _repository(self, root: Path) -> str:
        self._git(root, "init", "--quiet")
        self._git(root, "config", "user.email", "candidate@example.invalid")
        self._git(root, "config", "user.name", "Candidate Test")
        (root / "ci").mkdir()
        style = root / "ci" / "style"
        style.write_text(
            "#!/bin/sh\n"
            "set -eu\n"
            "case \"$1\" in\n"
            "  --fix) sed -i 's/value=1/value = 1/' candidate.py ;;\n"
            "  --check) grep -q '^value = 1$' candidate.py ;;\n"
            "  *) exit 2 ;;\n"
            "esac\n",
            encoding="utf-8",
        )
        style.chmod(0o755)
        (root / "base.txt").write_text("base\n", encoding="utf-8")
        self._git(root, "add", ".")
        self._git(root, "commit", "--quiet", "-m", "base")
        return self._git(root, "rev-parse", "HEAD")

    def test_raw_git_commit_characterizes_non_hook_escape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._repository(root)
            (root / "candidate.py").write_text("value=1\n", encoding="utf-8")
            self._git(root, "add", "candidate.py")
            completed = subprocess.run(
                ["git", "commit", "--quiet", "-m", "unprepared candidate"],
                cwd=root,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertEqual(
                "value=1\n",
                (root / "candidate.py").read_text(encoding="utf-8"),
            )

    def test_prepare_binds_normalized_tree_and_receipt(self) -> None:
        candidate_prepare = self._module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = self._repository(root)
            (root / "candidate.py").write_text("value=1\n", encoding="utf-8")
            focused = root / "focused.py"
            focused.write_text(
                "from pathlib import Path\n"
                'assert Path("candidate.py").read_text() == "value = 1\\n"\n',
                encoding="utf-8",
            )
            receipt = Path(directory).parent / f"{root.name}-receipt.json"
            with patch.object(
                candidate_prepare,
                "_repository_root",
                return_value=root,
            ), patch.object(
                candidate_prepare,
                "_ruff_version",
                return_value="ruff 0.16.0",
            ):
                payload = candidate_prepare.prepare(
                    parent,
                    receipt,
                    [sys.executable, str(focused)],
                )
            self.assertEqual(parent, payload["parent_commit"])
            self.assertEqual(["candidate.py", "focused.py"], payload["changed_paths"])
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
        candidate_prepare = self._module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = self._repository(root)
            (root / "second.txt").write_text("second\n", encoding="utf-8")
            self._git(root, "add", "second.txt")
            self._git(root, "commit", "--quiet", "-m", "second")
            receipt = Path(directory).parent / f"{root.name}-receipt.json"
            with patch.object(candidate_prepare, "_repository_root", return_value=root):
                with self.assertRaisesRegex(
                    candidate_prepare.PrepareError,
                    "stale parent",
                ):
                    candidate_prepare.prepare(
                        parent,
                        receipt,
                        [sys.executable, "-c", "pass"],
                    )
            self.assertFalse(receipt.exists())

    def test_receipt_verification_is_exact(self) -> None:
        candidate_prepare = self._module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = self._repository(root)
            (root / "candidate.py").write_text("value=1\n", encoding="utf-8")
            receipt = Path(directory).parent / f"{root.name}-receipt.json"
            with patch.object(
                candidate_prepare,
                "_repository_root",
                return_value=root,
            ), patch.object(
                candidate_prepare,
                "_ruff_version",
                return_value="ruff 0.16.0",
            ):
                payload = candidate_prepare.prepare(
                    parent,
                    receipt,
                    [sys.executable, "-c", "pass"],
                )
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

    def test_ci_wrapper_routes_to_candidate_prepare_module(self) -> None:
        wrapper = ROOT / "ci" / "prepare-candidate"
        self.assertTrue(wrapper.is_file())
        self.assertIn(
            "python -m tools.candidate_prepare",
            wrapper.read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
