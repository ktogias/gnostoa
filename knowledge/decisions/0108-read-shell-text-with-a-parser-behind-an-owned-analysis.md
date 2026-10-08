---
type: Decision
title: Read shell text with a parser behind an owned analysis
description: The reuse check's shell reader is rebuilt on tree-sitter-bash 0.25.1, with tree-sitter 0.25.2, behind a Gnostoa-owned ShellParser protocol and normalized analysis. It runs in one bounded worker process, gives a three-way GIT, NONE or UNKNOWN verdict, and fails closed on UNKNOWN unless an admitted exemption matches. It supersedes the tokenizer of Decision 0105, which is pending in #369 and not yet on `main`.
status: draft
generated:
  by: anthropic/claude-opus-5-5
  at: "2026-10-07T21:00:00Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/393
    title: Admit tree-sitter-bash as the shell parser dependency
  - id: owner-analysis
    resource: https://github.com/ktogias/gnostoa/pull/369#issuecomment-6045281181
    title: The owner's independent analysis of the first draft, with fourteen amendments
  - id: amended-draft
    resource: https://github.com/ktogias/gnostoa/pull/369#issuecomment-6045405977
    title: The amended draft the owner admitted on 2026-10-07
  - id: assessment
    resource: ../assessments/0108-shell-parser-evaluation.md
    title: The parser evaluation, its corpus, results, environment and reproducers
  - id: preparation-authority
    resource: ./0090-require-pre-candidate-preparation-receipts-for-non-hook-authoring.md
    title: pyproject.toml and the locks as preparation-authority surfaces
x-project-knowledge:
  id: kit.decision.0108.read-shell-text-with-a-parser-behind-an-owned-analysis
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /decisions/0090-require-pre-candidate-preparation-receipts-for-non-hook-authoring.md
---

# Read shell text with a parser behind an owned analysis

## Context

