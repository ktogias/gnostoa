"""Execute a frozen experiment lock through the existing #164 runner.

`execute` performs no discovery. It materialises the execution capsule from the
identities the lock binds plus the content-addressed artifact store, verifies what
it produced, and hands the execution profile to the runner. It cannot repair or
reinterpret the lock, and it never touches the qualification trust domain.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import tarfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from tools.capsule import lock as lock_module
from tools.capsule import profiles
from tools.capsule.authority import LaunchAuthority

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
    lock_payload: Mapping[str, Any],
    workspace: Path,
    task_id: str,
    *,
    run_id: str | None = None,
    arm_inputs: Sequence[Mapping[str, str]] = (),
) -> tuple[Path, dict[str, Any]]:
    """Rebuild one run's execution capsule from the lock and the artifact store."""
    task = next((item for item in lock_payload["tasks"] if item["id"] == task_id), None)
    if task is None:
        raise ExecuteError(f"unknown task {task_id!r} in lock")

    profile = dict(task["execution_profile"])
    slug = (run_id or task_id).replace("/", "__")
    root = workspace / "capsule" / slug
    project = root / "project"
    evidence = root / "evidence"
    scratch = root / "tmp"
    arm_root = root / "arm"
    for path in (project, evidence, scratch, arm_root):
        path.mkdir(parents=True, exist_ok=True)

    store = Path(str(lock_payload.get("artifact_store") or (workspace / "artifacts")))
    if not any(project.iterdir()):
        _materialize(Path(task["source_repository"]), task["base_tree"], project)

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
        payload = source.read_bytes()
        if hashlib.sha256(payload).hexdigest() != artifact["sha256"]:
            raise ExecuteError(f"artifact {artifact['path']!r} failed its digest check")
        destination = project / artifact["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)

    read_only: list[str] = []

    # Task-level executor inputs the lock declares must survive rematerialisation.
    inputs_root = root / "inputs"
    for declared in cast(
        Sequence[Mapping[str, str]], task.get("execution_inputs") or []
    ):
        source = store / Path(str(declared["store"])).name
        if not source.is_file():
            raise ExecuteError(
                f"execution input {declared['id']!r} is not recoverable from the bound store"
            )
        payload = source.read_bytes()
        if hashlib.sha256(payload).hexdigest() != declared["sha256"]:
            raise ExecuteError(
                f"execution input {declared['id']!r} failed its digest check"
            )
        target = inputs_root / str(declared["id"])
        target.mkdir(parents=True, exist_ok=True)
        (target / str(declared["name"])).write_bytes(payload)
        read_only.append(str(target))

    # Only this run's arm packet is attached. The sibling arm is never materialised.
    for item in arm_inputs:
        source = Path(str(item.get("source", "")))
        if not source.is_file():
            raise ExecuteError(
                f"arm input {item.get('id')!r} is not available at its bound locator"
            )
        observed = hashlib.sha256(source.read_bytes()).hexdigest()
        declared_digest = str(item.get("sha256") or "")
        if declared_digest and declared_digest != observed:
            raise ExecuteError(f"arm input {item.get('id')!r} failed its digest check")
        target = arm_root / str(item.get("id"))
        target.mkdir(parents=True, exist_ok=True)
        (target / source.name).write_bytes(source.read_bytes())
        read_only.append(str(target))

    profile["project_root"] = str(project)
    profile["evidence_root"] = str(evidence)
    profile["temporary_roots"] = [str(scratch)]
    profile["read_only_roots"] = read_only
    return project, profile


def execute_lock(
    lock_path: Path,
    workspace: Path,
    *,
    backend: str = "oci",
    dry_run: bool = False,
    launch_authority: LaunchAuthority | None = None,
) -> ExecutionResult:
    payload = lock_module.load(lock_path)
    result = ExecutionResult(status="BLOCKED")
    workspace.mkdir(parents=True, exist_ok=True)

    plan = cast(Mapping[str, Any], payload.get("run_plan") or {})
    entries = cast(Sequence[Mapping[str, Any]], plan.get("runs") or [])
    if not entries:
        result.blockers.append(
            {
                "task": None,
                "code": "run-plan-missing",
                "detail": "the lock binds no run plan",
            }
        )
        return result

    # A real run effect requires a launch authority bound to this exact lock.
    if not dry_run:
        if launch_authority is None:
            result.blockers.append(
                {
                    "task": None,
                    "code": "launch-authority-required",
                    "detail": "experimental execution needs a typed launch authority",
                }
            )
            return result
        reasons = launch_authority.covers(
            experiment_id=str(cast(Mapping[str, Any], payload["experiment"])["id"]),
            lock_sha256=str(payload["lock_sha256"]),
            runs=len(entries),
        )
        if reasons:
            result.blockers.append(
                {
                    "task": None,
                    "code": "launch-authority-does-not-cover-this-lock",
                    "detail": "; ".join(reasons),
                }
            )
            return result

    for entry in entries:
        run_id = str(entry["id"])
        task_id = str(entry["task"])
        task = next(
            (
                item
                for item in cast(Sequence[Mapping[str, Any]], payload["tasks"])
                if item["id"] == task_id
            ),
            None,
        )
        if task is None:
            result.blockers.append(
                {
                    "task": task_id,
                    "code": "run-plan-names-unknown-task",
                    "detail": run_id,
                }
            )
            continue
        try:
            project, profile = materialize_capsule(
                payload,
                workspace,
                task_id,
                run_id=run_id,
                arm_inputs=cast(
                    Sequence[Mapping[str, str]], entry.get("arm_inputs") or []
                ),
            )
        except ExecuteError as exc:
            result.blockers.append(
                {
                    "task": task_id,
                    "code": "capsule-not-materialisable",
                    "detail": str(exc),
                }
            )
            continue

        forbidden: dict[str, Path] = {}
        private = cast(
            Mapping[str, Mapping[str, Any]], task.get("private_material") or {}
        )
        for name, material in private.items():
            forbidden[name] = Path(str(material["locator"]))
        for other in cast(Sequence[Mapping[str, Any]], plan.get("runs") or []):
            if other["arm"] != entry["arm"]:
                for sibling in cast(
                    Sequence[Mapping[str, str]], other.get("arm_inputs") or []
                ):
                    forbidden[f"sibling-arm-{other['arm']}-{sibling.get('id')}"] = Path(
                        str(sibling.get("source", ""))
                    )
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
                        "runs the hidden oracle and is never reused as the executor command"
                    ),
                }
            )
            continue

        if dry_run:
            result.runs[run_id] = {
                "status": "MATERIALISED",
                "task": task_id,
                "arm": entry["arm"],
                "repetition": entry["repetition"],
                "project_root": str(project),
                "argv": argv,
                "files": sum(1 for path in project.rglob("*") if path.is_file()),
            }
            continue

        from tools.experiment.execution import run_profile_command
        from tools.experiment.profile import RunnerError

        profile_path = (
            workspace / "capsule" / run_id.replace("/", "__") / "profile.json"
        )
        profile_path.write_text(json.dumps(profile, indent=2, sort_keys=True))
        try:
            exit_code, run_payload = run_profile_command(profile_path, backend, argv)
        except (RunnerError, OSError) as exc:
            # The runner enforces its own contract, including that every declared
            # credential name is actually present. Report it, never work around it.
            result.blockers.append(
                {
                    "task": task_id,
                    "code": "runner-refused-run",
                    "detail": f"{run_id}: {type(exc).__name__}: {exc}",
                }
            )
            continue
        result.runs[run_id] = {
            "status": run_payload.get("status"),
            "task": task_id,
            "arm": entry["arm"],
            "repetition": entry["repetition"],
            "exit_code": exit_code,
            "evidence_root": profile["evidence_root"],
            "reasons": run_payload.get("reasons"),
        }

    if not result.blockers:
        result.status = "MATERIALISED" if dry_run else "EXECUTED"
    return result
