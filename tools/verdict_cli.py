"""The command-line boundary the verdict commands share (#408, #407).

`knowledge assurance-check` hardened this boundary over seven review rounds, and
`knowledge merge-admission` consumes it rather than a copy:

- the input is one JSON document on standard input, so no input path reaches a
  file read (SonarCloud S8707). It is bounded in size, strictly decoded and
  bounded in depth, as `review-check`'s input is;
- a path the command does read is resolved, symbolic links included, and
  refused outside the project root (Decisions 0033 and 0034);
- the verdict is written and flushed inside the guard. After a broken pipe,
  standard output points at the null device, so the flush at shutdown cannot
  fail again and turn exit 2 into 120;
- every failed run exits 2 and names the failure. Exit 1 is the command's
  negative verdict, and Python's own exit 1 for an uncaught exception would
  read as one.

Each function raises the caller's error class, so each command keeps its own
messages and exception type.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from .knowledge_common import KnowledgeFormatError, confine_to_root
from .review_check import assert_document_depth, strict_json_loads

MAX_INPUT_BYTES = 8 * 1024 * 1024


def read_json_input(label: str, error: type[ValueError]) -> object:
    """Read one bounded, strictly decoded JSON document from standard input."""

    try:
        raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    except (OSError, ValueError) as exc:
        # A closed stream raises ValueError; neither may exit as a verdict does.
        raise error(f"cannot read the input: {exc}") from exc
    return _decode(raw, label, error, "input")


def read_json_file(
    path: Path, label: str, error: type[ValueError], *, project_root: Path
) -> object:
    """Read one bounded, strictly decoded JSON document from `path`, confined to
    `project_root` as every path a command reads, under the same rules as
    standard input (#407, slice 1b.3b-2)."""

    resolved = confine(path, project_root, label=label, error=error)
    try:
        with resolved.open("rb") as stream:
            raw = stream.read(MAX_INPUT_BYTES + 1)
    except OSError as exc:
        raise error(f"cannot read the {label}: {exc}") from exc
    return _decode(raw, label, error, f"the {label}")


def _decode(raw: bytes, label: str, error: type[ValueError], name: str) -> object:
    if len(raw) > MAX_INPUT_BYTES:
        raise error(f"{name} is larger than the {MAX_INPUT_BYTES}-byte bound")
    try:
        value = strict_json_loads(raw.decode("utf-8"), label=label)
    except ValueError as exc:
        # UnicodeDecodeError and json's errors are ValueErrors.
        raise error(f"{name} is not valid JSON: {exc}") from exc
    try:
        assert_document_depth(value, label)
    except ValueError as exc:
        # Valid JSON past an operational bound (cubic on #410).
        raise error(f"{name} is out of bounds: {exc}") from exc
    return value


def confine(
    path: Path, project_root: Path, *, label: str, error: type[ValueError]
) -> Path:
    """Resolve `path` and refuse it outside `project_root`."""

    try:
        resolved, _ = confine_to_root(path, project_root, label=label)
    except (OSError, RuntimeError) as exc:
        # A symbolic-link loop raises RuntimeError before Python 3.13.
        raise error(f"cannot resolve the {label}: {exc}") from exc
    except KnowledgeFormatError as exc:
        raise error(str(exc)) from exc
    return resolved


def discard_stdout() -> None:
    """Point standard output at the null device after a broken pipe, as Python's
    `signal` documentation recommends."""

    try:
        null = os.open(os.devnull, os.O_WRONLY)
        os.dup2(null, sys.stdout.fileno())
    except (OSError, ValueError):
        # A stream without a file descriptor has nothing left to flush to a pipe.
        return


def run(
    prog: str,
    compute: Callable[[], Mapping[str, Any]],
    *,
    positive: Callable[[Mapping[str, Any]], bool],
    input_errors: tuple[type[Exception], ...],
) -> int:
    """Compute and write a verdict: 0 when `positive`, 1 when not, 2 when the
    run failed."""

    try:
        verdict = compute()
        print(json.dumps(verdict, indent=2, sort_keys=True))
        sys.stdout.flush()
        # Inside the guard, so a predicate that fails is a failed run (cubic on
        # #410).
        code = 0 if positive(verdict) else 1
    except input_errors as exc:
        print(f"{prog}: {exc}", file=sys.stderr)
        return 2
    except (
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
        LookupError,
        AttributeError,
    ) as exc:
        # RuntimeError includes RecursionError.
        if isinstance(exc, BrokenPipeError):
            discard_stdout()
        print(f"{prog}: error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    return code
