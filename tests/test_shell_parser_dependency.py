"""The pinned shell parser pair is installed, compatible, and reads the constructs
the shell reader relies on (Decision 0108).

The surface extraction below is interim. Decision 0108's item 1 makes host-language
extraction the reader's own (#369), and nothing on `main` owns it yet. When #369
lands, this smoke consumes the reader's extraction and these helpers are deleted, so
the two cannot drift apart (Claude on #394)."""

from __future__ import annotations

import ast
import hashlib
import json
import re
import shlex
import subprocess  # nosec B404 -- test-only boundary; the argv below is literal
import sys
import tarfile
import tempfile
import tomllib
import unittest
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import yaml

from tools.repository_scope import SOURCE_MANIFEST, candidate_paths

ROOT = Path(__file__).resolve().parents[1]
PROBE = Path(__file__).resolve().parent / "shell_parser_probe.py"
# The most the parser probe is sent: far above the repository's corpus, and far
# below what would strain a CI runner.
PROBE_INPUT_LIMIT = 16_777_216  # 16 MiB
# `env`'s documented options: GNU coreutils' `env --help`, and BSD's `-P`.
ENV_FLAGS = set("i0v")
ENV_ARGUMENT_FLAGS = set("uCaPS")
ENV_LONG_FLAGS = {
    "ignore-environment",
    "null",
    "debug",
    "list-signal-handling",
    "block-signal",
    "default-signal",
    "ignore-signal",
    "help",
    "version",
}
ENV_LONG_ARGUMENT = {"unset", "chdir", "argv0"}
ASSIGNMENT = re.compile(r"\A[A-Za-z_][A-Za-z0-9_]*=")
# How many chained `env` invocations a shebang may make.
ENV_CHAIN_LIMIT = 3
# A name shaped like a shell, such as a version-suffixed `bash5`.
SHELL_LIKE = re.compile(r"\A[a-z]*sh[\d.]*\Z")
SHELLS = {"sh", "bash", "dash", "ash"}
OTHER_SHELLS = {
    "zsh",
    "ksh",
    "mksh",
    "oksh",
    "fish",
    "csh",
    "tcsh",
    "yash",
    "posh",
    "hush",
    # Shells whose names do not end in `sh`, so `SHELL_LIKE` misses them (CodeAnt
    # on #396).
    "powershell",
    "nu",
    "elvish",
    "rc",
    "es",
}
# A multi-call binary runs the applet its first argument names, such as `sh`.
MULTI_CALL = {"busybox", "toybox"}
# Programs that run a command given among their own arguments, each with its own
# grammar, which this reader does not parse: a declared list, each failing closed
# (Codex and cubic on #396). One outside it is read as a program.
LAUNCHERS = {
    "timeout",
    "nice",
    "nohup",
    "setsid",
    "stdbuf",
    "ionice",
    "chrt",
    "taskset",
    "flock",
    "chroot",
    "unshare",
    "nsenter",
    "sudo",
    "doas",
    "su",
    "runuser",
    "gosu",
    "su-exec",
    "setpriv",
    "tini",
    "dumb-init",
    "xargs",
    "time",
    "strace",
    "watch",
    # `find` runs its `-exec` action; the rest run a command they are given (Codex
    # on #396).
    "find",
    "parallel",
    "ssh",
    "script",
}

# The YAML keys that hold shell in a CI definition. They are looked for in the
# loaded document, wherever and however written: flow style (CodeAnt on #394), quoted,
# or as an explicit `? key` (Codex on #396).
CI_KEYS = {"run", "script", "before_script", "after_script", "pre_get_sources_script"}
GITLAB_KEYS = ("before_script", "script", "after_script")
# GitLab's job hooks: commands the runner runs before the clone (Codex on #396).
GITLAB_HOOKS = {"pre_get_sources_script"}
# GitLab's global keywords, which are not jobs (GitLab's CI/CD YAML syntax).
GITLAB_GLOBALS = {
    "default",
    "include",
    "stages",
    "variables",
    "workflow",
    "image",
    "services",
    "cache",
    "spec",
}
# What only a GitLab job holds, among the keys this reader knows.
GITLAB_JOB_SIGNS = {*GITLAB_KEYS, "hooks", "extends", "run"}
# What holds shell in a GitLab job.
GITLAB_SHELL = {*GITLAB_KEYS, "hooks", "run"}
# The image variables this repository's GitLab template declares, and why each
# image runs a POSIX shell. Any other variable leaves a job's image unknown (cubic on
# #396).
DECLARED_IMAGE_VARIABLES = {
    # The Gnostoa runtime image, built on a Linux Python base (`Dockerfile`).
    "KNOWLEDGE_KIT_IMAGE",
    # An adopter's verification image, which the template's POSIX `sh` scripts
    # require (`ci/gitlab-ci.yml`).
    "PROJECT_VERIFICATION_IMAGE",
}
# Fence tags for a shell this parser does not read, beyond the shebang's list.
FENCE_OTHER_SHELLS = {"powershell", "ps1", "cmd", "bat", "batch"}
# Microsoft's Windows base images, which run PowerShell.
WINDOWS_IMAGE = re.compile(r"windows|servercore|nanoserver", re.I)
# A name cannot show an image's OS, so only images known to be Linux count (cubic
# on #396): Docker Official Images published for Linux alone, and `python` with a
# Linux variant's tag. Any other image may be Windows.
LINUX_ONLY_IMAGES = {"alpine", "debian", "ubuntu", "busybox"}
LINUX_VARIANT_IMAGES = {"python"}
LINUX_VARIANT_TAG = re.compile(
    r"(?:^|-)(?:slim|alpine|bookworm|bullseye|trixie|buster)"
)
# GitLab's runner, not the file, sets a job's shell (its `config.toml`), even in a
# Linux image (Codex on #396). No file can establish it, so this smoke declares it:
# this repository's GitLab jobs run on a Docker executor with its default shell,
# `sh` or `bash` in a Linux image. The images are still checked.
GITLAB_RUNNER_SHELL = "the Docker executor's default shell"
BOM = b"\xef\xbb\xbf"
# The instruction files whose shell fences agents run, found by name at any depth.
INSTRUCTION_FILES = {"AGENTS.md"}
# A top-level CommonMark fence line: up to three spaces of indent, then three or more
# backticks or tildes (CommonMark 0.31.2, section 4.5).
FENCE_LINE = re.compile(r"(?P<indent> {0,3})(?P<fence>`{3,}|~{3,})(?P<info>.*)")
# A shell fence's opener, and what a container's prefix is made of: block-quote and
# list markers, and indent. A shell fence behind such a prefix is in a list item, a
# block quote or deeper indent; this reader reads the top level only, so it fails
# closed. The prefix is stripped, not matched, so no input backtracks (CodeQL and
# Codacy on #396).
SHELL_FENCE_OPEN = re.compile(
    r"(?:`{3,}|~{3,})[ \t]*(?:bash|sh|shell)(?:[ \t]|$)", re.I
)
CONTAINER_PREFIX = " \t>-+*.)0123456789"
SHELL_INFO = {"bash", "sh", "shell"}
# The runner labels whose implicit shell is bash.
BASH_RUNNERS = {
    # GitHub's documented hosted labels with a Linux or macOS image. A custom
    # self-hosted label, such as `ubuntu-builder`, may name any runner (Codex on
    # #396), so only these imply bash.
    "ubuntu-latest",
    "ubuntu-24.04",
    "ubuntu-22.04",
    "ubuntu-24.04-arm",
    "ubuntu-22.04-arm",
    "macos-latest",
    "macos-15",
    "macos-14",
    "macos-13",
    *(
        f"macos-{v}-{size}"
        for v in ("latest", "15", "14", "13")
        for size in ("large", "xlarge")
    ),
    # A self-hosted runner's operating-system label.
    "linux",
    "macos",
}
# What a program's name is made of; a word with quotes, spaces or escapes names none.
PROGRAM = re.compile(r"[\w./+-]+")
# GNU env's `-S` escapes and what each yields (coreutils `env.c`, `build_argv`).
ENV_ESCAPES = {
    **{char: char for char in "\"#$'\\"},
    "f": "\f",
    "n": "\n",
    "r": "\r",
    "t": "\t",
    "v": "\v",
}
ENV_SPACE = " \t\n\v\f\r"
# What a `-S` step yields besides a character: a separator, or the string's end.
ENV_SEPARATE, ENV_END = "<separate>", "<end>"
# Bash's long options (bash(1)): those that take a word, and the flags.
BASH_LONG_ARGUMENT = {"init-file", "rcfile"}
BASH_LONG_FLAGS = {
    "debugger",
    "dump-po-strings",
    "dump-strings",
    "help",
    "login",
    "noediting",
    "noprofile",
    "norc",
    "posix",
    "pretty-print",
    "restricted",
    "verbose",
    "version",
}
# The single-letter shell options that take a word: `-o` an option, `-O` a shopt.
SHELL_OPTION_WORDS = set("oO")
# A stage's base and name, after any flags such as `--platform`; and a global
# `ARG`, whose default a `FROM` may use.
FROM_LINE = re.compile(
    r"[ \t]*FROM[ \t]+(?P<flags>(?:--\S+[ \t]+)*)(?P<image>\S+)"
    r"(?:[ \t]+AS[ \t]+(?P<stage>\S+))?[ \t]*",
    re.I,
)
ARG_LINE = re.compile(
    r"[ \t]*ARG[ \t]+(?P<name>[A-Za-z_]\w*)(?:=(?P<value>\S*))?[ \t]*", re.I
)
# A BuildKit here-document word: an optional descriptor, `<<`, an optional `-`, and
# a name holding no `<` (BuildKit's `frontend/dockerfile/parser`, measured on #396).
HEREDOC_WORD = re.compile(r"\d*<<-?[^<]*")
# A documentation placeholder, such as `<exact-40-character-parent-sha>`: not shell.
PLACEHOLDER = re.compile(r"<[a-z0-9][a-z0-9-]*>")
# A `RUN` or `SHELL`, also as a trigger that `ONBUILD` defers to a later build
# (CodeAnt on #396).
# A shell-form `CMD`, `ENTRYPOINT` or `HEALTHCHECK CMD` runs through the stage's
# shell too, at the container's start or check (Codex on #396).
RUN = re.compile(
    r"[ \t]*(?P<onbuild>ONBUILD[ \t]+)?"
    r"(?P<instruction>RUN|SHELL|CMD|ENTRYPOINT|HEALTHCHECK)"
    r"[ \t]+(?P<command>.*)",
    re.I,
)
# A lone escape character: one that is itself escaped ends the line instead, as a
# BuildKit build measured (Claude on #396).
CONTINUATION = re.compile(r"(?<!\\)\\[ \t]*\Z")
RUN_FLAGS = re.compile(r"\A(?:--[a-z-]+(?:=\S*)?[ \t]+)*")
MAKEFILE = re.compile(r"\A(?:GNUmakefile|[Mm]akefile|.+\.mk)\Z")
CONTAINER_FILE = re.compile(r"(?i)\A(?:.*\.)?(?:dockerfile|containerfile)(?:\..*)?\Z")


