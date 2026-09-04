"""Small public surface: prepare, status, execute.

`prepare` owns mechanical preparation and qualification within its declared
authority. `execute` consumes an already-frozen lock and cannot repair or
reinterpret it.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from tools.capsule import stages
from tools.capsule.authority import AuthorityError
from tools.capsule.authority import load_file as load_authority
from tools.capsule.compiler import CompileError, prepare, status
from tools.capsule.spec import SpecError, load_spec


def _emit(payload: object) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def command_prepare(args: argparse.Namespace) -> int:
    if not args.offline:
        _emit({"status": "BLOCKED", "blockers": [{"code": "offline-mode-required"}]})
        return 2
    try:
        spec = load_spec(args.spec)
    except SpecError as exc:
        _emit(
            {
                "status": "BLOCKED",
                "blockers": [{"code": "spec-invalid", "detail": str(exc)}],
            }
        )
        return 2
    authority = None
    if args.preflight_authority:
        try:
            authority = load_authority(Path(args.preflight_authority))
        except (AuthorityError, OSError, json.JSONDecodeError) as exc:
            _emit(
                {
                    "status": "BLOCKED",
                    "blockers": [
                        {"code": "preflight-authority-invalid", "detail": str(exc)}
                    ],
                }
            )
            return 2
    try:
        result = prepare(
            spec,
            args.workspace,
            offline=True,
            preflight_authority=authority,
        )
    except CompileError as exc:
        _emit(
            {
                "status": "BLOCKED",
                "blockers": [{"code": "compile-error", "detail": str(exc)}],
            }
        )
        return 2
    _emit(
        {
            "status": result.status,
            "stage": result.stage,
            "blockers": result.blockers,
            "reused_stages": result.reused_stages,
            "stage_receipts": result.stage_receipts(),
            "lock_sha256": result.lock_identity,
            "tasks": {
                task_id: {
                    "capsule_identity": task.capsule_identity,
                    "semantic_identity": task.semantic_identity,
                    "runtime_image": task.runtime_image,
                    "prepared_runtime_identity": task.prepared_runtime_identity,
                    "preparation_required": task.preparation.required,
                }
                for task_id, task in result.tasks.items()
            },
        }
    )
    return 0 if result.status == stages.READY_FOR_OWNER_REVIEW else 1


def command_status(args: argparse.Namespace) -> int:
    payload = status(args.workspace)
    _emit(
        {
            "stage": payload.get("stage"),
            "status": payload.get("status"),
            "blockers": payload.get("blockers", []),
        }
    )
    return 0


def command_execute(args: argparse.Namespace) -> int:
    payload = status(args.workspace)
    if payload.get("status") != stages.READY_FOR_OWNER_REVIEW:
        _emit(
            {
                "status": "REFUSED",
                "reason": "lock-not-ready",
                "stage": payload.get("stage"),
                "detail": "execute consumes a frozen READY_FOR_OWNER_REVIEW lock and cannot repair it",
            }
        )
        return 2
    if not args.authority:
        _emit({"status": "REFUSED", "reason": "launch-authority-required"})
        return 2
    _emit(
        {
            "status": "REFUSED",
            "reason": "runner-handoff-not-implemented-in-v1",
            "detail": "v1 prepares and freezes; handing the frozen profiles to the runner is a separate slice",
        }
    )
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gnostoa-experiment")
    sub = parser.add_subparsers(dest="command", required=True)

    prepare_parser = sub.add_parser(
        "prepare", help="prepare and qualify an experiment spec"
    )
    prepare_parser.add_argument("spec")
    prepare_parser.add_argument("--workspace", required=True)
    prepare_parser.add_argument("--offline", action="store_true", default=False)
    prepare_parser.add_argument(
        "--preflight-authority",
        default=None,
        help="path to a preflight authority naming this experiment and its scope",
    )
    prepare_parser.set_defaults(func=command_prepare)

    status_parser = sub.add_parser(
        "status", help="report the retained stage and blockers"
    )
    status_parser.add_argument("workspace")
    status_parser.set_defaults(func=command_status)

    execute_parser = sub.add_parser("execute", help="execute a frozen experiment lock")
    execute_parser.add_argument("workspace")
    execute_parser.add_argument("--authority", default=None)
    execute_parser.set_defaults(func=command_execute)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
