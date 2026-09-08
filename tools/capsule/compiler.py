"""Compile a declarative experiment specification into qualified capsules.

`prepare` performs mechanical preparation and qualification only. It returns either a
complete immutable lock or a structured BLOCKED result. It never acquires a
dependency, never repairs semantics, and never reports readiness for a stage whose
content-addressed receipt it does not hold.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import shutil
import stat
import subprocess
import tarfile
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, cast

from tools.capsule import (
    adapters,
    certificates,
    effect_claim,
    profiles,
    retained_commit,
    retained_preflight,
    runplan,
    stages,
)
from tools.capsule import lock as lock_module
from tools.capsule.adapters import HarnessResult, Invocation
from tools.capsule.authority import (
    BASE_REFERENCE_QUALIFICATION,
    PreflightAuthority,
    preflight_candidate_identity,
)
from tools.capsule.identity import PRODUCER, digest_of, digest_path, digest_text
from tools.capsule.oracle_qualification import qualify, read_shape
from tools.capsule.preparation import (
    SCM_COMPATIBLE_SCHEME,
    ConfigProjection,
    PreparationError,
    PreparationReceipt,
    PreparationRequirement,
    TestConfig,
    apply_preparation,
    declared_generated_paths,
    discover_preparation,
    discover_test_config,
    project_test_config,
)
from tools.capsule.qualification import (
    LOCAL_PYTHON,
    QualificationReceipt,
    ReceiptError,
    load_receipt,
    qualify_subjects,
)
from tools.capsule.spec import ExperimentSpec, TaskSpec
from tools.experiment.profile import validate_profile_data

STATE_FILENAME = "experiment-state.json"

#: Arbitration re-asks after each outcome it carries out. A workspace that
#: keeps changing under it is refused rather than spun on indefinitely.
_ARBITRATION_ROUNDS = 16

#: status re-reads when a commit lands between the state and the record it is
#: checked against. A workspace that will not hold still is reported, not guessed.
_STATUS_READ_ATTEMPTS = 8
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


def _frozen_tree_paths(repo: Path, tree: str) -> frozenset[str]:
    """Every path the frozen Git tree carries. The source of truth about absence."""
    listed = subprocess.run(
        ["git", "-C", str(repo), "ls-tree", "-r", "--name-only", tree],
        check=True,
        capture_output=True,
        text=True,
        env=_GIT_ENV,
    )
    return frozenset(line for line in listed.stdout.splitlines() if line)


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
                    # Index-only, and forced: without -f git refuses to drop a path
                    # whose staged content differs from HEAD, which silently left the
                    # generated artifact in the reconstructed tree whenever the same
                    # path happened to be tracked at HEAD.
                    "-f",
                    "-q",
                    "--ignore-unmatch",
                    *ignore,
                ],
                check=True,
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
        # A rerun sees the subject as preparation left it. This compiler's own
        # deterministic output is not evidence of tampering. But "declared by build
        # configuration" is not enough on its own: a declared path that the frozen
        # tree actually tracks is ordinary source, and excluding it would let a real
        # mutation hide. Exclude only paths that are both declared and provably
        # absent from the frozen tree, so tracked content stays fully verified.
        frozen = _frozen_tree_paths(repo, tree)
        generated = [
            path for path in declared_generated_paths(destination) if path not in frozen
        ]
        if generated:
            observed = _observed_tree(repo, destination, ignore=generated)
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


def _store_bytes(root: Path, payload: bytes) -> dict[str, str]:
    """Persist bytes content-addressed so a lock can be executed later."""
    store = root / "artifacts"
    store.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(payload).hexdigest()
    target = store / digest
    if target.is_file():
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise CompileError(f"artifact store entry {digest} does not match its name")
    else:
        target.write_bytes(payload)
    return {"sha256": digest, "store": f"artifacts/{digest}"}


def _store_artifact(root: Path, content: str) -> dict[str, str]:
    return _store_bytes(root, content.encode("utf-8"))


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
    qualification_profiles: dict[str, dict[str, Any]] = field(default_factory=dict)
    qualification_paths: dict[str, Path] = field(default_factory=dict)
    execution_profile: dict[str, Any] | None = None
    stored_artifacts: list[dict[str, str]] = field(default_factory=list)
    qualification: QualificationReceipt | None = None
    qualification_reused: bool = False
    source_repository: str = ""
    execution_command: tuple[str, ...] = ()
    execution_inputs: list[dict[str, str]] = field(default_factory=list)
    pending_execution_artifacts: list[tuple[str, str]] = field(default_factory=list)
    private_material: dict[str, dict[str, str]] = field(default_factory=dict)
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
            "source_repository": self.source_repository,
            "private_material": self.private_material,
            "qualification_invocation": (
                self.harness.invocation.as_json() if self.harness else None
            ),
            "execution_command": list(self.execution_command),
            "execution_inputs": list(self.execution_inputs),
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
            "stored_artifacts": list(self.stored_artifacts),
            "qualification_profiles": self.qualification_profiles,
            "execution_profile": self.execution_profile,
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
    # The exact prepared qualification request an owner authorises. Present once
    # static qualification is genuinely complete, so the digest can be approved
    # before any hidden-oracle effect; None while earlier blockers mean no
    # well-defined candidate exists yet.
    preflight_candidate_sha256: str | None = None
    run_plan: runplan.RunPlan | None = None
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


def _identities(result: TaskResult, harness: HarnessResult) -> list[str]:
    identities = [
        f"base-tree={digest_text(result.base_tree)}",
        f"oracle={result.oracle_sha256}",
        f"harness={harness.identity}",
    ]
    if result.identification_key_sha256:
        identities.append(f"identification-key={result.identification_key_sha256}")
    if result.preparation_receipt is not None:
        identities.append(f"preparation={result.preparation_receipt.identity}")
    if result.prepared_runtime_identity is not None:
        identities.append(f"prepared-runtime={result.prepared_runtime_identity}")
    return identities


def _build_profiles(
    spec: ExperimentSpec,
    task: TaskSpec,
    layout: Mapping[str, Path],
    result: TaskResult,
    harness: HarnessResult,
    blockers: list[dict[str, object]],
) -> None:
    """Build the coordinator-private qualification profile and the executor profile.

    They are distinct trust domains. The qualification profile may see the frozen
    reference and the hidden oracle; the execution profile must not, and is checked
    against an explicit forbidden-surface list before it is accepted.
    """
    common = profiles.ProfileCommon(
        image=task.runtime.image,
        # Qualification is a coordinator-run oracle check, not an experimental model
        # run; it must not be attributed to the experiment's executor.
        executor={
            "id": "gnostoa.capsule.qualification",
            "version": "1",
            "config_sha256": digest_text(PRODUCER),
        },
        timeout_seconds=spec.resources.timeout_seconds,
        archive_limit_bytes=spec.resources.archive_limit_bytes,
        # Forced, not defaulted, and not derived from spec.resources. Coordinator-
        # private qualification must never inherit experimental executor egress, so
        # no spec field can opt it into a network. A future qualification-network
        # capability would be designed and authorised separately.
        network={"mode": "none", "allow": []},
        environment_allowlist=tuple(sorted(harness.invocation.env)),
    )

    qualification_identities = [
        *_identities(result, harness),
        f"reference-tree={digest_text(result.reference_tree)}",
    ]
    result.qualification_profiles = {
        subject: profiles.build_profile(
            domain=profiles.QUALIFICATION,
            roots=profiles.ProfileRoots(
                project=layout[f"qualification_{subject}_project"],
                evidence=layout[f"qualification_{subject}_evidence"],
                temporary=layout[f"qualification_{subject}_tmp"],
            ),
            input_identities=qualification_identities,
            common=common,
        )
        for subject in ("base", "reference")
    }

    # The executor envelope is declared in the spec. Deriving it from the
    # qualification harness would take mechanics from the wrong trust domain.
    execution_common = profiles.ProfileCommon(
        image=task.runtime.image,
        executor=spec.executor.as_json(),
        timeout_seconds=spec.resources.timeout_seconds,
        archive_limit_bytes=spec.resources.archive_limit_bytes,
        network={
            "mode": spec.resources.network_mode,
            "allow": list(spec.resources.network_allow),
        },
        environment_allowlist=tuple(task.execution.environment_allowlist),
        credential_environment=tuple(task.execution.credential_environment),
        # Only a restricted envelope may carry one. A relay reaches the execution
        # profile because the runner needs it for egress; with no egress there is
        # nothing for it to serve, and passing it anyway would put an unused image
        # identity into the frozen lock.
        relay_image=(
            task.runtime.relay_image
            if spec.resources.network_mode == "restricted"
            else None
        ),
    )
    # The runner refuses a restricted profile without an immutable relay identity.
    # Say so in the spec's own terms rather than letting it surface later as an
    # opaque profile rejection. Nothing is discovered or defaulted to satisfy it.
    if (
        spec.resources.network_mode != "restricted"
        and task.runtime.relay_image is not None
    ):
        blockers.append(
            {
                "task": task.id,
                "code": "relay-image-requires-restricted-execution",
                "detail": (
                    "runtime.relay_image is declared while experimental execution network "
                    f"mode is {spec.resources.network_mode!r}; a relay serves restricted "
                    "egress only, so declaring one here would bind an image identity the "
                    "experiment never uses"
                ),
            }
        )
    if spec.resources.network_mode == "restricted" and task.runtime.relay_image is None:
        blockers.append(
            {
                "task": task.id,
                "code": "restricted-execution-requires-relay-image",
                "detail": (
                    "experimental execution declares network mode 'restricted', which the "
                    "runner serves through a relay; declare runtime.relay_image as an "
                    "immutable digest. It is never discovered, resolved or pulled"
                ),
            }
        )
    result.execution_profile = profiles.build_profile(
        domain=profiles.EXECUTION,
        roots=profiles.ProfileRoots(
            project=layout["execution_project"],
            evidence=layout["execution_evidence"],
            temporary=layout["execution_tmp"],
            read_only=tuple(
                layout["execution_inputs"] / item.id
                for item in task.execution.read_only_inputs
            ),
        ),
        input_identities=_identities(result, harness),
        common=execution_common,
    )

    forbidden = {
        "reference-subject": layout["subject"],
        "qualification-workspace": layout["qualification"],
    }
    if task.oracle_path.is_file():
        forbidden["hidden-oracle"] = task.oracle_path.resolve()
    if task.identification_key_path is not None:
        forbidden["identification-key"] = task.identification_key_path.resolve()
    try:
        profiles.assert_execution_boundary(result.execution_profile, forbidden)
    except profiles.ProfileBoundaryError as exc:
        blockers.append(
            {
                "task": task.id,
                "code": "execution-profile-admits-private-surface",
                "detail": str(exc),
            }
        )

    candidates = [
        (f"qualification-{k}", v) for k, v in result.qualification_profiles.items()
    ]
    candidates.append(("execution", result.execution_profile))
    for name, profile in candidates:
        reasons = validate_profile_data(profile, for_run=True)
        if reasons:
            blockers.append(
                {
                    "task": task.id,
                    "code": f"generated-{name}-profile-not-runnable",
                    "detail": ",".join(reasons),
                }
            )


def _prepare_task(
    spec: ExperimentSpec,
    task: TaskSpec,
    workspace: Path,
    *,
    blockers: list[dict[str, object]],
) -> TaskResult:
    task_root = (workspace / "tasks" / task.id).resolve()
    layout = {
        # coordinator-private: pristine materialisations plus the qualification run
        "subject": task_root / "subject",
        "qualification": task_root / "qualification",
        "qualification_base_project": task_root / "qualification" / "base" / "project",
        "qualification_base_evidence": task_root
        / "qualification"
        / "base"
        / "evidence",
        "qualification_base_tmp": task_root / "qualification" / "base" / "tmp",
        "qualification_reference_project": task_root
        / "qualification"
        / "reference"
        / "project",
        "qualification_reference_evidence": task_root
        / "qualification"
        / "reference"
        / "evidence",
        "qualification_reference_tmp": task_root
        / "qualification"
        / "reference"
        / "tmp",
        # executor-visible: a separate materialisation carrying the BASE subject only
        "execution": task_root / "execution",
        "execution_project": task_root / "execution" / "project",
        "execution_evidence": task_root / "execution" / "evidence",
        "execution_tmp": task_root / "execution" / "tmp",
        "execution_inputs": task_root / "execution" / "inputs",
    }
    for key, path in layout.items():
        if key not in {"subject", "qualification", "execution"}:
            path.mkdir(parents=True, exist_ok=True)
    layout["subject"].mkdir(parents=True, exist_ok=True)

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
        repo, task.source.base_tree, layout["subject"], "base", blockers, task.id
    )
    reference_dir = _materialize_verified(
        reference_repo,
        task.reference.tree,
        layout["subject"],
        "reference",
        blockers,
        task.id,
    )
    # The executor gets its own materialisation of BASE only. It is never a view of
    # the private subject directory, which also holds the known-correct reference.
    if not any(layout["execution_project"].iterdir()):
        _materialize(repo, task.source.base_tree, layout["execution_project"])

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
                    "detail": f"{task.identification_key_path} is not present locally",
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
    # The task needs preparation when *either* subject's frozen tree omits a declared
    # target. Asking BASE alone would miss the inverse case, where BASE already tracks
    # the target and only REFERENCE must be prepared: the requirement would read
    # false and preparation would never run for the subject that needs it. The
    # per-subject application below then decides where generation actually happens.
    base_preparation = discover_preparation(
        base_dir, frozen_paths=_frozen_tree_paths(repo, task.source.base_tree)
    )
    reference_preparation = discover_preparation(
        reference_dir,
        frozen_paths=_frozen_tree_paths(reference_repo, task.reference.tree),
    )
    preparation = _union_preparation(base_preparation, reference_preparation)

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
        source_repository=str(repo),
        execution_command=task.execution.command,
        # Private material is bound by identity and by an explicit owner-private
        # locator. The bytes never enter the lock.
        private_material={
            "oracle": {
                "sha256": oracle_sha256,
                "resolver": "owner-private",
                "locator": str(task.oracle_path),
            },
            **(
                {
                    "identification_key": {
                        "sha256": key_sha256 or "",
                        "resolver": "owner-private",
                        "locator": str(task.identification_key_path),
                    }
                }
                if task.identification_key_path is not None
                else {}
            ),
        },
    )

    if preparation.required:
        _apply_task_preparation(
            task, result, repo, reference_repo, base_dir, reference_dir, blockers
        )

    # Coordinator-private qualification workspace: a copy of BASE plus the oracle.
    # Kept apart from the pristine materialisation so tree verification stays honest,
    # and apart from the executor workspace so the oracle never reaches an executor.
    # The adapter owns the staged filename because the constraint belongs to its
    # runner, not to the experiment. BASE and REFERENCE use the same rule, so one
    # qualification is comparable with the other.
    adapter = adapters.get(task.adapter)
    staged_oracle_name = adapter.staged_oracle_name(
        oracle_sha256, task.oracle_path.name
    )
    oracle_bytes = task.oracle_path.read_bytes()
    for subject, source in (("base", base_dir), ("reference", reference_dir)):
        project = layout[f"qualification_{subject}_project"]
        if not any(project.iterdir()):
            shutil.copytree(source, project, dirs_exist_ok=True, symlinks=True)
        destination = project / staged_oracle_name
        # The staging destination is reserved. If the subject already occupies it,
        # refuse rather than overwrite subject content or quietly pick another name,
        # which would change what was qualified. lstat, so a symlink is judged as a
        # symlink: anything that is not a plain regular file is refused without ever
        # being followed, read or copied through.
        try:
            occupant = destination.lstat()
        except OSError:
            occupant = None
        if occupant is not None and not stat.S_ISREG(occupant.st_mode):
            blockers.append(
                {
                    "task": task.id,
                    "code": "oracle-staging-destination-occupied",
                    "detail": (
                        f"the reserved qualification staging path {staged_oracle_name!r} "
                        "exists in the subject and is not a regular file; refusing to "
                        "follow or replace it"
                    ),
                }
            )
            continue
        if occupant is not None and destination.read_bytes() != oracle_bytes:
            blockers.append(
                {
                    "task": task.id,
                    "code": "oracle-staging-destination-occupied",
                    "detail": (
                        f"the reserved qualification staging path {staged_oracle_name!r} "
                        "already exists in the subject with different bytes; refusing to "
                        "overwrite subject content"
                    ),
                }
            )
            continue
        shutil.copy2(task.oracle_path, destination)
        result.qualification_paths[subject] = project

    projection: ConfigProjection | None = None
    if task.harness.isolate_test_config:
        projection = project_test_config(test_config, task.runtime.available_plugins)
        result.config_projection = projection
    harness = adapter.build(
        task,
        workspace_path="/workspace",
        oracle_name=staged_oracle_name,
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

    for relative, content in result.pending_execution_artifacts:
        result.stored_artifacts.append(
            {
                "path": relative,
                "domain": profiles.EXECUTION,
                **_store_artifact(workspace, content),
            }
        )
    for generated in harness.generated_files:
        result.stored_artifacts.append(
            {
                "path": generated.path,
                "domain": profiles.QUALIFICATION,
                **_store_artifact(workspace, generated.content),
            }
        )
        for destination in (
            layout["qualification_base_project"],
            layout["qualification_reference_project"],
        ):
            if destination.is_dir():
                (destination / generated.path).write_text(generated.content)

    for item in task.execution.read_only_inputs:
        destination = layout["execution_inputs"] / item.id
        destination.mkdir(parents=True, exist_ok=True)
        if not item.source.is_file():
            blockers.append(
                {
                    "task": task.id,
                    "code": "execution-input-unavailable",
                    "detail": f"{item.id}: {item.source} is not present locally",
                }
            )
            continue
        observed = digest_path(item.source)
        if item.sha256 and item.sha256 != observed:
            blockers.append(
                {
                    "task": task.id,
                    "code": "execution-input-identity-mismatch",
                    "detail": f"{item.id}: declared {item.sha256}, observed {observed}",
                }
            )
            continue
        shutil.copy2(item.source, destination / item.source.name)
        # Bound into the lock as recoverable bytes, so the executor still receives the
        # declared input when the capsule is rematerialised at execute time.
        result.execution_inputs.append(
            {
                "id": item.id,
                "name": item.source.name,
                **_store_bytes(workspace, item.source.read_bytes()),
            }
        )

    _build_profiles(spec, task, layout, result, harness, blockers)
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
    if (
        task.preparation_scheme == SCM_COMPATIBLE_SCHEME
        and task.runtime.preparation_tools
    ):
        blockers.append(
            {
                "task": task.id,
                "code": "preparation-tool-not-used-by-scheme",
                "detail": (
                    f"{SCM_COMPATIBLE_SCHEME} is a Gnostoa-owned algorithm and consumes no "
                    "external artifact; declaring preparation_tools here would bind a "
                    "producer that cannot change the produced bytes"
                ),
            }
        )
        return
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
    # Each subject answers for its own frozen tree. A target the BASE tree omits may
    # be tracked source in the REFERENCE tree, and there it is ordinary content: it
    # must not be generated over, nor excluded from that subject's verification.
    subjects = (
        ("base", base_dir, task.source.base_commit, repo, task.source.base_tree),
        (
            "reference",
            reference_dir,
            task.reference.commit or task.reference.tree,
            reference_repo,
            task.reference.tree,
        ),
    )
    per_subject_generated: dict[str, tuple[str, ...]] = {}
    try:
        for kind, subject_dir, commit, source_repo, subject_tree in subjects:
            frozen = _frozen_tree_paths(source_repo, subject_tree)
            generated_here = tuple(
                path
                for path in result.preparation.generated_paths
                if path not in frozen
            )
            per_subject_generated[kind] = generated_here
            if not generated_here:
                # This subject already carries every declared target as tracked
                # source, so there is nothing to prepare and nothing to exclude.
                continue
            requirement = replace(result.preparation, generated_paths=generated_here)
            # A previous prepare may already have written this artifact. Verify and
            # reuse it rather than skipping, so the replay reproduces the same
            # receipt and identity instead of losing them.
            receipts.append(
                apply_preparation(
                    subject_dir,
                    requirement,
                    repository=source_repo,
                    commit=commit,
                    scheme=task.preparation_scheme,
                    allow_existing=True,
                )
            )
    except PreparationError as exc:
        blockers.append(
            {"task": task.id, "code": "preparation-failed", "detail": str(exc)}
        )
        return

    # Both tracked trees must still reconstruct to their declared identities once
    # that subject's own generated artifacts are ignored: preparation adds, it never
    # edits the subject. Verified per subject, because a reference-side edit is no
    # less a modification than a base-side one.
    for kind, subject_dir, _commit, source_repo, subject_tree in subjects:
        observed = _observed_tree(
            source_repo, subject_dir, ignore=list(per_subject_generated[kind])
        )
        if observed != subject_tree:
            blockers.append(
                {
                    "task": task.id,
                    "code": "preparation-modified-tracked-source",
                    "detail": (
                        f"{kind} tracked tree became {observed}, expected {subject_tree}"
                    ),
                }
            )
            return

    if receipts:
        result.preparation_receipt = receipts[0]
        # The executor materialises a pristine BASE, so any generated subject file the
        # subject needs to import must travel with the lock as an execution artifact.
        for relative in per_subject_generated["base"]:
            generated_file = base_dir / relative
            if generated_file.is_file():
                result.pending_execution_artifacts.append(
                    (relative, generated_file.read_text())
                )
    result.prepared_runtime_identity = digest_of(
        {
            "base_image": task.runtime.image,
            "preparation": result.preparation.as_json(),
            "scheme": task.preparation_scheme,
            "tools": available,
            "receipts": [receipt.as_json() for receipt in receipts],
        }
    )


def _union_preparation(
    base: PreparationRequirement, reference: PreparationRequirement
) -> PreparationRequirement:
    """One task-level requirement covering what either frozen tree omits.

    Union rather than intersection: a target missing from only one subject still has
    to be generated for that subject. Order is deterministic -- BASE's targets first,
    then any REFERENCE-only ones -- so the requirement, and every identity derived
    from it, is stable across replays.
    """
    if not base.required and not reference.required:
        return base
    targets = list(base.generated_paths)
    targets += [
        path for path in reference.generated_paths if path not in base.generated_paths
    ]
    primary = base if base.required else reference
    inference = list(base.inference)
    inference += [item for item in reference.inference if item not in inference]
    return replace(
        primary,
        required=True,
        generated_paths=tuple(targets),
        inference=tuple(inference),
    )


def _qualification_bound(task: TaskSpec, current: TaskResult) -> dict[str, str]:
    """The identities a qualification receipt must bind to stand in for this task."""
    harness = current.harness
    return {
        "base_tree": current.base_tree,
        "reference_tree": current.reference_tree,
        "oracle_sha256": current.oracle_sha256,
        "runtime_image": current.runtime_image,
        "harness_identity": harness.identity if harness else "",
        "expectations_digest": digest_of(task.expectations.as_json()),
        # The combined prepared identity, not the BASE receipt alone: it digests the
        # receipts for both subjects, so a reference-side preparation change cannot
        # leave a stale qualification looking current. Unprepared tasks keep "none".
        "preparation_identity": (current.prepared_runtime_identity or "none"),
    }


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


def _deterministic_pre_effect_blocker(
    task: TaskSpec,
    current: TaskResult,
    *,
    qualification_backend: str,
) -> dict[str, object] | None:
    """Return a deterministic refusal that proves this task cannot reach an effect.

    The real fresh-qualification path is the single place these guards run. A task
    whose authorised candidate binds exact prior-receipt reuse is consumed before
    this helper is called. Fresh effect claims are created only after all pre-effect
    work for the first actual fresh qualification has completed, immediately before
    ``qualify_subjects()``.
    """
    if qualification_backend == "oci" and task.adapter != "python-pytest":
        return {
            "task": task.id,
            "code": "oci-qualification-unsupported-for-adapter",
            "detail": (
                "the OCI result parser is pytest-specific; adapter "
                f"{task.adapter!r} has no OCI qualification support in v1"
            ),
        }
    if current.base_path is None or current.reference_path is None:
        return {
            "task": task.id,
            "code": "qualification-subject-unavailable",
            "detail": "a materialised subject is missing; nothing can be qualified",
        }
    return None


def prepare(
    spec: ExperimentSpec,
    workspace: str | Path,
    *,
    offline: bool = True,
    preflight_authority: PreflightAuthority | None = None,
    qualification_backend: str = LOCAL_PYTHON,
) -> PrepareResult:
    # The liveness lock a reservation is judged by is held for the whole
    # transaction, including an effect that raises. Releasing it on the return
    # paths alone would leave a crashed transaction looking alive forever.
    with contextlib.ExitStack() as transaction_stack:
        if not offline:
            raise CompileError(
                "online preparation is not implemented in v1; dependency acquisition is out of scope"
            )
        root = Path(workspace)
        root.mkdir(parents=True, exist_ok=True)
        root = root.resolve()
        blockers: list[dict[str, object]] = []
        result = PrepareResult(status="BLOCKED", stage=stages.DISCOVERED)
        ledger = stages.StageLedger(root=root)
        transaction_id = retained_commit.new_transaction_id()
        transaction_state: dict[str, object] = {"reserved": False}
        # Declared here, not at the effect loop: refusal paths that return before the
        # loop must still be able to tell whether this transaction crossed the
        # boundary, because that is what decides whether its reservation is
        # releasable.
        effect_claimed = False

        def _transaction_authority() -> str | None:
            recorded = transaction_state.get("authority_sha256")
            return recorded if isinstance(recorded, str) else None

        def refuse_without_persisting(code: str, detail: str) -> PrepareResult:
            """A retained-state refusal that writes nothing at all."""
            blockers.append({"task": None, "code": code, "detail": detail})
            result.blockers = blockers
            result.stage = stages.STATIC_QUALIFIED
            result.status = "BLOCKED"
            transaction_stack.close()
            return result

        # The snapshot and the record describing it are read together under the
        # coordination lock. Reading them separately lets an invocation pair an old
        # snapshot with a token another invocation has already advanced, after which any
        # equality check on that token passes and the stale write proceeds.
        try:
            with retained_commit.coordination_lock(root):
                # An interrupted transaction is finished forward before the workspace
                # it left behind is judged. Reading first would report the very
                # inconsistency recovery exists to resolve, and refuse on it.
                retained_commit.recover(root)
                base_snapshot = retained_commit.read_committed(root)
                ledger.load()
        except retained_commit.RetainedTransactionError as exc:
            return refuse_without_persisting(exc.code, exc.detail)

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

            staged_lock = transaction_state.get("staged_lock")
            lock_bytes = staged_lock if isinstance(staged_lock, bytes) else None

            # The whole output is made durable before any of it becomes canonical,
            # and the lock is published with the state that records it: an immutable
            # lock emitted outside the committing transaction survives a commit that
            # never happened and then refuses every later attempt to reach the same
            # readiness.
            try:
                staged = retained_commit.stage(
                    root,
                    transaction_id=transaction_id,
                    base_identity=_snapshot_identity(base_snapshot),
                    candidate_sha256=result.preflight_candidate_sha256,
                    authority_sha256=_transaction_authority(),
                    ledger=ledger.serialised().encode(),
                    state=_state_payload(result).encode(),
                    lock=lock_bytes,
                    lock_identity=result.lock_identity if lock_bytes else None,
                )
                with retained_commit.coordination_lock(root):
                    if transaction_state.get("reserved"):
                        # Commit this reservation to the bytes just staged, before
                        # any of them can become a recovery source.
                        retained_commit.seal_reservation(
                            root,
                            expected_transaction_id=transaction_id,
                            manifest_sha256=staged.manifest_sha256,
                        )
                    # Resolve what is in flight before deciding anything. This
                    # invocation's standing was settled earlier, and an interrupted
                    # publication may have appeared since; persisting on the strength
                    # of the older decision would overwrite the record of a commit
                    # that is the only route back to an effect already performed.
                    retained_commit.recover(root)
                    current = retained_commit.read_committed(root)
                    reservation = retained_commit.read_reservation(root)
                    held = bool(transaction_state.get("reserved"))
                    if (
                        reservation is not None
                        and reservation.transaction_id != transaction_id
                        and retained_commit.owner_is_live(root, reservation)
                    ):
                        # Another transaction holds the right to finish. Nothing this
                        # invocation did is irreversible, so it yields rather than
                        # writing over work that is still in flight.
                        return refuse_without_persisting(
                            retained_commit.TRANSACTION_RESERVED,
                            "another transaction holds the reservation for this "
                            "workspace; refusing to persist over an in-flight "
                            "transaction",
                        )
                    if _already_committed(current, staged):
                        # This transaction reproduced what is already committed. It
                        # has nothing to add, and publishing it would advance the
                        # committed history for work another transaction performed.
                        pass
                    elif not held and _snapshot_identity(current) != _snapshot_identity(
                        base_snapshot
                    ):
                        return refuse_without_persisting(
                            retained_commit.CONCURRENT_STATE_CHANGED,
                            "another invocation committed this workspace after the "
                            "retained state was read; refusing to overwrite newer "
                            "evidence with a stale snapshot",
                        )
                    else:
                        retained_commit.publish(
                            root,
                            staged=staged,
                            generation=(current.generation + 1 if current else 1),
                        )
                    if held:
                        retained_commit.clear_reservation(
                            root, expected_transaction_id=transaction_id
                        )
                        transaction_state["reserved"] = False
            except retained_commit.RetainedTransactionError as exc:
                return refuse_without_persisting(exc.code, exc.detail)
            transaction_stack.close()
            retained_commit.discard_staging(root, transaction_id)
            return result

        def finish_without_persisting(stage: str) -> PrepareResult:
            """Return a retained-evidence refusal without overwriting successful evidence."""
            result.blockers = blockers
            result.stage = stage
            result.status = "BLOCKED"
            result._identities = ledger.identities()
            result._receipts = ledger.receipts()
            result.reused_stages = list(ledger.reused)
            if transaction_state.get("reserved") and not effect_claimed:
                # Nothing irreversible happened under this reservation, so it is
                # released rather than left for the next caller to reason about.
                try:
                    with retained_commit.coordination_lock(root):
                        retained_commit.clear_reservation(
                            root, expected_transaction_id=transaction_id
                        )
                    transaction_state["reserved"] = False
                except retained_commit.RetainedTransactionError:
                    # A reservation that cannot be released is left alone: liveness
                    # is what tells the next caller it is abandoned.
                    pass
            # A post-claim refusal is not rolled back. The reservation is deliberately
            # left where a later caller can find it; releasing liveness is what marks
            # it as interrupted rather than in flight.
            transaction_stack.close()
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
            {
                task_id: digest_of(payload)
                for task_id, payload in semantic_inputs.items()
            },
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
                    "qualification_profiles": tasks[task.id].qualification_profiles,
                    "execution_profile": tasks[task.id].execution_profile,
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

        # What will actually happen per task, decided before the candidate is emitted.
        # Reading and validating a declared prior receipt is read-only, and it must be
        # settled here: approving subjects and a backend is not approval of an effect if
        # the same digest could stand for either running the hidden oracle or reusing a
        # receipt instead.
        resolved_priors: dict[str, QualificationReceipt] = {}
        candidate_tasks: list[dict[str, str]] = []
        for task in spec.tasks:
            current = tasks[task.id]
            entry = {"id": task.id, "capsule_identity": current.capsule_identity}
            if task.prior_qualification_receipt is None:
                entry["qualification_mode"] = "fresh"
                candidate_tasks.append(entry)
                continue
            try:
                prior = load_receipt(task.prior_qualification_receipt)
            except (ReceiptError, OSError, json.JSONDecodeError) as exc:
                blockers.append(
                    {
                        "task": task.id,
                        "code": "prior-qualification-receipt-invalid",
                        "detail": str(exc),
                    }
                )
                continue
            # A receipt earned through one backend is not evidence about another: the
            # hidden-oracle effect path differs, so it cannot stand in for this request.
            if prior.backend != qualification_backend:
                blockers.append(
                    {
                        "task": task.id,
                        "code": "prior-qualification-backend-mismatch",
                        "detail": (
                            f"the prior receipt was produced by backend {prior.backend!r}, but "
                            f"this request qualifies through {qualification_backend!r}; a receipt "
                            "from another backend cannot stand in for it"
                        ),
                    }
                )
                continue
            covers, mismatched = prior.covers(_qualification_bound(task, current))
            if not covers:
                blockers.append(
                    {
                        "task": task.id,
                        "code": "prior-qualification-receipt-not-current",
                        "detail": (
                            f"the receipt does not bind {mismatched or 'a qualified outcome'}; "
                            "requalify or remove the prior-qualification claim"
                        ),
                    }
                )
                continue
            resolved_priors[task.id] = prior
            entry["qualification_mode"] = "reuse"
            entry["prior_receipt_identity"] = prior.identity
            candidate_tasks.append(entry)

        if blockers:
            # A request whose disposition cannot be settled has no well-defined candidate,
            # so none is emitted: an owner must never approve a digest that misrepresents
            # what would run.
            return finish(stages.STATIC_QUALIFIED)

        # The exact request about to be authorised, computed here rather than after an
        # authority arrives, so an authority-less prepare can report the digest the
        # owner is being asked to approve. Task order is qualification order.
        candidate_sha256 = preflight_candidate_identity(
            experiment_id=spec.id,
            scope=BASE_REFERENCE_QUALIFICATION,
            qualification_backend=qualification_backend,
            tasks=tuple(candidate_tasks),
        )
        result.preflight_candidate_sha256 = candidate_sha256
        authority_sha256 = (
            digest_of(preflight_authority.as_json())
            if preflight_authority is not None
            else None
        )

        transaction_state["authority_sha256"] = authority_sha256

        def reload_retained() -> None:
            """Adopt what is committed now, keeping this invocation's own progress."""
            nonlocal base_snapshot
            with retained_commit.coordination_lock(root):
                # The transaction this invocation waited for may have died part way
                # through publishing. Reading first would meet that inconsistency and
                # refuse, when finishing it forward is exactly what waiting was for.
                retained_commit.recover(root)
                base_snapshot = retained_commit.read_committed(root)
                ledger.reused.clear()
                ledger.load()

        def arbitrate_transaction() -> PrepareResult | None:
            """Settle this invocation's standing before anything irreversible.

            Every decision -- wait for a live identical owner, refuse a different
            one, reconcile onto a transaction that landed meanwhile, release an
            abandonment that never crossed the boundary, finish forward one that did,
            or take the reservation -- is made by `arbitrate` from a single coherent
            read. This loop only carries out what it is told and asks again, because
            each outcome changes the workspace it was decided from.
            """
            nonlocal base_snapshot
            if authority_sha256 is not None:
                # Liveness first and separately: it makes this transaction
                # observable, and confers no right to write by itself.
                transaction_stack.enter_context(
                    retained_commit.owner_liveness(root, transaction_id)
                )
            for _ in range(_ARBITRATION_ROUNDS):
                try:
                    decision = retained_commit.arbitrate(
                        root,
                        transaction_id=transaction_id,
                        base_identity=_snapshot_identity(base_snapshot),
                        experiment_id=spec.id,
                        scope=BASE_REFERENCE_QUALIFICATION,
                        candidate_sha256=candidate_sha256,
                        authority_sha256=authority_sha256,
                    )
                    if decision.action == retained_commit.TAKE:
                        base_snapshot = decision.snapshot
                        transaction_state["reserved"] = authority_sha256 is not None
                        return None
                    if decision.action == retained_commit.WAIT:
                        assert decision.reservation is not None
                        retained_commit.wait_for_owner(root, decision.reservation)
                        reload_retained()
                        continue
                    if decision.action == retained_commit.RECONCILE:
                        reload_retained()
                        continue
                    return refuse_without_persisting(
                        retained_commit.TRANSACTION_RESERVED, decision.detail
                    )
                except retained_commit.RetainedTransactionError as exc:
                    return refuse_without_persisting(exc.code, exc.detail)
            return refuse_without_persisting(
                retained_commit.INCONSISTENT_STATE,
                "the retained workspace kept changing under arbitration; refusing to "
                "act on a state that will not settle",
            )

        arbitrated = arbitrate_transaction()
        if arbitrated is not None:
            return arbitrated

        preserve_completed_candidate = False
        existing_qualification = ledger.records.get(stages.BASE_REFERENCE_QUALIFIED)
        if existing_qualification is not None and existing_qualification.complete:
            try:
                preserve_completed_candidate = (
                    retained_preflight.matching_completed_candidate_stage(
                        root,
                        ledger,
                        candidate_sha256=candidate_sha256,
                    )
                    is not None
                    # The candidate proves the qualification transaction is the same one.
                    # It says nothing about the downstream material the lock also binds,
                    # so an unchanged candidate alone must not keep an old READY and its
                    # lock presented as current after that material has drifted.
                    and retained_preflight.retained_lock_material_matches(
                        root,
                        experiment_id=spec.id,
                        question=spec.question,
                        claim_boundary=spec.claim_boundary,
                        launch=spec.launch_payload(),
                        capabilities=reused_certificates,
                        artifact_store=str(root / "artifacts"),
                    )
                )
            except retained_preflight.RetainedPreflightError:
                # A completed qualification whose retained public state cannot be safely
                # matched is forensic evidence. An authority refusal must not rewrite it;
                # a later authorised replay will surface the retained-integrity blocker.
                preserve_completed_candidate = True

        def finish_preserving(stage: str) -> PrepareResult:
            """Refuse without replacing retained evidence that may still be current.

            ``preserve_completed_candidate`` is set when a completed qualification is
            retained here and nothing has shown it to be stale -- including the case
            where the retained lock cannot be compared at all, which is ambiguity
            rather than proof of drift. Publishing a refusal over that would destroy
            a completed success on the strength of a question nobody answered.
            """
            if preserve_completed_candidate:
                return finish_without_persisting(stage)
            return finish(stage)

        def finish_authority_refusal() -> PrepareResult:
            return finish_preserving(stages.STATIC_QUALIFIED)

        if preflight_authority is None:
            blockers.append(
                {
                    "task": None,
                    "code": "base-reference-qualification-requires-preflight-authority",
                    "detail": (
                        "static preparation is complete; executing the declared oracle against "
                        "BASE and REFERENCE requires an explicit owner preflight authority "
                        f"naming preflight candidate {candidate_sha256}"
                    ),
                }
            )
            return finish_authority_refusal()

        if not preflight_authority.covers(
            spec.id, BASE_REFERENCE_QUALIFICATION, candidate_sha256=candidate_sha256
        ):
            # Distinguish the two refusals: a wrong experiment or scope is a different
            # mistake from an authority issued against a candidate that has since changed.
            if (
                preflight_authority.experiment_id != spec.id
                or BASE_REFERENCE_QUALIFICATION not in preflight_authority.scope
            ):
                blockers.append(
                    {
                        "task": None,
                        "code": "preflight-authority-out-of-scope",
                        "detail": (
                            f"authority {preflight_authority.id!r} covers experiment "
                            f"{preflight_authority.experiment_id!r} scopes "
                            f"{list(preflight_authority.scope)}, not "
                            f"{BASE_REFERENCE_QUALIFICATION} for {spec.id!r}"
                        ),
                    }
                )
            else:
                blockers.append(
                    {
                        "task": None,
                        "code": "preflight-authority-candidate-mismatch",
                        "detail": (
                            f"authority {preflight_authority.id!r} approves preflight candidate "
                            f"{preflight_authority.preflight_candidate_sha256}, but this prepared "
                            f"request is {candidate_sha256}; the qualification inputs or backend "
                            "changed since the authority was issued, so it is refused before any "
                            "oracle runs"
                        ),
                    }
                )
            return finish_authority_refusal()

        qualification_stage_inputs: dict[str, object] = {
            "authority": preflight_authority.as_json(),
            # Recorded from what this run computed, not copied from the authority, so
            # the evidence shows the executed request independently of the approval it
            # was matched against. Equality above is what makes them agree.
            "preflight_candidate_sha256": candidate_sha256,
            "authorised_candidate_sha256": preflight_authority.preflight_candidate_sha256,
            "backend": qualification_backend,
            "capsules": {
                task_id: task.capsule_identity for task_id, task in tasks.items()
            },
        }
        completed_qualification = retained_preflight.matching_completed_stage(
            ledger, qualification_stage_inputs
        )
        if completed_qualification is None:
            try:
                completed_qualification = (
                    retained_preflight.matching_completed_candidate_stage(
                        root,
                        ledger,
                        candidate_sha256=candidate_sha256,
                    )
                )
            except retained_preflight.RetainedPreflightError as exc:
                blockers.append(
                    {
                        "task": None,
                        "code": retained_preflight.INVALID_RETAINED_QUALIFICATION,
                        "detail": str(exc),
                    }
                )
                return finish_without_persisting(stages.STATIC_QUALIFIED)

        qualification_reused = completed_qualification is not None
        if completed_qualification is not None:
            has_fresh_task = any(
                entry.get("qualification_mode") == "fresh" for entry in candidate_tasks
            )
            if has_fresh_task:
                try:
                    consumed = effect_claim.load_consumed_candidate(
                        root,
                        experiment_id=spec.id,
                        scope=BASE_REFERENCE_QUALIFICATION,
                        candidate_sha256=candidate_sha256,
                        candidate_tasks=tuple(candidate_tasks),
                    )
                except effect_claim.EffectClaimError as exc:
                    blockers.append(
                        {"task": None, "code": exc.code, "detail": exc.detail}
                    )
                    return finish_without_persisting(stages.STATIC_QUALIFIED)

                if consumed.get("authority_sha256") != digest_of(
                    preflight_authority.as_json()
                ):
                    blockers.append(
                        {
                            "task": None,
                            "code": effect_claim.ALREADY_CONSUMED,
                            "detail": (
                                f"preflight candidate {candidate_sha256} completed under a "
                                "different authority; issuing another authority does not reopen "
                                "or replace the retained transaction"
                            ),
                        }
                    )
                    return finish_without_persisting(stages.STATIC_QUALIFIED)

            try:
                restored = retained_preflight.load_completed_qualifications(
                    root,
                    candidate_sha256=candidate_sha256,
                    stage_record=completed_qualification,
                    task_ids=tuple(task.id for task in spec.tasks),
                )
            except retained_preflight.RetainedPreflightError as exc:
                blockers.append(
                    {
                        "task": None,
                        "code": retained_preflight.INVALID_RETAINED_QUALIFICATION,
                        "detail": str(exc),
                    }
                )
                return finish_without_persisting(stages.STATIC_QUALIFIED)

            for task in spec.tasks:
                current = tasks[task.id]
                receipt = restored[task.id]
                if receipt.backend != qualification_backend:
                    blockers.append(
                        {
                            "task": task.id,
                            "code": retained_preflight.INVALID_RETAINED_QUALIFICATION,
                            "detail": (
                                f"retained qualification backend {receipt.backend!r} does not "
                                f"match current backend {qualification_backend!r}"
                            ),
                        }
                    )
                    continue
                covers, mismatched = receipt.covers(_qualification_bound(task, current))
                if not covers:
                    blockers.append(
                        {
                            "task": task.id,
                            "code": retained_preflight.INVALID_RETAINED_QUALIFICATION,
                            "detail": (
                                "retained qualification is no longer current for "
                                f"{mismatched or 'the qualified outcome'}"
                            ),
                        }
                    )
                    continue
                current.qualification = receipt
                current.qualification_reused = True
            if blockers:
                return finish_without_persisting(stages.STATIC_QUALIFIED)
            if stages.BASE_REFERENCE_QUALIFIED not in ledger.reused:
                ledger.reused.append(stages.BASE_REFERENCE_QUALIFIED)

        if not qualification_reused:
            ledger.enter(stages.BASE_REFERENCE_QUALIFIED, qualification_stage_inputs)
            for task in spec.tasks:
                current = tasks[task.id]

                # The disposition was settled before the candidate was emitted and the owner
                # authorised that exact digest. Exact prior reuse is zero-effect, so consume it
                # before checks which exist only to admit fresh qualification execution.
                approved_prior = resolved_priors.get(task.id)
                if approved_prior is not None:
                    current.qualification = approved_prior
                    current.qualification_reused = True
                    continue

                guard = _deterministic_pre_effect_blocker(
                    task, current, qualification_backend=qualification_backend
                )
                if guard is not None:
                    blockers.append(guard)
                    continue
                harness = current.harness
                bound = _qualification_bound(task, current)
                # The helper above is the sole runtime check for subject availability;
                # these casts preserve that proven invariant for static type checking
                # without duplicating the guard conditions here.
                base_path = cast(Path, current.base_path)
                reference_path = cast(Path, current.reference_path)

                # No effect-bearing operation has started while the claim is absent. If
                # any earlier task or future pre-effect refusal accumulated a blocker,
                # stop before consuming the candidate. Once the claim succeeds, the very
                # next top-level operation is the first actual qualification effect.
                if blockers and not effect_claimed:
                    return finish(stages.STATIC_QUALIFIED)
                if not effect_claimed:
                    try:
                        effect_claim.claim_fresh_candidate(
                            root,
                            experiment_id=spec.id,
                            scope=BASE_REFERENCE_QUALIFICATION,
                            candidate_sha256=candidate_sha256,
                            authority=preflight_authority,
                            candidate_tasks=tuple(candidate_tasks),
                        )
                    except effect_claim.EffectClaimError as exc:
                        blockers.append(
                            {"task": None, "code": exc.code, "detail": exc.detail}
                        )
                        return finish_without_persisting(stages.STATIC_QUALIFIED)
                    effect_claimed = True

                outcome = qualify_subjects(
                    task_id=task.id,
                    backend=qualification_backend,
                    base_tree=current.qualification_paths.get("base", base_path),
                    reference_tree=current.qualification_paths.get(
                        "reference", reference_path
                    ),
                    oracle=task.oracle_path,
                    import_roots=_IMPORT_ROOTS,
                    subject_profiles=current.qualification_profiles or None,
                    argv=list(harness.invocation.argv) if harness else None,
                    bound=bound,
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
                                f"reference {outcome.reference.classification}: "
                                f"{outcome.reference.detail}"
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
            {
                "certificates": reused_certificates,
                "resources": spec.resources.as_json(),
            },
        )
        ledger.complete(
            stages.BOUNDARY_QUALIFIED, {"certificates": len(reused_certificates)}
        )

        for task in spec.tasks:
            if not task.execution.command:
                blockers.append(
                    {
                        "task": task.id,
                        "code": "execution-command-required-for-freeze",
                        "detail": (
                            "a lock reported READY_FOR_OWNER_REVIEW must already be executable; "
                            "declare execution.command, which is never inferred from the "
                            "qualification invocation"
                        ),
                    }
                )
        if blockers:
            return finish(stages.BOUNDARY_QUALIFIED)

        # What runs, and in what order, is preregistered experiment material. If arms are
        # declared, an explicit schedule is required: a default ordering would silently
        # stand in for material the owner is supposed to have frozen.
        if spec.arms and not spec.assignment.schedule:
            blockers.append(
                {
                    "task": None,
                    "code": "assignment-schedule-required",
                    "detail": (
                        "arms are declared but experiment.assignment carries no ordered schedule; "
                        "declare assignment.schedule inline or bind assignment.schedule_artifact "
                        "with its sha256. The compiler never derives assignment order."
                    ),
                }
            )
            return finish(stages.BOUNDARY_QUALIFIED)

        scheduled_arms = list(spec.assignment.arms) or ["default"]
        schedule = [entry.as_json() for entry in spec.assignment.schedule] or [
            {"task": task.id, "repetition": repetition, "arm": "default"}
            for task in spec.tasks
            for repetition in range(1, spec.assignment.repetitions + 1)
        ]
        # A frozen order is not enough: it must be exactly the preregistered set of runs.
        schedule_reasons = runplan.validate_schedule(
            schedule=schedule,
            task_ids=[task.id for task in spec.tasks],
            arms=scheduled_arms,
            repetitions=spec.assignment.repetitions,
        )
        if schedule_reasons:
            blockers.append(
                {
                    "task": None,
                    "code": "assignment-schedule-not-a-complete-permutation",
                    "detail": (
                        "the schedule must be exactly one permutation of "
                        "tasks x repetitions x arms: " + "; ".join(schedule_reasons)
                    ),
                }
            )
            return finish(stages.BOUNDARY_QUALIFIED)

        plan = runplan.compile_plan(
            schedule=schedule,
            schedule_source=spec.assignment.source,
            schedule_sha256=spec.assignment.schedule_sha256,
            arm_inputs={
                arm.name: [
                    {
                        "id": item.id,
                        "sha256": item.sha256 or "",
                        "source": str(item.source),
                    }
                    for item in arm.inputs
                ]
                for arm in spec.arms
            },
        )
        result.run_plan = plan

        ledger.enter(
            stages.EXECUTION_FROZEN,
            {
                "capsules": {
                    task_id: task.capsule_identity for task_id, task in tasks.items()
                },
                "launch": spec.launch_payload(),
                "run_plan": plan.identity,
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
            run_plan=plan.as_json(),
            artifact_store=str(root / "artifacts"),
        )
        try:
            transaction_state["staged_lock"] = experiment_lock.stage(root)
        except lock_module.LockError as exc:
            blockers.append(
                {"task": None, "code": "experiment-lock-conflict", "detail": str(exc)}
            )
            # A lock this preparation cannot reconcile with is the same ambiguity one
            # step later: either the retained lock is damaged or the material drifted,
            # and the conflict alone does not say which. When a completed
            # qualification is retained and nothing has shown it stale, the refusal is
            # reported without publishing over it.
            return finish_preserving(stages.BOUNDARY_QUALIFIED)
        result.lock_path = root / lock_module.LOCK_FILENAME
        result.lock_identity = experiment_lock.identity
        ledger.complete(
            stages.EXECUTION_FROZEN, {"lock_sha256": experiment_lock.identity}
        )

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


def _snapshot_identity(
    snapshot: retained_commit.CommittedSnapshot | None,
) -> str | None:
    """A comparable identity for a committed snapshot, or None if none was made."""
    return snapshot.identity if snapshot is not None else None


def _already_committed(
    current: retained_commit.CommittedSnapshot | None,
    staged: retained_commit.StagedTransaction,
) -> bool:
    """Whether publishing this staged output would change nothing at all.

    A transaction that stages no lock leaves the published one where it is, so it
    cannot differ from what is committed on that account.
    """
    if current is None:
        return False
    return (
        current.stages_sha256 == staged.stages_file_sha256
        and current.state_sha256 == staged.state_file_sha256
        and (
            staged.lock_file_sha256 is None
            or current.lock_file_sha256 == staged.lock_file_sha256
        )
    )


def _state_payload(result: PrepareResult) -> str:
    """The public state as it is persisted, without persisting it."""
    payload = {
        "schema": "gnostoa-capsule-state/v1",
        "producer": PRODUCER,
        "status": result.status,
        "stage": result.stage,
        "blockers": result.blockers,
        "reused_certificates": result.reused_certificates,
        "stage_receipts": result.stage_receipts(),
        "lock_sha256": result.lock_identity,
        "preflight_candidate_sha256": result.preflight_candidate_sha256,
        "tasks": {task_id: task.as_json() for task_id, task in result.tasks.items()},
        # Self-declares that this state was written under a retained transaction, so
        # a later reader can tell a workspace that never had a commit record from one
        # whose record was removed.
        retained_commit.TRANSACTION_MARKER_FIELD: (
            retained_commit.TRANSACTION_MARKER_VALUE
        ),
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


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
    # The state file asserts a readiness; the commit record says which files that
    # assertion was made about. A lock that is canonically valid but is not the one
    # the successful transaction recorded would otherwise be presented as current,
    # so provenance is checked here rather than trusted. Nothing is rewritten: a
    # workspace that disagrees with its record is evidence, and reporting it BLOCKED
    # is a read, not a repair. A workspace with no record at all predates the
    # transaction model and is reported as it always was.
    #
    # The payload returned must be the one the validated record vouches for. Reading
    # the state and then validating the record are two moments, and a perfectly
    # legitimate concurrent commit in between would leave this reporting the
    # readiness of a snapshot it did not check. The record binds the state digest,
    # so agreement is established rather than assumed, and a commit that lands mid
    # read is simply read again.
    payload: dict[str, Any] = {}
    refusal: retained_commit.RetainedTransactionError | None = None
    for _ in range(_STATUS_READ_ATTEMPTS):
        try:
            raw = path.read_bytes()
        except FileNotFoundError:  # pragma: no cover - removed mid-read
            return {
                "stage": stages.DISCOVERED,
                "status": "BLOCKED",
                "tasks": {},
                "blockers": [],
            }
        payload = json.loads(raw)
        try:
            snapshot = retained_commit.read_committed(root)
        except retained_commit.RetainedTransactionError as exc:
            refusal = exc
            break
        refusal = None
        if snapshot is None or snapshot.state_sha256 == hashlib.sha256(raw).hexdigest():
            break
    else:
        refusal = retained_commit.RetainedTransactionError(
            retained_commit.INCONSISTENT_STATE,
            "the retained workspace kept changing while it was being read; refusing "
            "to report a state no committed snapshot vouches for",
        )
    if refusal is not None:
        payload["status"] = "BLOCKED"
        payload["blockers"] = [
            *payload.get("blockers", []),
            {"task": None, "code": refusal.code, "detail": refusal.detail},
        ]
    return payload
