"""The bounded GitLab CI script reader of the inventory's gitlab-script family (#389 H-PYSEC-2; Decision 0122)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class GitlabUnsupported(ValueError):
    """A GitLab CI construct the bounded reader does not resolve: an attributable gap."""


_GITLAB_RESERVED = frozenset(
    {
        "stages",
        "workflow",
        "variables",
        "default",
        "include",
        "image",
        "services",
        "before_script",
        "after_script",
        "cache",
    }
)


_GITLAB_SCALARS = frozenset(
    {"tag:yaml.org,2002:" + name for name in ("str", "int", "bool", "null", "float")}
)


def _gitlab_folded(node: Any, line: int) -> tuple[str, list[tuple[int, int]]]:
    """A simple folded item (non-empty, equally indented lines, each break folded to one space), with each column's
    YAML line; anything else has no exact map."""
    stop = node.end_mark.line + (1 if node.end_mark.column else 0)
    raw = node.start_mark.buffer.rstrip("\0").split("\n")[
        node.start_mark.line + 1 : stop
    ]
    while raw and raw[-1] == "":
        raw.pop()
    parts = [r.strip() for r in raw]
    simple = (
        bool(raw)
        and all(parts)
        and len({len(r) - len(r.lstrip(" ")) for r in raw}) == 1
        and node.value.rstrip("\n") == " ".join(parts)
        and node.value.count("\n") <= 1
    )
    if not simple:
        raise GitlabUnsupported(f"a folded item with no exact line map at line {line}")
    spans, column = [], 1
    for offset, part in enumerate(parts):
        spans.append((column, line + 1 + offset))
        column += len(part) + 1
    return node.value.rstrip("\n"), spans


def _gitlab_scalar(node: Any) -> Any:
    import yaml

    if node.tag not in _GITLAB_SCALARS:
        raise GitlabUnsupported(
            f"an unsupported tag {node.tag} at line {node.start_mark.line + 1}"
        )
    if node.tag != "tag:yaml.org,2002:str":
        try:
            return yaml.SafeLoader("").construct_object(node)
        except (ValueError, LookupError, yaml.YAMLError) as exc:
            # A tag whose text it cannot read: PyYAML's scalar constructors raise ValueError (`!!int x`), KeyError
            # (`!!bool invalid`) or IndexError (`!!int ""`), measured (Codex on #470). Any other failure is the
            # loader's own defect, and surfaces (cubic on #470).
            raise GitlabUnsupported(
                f"a {node.tag} item that cannot be read at line {node.start_mark.line + 1}"
            ) from exc
    line = node.start_mark.line + 1
    try:
        node.value.encode("utf-8")
    except UnicodeEncodeError as exc:
        # An escaped lone surrogate decodes, but no analysis copy can hold it (Codex on #470).
        raise GitlabUnsupported(
            f"an item that is not UTF-8 text at line {line}"
        ) from exc
    if node.style == "|":
        return (node.value, line + 1)
    if node.style == ">":
        return _gitlab_folded(node, line)
    if "\n" in node.value or node.start_mark.line != node.end_mark.line:
        raise GitlabUnsupported(f"a multi-line flow item at line {line}")
    return (node.value, line)


def _gitlab_construct(node: Any) -> Any:
    """The document's value, each script string with its YAML line, refusing what the reader does not resolve."""
    import yaml

    if isinstance(node, yaml.ScalarNode):
        return _gitlab_scalar(node)
    if node.tag not in ("tag:yaml.org,2002:seq", "tag:yaml.org,2002:map"):
        # A tagged collection, as `!reference [.job, script]`, is unsupported as a tagged scalar is.
        raise GitlabUnsupported(
            f"an unsupported tag {node.tag} at line {node.start_mark.line + 1}"
        )
    if isinstance(node, yaml.SequenceNode):
        return [_gitlab_construct(v) for v in node.value]
    if not isinstance(node, yaml.MappingNode):
        raise GitlabUnsupported("an unsupported node")
    out = {}
    for key, value in node.value:
        text = _gitlab_construct(key)
        text = text[0] if isinstance(text, tuple) else text
        line = key.start_mark.line + 1
        if text == "<<":
            raise GitlabUnsupported(f"a YAML merge key at line {line}")
        if not isinstance(text, str) or text in out:
            what = (
                "a duplicate key" if isinstance(text, str) else "a key that is not text"
            )
            raise GitlabUnsupported(f"{what} at line {line}")
        out[text] = _gitlab_construct(value)
    return out


