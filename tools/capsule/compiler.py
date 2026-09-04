"""Compile a declarative experiment specification into qualified capsules.

`prepare` performs mechanical preparation and qualification only. It returns either a
complete immutable lock or a structured BLOCKED result. It never acquires a
dependency, never repairs semantics, and never reports readiness for a stage whose
content-addressed receipt it does not hold.
"""

from __future__ import annotations

import json
import subprocess
import tarfile
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tools.capsule import adapters, certificates, stages
from tools.capsule import lock as lock_module
from tools.capsule.adapters import HarnessResult, Invocation
from tools.capsule.authority import PreflightAuthority
from tools.capsule.identity import PRODUCER, digest_of, digest_path, digest_text
from tools.capsule.oracle_qualification import qualify, read_shape
from tools.capsule.preparation import (
    ConfigProjection,
    PreparationError,
    PreparationReceipt,
    PreparationRequirement,
    TestConfig,
    apply_preparation,
    discover_preparation,
    discover_test_config,
    project_test_config,
)
from tools.capsule.qualification import (
    LOCAL_PYTHON,
    QualificationReceipt,
    qualify_subjects,
)
from tools.capsule.spec import ExperimentSpec, TaskSpec
from tools.experiment.profile import PROFILE_SCHEMA, validate_profile_data

STATE_FILENAME = "experiment-state.json"
_GIT_ENV = {
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
    "PATH": "/usr/bin:/bin",
}
_IMPORT_ROOTS = ("src",)


class CompileError(RuntimeError):
    pass


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        env=_GIT_ENV,
    ).stdout.strip()


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
            # PEP 706 landed in 3.12 and was backported to 3.11.4. Refuse rather than
            # extract a subject tree without the hardened member filter.
            raise CompileError("tarfile-data-filter-unavailable")
        with tarfile.open(archive) as handle:
            handle.extractall(destination, filter="data")
    finally:
        archive.unlink(missing_ok=True)


def _observed_tree(repo: Path, worktree: Path, ignore: Sequence[str] = ()) -> str:
    """Independently reconstruct the Git tree identity of a materialised directory."""
    with tempfile.TemporaryDirectory() as scratch:
        index = Path(scratch) / "index"
        env = {**_GIT_ENV, "GIT_INDEX_FILE": str(index)}
        subprocess.run(
            [
                "git",
                "-C",
                str(repo),
                "--work-tree",
                str(worktree),
                "add",
                "-A",
                "--force",
            ],
            check=True,
            capture_output=True,
            env=env,
        )
        if ignore:
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo),
                    "rm",
                    "--cached",
                    "-q",
                    "--ignore-unmatch",
                    *ignore,
                ],
                check=False,
                capture_output=True,
                env=env,
            )
        return subprocess.run(
            ["git", "-C", str(repo), "write-tree"],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        ).stdout.strip()