def _probe(scripts: list[str]) -> dict[str, object]:
    """The probe's answer for ``scripts``, from a child process: a native crash fails
    here, as an error the test reports. A corpus beyond the input bound is refused
    before it is sent; the answer, which grows with the input, is bounded with it
    (CodeAnt on #396)."""
    payload = json.dumps(scripts)
    if len(payload) > PROBE_INPUT_LIMIT:
        raise AssertionError(
            f"a corpus of {len(payload)} characters, beyond the probe's input bound"
        )
    done = subprocess.run(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
        [sys.executable, str(PROBE)],
        input=payload,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    if done.returncode != 0:
        raise AssertionError(
            f"the parser probe exited {done.returncode}: {done.stderr[-2000:]}"
        )
    try:
        answer = json.loads(done.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"the parser probe answered no JSON ({exc}): {done.stdout[-2000:]!r}"
        ) from exc
    if not isinstance(answer, dict) or set(answer) != {"abi", "facts"}:
        raise AssertionError(
            f"the parser probe answered another shape: {done.stdout[-2000:]!r}"
        )
    return answer


def _mask_expressions(run: str, path: Path) -> str:
    """Each Actions expression as underscores of its own width, each line break
    kept, so the shell's lines stay where they were (CodeAnt on #394). An
    expression ends at the first `}}` outside its string literals; an unclosed one
    fails closed (Codex on #396)."""
    masked: list[str] = []
    index = 0
    while (start := run.find("${{", index)) != -1:
        end = _expression_end(run, start + 3)
        if end is None:
            raise AssertionError(
                f"{path}: an unclosed expression; extend this extraction"
            )
        masked.extend((run[index:start], re.sub(r"[^\n]", "_", run[start:end])))
        index = end
    return "".join(masked) + run[index:]


def _expression_end(text: str, index: int) -> int | None:
    """Where an expression ends: after its first `}}` outside a string literal.
    Strings quote with `'`, and a doubled `''` inside one is a quote (GitHub's
    expression syntax), so toggling on each `'` reads both."""
    quoted = False
    while index < len(text):
        if text[index] == "'":
            quoted = not quoted
        elif not quoted and text.startswith("}}", index):
            return index + 2
        index += 1
    return None


def _masked(match: re.Match[str]) -> str:
    """A placeholder as a plain word of its own width: `<ref>` becomes `_ref_`."""
    return "_" + match.group(0)[1:-1] + "_"


def _facts(scripts: list[str]) -> list[dict[str, object]]:
    facts: list[dict[str, object]] = _probe(scripts)["facts"]  # type: ignore[assignment]
    return facts


def _workflow_runs(path: Path) -> list[str]:
    """Each shell `run:` value of a workflow or action, with its expressions masked.
    A step, or a job's or workflow's default, in another language fails closed:
    this reads shell only."""
    return _github_runs(path, _load_yaml(path))


def _load_yaml(path: Path) -> object:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    except yaml.YAMLError as exc:
        raise AssertionError(f"{path}: not YAML: {exc}") from exc


def _entered(node: object, above: frozenset[int], where: str) -> frozenset[int]:
    """The containers above a node's children: a container already above is a
    recursive YAML alias, which fails closed. An anchor merely reused elsewhere is not
    above itself, and is read."""
    if id(node) in above:
        raise AssertionError(f"{where}: a recursive YAML alias; extend this extraction")
    return above | {id(node)}


def _runner_shell(runs_on: object) -> str | None:
    """The shell a job's runner gives a `run` without one: bash on Linux and macOS.
    On Windows it is PowerShell, and an expression or a group is decided at run
    time, so neither is known (GitHub's workflow syntax, `defaults.run`)."""
    labels = runs_on if isinstance(runs_on, list) else [runs_on]
    names = [label for label in labels if isinstance(label, str) and "${{" not in label]
    if len(names) != len(labels) or any("windows" in name.lower() for name in names):
        return None
    return "bash" if any(name.lower() in BASH_RUNNERS for name in names) else None


def _github_context(
    path: Path, node: dict[str, object], default: str | None, runner: str | None
) -> tuple[str | None, str | None]:
    """The nearest `defaults.run.shell` and the job's runner's shell, for the
    nodes below this one. A default other than bash or sh fails closed."""
    defaults = node.get("defaults")
    run = defaults.get("run") if isinstance(defaults, dict) else None
    if isinstance(run, dict) and "shell" in run:
        default = run["shell"]
        if default not in ("bash", "sh"):
            raise AssertionError(
                f"{path}: a `{default}` default; extend this extraction"
            )
    if "runs-on" in node:
        runner = _runner_shell(node["runs-on"])
    return default, runner


def _step_run(path: Path, step: dict[str, object], shell: object) -> list[str]:
    """A step's `run`, with its expressions masked, read with its shell. A step
    without one runs an action; a `run` that is not a string fails closed (Claude on
    #396)."""
    if "run" not in step:
        return []
    run = step["run"]
    if not isinstance(run, str):
        raise AssertionError(
            f"{path}: a `run` that is not a string; extend this extraction"
        )
    _check_step_shell(path, shell)
    return [_mask_expressions(run, path)]


def _check_step_shell(path: Path, shell: object) -> None:
    """A step's shell: its own, else its default, else its runner's. Unknown, or
    neither bash nor sh, it fails closed."""
    if shell is None:
        raise AssertionError(
            f"{path}: a `run` whose shell is decided by its runner; "
            "extend this extraction"
        )
    if shell not in ("bash", "sh"):
        raise AssertionError(f"{path}: a `{shell}` step; extend this extraction")


def _github_runs(path: Path, document: object) -> list[str]:
    """Each step's `run`, read where GitHub runs one: a workflow's
    `jobs.<id>.steps[*]`, or a composite action's `runs.steps[*]`. A `run` key
    elsewhere, such as a variable in `env`, is data (Codex on #396). A step's shell
    is its own, else its job's or the workflow's `defaults.run.shell`, else its
    runner's. Another shape on those paths fails closed, and so does a recursive
    alias along them (CodeAnt on #396)."""
    if not isinstance(document, dict) or not ("jobs" in document or "runs" in document):
        if _has_shell_key(path):
            raise _refuse(path.name, "shell in an unknown GitHub shape")
        return []
    above = _entered(document, frozenset(), path.name)
    default, _ = _github_context(path, document, None, None)
    if "runs" in document:
        runs = _mapping(document["runs"], "runs", path)
        return _github_steps(path, runs.get("steps", []), above, None)
    jobs = _mapping(document["jobs"], "jobs", path)
    above = _entered(jobs, above, path.name)
    found: list[str] = []
    for job in jobs.values():
        job = _mapping(job, "a job", path)
        job_default, runner = _github_context(path, job, default, None)
        found.extend(
            _github_steps(
                path,
                job.get("steps", []),
                _entered(job, above, path.name),
                job_default or runner,
            )
        )
    return found


def _mapping(node: object, what: str, path: Path) -> dict[str, object]:
    if not isinstance(node, dict):
        noun = "jobs that are" if what == "jobs" else f"{what} that is"
        raise _refuse(path.name, f"{noun} not a mapping")
    return node


def _github_steps(
    path: Path, steps: object, above: frozenset[int], shell: str | None
) -> list[str]:
    """Each step's `run`, with `shell` the one a step without its own takes."""
    if not isinstance(steps, list):
        raise _refuse(path.name, "steps that are not a list")
    above = _entered(steps, above, path.name)
    found: list[str] = []
    for step in steps:
        step = _mapping(step, "a step", path)
        _entered(step, above, path.name)
        found.extend(_step_run(path, step, step.get("shell") or shell))
    return found


def _gitlab_shaped(document: dict[str, object]) -> bool:
    """Whether a document is a GitLab CI file: `stages` or `default`, or a job with
    a lifecycle script, a hook or an `extends` (Claude on #396)."""
    return (
        "stages" in document
        or "default" in document
        or any(
            isinstance(job, dict) and not GITLAB_JOB_SIGNS.isdisjoint(job)
            for job in document.values()
        )
    )


def _gitlab_scripts(document: dict[str, object], name: str) -> list[str]:
    """Each GitLab CI job's (and `default`'s) hook commands, `before_script`,
    `script` and `after_script`, and the deprecated top-level ones, in document
    order. A list is the lines the runner's shell runs in turn. A global keyword,
    such as `variables`, is not a job (Codex on #396); a job that runs is read only
    in a container image whose shell is known (Codex on #396)."""
    _check_gitlab_shells(document, name)
    found: list[str] = []
    for key, value in document.items():
        if key in GITLAB_KEYS:
            # A deprecated but valid global lifecycle script (Codex on #396).
            found.extend(_script_value(value))
        elif isinstance(value, dict) and (
            key == "default" or key not in GITLAB_GLOBALS
        ):
            found.extend(_gitlab_hooks(value))
            for script in GITLAB_KEYS:
                found.extend(_script_value(value.get(script)))
            found.extend(_gitlab_run_steps(value, key, name))
    return found


def _gitlab_run_steps(job: dict[str, object], key: str, name: str) -> list[str]:
    """A job's `run`: GitLab's CI/CD steps, each with a `script`. A step that runs
    a step component, or any other shape, fails closed (Codex and cubic on #396)."""
    if "run" not in job:
        return []
    steps = job["run"]
    if not isinstance(steps, list):
        raise _refuse(name, f"`{key}`: a GitLab `run` that is not a list of steps")
    found: list[str] = []
    for step in steps:
        if not isinstance(step, dict) or "script" not in step or "step" in step:
            raise _refuse(name, f"`{key}`: a GitLab `run` step that is not a script")
        found.extend(_script_value(step["script"]))
    return found


def _check_gitlab_shells(document: dict[str, object], name: str) -> None:
    """Each job that runs is in an image whose shell is known. A hidden job runs
    in the jobs that extend it, which are checked; one holding shell that no job
    extends is checked by its own image (Claude on #396)."""
    jobs = {
        key: job
        for key, job in document.items()
        if isinstance(job, dict) and key not in GITLAB_GLOBALS
    }
    covered: set[str] = set()
    for key, job in jobs.items():
        if key.startswith(".") or "trigger" in job:
            continue
        lineage = _gitlab_lineage(document, job, key, name)
        covered.update(base for base, _ in lineage)
        _check_gitlab_image(_gitlab_image(document, lineage), key, name)
    for key, job in jobs.items():
        if (
            key.startswith(".")
            and key not in covered
            and not GITLAB_SHELL.isdisjoint(job)
        ):
            lineage = _gitlab_lineage(document, job, key, name)
            _check_gitlab_image(_gitlab_image(document, lineage), key, name)


def _gitlab_lineage(
    document: dict[str, object], job: dict[str, object], key: str, name: str
) -> list[tuple[str, dict[str, object]]]:
    """A job and its `extends` bases, in GitLab's precedence: the job, then its
    last base and that base's own bases, and so on. A base reached twice is read
    once; an unknown or malformed one fails closed."""
    seen: set[str] = set()
    lineage: list[tuple[str, dict[str, object]]] = []
    pending = [(key, job)]
    while pending:
        current_key, current = pending.pop()
        lineage.append((current_key, current))
        extends = current.get("extends", [])
        bases = [extends] if isinstance(extends, str) else extends
        if not isinstance(bases, list):
            raise _refuse(name, f"`{key}`: an `extends` of `{bases}`")
        for base in bases:
            if not isinstance(base, str):
                raise _refuse(name, f"`{key}`: an `extends` of `{base}`")
            if base in seen:
                continue
            parent = document.get(base)
            if not isinstance(parent, dict):
                raise _refuse(name, f"`{key}`: an `extends` of `{base}`")
            seen.add(base)
            pending.append((base, parent))
    return lineage


def _gitlab_image(
    document: dict[str, object], lineage: list[tuple[str, dict[str, object]]]
) -> object:
    """A job's image: the first its lineage gives, else `default`'s, else the
    deprecated global one, unless `inherit` drops the default (Codex on #396)."""
    for _, current in lineage:
        if "image" in current:
            return current["image"]
    # The nearest `inherit: default` in the lineage, as GitLab merges a base's keys
    # into the job (Codex on #396).
    inherited: object = True
    for _, current in lineage:
        inherit = current.get("inherit")
        if isinstance(inherit, dict) and "default" in inherit:
            inherited = inherit["default"]
            break
    if inherited is not True and not (
        isinstance(inherited, list) and "image" in inherited
    ):
        return None
    default = document.get("default")
    if isinstance(default, dict) and "image" in default:
        return default["image"]
    return document.get("image")


def _linux_image(reference: str) -> bool:
    """Whether an image reference names an image known to be Linux. A registry
    other than Docker Hub, a bare digest of a multi-OS image, or another tag is
    not known (cubic on #396)."""
    name = reference.partition("@")[0]
    repository, _, tag = (
        name.rpartition(":") if ":" in name.rsplit("/", 1)[-1] else (name, "", "")
    )
    repository = repository.lower().removeprefix("docker.io/").removeprefix("library/")
    if repository in LINUX_ONLY_IMAGES:
        return True
    return repository in LINUX_VARIANT_IMAGES and bool(LINUX_VARIANT_TAG.search(tag))


def _check_gitlab_image(image: object, key: str, name: str) -> None:
    """A job's scripts run with the declared runner shell (`GITLAB_RUNNER_SHELL`)
    only in an image known to be Linux, or one a declared variable names. A Windows
    base image runs PowerShell, another image's OS is unknown, and with no image the
    runner decides."""
    reference = image.get("name") if isinstance(image, dict) else image
    if not isinstance(reference, str) or not reference:
        raise _refuse(name, f"`{key}`: a GitLab job whose shell its runner decides")
    if WINDOWS_IMAGE.search(reference):
        raise _refuse(name, f"`{key}`: a Windows image")
    variables = re.findall(r"\$\{?(\w+)", reference)
    for variable in variables:
        if variable not in DECLARED_IMAGE_VARIABLES:
            raise _refuse(name, f"`{key}`: an image `{variable}` decides")
    # A declared variable names the whole image, as the template defines it; one
    # composed into a larger reference names something else (CodeAnt on #396).
    if variables and not re.fullmatch(r"\$\{?\w+\}?", reference.strip()):
        raise _refuse(name, f"`{key}`: an image a declared variable only partly names")
    if not variables and not _linux_image(reference):
        raise _refuse(name, f"`{key}`: an image not known to be Linux")


def _gitlab_hooks(job: dict[str, object]) -> list[str]:
    """A job's hook commands, which run before its scripts. A hook this reader does
    not know fails closed."""
    hooks = job.get("hooks")
    if hooks is None:
        return []
    if not isinstance(hooks, dict):
        raise AssertionError(
            "GitLab hooks that are not a mapping; extend this extraction"
        )
    for hook in hooks:
        if hook not in GITLAB_HOOKS:
            raise AssertionError(
                f"an unknown GitLab hook `{hook}`; extend this extraction"
            )
    return _script_value(hooks.get("pre_get_sources_script"))


def _script_value(value: object) -> list[str]:
    """A `before_script`, `script` or `after_script` value as shell: a string, or a
    list of lines."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return ["\n".join(_script_lines(value))]
    return []


def _script_lines(value: list[object]) -> list[str]:
    """A GitLab `script` array, flattened at any depth as GitLab flattens nested
    arrays (YAML anchors and aliases build them). A line that is not a string fails
    closed rather than being stringified (CodeAnt on #396). A `!reference` tag never
    reaches here: the YAML load refuses it, and that fails closed (cubic on #396)."""
    lines: list[str] = []
    top = _entered(value, frozenset(), "a GitLab script")
    stack: list[tuple[object, frozenset[int]]] = [
        (item, top) for item in reversed(value)
    ]
    while stack:
        item, above = stack.pop()
        if isinstance(item, list):
            inner = _entered(item, above, "a GitLab script")
            stack.extend((nested, inner) for nested in reversed(item))
        elif isinstance(item, str):
            lines.append(item)
        else:
            raise AssertionError(
                f"a `{type(item).__name__}` script line; extend this extraction"
            )
    return lines


def _github_shaped(document: object) -> bool:
    """A GitHub workflow (`on` and `jobs`; YAML reads a bare `on` as true) or action
    (`runs.using`). A GitLab job may itself be named `jobs` or `runs` (CodeAnt on
    #396)."""
    if not isinstance(document, dict):
        return False
    workflow = isinstance(document.get("jobs"), dict) and (
        "on" in document or True in document
    )
    runs = document.get("runs")
    return workflow or (isinstance(runs, dict) and "using" in runs)


def _ci_shell(path: Path, under_github: bool) -> list[str]:
    """The shell of a CI definition, read by its shape wherever it sits: a GitHub
    workflow or action, or a GitLab CI file. A YAML file outside `.github` that
    holds a shell key in another shape fails closed (CodeAnt on #394)."""
    if not under_github and not _has_shell_key(path):
        return []
    document = _load_yaml(path)
    if under_github or _github_shaped(document):
        return _github_runs(path, document)
    if isinstance(document, dict) and _gitlab_shaped(document):
        return _gitlab_scripts(document, path.name)
    raise AssertionError(
        f"{path.name}: shell in an unknown CI shape; extend this extraction"
    )


def _has_shell_key(path: Path) -> bool:
    """Whether any mapping in a YAML file has a key that holds shell in a CI
    definition. The file is composed, not constructed: its node graph is read
    without its tags' meaning, so a tag the safe loader refuses, such as
    `mkdocs.yml`'s `!!python/name:`, hides no key. Extraction still loads safely,
    so a tagged CI file, such as one with GitLab's `!reference`, fails closed. Each
    node is visited once, so a recursive alias ends."""
    try:
        root = yaml.compose(
            path.read_text(encoding="utf-8-sig"), Loader=yaml.SafeLoader
        )
    except yaml.YAMLError as exc:
        raise AssertionError(f"{path}: not YAML: {exc}") from exc
    seen: set[int] = set()
    stack: list[yaml.Node | None] = [root]
    while stack:
        node = stack.pop()
        if not isinstance(node, yaml.CollectionNode) or id(node) in seen:
            continue
        seen.add(id(node))
        if isinstance(node, yaml.SequenceNode):
            stack.extend(node.value)
            continue
        for key, value in node.value:
            if isinstance(key, yaml.ScalarNode) and key.value in CI_KEYS:
                return True
            stack.extend((key, value))
    return False


def _refuse(name: str, reason: str) -> AssertionError:
    return AssertionError(f"{name}: {reason}; extend this extraction")


def _shebang_words(head: bytes, name: str) -> list[str]:
    """The command a shebang line runs, with its arguments. Through `env`, its whole
    documented grammar is read (GNU `env --help`, and BSD's `-P`): options and their
    arguments, `-S` strings split again, then assignments, then the command. A word
    outside that grammar, a line that cannot be split, or no command fails closed, so
    nothing is guessed (Codex, Claude and CodeAnt on #394)."""
    try:
        line = head[2:].split(b"\n", 1)[0].decode("utf-8")
    except UnicodeDecodeError as exc:
        raise _refuse(name, "an unreadable shebang") from exc
    # A kernel splits on whitespace and reads no quotes; `env -S` reads its own.
    words = _follow_launchers(line.split(), name, split=True)
    if not words or not PROGRAM.fullmatch(words[0]):
        raise _refuse(name, "an unreadable shebang")
    return words


def _follow_launchers(words: list[str], name: str, *, split: bool) -> list[str]:
    """The command a chain of launchers runs, with its arguments: `env`, read by
    its own reader, and a multi-call binary's applet, to a bound. `split` admits
    `env -S`, whose words come from one string, as in a shebang. One walk serves
    shebangs and exec forms (Claude on #396); a launcher left after the bound fails
    closed (Codex on #396)."""
    for _ in range(ENV_CHAIN_LIMIT):
        launcher = Path(words[0]).name if words else ""
        if launcher == "env":
            words = _env_operands(words[1:], name, split=split)
        elif launcher in MULTI_CALL:
            words = words[1:]
        else:
            return _refuse_launched_shell(words, name)
    if words and (Path(words[0]).name == "env" or Path(words[0]).name in MULTI_CALL):
        raise _refuse(name, "a launcher chain beyond the bound")
    # A launcher right after the bound's last wrapper is still one (Codex on #396).
    return _refuse_launched_shell(words, name)


def _refuse_launched_shell(words: list[str], name: str) -> list[str]:
    """`words` unchanged, unless they are a declared launcher: each runs a command by
    its own grammar, which may hand it to a shell without naming one, as `su -c`
    does, or name a shell this reader does not list. So one fails closed, whatever
    follows it (Codex and cubic on #396)."""
    launcher = Path(words[0]).name if words else ""
    if launcher in LAUNCHERS:
        raise _refuse(name, f"a `{launcher}` launcher")
    return words


def _env_operands(rest: list[str], name: str, *, split: bool = True) -> list[str]:
    """`env`'s arguments after its options and assignments: the command and its
    arguments. Without `split`, as in an exec-form instruction whose words are
    already apart, `-S` would split one again and fails closed (Codex on #396)."""
    while rest and rest[0].startswith("-") and rest[0] != "--":
        word, rest = rest[0], rest[1:]
        if word == "-":
            continue
        if not split and _env_splits(word):
            raise _refuse(name, "an exec-form `env -S`")
        handler = _env_long_option if word.startswith("--") else _env_short_options
        rest = handler(word, rest, name)
    if rest and rest[0] == "--":
        rest = rest[1:]
    while rest and ASSIGNMENT.match(rest[0]):
        rest = rest[1:]
    return rest


def _env_splits(word: str) -> bool:
    """Whether an `env` option word asks for `-S`: `--split-string`, or `S` where
    getopt reads an option letter. A letter taking an argument takes the rest of
    the word, so the `S` of `-uSHELL` is `-u`'s (cubic on #396)."""
    if word.startswith("--"):
        return word[2:].partition("=")[0] == "split-string"
    for letter in word[1:]:
        if letter not in ENV_FLAGS:
            return letter == "S"
    return False


def _env_long_option(word: str, rest: list[str], name: str) -> list[str]:
    option, equals, value = word[2:].partition("=")
    if option in ENV_LONG_FLAGS:
        return rest
    if option == "split-string":
        return _env_split(" ".join([value, *rest]), name)
    if option not in ENV_LONG_ARGUMENT:
        raise _refuse(name, f"an unknown env option `{word}`")
    if not equals:
        _, rest = _env_argument(rest, name)
    return rest


def _env_short_options(word: str, rest: list[str], name: str) -> list[str]:
    for index, letter in enumerate(word[1:], start=1):
        if letter in ENV_FLAGS:
            continue
        if letter not in ENV_ARGUMENT_FLAGS:
            raise _refuse(name, f"an unknown env option `{word}`")
        value = word[index + 1 :]
        if letter == "S":
            return _env_split(" ".join([value, *rest]), name)
        if not value:
            _, rest = _env_argument(rest, name)
        return rest
    return rest


def _env_split(value: str, name: str) -> list[str]:
    """GNU `env -S`'s words, read as `env` reads them (coreutils `env.c`,
    `build_argv`). Linux passes a shebang's rest as one argument, so `-S` takes the
    rest of the line (rejoined here). Quotes group; outside them, whitespace and
    `\\_` separate; `#` at a word's start and `\\c` end the string. An expansion,
    which the environment decides, an unknown escape or an open quote fails closed
    (CodeAnt on #396)."""
    words: list[str] = []
    separated, quote, index = True, "", 0
    while index < len(value):
        added, index, quote = _env_step(value, index, quote, separated, name)
        if added == ENV_END:
            return words
        if added == ENV_SEPARATE:
            separated = True
            continue
        if separated:
            words.append("")
            separated = False
        words[-1] += added
    if quote:
        raise _refuse(name, "an unreadable shebang")
    return words


def _env_argument(rest: list[str], name: str) -> tuple[str, list[str]]:
    if not rest:
        raise _refuse(name, "an unreadable shebang")
    return rest[0], rest[1:]


def _env_step(
    value: str, index: int, quote: str, separated: bool, name: str
) -> tuple[str, int, str]:
    """One step of reading a `-S` string at `index`: what it adds (a character, ""
    for an opening or closing quote, which starts a word, `ENV_SEPARATE` or
    `ENV_END`), the next index, and the quote then open."""
    char = value[index]
    index += 1
    if char in "'\"" and quote in ("", char):
        return "", index, "" if quote else char
    if char in ENV_SPACE and not quote:
        return ENV_SEPARATE, index, quote
    if char == "#" and separated:
        return ENV_END, index, quote
    if char == "$" and quote != "'":
        raise _refuse(name, "an unreadable shebang")
    # Inside single quotes, only a doubled backslash and `\'` are escapes.
    if char != "\\" or (quote == "'" and value[index : index + 1] not in ("\\", "'")):
        return char, index, quote
    return _env_escape(value[index : index + 1], quote, name), index + 1, quote


def _env_escape(escape: str, quote: str, name: str) -> str:
    """What a `-S` escape yields. `\\c` ends the string, and `\\_` separates
    words outside quotes and is a space inside them. An unknown escape, `\\c`
    inside quotes, or a backslash at the end fails closed."""
    if escape == "c" and not quote:
        return ENV_END
    if escape == "_":
        return " " if quote else ENV_SEPARATE
    if escape not in ENV_ESCAPES:
        raise _refuse(name, "an unreadable shebang")
    return ENV_ESCAPES[escape]


def _exec_form_shell(argv: list[str], *, open_ended: bool = False) -> list[str]:
    """An exec-form `RUN` of `sh`, `bash`, `dash` or `ash` still hands its `-c`
    command to that shell; another shell fails closed (cubic on #396). The options
    are read as the shell reads them, up to the first word that is not one. With
    `-c` among them, that word is the command; otherwise it is a script's path
    (CodeAnt on #396). A multi-call binary's applet is the program. A container's
    process is `open_ended`: a `-c` without its command there takes it from a later
    stage or from the run, so it is not yet shell (cubic on #396)."""
    # `env` and a multi-call binary launch the command after them (Codex on #396).
    argv = _follow_launchers(argv, "RUN", split=False)
    program = Path(argv[0]).name if argv else ""
    if program in OTHER_SHELLS:
        raise AssertionError(f"an exec-form `{program}` RUN; extend this extraction")
    if program not in SHELLS:
        return []
    inline, words = _shell_options(argv[1:])
    if words[:1] == ["-"]:
        words = words[1:]
    if not inline:
        # The first word after the options is a script in the image, which this
        # reader cannot map back to the repository (Codex on #396); none means the
        # shell reads standard input.
        if words:
            raise AssertionError(
                "an exec-form shell running a script; extend this extraction"
            )
        return []
    if not words and open_ended:
        return []
    if not words:
        raise AssertionError("a `-c` without its command; extend this extraction")
    return [words[0]]


def _shell_options(words: list[str]) -> tuple[bool, list[str]]:
    """Whether `-c` is among a shell's options, and the words after the options."""
    inline = False
    while words and words[0][:1] in ("-", "+") and len(words[0]) > 1:
        word, words = words[0], words[1:]
        if word == "--":
            break
        if word.startswith("--"):
            words = _shell_long_option(word, words)
            continue
        if "c" in word[1:]:
            if word[0] == "+":
                raise _unknown_shell_option(word)
            inline = True
        for _ in range(sum(letter in SHELL_OPTION_WORDS for letter in word[1:])):
            words = _shell_option_word(words)
    return inline, words


def _shell_long_option(word: str, words: list[str]) -> list[str]:
    if word[2:] in BASH_LONG_ARGUMENT:
        return _shell_option_word(words)
    if word[2:] not in BASH_LONG_FLAGS:
        raise _unknown_shell_option(word)
    return words


def _unknown_shell_option(word: str) -> AssertionError:
    return AssertionError(f"an unknown shell option `{word}`; extend this extraction")


def _shell_option_word(words: list[str]) -> list[str]:
    """The words after an option's own word."""
    if not words:
        raise AssertionError("a shell option without its word; extend this extraction")
    return words[1:]


def _exec_form(command: str) -> bool:
    """Whether a `RUN` is in exec form: a JSON list of strings. A shell command that
    starts with `[`, such as a test, is shell (CodeAnt on #394)."""
    try:
        argv = json.loads(command)
    except json.JSONDecodeError:
        return False
    return isinstance(argv, list) and all(isinstance(word, str) for word in argv)


def _check_shell_instruction(argument: str) -> None:
    """A Dockerfile `SHELL` keeps the `RUN` lines shell only when it names `sh`,
    `bash`, `dash` or `ash`; another program fails closed (CodeAnt on #394)."""
    try:
        argv = json.loads(argument)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"an unreadable SHELL: {argument!r}") from exc
    program = Path(argv[0]).name if isinstance(argv, list) and argv else ""
    if program not in SHELLS:
        raise AssertionError(f"a `{program}` SHELL; extend this extraction")
    # Docker appends a shell-form `RUN` to the whole vector, so the vector's
    # options must end with `-c`, leaving no command of its own (Codex on #396).
    inline, rest = _shell_options(argv[1:])
    if not inline or rest:
        raise AssertionError(
            f"a SHELL that does not hand RUN to `-c`: {argument!r}; extend this extraction"
        )


def _overrides_build_arg(text: str, name: str) -> bool:
    """Whether `text` passes `--build-arg` for `name`, with its value or from the
    environment, its word after `=`, a space or a continued line (cubic on #396)."""
    pattern = rf"--build-arg(?:=|[\s\\]+)[\"']?{re.escape(name)}\b"
    return re.search(pattern, text) is not None


def _dockerfile_runs(text: str) -> list[str]:
    """Each shell-form `RUN` instruction, as Docker hands it to the shell: its
    continuation lines joined, comment lines inside it dropped, its flags removed.
    The exec form is not shell; a here-document or another escape character fails
    closed, and so does a `RUN` in a stage whose shell is unknown (Codex on #396)."""
    # The default escape, a backslash, may be stated; another is not read here
    # (CodeAnt on #396).
    if re.search(r"^#[ \t]*escape[ \t]*=(?![ \t]*\\[ \t]*$)", text, re.M | re.I):
        raise AssertionError("a Dockerfile escape directive; extend this extraction")
    runs: list[str] = []
    state = _Stages()
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        index += 1
        if state.read(line):
            continue
        match = RUN.fullmatch(line)
        if match is None:
            continue
        command = match["command"]
        deferred = match["onbuild"] is not None
        if match["instruction"].upper() == "SHELL":
            _check_shell_instruction(command)
            # `ONBUILD SHELL` changes no current stage, only the `ONBUILD RUN`s
            # after it (Codex on #396).
            state.set_shell("sh", deferred=deferred)
            continue
        # BuildKit continues past spaces or tabs after the escape character, and
        # skips empty and comment lines inside a continuation (Codex on #396).
        while (end := CONTINUATION.search(command)) and index < len(lines):
            line = lines[index]
            index += 1
            if line.strip() and not line.lstrip().startswith("#"):
                command = command[: end.start()] + line
        runs.extend(
            _instruction_runs(match["instruction"].upper(), command, deferred, state)
        )
    if state.started:
        state.finish()
    return runs + state.surfaces


def _instruction_runs(
    instruction: str, command: str, deferred: bool, state: _Stages
) -> list[str]:
    """The shell one `RUN`, `CMD`, `ENTRYPOINT` or `HEALTHCHECK` hands over, its
    continuation lines already joined."""
    if instruction == "HEALTHCHECK":
        healthcheck = _healthcheck_command(command)
        if healthcheck is None:
            return []
        command = healthcheck
    # Only `RUN` takes `--mount`-style flags (cubic on #396).
    if instruction == "RUN":
        command = RUN_FLAGS.sub("", command)
    # A stage's process is read whole when the stage ends (Codex and cubic on #396).
    if instruction in {"CMD", "ENTRYPOINT"}:
        state.record(instruction, command, deferred)
        return []
    if _exec_form(command):
        return _exec_form_shell(json.loads(command))
    return [_shell_form_run(command, state.shell_for(deferred))]


class _Stages:
    """The stages read so far, and the current stage's shell: its base's, `sh`
    for a Linux image, a named stage's for a stage, `SHELL`'s once set. A global
    `ARG`'s default resolves in `FROM`. A Windows base, `scratch` or an unresolved
    reference leaves it unknown (Codex on #396)."""

    def __init__(self) -> None:
        self.args: dict[str, str] = {}
        self.shells: dict[str, str | None] = {}
        self.shell: str | None = None
        self.stage = ""
        self.started = False
        # The shell an `ONBUILD SHELL` set for a later build's triggers.
        self.deferred: str | None = None
        # The container's process: each named stage's `ENTRYPOINT` and `CMD`, and
        # the current stage's, read whole when the stage ends (Codex on #396).
        self.processes: dict[str, _Process] = {}
        self.process = _Process()
        # This stage's `ONBUILD ENTRYPOINT` and `CMD`, which a later build runs in
        # order, as if after its `FROM` (Codex on #396).
        self.triggers: list[tuple[str, _Form]] = []
        self.stage_triggers: dict[str, list[tuple[str, _Form]]] = {}
        self.surfaces: list[str] = []

    def read(self, line: str) -> bool:
        """Whether a line is a `FROM`, or a global `ARG`, and so read here."""
        if (stage := FROM_LINE.fullmatch(line)) is not None:
            if self.started:
                self.finish()
            self.started = True
            self.process = self._base_process(stage["image"], stage["flags"])
            self.shell = self._base_shell(stage["image"], stage["flags"])
            self.stage = (stage["stage"] or "").lower()
            self.deferred = None
            self.set_shell(self.shell)
            return True
        if not self.started and (arg := ARG_LINE.fullmatch(line)) is not None:
            if arg["value"] is not None:
                self.args[arg["name"]] = arg["value"].strip("\"'")
            return True
        return False

    def set_shell(self, shell: str | None, *, deferred: bool = False) -> None:
        if deferred:
            self.deferred = shell
            return
        self.shell = shell
        if self.stage:
            self.shells[self.stage] = shell

    def shell_for(self, deferred: bool) -> str | None:
        """The shell a `RUN` runs in: an `ONBUILD RUN`'s is the later build's,
        whose base is this stage, after any `ONBUILD SHELL` before it."""
        return (self.deferred or self.shell) if deferred else self.shell

    def record(self, instruction: str, command: str, deferred: bool) -> None:
        """A stage's `ENTRYPOINT` or `CMD`, or an `ONBUILD` one for a later build.
        A shell form keeps the shell in effect where it is written."""
        value: _Form
        if _exec_form(command):
            value = json.loads(command) or None
        else:
            value = _ShellForm(command, self.shell_for(deferred)) if command else None
        if deferred:
            self.triggers.append((instruction, value))
        else:
            self.process.apply(instruction, value)

    def finish(self) -> None:
        """The process of the stage that ends, and the one a later build gets from
        its `ONBUILD` triggers."""
        process = self.process
        if self.stage:
            self.processes[self.stage] = process
            self.stage_triggers[self.stage] = self.triggers
        if process.set_here:
            self.surfaces.extend(process.runs())
        if self.triggers:
            later = _Process(process.entrypoint, process.cmd, process.known)
            for instruction, value in self.triggers:
                later.apply(instruction, value)
            self.surfaces.extend(later.runs())
        self.triggers = []

    def _resolve(self, image: str, flags: str) -> str | None:
        """The base a `FROM` names, its global `ARG`s resolved; a platform other
        than Linux, or a name a variable still holds, is unknown (Codex on #396)."""
        platform = re.search(r"--platform=(\S+)", flags)
        if platform and not platform[1].lower().startswith("linux/"):
            return None
        resolved = re.sub(
            r"\$\{(\w+)\}|\$(\w+)",
            lambda match: self.args.get(match[1] or match[2], match[0]),
            image,
        )
        return None if "$" in resolved else resolved.lower()

    def _base_shell(self, image: str, flags: str) -> str | None:
        resolved = self._resolve(image, flags)
        if resolved is None:
            return None
        if resolved in self.shells:
            return self.shells[resolved]
        return "sh" if _linux_image(resolved) else None

    def _base_process(self, image: str, flags: str) -> _Process:
        """A named stage's process, inherited; none for `scratch` or a Linux image
        this reader knows, whose official images set no `ENTRYPOINT`; otherwise an
        unknown one."""
        resolved = self._resolve(image, flags)
        if resolved is not None and resolved in self.processes:
            inherited = self.processes[resolved]
            process = _Process(inherited.entrypoint, inherited.cmd, inherited.known)
            # Its `ONBUILD` triggers run first, as if right after this `FROM`
            # (Codex on #396).
            for instruction, value in self.stage_triggers.get(resolved, []):
                process.apply(instruction, value)
            return process
        known = resolved is not None and (
            resolved == "scratch" or _linux_image(resolved)
        )
        return _Process(known=known)


@dataclass(frozen=True)
class _ShellForm:
    """A shell-form `ENTRYPOINT` or `CMD`: its text, and the shell it runs in."""

    text: str
    shell: str | None


# An exec form's words, a shell form, or none.
_Form = list[str] | _ShellForm | None


@dataclass
class _Process:
    """A stage's `ENTRYPOINT` and `CMD`; whether the entrypoint is known; and
    whether this stage set either."""

    entrypoint: _Form = None
    cmd: _Form = None
    known: bool = True
    cmd_set: bool = False
    set_here: bool = False

    def apply(self, instruction: str, value: _Form) -> None:
        """An `ENTRYPOINT` or `CMD`. An `ENTRYPOINT` resets an inherited `CMD`, as
        Docker's builder does."""
        self.set_here = True
        if instruction == "ENTRYPOINT":
            self.entrypoint = value
            self.known = True
            if not self.cmd_set:
                self.cmd = None
        else:
            self.cmd = value
            self.cmd_set = True

    def runs(self) -> list[str]:
        """The shell this process runs, as Docker combines it: a shell-form
        `ENTRYPOINT` alone, ignoring `CMD`; an exec-form one with `CMD` as its
        arguments, a shell-form `CMD` through its shell; or `CMD` alone (cubic and
        Codex on #396). An exec-form `CMD` under an unknown base's `ENTRYPOINT`
        fails closed; a shell-form one is read, since it may run."""
        entrypoint, cmd = self.entrypoint, self.cmd
        if isinstance(entrypoint, _ShellForm):
            return [_shell_form_run(entrypoint.text, entrypoint.shell)]
        if entrypoint is None or not self.known:
            if isinstance(cmd, _ShellForm):
                return [_shell_form_run(cmd.text, cmd.shell)]
            if cmd is not None and not self.known:
                raise AssertionError(
                    "an exec-form `CMD` under an unknown base's `ENTRYPOINT`; "
                    "extend this extraction"
                )
            return _exec_form_shell(cmd, open_ended=True) if cmd else []
        argv = list(entrypoint)
        if isinstance(cmd, _ShellForm):
            argv += [cmd.shell or "/bin/sh", "-c", cmd.text]
        elif cmd is not None:
            argv += cmd
        return _exec_form_shell(argv, open_ended=True)


def _healthcheck_command(argument: str) -> str | None:
    """A `HEALTHCHECK`'s command: what follows its options and `CMD`. `NONE`
    runs nothing; another form fails closed. The options are read word by word, so
    no pattern backtracks over them (Codacy on #396)."""
    words = argument.strip()
    while words.startswith("--"):
        parts = re.split(r"[ \t]+", words, maxsplit=1)
        words = parts[1] if len(parts) == 2 else ""
    keyword, *command = re.split(r"[ \t]+", words, maxsplit=1)
    if keyword.upper() == "NONE" and not command:
        return None
    if keyword.upper() != "CMD" or not command:
        raise AssertionError(
            f"an unreadable HEALTHCHECK: {argument!r}; extend this extraction"
        )
    return command[0]


def _shell_form_run(command: str, shell: str | None) -> str:
    """A shell-form `RUN`'s command, read only in a stage whose shell is known.
    BuildKit reads a here-document from a whole word, its quotes kept; `<<` inside
    quotes, inside a word or as `<<<` is shell (CodeAnt and cubic on #396)."""
    if shell is None:
        raise AssertionError(
            f"a RUN whose shell is unknown: {command!r}; extend this extraction"
        )
    try:
        words = shlex.split(command, posix=False)
    except ValueError as exc:
        raise AssertionError(
            f"an unreadable RUN: {command!r}; extend this extraction"
        ) from exc
    if any(HEREDOC_WORD.fullmatch(word) for word in words):
        raise AssertionError("a RUN here-document; extend this extraction")
    return command


def _files(root: Path) -> list[Path]:
    """The repository's candidate files, from their owner: Git's tracked files in a
    checkout, or the runtime image's source manifest (`tools/repository_scope.py`).
    A hidden source directory is read like any other; an untracked file is not
    (Codex on #394)."""
    return [
        path
        for relative in candidate_paths(root)
        if (path := root / relative).is_file() and not path.is_symlink()
    ]


def _shell_surfaces(root: Path = ROOT) -> dict[str, str]:
    """Every shell surface of the kinds the frozen corpus held (Decision 0108), and
    GitLab CI's:
    - each workflow or action `run:` value, and each GitLab CI script, by the CI
      definition's shape, anywhere;
    - each `sh`, `bash`, `dash` or `ash` script, by its shebang's interpreter,
      anywhere; another shell's script fails closed;
    - each shell fence of the instruction files, its placeholders masked;
    - each shell-form `RUN` of the Dockerfile.
    A Make recipe or another container file fails closed: none is tracked, and none
    was in the corpus."""
    surfaces: dict[str, str] = {}
    for path in _files(root):
        surfaces.update(_surfaces_of(path, path.relative_to(root).as_posix()))
    return surfaces


def _surfaces_of(path: Path, name: str) -> dict[str, str]:
    """One file's shell surfaces, by what the file is."""
    if MAKEFILE.match(path.name):
        raise _refuse(name, "a Make recipe")
    # A shebang decides first, whatever the file's name (Codex on #394).
    with path.open("rb") as handle:
        head = handle.read(256).removeprefix(BOM)
    if head.startswith(b"#!"):
        return _script_surface(path, name, head)
    if path.suffix in (".yml", ".yaml"):
        return _numbered(name, _ci_shell(path, name.startswith(".github/")))
    if path.name in INSTRUCTION_FILES:
        fences = _shell_fences(path.read_text(encoding="utf-8-sig"), name)
        return _numbered(name, [PLACEHOLDER.sub(_masked, fence) for fence in fences])
    if CONTAINER_FILE.match(path.name) and path.name != "Dockerfile":
        raise _refuse(name, "a container file")
    if path.name == "Dockerfile":
        return _numbered(name, _dockerfile_runs(path.read_text(encoding="utf-8-sig")))
    return {}


def _shell_fences(text: str, name: str) -> list[str]:
    """Each top-level shell fence's content, as CommonMark reads it. The opener's
    indent is removed from each line. A run of the opener's own character, at least
    as long and with nothing after it, closes it, or the end does. A shell fence in a
    list item or a block quote fails closed (CodeAnt, Codex, cubic and Claude on
    #396)."""
    fences: list[str] = []
    lines = text.splitlines(keepends=True)
    index = 0
    while index < len(lines):
        line = lines[index].rstrip("\r\n")
        index += 1
        opener = FENCE_LINE.fullmatch(line)
        # A backtick fence's info string holds no backtick (CommonMark, 4.5).
        if opener is None or (opener["fence"][0] == "`" and "`" in opener["info"]):
            rest = line.lstrip(CONTAINER_PREFIX)
            prefix = line[: len(line) - len(rest)]
            if SHELL_FENCE_OPEN.match(rest) and not re.fullmatch(" {0,3}", prefix):
                raise _refuse(name, "a shell fence inside a list or quote")
            continue
        fence, indent = opener["fence"], len(opener["indent"])
        closer = re.compile(rf" {{0,3}}{re.escape(fence[0])}{{{len(fence)},}}[ \t]*")
        body: list[str] = []
        while index < len(lines) and not closer.fullmatch(lines[index].rstrip("\r\n")):
            content = lines[index]
            body.append(content[min(indent, len(content) - len(content.lstrip(" "))) :])
            index += 1
        index += 1
        language = (opener["info"].split() or [""])[0].lower()
        if language in OTHER_SHELLS | FENCE_OTHER_SHELLS or (
            language not in SHELL_INFO and SHELL_LIKE.match(language)
        ):
            # A shell this parser does not read (CodeAnt on #396).
            raise _refuse(name, f"a `{language}` fence")
        if language in SHELL_INFO:
            fences.append("".join(body))
    return fences


def _script_surface(path: Path, name: str, head: bytes) -> dict[str, str]:
    """A script read when its shebang runs `sh`, `bash`, `dash` or `ash`; another
    shell, or a shell-like name no known shell, fails closed (Claude on #394)."""
    words = _shebang_words(head, name)
    command = Path(words[0]).name
    if command in OTHER_SHELLS:
        raise _refuse(name, f"a `{command}` script")
    if command not in SHELLS and SHELL_LIKE.match(command):
        raise _refuse(name, f"an unrecognised shell `{command}`")
    if command not in SHELLS:
        return {}
    # The shebang's own options decide what the shell reads (Codex on #396): with
    # `-c`, its command string, the file only `$0`; with `-s`, standard input.
    inline, rest = _shell_options(words[1:])
    options = words[1 : len(words) - len(rest)]
    reads_input = any(
        word[:1] == "-" and word[:2] != "--" and "s" in word[1:] for word in options
    )
    # With `-c`, bash ignores `-s`, but dash runs the string and then reads
    # standard input too, so only bash's is read (cubic on #396).
    if reads_input and not (inline and command == "bash"):
        raise _refuse(name, "a shebang shell that reads standard input")
    if inline:
        rest = rest[1:] if rest[:1] == ["-"] else rest
        if not rest:
            raise _refuse(name, "a shebang `-c` without its command")
        return {name: rest[0]}
    # A shell script that is not UTF-8 fails here, loudly.
    return {name: path.read_text(encoding="utf-8-sig")}


def _numbered(name: str, texts: list[str]) -> dict[str, str]:
    return {f"{name}#{index}": text for index, text in enumerate(texts)}


def _declared(root: Path, *, unlisted: tuple[str, ...] = ()) -> Path:
    """``root`` with a source manifest listing its files, but ``unlisted``."""
    names = sorted(
        relative
        for path in root.rglob("*")
        if path.is_file()
        and path.name != SOURCE_MANIFEST
        and (relative := path.relative_to(root).as_posix()) not in unlisted
    )
    (root / SOURCE_MANIFEST).write_bytes(b"".join(n.encode() + b"\0" for n in names))
    return root


class ShellParserDependencyTests(unittest.TestCase):
    def test_the_pinned_pair_is_installed(self) -> None:
        """`tree-sitter` 0.26.0 segfaulted with this grammar in the evaluation, so
        the pair is pinned together; the grammar's ABI is the runtime's.

        This smoke cannot reproduce that crash: it needs the reader's nested parses
        (the assessment's "The tree-sitter 0.26.0 crash"). Changing either version
        here therefore also needs the reader re-run over the corpus first."""
        self.assertEqual("0.25.2", metadata.version("tree-sitter"))
        self.assertEqual("0.25.1", metadata.version("tree-sitter-bash"))
        self.assertEqual(15, _probe([])["abi"])

    def test_the_pair_is_declared_exactly(self) -> None:
        """An install from the package metadata alone takes the same pair as the
        locks (Codex and CodeAnt on #394; Decision 0108, items 7 and 14)."""
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        declared = project["project"]["dependencies"]
        self.assertIn("tree-sitter==0.25.2", declared)
        self.assertIn("tree-sitter-bash==0.25.1", declared)
        self.assertEqual(
            [],
            [
                line
                for line in declared
                if line.startswith("tree-sitter") and "==" not in line
            ],
        )

    def test_the_grammar_reads_what_the_shell_reader_relies_on(self) -> None:
        cases = {
            # A substitution in an assignment, then the command after it.
            "x=`date` git status": ["date", "git"],
            # Single quotes keep a substitution inert; double quotes do not.
            "echo '$(git status)'": ["echo"],
            'echo "$(git status)"': ["echo", "git"],
            # A quoted newline is part of its word.
            "echo 'abc\ndef`git status`'": ["echo"],
            # A comment's apostrophe opens no quote.
            "echo hi # it's\ngit status": ["echo", "git"],
            # A function body and a process substitution hold commands.
            "f() { git log; }": ["git"],
            "cat < <(git status)": ["cat", "git"],
            # A quoted command word keeps its quotes in the tree, so the shell
            # reader unquotes it (Kody on #394; Decision 0108, item 11).
            '"git" status': ['"git"'],
            "'git' status": ["'git'"],
            'g"i"t status': ['g"i"t'],
            'echo "$("git" status)"': ['"git"', "echo"],
            'f() { "git" status; }; f': ['"git"', "f"],
            'cat < <("git" status)': ['"git"', "cat"],
        }
        facts = _facts(list(cases))
        for (text, names), found in zip(cases.items(), facts, strict=True):
            with self.subTest(text=text):
                self.assertEqual(sorted(names), found["names"])
                self.assertEqual(0, found["errors"])
        [heredoc] = _facts(['bash 2>&1 <<EOF\n"git" status\nEOF\n'])
        self.assertEqual(['"git" status\n'], heredoc["heredocs"])
        # In source order (CodeAnt on #394).
        facts = _facts(["cat <<A\none\nA\ncat <<B\ntwo\nB\n"])
        self.assertEqual(["one\n", "two\n"], facts[0]["heredocs"])

    def test_every_shell_surface_parses_without_an_unexpected_error(self) -> None:
        """Every surface kind of the frozen corpus parses with no error. The
        instruction fences' placeholders are documentation, not shell, so each is
        masked at its own width first (Codex, Kody and CodeAnt on #394)."""
        surfaces = _shell_surfaces()
        self.assertGreater(len(surfaces), 50)
        # Each file of the frozen corpus that is still tracked still yields a
        # surface, so an extraction that drops one fails here (CodeAnt on #396).
        evidence = json.loads(
            (
                ROOT / "knowledge/assessments/0108-shell-parser-evaluation.json"
            ).read_text(encoding="utf-8")
        )
        found = {name.split("#", 1)[0] for name in surfaces}
        for path in sorted({script["path"] for script in evidence["scripts"]}):
            if (ROOT / path).is_file():
                with self.subTest(corpus_file=path):
                    self.assertIn(path, found)
        for kind in (
            ".github/workflows/verification.yml#",
            ".gitlab-ci.yml#",
            "ci/gitlab-ci.yml#",
            "ci/github-actions.yml#",
            "Dockerfile#",
            "AGENTS.md#",
            "ci/verify",
            "knowledge/assessments/365-duplication-inventory-2026-10-05-evidence/"
            "duplicate_code.sh",
        ):
            with self.subTest(kind=kind):
                self.assertTrue(any(name.startswith(kind) for name in surfaces))
        facts = _facts(list(surfaces.values()))
        broken = {
            name for name, found in zip(surfaces, facts, strict=True) if found["errors"]
        }
        # With its placeholders masked, every surface, the instruction fences
        # included, parses with no error at all (Codex and CodeAnt on #394).
        self.assertEqual(set(), broken)
        self.assertTrue(
            any(
                Path(name.split("#")[0]).name in INSTRUCTION_FILES and "_exact-" in text
                for name, text in surfaces.items()
            )
        )


class SurfaceExtractionTests(unittest.TestCase):
    """Each extraction rule, and each case it refuses rather than misreads."""

    def test_a_run_instruction_is_read_as_docker_hands_it_to_the_shell(self) -> None:
        text = (
            "FROM alpine\n"
            "RUN --mount=type=bind,source=a,target=/b \\\n"
            "    set -eux; \\\n"
            "    # a comment Docker drops\n"
            "    echo 'a b'\n"
            'RUN ["python", "-V"]\n'
            "run true\n"
        )
        self.assertEqual(["set -eux;     echo 'a b'", "true"], _dockerfile_runs(text))
        # Exec form is a JSON list of strings; a shell test is not (CodeAnt on #394).
        self.assertEqual(
            ["[ -f marker ] && git status"],
            _dockerfile_runs(
                'FROM alpine\nRUN ["python", "-V"]\nRUN [ -f marker ] && git status\n'
            ),
        )

    def test_an_exec_form_shell_run_hands_its_command_to_the_shell(self) -> None:
        """`RUN ["bash", "-c", "…"]` still asks bash to parse its command; another
        shell in exec form fails closed (cubic on #396)."""
        self.assertEqual(
            ["git status"],
            _dockerfile_runs(
                'RUN ["/bin/bash", "-o", "pipefail", "-c", "git status"]\n'
            ),
        )
        self.assertEqual([], _dockerfile_runs('RUN ["python", "-c", "print()"]\n'))
        with self.assertRaisesRegex(AssertionError, "an exec-form `zsh` RUN"):
            _dockerfile_runs('RUN ["zsh", "-c", "git status"]\n')

    def test_a_run_here_document_or_another_escape_fails_closed(self) -> None:
        with self.assertRaisesRegex(AssertionError, "here-document"):
            _dockerfile_runs("FROM alpine\nRUN <<EOF\ngit status\nEOF\n")
        with self.assertRaisesRegex(AssertionError, "escape directive"):
            _dockerfile_runs("# escape=`\nRUN true\n")
        # The default escape may be stated (CodeAnt on #396).
        self.assertEqual(
            ["true"], _dockerfile_runs("# escape=\\\nFROM alpine\nRUN true\n")
        )

    def test_a_dockerfile_shell_override_is_honoured_or_fails_closed(self) -> None:
        """A `SHELL` instruction to bash or sh keeps the `RUN` lines shell; to
        another program it fails closed (CodeAnt on #394)."""
        self.assertEqual(
            ["git status"],
            _dockerfile_runs(
                'SHELL ["/bin/bash", "-o", "pipefail", "-c"]\nRUN git status\n'
            ),
        )
        with self.assertRaisesRegex(AssertionError, "a `pwsh` SHELL"):
            _dockerfile_runs('SHELL ["pwsh", "-Command"]\nRUN Write-Output hi\n')

    def test_a_workflow_step_is_read_with_its_expressions_masked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "w.yml"
            path.write_bytes(
                BOM + b"jobs:\n  j:\n    defaults:\n      run:\n        shell: bash\n"
                b"    steps:\n      - run: echo ${{ github.sha }}\n"
                b"      - run: git status\n        shell: sh\n"
            )
            self.assertEqual(
                sorted(["echo " + "_" * 17, "git status"]),
                sorted(_workflow_runs(path)),
            )

    def test_a_multi_line_expression_keeps_its_line_breaks(self) -> None:
        """Masking keeps each newline, so the shell's lines stay where they were
        (CodeAnt on #394)."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "w.yml"
            path.write_text(
                "on: push\njobs:\n  j:\n    runs-on: ubuntu-latest\n    steps:\n"
                "      - run: |\n          echo ${{ fromJSON(\n            x) }}\n"
                "          git status\n",
                "utf-8",
            )
            runs = _workflow_runs(path)
            self.assertEqual(
                ["echo " + "_" * 13 + "\n" + "_" * 7 + "\ngit status\n"], runs
            )
            self.assertEqual(3, runs[0].count("\n"))

    def test_a_step_in_another_language_or_broken_yaml_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "w.yml"
            path.write_text(
                "on: push\njobs:\n  j:\n    runs-on: ubuntu-latest\n    steps:\n"
                "      - run: print(1)\n        shell: python\n",
                "utf-8",
            )
            with self.assertRaisesRegex(AssertionError, "`python` step"):
                _workflow_runs(path)
            path.write_text("steps: [\n", "utf-8")
            with self.assertRaisesRegex(AssertionError, "w.yml: not YAML"):
                _workflow_runs(path)

    def test_every_surface_kind_is_found_and_a_make_recipe_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".github" / "workflows").mkdir(parents=True)
            (root / ".github" / "workflows" / "w.yml").write_text(
                "on: push\njobs:\n  j:\n    runs-on: ubuntu-latest\n    steps:\n"
                "      - run: git status\n",
                "utf-8",
            )
            (root / "AGENTS.md").write_text(
                "x\n```bash\ngit log <ref>\n```\n```python\nprint()\n```\n", "utf-8"
            )
            # An instruction file is found by its name, at any depth (Codex on #394).
            (root / "sub").mkdir()
            (root / "sub" / "AGENTS.md").write_text(
                "```sh\ngit fetch <remote>\n```\n", "utf-8"
            )
            (root / "Dockerfile").write_text("FROM alpine\nRUN git fetch\n", "utf-8")
            (root / "deep" / "er").mkdir(parents=True)
            (root / "deep" / "er" / "tool").write_bytes(BOM + b"#!/bin/sh\ngit gc\n")
            (root / "deep" / "data.bin").write_bytes(b"\xff\xfe")
            # A hidden source directory is read; an untracked file is not (Codex on
            # #394).
            (root / ".husky").mkdir()
            (root / ".husky" / "pre-commit").write_text(
                "#!/bin/sh\ngit diff\n", "utf-8"
            )
            (root / "scratch").write_text("#!/bin/sh\nuntracked\n", "utf-8")
            self.assertEqual(
                {
                    ".github/workflows/w.yml#0": "git status",
                    "AGENTS.md#0": "git log _ref_\n",
                    "sub/AGENTS.md#0": "git fetch _remote_\n",
                    "Dockerfile#0": "git fetch",
                    "deep/er/tool": "#!/bin/sh\ngit gc\n",
                    ".husky/pre-commit": "#!/bin/sh\ngit diff\n",
                },
                _shell_surfaces(_declared(root, unlisted=("scratch",))),
            )
            (root / "deep" / "er" / "tool").write_bytes(b"#!/bin/sh\n\xff\n")
            declared = _declared(root, unlisted=("scratch",))
            with self.assertRaises(UnicodeDecodeError):
                _shell_surfaces(declared)
            (root / "deep" / "er" / "tool").unlink()
            (root / "Makefile").write_text("all:\n\tgit status\n", "utf-8")
            declared = _declared(root, unlisted=("scratch",))
            with self.assertRaisesRegex(AssertionError, "Makefile: a Make recipe"):
                _shell_surfaces(declared)

    def test_a_probe_answer_that_is_not_json_is_reported(self) -> None:
        answer = SimpleNamespace(returncode=0, stdout="warn", stderr="")
        with (
            patch("subprocess.run", return_value=answer),
            self.assertRaisesRegex(AssertionError, "answered no JSON.*'warn'"),
        ):
            _probe([])

    def test_a_probe_answer_of_another_shape_is_reported(self) -> None:
        """Amazon Q on #394: a missing key is named, not a bare KeyError."""
        for stdout in ('{"facts": []}', "[]", '{"abi": 15, "facts": [], "x": 1}'):
            answer = SimpleNamespace(returncode=0, stdout=stdout, stderr="")
            with (
                self.subTest(stdout=stdout),
                patch("subprocess.run", return_value=answer),
                self.assertRaisesRegex(AssertionError, "answered another shape"),
            ):
                _probe([])

    def test_a_default_shell_in_another_language_fails_closed(self) -> None:
        """A step inherits the job's or the workflow's `defaults.run.shell`
        (Claude on #394)."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "w.yml"
            for document in (
                "defaults:\n  run:\n    shell: pwsh\njobs:\n  j:\n    steps:\n"
                "      - run: Get-Content x\n",
                "jobs:\n  j:\n    defaults:\n      run:\n        shell: python\n"
                "    steps:\n      - run: print(1)\n",
            ):
                path.write_text(document, "utf-8")
                with (
                    self.subTest(document=document),
                    self.assertRaisesRegex(AssertionError, "a `(pwsh|python)` default"),
                ):
                    _workflow_runs(path)

    def test_a_dockerfile_variant_fails_closed(self) -> None:
        """Only `Dockerfile` itself is read; another container file fails closed
        rather than going unread (Claude on #394)."""
        for name in ("Dockerfile.ci", "build.Dockerfile", "Containerfile"):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / name).write_text("FROM a\nRUN true\n", "utf-8")
                declared = _declared(root)
                with (
                    self.subTest(name=name),
                    self.assertRaisesRegex(AssertionError, "a container file"),
                ):
                    _shell_surfaces(declared)


class InterpreterAndCiShapeTests(unittest.TestCase):
    """Shell surfaces are found by what they are, not where they sit (CodeAnt and
    Claude on #394)."""

    def test_ci_definitions_are_read_by_their_shape_anywhere(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "ci").mkdir()
            (root / ".gitlab-ci.yml").write_text(
                "stages: [test]\ndefault:\n  image: alpine\n  before_script:\n    - git fetch\n"
                "job:\n  stage: test\n  script:\n    - git status\n    - echo ok\n"
                "  after_script: git gc\n",
                "utf-8",
            )
            (root / "ci" / "github-actions.yml").write_text(
                "on: push\njobs:\n  j:\n    runs-on: ubuntu-latest\n"
                "    steps:\n      - run: git log\n",
                "utf-8",
            )
            (root / "ci" / "policy.yml").write_text("checks:\n  - name: x\n", "utf-8")
            (root / "ci" / "flow.yml").write_text(
                'stages: [t]\nimage: alpine\njob: {stage: t, script: "git describe"}\n',
                "utf-8",
            )
            self.assertEqual(
                {
                    ".gitlab-ci.yml#0": "git fetch",
                    ".gitlab-ci.yml#1": "git status\necho ok",
                    ".gitlab-ci.yml#2": "git gc",
                    "ci/flow.yml#0": "git describe",
                    "ci/github-actions.yml#0": "git log",
                },
                _shell_surfaces(_declared(root)),
            )
            (root / "ci" / "other.yml").write_text(
                "pipeline:\n  steps:\n    - script: git status\n", "utf-8"
            )
            declared = _declared(root)
            with self.assertRaisesRegex(
                AssertionError, "other.yml: shell in an unknown"
            ):
                _shell_surfaces(declared)

    def test_a_checkout_s_tracked_files_are_the_universe(self) -> None:
        """In a Git checkout the tracked files are read, wherever they sit, and an
        untracked one is not; the runtime image's source manifest stands in for Git
        where there is none."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".husky").mkdir()
            (root / ".husky" / "hook").write_text("#!/bin/sh\ngit a\n", "utf-8")
            (root / "scratch").write_text("#!/bin/sh\ngit b\n", "utf-8")
            git = ["git", "-c", "init.defaultBranch=main", "-C", str(root)]
            for argv in (["init", "-q"], ["add", ".husky/hook"]):
                subprocess.run([*git, *argv], check=True, timeout=60)  # nosec B603 B607  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
            self.assertEqual({".husky/hook"}, set(_shell_surfaces(root)))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "listed").write_text("#!/bin/sh\ngit c\n", "utf-8")
            (root / "unlisted").write_text("#!/bin/sh\ngit d\n", "utf-8")
            (root / ".gnostoa-source-files").write_bytes(b"listed\0")
            self.assertEqual({"listed"}, set(_shell_surfaces(root)))

    def test_nested_gitlab_script_lists_are_flattened_and_others_fail(self) -> None:
        """GitLab flattens nested `script` arrays (anchors and aliases build them)
        at any depth; a value that is not a string fails closed rather than being
        stringified (CodeAnt on #396). A `!reference` tag fails closed at the YAML
        load: none is tracked (cubic on #396)."""
        nested: dict[str, object] = {
            "image": "alpine",
            "job": {"script": ["git a", ["git b", ["git c"]]]},
        }
        self.assertEqual(["git a\ngit b\ngit c"], _gitlab_scripts(nested, "x"))
        with self.assertRaisesRegex(AssertionError, "a `int` script line"):
            _gitlab_scripts({"image": "alpine", "job": {"script": ["git a", 7]}}, "x")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".gitlab-ci.yml"
            path.write_text(
                ".base:\n  script: [git a]\njob:\n  script: [!reference [.base, script]]\n",
                "utf-8",
            )
            with self.assertRaisesRegex(AssertionError, "not YAML.*!reference"):
                _ci_shell(path, under_github=False)

    def test_ci_scripts_are_found_in_every_valid_form_and_source_order(self) -> None:
        """Top-level GitLab lifecycle scripts (Codex on #396), quoted keys, and
        steps numbered in source order (CodeAnt on #396)."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "ci").mkdir()
            (root / ".gitlab-ci.yml").write_text(
                "image: alpine\nbefore_script: [git a]\nafter_script: git z\n"
                "job:\n  script: [git b]\n",
                "utf-8",
            )
            (root / "ci" / "quoted.yml").write_text(
                '{"stages": ["t"], "image": "alpine", "job": {"stage": "t", "script": "git c"}}\n',
                "utf-8",
            )
            (root / "ci" / "order.yml").write_text(
                "on: push\njobs:\n  one:\n    runs-on: ubuntu-latest\n"
                "    steps:\n      - run: git first\n      - run: git second\n"
                "  two:\n    runs-on: ubuntu-latest\n"
                "    steps:\n      - run: git third\n",
                "utf-8",
            )
            declared = _declared(root)
            self.assertEqual(
                {
                    ".gitlab-ci.yml#0": "git a",
                    ".gitlab-ci.yml#1": "git z",
                    ".gitlab-ci.yml#2": "git b",
                    "ci/quoted.yml#0": "git c",
                    "ci/order.yml#0": "git first",
                    "ci/order.yml#1": "git second",
                    "ci/order.yml#2": "git third",
                },
                _shell_surfaces(declared),
            )

    def test_every_commonmark_shell_fence_form_is_read(self) -> None:
        """Up to three spaces of indent, removed from the content; three or more
        backticks or tildes, with spaces or an info string after the language; a fence
        left open to the end; a closer inside another fence is its content (CodeAnt,
        Codex, cubic and Claude on #396)."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "AGENTS.md").write_text(
                "  ```bash\n  git d\n   git d2\n  ```\n\n"
                "````sh\ngit e\n````\n\n"
                "~~~Shell title=setup\ngit f\n~~~\n\n"
                "``` bash\ngit g\n```\n\n"
                "```text\n```bash\nnot shell\n```\n\n"
                "~~~bash\ngit h\n",
                "utf-8",
            )
            declared = _declared(root)
            self.assertEqual(
                ["git d\n git d2\n", "git e\n", "git f\n", "git g\n", "git h\n"],
                list(_shell_surfaces(declared).values()),
            )

    def test_a_line_of_list_markers_is_read_in_linear_time(self) -> None:
        """A container's prefix is read without backtracking: repeated list markers
        and tabs once took exponential time (CodeQL and Codacy on #396). The reader
        runs in a subprocess, so the old shape fails by its deadline instead of
        hanging the suite."""
        hostile = "*\t\t\t" * 40 + "x\n"
        # This interpreter, with a literal argv.
        completed = subprocess.run(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
            [
                sys.executable,
                "-c",
                "import sys; from tests.test_shell_parser_dependency import "
                "_shell_fences; print(_shell_fences(sys.argv[1], 'AGENTS.md'))",
                hostile,
            ],
            cwd=ROOT,
            env={"PYTHONPATH": str(ROOT), "PATH": "/usr/bin:/bin"},
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        self.assertEqual("[]\n", completed.stdout)

    def test_a_shell_fence_inside_a_list_or_quote_fails_closed(self) -> None:
        """This reader reads top-level fences; one in a list item or a block quote
        fails closed instead of being skipped (Codex, cubic and Claude on #396)."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for text in (
                "> ```bash\n> git a\n> ```\n",
                "1. Step:\n\n    ```bash\n    git a\n    ```\n",
                "- ```sh\n  git a\n  ```\n",
            ):
                (root / "AGENTS.md").write_text(text, "utf-8")
                declared = _declared(root)
                with (
                    self.subTest(text=text),
                    self.assertRaisesRegex(
                        AssertionError, "a shell fence inside a list or quote"
                    ),
                ):
                    _shell_surfaces(declared)

    def test_a_fence_closes_only_on_its_own_character(self) -> None:
        """A closing fence repeats the opening character alone, so a line such as
        ```~~~ inside a backtick block does not end it (cubic and Claude on #396)."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "AGENTS.md").write_text(
                "```bash\ngit a\n```~~~\ngit b\n````\n", "utf-8"
            )
            declared = _declared(root)
            self.assertEqual(
                {"AGENTS.md#0": "git a\n```~~~\ngit b\n"}, _shell_surfaces(declared)
            )

    def test_a_run_s_implicit_shell_is_its_runner_s(self) -> None:
        """A `run` without `shell` takes its job's or workflow's default, else its
        runner's: bash on Linux and macOS, PowerShell on Windows, unknown for an
        expression or a group. Only an established bash or sh is read (Codex on
        #396)."""
        windows = "on: push\njobs:\n  a:\n    runs-on: windows-latest\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workflow.yml"
            for document in (
                windows + "    steps:\n      - run: Write-Output hi\n",
                "on: push\njobs:\n  a:\n    runs-on: ${{ matrix.os }}\n"
                "    steps:\n      - run: git x\n",
                "on: push\njobs:\n  a:\n    runs-on: {group: g}\n"
                "    steps:\n      - run: git x\n",
                "runs:\n  using: composite\n  steps:\n    - run: git x\n",
            ):
                path.write_text(document, "utf-8")
                with (
                    self.subTest(document=document),
                    self.assertRaisesRegex(AssertionError, "decided by its runner"),
                ):
                    _ci_shell(path, under_github=True)
            for document, expected in (
                (
                    "on: push\njobs:\n  a:\n    runs-on: macos-15\n"
                    "    steps:\n      - run: git a\n",
                    ["git a"],
                ),
                (
                    "on: push\njobs:\n  a:\n    runs-on: [self-hosted, Linux]\n"
                    "    steps:\n      - run: git b\n",
                    ["git b"],
                ),
                (
                    windows + "    steps:\n      - run: git c\n        shell: bash\n",
                    ["git c"],
                ),
                (
                    windows + "    defaults:\n      run:\n        shell: bash\n"
                    "    steps:\n      - run: git d\n",
                    ["git d"],
                ),
                (
                    "defaults:\n  run:\n    shell: sh\n"
                    + windows
                    + "    steps:\n      - run: git e\n",
                    ["git e"],
                ),
                (
                    "runs:\n  using: composite\n  steps:\n"
                    "    - run: git f\n      shell: bash\n",
                    ["git f"],
                ),
            ):
                path.write_text(document, "utf-8")
                with self.subTest(document=document):
                    self.assertEqual(expected, _ci_shell(path, under_github=True))

    def test_an_exec_form_shell_s_options_are_read_as_the_shell_reads_them(
        self,
    ) -> None:
        """With `-c` among the options, the command is the first word after them;
        `-o` and `-O` take a word, and so do `--rcfile` and `--init-file`. After a
        script's path, `-c` is the script's (CodeAnt on #396). A script operand is
        a file in the image, which this reader cannot map back to the repository, so
        it fails closed (Codex on #396); `-` reads standard input instead."""
        for argv, expected in (
            (["bash", "-c", "-e", "git b"], ["git b"]),
            (["bash", "-eo", "pipefail", "-c", "git c"], ["git c"]),
            (["bash", "--rcfile", "f", "-c", "git d"], ["git d"]),
            (["sh", "-c", "--", "git e", "zero"], ["git e"]),
            (["bash", "+e", "-xc", "git f"], ["git f"]),
            (["bash", "-"], []),
        ):
            with self.subTest(argv=argv):
                self.assertEqual(expected, _exec_form_shell(argv))
        for argv, reason in (
            (["bash", "--unknown", "-c", "x"], "an unknown shell option `--unknown`"),
            (["bash", "-c"], "a `-c` without its command"),
            (
                ["bash", "script.sh", "-c", "git a"],
                "an exec-form shell running a script",
            ),
            (["sh", "scripts/check.sh"], "an exec-form shell running a script"),
            (["bash", "-o"], "a shell option without its word"),
            (["bash", "+c", "x"], "an unknown shell option `\\+c`"),
        ):
            with (
                self.subTest(argv=argv),
                self.assertRaisesRegex(AssertionError, reason),
            ):
                _exec_form_shell(argv)

    def test_only_a_here_document_word_starts_a_here_document(self) -> None:
        """BuildKit reads a here-document from a word, quotes kept, that is an
        optional descriptor, `<<`, an optional `-` and a name holding no `<`.
        `<<` inside quotes, `cat<<EOF` and a `<<<` here-string are shell; measured
        against BuildKit (CodeAnt and cubic on #396)."""
        for line in (
            'RUN echo "a << b"',
            'RUN echo "<<EOF"',
            "RUN cat<<EOF",
            'RUN cat <<<"here"',
        ):
            with self.subTest(line=line):
                self.assertEqual([line[4:]], _dockerfile_runs(f"FROM alpine\n{line}\n"))
        for line in ("RUN cat <<EOF\n", "RUN cat << EOF\n", "RUN cat 3<<-EOF\n"):
            with (
                self.subTest(line=line),
                self.assertRaisesRegex(AssertionError, "here-document"),
            ):
                _dockerfile_runs("FROM alpine\n" + line)
        with self.assertRaisesRegex(AssertionError, "an unreadable RUN"):
            _dockerfile_runs('FROM alpine\nRUN echo "unclosed\n')

    def test_a_run_that_is_not_a_string_fails_closed(self) -> None:
        """A step's `run` is a string; any other value fails closed instead of being
        skipped. A `defaults.run` mapping of `shell` and `working-directory` is not a
        step (Claude on #396)."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workflow.yml"
            job = "on: push\njobs:\n  a:\n    runs-on: ubuntu-latest\n"
            for document in (
                job + "    steps:\n      - run:\n          - git status\n",
                job + "    steps:\n      - run: {git: status}\n",
                job + "    steps:\n      - run: 1\n",
            ):
                path.write_text(document, "utf-8")
                with (
                    self.subTest(document=document),
                    self.assertRaisesRegex(
                        AssertionError, "a `run` that is not a string"
                    ),
                ):
                    _ci_shell(path, under_github=True)
            path.write_text(
                job + "    defaults:\n      run:\n        shell: bash\n"
                "        working-directory: x\n    steps:\n      - run: git log\n",
                "utf-8",
            )
            self.assertEqual(["git log"], _ci_shell(path, under_github=True))

    def test_a_multi_call_binary_runs_its_applet(self) -> None:
        """`busybox sh` and `toybox sh` run a shell: in a shebang and in an exec-form
        `RUN` (CodeAnt on #396). Busybox's `hush` is another shell, which fails
        closed."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, content in (
                ("q", b"#!/bin/busybox sh\ngit q\n"),
                ("r", b"#!/usr/bin/env busybox ash\ngit r\n"),
                ("s", b"#!/usr/bin/toybox sh\ngit s\n"),
            ):
                (root / name).write_bytes(content)
            self.assertEqual({"q", "r", "s"}, set(_shell_surfaces(_declared(root))))
            for content, reason in (
                (b"#!/bin/busybox\ngit u\n", "u: an unreadable shebang"),
                (b"#!/bin/busybox hush\ngit u\n", "u: a `hush` script"),
            ):
                (root / "u").write_bytes(content)
                declared = _declared(root)
                with (
                    self.subTest(shebang=content),
                    self.assertRaisesRegex(AssertionError, reason),
                ):
                    _shell_surfaces(declared)
        self.assertEqual(
            ["git t"], _exec_form_shell(["/bin/busybox", "sh", "-c", "git t"])
        )
        with self.assertRaisesRegex(AssertionError, "an exec-form `hush` RUN"):
            _exec_form_shell(["busybox", "hush", "-c", "git t"])

    def test_only_a_step_s_run_is_shell(self) -> None:
        """GitHub runs shell at `jobs.<id>.steps[*].run` and a composite action's
        `runs.steps[*].run` only; a `run` key elsewhere, such as a variable in
        `env`, a matrix value or an action's input, is data (Codex on #396). Any
        other shape on those paths fails closed."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workflow.yml"
            path.write_text(
                "on: push\nenv:\n  run: one\njobs:\n  a:\n"
                "    runs-on: ubuntu-latest\n    env:\n      run: two\n"
                "    strategy:\n      matrix:\n        include:\n          - run: three\n"
                "    steps:\n      - run: git a\n        env:\n          run: four\n"
                "      - uses: some/action@v1\n        with:\n          run: five\n",
                "utf-8",
            )
            self.assertEqual(["git a"], _ci_shell(path, under_github=True))
            for document, reason in (
                ("on: push\njobs: [a]\n", "jobs that are not a mapping"),
                ("on: push\njobs:\n  a: x\n", "a job that is not a mapping"),
                (
                    "on: push\njobs:\n  a:\n    runs-on: ubuntu-latest\n    steps: x\n",
                    "steps that are not a list",
                ),
                (
                    "on: push\njobs:\n  a:\n    runs-on: ubuntu-latest\n"
                    "    steps:\n      - x\n",
                    "a step that is not a mapping",
                ),
                (
                    "runs:\n  using: composite\n  steps: x\n",
                    "steps that are not a list",
                ),
                ("other:\n  run: git x\n", "shell in an unknown GitHub shape"),
            ):
                path.write_text(document, "utf-8")
                with (
                    self.subTest(document=document),
                    self.assertRaisesRegex(AssertionError, reason),
                ):
                    _ci_shell(path, under_github=True)
            path.write_text("version: 2\nupdates: []\n", "utf-8")
            self.assertEqual([], _ci_shell(path, under_github=True))

    def test_an_expression_ends_outside_its_strings(self) -> None:
        """An Actions expression ends at the first `}}` outside its string
        literals, which quote with `'` and escape it by doubling; an unclosed one
        fails closed (Codex on #396)."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workflow.yml"
            job = "on: push\njobs:\n  a:\n    runs-on: ubuntu-latest\n    steps:\n"
            for expression in (
                "${{ format('{{Hello {0}!}}', github.actor) }}",
                "${{ 'it''s }}' }}",
            ):
                path.write_text(
                    job + "      - run: >-\n          echo " + expression + " done\n",
                    "utf-8",
                )
                with self.subTest(expression=expression):
                    self.assertEqual(
                        ["echo " + "_" * len(expression) + " done"],
                        _ci_shell(path, under_github=True),
                    )
            path.write_text(job + "      - run: echo ${{ x\n", "utf-8")
            with self.assertRaisesRegex(AssertionError, "an unclosed expression"):
                _ci_shell(path, under_github=True)

    def test_a_shell_key_is_found_however_it_is_written(self) -> None:
        """Whether a YAML file holds a shell key is read from its loaded structure,
        so YAML's explicit-key form counts like any other (Codex on #396)."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "explicit.yml"
            for document in (
                "image: alpine\njob:\n  ? script\n  : git status\n",
                "image: alpine\njob:\n  ? script  # the job's commands\n  : git status\n",
            ):
                path.write_text(document, "utf-8")
                with self.subTest(document=document):
                    self.assertEqual(
                        ["git status"], _ci_shell(path, under_github=False)
                    )
            path.write_text("other:\n  ? run\n  : git x\n", "utf-8")
            with self.assertRaisesRegex(AssertionError, "unknown GitHub shape"):
                _ci_shell(path, under_github=True)
            # Text that merely mentions a key is not one; a tag the safe loader
            # refuses, as in mkdocs.yml, does not hide a file's keys.
            for document in (
                "note: 'run: and script: are words here'\n",
                "markdown: !!python/name:pymdownx.superfences.fence_code_format\n",
            ):
                path.write_text(document, "utf-8")
                with self.subTest(document=document):
                    self.assertEqual([], _ci_shell(path, under_github=False))
            # A tagged CI file is not read as plain data; it fails closed.
            path.write_text("job:\n  script: !reference [.setup, script]\n", "utf-8")
            with self.assertRaisesRegex(AssertionError, "not YAML"):
                _ci_shell(path, under_github=False)

    def test_an_onbuild_run_is_read(self) -> None:
        """`ONBUILD RUN` runs its command in a later build, so it is read as a `RUN`
        (CodeAnt on #396)."""
        self.assertEqual(
            ["git status", "git log"],
            _dockerfile_runs(
                'FROM alpine\nONBUILD RUN git status\nonbuild run ["sh", "-c", "git log"]\n'
            ),
        )

    def test_a_gitlab_hook_s_commands_are_read(self) -> None:
        """`hooks:pre_get_sources_script` runs on the runner before the clone, in
        a job or in `default`; another hook fails closed (Codex on #396)."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".gitlab-ci.yml"
            path.write_text(
                "default:\n  image: alpine\n  hooks:\n    pre_get_sources_script: [git a]\n"
                "job:\n  hooks:\n    pre_get_sources_script: git b\n  script: [git c]\n",
                "utf-8",
            )
            self.assertEqual(
                ["git a", "git b", "git c"], _ci_shell(path, under_github=False)
            )
            path.write_text(
                "job:\n  image: alpine\n  hooks:\n    other: git x\n  script: [git c]\n",
                "utf-8",
            )
            with self.assertRaisesRegex(
                AssertionError, "an unknown GitLab hook `other`"
            ):
                _ci_shell(path, under_github=False)

    def test_only_a_known_runner_label_implies_bash(self) -> None:
        """A documented GitHub-hosted Linux or macOS label, or a self-hosted
        runner's OS label, implies bash; a custom label such as `ubuntu-builder`
        may name any runner, and fails closed (Codex on #396)."""
        for runs_on in (
            "ubuntu-latest",
            "ubuntu-24.04-arm",
            "macos-15-xlarge",
            ["self-hosted", "Linux"],
        ):
            with self.subTest(runs_on=runs_on):
                self.assertEqual("bash", _runner_shell(runs_on))
        for runs_on in ("ubuntu-builder", "macos-anything", ["self-hosted", "build"]):
            with self.subTest(runs_on=runs_on):
                self.assertIsNone(_runner_shell(runs_on))

    def test_a_gitlab_job_s_shell_is_its_image_s(self) -> None:
        """GitLab's runner, not the file, picks the shell, except in a container: a
        Linux image runs `sh` or `bash` (GitLab Runner's Docker executor). A job's
        image is its own, else its `extends` base's, else `default`'s, else the
        global one. A job without one, or with a Windows base image, fails closed
        (Codex on #396)."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".gitlab-ci.yml"
            for document in (
                "job:\n  image: alpine\n  script: [git a]\n",
                ".base:\n  image: alpine\njob:\n  extends: .base\n  script: [git a]\n",
                # A base reached twice, through both bases, before the image.
                ".root:\n  stage: x\n.img:\n  image: alpine\n"
                ".a:\n  extends: [.img, .root]\n.b:\n  extends: .root\n"
                "job:\n  extends: [.a, .b]\n  script: [git a]\n",
                "default:\n  image: {name: alpine}\njob:\n  script: [git a]\n",
                "image: alpine\njob:\n  script: [git a]\n",
                "job:\n  image: alpine\n  script: [git a]\nbridge:\n  trigger: other\n",
            ):
                path.write_text(document, "utf-8")
                with self.subTest(document=document):
                    self.assertEqual(["git a"], _ci_shell(path, under_github=False))
            for document, reason in (
                (
                    "job:\n  script: [git a]\n",
                    "`job`: a GitLab job whose shell its runner decides",
                ),
                (
                    "job:\n  image: mcr.microsoft.com/windows/servercore:ltsc2022\n"
                    "  script: [git a]\n",
                    "`job`: a Windows image",
                ),
                (
                    "job:\n  extends: .missing\n  script: [git a]\n",
                    "`job`: an `extends` of `.missing`",
                ),
            ):
                path.write_text(document, "utf-8")
                with (
                    self.subTest(document=document),
                    self.assertRaisesRegex(AssertionError, reason),
                ):
                    _ci_shell(path, under_github=False)

    def test_a_hidden_job_runs_in_the_jobs_that_extend_it(self) -> None:
        """A hidden job's scripts run in each job that extends it, whose image is
        checked; one that no job extends is checked by its own image (Claude on
        #396). A malformed `extends` entry fails closed."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".gitlab-ci.yml"
            path.write_text(
                ".lint:\n  script: [git a]\njob:\n  extends: .lint\n  image: alpine\n",
                "utf-8",
            )
            self.assertEqual(["git a"], _ci_shell(path, under_github=False))
            for document, reason in (
                (
                    ".t:\n  image: mcr.microsoft.com/windows/nanoserver:ltsc2022\n"
                    "  script: [git a]\n",
                    "`.t`: a Windows image",
                ),
                (
                    ".t:\n  script: [git a]\n",
                    "`.t`: a GitLab job whose shell its runner decides",
                ),
                (
                    "job:\n  image: alpine\n  extends: [[.x]]\n  script: [git a]\n",
                    "`job`: an `extends` of",
                ),
            ):
                path.write_text(document, "utf-8")
                with (
                    self.subTest(document=document),
                    self.assertRaisesRegex(AssertionError, reason),
                ):
                    _ci_shell(path, under_github=False)

    def test_gitlab_global_keywords_are_not_jobs(self) -> None:
        """A global keyword, such as `variables`, holds data, not a job, even when
        one of its keys is named `script`; a job with hooks alone is GitLab's too
        (Codex and Claude on #396)."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".gitlab-ci.yml"
            path.write_text(
                "variables:\n  script: 'not shell ('\nworkflow:\n  rules: []\n"
                "job:\n  image: alpine\n  script: [git a]\n",
                "utf-8",
            )
            self.assertEqual(["git a"], _ci_shell(path, under_github=False))
            path.write_text(
                "fetch:\n  image: alpine\n  hooks:\n"
                "    pre_get_sources_script: [git submodule sync]\n",
                "utf-8",
            )
            self.assertEqual(
                ["git submodule sync"], _ci_shell(path, under_github=False)
            )

    def test_a_fence_in_another_shell_fails_closed(self) -> None:
        """A fence tagged with a shell this parser does not read, such as `zsh`,
        fails closed instead of being skipped (CodeAnt on #396)."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for tag in ("zsh", "ksh", "pwsh", "powershell"):
                (root / "AGENTS.md").write_text(f"```{tag}\ngit a\n```\n", "utf-8")
                declared = _declared(root)
                with (
                    self.subTest(tag=tag),
                    self.assertRaisesRegex(AssertionError, f"a `{tag}` fence"),
                ):
                    _shell_surfaces(declared)

    def test_gitlab_run_steps_inheritance_and_variable_images(self) -> None:
        """A job's `run` steps hold scripts; a step component fails closed (Codex
        and cubic on #396). `inherit: {default: false}`, or a list without `image`,
        drops `default`'s image (Codex on #396). An image a variable names is known
        only for a variable this repository declares (cubic on #396)."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".gitlab-ci.yml"
            for document, expected in (
                (
                    "job:\n  image: alpine\n  run:\n    - name: a\n      script: git a\n",
                    ["git a"],
                ),
                (
                    "default:\n  image: alpine\njob:\n  inherit: {default: [image]}\n"
                    "  script: [git a]\n",
                    ["git a"],
                ),
                (
                    'job:\n  image: {name: "${KNOWLEDGE_KIT_IMAGE}"}\n  script: [git a]\n',
                    ["git a"],
                ),
            ):
                path.write_text(document, "utf-8")
                with self.subTest(document=document):
                    self.assertEqual(expected, _ci_shell(path, under_github=False))
            for document, reason in (
                (
                    "job:\n  image: alpine\n  run:\n    - name: a\n      step: some/step@v1\n",
                    "`job`: a GitLab `run` step that is not a script",
                ),
                (
                    "default:\n  image: alpine\njob:\n  inherit: {default: false}\n"
                    "  script: [git a]\n",
                    "`job`: a GitLab job whose shell its runner decides",
                ),
                (
                    "default:\n  image: alpine\njob:\n  inherit: {default: [cache]}\n"
                    "  script: [git a]\n",
                    "`job`: a GitLab job whose shell its runner decides",
                ),
                (
                    "job:\n  image: $CI_IMAGE\n  script: [git a]\n",
                    "`job`: an image `CI_IMAGE` decides",
                ),
                # An `inherit` from a base is the job's too (Codex on #396).
                (
                    ".base:\n  inherit: {default: false}\ndefault:\n  image: alpine\n"
                    "job:\n  extends: .base\n  script: [git a]\n",
                    "`job`: a GitLab job whose shell its runner decides",
                ),
                # A declared variable counts only as the whole reference (CodeAnt on
                # #396).
                (
                    'job:\n  image: "registry.example/${KNOWLEDGE_KIT_IMAGE}"\n'
                    "  script: [git a]\n",
                    "`job`: an image a declared variable only partly names",
                ),
            ):
                path.write_text(document, "utf-8")
                with (
                    self.subTest(document=document),
                    self.assertRaisesRegex(AssertionError, reason),
                ):
                    _ci_shell(path, under_github=False)

    def test_only_an_image_known_to_be_linux_runs_sh(self) -> None:
        """A name cannot show an image's OS, so only images known to be Linux
        count: an official image published for Linux alone, or `python` with a
        Linux variant's tag. A custom name or a bare digest may be Windows, and
        leaves the shell unknown (cubic on #396)."""
        for image in (
            "alpine",
            "alpine:3.20",
            "docker.io/library/debian:trixie",
            "python:3.12-slim@sha256:" + "0" * 64,
            "python:3.12-alpine3.20",
        ):
            with self.subTest(image=image):
                self.assertTrue(_linux_image(image))
        for image in (
            "registry.example/custom-base",
            "python@sha256:" + "0" * 64,
            "python:3.12",
            "python:3.12-windowsservercore",
            "mcr.microsoft.com/windows/servercore:ltsc2022",
        ):
            with self.subTest(image=image):
                self.assertFalse(_linux_image(image))
        for text in (
            "FROM registry.example/custom-base\nRUN Write-Output hi\n",
            # A platform other than Linux leaves the shell unknown (Codex on #396).
            "FROM --platform=windows/amd64 alpine\nRUN Write-Output hi\n",
            "FROM --platform=$BUILDPLATFORM python:3.12-slim\nRUN true\n",
        ):
            with (
                self.subTest(text=text),
                self.assertRaisesRegex(AssertionError, "a RUN whose shell is unknown"),
            ):
                _dockerfile_runs(text)
        self.assertEqual(
            ["true"], _dockerfile_runs("FROM --platform=linux/arm64 alpine\nRUN true\n")
        )

    def test_a_shell_instruction_hands_run_to_c_and_defers_under_onbuild(
        self,
    ) -> None:
        """Docker appends a shell-form `RUN` to the whole `SHELL` vector, so the
        vector must end its options with `-c` and hold no command of its own (Codex
        on #396). `ONBUILD SHELL` defers to a later build: it changes no current
        stage, only the `ONBUILD RUN`s after it (Codex on #396)."""
        windows = "FROM mcr.microsoft.com/windows/servercore:ltsc2022\n"
        for text in (
            'FROM alpine\nSHELL ["bash", "-c", "git status"]\nRUN true\n',
            'FROM alpine\nSHELL ["bash"]\nRUN true\n',
            windows + 'ONBUILD SHELL ["bash", "-c"]\nRUN Write-Output hi\n',
        ):
            with self.subTest(text=text), self.assertRaises(AssertionError):
                _dockerfile_runs(text)
        self.assertEqual(
            ["git x"],
            _dockerfile_runs(
                windows + 'ONBUILD SHELL ["bash", "-c"]\nONBUILD RUN git x\n'
            ),
        )
        self.assertEqual(
            ["git y"],
            _dockerfile_runs(
                'FROM alpine\nSHELL ["/bin/bash", "-eo", "pipefail", "-c"]\nRUN git y\n'
            ),
        )

    def test_an_exec_form_env_and_the_runtime_instructions_are_read(self) -> None:
        """An exec-form `env` launches its command, so a shell after it is read;
        `-S` there fails closed (Codex on #396). A shell-form `CMD`, `ENTRYPOINT`
        or `HEALTHCHECK CMD` runs through the stage's shell, as `RUN` does (Codex on
        #396)."""
        self.assertEqual(["git a"], _exec_form_shell(["env", "sh", "-c", "git a"]))
        self.assertEqual(
            ["git b"],
            _exec_form_shell(["/usr/bin/env", "-i", "FOO=1", "bash", "-c", "git b"]),
        )
        with self.assertRaisesRegex(AssertionError, "an exec-form `env -S`"):
            _exec_form_shell(["env", "-S", "sh -c", "git x"])
        # A launcher chain beyond the bound fails closed, as a shebang's does
        # (Codex on #396).
        with self.assertRaisesRegex(AssertionError, "a launcher chain beyond"):
            _exec_form_shell(["env", "env", "env", "env", "sh", "-c", "git x"])
        # The multi-call half of the bound too (Claude on #396).
        with self.assertRaisesRegex(AssertionError, "a launcher chain beyond"):
            _exec_form_shell([*["busybox"] * 4, "sh", "-c", "git x"])
        # The health check runs on its own; the process is read when the stage
        # ends, and Docker ignores `CMD` under a shell-form `ENTRYPOINT` (cubic on
        # #396).
        self.assertEqual(
            ["git e", "git d"],
            _dockerfile_runs(
                "FROM alpine\nCMD git c\nENTRYPOINT git d\n"
                "HEALTHCHECK --interval=5m CMD git e\n"
            ),
        )
        self.assertEqual(
            [],
            _dockerfile_runs('FROM alpine\nENTRYPOINT ["knowledge"]\nCMD ["--help"]\n'),
        )

    def test_no_build_overrides_a_from_argument(self) -> None:
        """A `FROM` that names a global `ARG` is read with its default, so no
        repository build may override that `ARG`: a caller's own `--build-arg` is
        outside the repository, the assumption this reader declares (Codex on
        #396)."""
        files = _files(ROOT)
        names: set[str] = set()
        for path in files:
            if CONTAINER_FILE.match(path.name):
                for line in path.read_text(encoding="utf-8").splitlines():
                    if (stage := FROM_LINE.fullmatch(line)) is not None:
                        names |= set(re.findall(r"\$\{?(\w+)", stage["image"]))
        self.assertEqual({"PYTHON_BASE_IMAGE"}, names)
        for path in files:
            # This module's own cases below are examples, not a build.
            if path.resolve() == Path(__file__).resolve():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for name in names:
                with self.subTest(path=str(path.relative_to(ROOT)), name=name):
                    self.assertFalse(_overrides_build_arg(text, name))
        # Every way a build names the argument, its value given or taken from the
        # environment (cubic on #396).
        base = "PYTHON_BASE_IMAGE"
        for text in (
            f'--build-arg "{base}=x"',
            f"--build-arg {base}=x",
            f"--build-arg={base}=x",
            f"--build-arg {base}",
            f"--build-arg={base}",
            f"--build-arg \\\n    {base}",
        ):
            with self.subTest(text=text):
                self.assertTrue(_overrides_build_arg(text, base))
        self.assertFalse(_overrides_build_arg(f"--build-arg {base}_X=y", base))

    def test_a_launcher_fails_closed(self) -> None:
        """A launcher such as `timeout`, `su` or `tini` runs a command by its own
        grammar, which may hand it to a shell without naming one, as `su -c` does, or
        name a shell this reader does not list, such as `bash5`. So a declared
        launcher fails closed, in an exec form and in a shebang alike (Codex and
        cubic on #396)."""
        for argv in (
            ["timeout", "10", "sh", "-c", "git x"],
            ["nice", "-n", "5", "bash", "-c", "git y"],
            ["sudo", "-u", "app", "/bin/sh", "-c", "git z"],
            ["su", "-c", "git w", "nobody"],
            ["timeout", "10", "bash5", "-c", "git v"],
            ["tini", "--", "knowledge"],
            # `find` runs its `-exec` action, and the rest run commands too (Codex on
            # #396).
            ["find", ".", "-exec", "sh", "-c", "git u", ";"],
            ["ssh", "host", "git t"],
            # A launcher after the bound's last wrapper is still a launcher (Codex on
            # #396).
            ["env", "env", "env", "timeout", "10", "sh", "-c", "git s"],
        ):
            launcher = next((word for word in argv if word != "env"), argv[0])
            with (
                self.subTest(argv=argv),
                self.assertRaisesRegex(AssertionError, f"a `{launcher}` launcher;"),
            ):
                _exec_form_shell(argv)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "t").write_bytes(b"#!/usr/bin/env -S timeout 10 sh\ngit t\n")
            declared = _declared(root)
            with self.assertRaisesRegex(AssertionError, "t: a `timeout` launcher;"):
                _shell_surfaces(declared)

    def test_a_continuation_follows_buildkit_s_rule(self) -> None:
        """BuildKit continues a line whose escape character is followed only by
        spaces or tabs, and skips empty and comment lines inside it; measured with
        a BuildKit build (Codex on #396)."""
        self.assertEqual(
            ["git a     && git b", "git c     && git d", "git e     && git f"],
            _dockerfile_runs(
                "FROM alpine\nRUN git a \\   \n    && git b\n"
                "RUN git c \\\n\n    && git d\n"
                "RUN git e \\\n# a comment\n    && git f\n"
            ),
        )
        # Only a lone escape character continues: two or three end the line, as a
        # BuildKit build measured (Claude on #396).
        for escapes in (2, 3):
            with self.subTest(escapes=escapes):
                self.assertEqual(
                    ["git a" + "\\" * escapes],
                    _dockerfile_runs(
                        "FROM alpine\nRUN git a" + "\\" * escapes + "\n    && git b\n"
                    ),
                )

    def test_an_exec_form_entrypoint_takes_its_cmd(self) -> None:
        """An exec-form `ENTRYPOINT` takes an exec-form `CMD` as its arguments, so
        the stage's process is read whole, as Docker runs it (Codex on #396). A
        stage inherits a named stage's; its own `ENTRYPOINT` resets an inherited
        `CMD`; a shell-form `ENTRYPOINT` ignores `CMD`; only the last of each runs.
        An exec-form `CMD` under an unknown base's `ENTRYPOINT` fails closed."""
        for dockerfile, expected in (
            ('FROM alpine\nENTRYPOINT ["sh"]\nCMD ["-c", "git a"]\n', ["git a"]),
            ('FROM alpine\nENTRYPOINT ["sh", "-c"]\nCMD ["git b"]\n', ["git b"]),
            (
                'FROM alpine AS base\nENTRYPOINT ["bash"]\nFROM base\nCMD ["-c", "git c"]\n',
                ["git c"],
            ),
            (
                'FROM alpine AS base\nENTRYPOINT ["sh", "-c"]\nCMD ["git d"]\n'
                'FROM base\nENTRYPOINT ["knowledge"]\n',
                ["git d"],
            ),
            # Docker ignores `CMD` under a shell-form `ENTRYPOINT`, though it
            # would run on its own.
            ('FROM alpine\nENTRYPOINT git e\nCMD ["sh", "-c", "git z"]\n', ["git e"]),
            (
                'FROM alpine\nCMD ["sh", "-c", "git old"]\nCMD ["sh", "-c", "git f"]\n',
                ["git f"],
            ),
            # Without the reset, the child would run `sh -c "git y"`.
            (
                'FROM alpine AS base\nENTRYPOINT ["knowledge"]\nCMD ["-c", "git y"]\n'
                'FROM base\nENTRYPOINT ["sh"]\n',
                [],
            ),
            ('FROM scratch\nCMD ["/app"]\n', []),
            # A shell-form `CMD` is part of the process too: one Docker ignores, or a
            # later one replaces, is not read (cubic on #396).
            ("FROM alpine\nCMD if then\nENTRYPOINT git i\n", ["git i"]),
            ("FROM alpine\nCMD git old\nCMD git j\n", ["git j"]),
            # `ONBUILD` triggers run in order in a later build, as if after its
            # `FROM`, so they are combined too (Codex on #396).
            (
                'FROM alpine\nONBUILD ENTRYPOINT ["sh"]\nONBUILD CMD ["-c", "git h"]\n',
                ["git h"],
            ),
            (
                'FROM alpine\nENTRYPOINT ["bash"]\nONBUILD CMD ["-c", "git k"]\n',
                ["git k"],
            ),
            # A stage built on this one runs its triggers right after its `FROM`
            # (Codex on #396), and a `-c` whose command a later stage supplies is
            # not yet a defect (cubic on #396).
            (
                'FROM alpine AS base\nONBUILD ENTRYPOINT ["sh", "-c"]\n'
                'FROM base\nCMD ["git x"]\n',
                ["git x"],
            ),
            (
                'FROM alpine AS base\nONBUILD ENTRYPOINT ["sh"]\n'
                'FROM base\nCMD ["-c", "git z"]\n',
                ["git z"],
            ),
            (
                'FROM alpine AS base\nENTRYPOINT ["sh", "-c"]\nFROM base\nCMD ["git y"]\n',
                ["git y"],
            ),
            ('FROM alpine\nENTRYPOINT ["knowledge"]\nCMD ["--help"]\n', []),
        ):
            with self.subTest(dockerfile=dockerfile):
                self.assertEqual(expected, _dockerfile_runs(dockerfile))
        with self.assertRaisesRegex(AssertionError, "an unknown base's `ENTRYPOINT`"):
            _dockerfile_runs('FROM example.com/tool\nCMD ["sh", "-c", "git g"]\n')

    def test_env_s_is_read_by_position_and_flags_belong_to_run(self) -> None:
        """An `S` inside `-u`'s attached argument is not `-S` (cubic on #396).
        Only `RUN` takes `--mount`-style flags; a runtime instruction keeps its
        command whole (cubic on #396). `HEALTHCHECK`'s own options precede its
        `CMD`, and `HEALTHCHECK NONE` runs nothing."""
        self.assertEqual(
            ["git x"], _exec_form_shell(["env", "-uSHELL", "bash", "-c", "git x"])
        )
        with self.assertRaisesRegex(AssertionError, "an exec-form `env -S`"):
            _exec_form_shell(["env", "-iS", "sh -c", "git x"])
        self.assertEqual(
            ["git e", "git f", "--quiet git y"],
            _dockerfile_runs(
                "FROM alpine\nCMD --quiet git y\n"
                "HEALTHCHECK --interval=5m --timeout=3s CMD git e\n"
                'HEALTHCHECK --interval=5m CMD ["sh", "-c", "git f"]\n'
                "HEALTHCHECK NONE\n"
            ),
        )

    def test_each_dockerfile_stage_has_its_own_shell(self) -> None:
        """A stage's shell is its base's: `sh` for a Linux image, a named stage's
        for a stage, its `SHELL` once set. A global `ARG`'s default resolves in
        `FROM`. A Windows base, `scratch`, or an unresolved reference leaves the
        shell unknown, so a shell-form `RUN` there fails closed (Codex on #396)."""
        self.assertEqual(
            ["git a", "git b"],
            _dockerfile_runs(
                "ARG BASE=alpine:3\nFROM ${BASE} AS base\nRUN git a\n"
                "FROM base AS next\nRUN git b\n"
            ),
        )
        self.assertEqual(
            ["git c"],
            _dockerfile_runs(
                "FROM mcr.microsoft.com/windows/servercore:ltsc2022\n"
                'SHELL ["bash", "-c"]\nRUN git c\n'
            ),
        )
        for text in (
            "FROM mcr.microsoft.com/windows/servercore:ltsc2022\nRUN dir\n",
            "FROM scratch\nRUN true\n",
            "FROM $UNSET\nRUN true\n",
            "RUN true\n",
        ):
            with (
                self.subTest(text=text),
                self.assertRaisesRegex(AssertionError, "a RUN whose shell is unknown"),
            ):
                _dockerfile_runs(text)

    def test_a_shebang_s_own_command_is_what_runs(self) -> None:
        """A shebang whose shell has `-c` runs that string, not the file's body;
        `-s` reads standard input instead, and fails closed (Codex on #396)."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "c").write_bytes(
                b"#!/usr/bin/env -S bash -c 'git status'\necho body\n"
            )
            (root / "e").write_bytes(b"#!/bin/sh -e\ngit log\n")
            self.assertEqual(
                {"c": "git status", "e": "#!/bin/sh -e\ngit log\n"},
                _shell_surfaces(_declared(root)),
            )
            (root / "s").write_bytes(b"#!/bin/sh -s\ngit log\n")
            declared = _declared(root)
            with self.assertRaisesRegex(
                AssertionError, "s: a shebang shell that reads"
            ):
                _shell_surfaces(declared)
        # With `-c`, bash ignores `-s`; dash runs the string, then reads standard
        # input too, so `sh`, `dash` and `ash` still fail closed (cubic on #396).
        cases: dict[bytes, dict[str, str] | str] = {
            b"#!/usr/bin/env -S bash -sc 'git status'\n": {"b": "git status"},
            b"#!/usr/bin/env -S sh -sc 'git status'\n": "b: a shebang shell that reads",
            # `-c -` names no command: such a file runs its own path as the
            # command, and so itself, without end (Claude on #396).
            b"#!/usr/bin/env -S sh -c -\n": "b: a shebang `-c` without its command",
        }
        for head, expected in cases.items():
            with self.subTest(head=head), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "b").write_bytes(head + b"git log\n")
                declared = _declared(root)
                if isinstance(expected, dict):
                    self.assertEqual(expected, _shell_surfaces(declared))
                else:
                    with self.assertRaisesRegex(AssertionError, expected):
                        _shell_surfaces(declared)
        with self.assertRaisesRegex(AssertionError, "a `-c` without its command"):
            _exec_form_shell(["sh", "-c", "-"])

    def test_the_probe_takes_a_bounded_list_of_strings(self) -> None:
        """The probe child refuses input that is not a list of strings (Amazon Q on
        #396), and the parent refuses a corpus beyond its bound before sending it
        (CodeAnt on #396); the answer, which grows with the input, is bounded with
        it."""
        completed = subprocess.run(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
            [sys.executable, str(PROBE)],
            input='{"not": "a list"}',
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("a JSON list of strings", completed.stderr)
        # Text that is not JSON at all is refused the same way, not with a
        # traceback (Amazon Q on #396).
        malformed = subprocess.run(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
            [sys.executable, str(PROBE)],
            input="not json",
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        self.assertEqual(2, malformed.returncode)
        self.assertIn("a JSON list of strings", malformed.stderr)
        self.assertNotIn("Traceback", malformed.stderr)
        # JSON nested past the decoder's recursion limit too (cubic on #396).
        nested = subprocess.run(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
            [sys.executable, str(PROBE)],
            input="[" * 100_000,
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        self.assertEqual(2, nested.returncode)
        self.assertIn("a JSON list of strings", nested.stderr)
        self.assertNotIn("Traceback", nested.stderr)
        # An integer past Python's digit limit raises `ValueError` (CodeAnt on #396).
        digits = subprocess.run(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
            [sys.executable, str(PROBE)],
            input="[" + "1" * 5000 + "]",
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        self.assertEqual(2, digits.returncode)
        self.assertIn("a JSON list of strings", digits.stderr)
        self.assertNotIn("Traceback", digits.stderr)
        with self.assertRaisesRegex(AssertionError, "beyond the probe's input bound"):
            _probe(["x" * (PROBE_INPUT_LIMIT + 1)])
        # The child bounds its own read too, at the same limit, whoever writes to it
        # (Amazon Q on #396); it reads no more than one character past it.
        probe = ast.parse(PROBE.read_text(encoding="utf-8"))
        [limit] = [
            node.value
            for node in probe.body
            if isinstance(node, ast.Assign)
            and [getattr(target, "id", None) for target in node.targets]
            == ["INPUT_LIMIT"]
        ]
        self.assertEqual(PROBE_INPUT_LIMIT, ast.literal_eval(limit))
        oversized = subprocess.run(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
            [sys.executable, str(PROBE)],
            input=json.dumps(["x" * PROBE_INPUT_LIMIT]),
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        self.assertEqual(2, oversized.returncode)
        self.assertIn("beyond the probe's input bound", oversized.stderr)

    def test_a_recursive_yaml_alias_fails_closed(self) -> None:
        """`safe_load` builds self-referential lists and mappings from recursive
        aliases; both walkers refuse a cycle rather than loop on it, and still read an
        anchor that is merely reused (CodeAnt on #396)."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "w.yml"
            # The GitHub walker on a workflow; the GitLab flattening on a script
            # outside `.github` (cubic on #396).
            for document, under_github in (
                ("on: push\njobs: &j\n  again: *j\n", True),
                ("job:\n  image: alpine\n  script: &s\n    - git a\n    - *s\n", False),
            ):
                path.write_text(document, "utf-8")
                with (
                    self.subTest(document=document),
                    self.assertRaisesRegex(AssertionError, "a recursive YAML alias"),
                ):
                    _ci_shell(path, under_github=under_github)
            path.write_text(
                "job:\n  image: alpine\n  before_script: &s [git a]\n"
                "  script: [*s, git b]\n",
                "utf-8",
            )
            self.assertEqual(
                ["git a", "git a\ngit b"], _ci_shell(path, under_github=False)
            )

    def test_a_gitlab_job_named_like_github_s_keys_stays_gitlab(self) -> None:
        """A workflow has `on` and `jobs`, an action `runs.using`; a GitLab job may
        be named `jobs` or `runs` (CodeAnt on #396)."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".gitlab-ci.yml").write_text(
                "image: alpine\njobs:\n  script: git status\nruns:\n  script:\n    - git log\n",
                "utf-8",
            )
            declared = _declared(root)
            self.assertEqual(
                {".gitlab-ci.yml#0": "git status", ".gitlab-ci.yml#1": "git log"},
                _shell_surfaces(declared),
            )

    def test_a_shebang_is_classified_by_its_interpreter(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scripts = {
                "a": b"#!/bin/ash\ngit a\n",
                "b": b"#!/usr/local/bin/bash\ngit b\n",
                "c": b"#!/usr/bin/env -S bash -e\ngit c\n",
                "d": b"#! /bin/dash\ngit d\n",
                "e": b"#!/usr/bin/env -S 'bash' -e\ngit e\n",
                "f": b"#!/usr/bin/env VAR=1 bash\ngit f\n",
                "g": b"#!/usr/bin/env --split-string=bash -e\ngit g\n",
                "h": b"#!/usr/bin/env -Sbash -e\ngit h\n",
                "j": b"#!/usr/bin/env -i - --unset=X -C /tmp -0v bash\ngit j\n",
                # GNU env's `-S` escapes: `\_` separates, `\c` ends the string,
                # `#` at a word's start is a comment (CodeAnt on #396).
                "m": b"#!/usr/bin/env -S bash\\_-e\ngit m\n",
                "n": b"#!/usr/bin/env -S sh\\c junk\ngit n\n",
                "o": b"#!/usr/bin/env -S bash #comment\ngit o\n",
                "p": b"#!/usr/bin/env python3\nprint()\n",
            }
            for name, content in scripts.items():
                (root / name).write_bytes(content)
            self.assertEqual(
                {"a", "b", "c", "d", "e", "f", "g", "h", "j", "m", "n", "o"},
                set(_shell_surfaces(_declared(root))),
            )
            for content in (
                b"#!\ngit u\n",
                b"#! \t\ngit u\n",
                b"#!/bin/\xffsh\ngit u\n",
                b"#!/usr/bin/env -S 'bash\ngit u\n",
                b"#!/usr/bin/env -u\ngit u\n",
                # Quotes make one word, and no program is named `bash -e`; the
                # environment decides an expansion; an unknown escape is env's
                # error (GNU coreutils, `env.c`).
                b'#!/usr/bin/env -S "bash -e"\ngit u\n',
                b'#!/usr/bin/env --split-string="bash -e"\ngit u\n',
                b'#!/usr/bin/env "bash"\ngit u\n',
                b"#!/usr/bin/env -S ${SHELL}\ngit u\n",
                b"#!/usr/bin/env -S bash\\q\ngit u\n",
            ):
                (root / "u").write_bytes(content)
                declared = _declared(root)
                with (
                    self.subTest(shebang=content),
                    self.assertRaisesRegex(AssertionError, "u: an unreadable shebang"),
                ):
                    _shell_surfaces(declared)
            (root / "u").unlink()
            # An option's argument or an assignment is not the command (Codex,
            # Claude and CodeAnt on #394).
            for content in (
                b"#!/usr/bin/env -u bash python3\nprint()\n",
                b"#!/usr/bin/env FOO=bash python3\nprint()\n",
                b"#!/usr/bin/env --chdir=/bin/sh perl\nprint 1\n",
            ):
                (root / "v").write_bytes(content)
                with self.subTest(shebang=content):
                    self.assertNotIn("v", _shell_surfaces(_declared(root)))
            (root / "v").unlink()
            # A chained env is followed to its command (Claude on #396).
            for content in (
                b"#!/usr/bin/env env bash\ngit k\n",
                b"#!/usr/bin/env -S env -i bash\ngit k\n",
            ):
                (root / "k").write_bytes(content)
                declared = _declared(root)
                with self.subTest(shebang=content):
                    self.assertIn("k", _shell_surfaces(declared))
            (root / "k").write_bytes(b"#!/usr/bin/env env env env env bash\ngit k\n")
            declared = _declared(root)
            # One launcher walk serves shebangs and exec forms (Claude on #396).
            with self.assertRaisesRegex(AssertionError, "k: a launcher chain beyond"):
                _shell_surfaces(declared)
            (root / "k").unlink()
            # A shell-like name that is no known shell fails closed (Claude on #394).
            (root / "q").write_bytes(b"#!/bin/bash5\ngit q\n")
            declared = _declared(root)
            with self.assertRaisesRegex(
                AssertionError, "q: an unrecognised shell `bash5`"
            ):
                _shell_surfaces(declared)
            (root / "q").unlink()
            # An option env does not document fails closed.
            (root / "x").write_bytes(b"#!/usr/bin/env --frobnicate bash\ngit x\n")
            declared = _declared(root)
            with self.assertRaisesRegex(AssertionError, "x: an unknown env option"):
                _shell_surfaces(declared)
            (root / "x").unlink()
            # A shell script with a YAML name is read by its shebang (Codex on #394).
            (root / "tool.yml").write_bytes(b"#!/bin/sh\ngit y\n")
            self.assertIn("tool.yml", _shell_surfaces(_declared(root)))
            (root / "tool.yml").unlink()
            (root / "w").write_bytes(b"#!/usr/bin/env -u NAME zsh\ngit w\n")
            declared = _declared(root)
            with self.assertRaisesRegex(AssertionError, "w: a `zsh` script"):
                _shell_surfaces(declared)
            (root / "w").unlink()
            # A shell whose name does not end in `sh` is named, so it fails closed
            # too (CodeAnt on #396).
            for shell in ("powershell", "nu", "elvish", "rc", "es"):
                (root / "o").write_bytes(f"#!/usr/bin/{shell}\ngit o\n".encode())
                declared = _declared(root)
                with (
                    self.subTest(interpreter=shell),
                    self.assertRaisesRegex(AssertionError, f"o: a `{shell}` script"),
                ):
                    _shell_surfaces(declared)
            (root / "o").unlink()
            (root / "z").write_bytes(b"#!/usr/bin/env zsh\ngit z\n")
            declared = _declared(root)
            with self.assertRaisesRegex(AssertionError, "z: a `zsh` script"):
                _shell_surfaces(declared)


RETAINED_SCRIPTS = [
    "stress_probe.py",
    "audit_oracle.py",
    "audit_docs.py",
    "evaluate314.py",
    "corpus_scripts.py",
    "diff_parsers.py",
    "oracle.py",
    "docs.py",
    "worker.py",
    "parent.py",
    "spike.py",
    "gate.py",
    "crash_doc.py",
]


class RetainedEvidenceTests(unittest.TestCase):
    """The assessment's retained evidence is the evidence it names (Codex and
    CodeRabbit on #394)."""

    ASSESSMENT = ROOT / "knowledge/assessments/0108-shell-parser-evaluation.md"
    EVIDENCE = ROOT / "knowledge/assessments/0108-shell-parser-evaluation.json"

    ARCHIVE = (
        ROOT
        / "knowledge/assessments/0108-shell-parser-evaluation-evidence"
        / "spike-scripts.tar.gz"
    )

    def test_each_retained_script_is_a_native_file_of_its_declared_digest(
        self,
    ) -> None:
        """The scripts are retained as native `.py` files, byte for byte, in the
        evidence archive (Codex on #394; AGENTS.md: executable artifacts stay
        canonical in their native formats). The assessment declares each digest."""
        text = self.ASSESSMENT.read_text(encoding="utf-8")
        declared = dict(
            re.findall(r"^\| `([\w.]+\.py)` \| `([0-9a-f]{16})…` \|", text, re.M)
        )
        with tarfile.open(self.ARCHIVE, "r:gz") as archive:
            members = archive.getmembers()
            # The exact inventory, so a lost script fails too (CodeAnt on #394).
            self.assertEqual(
                sorted(RETAINED_SCRIPTS), [member.name for member in members]
            )
            self.assertEqual(sorted(RETAINED_SCRIPTS), sorted(declared))
            for member in members:
                with self.subTest(script=member.name):
                    self.assertTrue(member.isfile())
                    handle = archive.extractfile(member)
                    if handle is None:
                        self.fail(f"{member.name} has no content")
                    digest = hashlib.sha256(handle.read()).hexdigest()
                    self.assertTrue(digest.startswith(declared[member.name]))
        # The prose holds no copy that could drift from the archive.
        self.assertNotIn("````text", text)

    def test_the_assessment_prints_the_archive_s_digests(self) -> None:
        """The digest prefixes the assessment prints are those of the JSON
        evidence, for the archive and for each script, so neither can go stale
        (CodeAnt on #396)."""
        text = self.ASSESSMENT.read_text(encoding="utf-8")
        scripts = json.loads(self.EVIDENCE.read_text(encoding="utf-8"))["spike_scripts"]
        [archive] = re.findall(
            r"spike-scripts\.tar\.gz\)\n\(SHA-256 `([0-9a-f]{16})…`\)", text
        )
        self.assertTrue(scripts["sha256"].startswith(archive))
        printed = dict(
            re.findall(r"^\| `([\w.]+\.py)` \| `([0-9a-f]{16})…` \|", text, re.M)
        )
        full = {member["name"]: member["sha256"] for member in scripts["members"]}
        self.assertEqual(sorted(full), sorted(printed))
        for name, digest in printed.items():
            with self.subTest(script=name):
                self.assertTrue(full[name].startswith(digest))

    def test_the_evaluated_artifacts_keep_their_full_digests(self) -> None:
        """Decision 0108 item 12 asks for the hashes of the wheels and binaries, so
        the JSON evidence keeps each full SHA-256 and its source, and the prefixes
        the assessment prints are theirs (Codex on #396). The image's full identity
        was never recorded, and the assessment says so."""
        text = self.ASSESSMENT.read_text(encoding="utf-8")
        artifacts = json.loads(self.EVIDENCE.read_text(encoding="utf-8"))["artifacts"]
        self.assertEqual(
            [
                "tree_sitter-0.25.2-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl",
                "tree_sitter_bash-0.25.1-cp310-abi3-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl",
                "tree_sitter-0.26.0-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl",
                "shfmt_v3.10.0_linux_amd64",
                "shfmt_v3.14.1_linux_amd64",
            ],
            [artifact["name"] for artifact in artifacts],
        )
        printed = re.findall(r"`([0-9a-f]{16})`", text.split("## Corpus", 1)[0])
        self.assertEqual(len(artifacts), len(printed))
        for artifact, prefix in zip(artifacts, printed, strict=True):
            with self.subTest(artifact=artifact["name"]):
                self.assertRegex(artifact["sha256"], r"\A[0-9a-f]{64}\Z")
                self.assertTrue(artifact["sha256"].startswith(prefix))
                self.assertTrue(artifact["source"].startswith("https://"))
        self.assertIn("its full identity was not recorded", " ".join(text.split()))

    def test_the_archive_is_deterministic_and_matches_its_full_digests(self) -> None:
        """The archive and each member match their full SHA-256 in the JSON
        evidence, not a prefix (CodeAnt on #396), and the archive is as deterministic
        as the assessment says: sorted members, no times or owners, mode 0644
        (Claude on #396)."""
        evidence = json.loads(self.EVIDENCE.read_text(encoding="utf-8"))
        scripts = evidence["spike_scripts"]
        self.assertEqual(
            scripts["sha256"], hashlib.sha256(self.ARCHIVE.read_bytes()).hexdigest()
        )
        expected = {member["name"]: member["sha256"] for member in scripts["members"]}
        with tarfile.open(self.ARCHIVE, "r:gz") as archive:
            members = archive.getmembers()
            self.assertEqual(sorted(expected), [member.name for member in members])
            for member in members:
                with self.subTest(script=member.name):
                    self.assertEqual(
                        (0, 0, 0, "", "", 0o644),
                        (
                            member.mtime,
                            member.uid,
                            member.gid,
                            member.uname,
                            member.gname,
                            member.mode,
                        ),
                    )
                    handle = archive.extractfile(member)
                    if handle is None:
                        self.fail(f"{member.name} has no content")
                    self.assertEqual(
                        expected[member.name], hashlib.sha256(handle.read()).hexdigest()
                    )

    def test_the_oracle_is_retained_with_its_digest(self) -> None:
        evidence = json.loads(self.EVIDENCE.read_text(encoding="utf-8"))
        oracle = evidence["oracle"]["entries"]
        self.assertEqual(76, len(oracle))
        # `oracle.py` wrote it with `json.dump(oracle, …, indent=0)`, so those bytes
        # are what its digest names.
        self.assertEqual(
            evidence["oracle"]["sha256"],
            hashlib.sha256(json.dumps(oracle, indent=0).encode("utf-8")).hexdigest(),
        )
        counts: dict[str, int] = {}
        for entry in oracle:
            counts[entry["path"]] = counts.get(entry["path"], 0) + 1
        self.assertEqual(evidence["oracle_git_commands_per_file"], counts)


if __name__ == "__main__":
    unittest.main()
