---
type: Source
title: Shell parser evaluation for Decision 0108
description: The measured comparison of tree-sitter-bash 0.25.1 and mvdan/sh 3.14.1 as the shell parser behind the reuse check, over the frozen shell corpus at c8ababd, with the worker-boundary timing, the tree-sitter 0.26.0 crash reproducer, the environment and the spike scripts.
status: draft
generated:
  by: anthropic/claude-opus-5-5
  at: "2026-10-07T21:00:00Z"
sources:
  - id: evidence-json
    resource: ./0108-shell-parser-evaluation.json
    title: Machine-readable corpus identity, oracle counts and results
  - id: decision
    resource: ../decisions/0108-read-shell-text-with-a-parser-behind-an-owned-analysis.md
    title: Read shell text with a parser behind an owned analysis
  - id: owner-analysis
    resource: https://github.com/ktogias/gnostoa/pull/369#issuecomment-6045281181
    title: The owner's analysis that asked for this durable evidence
x-project-knowledge:
  id: kit.assessment.0108-shell-parser-evaluation
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
---

# Shell parser evaluation for Decision 0108

## Subject and environment

- **Subject:** `ktogias/gnostoa` at `c8ababdaa11a0901e3661b8bba594fd7b2ef6c13`, #369's
  frozen head (round 47).
- **Image:** the development target, `sha256:0099ecaeef2a…`; Python 3.12.14 on Linux
  x86_64, glibc 2.41.
- **Wheel SHA-256 values** (the first 16 hex digits):

  | Wheel | SHA-256 |
  |---|---|
  | `tree_sitter-0.25.2` (cp312, manylinux x86_64) | `b43a9e4c89d4d083` |
  | `tree_sitter_bash-0.25.1` (abi3, manylinux x86_64) | `3f484c4bb8796cde` |
  | `tree_sitter-0.26.0`, the crashing pair's runtime | `5a6b333b0282d8bb` |

- **The mvdan/sh binaries:**
  - `shfmt` v3.10.0: `1f57a384d59542f8`;
  - v3.14.1 (`shfmt_v3.14.1_linux_amd64`): `76e77641faa02581`. The v3.14.1 release
    publishes no checksum file, so this is a measurement, not a provenance claim.

## Corpus

The surfaces are each workflow and action `run:` value, extracted through YAML so
that its block indentation is removed. Every other shell surface is taken whole: the
reader's lines for scripts, `AGENTS.md` fences, Make recipes and Dockerfile `RUN`
instructions.

- Each `${{ … }}` is masked by underscores of the same width.
- That gives 127 scripts from 27 files.
- [The JSON evidence](./0108-shell-parser-evaluation.json) lists each script with its
  masked SHA-256. It also holds the oracle: its 76 Git commands, each with its file
  and argv, the count per file, and the SHA-256 of the bytes `oracle.py` wrote.
  Decision 0108's item 12 requires that SHA-256; the first revision omitted it
  (CodeRabbit on #394).

A first pass kept the YAML indentation. That left each here-document's terminator
off column 0, and mvdan/sh rightly refused nine documents as unclosed
here-documents, where tree-sitter silently tolerated them. The extraction above
corrects that.

## Results

| Parser | Git commands | Scripts with a parse problem | Dynamic command words |
|---|---|---|---|
| tree-sitter-bash 0.25.1 (`tree-sitter` 0.25.2) | 76 | 1: `AGENTS.md`, its `<…>` placeholders | 10 |
| mvdan/sh 3.14.1 | 75 | 1: `AGENTS.md` | 7 |

- **Agreement.** The two agree on every one of the 75 real Git executions. The one
  difference is `command -v git` in `AGENTS.md`. tree-sitter parses that file
  partially, and the policy takes the lookup for an execution, which is a policy false
  positive. mvdan/sh refuses the whole file, which is UNKNOWN.
- **The line pattern, at the same subject:**
  - the frozen `git-execution` line pattern caught all 76;
  - the token reader caught 28;
  - neither missed any.
- **The reader's own 30 tests** (supporting only, since they are line-fragment
  oriented):
  - tree-sitter fails 2: ``x=a`date`b git status``, which lands as UNKNOWN, and
    nested escaped backticks;
  - mvdan/sh fails 5, every one an incomplete line fragment that it refuses.

## The worker boundary

One worker process parsed all 127 scripts in 0.51 s, against 0.05 s in-process, the
difference being interpreter start. A forced SIGSEGV in the worker reached the parent
as exit `-11`, and the parent recorded UNKNOWN for all 127.

## The tree-sitter 0.26.0 crash

- **Pairs:** with `tree-sitter` 0.26.0 and `tree-sitter-bash` 0.25.1, `gate.py`
  segfaults deterministically. With 0.25.2 and 0.25.1 it completes.
- **Conditions:** it needs the gate's interleaving of nested parses (a policy
  recursion into `sh -c` strings) with node access, in one process.
  - Parsing each of the 27 documents alone does not crash.
  - Neither does a plain sequential traversal of all of them, whether with one shared
    parser or a new parser per document.
  - A minimal reproducer is still open.
