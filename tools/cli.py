from __future__ import annotations

import sys
from collections.abc import Callable
from importlib.metadata import PackageNotFoundError, version

from . import (
    adoption_check,
    build_context_pack,
    build_docs,
    check_change_policy,
    check_ci_policy,
    check_guardrails,
    check_runtime_lock,
    self_check,
    task_envelope,
    validate_bundle,
)

COMMANDS: dict[str, tuple[str, Callable[[list[str] | None], int]]] = {
    "adoption-check": (
        "produce bounded mechanical adoption evidence",
        adoption_check.main,
    ),
    "validate": ("validate an OKF bundle", validate_bundle.main),
    "context-pack": ("build a bounded orientation pack", build_context_pack.main),
    "docs-build": ("build the derived human documentation site", build_docs.main),
    "check-guardrails": (
        "validate guardrail ownership and coverage",
        check_guardrails.main,
    ),
    "check-change-policy": (
        "validate inherited change-control policy",
        check_change_policy.main,
    ),
    "check-ci-policy": (
        "validate inherited CI policy and verification suites",
        check_ci_policy.main,
    ),
    "check-runtime": (
        "validate toolkit source and runtime lockstep",
        check_runtime_lock.main,
    ),
    "surface-digest": (
        "compute the deterministic toolkit public-surface digest",
        check_runtime_lock.surface_digest_main,
    ),
    "task-validate": (
        "validate a bounded task envelope",
        task_envelope.validate_main,
    ),
    "task-project": (
        "render a validated current task projection",
        task_envelope.project_main,
    ),
    "self-check": ("run the toolkit self-check", self_check.main),
}


def _version() -> str:
    try:
        return version("gnostoa")
    except PackageNotFoundError:
        return "development"


def _help() -> str:
    width = max(len(command) for command in COMMANDS)
    commands = "\n".join(
        f"  {command:<{width}}  {description}"
        for command, (description, _) in COMMANDS.items()
    )
    return (
        "usage: knowledge <command> [options]\n\n"
        "commands:\n"
        f"{commands}\n\n"
        "Use 'knowledge <command> --help' for command-specific options."
    )


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments or arguments[0] in {"-h", "--help", "help"}:
        print(_help())
        return 0
    if arguments[0] in {"-V", "--version"}:
        print(_version())
        return 0

    command = arguments.pop(0)
    selected = COMMANDS.get(command)
    if selected is None:
        print(f"ERROR: unknown command {command!r}\n", file=sys.stderr)
        print(_help(), file=sys.stderr)
        return 2
    return selected[1](arguments)


if __name__ == "__main__":
    raise SystemExit(main())
