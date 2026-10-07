from __future__ import annotations

import hashlib
import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
ORIENTATION_PATH = ROOT / "tasks/gnostoa_orientation.py"
SPEC = importlib.util.spec_from_file_location(
    "gnostoa_self_orientation_git_guard", ORIENTATION_PATH
)
assert SPEC is not None and SPEC.loader is not None
orientation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(orientation)

NOW = "2026-09-11T13:00:00Z"


def _fact(identity: str, text: str) -> dict[str, object]:
    return {"id": identity, "text": text, "source_ids": ["local"]}


def _snapshot(root: Path) -> dict[str, object]:
    local = root / "source.md"
    local.write_text("source\n", encoding="utf-8")
    digest = "sha256:" + hashlib.sha256(local.read_bytes()).hexdigest()
    return {
        "contract": "gnostoa-self-orientation/0.1",
        "subject": {"source_commit": "a" * 40, "source_tree": "b" * 40},
        "projection": {
            "id": "D14-O1",
            "observed_at": "2026-09-11T12:00:00Z",
            "freshness_seconds": 7200,
            "review_characters": 5000,
        },
        "sources": [
            {
                "id": "local",
                "kind": "local-file",
                "locator": "source.md",
                "identity": digest,
                "observed_at": "2026-09-11T12:00:00Z",
                "required": True,
                "status": "complete",
            }
        ],
        "facts": {
            "purpose": _fact("purpose", "Resume bounded work."),
            "implemented": [_fact("implemented", "A tested projector.")],
            "proposed": [_fact("proposed", "A generic projection capability.")],
            "current": [_fact("current", "D14-O1 is selected.")],
            "next_action": _fact("next", "Review the exact candidate."),
            "proposed_successor": {
                **_fact("successor", "Evaluate a later slice."),
                "admission_state": "proposed",
            },
            "blockers": [],
            "constraints": [_fact("constraint", "No provider write-back.")],
            "return_to_adoption": _fact("return", "Use actual launch gates."),
        },
    }


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


class OrientationGitExecutableTests(unittest.TestCase):
    def test_a_git_planted_first_on_the_caller_s_path_is_not_run(self) -> None:
        """A bare `git` resolved through the caller's `PATH` would run whatever is
        first there (CodeAnt on #369); orientation runs the owner's trusted Git."""
        import os

        with tempfile.TemporaryDirectory() as scratch:
            base = Path(scratch)
            root = base / "repo"
            root.mkdir()
            _git(root, "init", "--quiet")
            _git(
                root,
                "-c",
                "user.name=a",
                "-c",
                "user.email=a@example.invalid",
                "commit",
                "--quiet",
                "--allow-empty",
                "-m",
                "c",
            )
            planted = base / "bin"
            planted.mkdir()
            marker = base / "planted-git-ran"
            fake = planted / "git"
            fake.write_text(
                f'#!/bin/sh\nprintf x > {marker}\nexec /usr/bin/git "$@"\n',
                encoding="utf-8",
            )
            fake.chmod(0o755)
            with patch.dict(
                os.environ, {"PATH": f"{planted}:{os.environ.get('PATH', '')}"}
            ):
                orientation._git_output(  # skipcq: PYL-W0212
                    root, "rev-parse", "HEAD"
                )
            self.assertFalse(marker.exists(), "the git planted on PATH ran")


class OrientationGitEnvironmentTests(unittest.TestCase):
    def test_no_loader_variable_reaches_the_trusted_git(self) -> None:
        """The caller's `LD_PRELOAD` survived the scrub and was honored when Git
        started (CodeAnt on #369); macOS reads `DYLD_*` the same way."""
        caller = {
            "PATH": "/usr/bin:/bin",
            "HOME": "/home/caller",
            "GIT_DIR": "/elsewhere",
            "LD_PRELOAD": "/opt/injected/x.so",
            "LD_LIBRARY_PATH": "/opt/injected",
            "DYLD_INSERT_LIBRARIES": "/opt/injected/x.dylib",
        }
        with patch.dict("os.environ", caller, clear=True):
            environment = orientation._git_environment()  # skipcq: PYL-W0212
        self.assertEqual("/usr/bin:/bin", environment["PATH"])
        for name in (
            "GIT_DIR",
            "LD_PRELOAD",
            "LD_LIBRARY_PATH",
            "DYLD_INSERT_LIBRARIES",
        ):
            with self.subTest(name=name):
                self.assertNotIn(name, environment)


