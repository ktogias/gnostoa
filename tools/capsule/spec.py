"""Declarative experiment specification.

The spec states intent. Everything mechanical -- Dockerfiles, harness files,
runner profiles, locks -- is derived from it. Ambiguity is rejected rather than
guessed: the compiler never invents an adapter, a reference or an expectation.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

SPEC_SCHEMA = "gnostoa-experiment-spec/v1"
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
    value_substitutions: Mapping[str, str] = field(default_factory=dict)
    prior_qualification_sha256: str | None = None

    def as_json(self) -> dict[str, object]:
        return {
            "path": self.path,
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
            "corroboration": self.corroboration.as_json() if self.corroboration else None,
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

    def as_json(self) -> dict[str, object]:
        return {
            "image": self.image,
            "available_plugins": list(self.available_plugins),
            "preparation_tools": [tool.as_json() for tool in self.preparation_tools],
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
    prior_qualification_sha256: str | None = None

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
class CapabilityRequest:
    """An expensive qualification the experiment needs, and the certificate offered."""

    capability: str
    certificate_path: Path
    requested_bounds: Mapping[str, int]

    def as_json(self) -> dict[str, object]:
        return {
            "capability": self.capability,
            "certificate": str(self.certificate_path),
            "requested_bounds": dict(self.requested_bounds),
        }


@dataclass(frozen=True, slots=True)
class ExperimentSpec:
    id: str
    question: str
    claim_boundary: str
    tasks: tuple[TaskSpec, ...]
    source_path: Path
    capabilities: tuple[CapabilityRequest, ...] = ()

    def task(self, identifier: str) -> TaskSpec:
        for task in self.tasks:
            if task.id == identifier:
                return task
        raise SpecError(f"unknown task {identifier!r}")


def _parse_semantics(raw: Mapping[str, Any], where: str) -> Semantics:
    discriminator = _require(raw, "discriminator", where)
    if not isinstance(discriminator, dict):
        raise SpecError(f"{where}: discriminator must be a mapping")
    cases = discriminator.get("cases", [])
    if not isinstance(cases, list) or not cases or not all(isinstance(c, str) for c in cases):
        raise SpecError(f"{where}: discriminator.cases must be a non-empty string list")
    behavior_paths = discriminator.get("behavior_paths", [])
    if not isinstance(behavior_paths, list):
        raise SpecError(f"{where}: discriminator.behavior_paths must be a list")

    controls_raw = raw.get("controls", [])
    if not isinstance(controls_raw, list):
        raise SpecError(f"{where}: controls must be a list")
    controls: list[Control] = []
    for item in cast(list[Any], controls_raw):
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
            corroboration = Corroboration(
                path=str(path_value) if path_value is not None else None,
                value_substitutions={str(k): str(v) for k, v in substitutions.items()},
                prior_qualification_sha256=str(prior) if prior is not None else None,
            )
        controls.append(Control(case=case, corroboration=corroboration))

    return Semantics(
        requirement=_require_str(raw, "requirement", where),
        discriminator_cases=tuple(cast(list[str], cases)),
        behavior_paths=tuple(str(p) for p in cast(list[Any], behavior_paths)),
        controls=tuple(controls),
    )


def _parse_task(raw: Mapping[str, Any], index: int, base_dir: Path) -> TaskSpec:
    where = f"tasks[{index}]"
    identifier = _require_str(raw, "id", where)
    adapter = _require_str(raw, "adapter", f"{where}({identifier})")
    if adapter not in ADAPTERS:
        raise SpecError(f"{where}: unsupported adapter {adapter!r}; declare one of {sorted(ADAPTERS)}")

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
        for tool in cast(list[Any], tools_raw)
        if isinstance(tool, dict)
    )
    runtime = Runtime(
        image=_require_str(runtime_raw, "image", f"{where}.runtime"),
        available_plugins=tuple(str(p) for p in runtime_raw.get("available_plugins", [])),
        preparation_tools=tools,
    )

    oracle_raw = _require(raw, "oracle", where)
    if not isinstance(oracle_raw, dict):
        raise SpecError(f"{where}: oracle must be a mapping")
    oracle_path = Path(_require_str(oracle_raw, "path", f"{where}.oracle"))
    if not oracle_path.is_absolute():
        oracle_path = base_dir / oracle_path

    key_raw = raw.get("identification_key")
    key_path: Path | None = None
    if isinstance(key_raw, dict) and "path" in key_raw:
        key_path = Path(str(key_raw["path"]))
        if not key_path.is_absolute():
            key_path = base_dir / key_path

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
    if isinstance(prior_raw, dict):
        prior_sha = prior_raw.get("evidence_sha256")
    return TaskSpec(
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
            cast(Mapping[str, Any], _require(raw, "semantics", where)), f"{where}.semantics"
        ),
        harness=harness,
        expectations=expectations,
    )


def parse_spec(payload: Mapping[str, Any], *, source_path: Path) -> ExperimentSpec:
    if payload.get("schema") != SPEC_SCHEMA:
        raise SpecError(f"unsupported spec schema {payload.get('schema')!r}; expected {SPEC_SCHEMA}")
    experiment = payload.get("experiment")
    if not isinstance(experiment, dict):
        raise SpecError("experiment must be a mapping")
    tasks_raw = payload.get("tasks")
    if not isinstance(tasks_raw, list):
        raise SpecError("tasks must be a list")
    base_dir = source_path.parent
    tasks = tuple(
        _parse_task(cast(Mapping[str, Any], task), index, base_dir)
        for index, task in enumerate(cast(list[Any], tasks_raw))
    )
    identifiers = [task.id for task in tasks]
    if len(set(identifiers)) != len(identifiers):
        raise SpecError("duplicate task id")
    capabilities_raw = payload.get("capabilities", [])
    if not isinstance(capabilities_raw, list):
        raise SpecError("capabilities must be a list")
    capabilities: list[CapabilityRequest] = []
    for index, item in enumerate(cast(list[Any], capabilities_raw)):
        if not isinstance(item, dict):
            raise SpecError(f"capabilities[{index}] must be a mapping")
        certificate = Path(_require_str(item, "certificate", f"capabilities[{index}]"))
        if not certificate.is_absolute():
            certificate = base_dir / certificate
        bounds = item.get("requested_bounds", {})
        if not isinstance(bounds, dict):
            raise SpecError(f"capabilities[{index}]: requested_bounds must be a mapping")
        capabilities.append(
            CapabilityRequest(
                capability=_require_str(item, "capability", f"capabilities[{index}]"),
                certificate_path=certificate,
                requested_bounds={str(k): int(v) for k, v in bounds.items()},
            )
        )

    return ExperimentSpec(
        capabilities=tuple(capabilities),
        id=_require_str(experiment, "id", "experiment"),
        question=str(experiment.get("question", "")),
        claim_boundary=str(experiment.get("claim_boundary", "")),
        tasks=tasks,
        source_path=source_path,
    )


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
    return parse_spec(cast(Mapping[str, Any], payload), source_path=source_path)