The reuse check (#369, and its Decision 0105, pending there) found Git commands in shell text with a
`shlex` tokenizer and hand-written handling of quotes, substitutions, groups and
here-documents. Each of its eight rounds after round 39 brought three to nine new
shell findings, and in rounds 46 and 47 about seven of twelve were defects the
previous round's fix had introduced. It also missed `echo "$(git status)"`
outright, since `shlex` keeps a double-quoted word whole.

On 2026-10-07 the owner chose to rebuild the reader on a real parser inside #369.
They reviewed the first draft of this Decision independently, proposed fourteen
amendments, and admitted the amended draft: «εγκρίνω τη Decision 0108» ("I approve
Decision 0108").

## Evidence

**The comparison was rerun against the current mvdan/sh, 3.14.1** (amendment 7a). This time each workflow and action `run:` value was extracted through YAML as its own script. The first spike had kept the YAML block's indentation, so a here-document's terminator was never at column 0. mvdan/sh rightly refused those scripts as unclosed here-documents, and tree-sitter silently tolerated them. Over 127 scripts from 27 files at `c8ababd`, with each `${{ … }}` masked at the same width:

| | Git commands | scripts with a parse problem | dynamic command words |
|---|---|---|---|
| tree-sitter-bash 0.25.1 (`tree-sitter` 0.25.2) | 76 | 1: `AGENTS.md`, its `<…>` placeholders | 10 |
| mvdan/sh 3.14.1 | 75 | 1: `AGENTS.md` | 7 |

**The two parsers agree on every one of the 75 real Git executions.** The one difference is `command -v git` in `AGENTS.md`. tree-sitter parsed that file partially, and the *policy* took a lookup for an execution, which is a policy false positive and now an acceptance case. mvdan/sh refused the whole file, which is UNKNOWN. So the earlier "28/30 against 25/30" is set aside as fragment-oriented, as amendment 7b says. The selection now rests on whole-script cases, bounded UNKNOWN, crash handling and integration cost.

**The tree-sitter crash** (amendment 8):
- `tree-sitter` 0.26.0 with `tree-sitter-bash` 0.25.1 segfaults deterministically in the spike's gate measurement. 0.25.2 with 0.25.1 does not, on the same inputs.
- It is not a single input. Each of the 27 documents parses alone with 0.26.0, and so does a plain sequential traversal of all of them. The crash needs the gate's interleaving of nested parses and node access in one process. Reducing it to a minimal reproducer is still open.
- The exact reproducer and environment are recorded below.
- Upstream's 5-byte `{𱡀` SIGSEGV ([tree-sitter-bash#337](https://github.com/tree-sitter/tree-sitter-bash/issues/337)) did **not** reproduce through the Python binding with either pair. That is recorded as "not reproduced", not as "safe".

**The worker boundary was measured** (amendment 9, the owner's second condition). One worker process parsed the whole batch of 127 scripts:

| | Time | A SIGSEGV in the parser |
|---|---|---|
| bounded worker | 0.51 s, almost all of it interpreter start, once per run | the worker exits `-11`; the parent records UNKNOWN for all 127 and fails closed |
| in-process | 0.05 s | the checker itself dies, with no verdict |

**mvdan/sh delivery.** The v3.14.1 release publishes the binary but no checksum file. The measured SHA-256 of `shfmt_v3.14.1_linux_amd64` is recorded below as a measurement, not as a provenance claim.

## Decision

1. **The split** : host-language extraction → `ExtractedShell` → `ShellParser` → normalized invocations → Gnostoa policy → GIT, NONE or UNKNOWN.
   - The policy never imports or names a parser object, node type or capture.
   - `ExtractedShell` holds:
     - the text;
     - its origin: path, the kind of surface, and which step or instruction;
     - its dialect;
     - a source map back to the original path, line and byte range.
   - Masking keeps newlines and width; `${{ … }}` becomes a placeholder of the same length.
   - A Docker exec form stays argument-list data. `RUN ["git", …]` is a direct invocation, and only a shell's `-c` value is parsed.
   - Make extraction follows `.ONESHELL`, recipe continuations and the selected `SHELL`. A command word that Make expansion produces is UNKNOWN.
   - Here-document bodies come from parser structure.
2. **The normalized invocation**  carries:
   - its source span;
   - its argv, each word **literal** or **dynamic**;
   - its kind: command, command or process substitution, function body, coprocess, nested shell string, or stdin script;
   - its dialect and origin;
   - any adapter problem behind an uncertainty.
3. **Dialects**:
   - Bash is supported.
   - For `sh`, dash and ash, only the subset the corpus proves; anything else is UNKNOWN.
   - ksh and zsh are UNKNOWN until an adapter for them is admitted.
   - Shebangs, Docker `SHELL`, workflow `shell:` and Make's `SHELL` set the dialect.
4. **The verdict**:
   - **GIT:** a violation.
   - **NONE:** authoritative on a shell surface.
   - **UNKNOWN:** fails closed unless an admitted exemption matches it. UNKNOWN never counts as clean.
   - **The exemption** binds the path, the span or construct identity, the UNKNOWN category, a content fingerprint, a reason, and an owner or `until`. It goes stale like debt does when the construct changes, and it is never a wildcard.
   - **Scope:** this governs Gnostoa-self's registered surfaces. The public CLI does not reject consumer repositories for dynamic shell.
5. **No second parser inside the adapter**. A grammar gap the adapter cannot handle with a tiny extraction from an already recognized node is UNKNOWN, with a fixture. The nested escaped-backtick repair proposed in the first draft is withdrawn: that case is UNKNOWN.
6. **The legacy line pattern runs in shadow mode**:
   - for shell surfaces, the parser result is authoritative;
   - the shell-oriented part of the `git-execution` pattern runs in discrepancy mode for a bounded migration window, which the Decision states;
   - it stays authoritative for the non-shell contexts it alone covers;
   - after the window, its shell-specific part is removed or narrowed.
7. **The parser**: `tree-sitter-bash` 0.25.1, paired with `tree-sitter` 0.25.2 and pinned exactly. mvdan/sh 3.14.1 is recorded as the measured reference parser, used for differential checks when the corpus grows. It is not the runtime contract: its typed-JSON enum mapping broke between versions ([mvdan/sh#1321](https://github.com/mvdan/sh/issues/1321)).
8. **Pins and smoke**:
   - Both packages are declared directly, with no `[core]` extra.
   - The dependency PR's smoke test asserts:
     - the exact versions and the language ABI;
     - every surface kind of the frozen corpus, in the current tree, parsing with no ERROR or MISSING node;
     - the runtime image.
   - #369's reader smoke asserts what needs the reader itself: every acceptance fixture, normalized output and source spans, and Python 3.11 and 3.12. The dependency PR's smoke has no normalized output to assert (cubic on #396).
   - The 0.26.0 reproducer is kept as evidence.
9. **The worker boundary**: one bounded parser worker per reuse-check run.
   - The parent owns the contract.
   - A crash, a signal, a timeout, a malformed or an oversized response is UNKNOWN for every script in the batch.
   - No path through a crash can produce NONE.
10. **Resource bounds**:
    - a maximum number of bytes per script;
    - a maximum number of scripts, and of total bytes, per run;
    - a maximum number of invocations emitted;
    - the existing nesting depth;
    - the worker's response size and timeout.

    Crossing any bound is UNKNOWN. Parse trees are walked iteratively.
11. **The acceptance corpus**. Each case declares GIT, NONE or UNKNOWN and an expected source span. It takes in every post-freeze finding:
    - `echo hi # it's⏎git status`;
    - the redirection-only here-documents: `RUN 2>&1 <<EOF`, `RUN > /dev/null <<EOF`, `RUN 0<<EOF`, and `RUN <<EOF` as the control;
    - `echo "$("git" status)"`;
    - `f() { "git" status; }; f`;
    - `cat < <("git" status)`;
    - `command -v git` as NONE, newly found;
    - the earlier backtick, assignment, exec-form, group, `eval`, `coproc`, wrapper and `-c` cases.
12. **Durable evidence**: the dependency PR carries `knowledge/assessments/0108-shell-parser-evaluation.{md,json}`, with:
    - the subject `c8ababd`;
    - the corpus identity: 27 files and 127 scripts, each with its SHA-256;
    - the 76-entry oracle, with a SHA-256;
    - each parser's results and differences;
    - the versions, platform and image;
    - the hashes of the wheels, binaries and scripts;
    - the spike scripts themselves.
13. **License wording**: bashlex and ShellCheck are rejected because GPLv3 code in the distributed or runtime dependency surface would impose obligations inconsistent with Gnostoa's intended Apache-2.0 distribution.
14. **Order**, as a hard gate:
    1. Decision 0108 and the parser choice are admitted.
    2. A separate authority-evolution dependency PR to `main`. It carries exact pins and hashes in `pyproject.toml` and both locks, license, SBOM and notice evidence, the compatibility and corpus smoke, and runtime and devcontainer rebuild evidence. The evidence does not overstate publisher provenance: `tree-sitter-bash` 0.25.1 was uploaded with Twine, not Trusted Publishing.
    3. #369 is re-parented onto it.
    4. The reader is rebuilt behind the protocol, RED-first from the corpus.
    5. The superseded machinery of Decision 0105 is retired only after the new analyzer converges.

## Consequences

- **Grammar belongs to the parser.** Quoting, substitutions, groups, functions,
  here-documents and line continuations are the parser's to read. Gnostoa keeps the
  policy: wrappers, shells' `-c`, `eval`, `coproc`, and which command reads a
  here-document.
- **Uncertainty is visible.** UNKNOWN is a stated result and fails closed. Today it
  covers two documents that run Git through a variable, which both earlier layers
  missed, and `AGENTS.md`'s placeholders.
- **The runtime image holds two more distributions,** a native extension among them.
  The pair is pinned together, and a smoke test proves its compatibility on every
  run.
- **A native crash cannot pass silently.** It ends the worker, never the checker, and
  produces UNKNOWN.
- **Decision 0105's tokenizer is superseded once #369's rebuild converges.** Until
  then the reader stays frozen at round 47.

## Alternatives not chosen

- **Continuing to harden the `shlex` reader:** the measured churn and the
  false-negative class above.
- **mvdan/sh as the runtime parser:** an equal reading of this repository's shell, but
  a Go binary to distribute, with no published checksum for v3.14.1. Its typed-JSON
  mapping also changed between versions (mvdan/sh#1321). It stays the reference parser.
- **bashlex and ShellCheck:** introducing GPLv3 code into the distributed or runtime
  dependency surface would impose obligations inconsistent with Gnostoa's intended
  Apache-2.0 distribution.
- **Parsing in-process:** a native crash would end the checker with no verdict.

## Admission and delivery

- **Admitted:** the owner admitted this Decision on 2026-10-07, together with this
  separate dependency change.
- **This change adds:** the pinned pair, its compatibility smoke test and the
  durable evaluation evidence.
- **Authority evolution:** `pyproject.toml` and the locks are preparation authority
  under Decision 0090, so the change is verified directly, not through
  `ci/prepare-candidate`.
- **The reader:** #369 rebuilds it on this foundation once this change is in `main`.
