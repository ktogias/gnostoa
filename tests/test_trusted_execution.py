"""Tests for tools.trusted_execution: the single Python owner for isolated Git execution."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from tools.trusted_path import TRUSTED_PATH


class IsolatedGitEnvTests(unittest.TestCase):
    def test_isolated_git_env_strips_caller_git_overrides_and_sets_trusted_path(
        self,
    ) -> None:
        from tools.trusted_execution import isolated_git_env

        tmp_root = Path(tempfile.gettempdir())
        dirty_env = {
            "PATH": f"{tmp_root / 'evil'}:/usr/bin",
            "HOME": "/home/test",
            "GIT_EXEC_PATH": str(tmp_root / "evil-git-exec"),
            "GIT_DIR": str(tmp_root / "evil-git-dir"),
            "GIT_WORK_TREE": str(tmp_root / "evil-worktree"),
            "GIT_CONFIG_PARAMETERS": "'core.fsmonitor=evil'",
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "core.sshCommand",
            "GIT_CONFIG_VALUE_0": "evil",
            "GIT_REPLACE_REF_BASE": "refs/evil/",
        }

        clean = isolated_git_env(dirty_env)

        self.assertEqual(clean["PATH"], TRUSTED_PATH)
        self.assertEqual(clean["LC_ALL"], "C")
        self.assertNotIn("HOME", clean)
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
        self.assertEqual(clean["GIT_OPTIONAL_LOCKS"], "0")
        self.assertEqual(clean["GIT_ALLOW_PROTOCOL"], "")
        self.assertEqual(clean["GIT_NO_LAZY_FETCH"], "1")
        self.assertEqual(clean["GIT_CONFIG_COUNT"], "3")
        self.assertEqual(clean["GIT_CONFIG_KEY_0"], "core.hooksPath")
        self.assertEqual(clean["GIT_CONFIG_VALUE_0"], os.devnull)
        self.assertEqual(clean["GIT_CONFIG_KEY_1"], "core.fsmonitor")
        self.assertEqual(clean["GIT_CONFIG_VALUE_1"], "false")
        self.assertEqual(clean["GIT_CONFIG_KEY_2"], "core.attributesFile")
        self.assertEqual(clean["GIT_CONFIG_VALUE_2"], os.devnull)

    def test_isolated_git_env_rejects_protected_extra_overrides(self) -> None:
        from tools.trusted_execution import isolated_git_env

        for protected_key in (
            "PATH",
            "GIT_CONFIG_COUNT",
            "GIT_CONFIG_KEY_0",
            "GIT_CONFIG_VALUE_0",
            "GIT_CONFIG_KEY_1",
            "GIT_CONFIG_VALUE_1",
            "GIT_CONFIG_KEY_2",
            "GIT_CONFIG_VALUE_2",
        ):
            with self.subTest(key=protected_key), self.assertRaises(ValueError):
                isolated_git_env(extra={protected_key: "override"})

    def test_isolated_git_env_applies_extra_overrides(self) -> None:
        from tools.trusted_execution import isolated_git_env

        tmp_root = Path(tempfile.gettempdir())
        evil_path = str(tmp_root / "evil")
        repo_git_dir = str(tmp_root / "repo" / ".git")
        clean = isolated_git_env({"PATH": evil_path}, extra={"GIT_DIR": repo_git_dir})
        self.assertEqual(clean["GIT_DIR"], repo_git_dir)
        self.assertEqual(clean["PATH"], TRUSTED_PATH)

    def test_run_isolated_git_executes_git_version(self) -> None:
        from unittest import mock

        from tools.trusted_execution import run_isolated_git

        with tempfile.TemporaryDirectory() as tmpdir:
            fake_git = Path(tmpdir) / "git"
            fake_git.write_text("#!/bin/sh\necho 'fake git'\n", encoding="utf-8")
            fake_git.chmod(0o755)
            with mock.patch.dict(os.environ, {"PATH": tmpdir}, clear=False):
                result = run_isolated_git(["--version"], cwd=Path.cwd())
        self.assertEqual(result.returncode, 0)
        self.assertIn("git version", result.stdout)
        self.assertNotIn("fake git", result.stdout)

    def test_run_isolated_git_disables_repo_fsmonitor_helper(self) -> None:
        from tools.trusted_execution import run_isolated_git

        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir) / "repo"
            repo.mkdir()
            run_isolated_git(["init"], cwd=repo)
            marker = Path(tmpdir) / "pwned"
            helper = Path(tmpdir) / "helper.sh"
            helper.write_text(f"#!/bin/sh\ntouch {marker}\n", encoding="utf-8")
            helper.chmod(0o755)
            run_isolated_git(["config", "core.fsmonitor", str(helper)], cwd=repo)

            result = run_isolated_git(["status"], cwd=repo)
            self.assertEqual(result.returncode, 0)
            self.assertFalse(marker.exists())

    def test_run_isolated_git_routes_through_bounded_process_drain(self) -> None:
        from unittest import mock

        from tools import bounded_process
        from tools.trusted_execution import run_isolated_git

        with mock.patch(
            "tools.trusted_execution.bounded_process.drain",
            wraps=bounded_process.drain,
        ) as drain_spy:
            result = run_isolated_git(["--version"], cwd=Path.cwd(), timeout=15.0)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(drain_spy.call_count, 1)
        self.assertIn("deadline", drain_spy.call_args.kwargs)


if __name__ == "__main__":
    unittest.main()