def _gitlab_merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in over.items():
        merged[key] = (
            _gitlab_merge(merged[key], value)
            if isinstance(value, dict) and isinstance(merged.get(key), dict)
            else value
        )
    return merged


def _gitlab_resolve(
    name: str,
    jobs: Mapping[str, Any],
    resolved: dict[str, tuple[dict[str, Any], int]],
    seen: tuple[str, ...] = (),
) -> dict[str, Any]:
    """`name` with its local `extends` merged in, at most eleven levels deep. Each job resolves once per file, into
    `resolved` with how many levels lie below it, so a shared ancestor is never resolved again (Codex on #470), and
    one reached deeper than it was first still keeps the bound."""
    if name in seen:
        raise GitlabUnsupported(f"an extends cycle at {name}")
    if name not in jobs:
        raise GitlabUnsupported(f"extends names {name!r}, not a local job")
    if name not in resolved:
        if len(seen) > 11:
            raise GitlabUnsupported(f"extends past eleven levels at {name}")
        resolved[name] = _gitlab_extended(name, jobs, resolved, seen)
    job, below = resolved[name]
    if len(seen) + below > 11:
        raise GitlabUnsupported(f"extends past eleven levels at {name}")
    return job


def _gitlab_extended(
    name: str,
    jobs: Mapping[str, Any],
    resolved: dict[str, tuple[dict[str, Any], int]],
    seen: tuple[str, ...],
) -> tuple[dict[str, Any], int]:
    """`name`'s own definition merged over its parents', in order, and how many levels lie below it."""
    job = jobs[name]
    if "inherit" in job:
        raise GitlabUnsupported(f"inherit in {name}")
    parents = job.get("extends")
    own = {k: v for k, v in job.items() if k != "extends"}
    if parents is None:
        return own, 0
    parents = [parents] if isinstance(parents, tuple) else parents
    if not isinstance(parents, list) or not all(isinstance(p, tuple) for p in parents):
        raise GitlabUnsupported(f"a malformed extends in {name}")
    merged: dict[str, Any] = {}
    below = 0
    for parent in parents:
        merged = _gitlab_merge(
            merged, _gitlab_resolve(parent[0], jobs, resolved, (*seen, name))
        )
        below = max(below, 1 + resolved[parent[0]][1])
    return _gitlab_merge(merged, own), below


def _gitlab_items(value: Any, where: str) -> list[tuple[str, Any]]:
    if value is None:
        return []
    items = [value] if isinstance(value, tuple) else value
    if not isinstance(items, list):
        raise GitlabUnsupported(f"{where} is neither a string nor a list")
    out: list[tuple[str, Any]] = []
    for item in items:
        if isinstance(item, tuple):
            out.append(item)
        elif isinstance(item, list) and all(isinstance(i, tuple) for i in item):
            out.extend(item)
        else:
            raise GitlabUnsupported(f"{where} has a non-string or deeper item")
    return out


def _gitlab_job(
    name: str,
    jobs: Mapping[str, Any],
    default: Mapping[str, Any],
    resolved: dict[str, tuple[dict[str, Any], int]],
) -> list[list[tuple[str, Any]]] | None:
    """A job's shells, `before_script` + `script` as one and `after_script` as the other; None without a script."""
    job = _gitlab_resolve(name, jobs, resolved)
    if "script" not in job:
        return None
    main = _gitlab_items(
        job.get("before_script", default.get("before_script")), f"{name}.before_script"
    )
    main += _gitlab_items(job.get("script"), f"{name}.script")
    after = _gitlab_items(
        job.get("after_script", default.get("after_script")), f"{name}.after_script"
    )
    return [part for part in (main, after) if part]


