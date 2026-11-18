"""The pinned shell parser pair is installed, compatible, and reads the constructs
the shell reader relies on (Decision 0108).

The surface extraction below is interim. Decision 0108's item 1 makes host-language
extraction the reader's own (#369), and nothing on `main` owns it yet. When #369
lands, this smoke consumes the reader's extraction and these helpers are deleted, so
the two cannot drift apart (Claude on #394)."""

from __future__ import annotations

import json
import re
import shlex
import subprocess  # nosec B404 -- test-only boundary; the argv below is literal
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

from tools.gitlab_ci_reader import GitlabUnsupported, read_scripts
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
    "cmd",
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
    # The scripts' own length first, so an oversized corpus is refused before it is
    # serialised again (CodeAnt on #396); the payload, which escapes may lengthen,
    # after.
    if sum(len(script) for script in scripts) > PROBE_INPUT_LIMIT:
        raise AssertionError(
            "a corpus beyond the probe's input bound, before it is serialised"
        )
    payload = json.dumps(scripts)
    if len(payload) > PROBE_INPUT_LIMIT:
        raise AssertionError(
            f"a corpus of {len(payload)} characters, beyond the probe's input bound"
        )
    done = subprocess.run(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit  # -- test-only fixed interpreter/probe argv with bounded JSON stdin and deadline
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
    answer = _probe(scripts)["facts"]
    if not isinstance(answer, list):
        raise AssertionError("the probe facts are not a list of mappings")
    if len(answer) != len(scripts):
        raise AssertionError("the probe facts must contain one fact per input script")
    facts: list[dict[str, object]] = []
    for fact in answer:
        if not isinstance(fact, dict):
            raise AssertionError("the probe facts include a non-mapping")
        if set(fact) != {"names", "errors", "heredocs"}:
            raise AssertionError("the probe fact has unexpected fields")
        for field in ("names", "heredocs"):
            values = fact[field]
            if not isinstance(values, list) or not all(
                isinstance(value, str) for value in values
            ):
                raise AssertionError(f"the probe fact {field} is not a list of strings")
        errors = fact["errors"]
        # bool is an int subclass, but the producer emits a node count.
        if isinstance(errors, bool) or not isinstance(errors, int) or errors < 0:
            raise AssertionError("the probe fact errors is not a nonnegative integer")
        facts.append(fact)
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


def _gitlab_reader_scripts(
    document: dict[str, object], name: str
) -> dict[str, list[list[tuple[str, object]]]] | None:
    """Translate loaded jobs through the shared reader or its explicit legacy domain."""
    # The shared inventory reader owns ordinary script/default/extends extraction.
    # This adapter renders already-loaded data, so its generated YAML locations
    # are intentionally not presented as source locations. Non-script global
    # metadata stays with the caller, including its image/shell checks.
    reader_document = {
        key: value
        for key, value in document.items()
        if key not in GITLAB_GLOBALS
        or key in GITLAB_KEYS
        or key in {"default", "image", "include"}
    }
    try:
        return read_scripts(
            yaml.safe_dump(reader_document, sort_keys=False, default_style="|")
        )
    except GitlabUnsupported as exc:
        reason = str(exc)
        legacy = reason.startswith(
            (
                "a YAML anchor",
                "a YAML alias",
                "inherit in ",
                "a multi-line flow item",
                "extends past eleven levels at ",
            )
        ) or reason.endswith(" has a non-string or deeper item")
        default = document.get("default")
        legacy = legacy or (
            reason == "an unsupported default"
            and isinstance(default, dict)
            and "inherit" in default
        )
        if not legacy:
            raise _refuse(name, f"shared GitLab reader: {reason}") from exc
        # Frozen compatibility cases exceed the inventory reader's declared
        # domain. Keep this explicit, unchanged legacy path until #369 supplies
        # qualified extraction; an arbitrary shared-reader failure is not a
        # reason to fall back. Hooks/run/unexecuted-template evidence below is
        # likewise caller-owned, not an expansion of the inventory contract.
        return None


def _gitlab_scripts(document: dict[str, object], name: str) -> list[str]:
    """Each GitLab CI job's shell, as the runner runs it: the job's effective
    `before_script` and `script` concatenated into one script, its `after_script`
    apart, each from the job, its `extends` lineage, then `default` or the
    deprecated global one, unless `inherit` drops it (Codex on #396); and its hook
    commands and `run` steps. A template no running job extends, and `default` and
    the global sections when no job runs, are read alone, so no shell goes unread.
    A global keyword, such as `variables`, is not a job (Codex on #396); a job that
    runs is read only in a container image whose shell is known (Codex on #396)."""
    _check_gitlab_shells(document, name)
    shared = _gitlab_reader_scripts(document, name)
    # Hooks run before the clone, so before any script; `run` steps stand in for a
    # `script` (Codex on #396).
    found: list[str] = []
    for key, value in document.items():
        if isinstance(value, dict) and (key == "default" or key not in GITLAB_GLOBALS):
            found.extend(_gitlab_hooks(value))
            found.extend(_gitlab_run_steps(value, key, name))
    running = [
        (key, job)
        for key, job in document.items()
        if isinstance(job, dict)
        and key not in GITLAB_GLOBALS
        and not key.startswith(".")
        and "trigger" not in job
    ]
    covered: set[str] = set()
    for key, job in running:
        found.extend(
            _gitlab_job_scripts(
                document,
                key,
                job,
                covered,
                name,
                None if shared is None else shared.get(key),
            )
        )
    found.extend(_gitlab_unrun_scripts(document, covered, bool(running)))
    return found


def _gitlab_job_scripts(
    document: dict[str, object],
    key: str,
    job: dict[str, object],
    covered: set[str],
    name: str,
    shared: list[list[tuple[str, object]]] | None = None,
) -> list[str]:
    """One running job's shell: its effective `before_script` and `script` as one
    script, its `after_script` apart (Codex on #396). The lineage it reads joins
    `covered`."""
    lineage = _gitlab_lineage(document, job, key, name)
    covered.update(base for base, _ in lineage)
    if shared is not None:
        return ["\n".join(text for text, _ in part) for part in shared]
    main = [
        *_script_value(_gitlab_inherited(document, lineage, "before_script")),
        *_script_value(_gitlab_inherited(document, lineage, "script")),
    ]
    found = ["\n".join(main)] if main else []
    found.extend(_script_value(_gitlab_inherited(document, lineage, "after_script")))
    return found


def _gitlab_unrun_scripts(
    document: dict[str, object], covered: set[str], running: bool
) -> list[str]:
    """The sections no running job takes, read alone so that no shell goes unread:
    a template no job extends, and, when no job runs, `default`'s and the deprecated
    global ones."""
    found: list[str] = []
    for key, value in document.items():
        if key in GITLAB_KEYS and not running:
            # A deprecated but valid global lifecycle script (Codex on #396).
            found.extend(_script_value(value))
        elif (
            isinstance(value, dict)
            and (key == "default" or key not in GITLAB_GLOBALS)
            and key not in covered
            and not (key == "default" and running)
        ):
            for script in GITLAB_KEYS:
                found.extend(_script_value(value.get(script)))
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


def _refuse_extends_cycle(document: dict[str, object], key: str, name: str) -> None:
    """Fails closed when `key`'s `extends` chain returns to a job still on it: a
    cycle, unlike a base two paths reach. A depth-first walk marks each job when it
    is entered and when it is left, so each is visited once, and a chain of
    diamonds stays linear (cubic on #396). Malformed bases are left to the lineage
    walk, which refuses them."""
    entered: set[str] = set()
    left: set[str] = set()
    stack: list[tuple[str, bool]] = [(key, False)]
    while stack:
        current, leaving = stack.pop()
        if leaving:
            left.add(current)
            continue
        if current in left:
            continue
        if current in entered:
            raise _refuse(name, f"`{key}`: an `extends` cycle through `{current}`")
        entered.add(current)
        stack.append((current, True))
        job = document.get(current)
        extends = job.get("extends", []) if isinstance(job, dict) else []
        bases = [extends] if isinstance(extends, str) else extends
        if isinstance(bases, list):
            stack.extend((base, False) for base in bases if isinstance(base, str))


def _gitlab_lineage(
    document: dict[str, object], job: dict[str, object], key: str, name: str
) -> list[tuple[str, dict[str, object]]]:
    """A job and its `extends` bases, in GitLab's precedence: the job, then its
    last base and that base's own bases, and so on. A base reached twice is read
    once; an unknown or malformed one fails closed, and so does a cycle, which GitLab
    refuses (CodeAnt on #396)."""
    _refuse_extends_cycle(document, key, name)
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


def _gitlab_inherited(
    document: dict[str, object],
    lineage: list[tuple[str, dict[str, object]]],
    keyword: str,
) -> object:
    """A job's `keyword`: the first its lineage gives, else `default`'s, else the
    deprecated global one, unless `inherit` drops the default (Codex on #396)."""
    for _, current in lineage:
        if keyword in current:
            return current[keyword]
    # The nearest `inherit: default` in the lineage, as GitLab merges a base's keys
    # into the job (Codex on #396).
    inherited: object = True
    for _, current in lineage:
        inherit = current.get("inherit")
        if isinstance(inherit, dict) and "default" in inherit:
            inherited = inherit["default"]
            break
    if inherited is not True and not (
        isinstance(inherited, list) and keyword in inherited
    ):
        return None
    default = document.get("default")
    if isinstance(default, dict) and keyword in default:
        return default[keyword]
    return document.get(keyword)


def _gitlab_image(
    document: dict[str, object], lineage: list[tuple[str, dict[str, object]]]
) -> object:
    """A job's image, inherited as any default keyword is."""
    return _gitlab_inherited(document, lineage, "image")


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
    list of lines; an absent one is nothing. Any other shape fails closed, as GitLab
    refuses it (CodeAnt on #396)."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return ["\n".join(_script_lines(value))]
    raise AssertionError("a GitLab script of an unread shape; extend this extraction")


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
        launcher = _program_stem(words[0]) if words else ""
        if launcher == "env":
            words = _env_operands(words[1:], name, split=split)
        elif launcher in MULTI_CALL:
            words = words[1:]
        else:
            return _refuse_launched_shell(words, name)
    # Each launcher however Windows spells it (Codex on #396).
    if words and (
        _program_stem(words[0]) == "env" or _program_stem(words[0]) in MULTI_CALL
    ):
        raise _refuse(name, "a launcher chain beyond the bound")
    # A launcher right after the bound's last wrapper is still one (Codex on #396).
    return _refuse_launched_shell(words, name)


def _refuse_launched_shell(words: list[str], name: str) -> list[str]:
    """`words` unchanged, unless they are a declared launcher: each runs a command by
    its own grammar, which may hand it to a shell without naming one, as `su -c`
    does, or name a shell this reader does not list. So one fails closed, whatever
    follows it (Codex and cubic on #396)."""
    launcher = _program_stem(words[0]) if words else ""
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


def _program_stem(word: str) -> str:
    """The program a word names, as a shell is classified: its basename across both
    path separators, case-folded, without `.exe`, since Windows names are
    case-insensitive (cubic and Codex on #396)."""
    return re.split(r"[\\/]", word)[-1].casefold().removesuffix(".exe")


def _other_shell(word: str) -> bool:
    """Whether the program `word` names is a shell this reader does not read: a
    listed one, or a shell-like name that is no known shell. One test serves
    shebangs and exec forms (Codex on #396). A Windows name is a path with either
    separator, in any case, with or without `.exe` (cubic and Codex on #396)."""
    stem = _program_stem(word)
    if stem in OTHER_SHELLS:
        return True
    return stem not in SHELLS and SHELL_LIKE.match(stem) is not None


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
    if _other_shell(argv[0] if argv else ""):
        raise AssertionError(f"an exec-form `{program}` RUN; extend this extraction")
    # A supported shell as Windows names it is still that shell (Codex on #396).
    if _program_stem(argv[0] if argv else "") not in SHELLS:
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
        # BuildKit continues past spaces or tabs after the escape character, and
        # skips empty and comment lines inside a continuation (Codex on #396); a
        # `SHELL` continues too, so it is joined before it is read (CodeAnt on #396).
        while (end := CONTINUATION.search(command)) and index < len(lines):
            line = lines[index]
            index += 1
            if line.strip() and not line.lstrip().startswith("#"):
                command = command[: end.start()] + line
        if match["instruction"].upper() == "SHELL":
            _check_shell_instruction(command)
            # `ONBUILD SHELL` changes no current stage, only the `ONBUILD RUN`s
            # after it (Codex on #396).
            state.set_shell("sh", deferred=deferred)
            continue
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
    (Codex on #394). A symlink in a canonical path is refused without reading
    its target, including an ancestor component (cubic on #396)."""
    paths: list[Path] = []
    for relative in candidate_paths(root):
        path = root
        for part in relative.parts:
            path /= part
            if path.is_symlink():
                raise _refuse(relative.as_posix(), "a candidate symlink")
        if path.is_file():
            paths.append(path)
    return paths


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
    if _other_shell(words[0]):
        raise _refuse(name, f"an unrecognised shell `{command}`")
    # A supported shell as Windows or Cygwin names it is that shell (Codex on #396).
    shell = _program_stem(words[0])
    if shell not in SHELLS:
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
    if reads_input and not (inline and shell == "bash"):
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
