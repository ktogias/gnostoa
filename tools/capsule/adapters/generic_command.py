"""generic-command adapter: everything is declared, nothing is inferred."""

from __future__ import annotations

from tools.capsule.adapters import Adapter, HarnessResult, Invocation
from tools.capsule.preparation import ConfigProjection, TestConfig
from tools.capsule.spec import TaskSpec


class GenericCommandAdapter(Adapter):
    name = "generic-command"

    def build(
        self,
        task: TaskSpec,
        *,
        workspace_path: str,
        oracle_name: str,
        test_config: TestConfig,
        projection: ConfigProjection | None = None,
    ) -> HarnessResult:
        blockers: list[dict[str, object]] = []
        if not task.harness.extra_argv:
            blockers.append(
                {
                    "task": task.id,
                    "code": "generic-command-requires-explicit-argv",
                    "detail": "the generic-command adapter never infers a command; declare harness.extra_argv",
                }
            )
        return HarnessResult(
            preload_modules=task.harness.preload_modules,
            generated_files=(),
            invocation=Invocation(
                argv=tuple(task.harness.extra_argv), cwd=workspace_path, env={}
            ),
            added_runtime_packages=(),
            isolated_test_config=False,
            blockers=tuple(blockers),
        )