def _gitlab_defaults(root: Mapping[str, Any]) -> dict[str, Any]:
    """`default`, with a top-level before_script or after_script read as a default's, since the runner runs them as
    one; both at once, or an `inherit`, is unsupported."""
    default = root.get("default") or {}
    if not isinstance(default, dict) or "inherit" in default:
        raise GitlabUnsupported("an unsupported default")
    for key in ("before_script", "after_script"):
        if key in root and key in default:
            raise GitlabUnsupported(f"both a top-level and a default {key}")
        default = {**default, key: root[key]} if key in root else default
    return default


def _gitlab_jobs(root: Mapping[str, Any]) -> dict[str, Any]:
    """Each job and hidden template. GitLab runs every visible key that is not a global keyword as a job, whose
    definition is a mapping (cubic on #470); a hidden key is never run."""
    jobs: dict[str, Any] = {}
    for name, value in root.items():
        if isinstance(value, dict) and name not in _GITLAB_RESERVED:
            jobs[name] = value
        elif not (name in _GITLAB_RESERVED or name.startswith(".")):
            raise GitlabUnsupported(f"job {name!r} is not a mapping")
    return jobs


def read_scripts(text: str) -> dict[str, list[list[tuple[str, Any]]]]:
    """The bounded GitLab CI reader: per job, its shells, each item with its YAML line (a column table for a simple
    folded item). Local `extends` (GitLab's merge, each job resolved once) and `default` are resolved. These raise
    GitlabUnsupported: anchors, aliases and more than 32 open collections (task_envelope's preflight, before
    composition, Router 6513998438; an indentless sequence opens none, so 32 keys over such sequences compose 64
    levels, measured), include, `!reference`, `inherit`, cycles, merge keys, more than one document, a job that is
    not a mapping and unmappable items. Its caller refuses a NEL, LS or PS first, at which PyYAML breaks a line and
    the file does not."""
    import yaml

    from tools.task_envelope import yaml_preflight

    try:
        found = yaml_preflight(text, 32)
        nodes = [] if found else list(yaml.compose_all(text, Loader=yaml.SafeLoader))
    except (yaml.YAMLError, ValueError, RecursionError) as exc:
        # PyYAML's scanner raises ValueError, never a YAMLError, for an escape past U+10FFFF (cubic on #470).
        raise GitlabUnsupported(f"unparsable: {type(exc).__name__}") from exc
    if found:
        what = (
            "a nesting deeper than 32 levels"
            if found[0] == "depth"
            else f"a YAML {found[0]}"
        )
        raise GitlabUnsupported(f"{what} at line {found[1]}")
    if len(nodes) != 1:
        raise GitlabUnsupported(f"{len(nodes)} documents")
    root = _gitlab_construct(nodes[0])
    if not isinstance(root, dict) or "include" in root:
        raise GitlabUnsupported(
            "include" if isinstance(root, dict) else "the document is not a mapping"
        )
    default = _gitlab_defaults(root)
    jobs = _gitlab_jobs(root)
    resolved: dict[str, tuple[dict[str, Any], int]] = {}
    scripts = {}
    for name in jobs:
        shells = (
            None if name.startswith(".") else _gitlab_job(name, jobs, default, resolved)
        )
        if shells is not None:
            scripts[name] = shells
    return scripts


def analysis_file(items: list[tuple[str, Any]]) -> tuple[str, dict[int, Any]]:
    """An analysis-only POSIX sh file and its map from each analysis line to a YAML line (or a column table)."""
    body, mapping = ["#!/bin/sh"], {}
    for text, line in items:
        if isinstance(line, list):
            body.append(text)
            mapping[len(body)] = line
            continue
        # Only a newline ends an analysis line, so the shell reads the item as it is.
        parts = text.split("\n")
        if len(parts) > 1 and parts[-1] == "":
            parts.pop()
        for offset, part in enumerate(parts):
            body.append(part)
            mapping[len(body)] = line + offset
    return "\n".join(body) + "\n", mapping
