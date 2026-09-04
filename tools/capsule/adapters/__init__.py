"""Mechanical adapters.

An adapter owns invocation mechanics only: preload, test-config isolation,
subject mode, generated build artifacts, mounts and the exact argv, cwd and
environment. Adapters never contain assertions about subject behaviour; semantic
qualification lives in tools.capsule.oracle_qualification.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from tools.capsule.identity import digest_of
from tools.capsule.preparation import ConfigProjection, TestConfig
from tools.capsule.spec import TaskSpec


@dataclass(frozen=True, slots=True)
class GeneratedFile:
    path: str
    content: str
    provenance: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class Invocation:
    argv: tuple[str, ...]
    cwd: str
    env: Mapping[str, str]

    def as_json(self) -> dict[str, object]:
        return {"argv": list(self.argv), "cwd": self.cwd, "env": dict(self.env)}


@dataclass(frozen=True, slots=True)
class HarnessResult:
    preload_modules: tuple[str, ...]
    generated_files: tuple[GeneratedFile, ...]
    invocation: Invocation
    added_runtime_packages: tuple[str, ...]
    isolated_test_config: bool
    blockers: tuple[Mapping[str, object], ...] = ()

    @property
    def identity(self) -> str:
        return digest_of(
            {
                "preload_modules": list(self.preload_modules),
                "generated": [
                    {"path": f.path, "sha256": digest_of(f.content)}
                    for f in self.generated_files
                ],
                "invocation": self.invocation.as_json(),
                "isolated_test_config": self.isolated_test_config,
            }
        )

    def as_json(self) -> dict[str, object]:
        return {
            "identity": self.identity,
            "preload_modules": list(self.preload_modules),
            "generated_files": [
                {"path": f.path, "sha256": digest_of(f.content)}
                for f in self.generated_files
            ],
            "invocation": self.invocation.as_json(),
            "added_runtime_packages": list(self.added_runtime_packages),
            "isolated_test_config": self.isolated_test_config,
        }


class Adapter:
    """Adapter contract."""

    name = "abstract"

    def build(
        self,
        task: TaskSpec,
        *,
        workspace_path: str,
        oracle_name: str,
        test_config: TestConfig,
        projection: ConfigProjection | None = None,
    ) -> HarnessResult:  # pragma: no cover - abstract
        raise NotImplementedError


def get(name: str) -> Adapter:
    from tools.capsule.adapters.generic_command import GenericCommandAdapter
    from tools.capsule.adapters.node_vitest import NodeVitestAdapter
    from tools.capsule.adapters.python_pytest import PythonPytestAdapter

    registry: dict[str, Adapter] = {
        PythonPytestAdapter.name: PythonPytestAdapter(),
        NodeVitestAdapter.name: NodeVitestAdapter(),
        GenericCommandAdapter.name: GenericCommandAdapter(),
    }
    return registry[name]
