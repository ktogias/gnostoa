"""Declarative experiment specification.

The spec states intent. Everything mechanical -- Dockerfiles, harness files,
runner profiles, locks -- is derived from it. Ambiguity is rejected rather than
guessed: the compiler never invents an adapter, a reference or an expectation.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

SPEC_SCHEMA = "gnostoa-experiment-spec/v1"

# Mirrors the immutable image syntax tools/experiment/profile.py already enforces.
# Declared here so a malformed relay identity is refused at spec load rather than
# surfacing later as an opaque runner rejection.
IMMUTABLE_IMAGE_RE = re.compile(r"^(?:sha256:[a-f0-9]{64}|.+@sha256:[a-f0-9]{64})$")
ADAPTERS = frozenset({"python-pytest", "node-vitest", "generic-command"})
REFERENCE_KINDS = frozenset(
    {
        "accepted-merge-commit",
        "accepted-squash-merge-commit",
        "accepted-pr-head",
        "rederived-reference-tree",
    }
)


class SpecError(ValueError):
    """The specification is unusable and must not be repaired by inference."""


def _require(mapping: Mapping[str, Any], key: str, where: str) -> Any:
    if key not in mapping:
        raise SpecError(f"{where}: missing required field {key!r}")
    return mapping[key]


def _require_str(mapping: Mapping[str, Any], key: str, where: str) -> str:
    value = _require(mapping, key, where)
    if not isinstance(value, str) or not value:
        raise SpecError(f"{where}: {key!r} must be a non-empty string")
    return value


@dataclass(frozen=True, slots=True)
class Corroboration:
    """Where a control's expected behaviour is already evidenced.

    Either by citation into the frozen base tree, or by a prior qualification of
    the exact same oracle, base and reference identities.
    """

    path: str | None = None
    symbol: str | None = None
    value_substitutions: Mapping[str, str] = field(default_factory=dict)
    prior_qualification_sha256: str | None = None

    def as_json(self) -> dict[str, object]:
        return {
            "path": self.path,
            "symbol": self.symbol,
            "value_substitutions": dict(self.value_substitutions),
            "prior_qualification_sha256": self.prior_qualification_sha256,
        }


@dataclass(frozen=True, slots=True)
class Control:
    case: str
    corroboration: Corroboration | None

    def as_json(self) -> dict[str, object]:
        return {
            "case": self.case,
            "corroboration": self.corroboration.as_json()
            if self.corroboration
            else None,
        }


@dataclass(frozen=True, slots=True)
class Semantics:
    """The semantic freeze payload: authored, never inferred."""

    requirement: str
    discriminator_cases: tuple[str, ...]
    behavior_paths: tuple[str, ...]
    controls: tuple[Control, ...]

    def as_json(self) -> dict[str, object]:
        return {
            "requirement": self.requirement,
            "discriminator": {
                "cases": list(self.discriminator_cases),
                "behavior_paths": list(self.behavior_paths),
            },
            "controls": [control.as_json() for control in self.controls],
        }


@dataclass(frozen=True, slots=True)
class Harness:
    """Mechanical invocation adaptation. Never semantic."""

    preload_modules: tuple[str, ...] = ()
    isolate_test_config: bool = False
    extra_argv: tuple[str, ...] = ()

    def as_json(self) -> dict[str, object]:
        return {
            "preload_modules": list(self.preload_modules),
            "isolate_test_config": self.isolate_test_config,
            "extra_argv": list(self.extra_argv),
        }


@dataclass(frozen=True, slots=True)
class PreparationTool:
    name: str
    artifact: str

    def as_json(self) -> dict[str, object]:
        return {"name": self.name, "artifact": self.artifact}


@dataclass(frozen=True, slots=True)
class Runtime:
    image: str
    available_plugins: tuple[str, ...] = ()
    preparation_tools: tuple[PreparationTool, ...] = ()
    # The runner requires an immutable relay identity whenever experimental
    # execution is network-restricted. It is declared, never discovered: no tag
    # is resolved to a digest and no image is fetched.
    relay_image: str | None = None

    def as_json(self) -> dict[str, object]:
        return {
            "image": self.image,
            "available_plugins": list(self.available_plugins),
            "preparation_tools": [tool.as_json() for tool in self.preparation_tools],
            "relay_image": self.relay_image,
        }


@dataclass(frozen=True, slots=True)
class Source:
    repository: str
    base_commit: str
    base_tree: str


@dataclass(frozen=True, slots=True)
class Reference:
    kind: str
    commit: str | None
    tree: str
    repository: str | None = None


@dataclass(frozen=True, slots=True)
class Expectations:
    base: Mapping[str, int]
    reference: Mapping[str, int]

    def as_json(self) -> dict[str, object]:
        return {"base": dict(self.base), "reference": dict(self.reference)}


@dataclass(frozen=True, slots=True)
class ExecutionInput:
    """A read-only surface the experimental executor is meant to see."""

    id: str
    source: Path
    sha256: str | None = None

    def as_json(self) -> dict[str, object]:
        return {"id": self.id, "source": str(self.source), "sha256": self.sha256}


@dataclass(frozen=True, slots=True)
class ExecutionEnvelope:
    """Executor mechanics, declared separately from qualification mechanics."""

    command: tuple[str, ...] = ()
    environment_allowlist: tuple[str, ...] = ()
    credential_environment: tuple[str, ...] = ()
    read_only_inputs: tuple[ExecutionInput, ...] = ()

    def as_json(self) -> dict[str, object]:
        return {
            "command": list(self.command),
            "environment_allowlist": list(self.environment_allowlist),
            "credential_environment": list(self.credential_environment),
            "read_only_inputs": [item.as_json() for item in self.read_only_inputs],
        }


@dataclass(frozen=True, slots=True)
class Arm:
    """One experimental arm and the packet only that arm may see."""

    name: str
    inputs: tuple[ExecutionInput, ...] = ()

    def as_json(self) -> dict[str, object]:
        return {"name": self.name, "inputs": [item.as_json() for item in self.inputs]}


@dataclass(frozen=True, slots=True)
class ScheduleEntry:
    task: str
    repetition: int
    arm: str

    def as_json(self) -> dict[str, object]:
        return {"task": self.task, "repetition": self.repetition, "arm": self.arm}


@dataclass(frozen=True, slots=True)
class Assignment:
    """The preregistered ordered schedule, never re-derived by the compiler."""

    repetitions: int = 1
    arms: tuple[str, ...] = ()
    schedule: tuple[ScheduleEntry, ...] = ()
    source: str = "none"
    schedule_sha256: str | None = None

    def as_json(self) -> dict[str, object]:
        return {
            "repetitions": self.repetitions,
            "arms": list(self.arms),
            "source": self.source,
            "schedule_sha256": self.schedule_sha256,
            "schedule": [entry.as_json() for entry in self.schedule],
        }


@dataclass(frozen=True, slots=True)
class TaskSpec:
    id: str
    adapter: str
    source: Source
    reference: Reference
    runtime: Runtime
    oracle_path: Path
    oracle_sha256: str | None
    identification_key_path: Path | None
    semantics: Semantics
    harness: Harness
    expectations: Expectations
    preparation_scheme: str | None = None
    identification_key_sha256: str | None = None
    prior_qualification_sha256: str | None = None
    prior_qualification_receipt: Path | None = None
    execution: ExecutionEnvelope = field(default_factory=ExecutionEnvelope)

    def semantic_payload(self) -> dict[str, object]:
        """Exactly the semantic freeze inputs: no mechanics, no runtime."""
        return {
            "task": self.id,
            "requirement": self.semantics.requirement,
            "discriminator": {
                "cases": list(self.semantics.discriminator_cases),
                "behavior_paths": list(self.semantics.behavior_paths),
            },
            "controls": [control.as_json() for control in self.semantics.controls],
            "reference_contract": {"kind": self.reference.kind},
            "expectations": self.expectations.as_json(),
        }


@dataclass(frozen=True, slots=True)
class Executor:
    """Executor identity required by the runner profile."""

    id: str
    version: str
    config_sha256: str
    model: str | None = None
    small_model: str | None = None

    def as_json(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "id": self.id,
            "version": self.version,
            "config_sha256": self.config_sha256,
        }
        if self.model:
            payload["model"] = self.model
        if self.small_model:
            payload["small_model"] = self.small_model
        return payload


@dataclass(frozen=True, slots=True)
class Resources:
    timeout_seconds: int
    archive_limit_bytes: int
    network_mode: str
    network_allow: tuple[str, ...] = ()

    def as_json(self) -> dict[str, object]:
        return {
            "timeout_seconds": self.timeout_seconds,
            "archive_limit_bytes": self.archive_limit_bytes,
            "network": {"mode": self.network_mode, "allow": list(self.network_allow)},
        }


@dataclass(frozen=True, slots=True)
class CapabilityRequest:
    """An expensive qualification the experiment needs, and the certificate offered.

    The expected identities are declared here, externally to the certificate, so a
    certificate can never self-match the fields it is being checked against.
    """

    capability: str
    certificate_path: Path
    certificate_sha256: str
    required_implementation_sha256: str
    required_runtime_identity: str
    required_configuration_sha256: str
    requested_bounds: Mapping[str, int]

    def as_json(self) -> dict[str, object]:
        return {
            "capability": self.capability,
            "certificate": str(self.certificate_path),
            "certificate_sha256": self.certificate_sha256,
            "required_implementation_sha256": self.required_implementation_sha256,
            "required_runtime_identity": self.required_runtime_identity,
            "required_configuration_sha256": self.required_configuration_sha256,
            "requested_bounds": dict(self.requested_bounds),
        }


@dataclass(frozen=True, slots=True)
class ExperimentSpec:
    id: str
    question: str
    claim_boundary: str
    tasks: tuple[TaskSpec, ...]
    source_path: Path
    executor: Executor
    resources: Resources
    capabilities: tuple[CapabilityRequest, ...] = ()
    reviewer: Executor | None = None
    arms: tuple[Arm, ...] = ()
    assignment: Assignment = field(default_factory=Assignment)

    def launch_payload(self) -> dict[str, object]:
        """Every launch-critical identity the lock must carry."""
        return {
            "executor": self.executor.as_json(),
            "reviewer": self.reviewer.as_json() if self.reviewer else None,
            "arms": [arm.as_json() for arm in self.arms],
            "assignment": self.assignment.as_json(),
            "resources": self.resources.as_json(),
        }

    def task(self, identifier: str) -> TaskSpec:
        for task in self.tasks:
            if task.id == identifier:
                return task
        raise SpecError(f"unknown task {identifier!r}")


def _execution_input(raw: object, where: str, base_dir: Path) -> ExecutionInput:
    if not isinstance(raw, dict):
        raise SpecError(f"{where}: each input must be a mapping")
    source = Path(_require_str(raw, "source", where))
    if not source.is_absolute():
        source = base_dir / source
    digest = raw.get("sha256")
    return ExecutionInput(
        id=_require_str(raw, "id", where),
        source=source,
        sha256=str(digest) if digest else None,
    )


def _parse_semantics(raw: Mapping[str, Any], where: str) -> Semantics:
    discriminator = _require(raw, "discriminator", where)
    if not isinstance(discriminator, dict):
        raise SpecError(f"{where}: discriminator must be a mapping")
    cases = discriminator.get("cases", [])
    if (
        not isinstance(cases, list)
        or not cases
        or not all(isinstance(c, str) for c in cases)
    ):
        raise SpecError(f"{where}: discriminator.cases must be a non-empty string list")
    behavior_paths = discriminator.get("behavior_paths", [])
    if not isinstance(behavior_paths, list):
        raise SpecError(f"{where}: discriminator.behavior_paths must be a list")

    controls_raw = raw.get("controls", [])
    if not isinstance(controls_raw, list):
        raise SpecError(f"{where}: controls must be a list")
    controls: list[Control] = []
    for item in controls_raw:
        if not isinstance(item, dict):
            raise SpecError(f"{where}: each control must be a mapping")
        case = _require_str(item, "case", f"{where}.controls")
        corroboration_raw = item.get("corroboration")
        corroboration: Corroboration | None = None
        if corroboration_raw is not None:
            if not isinstance(corroboration_raw, dict):
                raise SpecError(f"{where}: control corroboration must be a mapping")
            substitutions = corroboration_raw.get("value_substitutions", {})
            if not isinstance(substitutions, dict):
                raise SpecError(f"{where}: value_substitutions must be a mapping")
            prior = corroboration_raw.get("prior_qualification_sha256")
            path_value = corroboration_raw.get("path")
            if path_value is None and prior is None:
                raise SpecError(
                    f"{where}: corroboration needs either a base-tree path or a "
                    "prior_qualification_sha256"
                )
            symbol_value = corroboration_raw.get("symbol")
            corroboration = Corroboration(
                path=str(path_value) if path_value is not None else None,
                symbol=str(symbol_value) if symbol_value is not None else None,
                value_substitutions={str(k): str(v) for k, v in substitutions.items()},
                prior_qualification_sha256=str(prior) if prior is not None else None,
            )
        controls.append(Control(case=case, corroboration=corroboration))

    return Semantics(
        requirement=_require_str(raw, "requirement", where),
        discriminator_cases=tuple(cast(list[str], cases)),
        behavior_paths=tuple(str(p) for p in behavior_paths),
        controls=tuple(controls),
    )


def _parse_task(raw: Mapping[str, Any], index: int, base_dir: Path) -> TaskSpec:
    where = f"tasks[{index}]"
    identifier = _require_str(raw, "id", where)
    adapter = _require_str(raw, "adapter", f"{where}({identifier})")
    if adapter not in ADAPTERS:
        raise SpecError(
            f"{where}: unsupported adapter {adapter!r}; declare one of {sorted(ADAPTERS)}"
        )

    source_raw = _require(raw, "source", where)
    if not isinstance(source_raw, dict):
        raise SpecError(f"{where}: source must be a mapping")
    source = Source(
        repository=_require_str(source_raw, "repository", f"{where}.source"),
        base_commit=_require_str(source_raw, "base_commit", f"{where}.source"),
        base_tree=_require_str(source_raw, "base_tree", f"{where}.source"),
    )

    reference_raw = _require(raw, "reference", where)
    if not isinstance(reference_raw, dict):
        raise SpecError(f"{where}: reference must be a mapping")
    kind = _require_str(reference_raw, "kind", f"{where}.reference")
    if kind not in REFERENCE_KINDS:
        raise SpecError(f"{where}: unsupported reference kind {kind!r}")
    reference = Reference(
        kind=kind,
        commit=reference_raw.get("commit"),
        tree=_require_str(reference_raw, "tree", f"{where}.reference"),
        repository=reference_raw.get("repository"),
    )

    runtime_raw = _require(raw, "runtime", where)
    if not isinstance(runtime_raw, dict):
        raise SpecError(f"{where}: runtime must be a mapping")
    tools_raw = runtime_raw.get("preparation_tools", [])
    if not isinstance(tools_raw, list):
        raise SpecError(f"{where}: preparation_tools must be a list")
    tools = tuple(
        PreparationTool(
            name=_require_str(tool, "name", f"{where}.preparation_tools"),
            artifact=_require_str(tool, "artifact", f"{where}.preparation_tools"),
        )
        for tool in tools_raw
        if isinstance(tool, dict)
    )
    relay_raw = runtime_raw.get("relay_image")
    if relay_raw is not None:
        if not isinstance(relay_raw, str) or not IMMUTABLE_IMAGE_RE.fullmatch(
            relay_raw
        ):
            raise SpecError(
                f"{where}.runtime.relay_image must be an immutable digest reference, "
                "either sha256:<64 hex> or <name>@sha256:<64 hex>"
            )
    runtime = Runtime(
        image=_require_str(runtime_raw, "image", f"{where}.runtime"),
        available_plugins=tuple(
            str(p) for p in runtime_raw.get("available_plugins", [])
        ),
        preparation_tools=tools,
        relay_image=relay_raw,
    )

    oracle_raw = _require(raw, "oracle", where)
    if not isinstance(oracle_raw, dict):
        raise SpecError(f"{where}: oracle must be a mapping")
    oracle_path = Path(_require_str(oracle_raw, "path", f"{where}.oracle"))
    if not oracle_path.is_absolute():
        oracle_path = base_dir / oracle_path

    key_raw = raw.get("identification_key")
    key_path: Path | None = None
    key_sha256: str | None = None
    if isinstance(key_raw, dict) and "path" in key_raw:
        key_path = Path(str(key_raw["path"]))
        if not key_path.is_absolute():
            key_path = base_dir / key_path
        declared_key_sha = key_raw.get("sha256")
        key_sha256 = str(declared_key_sha) if declared_key_sha else None

    harness_raw = raw.get("harness", {})
    if not isinstance(harness_raw, dict):
        raise SpecError(f"{where}: harness must be a mapping")
    harness = Harness(
        preload_modules=tuple(str(m) for m in harness_raw.get("preload_modules", [])),
        isolate_test_config=bool(harness_raw.get("isolate_test_config", False)),
        extra_argv=tuple(str(a) for a in harness_raw.get("extra_argv", [])),
    )

    expectations_raw = _require(raw, "expectations", where)
    if not isinstance(expectations_raw, dict):
        raise SpecError(f"{where}: expectations must be a mapping")
    for side in ("base", "reference"):
        if not isinstance(expectations_raw.get(side), dict):
            raise SpecError(f"{where}: expectations.{side} must be a mapping")
    expectations = Expectations(
        base={k: int(v) for k, v in expectations_raw["base"].items()},
        reference={k: int(v) for k, v in expectations_raw["reference"].items()},
    )

    prior_raw = raw.get("prior_qualification")
    prior_sha = None
    prior_receipt: Path | None = None
    if isinstance(prior_raw, dict):
        prior_sha = prior_raw.get("evidence_sha256")
        receipt_value = prior_raw.get("receipt")
        if receipt_value:
            prior_receipt = Path(str(receipt_value))
            if not prior_receipt.is_absolute():
                prior_receipt = base_dir / prior_receipt
    execution_raw = raw.get("execution", {})
    if not isinstance(execution_raw, dict):
        raise SpecError(f"{where}: execution must be a mapping")
    execution = ExecutionEnvelope(
        command=tuple(str(item) for item in execution_raw.get("command", [])),
        environment_allowlist=tuple(
            str(item) for item in execution_raw.get("environment_allowlist", [])
        ),
        credential_environment=tuple(
            str(item) for item in execution_raw.get("credential_environment", [])
        ),
        read_only_inputs=tuple(
            _execution_input(item, f"{where}.execution.read_only_inputs", base_dir)
            for item in execution_raw.get("read_only_inputs", [])
        ),
    )

    preparation_raw = raw.get("preparation", {})
    if not isinstance(preparation_raw, dict):
        raise SpecError(f"{where}: preparation must be a mapping")

    return TaskSpec(
        execution=execution,
        prior_qualification_receipt=prior_receipt,
        preparation_scheme=(
            str(preparation_raw["scheme"]) if preparation_raw.get("scheme") else None
        ),
        identification_key_sha256=key_sha256,
        prior_qualification_sha256=str(prior_sha) if prior_sha else None,
        id=identifier,
        adapter=adapter,
        source=source,
        reference=reference,
        runtime=runtime,
        oracle_path=oracle_path,
        oracle_sha256=oracle_raw.get("sha256"),
        identification_key_path=key_path,
        semantics=_parse_semantics(
            cast(Mapping[str, Any], _require(raw, "semantics", where)),
            f"{where}.semantics",
        ),
        harness=harness,
        expectations=expectations,
    )


def parse_spec(payload: Mapping[str, Any], *, source_path: Path) -> ExperimentSpec:
    if payload.get("schema") != SPEC_SCHEMA:
        raise SpecError(
            f"unsupported spec schema {payload.get('schema')!r}; expected {SPEC_SCHEMA}"
        )
    experiment = payload.get("experiment")
    if not isinstance(experiment, dict):
        raise SpecError("experiment must be a mapping")
    tasks_raw = payload.get("tasks")
    if not isinstance(tasks_raw, list):
        raise SpecError("tasks must be a list")
    base_dir = source_path.parent
    tasks = tuple(
        _parse_task(cast(Mapping[str, Any], task), index, base_dir)
        for index, task in enumerate(tasks_raw)
    )
    identifiers = [task.id for task in tasks]
    if len(set(identifiers)) != len(identifiers):
        raise SpecError("duplicate task id")

    def _executor(raw_value: object, where: str) -> Executor:
        if not isinstance(raw_value, dict):
            raise SpecError(f"{where} must be a mapping")
        return Executor(
            id=_require_str(raw_value, "id", where),
            version=_require_str(raw_value, "version", where),
            config_sha256=_require_str(raw_value, "config_sha256", where),
            model=raw_value.get("model"),
            small_model=raw_value.get("small_model"),
        )

    executor = _executor(
        _require(experiment, "executor", "experiment"), "experiment.executor"
    )
    reviewer_raw = experiment.get("reviewer")
    reviewer = _executor(reviewer_raw, "experiment.reviewer") if reviewer_raw else None

    resources_raw = _require(experiment, "resources", "experiment")
    if not isinstance(resources_raw, dict):
        raise SpecError("experiment.resources must be a mapping")
    network_raw = resources_raw.get("network", {})
    if not isinstance(network_raw, dict):
        raise SpecError("experiment.resources.network must be a mapping")
    mode = str(network_raw.get("mode", "none"))
    if mode not in {"none", "restricted"}:
        raise SpecError(f"unsupported network mode {mode!r}")
    resources = Resources(
        timeout_seconds=int(
            _require(resources_raw, "timeout_seconds", "experiment.resources")
        ),
        archive_limit_bytes=int(
            _require(resources_raw, "archive_limit_bytes", "experiment.resources")
        ),
        network_mode=mode,
        network_allow=tuple(str(item) for item in network_raw.get("allow", [])),
    )

    arms_raw = experiment.get("arms", {})
    if not isinstance(arms_raw, dict):
        raise SpecError("experiment.arms must be a mapping")
    arms = tuple(
        Arm(
            name=str(name),
            inputs=tuple(
                _execution_input(item, f"experiment.arms.{name}.inputs", base_dir)
                for item in (value or {}).get("inputs", [])
            ),
        )
        for name, value in arms_raw.items()
        if isinstance(value, dict)
    )
    assignment_raw = experiment.get("assignment", {})
    if not isinstance(assignment_raw, dict):
        raise SpecError("experiment.assignment must be a mapping")
    repetitions = int(assignment_raw.get("repetitions", 1))
    if repetitions <= 0:
        raise SpecError("experiment.assignment.repetitions must be positive")
    declared_arms = tuple(str(item) for item in assignment_raw.get("arms", []))
    known = {arm.name for arm in arms}
    unknown = [name for name in declared_arms if name not in known]
    if unknown:
        raise SpecError(f"experiment.assignment names undeclared arms {unknown}")

    schedule_raw = assignment_raw.get("schedule")
    schedule_source = "none"
    schedule_sha256: str | None = None
    if schedule_raw is None:
        artifact = assignment_raw.get("schedule_artifact")
        if isinstance(artifact, dict):
            path = Path(
                _require_str(
                    artifact, "path", "experiment.assignment.schedule_artifact"
                )
            )
            if not path.is_absolute():
                path = base_dir / path
            raw_bytes = path.read_bytes()
            observed = hashlib.sha256(raw_bytes).hexdigest()
            declared_digest = artifact.get("sha256")
            if declared_digest and str(declared_digest) != observed:
                raise SpecError(
                    "experiment.assignment.schedule_artifact digest does not match the file"
                )
            schedule_raw = json.loads(raw_bytes)
            schedule_source = f"artifact:{path}"
            schedule_sha256 = observed
    else:
        schedule_source = "inline"

    entries: list[ScheduleEntry] = []
    if isinstance(schedule_raw, list):
        task_names = {
            str(task.get("id")) for task in tasks_raw if isinstance(task, dict)
        }
        for index, item in enumerate(schedule_raw):
            if not isinstance(item, dict):
                raise SpecError(
                    f"experiment.assignment.schedule[{index}] must be a mapping"
                )
            entry = ScheduleEntry(
                task=_require_str(
                    item, "task", f"experiment.assignment.schedule[{index}]"
                ),
                repetition=int(item.get("repetition", 1)),
                arm=_require_str(
                    item, "arm", f"experiment.assignment.schedule[{index}]"
                ),
            )
            if entry.task not in task_names:
                raise SpecError(f"schedule[{index}] names unknown task {entry.task!r}")
            if declared_arms and entry.arm not in declared_arms:
                raise SpecError(f"schedule[{index}] names unassigned arm {entry.arm!r}")
            entries.append(entry)
        if schedule_sha256 is None:
            schedule_sha256 = hashlib.sha256(
                json.dumps([e.as_json() for e in entries], sort_keys=True).encode()
            ).hexdigest()

    assignment = Assignment(
        repetitions=repetitions,
        arms=declared_arms,
        schedule=tuple(entries),
        source=schedule_source,
        schedule_sha256=schedule_sha256,
    )

    capabilities_raw = payload.get("capabilities", [])
    if not isinstance(capabilities_raw, list):
        raise SpecError("capabilities must be a list")
    capabilities: list[CapabilityRequest] = []
    for index, item in enumerate(capabilities_raw):
        if not isinstance(item, dict):
            raise SpecError(f"capabilities[{index}] must be a mapping")
        certificate = Path(_require_str(item, "certificate", f"capabilities[{index}]"))
        if not certificate.is_absolute():
            certificate = base_dir / certificate
        bounds = item.get("requested_bounds", {})
        if not isinstance(bounds, dict):
            raise SpecError(
                f"capabilities[{index}]: requested_bounds must be a mapping"
            )
        capabilities.append(
            CapabilityRequest(
                capability=_require_str(item, "capability", f"capabilities[{index}]"),
                certificate_path=certificate,
                certificate_sha256=_require_str(
                    item, "certificate_sha256", f"capabilities[{index}]"
                ),
                required_implementation_sha256=_require_str(
                    item, "required_implementation_sha256", f"capabilities[{index}]"
                ),
                required_runtime_identity=_require_str(
                    item, "required_runtime_identity", f"capabilities[{index}]"
                ),
                required_configuration_sha256=_require_str(
                    item, "required_configuration_sha256", f"capabilities[{index}]"
                ),
                requested_bounds={str(k): int(v) for k, v in bounds.items()},
            )
        )

    return ExperimentSpec(
        capabilities=tuple(capabilities),
        executor=executor,
        reviewer=reviewer,
        resources=resources,
        arms=arms,
        assignment=assignment,
        id=_require_str(experiment, "id", "experiment"),
        question=str(experiment.get("question", "")),
        claim_boundary=str(experiment.get("claim_boundary", "")),
        tasks=tasks,
        source_path=source_path,
    )


SCHEMA_PATH = (
    Path(__file__).resolve().parents[2] / "schemas" / "experiment-spec.schema.json"
)


def validate_against_schema(payload: Mapping[str, Any]) -> None:
    """Validate the declarative surface before interpreting it."""
    if not SCHEMA_PATH.is_file():  # pragma: no cover - packaging fallback
        return
    import jsonschema

    schema = json.loads(SCHEMA_PATH.read_text())
    errors = sorted(
        jsonschema.Draft202012Validator(schema).iter_errors(dict(payload)),
        key=lambda error: list(error.path),
    )
    if errors:
        first = errors[0]
        location = "/".join(str(part) for part in first.path) or "<root>"
        raise SpecError(f"spec schema violation at {location}: {first.message}")


def load_spec(path: str | Path) -> ExperimentSpec:
    source_path = Path(path).resolve()
    text = source_path.read_text()
    if source_path.suffix in {".yaml", ".yml"}:
        import yaml

        payload = yaml.safe_load(text)
    else:
        payload = json.loads(text)
    if not isinstance(payload, dict):
        raise SpecError("spec must be a mapping")
    validate_against_schema(cast(Mapping[str, Any], payload))
    return parse_spec(cast(Mapping[str, Any], payload), source_path=source_path)