class OrientationOwnerLoadFailureTests(unittest.TestCase):
    def test_an_owner_that_cannot_load_is_an_orientation_error(self) -> None:
        """The owner was loaded before the `try`, so a load failure escaped raw
        (CodeRabbit on #369)."""
        with (
            patch.object(
                orientation,
                "_trusted_execution",
                side_effect=ImportError("cannot load"),
            ),
            self.assertRaises(orientation.OrientationError),
        ):
            orientation._git_output(ROOT, "rev-parse", "HEAD")  # skipcq: PYL-W0212


class OrientationOwnerBindingTests(unittest.TestCase):
    def test_the_owner_is_this_checkout_s_whatever_comes_first_on_the_path(
        self,
    ) -> None:
        """A `tools` package earlier on `PYTHONPATH` stood in for the owner when the
        checkout was already on the path (Codex on #369)."""
        import os
        import sys

        with tempfile.TemporaryDirectory() as scratch:
            shadow = Path(scratch) / "tools"
            shadow.mkdir()
            (shadow / "__init__.py").write_text("", encoding="utf-8")
            (shadow / "trusted_execution.py").write_text(
                "SHADOW = True\n", encoding="utf-8"
            )
            probe = (
                "import importlib.util\n"
                f"spec = importlib.util.spec_from_file_location('o', {str(ORIENTATION_PATH)!r})\n"
                "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\n"
                "print(m._trusted_execution().__file__)\n"
            )
            result = subprocess.run(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
                [sys.executable, "-c", probe],
                capture_output=True,
                text=True,
                check=True,
                # Away from the checkout, whose directory `-c` would put first.
                cwd="/",
                env={**os.environ, "PYTHONPATH": f"{scratch}{os.pathsep}{ROOT}"},
            )
            self.assertEqual(
                str((ROOT / "tools" / "trusted_execution.py").resolve()),
                str(Path(result.stdout.strip()).resolve()),
            )