def _materialize_verified(
    repo: Path,
    tree: str,
    root: Path,
    kind: str,
    blockers: list[dict[str, object]],
    task_id: str,
) -> Path | None:
    """Materialise create-only per source identity, then verify the retained bytes.

    The directory is named by the tree it must contain, so a changed spec can never
    reuse a previous subject's bytes, and the retained tree is re-verified on every
    run rather than trusted because it is non-empty.
    """
    destination = root / f"{kind}-{tree}"
    if not destination.exists() or not any(destination.iterdir()):
        _materialize(repo, tree, destination)
    observed = _observed_tree(repo, destination)
    if observed != tree:
        blockers.append(
            {
                "task": task_id,
                "code": "materialised-subject-identity-mismatch",
                "detail": (
                    f"{kind} workspace reconstructs to {observed}, not the declared {tree}; "
                    "the retained bytes are stale or modified"
                ),
            }
        )
        return None
    return destination


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
    identification_key_sha256: str | None
    preparation: PreparationRequirement
    test_config: TestConfig
    harness: HarnessResult | None = None
    config_projection: ConfigProjection | None = None
    preparation_receipt: PreparationReceipt | None = None
    prepared_runtime_identity: str | None = None
    runner_profile: dict[str, Any] | None = None
    qualification: QualificationReceipt | None = None
    semantic_identity: str = ""
    capsule_identity: str = ""
    base_path: Path | None = None
    reference_path: Path | None = None

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
            "identification_key_sha256": self.identification_key_sha256,
            "preparation": self.preparation.as_json(),
            "preparation_receipt": (
                self.preparation_receipt.as_json() if self.preparation_receipt else None
            ),
            "test_config": self.test_config.as_json(),
            "config_projection": (
                self.config_projection.as_json() if self.config_projection else None
            ),
            "harness": self.harness.as_json() if self.harness else None,
            "runner_profile": self.runner_profile,
            "qualification": self.qualification.as_json()
            if self.qualification
            else None,
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
    reused_certificates: list[dict[str, object]] = field(default_factory=list)
    lock_path: Path | None = None
    lock_identity: str | None = None
    _identities: dict[str, str] = field(default_factory=dict)
    _receipts: dict[str, str] = field(default_factory=dict)

    def task(self, identifier: str) -> TaskResult:
        return self.tasks[identifier]

    def stage_identities(self) -> dict[str, str]:
        return dict(self._identities)

    def stage_receipts(self) -> dict[str, str]:
        return dict(self._receipts)

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
    spec: ExperimentSpec,
    task: TaskSpec,
    roots: Mapping[str, Path],
    result: TaskResult,
    harness: HarnessResult,
) -> dict[str, Any]:
    """A complete run profile: the runner's own validator must accept it for_run."""
    identities = [
        f"base-tree={digest_text(result.base_tree)}",
        f"reference-tree={digest_text(result.reference_tree)}",
        f"oracle={result.oracle_sha256}",
        f"harness={harness.identity}",
    ]
    if result.identification_key_sha256:
        identities.append(f"identification-key={result.identification_key_sha256}")
    if result.preparation_receipt is not None:
        identities.append(f"preparation={result.preparation_receipt.identity}")
    if result.prepared_runtime_identity is not None:
        identities.append(f"prepared-runtime={result.prepared_runtime_identity}")
    return {
        "schema": PROFILE_SCHEMA,
        "project_root": str(roots["project"]),
        "evidence_root": str(roots["evidence"]),
        "temporary_roots": [str(roots["temporary"])],
        "read_only_roots": [str(roots["subject"])],
        "excluded_roots": [],
        "environment_allowlist": sorted(harness.invocation.env),
        "credential_environment": [],
        "input_identities": identities,
        "network": {
            "mode": spec.resources.network_mode,
            "allow": list(spec.resources.network_allow),
        },
        "archive_limit_bytes": spec.resources.archive_limit_bytes,
        "timeout_seconds": spec.resources.timeout_seconds,
        "executor": spec.executor.as_json(),
        # The frozen image identity is unchanged by preparation; the prepared subject
        # identity is carried as a bound input identity, not by mutating the image.
        "runtime": {"image": task.runtime.image},
    }