- **Upstream's case:** the 5-byte SIGSEGV of tree-sitter-bash#337, `{𱡀`, did not
  reproduce through the Python binding with either pair. It is recorded as not
  reproduced, not as safe.

## The evidence scripts' limits

The spike scripts below are kept exactly as they ran, each bound by its SHA-256.
Editing one would leave the recorded results without the code that produced them.
They are evaluation tooling: Decision 0108's rules bind the reader that #369
rebuilds, not these scripts.

Review on #394 raised four questions about them. Each is answered here, with
measurements taken on the frozen subject:

- **Files that `docs.py` skipped.** Its `try` passes over any file that raises.
  At the frozen subject, 19 of the 672 tracked files raised `UnicodeDecodeError`.
  Every one is a binary archive: 18 gzip or tar files and one zip file. None
  starts with `#!`. The 27 files with shell surfaces are the corpus's 27.
- **BOM and line endings.** None of the 27 files starts with a UTF-8 BOM, and none
  holds a CR. Reading them as `utf-8` and splitting on `\n` therefore changed no
  corpus text.
- **The child environment.** `parent.py` passes its own environment to the worker.
  It ran once, in a disposable container of the development image. The rebuilt
  reader's worker environment is #369's to bound.
- **The oracle's independence.** `oracle.py` takes the oracle from tree-sitter's
  own commands, filtered by the policy, so it cannot show on its own that tree-sitter
  missed nothing. `audit_oracle.py` checks it against the text alone. It finds every
  occurrence of the word `git`, including path-qualified ones, in the 127 masked
  scripts. Of the 79 occurrences, 76 lie inside the oracle's 76 commands. The other 3
  are not shell executions:
  - the Dockerfile's `"git=${GIT_PACKAGE_VERSION}"`, a package argument to `apt-get`;
  - `ci/style`'s `"git",`, inside a Python here-document fed to `python -`;
  - a comment in the 365 evidence script.

  No shell Git execution that names `git` is missing from the oracle. Commands whose
  name is not static (the 10 dynamic command words) are UNKNOWN under the policy, and
  the oracle does not count them (Codex on #394).
- **Timeouts.** The `shfmt` adapter in `evaluate314.py` sets no timeout. Every run
  completed with the results above. Decision 0108's items 9 and 10 bound the
  rebuilt reader's worker, including its timeout.

### `audit_oracle.py`

Checks the oracle's completeness against the text alone: each occurrence of the word
`git` in the 127 masked scripts lies either inside a command the oracle counted, or is
listed. SHA-256 `94f5faf4f4aea242…`. Output: 79 occurrences, 76 inside an oracle command, and the
3 listed above.

````text
import json, re, sys
sys.argv = ["x"]
exec(open("/spike/corpus_scripts.py").read().split('print(f"{len(masked)} scripts')[0])
# Every occurrence of the word `git`, found by text alone, independently of any parser.
WORD = re.compile(r"(?<![\w.$-])git(?![\w-])")
parser = Parser(Language(tsb.language()))
covered_total = residual_total = 0
residual = []
for path, script in masked:
    data = script.encode("utf-8")
    spans = []
    stack = [parser.parse(data).root_node]
    while stack:
        node = stack.pop()
        if node.type == "command":
            argv = ts_argv(node)
            if argv and argv[0] is not None and sr._runs_git([w if w is not None else "\x00" for w in argv], 0):
                spans.append((node.start_byte, node.end_byte))
        stack.extend(node.children)
    for m in WORD.finditer(script):
        at = len(script[: m.start()].encode("utf-8"))
        if any(a <= at < b for a, b in spans):
            covered_total += 1
        else:
            residual_total += 1
            line_start = script.rfind("\n", 0, m.start()) + 1
            line_end = script.find("\n", m.start())
            residual.append((path, script[line_start: line_end if line_end != -1 else None].strip()))
print("scripts", len(masked), "git words", covered_total + residual_total, "inside an oracle command", covered_total, "elsewhere", residual_total)
for path, line in residual:
    print(f"  {path}: {line[:150]}")
````

### `audit_docs.py`

Re-runs `docs.py`'s reading over the frozen subject's tracked files. It records each
file that raised, and each corpus file with a BOM or a CR. SHA-256
`87328a813624da41…`. Output: 672 tracked files, 27 with shell surfaces, no BOM, no
CR, and 19 files that raised, each `shebang=False archive=True`.

````text
import sys

sys.path.insert(0, "/repo")
from tools import shell_reader as sr

files = open("/frozen/files.txt").read().split()
raised, corpus, bom, cr = [], [], [], []
for name in files:
    raw = open(f"/repo/{name}", "rb").read()
    try:
        found = sr.shell_lines(name, raw.decode("utf-8").split("\n"))
    except Exception as exc:
        raised.append((name, type(exc).__name__, raw[:2]))
        continue
    if found:
        corpus.append(name)
        bom += [name] if raw.startswith(b"\xef\xbb\xbf") else []
        cr += [name] if b"\r" in raw else []
print("tracked files:", len(files), "files with shell surfaces:", len(corpus))
print("corpus files with a BOM:", bom, "with a CR:", cr)
print("files that raised:", len(raised))
for name, kind, magic in raised:
    archive = magic in (b"\x1f\x8b", b"PK") or name.endswith(".tar")
    print(f"  {kind} {name} shebang={magic == b'#!'} archive={archive}")
````

## Spike scripts

These scripts are evaluation tooling, not repository code. Each is given with its
SHA-256 and the role it played. `gate.py` and `crash_doc.py` load `spike.py`.

Each block holds the script's exact bytes, fenced as `text` so that no formatter
rewrites them; `tests/test_shell_parser_dependency.py` checks each block against its
SHA-256. An earlier revision fenced them as Python, and the repository's formatter
reflowed them, so their bytes no longer matched their digests (Codex on #394).

### `evaluate314.py`

The two adapters, tree-sitter-bash and mvdan/sh 3.14.1, over shell_reader's policy, and the run of the reader's suite. SHA-256 `ffb69eeae78604e3…`.

````text
"""Evaluate two shell parsers as the structure behind shell_reader's own policy.

Each adapter turns shell text into the argument lists of the commands it executes,
the commands whose word is dynamic, the constructs it could not parse, and the
here-document bodies a shell reads. The policy is shell_reader's: `_runs_git` on each
argument list, recursing into `sh -c`, `eval` and the like through `runs_git`, which
is replaced by the adapter's. The shell reader's own suite then measures each.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from dataclasses import dataclass, field

sys.path.insert(0, "/repo")
from tools import shell_reader as sr  # noqa: E402

DYNAMIC = None


@dataclass
class Analysis:
    commands: list[list[str | None]] = field(default_factory=list)
    stdin_bodies: list[tuple[list[str | None], str]] = field(default_factory=list)
    unsupported: list[str] = field(default_factory=list)


def policy_runs_git(analysis: Analysis, depth: int, recurse) -> bool:
    if depth > 4:
        return False
    for argv in analysis.commands:
        if not argv or argv[0] is None:
            continue
        words = [w if w is not None else "\x00" for w in argv]
        if sr._runs_git(words, depth):
            return True
    for argv, body in analysis.stdin_bodies:
        words = [w for w in argv if w is not None]
        if words and sr._reads_stdin(words) and recurse(body, depth + 1):
            return True
    return False


# --- tree-sitter-bash -------------------------------------------------------------
import tree_sitter_bash as tsb  # noqa: E402
from tree_sitter import Language, Parser  # noqa: E402

LANG = Language(tsb.language())
KEEP: list = []


def ts_static(node) -> str | None:
    t, text = node.type, node.text.decode(errors="replace")
    if t == "word":
        out, i = [], 0
        while i < len(text):
            if text[i] == "\\" and i + 1 < len(text):
                if text[i + 1] != "\n":
                    out.append(text[i + 1])
                i += 2
            else:
                out.append(text[i])
                i += 1
        return "".join(out)
    if t == "raw_string":
        return text[1:-1]
    if t == "string":
        if any(c.type != "string_content" for c in node.named_children):
            return None
        return "".join(c.text.decode() for c in node.named_children).replace('\\"', '"').replace("\\\\", "\\").replace("\\$", "$").replace("\\`", "`")
    if t == "concatenation":
        parts = [ts_static(c) for c in node.named_children]
        return None if any(p is None for p in parts) else "".join(parts)
    if t == "number":
        return text
    return None


def ts_argv(command) -> list[str | None]:
    argv: list[str | None] = []
    for child in command.named_children:
        if child.type == "variable_assignment" or "redirect" in child.type:
            continue
        target = child.named_children[0] if child.type == "command_name" and child.named_children else child
        argv.append(ts_static(target))
    return argv


def ts_first_command(node):
    stack = [node]
    while stack:
        n = stack.pop(0)
        if n.type == "command":
            return n
        stack[:0] = list(n.named_children)
    return None


def ts_analyse(text: str) -> Analysis:
    source = text.encode()
    tree = Parser(LANG).parse(source)
    KEEP.append((source, tree))
    result = Analysis()
    stack = [tree.root_node]
    while stack:
        node = stack.pop()
        if node.is_error or node.is_missing:
            result.unsupported.append(node.type)
        if node.type == "command":
            result.commands.append(ts_argv(node))
        if node.type == "redirected_statement":
            redirect = next((c for c in node.named_children if c.type == "heredoc_redirect"), None)
            body_node = node.child_by_field_name("body")
            if redirect is not None and body_node is not None:
                first = ts_first_command(body_node)
                body = "".join(c.text.decode() for c in redirect.named_children if c.type == "heredoc_body")
                if first is not None:
                    result.stdin_bodies.append((ts_argv(first), body))
        stack.extend(node.named_children)
    return result


def ts_runs_git(text: str, depth: int = 0) -> bool:
    return policy_runs_git(ts_analyse(text), depth, ts_runs_git)


# --- mvdan/sh (shfmt --to-json) ---------------------------------------------------
SHFMT = "/spike/shfmt314"


def sh_unescape(value: str) -> str:
    out, i = [], 0
    while i < len(value):
        if value[i] == "\\" and i + 1 < len(value):
            if value[i + 1] != "\n":
                out.append(value[i + 1])
            i += 2
        else:
            out.append(value[i])
            i += 1
    return "".join(out)


def sh_dq_unescape(value: str) -> str:
    out, i = [], 0
    while i < len(value):
        if value[i] == "\\" and i + 1 < len(value) and value[i + 1] in '$`"\\\n':
            if value[i + 1] != "\n":
                out.append(value[i + 1])
            i += 2
        else:
            out.append(value[i])
            i += 1
    return "".join(out)


def sh_static(word) -> str | None:
    if not word:
        return None
    out = []
    for part in word.get("Parts") or []:
        kind = part.get("Type")
        if kind == "Lit":
            out.append(sh_unescape(part.get("Value", "")))
        elif kind == "SglQuoted":
            out.append(part.get("Value", ""))
        elif kind == "DblQuoted":
            inner = part.get("Parts") or []
            if any(p.get("Type") != "Lit" for p in inner):
                return None
            out.append("".join(sh_dq_unescape(p.get("Value", "")) for p in inner))
        else:
            return None
    return "".join(out)


def sh_first_call(node):
    stack = [node]
    while stack:
        n = stack.pop(0)
        if isinstance(n, dict):
            if n.get("Type") == "CallExpr":
                return n
            stack[:0] = [v for v in n.values() if isinstance(v, (dict, list))]
        elif isinstance(n, list):
            stack[:0] = n
    return None


def sh_hdoc_text(word) -> str:
    out = []
    for part in (word or {}).get("Parts") or []:
        if part.get("Type") == "Lit":
            out.append(part.get("Value", ""))
        else:
            out.append("_")
    return "".join(out)


def sh_analyse(text: str) -> Analysis:
    result = Analysis()
    done = subprocess.run([SHFMT, "--to-json", "-ln", "bash"], input=text, capture_output=True, text=True, check=False)
    if done.returncode != 0:
        result.unsupported.append(done.stderr.strip()[:80])
        return result
    tree = json.loads(done.stdout)

    def visit(node):
        if isinstance(node, list):
            for item in node:
                visit(item)
            return
        if not isinstance(node, dict):
            return
        kind = node.get("Type")
        if kind == "CallExpr":
            result.commands.append([sh_static(w) for w in node.get("Args") or []])
        if "Cmd" in node and node.get("Redirs"):
            for redirect in node["Redirs"]:
                if redirect.get("Hdoc") is not None:
                    first = sh_first_call(node.get("Cmd"))
                    if first is not None:
                        argv = [sh_static(w) for w in first.get("Args") or []]
                        result.stdin_bodies.append((argv, sh_hdoc_text(redirect["Hdoc"])))
        if kind == "CoprocClause":
            # coproc NAME stmt: the statement is visited as any other.
            pass
        for value in node.values():
            if isinstance(value, (dict, list)):
                visit(value)

    visit(tree)
    return result


def sh_runs_git(text: str, depth: int = 0) -> bool:
    return policy_runs_git(sh_analyse(text), depth, sh_runs_git)


ADAPTERS = {"tree-sitter-bash": ts_runs_git, "shfmt": sh_runs_git}


def run_suite(name: str) -> None:
    original = sr.runs_git
    sr.runs_git = ADAPTERS[name]  # type: ignore[assignment]
    try:
        import tests.test_owned_responsibilities as t

        loader = unittest.TestLoader()
        suite = unittest.TestSuite(
            [loader.loadTestsFromTestCase(t.ShellReaderTests), loader.loadTestsFromTestCase(t.ShellReaderUnitTests)]
        )
        result = unittest.TestResult()
        result.failfast = False
        # Count each subTest failure on its own.
        suite.run(result)
        failures = [(str(test), err.strip().splitlines()[-1][:160]) for test, err in result.failures + result.errors]
        print(f"== {name}: ran {result.testsRun} tests; {len(failures)} failing (test or subtest)")
        for test, last in failures:
            print(f"   {test.split("(")[0]} {test[test.find("(", test.find(")")):][:120]} -> {last[:60]}")
    finally:
        sr.runs_git = original  # type: ignore[assignment]


if __name__ == "__main__":
    for adapter in sys.argv[1:] or list(ADAPTERS):
        run_suite(adapter)
````

### `corpus_scripts.py`

Whole-script extraction, each workflow `run:` value through YAML, and the per-parser corpus results. SHA-256 `b5601f954a15ed72…`.

````text
"""Whole scripts, extracted properly: each workflow or action `run:` value through
YAML, so its block indentation is gone; other files as the reader's joined lines."""
import json, re, sys, yaml
sys.argv = ["x"]
exec(open("/spike/evaluate314.py").read().split("ADAPTERS = {")[0])
mask = re.compile(r"\$\{\{.*?\}\}", re.S)
docs = json.load(open("/spike/corpus.json"))
scripts = []
def runs(node, path):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "run" and isinstance(v, str):
                scripts.append((path, v))
            else:
                runs(v, path)
    elif isinstance(node, list):
        for v in node:
            runs(v, path)
for d in docs:
    p = d["path"]
    if p.startswith(".github/") and p.endswith((".yml", ".yaml")):
        runs(yaml.safe_load(open(f"/repo/{p}", encoding="utf-8")), p)
    else:
        scripts.append((p, d["text"]))
masked = [(p, mask.sub(lambda m: "_" * len(m.group(0)), s)) for p, s in scripts]
print(f"{len(masked)} scripts from {len({p for p, _ in masked})} files")
for name, analyse in (("tree-sitter-bash 0.25.1", ts_analyse), ("mvdan/sh 3.14.1", sh_analyse)):
    git = 0; problems = []; dynamic = 0
    for p, s in masked:
        a = analyse(s)
        if a.unsupported:
            problems.append(p)
        for argv in a.commands:
            if argv and argv[0] is None:
                dynamic += 1
            elif argv and sr._runs_git([w if w is not None else "\x00" for w in argv], 0):
                git += 1
    print(f"{name}: git commands {git}; scripts with a parse problem {len(problems)} {sorted(set(problems))}; dynamic command words {dynamic}")
````

### `diff_parsers.py`

The per-script differences between the two parsers. SHA-256 `480dcaf0fa826d93…`.

````text
import json, re, sys, yaml
sys.argv = ["x"]
exec(open("/spike/corpus_scripts.py").read().split('print(f"{len(masked)} scripts')[0])
def gits(analyse, s):
    out = []
    for argv in analyse(s).commands:
        if argv and argv[0] is not None and sr._runs_git([w if w is not None else "\x00" for w in argv], 0):
            out.append(" ".join(w if w is not None else "<dyn>" for w in argv)[:70])
    return out
for p, s in masked:
    a, b = gits(ts_analyse, s), gits(sh_analyse, s)
    if sorted(a) != sorted(b):
        print(p, "\n  tree-sitter only:", sorted(set(a) - set(b)), "\n  mvdan/sh only:", sorted(set(b) - set(a)))
        print("  counts", len(a), len(b))
````

### `oracle.py`

The 76-entry oracle of Git commands. SHA-256 `aae47ef9efc4942b…`.

````text
import json, re, sys, yaml
sys.argv = ["x"]
exec(open("/spike/corpus_scripts.py").read().split('print(f"{len(masked)} scripts')[0])
oracle = []
for p, s in masked:
    for argv in ts_analyse(s).commands:
        if argv and argv[0] is not None and sr._runs_git([w if w is not None else "\x00" for w in argv], 0):
            oracle.append({"path": p, "argv": argv})
json.dump(oracle, open("/spike/oracle.json", "w"), indent=0)
from collections import Counter
for p, n in sorted(Counter(o["path"] for o in oracle).items()):
    print(f"{n:3} {p}")
print("total", len(oracle))
````

### `docs.py`

The 27-document corpus at the frozen subject. SHA-256 `1be5a431d9a94d79…`.

````text
import hashlib, json, subprocess, sys
sys.path.insert(0, "/repo")
from tools import shell_reader as sr
files = subprocess.run(["git", "-C", "/repo", "ls-files"], capture_output=True, text=True, check=True).stdout.split()
out = []
for name in files:
    try:
        lines = open(f"/repo/{name}", encoding="utf-8").read().split("\n")
        found = sr.shell_lines(name, lines)
    except Exception:
        continue
    if found:
        numbers = sorted(found)
        text = "\n".join(found[n][0] for n in numbers)
        out.append({"path": name, "lines": numbers, "text": text, "sha256": hashlib.sha256(text.encode()).hexdigest()})
json.dump(out, open("/spike/corpus.json", "w"), indent=1)
print(len(out), "documents")
````

### `worker.py`

The bounded parser worker. SHA-256 `6487d0c626e07593…`.

````text
"""Parser worker: reads a JSON list of scripts on stdin, writes one analysis per script."""
import json, os, signal, sys
exec(open("/spike/evaluate314.py").read().split("ADAPTERS = {")[0])
scripts = json.load(sys.stdin)
if os.environ.get("CRASH"):
    os.kill(os.getpid(), signal.SIGSEGV)
out = []
for s in scripts:
    a = ts_analyse(s)
    out.append({"commands": a.commands, "unsupported": a.unsupported, "stdin": [[argv, body] for argv, body in a.stdin_bodies]})
json.dump(out, sys.stdout)
````

### `parent.py`

The worker's timing and its crash handling, against in-process parsing. SHA-256 `1d062b85079dd122…`.

````text
import json, os, re, subprocess, sys, time, yaml
exec(open("/spike/corpus_scripts.py").read().split('print(f"{len(masked)} scripts')[0])
batch = [s for _, s in masked]
for crash in ("", "1"):
    started = time.perf_counter()
    env = dict(os.environ, CRASH=crash)
    try:
        done = subprocess.run([sys.executable, "/spike/worker.py"], input=json.dumps(batch), capture_output=True, text=True, timeout=60, env=env)
        if done.returncode != 0:
            verdict = f"UNKNOWN for all {len(batch)} scripts: worker exited {done.returncode}"
        else:
            result = json.loads(done.stdout)
            verdict = f"{len(result)} analyses"
    except subprocess.TimeoutExpired:
        verdict = "UNKNOWN: worker timed out"
    elapsed = time.perf_counter() - started
    print(f"crash={bool(crash)}: {verdict}; {elapsed:.2f}s for the whole batch")
started = time.perf_counter()
for s in batch:
    ts_analyse(s)
print(f"in-process: {time.perf_counter() - started:.2f}s for the whole batch")
````

### `spike.py`

The first spike, which gate.py and crash_doc.py load. SHA-256 `cf8b602985d031e7…`.

````text
"""Spike: tree-sitter-bash for structure, shell_reader's own argv policy for meaning.

Not repository code. Compares the current ad-hoc reader with a parser-backed reader
on a corpus of hard cases from #369's reviews, and scans the repository's tracked
shell surfaces for parse errors and dynamic command words.
"""

from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass, field

import tree_sitter_bash as tsb
from tree_sitter import Language, Node, Parser

sys.path.insert(0, "/repo")
from tools import shell_reader as sr  # noqa: E402

LANG = Language(tsb.language())
PARSER = Parser(LANG)
TREES: list = []
DYNAMIC = "\x00dynamic"


@dataclass
class ShellAnalysis:
    runs_git: bool = False
    dynamic_commands: list[str] = field(default_factory=list)
    unsupported: list[str] = field(default_factory=list)

    @property
    def verdict(self) -> str:
        if self.runs_git:
            return "GIT"
        if self.unsupported or self.dynamic_commands:
            return "UNKNOWN"
        return "NONE"


def static(node: Node) -> str | None:
    """A word's text as the shell passes it, if no expansion can change it."""
    t = node.type
    text = node.text.decode(errors="replace")
    if t == "word":
        out, i = [], 0
        while i < len(text):
            if text[i] == "\\" and i + 1 < len(text):
                out.append(text[i + 1])
                i += 2
            else:
                out.append(text[i])
                i += 1
        return "".join(out)
    if t == "raw_string":
        return text[1:-1]
    if t == "string":
        if any(c.type not in ("string_content",) for c in node.named_children):
            return None
        return "".join(c.text.decode() for c in node.named_children)
    if t == "ansi_c_string":
        return None
    if t == "concatenation":
        parts = [static(c) for c in node.named_children]
        return None if any(p is None for p in parts) else "".join(parts)  # type: ignore[arg-type]
    if t == "number":
        return text
    return None


def analyse(text: str, depth: int = 0, result: ShellAnalysis | None = None) -> ShellAnalysis:
    result = result or ShellAnalysis()
    if depth > 4:
        result.unsupported.append("depth")
        return result
    # A parser per analysis: a nested parse with a shared parser crashed the binding.
    source = text.encode()
    tree = Parser(LANG).parse(source)
    TREES.append((source, tree))
    _walk(tree.root_node, depth, result)
    return result


def _walk(node: Node, depth: int, result: ShellAnalysis) -> None:
    if node.is_error or node.is_missing:
        result.unsupported.append(f"{node.type}: {node.text.decode(errors='replace')[:40]!r}")
    if node.type == "command":
        _command(node, depth, result)
    if node.type == "redirected_statement":
        _heredocs(node, depth, result)
    for child in node.named_children:
        _walk(child, depth, result)


def _argv(command: Node) -> list[str]:
    argv: list[str] = []
    for child in command.named_children:
        if child.type == "variable_assignment" or child.type.endswith("redirect"):
            continue
        target = child.named_children[0] if child.type == "command_name" else child
        word = static(target)
        argv.append(DYNAMIC if word is None else word)
    return argv


def _command(command: Node, depth: int, result: ShellAnalysis) -> None:
    argv = _argv(command)
    if argv and argv[0] == DYNAMIC:
        result.dynamic_commands.append(command.text.decode(errors="replace")[:60])
        return
    if any(word == DYNAMIC for word in argv) and argv and sr._command_name(argv[0]) in {"eval", *sr._SHELLS}:
        result.dynamic_commands.append(command.text.decode(errors="replace")[:60])
    # The policy is shell_reader's: wrappers, shells' -c, eval, coproc. Its
    # recursion into a command string re-enters this parser-backed reader.
    if sr._runs_git([w if w != DYNAMIC else "_" for w in argv], depth):
        result.runs_git = True


def _heredocs(statement: Node, depth: int, result: ShellAnalysis) -> None:
    body = next((c for c in statement.named_children if c.type == "heredoc_redirect"), None)
    commands = [c for c in statement.named_children if c.type == "command"]
    if body is None or not commands:
        return
    text = "".join(c.text.decode() for c in body.named_children if c.type == "heredoc_body")
    argv = _argv(commands[0])
    if argv and argv[0] != DYNAMIC and sr._reads_stdin(argv):
        analyse(text, depth + 1, result)


def ts_runs_git(text: str, depth: int = 0) -> bool:
    return analyse(text, depth).runs_git


# The parser-backed reader replaces the text-level entry point that the argv policy
# recurses into.
_ADHOC = sr.runs_git
sr.runs_git = ts_runs_git  # type: ignore[assignment]

CORPUS: list[tuple[str, bool]] = [
    ("git status", True), ("sudo git status", True), ("x=1 git status", True),
    ("echo $(git status)", True), ("echo `git status`", True),
    ("echo '`git status`'", False), ("echo \\`git status\\`", False),
    ('echo "\\`git status\\`"', False), ("echo '$(git status)'", False),
    ('echo "$(git status)"', True), ("eval 'git status'", True), ("eval 'echo git'", False),
    ("x=`date` git status", True), ("x=a`date`b git status", True), ("`date` git", False),
    ("echo `date` git", False), ("echo 'see ` lonely' ; x=`git status`", True),
    ("echo 'a\\' ; x=`git status`", True), ("echo \"it's\" ; x=`git status`", True),
    ("echo `echo \\`git status\\``", True),
    ("echo 'abc\ndef`git status`ghi'", False), ("echo 'a\nb; git status'", False),
    ('echo "a\n; git gc"', False), ("echo a\ngit status", True), ("x=1 \\\ngit status", True),
    ("coproc git status", True), ("coproc JOB { git fetch; }", True), ("coproc JOB git fetch", False),
    ("{ git gc; }", True), ("( git gc )", True), ("if true; then git pull; fi", True),
    ("a | git log", True), ("a && git log || b", True), ("! git diff", True),
    ("2>/dev/null git fetch", True), (">out git status", True), ("cat <(git log)", True),
    ("time git status", True), ("exec git gc", True), ("sh -c 'git status'", True),
    ("bash -c \"echo; git fetch\"", True), ("env -S 'git status'", True),
    ("flock /tmp/l git gc", True), ("timeout 5 git fetch", True), ("nice -n 5 git gc", True),
    ("sudo -u git echo ok", False), ("chrt -f 99 grep git", False),
    ("echo git status", False), ("grep git file", False), ("# git status", False),
    ("echo 'git status'", False), ("case x in y) git gc;; esac", True),
    ("f() { git log; }", True), ("[[ -n $(git status) ]]", True),
    ("bash <<EOF\n\"git\" status\nEOF", True), ("cat <<EOF\ngit status\nEOF", False),
    ("bash 2>&1 <<EOF\ngit status\nEOF", True), ("( bash ) <<EOF\ngit log\nEOF", True),
    ("{ cat; } <<EOF\ngit gc\nEOF", False), ("bash 0<<EOF\ngit fetch\nEOF", True),
    ("$GIT status", False), ("cmd=git; $cmd status", False),
]


def compare() -> None:
    rows = []
    for text, expected in CORPUS:
        adhoc = _ADHOC(text)
        a = analyse(text)
        rows.append((text, expected, adhoc, a.runs_git, a.verdict))
    wrong_adhoc = [r for r in rows if r[2] != r[1]]
    wrong_ts = [r for r in rows if r[3] != r[1]]
    print(f"corpus {len(rows)}: ad-hoc wrong {len(wrong_adhoc)}, parser-backed wrong {len(wrong_ts)}")
    for text, expected, adhoc, ts, verdict in rows:
        if adhoc != expected or ts != expected or verdict == "UNKNOWN":
            print(f"  expected={expected!s:5} adhoc={adhoc!s:5} parser={ts!s:5} {verdict:7} {text!r}")


def scan() -> None:
    files = subprocess.run(["git", "-C", "/repo", "ls-files"], capture_output=True, text=True, check=True).stdout.split()
    texts = []
    for name in files:
        try:
            lines = open(f"/repo/{name}", encoding="utf-8").read().split("\n")
        except (UnicodeDecodeError, IsADirectoryError, FileNotFoundError):
            continue
        try:
            found = sr.shell_lines(name, lines)
        except Exception:  # noqa: BLE001
            continue
        for number, (text, *_rest) in found.items():
            texts.append((name, number, text))
    started = time.perf_counter()
    disagree, unknown, errors = [], [], 0
    for name, number, text in texts:
        a = analyse(text)
        adhoc = _ADHOC(text)
        if a.unsupported:
            errors += 1
        if a.verdict == "UNKNOWN":
            unknown.append((name, number, text, a.dynamic_commands, a.unsupported[:1]))
        if adhoc != a.runs_git:
            disagree.append((name, number, text, adhoc, a.runs_git))
    elapsed = time.perf_counter() - started
    print(f"repo surfaces: {len(texts)} shell texts in {len({t[0] for t in texts})} files, parsed in {elapsed:.2f}s")
    print(f"  parse errors: {errors}; UNKNOWN (dynamic or unparsed): {len(unknown)}; ad-hoc vs parser disagree: {len(disagree)}")
    for row in unknown[:25]:
        print("  UNKNOWN", row[0], row[1], repr(row[2][:70]), row[3][:1], row[4])
    for row in disagree[:25]:
        print("  DIFF", row[0], row[1], repr(row[2][:70]), "adhoc", row[3], "parser", row[4])


if __name__ == "__main__":
    compare()
    scan()


def scan_documents() -> None:
    """Each file's shell lines, joined in order, parsed as one script: a run block or
    a RUN instruction keeps its continuation lines together."""
    files = subprocess.run(["git", "-C", "/repo", "ls-files"], capture_output=True, text=True, check=True).stdout.split()
    docs = []
    for name in files:
        try:
            lines = open(f"/repo/{name}", encoding="utf-8").read().split("\n")
            found = sr.shell_lines(name, lines)
        except Exception:  # noqa: BLE001
            continue
        if found:
            docs.append((name, "\n".join(found[n][0] for n in sorted(found))))
    errors, dynamic = [], []
    adhoc_git = parser_git = 0
    for name, text in docs:
        a = analyse(text)
        if a.unsupported:
            errors.append((name, a.unsupported[:2]))
        if a.dynamic_commands:
            dynamic.append((name, a.dynamic_commands[:3]))
        adhoc_git += _ADHOC(text)
        parser_git += a.runs_git
    print(f"documents: {len(docs)}; with a parse error: {len(errors)}; with a dynamic command word: {len(dynamic)}")
    print(f"  documents read as running Git: ad-hoc {adhoc_git}, parser {parser_git}")
    for row in errors:
        print("  ERROR", row)
    for row in dynamic:
        print("  DYNAMIC", row)


if __name__ == "__main__" and "--documents" in sys.argv:
    scan_documents()
````

### `gate.py`

The reproducer that segfaults with tree-sitter 0.26.0 and passes with 0.25.2. SHA-256 `167f850f7c9cb297…`.

````text
import re, subprocess, sys, yaml
exec(open("/spike/spike.py").read().split("CORPUS: list")[0])
reg = yaml.safe_load(open("/repo/policy/owned-responsibilities.yaml"))
patterns = [re.compile(s["pattern"]) for r in reg["responsibilities"] if r["id"] == "trusted-execution" for s in r.get("signatures") or [] if s.get("pattern") and s.get("id") == "git-execution"]
files = subprocess.run(["git", "-C", "/repo", "ls-files"], capture_output=True, text=True, check=True).stdout.split()
total = net = reader = neither = 0
missed = []
for name in files:
    try:
        lines = open(f"/repo/{name}", encoding="utf-8").read().split("\n")
        found = sr.shell_lines(name, lines)
    except Exception:
        continue
    if not found:
        continue
    numbers = sorted(found)
    source = "\n".join(found[n][0] for n in numbers).encode()
    tree = Parser(LANG).parse(source)
    # Collect first, with no parse in between: a nested parse during a walk crashed
    # the binding.
    collected = []
    stack = [tree.root_node]
    while stack:
        node = stack.pop()
        if node.type == "command":
            collected.append((node.start_point.row, _argv(node)))
        stack.extend(node.named_children)
    for row, argv in collected:
        if argv and argv[0] != DYNAMIC and sr._runs_git([w if w != DYNAMIC else "_" for w in argv], 0):
            original = numbers[row] if row < len(numbers) else None
            text = lines[original - 1] if original else ""
            total += 1
            by_net = any(p.search(text) for p in patterns)
            by_reader = _ADHOC(found[original][0]) if original else False
            net += by_net
            reader += by_reader
            if not (by_net or by_reader):
                neither += 1
                missed.append((name, original, text.strip()[:100]))
print(f"git commands the parser finds: {total}; caught by the line net: {net}; by the reader: {reader}; by neither: {neither}")
for m in missed:
    print("  MISSED", m)
````

### `crash_doc.py`

A single-document check, which does not reproduce the crash. SHA-256 `0d3c1f0b0c68454f…`.

````text
import json, sys, faulthandler
faulthandler.enable()
exec(open("/spike/spike.py").read().split("CORPUS: list")[0])
docs = json.load(open("/spike/corpus.json"))
selected = [d for d in docs if not sys.argv[1:] or d["path"] == sys.argv[1]]
for d in selected:
    print("DOC", d["path"], flush=True)
    source = d["text"].encode()
    tree = Parser(LANG).parse(source)
    stack = [tree.root_node]
    while stack:
        node = stack.pop()
        if node.type == "command":
            _argv(node)
        stack.extend(node.named_children)
print("ok")
````
