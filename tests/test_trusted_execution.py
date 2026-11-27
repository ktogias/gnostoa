"""Tests for tools.trusted_execution: the single Python owner for isolated Git execution."""

from __future__ import annotations

import os
import unittest
from pathlib import Path

from tools.trusted_path import TRUSTED_PATH


class IsolatedGitEnvTests(unittest.TestCase):
    def test_isolated_git_env_strips_caller_git_overrides_and_sets_trusted_path(
        self,
    ) -> None:
        from tools.trusted_execution import isolated_git_env

        dirty_env = {
            "PATH": "/tmp/evil:/usr/bin",
            "HOME": "/home/test",
            "GIT_EXEC_PATH": "/tmp/evil-git-exec",
            "GIT_DIR": "/tmp/evil-git-dir",
            "GIT_WORK_TREE": "/tmp/evil-worktree",
            "GIT_CONFIG_PARAMETERS": "'core.fsmonitor=evil'",
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "core.sshCommand",
            "GIT_CONFIG_VALUE_0": "evil",
            "GIT_REPLACE_REF_BASE": "refs/evil/",
        }

        clean = isolated_git_env(dirty_env)

        self.assertEqual(clean["PATH"], TRUSTED_PATH)
        self.assertEqual(clean["HOME"], "/home/test")
        self.assertNotIn("GIT_EXEC_PATH", clean)
        self.assertNotIn("GIT_DIR", clean)
        self.assertNotIn("GIT_WORK_TREE", clean)
        self.assertNotIn("GIT_CONFIG_PARAMETERS", clean)
        self.assertNotIn("GIT_REPLACE_REF_BASE", clean)
        self.assertEqual(clean["GIT_CONFIG_GLOBAL"], os.devnull)
        self.assertEqual(clean["GIT_CONFIG_SYSTEM"], os.devnull)
        self.assertEqual(clean["GIT_CONFIG_NOSYSTEM"], "1")
        self.assertEqual(clean["GIT_ATTR_NOSYSTEM"], "1")
        self.assertEqual(clean["GIT_NO_REPLACE_OBJECTS"], "1")
        self.assertEqual(clean["GIT_TERMINAL_PROMPT"], "0")
        self.assertEqual(clean["GIT_CONFIG_COUNT"], "1")
        self.assertEqual(clean["GIT_CONFIG_KEY_0"], "core.hooksPath")
        self.assertEqual(clean["GIT_CONFIG_VALUE_0"], os.devnull)

    def test_isolated_git_env_applies_extra_overrides(self) -> None:
        from tools.trusted_execution import isolated_git_env

        clean = isolated_git_env(
            {"PATH": "/tmp/evil"}, extra={"GIT_DIR": "/tmp/repo/.git"}
        )
        self.assertEqual(clean["GIT_DIR"], "/tmp/repo/.git")
        self.assertEqual(clean["PATH"], TRUSTED_PATH)

    def test_run_isolated_git_executes_git_version(self) -> None:
        from tools.trusted_execution import run_isolated_git

        result = run_isolated_git(["--version"], cwd=Path.cwd())
        self.assertEqual(result.returncode, 0)
        self.assertIn("git version", result.stdout)


if __name__ == "__main__":
    unittest.main()
