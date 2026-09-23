from __future__ import annotations

import hashlib
import json
import os
import re
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
SH: str = shutil.which("sh") or ""
if not GIT or not SH:
    raise RuntimeError("git and sh are required for candidate preparation tests")

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
_GIT_CALLER_OVERRIDE_ENVIRONMENT_VARIABLES = (
    "GIT_CONFIG",
    "GIT_CONFIG_PARAMETERS",
    "GIT_CONFIG_GLOBAL",
    "GIT_CONFIG_SYSTEM",
    "GIT_CONFIG_NOSYSTEM",
    "GIT_ATTR_NOSYSTEM",
    "GIT_EXTERNAL_DIFF",
    "GIT_TEMPLATE_DIR",
)


def _test_env() -> dict[str, str]:
    env = dict(os.environ)
    for name in tuple(env):
        if (
            name in _GIT_ENVIRONMENT_VARIABLES
            or name in _GIT_CALLER_OVERRIDE_ENVIRONMENT_VARIABLES
            or name == "GIT_CONFIG_COUNT"
            or name.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_"))
        ):
            env.pop(name, None)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    return env


class CandidatePreparationContractTests(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        home = Path(tempfile.mkdtemp(prefix="gnostoa-candidate-test-home-"))
        self.addCleanup(shutil.rmtree, home, ignore_errors=True)
        environment = patch.dict(
            os.environ,
            {
                "HOME": str(home),
                "XDG_CONFIG_HOME": str(home / ".config"),
            },
            clear=False,
        )
        environment.start()
        self.addCleanup(environment.stop)

    @staticmethod
    def _git(root: Path, *arguments: str) -> str:
        completed = subprocess.run(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
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
        (root / ".gitignore").write_text(
            "ignored-helper.txt\n",
            encoding="utf-8",
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
            "#!/bin/sh\n"
            "set -eu\n"
            'test "$1" = "fast"\n'
            'case "${GNOSTOA_TEST_FOCUSED_MODE:-pass}" in\n'
            "  mutate) printf 'changed\\n' > candidate.py ;;\n"
            "  mutate-skip-worktree)\n"
            "    printf 'changed\\n' > candidate.py\n"
            "    git update-index --skip-worktree candidate.py\n"
            "    ;;\n"
            "  fail) printf 'focused failure detail\\n'; exit 7 ;;\n"
            "  ignored-helper) test -f ignored-helper.txt ;;\n"
            "  toolkit-root)\n"
            '    test "${KNOWLEDGE_KIT_ROOT:-}" = "$PWD"\n'
            '    test "${KNOWLEDGE_KIT_REVISION:-}" = "development"\n'
            "    ;;\n"
            "  nested-git)\n"
            '    nested="$(mktemp -d)"\n'
            "    trap 'rm -rf \"$nested\"' EXIT\n"
            '    git -C "$nested" init --quiet\n'
            '    git -C "$nested" config user.email nested@example.invalid\n'
            "    git -C \"$nested\" config user.name 'Nested Test'\n"
            "    printf 'nested\\n' > \"$nested/nested.txt\"\n"
            '    git -C "$nested" add nested.txt\n'
            '    git -C "$nested" commit --quiet -m baseline\n'
            "    ;;\n"
            "  pass) grep -q '^value = 1$' candidate.py ;;\n"
            "  *) exit 8 ;;\n"
            "esac\n",
            encoding="utf-8",
        )
        verify.chmod(0o755)
        wrapper = root / "ci" / "prepare-candidate"
        wrapper.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        wrapper.chmod(0o755)
        (root / "tools").mkdir()
        (root / "tools" / "candidate_prepare.py").write_text(
            "# parent preparation authority\n",
            encoding="utf-8",
        )
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
            self.assertEqual(
                "value=1\n",
                (root / "candidate.py").read_text(encoding="utf-8"),
            )
            self.assertEqual(
                "value = 1",
                self._git(root, "show", f"{payload['prepared_tree']}:candidate.py"),
            )
            self.assertRegex(payload["style_sha256"], r"^sha256:[0-9a-f]{64}$")
            self.assertRegex(payload["verify_sha256"], r"^sha256:[0-9a-f]{64}$")
            self.assertRegex(
                payload["retention_ref"],
                (
                    rf"^refs/gnostoa/prepared/{parent}/"
                    rf"{payload['prepared_tree']}/[0-9a-f]{{32}}$"
                ),
            )
            self.assertEqual(
                payload["prepared_tree"],
                self._git(root, "rev-parse", payload["retention_ref"]),
            )
            self.assertTrue(receipt.is_file())
            self.assertEqual(
                payload,
                candidate_prepare.verify_receipt(
                    receipt,
                    parent,
                    payload["prepared_tree"],
                    payload["receipt_sha256"],
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
                candidate_prepare.verify_receipt(
                    receipt,
                    parent,
                    "0" * 40,
                    payload["receipt_sha256"],
                )
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
                    payload["receipt_sha256"],
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

    def test_prepare_rejects_candidate_modified_preparation_authority(self) -> None:
        for authority in (
            "ci/prepare-candidate",
            "ci/style",
            "ci/verify",
            "tools/candidate_prepare.py",
        ):
            with (
                self.subTest(authority=authority),
                tempfile.TemporaryDirectory() as directory,
            ):
                root = Path(directory)
                parent = self._repository(root)
                (root / "candidate.py").write_text("value=1\n", encoding="utf-8")
                authority_path = root / authority
                authority_path.write_text(
                    authority_path.read_text(encoding="utf-8")
                    + "\n# candidate authority override\n",
                    encoding="utf-8",
                )
                receipt = self._receipt()
                with self.assertRaisesRegex(
                    candidate_prepare.PrepareError,
                    rf"candidate modifies preparation authority: {re.escape(authority)}",
                ):
                    self._prepare(root, parent, receipt)
                self.assertFalse(receipt.exists())

    def test_prepare_rejects_candidate_ruff_configuration_authority(self) -> None:
        for configuration in (
            "pyproject.toml",
            "ruff.toml",
            ".ruff.toml",
            "nested/pyproject.toml",
        ):
            with (
                self.subTest(configuration=configuration),
                tempfile.TemporaryDirectory() as directory,
            ):
                root = Path(directory)
                parent = self._repository(root)
                (root / "candidate.py").write_text("value=1\n", encoding="utf-8")
                config_path = root / configuration
                config_path.parent.mkdir(parents=True, exist_ok=True)
                config_path.write_text(
                    "[tool.ruff]\nline-length = 100\n"
                    if config_path.name == "pyproject.toml"
                    else "line-length = 100\n",
                    encoding="utf-8",
                )
                receipt = self._receipt()
                with self.assertRaisesRegex(
                    candidate_prepare.PrepareError,
                    rf"candidate modifies preparation authority: {re.escape(configuration)}",
                ):
                    self._prepare(root, parent, receipt)
                self.assertFalse(receipt.exists())

    def test_prepare_rejects_source_candidate_change_during_capture(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = self._repository(root)
            candidate = root / "candidate.py"
            candidate.write_text("value=1\n", encoding="utf-8")
            receipt = self._receipt()
            # skipcq: PYL-W0212 -- intentional white-box capture-race regression
            original_stage = candidate_prepare._stage_candidate
            calls = 0

            def stage_then_mutate(
                repository_root: Path,
                exact_parent: str,
                git_dir: Path,
            ) -> tuple[str, list[str]]:
                nonlocal calls
                result = original_stage(repository_root, exact_parent, git_dir)
                calls += 1
                if calls == 1:
                    candidate.write_text("value=2\n", encoding="utf-8")
                return result

            with (
                patch.object(
                    candidate_prepare,
                    "_stage_candidate",
                    side_effect=stage_then_mutate,
                ),
                self.assertRaisesRegex(
                    candidate_prepare.PrepareError,
                    "source candidate changed during capture",
                ),
            ):
                self._prepare(root, parent, receipt)
            self.assertFalse(receipt.exists())

    def test_trusted_python_env_blocks_candidate_ruff_shadow(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "ruff.py").write_text(
                "raise SystemExit(97)\n",
                encoding="utf-8",
            )
            probe = root / "probe-style"
            probe.write_text(
                "#!/bin/sh\n"
                "set -eu\n"
                "python -c 'import importlib.util, pathlib; "
                'spec = importlib.util.find_spec("ruff"); '
                "assert spec is None or spec.origin is None or "
                "pathlib.Path(spec.origin).resolve() != "
                'pathlib.Path("ruff.py").resolve()\'\n',
                encoding="utf-8",
            )
            probe.chmod(0o755)
            with patch.dict(
                os.environ,
                {"PYTHONPATH": str(root)},
                clear=False,
            ):
                # skipcq: PYL-W0212 -- intentional white-box trusted-env regression
                trusted_env = candidate_prepare._trusted_python_env()
                # skipcq: PYL-W0212 -- intentional white-box subprocess regression
                completed = candidate_prepare._run(
                    [str(probe)],
                    cwd=root,
                    env=trusted_env,
                    check=False,
                )
            self.assertEqual(0, completed.returncode, completed.stderr)

    def test_trusted_python_env_keeps_virtualenv_bin_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            venv_bin = root / "venv" / "bin"
            venv_bin.mkdir(parents=True)
            python_link = venv_bin / "python"
            python_link.symlink_to(Path(candidate_prepare.sys.executable))
            with patch.object(
                candidate_prepare.sys,
                "executable",
                str(python_link),
            ):
                # skipcq: PYL-W0212 -- intentional white-box venv-path regression
                env = candidate_prepare._trusted_python_env()
            self.assertEqual(
                str(venv_bin),
                env["PATH"].split(os.pathsep)[0],
            )

    def test_trusted_python_env_includes_git_executable_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            git_dir = root / "custom-git-bin"
            git_dir.mkdir()
            git_executable = git_dir / "git"
            git_executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            git_executable.chmod(0o755)
            with patch.object(candidate_prepare, "_GIT", str(git_executable)):
                # skipcq: PYL-W0212 -- intentional white-box trusted-env regression
                env = candidate_prepare._trusted_python_env()
            self.assertIn(str(git_dir), env["PATH"].split(os.pathsep))

    def test_focused_verification_env_scrubs_inherited_pythonpath(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "candidate"
            outside = Path(directory) / "outside"
            root.mkdir()
            outside.mkdir()
            (root / "candidate_visible.py").write_text(
                "VALUE = 1\n",
                encoding="utf-8",
            )
            (outside / "outside_shadow.py").write_text(
                "raise SystemExit(97)\n",
                encoding="utf-8",
            )
            with patch.dict(
                os.environ,
                {"PYTHONPATH": str(outside)},
                clear=False,
            ):
                # skipcq: PYL-W0212 -- intentional white-box focused-env regression
                env = candidate_prepare._focused_verification_env()
                # skipcq: PYL-W0212 -- intentional white-box subprocess regression
                completed = candidate_prepare._run(
                    [
                        candidate_prepare.sys.executable,
                        "-c",
                        (
                            "import importlib.util; "
                            "assert importlib.util.find_spec('candidate_visible') "
                            "is not None; "
                            "assert importlib.util.find_spec('outside_shadow') "
                            "is None"
                        ),
                    ],
                    cwd=root,
                    env=env,
                    check=False,
                )
            self.assertEqual(0, completed.returncode, completed.stderr)

    def test_focused_verification_env_scrubs_preparation_git_routing(
        self,
    ) -> None:
        # skipcq: PYL-W0212 -- intentional white-box environment regression
        seeded = candidate_prepare._base_env()
        for name in _GIT_ENVIRONMENT_VARIABLES:
            seeded[name] = f"gnostoa-sentinel-{name.lower()}"
        # skipcq: PYL-W0212 -- intentional white-box environment regression
        env = candidate_prepare._focused_verification_env(seeded)
        for name in _GIT_ENVIRONMENT_VARIABLES:
            self.assertNotIn(name, env)
        self.assertEqual(os.devnull, env["GIT_CONFIG_GLOBAL"])
        self.assertEqual(os.devnull, env["GIT_CONFIG_SYSTEM"])
        self.assertEqual("1", env["GIT_CONFIG_NOSYSTEM"])

    def test_prepare_focused_verification_can_create_nested_git_repository(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = self._repository(root)
            (root / "candidate.py").write_text("value=1\n", encoding="utf-8")
            receipt = self._receipt()
            with patch.dict(
                os.environ,
                {"GNOSTOA_TEST_FOCUSED_MODE": "nested-git"},
                clear=False,
            ):
                payload = self._prepare(root, parent, receipt)
            self.assertEqual(0, payload["checks"]["focused_verification"])
            self.assertTrue(receipt.is_file())

    def test_focused_verification_uses_prepared_toolkit_root_and_source_cli(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = self._repository(root)
            (root / "candidate.py").write_text("value=1\n", encoding="utf-8")
            receipt = self._receipt()
            with patch.dict(
                os.environ,
                {
                    "GNOSTOA_TEST_FOCUSED_MODE": "toolkit-root",
                    "KNOWLEDGE_KIT_ROOT": "/caller/source",
                    "KNOWLEDGE_KIT_REVISION": "caller-revision",
                },
                clear=False,
            ):
                payload = self._prepare(root, parent, receipt)
            self.assertEqual(0, payload["checks"]["focused_verification"])

        with (
            tempfile.TemporaryDirectory() as directory,
            tempfile.TemporaryDirectory() as metadata_directory,
        ):
            workspace = Path(directory)
            tools_dir = workspace / "tools"
            tools_dir.mkdir()
            (tools_dir / "__init__.py").write_text("", encoding="utf-8")
            (tools_dir / "cli.py").write_text(
                "print('prepared-source-cli')\n",
                encoding="utf-8",
            )
            git_dir = Path(metadata_directory) / "git"
            git_dir.mkdir()
            # skipcq: PYL-W0212 -- intentional white-box focused-tooling regression
            tooling = candidate_prepare._focused_tooling_directory(git_dir)
            # skipcq: PYL-W0212 -- intentional white-box focused-env regression
            env = candidate_prepare._focused_verification_env(
                candidate_prepare._base_env(),
                workspace=workspace,
                tooling=tooling,
            )
            # skipcq: PYL-W0212 -- intentional white-box subprocess regression
            completed = candidate_prepare._run(
                [str(tooling / "knowledge"), "--help"],
                cwd=workspace,
                env=env,
                check=False,
            )
            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertEqual(
                "prepared-source-cli",
                completed.stdout.decode("utf-8").strip(),
            )

    def test_focused_runner_bounds_output_and_times_out(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            # skipcq: PYL-W0212 -- intentional white-box bounded-runner regression
            completed = candidate_prepare._run_focused(
                [
                    candidate_prepare.sys.executable,
                    "-c",
                    (
                        "import sys; "
                        "sys.stdout.write('x' * 10000); "
                        "sys.stderr.write('y' * 10000)"
                    ),
                ],
                cwd=root,
                env=_test_env(),
                timeout_seconds=5,
                max_output_bytes=128,
            )
            self.assertEqual(0, completed.returncode)
            self.assertEqual(128, len(completed.stdout))
            self.assertEqual(128, len(completed.stderr))
            self.assertEqual(b"x" * 128, completed.stdout)
            self.assertEqual(b"y" * 128, completed.stderr)

            with self.assertRaisesRegex(
                candidate_prepare.PrepareError,
                "focused verification timed out",
            ):
                # skipcq: PYL-W0212 -- intentional white-box timeout regression
                candidate_prepare._run_focused(
                    [
                        candidate_prepare.sys.executable,
                        "-c",
                        "import time; time.sleep(5)",
                    ],
                    cwd=root,
                    env=_test_env(),
                    timeout_seconds=0.1,
                    max_output_bytes=128,
                )

    def test_focused_success_cleans_process_group(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(
                candidate_prepare,
                "_terminate_focused_process",
            ) as terminate:
                # skipcq: PYL-W0212 -- intentional white-box process cleanup regression
                completed = candidate_prepare._run_focused(
                    [
                        candidate_prepare.sys.executable,
                        "-c",
                        "print('ok')",
                    ],
                    cwd=root,
                    env=_test_env(),
                    timeout_seconds=5,
                    max_output_bytes=128,
                )
            self.assertEqual(0, completed.returncode)
            self.assertGreaterEqual(terminate.call_count, 1)

    def test_focused_timeout_kills_group_after_leader_exit(self) -> None:
        class CompletedLeader:
            pid = 424242

            @staticmethod
            def poll() -> int:
                return 0

            @staticmethod
            def wait(timeout: float | None = None) -> int:
                del timeout
                return 0

        with patch.object(candidate_prepare.os, "killpg") as killpg:
            # skipcq: PYL-W0212 -- intentional white-box timeout cleanup regression
            candidate_prepare._terminate_focused_process(CompletedLeader())  # type: ignore[arg-type]
        killpg.assert_any_call(424242, candidate_prepare.signal.SIGTERM)
        killpg.assert_any_call(424242, candidate_prepare.signal.SIGKILL)

    def test_prepare_does_not_admit_ignored_source_worktree_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = self._repository(root)
            (root / "candidate.py").write_text("value=1\n", encoding="utf-8")
            (root / "ignored-helper.txt").write_text("source-only\n", encoding="utf-8")
            receipt = self._receipt()
            with (
                patch.dict(
                    os.environ,
                    {"GNOSTOA_TEST_FOCUSED_MODE": "ignored-helper"},
                    clear=False,
                ),
                self.assertRaisesRegex(
                    candidate_prepare.PrepareError,
                    r"focused verification failed \(1\)",
                ),
            ):
                self._prepare(root, parent, receipt)
            self.assertFalse(receipt.exists())

    def test_prepare_rejects_candidate_symlink_before_verification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = self._repository(root)
            outside = Path(directory).parent / f"{root.name}-outside.py"
            outside.write_text("value = 1\n", encoding="utf-8")
            self.addCleanup(outside.unlink, missing_ok=True)
            (root / "candidate.py").symlink_to(outside)
            receipt = self._receipt()
            with self.assertRaisesRegex(
                candidate_prepare.PrepareError,
                "candidate symlinks are unsupported: candidate.py",
            ):
                self._prepare(root, parent, receipt)
            self.assertFalse(receipt.exists())

    def test_prepare_rejects_skip_worktree_hidden_verifier_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = self._repository(root)
            (root / "candidate.py").write_text("value=1\n", encoding="utf-8")
            receipt = self._receipt()
            with (
                patch.dict(
                    os.environ,
                    {"GNOSTOA_TEST_FOCUSED_MODE": "mutate-skip-worktree"},
                    clear=False,
                ),
                self.assertRaisesRegex(
                    candidate_prepare.PrepareError,
                    "focused verification mutated candidate",
                ),
            ):
                self._prepare(root, parent, receipt)
            self.assertFalse(receipt.exists())

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
                    r"focused verification failed \(7\): focused failure detail",
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

    def test_receipt_writer_never_replaces_existing_evidence(self) -> None:
        receipt = self._receipt()
        receipt.write_text("original evidence\n", encoding="utf-8")
        with self.assertRaisesRegex(
            candidate_prepare.PrepareError,
            "receipt path already exists",
        ):
            # skipcq: PYL-W0212 -- intentional white-box atomic-publication regression
            candidate_prepare._write_receipt(
                receipt,
                {"schema": candidate_prepare.RECEIPT_SCHEMA},
            )
        self.assertEqual(
            "original evidence\n",
            receipt.read_text(encoding="utf-8"),
        )

    def test_prepare_rejects_existing_receipt_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = self._repository(root)
            (root / "candidate.py").write_text("value=1\n", encoding="utf-8")
            receipt = self._receipt()
            receipt.write_text("original evidence\n", encoding="utf-8")
            with self.assertRaisesRegex(
                candidate_prepare.PrepareError,
                "receipt path already exists",
            ):
                self._prepare(root, parent, receipt)
            self.assertEqual(
                "original evidence\n",
                receipt.read_text(encoding="utf-8"),
            )

    def test_receipt_verification_rejects_recomputed_untrusted_identity(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = self._repository(root)
            (root / "candidate.py").write_text("value=1\n", encoding="utf-8")
            receipt = self._receipt()
            payload = self._prepare(root, parent, receipt)
            trusted_identity = payload["receipt_sha256"]

            document = json.loads(receipt.read_text(encoding="utf-8"))
            document["changed_paths"] = ["forged.py"]
            forged_payload = {
                key: value for key, value in document.items() if key != "receipt_sha256"
            }
            encoded = json.dumps(
                forged_payload,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            ).encode("utf-8")
            document["receipt_sha256"] = "sha256:" + hashlib.sha256(encoded).hexdigest()
            receipt.write_text(json.dumps(document), encoding="utf-8")

            with self.assertRaisesRegex(
                candidate_prepare.PrepareError,
                "trusted receipt identity mismatch",
            ):
                candidate_prepare.verify_receipt(
                    receipt,
                    parent,
                    payload["prepared_tree"],
                    trusted_identity,
                )

    def test_receipt_verification_rejects_malformed_changed_paths_fail_closed(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = self._repository(root)
            (root / "candidate.py").write_text("value=1\n", encoding="utf-8")
            receipt = self._receipt()
            payload = self._prepare(root, parent, receipt)

            document = json.loads(receipt.read_text(encoding="utf-8"))
            document["changed_paths"] = [["unhashable"]]
            forged_payload = {
                key: value for key, value in document.items() if key != "receipt_sha256"
            }
            encoded = json.dumps(
                forged_payload,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            ).encode("utf-8")
            document["receipt_sha256"] = "sha256:" + hashlib.sha256(encoded).hexdigest()
            receipt.write_text(json.dumps(document), encoding="utf-8")

            with self.assertRaisesRegex(
                candidate_prepare.PrepareError,
                "receipt changed paths are invalid",
            ):
                candidate_prepare.verify_receipt(
                    receipt,
                    parent,
                    payload["prepared_tree"],
                    document["receipt_sha256"],
                )

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
                    payload["receipt_sha256"],
                ),
            )

    def test_prepared_tree_survives_gc_until_explicit_release(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = self._repository(root)
            (root / "candidate.py").write_text("value=1\n", encoding="utf-8")
            receipt = self._receipt()
            payload = self._prepare(root, parent, receipt)
            retention_ref = payload["retention_ref"]

            self._git(root, "reflog", "expire", "--expire=now", "--all")
            self._git(root, "gc", "--prune=now")
            self._git(root, "cat-file", "-e", payload["prepared_tree"])
            self.assertEqual(
                payload["prepared_tree"],
                self._git(root, "rev-parse", retention_ref),
            )

            with patch.object(
                candidate_prepare,
                "_repository_root",
                return_value=root,
            ):
                released = candidate_prepare.release_receipt(
                    receipt,
                    parent,
                    payload["prepared_tree"],
                    payload["receipt_sha256"],
                )
            self.assertTrue(released["released"])
            ref = subprocess.run(  # nosemgrep  # nosec B603
                [GIT, "show-ref", "--verify", retention_ref],
                cwd=root,
                env=_test_env(),
                check=False,
                shell=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(0, ref.returncode)

    def test_same_tree_receipts_hold_independent_retention_refs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = self._repository(root)
            (root / "candidate.py").write_text("value=1\n", encoding="utf-8")
            first_receipt = self._receipt()
            second_receipt = self._receipt()
            first = self._prepare(root, parent, first_receipt)
            second = self._prepare(root, parent, second_receipt)

            self.assertEqual(first["prepared_tree"], second["prepared_tree"])
            self.assertNotEqual(first["retention_ref"], second["retention_ref"])

            with patch.object(
                candidate_prepare,
                "_repository_root",
                return_value=root,
            ):
                candidate_prepare.release_receipt(
                    first_receipt,
                    parent,
                    first["prepared_tree"],
                    first["receipt_sha256"],
                )
            self.assertEqual(
                second["prepared_tree"],
                self._git(root, "rev-parse", second["retention_ref"]),
            )
            self._git(root, "reflog", "expire", "--expire=now", "--all")
            self._git(root, "gc", "--prune=now")
            self._git(root, "cat-file", "-e", second["prepared_tree"])

            with patch.object(
                candidate_prepare,
                "_repository_root",
                return_value=root,
            ):
                candidate_prepare.release_receipt(
                    second_receipt,
                    parent,
                    second["prepared_tree"],
                    second["receipt_sha256"],
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
                        "--receipt-sha256",
                        payload["receipt_sha256"],
                    ]
                ),
            )

    def test_cli_release_consumes_exact_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = self._repository(root)
            (root / "candidate.py").write_text("value=1\n", encoding="utf-8")
            receipt = self._receipt()
            payload = self._prepare(root, parent, receipt)
            with patch.object(
                candidate_prepare,
                "_repository_root",
                return_value=root,
            ):
                result = candidate_prepare.main(
                    [
                        "release",
                        "--parent",
                        parent,
                        "--tree",
                        payload["prepared_tree"],
                        "--receipt",
                        str(receipt),
                        "--receipt-sha256",
                        payload["receipt_sha256"],
                    ]
                )
            self.assertEqual(0, result)

    def test_prepare_scrubs_inherited_git_repository_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = self._repository(root)
            (root / "candidate.py").write_text("value=1\n", encoding="utf-8")
            (root / ".gitattributes").write_text(
                "candidate.py filter=poison\n",
                encoding="utf-8",
            )
            receipt = self._receipt()
            poisoned = {
                name: "poisoned-by-caller" for name in _GIT_ENVIRONMENT_VARIABLES
            }
            poisoned.update(
                {
                    "GIT_CONFIG_COUNT": "1",
                    "GIT_CONFIG_PARAMETERS": "'filter.poison.clean'='false'",
                    "GIT_CONFIG_KEY_0": "filter.poison.clean",
                    "GIT_CONFIG_VALUE_0": "false",
                    "GIT_CONFIG_KEY_7": "filter.extra.clean",
                    "GIT_CONFIG_VALUE_7": "false",
                    "GIT_EXTERNAL_DIFF": "false",
                }
            )
            with patch.dict(os.environ, poisoned, clear=False):
                payload = self._prepare(root, parent, receipt)
            self.assertEqual(parent, payload["parent_commit"])
            self.assertEqual("PRE_CANDIDATE_RUFF_CATCH", payload["metric_event"])

    def test_prepare_isolates_source_config_mutated_after_safety_check(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = self._repository(root)
            (root / "candidate.py").write_text("value=1\n", encoding="utf-8")
            (root / ".gitattributes").write_text(
                "candidate.py filter=poison\n",
                encoding="utf-8",
            )
            receipt = self._receipt()
            # skipcq: PYL-W0212 -- intentional white-box config-race regression
            original = candidate_prepare._assert_safe_repository_git_configuration

            def mutate_after_inspection(repository_root: Path) -> None:
                original(repository_root)
                self._git(
                    repository_root,
                    "config",
                    "filter.poison.clean",
                    "false",
                )

            with patch.object(
                candidate_prepare,
                "_assert_safe_repository_git_configuration",
                side_effect=mutate_after_inspection,
            ):
                payload = self._prepare(root, parent, receipt)

            self.assertEqual(parent, payload["parent_commit"])
            self.assertEqual(
                "value = 1",
                self._git(root, "show", f"{payload['prepared_tree']}:candidate.py"),
            )

    def test_prepare_snapshots_source_info_exclude(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = self._repository(root)
            exclude = Path(self._git(root, "rev-parse", "--git-path", "info/exclude"))
            if not exclude.is_absolute():
                exclude = root / exclude
            exclude.parent.mkdir(parents=True, exist_ok=True)
            exclude.write_text("local-secret.txt\n", encoding="utf-8")
            (root / "local-secret.txt").write_text(
                "do not publish\n",
                encoding="utf-8",
            )
            (root / "candidate.py").write_text("value=1\n", encoding="utf-8")
            receipt = self._receipt()

            payload = self._prepare(root, parent, receipt)

            self.assertEqual(["candidate.py"], payload["changed_paths"])
            with self.assertRaises(subprocess.CalledProcessError):
                self._git(
                    root,
                    "show",
                    f"{payload['prepared_tree']}:local-secret.txt",
                )

    def test_prepare_snapshots_caller_global_excludes_file(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            tempfile.TemporaryDirectory() as home_directory,
        ):
            root = Path(directory)
            parent = self._repository(root)
            home = Path(home_directory)
            global_exclude = home / "custom-ignore"
            global_exclude.write_text("global-secret.txt\n", encoding="utf-8")
            (home / ".gitconfig").write_text(
                f"[core]\n\texcludesFile = {global_exclude}\n",
                encoding="utf-8",
            )
            (root / "global-secret.txt").write_text(
                "do not publish\n",
                encoding="utf-8",
            )
            (root / "candidate.py").write_text("value=1\n", encoding="utf-8")
            receipt = self._receipt()

            with patch.dict(
                os.environ,
                {
                    "HOME": str(home),
                    "XDG_CONFIG_HOME": str(home / ".config"),
                },
                clear=False,
            ):
                self.assertEqual(
                    "global-secret.txt",
                    self._git(root, "check-ignore", "global-secret.txt"),
                )
                payload = self._prepare(root, parent, receipt)

            self.assertEqual(["candidate.py"], payload["changed_paths"])
            with self.assertRaises(subprocess.CalledProcessError):
                self._git(
                    root,
                    "show",
                    f"{payload['prepared_tree']}:global-secret.txt",
                )

    def test_prepare_ignores_caller_git_template_directory(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            tempfile.TemporaryDirectory() as template_directory,
        ):
            root = Path(directory)
            parent = self._repository(root)
            template_root = Path(template_directory)
            template = template_root / "template"
            template.mkdir()
            marker_path = template_root / "filter-executed"
            filter_script = template_root / "poison-filter"
            filter_script.write_text(
                f"#!/bin/sh\nprintf executed > {marker_path}\ncat\n",
                encoding="utf-8",
            )
            filter_script.chmod(0o755)
            (template / "config").write_text(
                f'[filter "poison"]\n\tclean = {filter_script}\n\trequired = true\n',
                encoding="utf-8",
            )
            (root / ".gitattributes").write_text(
                "candidate.py filter=poison\n",
                encoding="utf-8",
            )
            (root / "candidate.py").write_text("value=1\n", encoding="utf-8")
            receipt = self._receipt()

            with patch.dict(
                os.environ,
                {"GIT_TEMPLATE_DIR": str(template)},
                clear=False,
            ):
                payload = self._prepare(root, parent, receipt)

            self.assertFalse(marker_path.exists())
            self.assertIn("candidate.py", payload["changed_paths"])

    def test_prepare_rejects_repository_local_git_execution_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = self._repository(root)
            self._git(root, "config", "filter.poison.clean", "cat")
            (root / "candidate.py").write_text("value=1\n", encoding="utf-8")
            receipt = self._receipt()
            with self.assertRaisesRegex(
                candidate_prepare.PrepareError,
                "repository-local Git execution configuration is unsupported",
            ):
                self._prepare(root, parent, receipt)
            self.assertFalse(receipt.exists())

    def test_prepare_rejects_repository_local_git_attributes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = self._repository(root)
            attributes = Path(
                self._git(root, "rev-parse", "--git-path", "info/attributes")
            )
            if not attributes.is_absolute():
                attributes = root / attributes
            attributes.parent.mkdir(parents=True, exist_ok=True)
            attributes.write_text("*.py text\n", encoding="utf-8")
            (root / "candidate.py").write_text("value=1\n", encoding="utf-8")
            receipt = self._receipt()
            with self.assertRaisesRegex(
                candidate_prepare.PrepareError,
                "repository-local Git attributes are unsupported",
            ):
                self._prepare(root, parent, receipt)
            self.assertFalse(receipt.exists())

    def test_cli_prepare_uses_allowlisted_focused_profile(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = self._repository(root)
            (root / "candidate.py").write_text("value=1\n", encoding="utf-8")
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

    def test_cli_rejects_abbreviated_trusted_python_option(self) -> None:
        # skipcq: PYL-W0212 -- intentional white-box CLI parsing regression
        parser = candidate_prepare._parser()
        with self.assertRaises(SystemExit) as raised:
            parser.parse_args(
                [
                    "prepare",
                    "--parent",
                    "0" * 40,
                    "--receipt",
                    "receipt.json",
                    "--focused-profile",
                    "fast",
                    "--trusted-py",
                    "/usr/bin/python3",
                ]
            )
        self.assertEqual(2, raised.exception.code)

    def test_parent_wrapper_executes_parent_preparation_authority(self) -> None:
        wrapper = ROOT / "ci" / "prepare-candidate"
        self.assertTrue(wrapper.is_file())
        wrapper_text = wrapper.read_text(encoding="utf-8")
        self.assertNotIn("python -m tools.candidate_prepare", wrapper_text)
        self.assertIn('show "${parent}:tools/candidate_prepare.py"', wrapper_text)
        self.assertIn('"$python_executable" -I "$temporary"', wrapper_text)
        self.assertNotIn('exec "$python_executable"', wrapper_text)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._git(root, "init", "--quiet")
            self._git(root, "config", "user.email", "candidate@example.invalid")
            self._git(root, "config", "user.name", "Candidate Test")
            (root / "ci").mkdir()
            (root / "tools").mkdir()
            (root / "ci" / "prepare-candidate").write_text(
                wrapper_text,
                encoding="utf-8",
            )
            (root / "tools" / "candidate_prepare.py").write_text(
                "import importlib.util, sys\n"
                "assert importlib.util.find_spec('candidate_shadow') is None\n"
                "print('trusted-parent', sys.argv[1])\n",
                encoding="utf-8",
            )
            self._git(root, "add", ".")
            self._git(root, "commit", "--quiet", "-m", "trusted parent")
            parent = self._git(root, "rev-parse", "HEAD")

            (root / "tools" / "candidate_prepare.py").write_text(
                "raise SystemExit(97)\n",
                encoding="utf-8",
            )
            (root / "candidate_shadow.py").write_text(
                "raise SystemExit(98)\n",
                encoding="utf-8",
            )
            poison_bin = root / "poison-bin"
            poison_bin.mkdir()
            marker = root / "poisoned-bootstrap"
            for executable in ("git", "python", "python3", "mktemp"):
                fake = poison_bin / executable
                fake.write_text(
                    f"#!/bin/sh\nprintf poisoned > {marker}\nexit 99\n",
                    encoding="utf-8",
                )
                fake.chmod(0o755)

            trusted_wrapper = self._git(
                root,
                "show",
                f"{parent}:ci/prepare-candidate",
            )
            bootstrap_tmp = root / "bootstrap-tmp"
            bootstrap_tmp.mkdir()
            environment = _test_env()
            environment["PYTHONPATH"] = str(root)
            environment["PATH"] = str(poison_bin) + os.pathsep + environment["PATH"]
            environment["TMPDIR"] = str(bootstrap_tmp)
            completed = subprocess.run(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
                [  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-tainted-env-args.dangerous-subprocess-use-tainted-env-args
                    SH,
                    "-s",
                    "--",
                    "verify",
                    "--parent",
                    parent,
                    "--trusted-python",
                    candidate_prepare.sys.executable,
                ],
                cwd=root,
                env=environment,
                input=trusted_wrapper,
                check=False,
                shell=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertIn("trusted-parent verify", completed.stdout)
            self.assertFalse(marker.exists())
            self.assertEqual([], list(bootstrap_tmp.iterdir()))

            rejected = subprocess.run(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
                [  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-tainted-env-args.dangerous-subprocess-use-tainted-env-args
                    SH,
                    "-s",
                    "--",
                    "verify",
                    "--parent",
                    parent,
                    "--trusted-python",
                    str(poison_bin / "python"),
                ],
                cwd=root,
                env=environment,
                input=trusted_wrapper,
                check=False,
                shell=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(2, rejected.returncode)
            self.assertIn("outside the repository worktree", rejected.stderr)
            self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
