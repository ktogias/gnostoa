"""Compile a declarative experiment specification into qualified capsules.

`prepare` performs mechanical preparation and qualification only. It returns
either a complete immutable lock or a structured BLOCKED result. It never
acquires a dependency, never repairs semantics and never advances past a stage
whose evidence it does not hold.
"""

from __future__ import annotations

import json
import subprocess
import tarfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tools.capsule import adapters, certificates, stages
from tools.capsule.adapters import GeneratedFile, HarnessResult, Invocation
from tools.capsule.identity import PRODUCER, digest_of, digest_path, digest_text, provenance
from tools.capsule.oracle_qualification import OracleShape, qualify, read_shape
from tools.capsule.preparation import (
    PreparationRequirement,
    TestConfig,
    discover_preparation,
    discover_test_config,
)
from tools.capsule.spec import ExperimentSpec, TaskSpec
from tools.experiment.profile import PROFILE_SCHEMA, validate_profile_data

LOCK_SCHEMA = "gnostoa-experiment-lock/v1"
_GIT_ENV = {"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null", "PATH": "/usr/bin:/bin"}


class CompileError(RuntimeError):
    pass


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        env=_GIT_ENV,
    )
    return result.stdout.strip()


def _materialize(repo: Path, treeish: str, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination.parent / f"{destination.name}.tar"
    with archive.open("wb") as handle:
        subprocess.run(
            ["git", "-C", str(repo), "archive", "--format=tar", treeish],
            check=True,
            stdout=handle,
            env=_GIT_ENV,
        )
    try:
        if not hasattr(tarfile, "data_filter"):
            # PEP 706 landed in 3.12 and was backported to 3.11.4. Refuse rather
            # than extract a subject tree without the hardened member filter.
            raise CompileError("tarfile-data-filter-unavailable")
        with tarfile.open(archive) as tar:
            tar.extractall(destination, filter="data")
    finally:
        archive.unlink(missing_ok=True)


@dataclass(frozen=True, slots=True)
class GeneratedArtifact:
    path: str
    sha256: str
    provenance: Mapping[str, object]


@dataclass
class TaskResult:
    id: str
    adapter: str
    base_tree: str
    reference_tree: str
    runtime_image: str
    oracle_sha256: str
    preparation: PreparationRequirement
    test_config: TestConfig
    harness: HarnessResult | None = None
    prepared_runtime_identity: str | None = None
    runner_profile: dict[str, Any] | None = None
    semantic_identity: str = ""
    capsule_identity: str = ""

    @property
    def invocation(self) -> Invocation | None:
        return self.harness.invocation if self.harness else None

    @property
    def added_runtime_packages(self) -> list[str]:
        return list(self.harness.added_runtime_packages) if self.harness else []

    def as_json(self) -> dict[str, object]:
        return {
            "id": self.id,
            "adapter": self.adapter,
            "base_tree": self.base_tree,
            "reference_tree": self.reference_tree,
            "runtime_image": self.runtime_image,
            "prepared_runtime_identity": self.prepared_runtime_identity,
            "oracle_sha256": self.oracle_sha256,
            "preparation": self.preparation.as_json(),
            "test_config": self.test_config.as_json(),
            "harness": self.harness.as_json() if self.harness else None,
            "semantic_identity": self.semantic_identity,
            "capsule_identity": self.capsule_identity,
        }


@dataclass
class PrepareResult:
    status: str
    stage: str
    blockers: list[dict[str, object]] = field(default_factory=list)
    tasks: dict[str, TaskResult] = field(default_factory=dict)
    acquisitions: list[str] = field(default_factory=list)
    reused_stages: list[str] = field(default_factory=list)
    lock_path: Path | None = None
    reused_certificates: list[dict[str, object]] = field(default_factory=list)
    _identities: dict[str, str] = field(default_factory=dict)

    def task(self, identifier: str) -> TaskResult:
        return self.tasks[identifier]

    def stage_identities(self) -> dict[str, str]:
        return dict(self._identities)

    def generated_artifacts(self) -> list[GeneratedArtifact]:
        found: list[GeneratedArtifact] = []
        for task in self.tasks.values():
            if task.harness is None:
                continue
            for generated in task.harness.generated_files:
                found.append(
                    GeneratedArtifact(
                        path=generated.path,
                        sha256=digest_text(generated.content),
                        provenance=generated.provenance,
                    )
                )
        return found


def _runner_profile(
    task: TaskSpec,
    roots: Mapping[str, Path],
    oracle_sha256: str,
    harness: HarnessResult,
) -> dict[str, Any]:
    return {
        "schema": PROFILE_SCHEMA,
        "project_root": str(roots["project"]),
        "evidence_root": str(roots["evidence"]),
        "temporary_roots": [str(roots["temporary"])],
        "read_only_roots": [str(roots["subject"])],
        "excluded_roots": [],
        "environment_allowlist": sorted(harness.invocation.env),
        "credential_environment": [],
        "input_identities": [
            f"base-tree={digest_text(task.source.base_tree)}",
            f"reference-tree={digest_text(task.reference.tree)}",
            f"oracle={oracle_sha256}",
            f"harness={harness.identity}",
        ],
        "network": {"mode": "none", "allow": []},
        "archive_limit_bytes": 268435456,
    }


def _prepare_task(
    task: TaskSpec,
    workspace: Path,
    *,
    offline: bool,
    blockers: list[dict[str, object]],
) -> TaskResult:
    task_root = (workspace / "tasks" / task.id).resolve()
    roots = {
        "subject": task_root / "subject",
        "project": task_root / "project",
        "evidence": task_root / "evidence",
        "temporary": task_root / "tmp",
    }
    for path in roots.values():
        path.mkdir(parents=True, exist_ok=True)

    repo = Path(task.source.repository)
    base_dir = roots["subject"] / "base"
    reference_dir = roots["subject"] / "reference"

    observed_base = _git(repo, "rev-parse", f"{task.source.base_commit}^{{tree}}")
    if observed_base != task.source.base_tree:
        blockers.append(
            {
                "task": task.id,
                "code": "base-tree-identity-mismatch",
                "detail": f"declared {task.source.base_tree}, resolved {observed_base}",
            }
        )
    reference_repo = Path(task.reference.repository) if task.reference.repository else repo
    reference_ref = task.reference.commit or task.reference.tree
    observed_reference = _git(reference_repo, "rev-parse", f"{reference_ref}^{{tree}}")
    if observed_reference != task.reference.tree:
        blockers.append(
            {
                "task": task.id,
                "code": "reference-tree-identity-mismatch",
                "detail": f"declared {task.reference.tree}, resolved {observed_reference}",
            }
        )

    if not base_dir.exists() or not any(base_dir.iterdir()):
        _materialize(repo, task.source.base_tree, base_dir)
    if not reference_dir.exists() or not any(reference_dir.iterdir()):
        _materialize(reference_repo, task.reference.tree, reference_dir)

    test_config = discover_test_config(base_dir)
    preparation = discover_preparation(base_dir)
    oracle_sha256 = digest_path(task.oracle_path)
    if task.oracle_sha256 and task.oracle_sha256 != oracle_sha256:
        blockers.append(
            {
                "task": task.id,
                "code": "oracle-identity-mismatch",
                "detail": f"declared {task.oracle_sha256}, observed {oracle_sha256}",
            }
        )

    result = TaskResult(
        id=task.id,
        adapter=task.adapter,
        base_tree=task.source.base_tree,
        reference_tree=task.reference.tree,
        runtime_image=task.runtime.image,
        oracle_sha256=oracle_sha256,
        preparation=preparation,
        test_config=test_config,
        semantic_identity=digest_of(task.semantic_payload()),
    )

    if preparation.required:
        declared = {tool.name: tool for tool in task.runtime.preparation_tools}
        available: list[dict[str, object]] = []
        for name in preparation.tool_names:
            tool = declared.get(name)
            if tool is None:
                blockers.append(
                    {
                        "task": task.id,
                        "code": "preparation-tool-undeclared",
                        "detail": (
                            f"the frozen tree needs {name!r} to generate "
                            f"{list(preparation.generated_paths)}; declare it under "
                            "runtime.preparation_tools with a locally available artifact"
                        ),
                    }
                )
                continue
            artifact = Path(tool.artifact)
            if not artifact.is_file():
                blockers.append(
                    {
                        "task": task.id,
                        "code": "preparation-artifact-unavailable-offline",
                        "detail": (
                            f"{tool.name} artifact {tool.artifact!r} is not present locally; "
                            "offline preparation never acquires it"
                        ),
                    }
                )
                continue
            available.append({"name": tool.name, "sha256": digest_path(artifact)})
        if available and len(available) == len(preparation.tool_names):
            result.prepared_runtime_identity = digest_of(
                {
                    "base_image": task.runtime.image,
                    "preparation": preparation.as_json(),
                    "tools": available,
                }
            )

    adapter = adapters.get(task.adapter)
    harness = adapter.build(
        task,
        workspace_path="/workspace",
        oracle_name=task.oracle_path.name,
        test_config=test_config,
    )
    blockers.extend(dict(item) for item in harness.blockers)
    result.harness = harness

    shape = read_shape(task.oracle_path)
    blockers.extend(
        qualify(
            shape,
            task.semantics,
            base_tree=base_dir,
            task_id=task.id,
            prior_qualification_sha256=task.prior_qualification_sha256,
        )
    )

    profile = _runner_profile(task, roots, oracle_sha256, harness)
    reasons = validate_profile_data(profile, for_run=False)
    if reasons:
        blockers.append(
            {"task": task.id, "code": "generated-profile-invalid", "detail": ",".join(reasons)}
        )
    result.runner_profile = profile
    result.capsule_identity = digest_of(result.as_json())
    return result


def prepare(
    spec: ExperimentSpec,
    workspace: str | Path,
    *,
    offline: bool = True,
    preflight_authority: str | None = None,
) -> PrepareResult:
    if not offline:
        raise CompileError(
            "online preparation is not implemented in v1; dependency acquisition is out of scope"
        )
    root = Path(workspace)
    root.mkdir(parents=True, exist_ok=True)
    root = root.resolve()
    ledger = stages.StageLedger(root=root)
    ledger.load()

    blockers: list[dict[str, object]] = []
    result = PrepareResult(status="BLOCKED", stage=stages.DISCOVERED)

    ledger.enter(stages.DISCOVERED, {"spec": str(spec.source_path), "tasks": [t.id for t in spec.tasks]})
    ledger.complete(stages.DISCOVERED, {"tasks": len(spec.tasks)})

    semantic_inputs = {task.id: task.semantic_payload() for task in spec.tasks}
    ledger.enter(stages.SEMANTIC_FROZEN, semantic_inputs)
    ledger.complete(
        stages.SEMANTIC_FROZEN,
        {task_id: digest_of(payload) for task_id, payload in semantic_inputs.items()},
    )

    tasks: dict[str, TaskResult] = {}
    for task in spec.tasks:
        tasks[task.id] = _prepare_task(task, root, offline=offline, blockers=blockers)
    result.tasks = tasks

    ledger.enter(
        stages.RUNTIME_PREPARED,
        {
            task.id: {
                "runtime": task.runtime.as_json(),
                "source": {"base_tree": task.source.base_tree, "reference_tree": task.reference.tree},
                "preparation": tasks[task.id].preparation.as_json(),
            }
            for task in spec.tasks
        },
    )
    ledger.complete(
        stages.RUNTIME_PREPARED,
        {task_id: task.prepared_runtime_identity for task_id, task in tasks.items()},
    )

    ledger.enter(
        stages.STATIC_QUALIFIED,
        {
            task.id: {
                "harness": task.harness.as_json(),
                "oracle_sha256": tasks[task.id].oracle_sha256,
                "profile": tasks[task.id].runner_profile,
            }
            for task in spec.tasks
        },
    )
    if blockers:
        result.blockers = blockers
        result.status = "BLOCKED"
        result.stage = stages.RUNTIME_PREPARED
        result._identities = ledger.identities()
        result.reused_stages = list(ledger.reused)
        ledger.invalidate_from(stages.BASE_REFERENCE_QUALIFIED)
        ledger.save()
        _write_state(root, result)
        return result

    ledger.complete(
        stages.STATIC_QUALIFIED, {task_id: task.capsule_identity for task_id, task in tasks.items()}
    )
    result.stage = stages.STATIC_QUALIFIED

    reused_certificates = _consume_certificates(spec, blockers)
    result.reused_certificates = reused_certificates
    if blockers:
        result.blockers = blockers
        result.status = "BLOCKED"
        result._identities = ledger.identities()
        result.reused_stages = list(ledger.reused)
        ledger.save()
        _write_state(root, result)
        return result

    if preflight_authority is None:
        blockers.append(
            {
                "task": None,
                "code": "base-reference-qualification-requires-preflight-authority",
                "detail": (
                    "static preparation is complete; executing the hidden oracle against BASE and "
                    "REFERENCE requires an explicit owner preflight authority"
                ),
            }
        )
        result.blockers = blockers
        result.status = "BLOCKED"
        result._identities = ledger.identities()
        result.reused_stages = list(ledger.reused)
        ledger.save()
        _write_state(root, result)
        return result

    result.status = "READY_FOR_OWNER_REVIEW"
    result._identities = ledger.identities()
    result.reused_stages = list(ledger.reused)
    ledger.save()
    _write_state(root, result)
    return result


def _consume_certificates(
    spec: ExperimentSpec, blockers: list[dict[str, object]]
) -> list[dict[str, object]]:
    """Reuse an exact certificate, or block. Bounds are never widened to fit."""
    reused: list[dict[str, object]] = []
    for request in spec.capabilities:
        if not request.certificate_path.is_file():
            blockers.append(
                {
                    "task": None,
                    "code": "capability-certificate-missing",
                    "detail": f"{request.capability}: {request.certificate_path} is not present",
                }
            )
            continue
        try:
            certificate = certificates.load_file(request.certificate_path)
        except certificates.CertificateError as exc:
            blockers.append(
                {
                    "task": None,
                    "code": "capability-certificate-invalid",
                    "detail": f"{request.capability}: {exc}",
                }
            )
            continue
        if certificate.satisfies(
            capability=request.capability,
            runtime_identity=certificate.runtime_identity,
            implementation_sha256=certificate.implementation_sha256,
            configuration_sha256=certificate.configuration_sha256,
            requested=request.requested_bounds,
        ):
            reused.append(
                {
                    "capability": request.capability,
                    "evidence_sha256": certificate.evidence_sha256,
                    "requested_bounds": dict(request.requested_bounds),
                    "reused": True,
                }
            )
        else:
            blockers.append(
                {
                    "task": None,
                    "code": "capability-bounds-not-certified",
                    "detail": (
                        f"{request.capability}: requested {dict(request.requested_bounds)} exceeds or "
                        f"does not match certified {dict(certificate.bounds)}; requalify or block"
                    ),
                }
            )
    return reused


def _write_state(root: Path, result: PrepareResult) -> None:
    payload = {
        "schema": LOCK_SCHEMA,
        "producer": PRODUCER,
        "status": result.status,
        "stage": result.stage,
        "blockers": result.blockers,
        "reused_certificates": result.reused_certificates,
        "tasks": {task_id: task.as_json() for task_id, task in result.tasks.items()},
    }
    (root / "experiment-state.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def status(workspace: str | Path) -> dict[str, Any]:
    root = Path(workspace).resolve()
    path = root / "experiment-state.json"
    if not path.is_file():
        return {"stage": stages.DISCOVERED, "status": "BLOCKED", "tasks": {}, "blockers": []}
    payload: dict[str, Any] = json.loads(path.read_text())
    return payload