class OrientationGitGuardTests(unittest.TestCase):
    def test_bound_repository_subject_is_evidence_and_each_mismatch_is_stale(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = _snapshot(root)
            matching = {"source_commit": "a" * 40, "source_tree": "b" * 40}
            current = orientation.build_manifest(
                snapshot, root, NOW, observed_repository_subject=matching
            )
            self.assertEqual("CURRENT", current["evaluation"]["status"])
            self.assertEqual(matching, current["evaluation"]["repository_subject"])

            for name in ("source_commit", "source_tree"):
                with self.subTest(name=name):
                    observed = dict(matching)
                    observed[name] = "c" * 40
                    stale = orientation.build_manifest(
                        snapshot,
                        root,
                        NOW,
                        observed_repository_subject=observed,
                    )
                    self.assertEqual("STALE", stale["evaluation"]["status"])
                    self.assertIn(
                        f"repository-subject-mismatch:{name}",
                        stale["evaluation"]["diagnostics"],
                    )

    def test_malformed_bound_repository_subject_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = _snapshot(root)
            with self.assertRaisesRegex(
                orientation.OrientationError,
                "observed_repository_subject.source_commit",
            ):
                orientation.build_manifest(
                    snapshot,
                    root,
                    NOW,
                    observed_repository_subject={
                        "source_commit": "invalid",
                        "source_tree": "b" * 40,
                    },
                )

    def test_observer_rejects_repository_subdirectory_as_explicit_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "tracked.txt").write_text("tracked\n", encoding="utf-8")
            _git(root, "init", "-q")
            _git(root, "config", "user.email", "gnostoa-tests@example.test")
            _git(root, "config", "user.name", "Gnostoa Tests")
            _git(root, "add", "tracked.txt")
            _git(root, "commit", "-q", "-m", "fixture")
            child = root / "child"
            child.mkdir()
            with self.assertRaisesRegex(
                orientation.OrientationError,
                "repository root does not match Git top level",
            ):
                orientation.observe_repository_subject(child)

    def test_git_timeout_fails_closed(self) -> None:
        with patch.object(
            orientation.subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired(cmd=["git"], timeout=5),
        ):
            with self.assertRaisesRegex(
                orientation.OrientationError,
                "cannot observe repository Git subject",
            ):
                orientation.observe_repository_subject(Path("."))

    def test_git_invocation_uses_exact_local_trust_without_shell_or_wildcard(
        self,
    ) -> None:
        completed = subprocess.CompletedProcess(
            args=["git"], returncode=0, stdout="a" * 40 + "\n", stderr=""
        )
        root = Path("/tmp/a path;not-shell").resolve()
        with patch.dict(
            orientation.os.environ,
            {
                "GIT_DIR": "/tmp/ambient.git",
                "GIT_WORK_TREE": "/tmp/ambient-work-tree",
                "GIT_CONFIG_COUNT": "1",
            },
            clear=False,
        ):
            with patch.object(
                orientation.subprocess, "run", return_value=completed
            ) as run:
                value = orientation._git_output(root, "rev-parse", "HEAD")
        self.assertEqual("a" * 40, value)
        command = run.call_args.args[0]
        kwargs = run.call_args.kwargs
        self.assertIsInstance(command, list)
        self.assertEqual(
            [
                orientation._trusted_execution().git_executable(),  # skipcq: PYL-W0212
                "-c",
                f"safe.directory={root}",
                "-C",
                str(root),
                "rev-parse",
                "HEAD",
            ],
            command,
        )
        self.assertNotIn("safe.directory=*", command)
        self.assertFalse(kwargs.get("shell", False))
        self.assertEqual(orientation.GIT_TIMEOUT_SECONDS, kwargs["timeout"])
        environment = kwargs["env"]
        self.assertEqual("0", environment["GIT_OPTIONAL_LOCKS"])
        self.assertEqual("C", environment["LC_ALL"])
        self.assertEqual("C", environment["LANG"])
        self.assertNotIn("GIT_DIR", environment)
        self.assertNotIn("GIT_WORK_TREE", environment)
        self.assertNotIn("GIT_CONFIG_COUNT", environment)
        self.assertTrue(
            all(
                not key.startswith("GIT_") or key == "GIT_OPTIONAL_LOCKS"
                for key in environment
            )
        )

    def test_observer_derives_tree_from_the_observed_commit(self) -> None:
        root = Path("/tmp/coherent-repository-subject").resolve()
        commit = "a" * 40
        tree = "b" * 40
        with patch.object(
            orientation,
            "_git_output",
            side_effect=[str(root), commit, tree],
        ) as git_output:
            observed = orientation.observe_repository_subject(root)
        self.assertEqual(
            {"source_commit": commit, "source_tree": tree},
            observed,
        )
        calls = [call.args[1:] for call in git_output.call_args_list]
        self.assertEqual(
            [
                ("rev-parse", "--show-toplevel"),
                ("rev-parse", "--verify", "HEAD^{commit}"),
                ("rev-parse", "--verify", f"{commit}^{{tree}}"),
            ],
            calls,
        )

    def test_observer_rejects_malformed_commit_before_tree_lookup(self) -> None:
        root = Path("/tmp/malformed-repository-subject").resolve()
        with patch.object(
            orientation,
            "_git_output",
            side_effect=[str(root), "not-a-git-id"],
        ) as git_output:
            with self.assertRaisesRegex(
                orientation.OrientationError,
                "observed_repository_subject.source_commit",
            ):
                orientation.observe_repository_subject(root)
        self.assertEqual(2, len(git_output.call_args_list))


if __name__ == "__main__":
    unittest.main()
