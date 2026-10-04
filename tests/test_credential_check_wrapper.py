"""The credential check runs from an exact authority commit (Decision 0101, #364).

The check gates an agent's first provider write, so it must not take its declaration
or its judgement from the candidate it authorizes: a candidate could widen a maximum
or accept a grant and pass its own gate (Codex on #364; owner decision 2026-10-05).
`ci/credential-check`, retrieved from the protected-main commit, extracts that commit
and runs its checker against its declaration; the agent's checkout is read only for
how it pushes. These tests run the wrapper against a real repository whose working
tree disagrees with the commit, and whose PATH is poisoned.
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess  # nosec B404
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "ci" / "credential-check"
# Parses as the real checker does (argparse: the last occurrence of an option wins).
FAKE_CHECKER = """
import argparse, json, os, sys


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy")
    parser.add_argument("--worktree")
    known, _ = parser.parse_known_args(argv)
    policy = known.policy
    print(json.dumps({
        "from": "authority",
        "cwd": os.getcwd(),
        "argv": argv,
        "policy": open(policy, encoding="utf-8").read() if policy else None,
        "kit": os.environ.get("KNOWLEDGE_KIT_ROOT"),
        "worktree": known.worktree,
    }))
    return 0
"""


def _git(root: pathlib.Path, *arguments: str) -> str:
    completed = subprocess.run(  # nosec B603 B607
        ["git", "-C", str(root), *arguments],
        check=True,
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", "HOME": str(root), "GIT_CONFIG_NOSYSTEM": "1"},
    )
    return completed.stdout.strip()


class CredentialCheckWrapperTests(unittest.TestCase):
    """The wrapper's authority is the commit it names, never the working tree."""

    def setUp(self) -> None:
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = pathlib.Path(self.scratch.name) / "repository"
        self.root.mkdir()
        _git(self.root, "init", "--quiet")
        _git(self.root, "config", "user.email", "authority@example.invalid")
        _git(self.root, "config", "user.name", "Authority")
        for directory in ("ci", "tools", "policy"):
            (self.root / directory).mkdir()
        shutil.copyfile(WRAPPER, self.root / "ci" / "credential-check")
        (self.root / "tools" / "__init__.py").write_text("", encoding="utf-8")
        (self.root / "tools" / "credential_check.py").write_text(
            FAKE_CHECKER, encoding="utf-8"
        )
        (self.root / "policy" / "agent-credentials.yaml").write_text(
            "authority-declaration\\n", encoding="utf-8"
        )
        _git(self.root, "add", ".")
        _git(self.root, "commit", "--quiet", "-m", "authority")
        self.authority = _git(self.root, "rev-parse", "HEAD")
        # The candidate disagrees with its authority, and its PATH is hostile.
        (self.root / "tools" / "credential_check.py").write_text(
            "raise SystemExit(97)\\n", encoding="utf-8"
        )
        (self.root / "policy" / "agent-credentials.yaml").write_text(
            "candidate-declaration\\n", encoding="utf-8"
        )
        self.poison = pathlib.Path(self.scratch.name) / "poison"
        self.poison.mkdir()
        self.marker = pathlib.Path(self.scratch.name) / "poisoned"
        for executable in ("git", "python", "python3", "mktemp", "tar"):
            fake = self.poison / executable
            fake.write_text(
                f"#!/bin/sh\\nprintf x > {self.marker}\\nexit 99\\n", encoding="utf-8"
            )
            fake.chmod(0o755)
        self.tmp = pathlib.Path(self.scratch.name) / "tmp"
        self.tmp.mkdir()

    def _run(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        private = pathlib.Path(self.scratch.name) / "wrapper"
        shutil.copyfile(WRAPPER, private)
        private.chmod(0o700)
        environment = {
            "PATH": f"{self.poison}{os.pathsep}/usr/local/bin:/usr/bin:/bin",
            "HOME": str(self.root),
            "PYTHONPATH": str(self.root),
            "TMPDIR": str(self.tmp),
            "GIT_CONFIG_NOSYSTEM": "1",
        }
        return subprocess.run(  # nosec B603 B607
            ["sh", str(private), *arguments],
            cwd=self.root,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )

    def test_the_authority_s_checker_judges_by_the_authority_s_declaration(
        self,
    ) -> None:
        completed = self._run(self.authority, "--repository", "o/r")
        self.assertEqual(0, completed.returncode, completed.stderr)
        ran = json.loads(completed.stdout)
        self.assertEqual("authority", ran["from"])
        self.assertEqual("authority-declaration\\n", ran["policy"])
        # Run from the extracted commit, reading the checkout only for its pushes.
        self.assertNotEqual(
            str(self.root.resolve()), str(pathlib.Path(ran["cwd"]).resolve())
        )
        self.assertEqual(ran["cwd"], ran["kit"])
        worktree = ran["argv"][ran["argv"].index("--worktree") + 1]
        self.assertEqual(
            str(self.root.resolve()), str(pathlib.Path(worktree).resolve())
        )
        self.assertEqual("policy/agent-credentials.yaml", ran["argv"][-1])
        self.assertFalse(self.marker.exists(), "a poisoned executable ran")
        self.assertEqual(
            [], list(self.tmp.iterdir()), "the extracted tree was left behind"
        )

    def test_a_caller_cannot_point_the_declaration_elsewhere(self) -> None:
        completed = self._run(
            self.authority, "--repository", "o/r", "--policy", "/etc/passwd"
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertEqual(
            "authority-declaration\\n", json.loads(completed.stdout)["policy"]
        )

    def test_a_caller_cannot_point_the_push_binding_at_another_checkout(self) -> None:
        """The checkout the wrapper runs in is the one whose pushes are bound, whatever
        the caller passes (gitar on #364)."""
        completed = self._run(
            self.authority, "--repository", "o/r", "--worktree", "/elsewhere"
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        worktree = json.loads(completed.stdout)["worktree"]
        self.assertEqual(
            str(self.root.resolve()), str(pathlib.Path(worktree).resolve())
        )

    def test_an_authority_that_is_not_an_exact_commit_is_refused(self) -> None:
        for authority in ("", "main", "HEAD", "0" * 39, "g" * 40):
            with self.subTest(authority=authority):
                completed = self._run(authority, "--repository", "o/r")
                self.assertEqual(2, completed.returncode)
                self.assertIn("exact 40-character", completed.stderr)

    def test_an_authority_this_repository_does_not_hold_is_refused(self) -> None:
        completed = self._run("1" * 40, "--repository", "o/r")
        self.assertEqual(2, completed.returncode)
        self.assertIn("could not be extracted", completed.stderr)


if __name__ == "__main__":
    unittest.main()
