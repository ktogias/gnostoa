"""What other test modules share from tests/test_experiment_capsule.py, outside the discovered test modules (#389 N1b; Decision 0128)."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any

from tools.capsule import compiler, qualification
from tools.capsule.authority import LaunchAuthority, PreflightAuthority
from tools.capsule.spec import ExperimentSpec

IMAGE_A = "sha256:" + "a" * 64


def git(repo: Path, *args: str) -> str:
    environment = {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.invalid",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "PATH": "/usr/bin:/bin",
    }
    # The child's own PATH is where subprocess would look for git.
    executable = shutil.which("git", path=environment["PATH"])
    if executable is None:
        raise FileNotFoundError(f"git is not on {environment['PATH']}")
    return subprocess.run(
        [executable, "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    ).stdout.strip()


class CapsuleFixture(unittest.TestCase):
    """Builds a tiny offline Git subject and a minimal spec around it."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()

    def make_repo(self, name: str, files: dict[str, str]) -> Path:
        repo = self.root / name
        (repo / "src").mkdir(parents=True)
        git(repo.parent, "init", "-q", "-b", "main", str(repo))
        for rel, text in files.items():
            target = repo / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "base")
        return repo

    @staticmethod
    def commit(repo: Path, files: dict[str, str], message: str) -> str:
        for rel, text in files.items():
            target = repo / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", message)
        return git(repo, "rev-parse", "HEAD")

    def write_spec(self, payload: dict[str, Any]) -> Path:
        path = self.root / "experiment.json"
        path.write_text(json.dumps(payload, indent=2))
        return path

    def base_spec(
        self, repo: Path, base: str, ref: str, **task: object
    ) -> dict[str, Any]:
        entry: dict[str, object] = {
            "id": "T1",
            "adapter": "python-pytest",
            "source": {
                "repository": str(repo),
                "base_commit": base,
                "base_tree": git(repo, "rev-parse", base + "^{tree}"),
            },
            "reference": {
                "kind": "accepted-merge-commit",
                "commit": ref,
                "tree": git(repo, "rev-parse", ref + "^{tree}"),
            },
            "runtime": {"image": IMAGE_A},
            "oracle": {"path": str(self.root / "oracle.py")},
            "semantics": {
                "requirement": "subject must not regress",
                "discriminator": {"cases": ["test_discriminates"]},
                "controls": [],
            },
            "expectations": {
                "base": {"failed": 1, "passed": 0},
                "reference": {"failed": 0, "passed": 1},
            },
            "execution": {
                "command": ["python", "-c", "print('executor')"],
                "environment_allowlist": ["HOME"],
            },
        }
        entry.update(task)
        return {
            "schema": "gnostoa-experiment-spec/v1",
            "experiment": {
                "id": "E1",
                "question": "q",
                "claim_boundary": "bounded",
                "executor": {"id": "exec", "version": "1", "config_sha256": "1" * 64},
                "resources": {
                    "timeout_seconds": 600,
                    "archive_limit_bytes": 268435456,
                    "network": {"mode": "none", "allow": []},
                },
            },
            "tasks": [entry],
        }

    @staticmethod
    def launch_authority(
        lock_sha256: str,
        *,
        experiment_id: str = "E1",
        max_runs: int | None = None,
    ) -> LaunchAuthority:
        return LaunchAuthority(
            id="launch-1",
            experiment_id=experiment_id,
            lock_sha256=lock_sha256,
            scope=("experimental-execution",),
            max_runs=max_runs,
        )

    @staticmethod
    def authority(
        experiment_id: str = "E1", candidate: str | None = None
    ) -> PreflightAuthority:
        return PreflightAuthority(
            id="auth-1",
            experiment_id=experiment_id,
            scope=("base-reference-qualification",),
            preflight_candidate_sha256=candidate or "",
        )

    def prepare_authorized(
        self,
        spec: ExperimentSpec,
        workspace: str | Path,
        *,
        experiment_id: str = "E1",
        qualification_backend: str = qualification.LOCAL_PYTHON,
    ) -> compiler.PrepareResult:
        """Observe the prepared candidate, authorise that exact one, then run it.

        This is the operational sequence itself, not a shortcut around it: an
        authority-less prepare reports the candidate digest, the owner approves that
        digest, and the unchanged candidate is re-prepared under it. prepare is
        idempotent, so the second call reuses the retained stages.
        """
        observed = compiler.prepare(
            spec,
            workspace,
            offline=True,
            qualification_backend=qualification_backend,
        )
        return compiler.prepare(
            spec,
            workspace,
            offline=True,
            preflight_authority=self.authority(
                experiment_id=experiment_id,
                candidate=observed.preflight_candidate_sha256,
            ),
            qualification_backend=qualification_backend,
        )