def _prepare_task(
    spec: ExperimentSpec,
    task: TaskSpec,
    workspace: Path,
    *,
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
    reference_repo = (
        Path(task.reference.repository) if task.reference.repository else repo
    )

    observed_base = _git(repo, "rev-parse", f"{task.source.base_commit}^{{tree}}")
    if observed_base != task.source.base_tree:
        blockers.append(
            {
                "task": task.id,
                "code": "base-tree-identity-mismatch",
                "detail": f"declared {task.source.base_tree}, resolved {observed_base}",
            }
        )
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

    base_dir = _materialize_verified(
        repo, task.source.base_tree, roots["subject"], "base", blockers, task.id
    )
    reference_dir = _materialize_verified(
        reference_repo,
        task.reference.tree,
        roots["subject"],
        "reference",
        blockers,
        task.id,
    )

    oracle_sha256 = digest_path(task.oracle_path)
    if task.oracle_sha256 and task.oracle_sha256 != oracle_sha256:
        blockers.append(
            {
                "task": task.id,
                "code": "oracle-identity-mismatch",
                "detail": f"declared {task.oracle_sha256}, observed {oracle_sha256}",
            }
        )

    key_sha256: str | None = None
    if task.identification_key_path is not None:
        if not task.identification_key_path.is_file():
            blockers.append(
                {
                    "task": task.id,
                    "code": "identification-key-missing",
                    "detail": f"{task.identification_key_path} is not present",
                }
            )
        else:
            key_sha256 = digest_path(task.identification_key_path)
            if (
                task.identification_key_sha256
                and task.identification_key_sha256 != key_sha256
            ):
                blockers.append(
                    {
                        "task": task.id,
                        "code": "identification-key-identity-mismatch",
                        "detail": "declared identification key digest does not match the file",
                    }
                )

    if base_dir is None or reference_dir is None:
        return TaskResult(
            id=task.id,
            adapter=task.adapter,
            base_tree=task.source.base_tree,
            reference_tree=task.reference.tree,
            runtime_image=task.runtime.image,
            oracle_sha256=oracle_sha256,
            identification_key_sha256=key_sha256,
            preparation=PreparationRequirement(required=False),
            test_config=TestConfig(source=None),
            semantic_identity=digest_of(task.semantic_payload()),
        )

    test_config = discover_test_config(base_dir)
    preparation = discover_preparation(base_dir)

    result = TaskResult(
        id=task.id,
        adapter=task.adapter,
        base_tree=task.source.base_tree,
        reference_tree=task.reference.tree,
        runtime_image=task.runtime.image,
        oracle_sha256=oracle_sha256,
        identification_key_sha256=key_sha256,
        preparation=preparation,
        test_config=test_config,
        semantic_identity=digest_of(task.semantic_payload()),
        base_path=base_dir,
        reference_path=reference_dir,
    )

    if preparation.required:
        _apply_task_preparation(
            task, result, repo, reference_repo, base_dir, reference_dir, blockers
        )

    adapter = adapters.get(task.adapter)
    projection: ConfigProjection | None = None
    if task.harness.isolate_test_config:
        projection = project_test_config(test_config, task.runtime.available_plugins)
        result.config_projection = projection
    harness = adapter.build(
        task,
        workspace_path="/workspace",
        oracle_name=task.oracle_path.name,
        test_config=test_config,
        projection=projection,
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

    profile = _runner_profile(spec, task, roots, result, harness)
    reasons = validate_profile_data(profile, for_run=True)
    if reasons:
        blockers.append(
            {
                "task": task.id,
                "code": "generated-profile-not-runnable",
                "detail": ",".join(reasons),
            }
        )
    result.runner_profile = profile
    result.capsule_identity = digest_of(result.as_json())
    return result


def _apply_task_preparation(
    task: TaskSpec,
    result: TaskResult,
    repo: Path,
    reference_repo: Path,
    base_dir: Path,
    reference_dir: Path,
    blockers: list[dict[str, object]],
) -> None:
    """Actually produce the declared build artifact, or block."""
    declared = {tool.name: tool for tool in task.runtime.preparation_tools}
    available: list[dict[str, object]] = []
    for name in result.preparation.tool_names:
        tool = declared.get(name)
        if tool is None:
            blockers.append(
                {
                    "task": task.id,
                    "code": "preparation-tool-undeclared",
                    "detail": (
                        f"the frozen tree needs {name!r} to generate "
                        f"{list(result.preparation.generated_paths)}; declare it under "
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

    if len(available) != len(result.preparation.tool_names):
        return
    if not task.preparation_scheme:
        blockers.append(
            {
                "task": task.id,
                "code": "preparation-scheme-undeclared",
                "detail": (
                    "a build-generated artifact is required but no preparation.scheme is "
                    "declared; the compiler does not choose a versioning scheme for you"
                ),
            }
        )
        return

    receipts: list[PreparationReceipt] = []
    try:
        for subject_dir, commit in (
            (base_dir, task.source.base_commit),
            (reference_dir, task.reference.commit or task.reference.tree),
        ):
            source_repo = repo if subject_dir is base_dir else reference_repo
            if all(
                (subject_dir / p).exists() for p in result.preparation.generated_paths
            ):
                continue
            receipts.append(
                apply_preparation(
                    subject_dir,
                    result.preparation,
                    repository=source_repo,
                    commit=commit,
                    scheme=task.preparation_scheme,
                )
            )
    except PreparationError as exc:
        blockers.append(
            {"task": task.id, "code": "preparation-failed", "detail": str(exc)}
        )
        return

    # The tracked tree must still reconstruct to its declared identity once the
    # generated artifact is ignored: preparation adds, it never edits the subject.
    observed = _observed_tree(repo, base_dir, ignore=result.preparation.generated_paths)
    if observed != task.source.base_tree:
        blockers.append(
            {
                "task": task.id,
                "code": "preparation-modified-tracked-source",
                "detail": f"tracked tree became {observed}, expected {task.source.base_tree}",
            }
        )
        return

    if receipts:
        result.preparation_receipt = receipts[0]
    result.prepared_runtime_identity = digest_of(
        {
            "base_image": task.runtime.image,
            "preparation": result.preparation.as_json(),
            "scheme": task.preparation_scheme,
            "tools": available,
            "receipts": [receipt.as_json() for receipt in receipts],
        }
    )


def _harness_json(task: TaskResult) -> dict[str, object] | None:
    harness = task.harness
    return harness.as_json() if harness is not None else None


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
        observed = digest_path(request.certificate_path)
        if observed != request.certificate_sha256:
            blockers.append(
                {
                    "task": None,
                    "code": "capability-certificate-identity-mismatch",
                    "detail": (
                        f"{request.capability}: certificate file digest {observed} does not "
                        f"match the declared {request.certificate_sha256}"
                    ),
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
        # Identities come from the request, never from the certificate itself.
        if certificate.satisfies(
            capability=request.capability,
            runtime_identity=request.required_runtime_identity,
            implementation_sha256=request.required_implementation_sha256,
            configuration_sha256=request.required_configuration_sha256,
            requested=request.requested_bounds,
        ):
            reused.append(
                {
                    "capability": request.capability,
                    "certificate_sha256": request.certificate_sha256,
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
                        f"{request.capability}: the certificate does not cover the declared "
                        f"identities or the requested {dict(request.requested_bounds)}; "
                        "requalify or block"
                    ),
                }
            )
    return reused


def prepare(
    spec: ExperimentSpec,
    workspace: str | Path,
    *,
    offline: bool = True,
    preflight_authority: PreflightAuthority | None = None,
    qualification_backend: str = LOCAL_PYTHON,
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

    def finish(stage: str) -> PrepareResult:
        result.blockers = blockers
        result.stage = stage
        result.status = (
            stages.READY_FOR_OWNER_REVIEW
            if stage == stages.READY_FOR_OWNER_REVIEW and not blockers
            else "BLOCKED"
        )
        result._identities = ledger.identities()
        result._receipts = ledger.receipts()
        result.reused_stages = list(ledger.reused)
        ledger.save()
        _write_state(root, result)
        return result

    ledger.enter(
        stages.DISCOVERED,
        {"spec": str(spec.source_path), "tasks": [t.id for t in spec.tasks]},
    )
    ledger.complete(stages.DISCOVERED, {"tasks": len(spec.tasks)})

    semantic_inputs = {task.id: task.semantic_payload() for task in spec.tasks}
    ledger.enter(stages.SEMANTIC_FROZEN, semantic_inputs)
    ledger.complete(
        stages.SEMANTIC_FROZEN,
        {task_id: digest_of(payload) for task_id, payload in semantic_inputs.items()},
    )

    tasks = {
        task.id: _prepare_task(spec, task, root, blockers=blockers)
        for task in spec.tasks
    }
    result.tasks = tasks

    ledger.enter(
        stages.RUNTIME_PREPARED,
        {
            task.id: {
                "runtime": task.runtime.as_json(),
                "source": {
                    "base_tree": task.source.base_tree,
                    "reference_tree": task.reference.tree,
                },
                "preparation": tasks[task.id].preparation.as_json(),
                "scheme": task.preparation_scheme,
            }
            for task in spec.tasks
        },
    )
    if blockers:
        return finish(stages.RUNTIME_PREPARED)
    ledger.complete(
        stages.RUNTIME_PREPARED,
        {
            task_id: {
                "prepared_runtime_identity": task.prepared_runtime_identity,
                "preparation_receipt": (
                    task.preparation_receipt.identity
                    if task.preparation_receipt
                    else None
                ),
            }
            for task_id, task in tasks.items()
        },
    )

    ledger.enter(
        stages.STATIC_QUALIFIED,
        {
            task.id: {
                "harness": _harness_json(tasks[task.id]),
                "oracle_sha256": tasks[task.id].oracle_sha256,
                "profile": tasks[task.id].runner_profile,
            }
            for task in spec.tasks
        },
    )
    ledger.complete(
        stages.STATIC_QUALIFIED,
        {task_id: task.capsule_identity for task_id, task in tasks.items()},
    )

    reused_certificates = _consume_certificates(spec, blockers)
    result.reused_certificates = reused_certificates
    if blockers:
        return finish(stages.STATIC_QUALIFIED)

    if preflight_authority is None:
        blockers.append(
            {
                "task": None,
                "code": "base-reference-qualification-requires-preflight-authority",
                "detail": (
                    "static preparation is complete; executing the declared oracle against BASE "
                    "and REFERENCE requires an explicit owner preflight authority naming this "
                    "experiment"
                ),
            }
        )
        return finish(stages.STATIC_QUALIFIED)

    if not preflight_authority.covers(spec.id, "base-reference-qualification"):
        blockers.append(
            {
                "task": None,
                "code": "preflight-authority-out-of-scope",
                "detail": (
                    f"authority {preflight_authority.id!r} covers experiment "
                    f"{preflight_authority.experiment_id!r} scopes "
                    f"{list(preflight_authority.scope)}, not base-reference-qualification for "
                    f"{spec.id!r}"
                ),
            }
        )
        return finish(stages.STATIC_QUALIFIED)

    ledger.enter(
        stages.BASE_REFERENCE_QUALIFIED,
        {
            "authority": preflight_authority.as_json(),
            "backend": qualification_backend,
            "capsules": {
                task_id: task.capsule_identity for task_id, task in tasks.items()
            },
        },
    )
    for task in spec.tasks:
        current = tasks[task.id]
        if current.base_path is None or current.reference_path is None:
            blockers.append(
                {
                    "task": task.id,
                    "code": "qualification-subject-unavailable",
                    "detail": "a materialised subject is missing; nothing can be qualified",
                }
            )
            continue
        outcome = qualify_subjects(
            task_id=task.id,
            backend=qualification_backend,
            base_tree=current.base_path,
            reference_tree=current.reference_path,
            oracle=task.oracle_path,
            import_roots=_IMPORT_ROOTS,
            expectations={
                "base": task.expectations.base,
                "reference": task.expectations.reference,
            },
            discriminator_cases=task.semantics.discriminator_cases,
        )
        if isinstance(outcome, list):
            blockers.extend(outcome)
            continue
        current.qualification = outcome
        if not outcome.qualified:
            blockers.append(
                {
                    "task": task.id,
                    "code": "base-reference-qualification-failed",
                    "detail": (
                        f"base {outcome.base.classification}: {outcome.base.detail}; "
                        f"reference {outcome.reference.classification}: {outcome.reference.detail}"
                    ),
                }
            )
    if blockers:
        return finish(stages.STATIC_QUALIFIED)
    ledger.complete(
        stages.BASE_REFERENCE_QUALIFIED,
        {
            task_id: task.qualification.identity
            for task_id, task in tasks.items()
            if task.qualification
        },
    )

    ledger.enter(
        stages.BOUNDARY_QUALIFIED,
        {"certificates": reused_certificates, "resources": spec.resources.as_json()},
    )
    ledger.complete(
        stages.BOUNDARY_QUALIFIED, {"certificates": len(reused_certificates)}
    )

    ledger.enter(
        stages.EXECUTION_FROZEN,
        {
            "capsules": {
                task_id: task.capsule_identity for task_id, task in tasks.items()
            },
            "launch": spec.launch_payload(),
        },
    )
    experiment_lock = lock_module.build(
        experiment_id=spec.id,
        question=spec.question,
        claim_boundary=spec.claim_boundary,
        launch=spec.launch_payload(),
        tasks=[task.as_json() for task in tasks.values()],
        capabilities=reused_certificates,
        stage_receipts=ledger.receipts(),
        authority=preflight_authority.as_json(),
    )
    try:
        result.lock_path = experiment_lock.write(root)
    except lock_module.LockError as exc:
        blockers.append(
            {"task": None, "code": "experiment-lock-conflict", "detail": str(exc)}
        )
        return finish(stages.BOUNDARY_QUALIFIED)
    result.lock_identity = experiment_lock.identity
    ledger.complete(stages.EXECUTION_FROZEN, {"lock_sha256": experiment_lock.identity})

    missing = ledger.missing_for_readiness()
    if missing:
        blockers.append(
            {
                "task": None,
                "code": "readiness-missing-stage-receipts",
                "detail": f"no completed receipt for {missing}",
            }
        )
        return finish(stages.EXECUTION_FROZEN)

    ledger.enter(
        stages.READY_FOR_OWNER_REVIEW, {"lock_sha256": experiment_lock.identity}
    )
    ledger.complete(
        stages.READY_FOR_OWNER_REVIEW, {"lock_sha256": experiment_lock.identity}
    )
    return finish(stages.READY_FOR_OWNER_REVIEW)


def _write_state(root: Path, result: PrepareResult) -> None:
    payload = {
        "schema": "gnostoa-capsule-state/v1",
        "producer": PRODUCER,
        "status": result.status,
        "stage": result.stage,
        "blockers": result.blockers,
        "reused_certificates": result.reused_certificates,
        "stage_receipts": result.stage_receipts(),
        "lock_sha256": result.lock_identity,
        "tasks": {task_id: task.as_json() for task_id, task in result.tasks.items()},
    }
    (root / STATE_FILENAME).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
    )


def status(workspace: str | Path) -> dict[str, Any]:
    root = Path(workspace).resolve()
    path = root / STATE_FILENAME
    if not path.is_file():
        return {
            "stage": stages.DISCOVERED,
            "status": "BLOCKED",
            "tasks": {},
            "blockers": [],
        }
    payload: dict[str, Any] = json.loads(path.read_text())
    return payload
