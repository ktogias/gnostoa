"""Execute a frozen experiment lock through the existing #164 runner.

`execute` performs no discovery. It materialises the execution capsule from the
identities the lock binds plus the content-addressed artifact store, verifies what
it produced, and hands the execution profile to the runner. It cannot repair or
reinterpret the lock, and it never touches the qualification trust domain.
"""

from __future__ import annotations

import json
import subprocess
import tarfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from tools.capsule import lock as lock_module
from tools.capsule import profiles
from tools.capsule.identity import digest_text

_GIT_ENV = {
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
    "PATH": "/usr/bin:/bin",
}


class ExecuteError(RuntimeError):
    """The lock cannot be executed as frozen."""


@dataclass
class ExecutionResult:
    status: str
    blockers: list[dict[str, object]] = field(default_factory=list)
    runs: dict[str, dict[str, object]] = field(default_factory=dict)

    def as_json(self) -> dict[str, object]:
        return {"status": self.status, "blockers": self.blockers, "runs": self.runs}


def _materialize(repo: Path, tree: str, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination.parent / f"{destination.name}.tar"
    try:
        with archive.open("wb") as handle:
            subprocess.run(
                ["git", "-C", str(repo), "archive", "--format=tar", tree],
                check=True,
                stdout=handle,
                env=_GIT_ENV,
            )
        if not hasattr(tarfile, "data_filter"):
            raise ExecuteError("tarfile-data-filter-unavailable")
        with tarfile.open(archive) as handle:
            handle.extractall(destination, filter="data")
    finally:
        archive.unlink(missing_ok=True)


def materialize_capsule(
    lock_payload: Mapping[str, Any], workspace: Path, task_id: str
) -> tuple[Path, dict[str, Any]]:
    """Rebuild one task's execution capsule from the lock and the artifact store."""
    task = next((item for item in lock_payload["tasks"] if item["id"] == task_id), None)
    if task is None:
        raise ExecuteError(f"unknown task {task_id!r} in lock")

    profile = dict(task["execution_profile"])
    project = workspace / "capsule" / task_id / "project"
    evidence = workspace / "capsule" / task_id / "evidence"
    scratch = workspace / "capsule" / task_id / "tmp"
    for path in (project, evidence, scratch):
        path.mkdir(parents=True, exist_ok=True)

    if not any(project.iterdir()):
        _materialize(Path(task["source_repository"]), task["base_tree"], project)

    store = workspace / "artifacts"
    for artifact in cast(
        Sequence[Mapping[str, str]], task.get("stored_artifacts") or []
    ):
        if artifact.get("domain") != profiles.EXECUTION:
            # Qualification-domain artifacts (oracle harness, test-config isolation)
            # never enter the executor capsule.
            continue
        source = store / Path(artifact["store"]).name
        if not source.is_file():
            raise ExecuteError(
                f"artifact {artifact['path']!r} is not recoverable from the bound store"
            )
        content = source.read_text()
        if digest_text(content) != artifact["sha256"]:
            raise ExecuteError(f"artifact {artifact['path']!r} failed its digest check")
        (project / artifact["path"]).write_text(content)

    profile["project_root"] = str(project)
    profile["evidence_root"] = str(evidence)
    profile["temporary_roots"] = [str(scratch)]
    profile["read_only_roots"] = []
    return project, profile


def execute_lock(
    lock_path: Path, workspace: Path, *, backend: str = "oci", dry_run: bool = False
) -> ExecutionResult:
    payload = lock_module.load(lock_path)
    result = ExecutionResult(status="BLOCKED")
    workspace.mkdir(parents=True, exist_ok=True)

    for task in cast(Sequence[Mapping[str, Any]], payload["tasks"]):
        task_id = str(task["id"])
        try:
            project, profile = materialize_capsule(payload, workspace, task_id)
        except ExecuteError as exc:
            result.blockers.append(
                {
                    "task": task_id,
                    "code": "capsule-not-materialisable",
                    "detail": str(exc),
                }
            )
            continue

        # The frozen execution profile must still refuse every private surface.
        forbidden: dict[str, Path] = {}
        for name, material in (task.get("private_material") or {}).items():
            forbidden[name] = Path(str(material["locator"]))
        try:
            profiles.assert_execution_boundary(profile, forbidden)
        except profiles.ProfileBoundaryError as exc:
            result.blockers.append(
                {
                    "task": task_id,
                    "code": "execution-boundary-violated",
                    "detail": str(exc),
                }
            )
            continue

        argv = list(task.get("execution_command") or [])
        if not argv:
            result.blockers.append(
                {
                    "task": task_id,
                    "code": "execution-command-not-declared",
                    "detail": (
                        "the lock binds no execution command; the qualification invocation "
                        "runs the hidden oracle and must never be reused as the executor "
                        "command, so the spec has to declare execution.command explicitly"
                    ),
                }
            )
            continue

        if dry_run:
            result.runs[task_id] = {
                "status": "MATERIALISED",
                "project_root": str(project),
                "argv": argv,
                "files": sum(1 for _ in project.rglob("*") if _.is_file()),
            }
            continue

        from tools.experiment.execution import run_profile_command

        profile_path = workspace / "capsule" / task_id / "execution-profile.json"
        profile_path.write_text(json.dumps(profile, indent=2, sort_keys=True))
        exit_code, run_payload = run_profile_command(profile_path, backend, argv)
        result.runs[task_id] = {
            "status": run_payload.get("status"),
            "exit_code": exit_code,
            "evidence_root": profile["evidence_root"],
            "reasons": run_payload.get("reasons"),
        }

    if not result.blockers:
        result.status = "EXECUTED" if not dry_run else "MATERIALISED"
    return result
