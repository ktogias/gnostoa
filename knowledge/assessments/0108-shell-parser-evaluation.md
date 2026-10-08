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

## License, SBOM and notice evidence

Decision 0108's item 14 asks the dependency PR for this evidence. It comes from the
`extended` suite's quality evidence (`ci/quality_evidence.py`), run on #394's branch
rebased onto `9e45bd6`:

| Package | Version | Declared license | License file | SBOM component |
|---|---|---|---|---|
| `tree-sitter` | 0.25.2 | MIT | `LICENSE` | `pkg:pypi/tree-sitter@0.25.2` |
| `tree-sitter-bash` | 0.25.1 | MIT | `LICENSE` | `pkg:pypi/tree-sitter-bash@0.25.1` |

- **Inventories:** both rows appear in the runtime and in the development license
  inventory, and both CycloneDX SBOMs (runtime and development) list both
  components.
- **Notices:** each wheel ships its license file in its metadata, as PyYAML's and
  jsonschema's do. `THIRD_PARTY_NOTICES` covers CPython only (Decision 0037), so it
  does not change.
- **Compatibility:** MIT is compatible with Gnostoa's Apache-2.0 distribution.
  This is unlike bashlex and ShellCheck (GPLv3), which Decision 0108's item 13
  rejects.

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
- **What the dependency smoke can and cannot guard (Codex on #394).**
  - `stress_probe.py` re-parsed every command, pipeline, subshell and substitution
    of the 168 shell surfaces of this branch at `9ff6c79` during the walk, to a
    depth of 3.
    That made 14,350 parses, every tree kept alive, and nodes read after each
    nested parse. It did not crash 0.26.0 either, in three runs, nor 0.25.2.
  - So the crash needs the gate's own path, which #369's reader rebuilds and
    `main` does not have yet. The dependency smoke cannot reproduce it.
  - The guard until then is the exact pin, and the smoke's assertion of the
    installed versions.
  - **An upgrade of either package must re-run the reader over the corpus**, the
    path that crashed, before it is admitted. This covers #369's tests as well as
    the smoke.

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

## Spike scripts

These scripts are evaluation tooling, not repository code. They are retained as
native `.py` files, byte for byte as they ran, in
[`0108-shell-parser-evaluation-evidence/spike-scripts.tar.gz`](./0108-shell-parser-evaluation-evidence/spike-scripts.tar.gz)
(SHA-256 `f682e3bcc1fc12fc…`). The archive is deterministic: sorted members, no
times or owners, mode `0644`. `tests/test_shell_parser_dependency.py` checks each
member against the digest below, and the exact inventory.

They are archived rather than committed as loose `.py` files for a reason.
Repository-root Ruff covers every tracked Python file (Decision 0081), and these
scripts fail it, with 71 lint findings and 12 reformats. Making them comply would
change the bytes that produced the results. An earlier revision kept them in `text`
fences in this document; that made the code canonical only inside prose (Codex on
#394). Before that, a Python fence was reflowed by the formatter.

`gate.py` and `crash_doc.py` load `spike.py`. The scripts expect the frozen subject
at `/repo` and this directory's files at `/spike`.

| Script | SHA-256 | Role |
|---|---|---|
| `stress_probe.py` | `a34ba9077284334f…` | Interleaves nested parses with node access, without the reader's policy: each command, pipeline, subshell and substitution is parsed again during the walk, to a depth of 3, and every tree is kept alive. Output: 14,350 parses, exit 0, with both 0.25.2 and 0.26.0, three runs each. |
| `audit_oracle.py` | `94f5faf4f4aea242…` | Checks the oracle's completeness against the text alone: each occurrence of the word `git` in the 127 masked scripts lies either inside a command the oracle counted, or is listed. Output: 79 occurrences, 76 inside an oracle command, and the 3 listed above. |
| `audit_docs.py` | `87328a813624da41…` | Re-runs `docs.py`'s reading over the frozen subject's tracked files. It records each file that raised, and each corpus file with a BOM or a CR. Output: 672 tracked files, 27 with shell surfaces, no BOM, no CR, and 19 files that raised, each `shebang=False archive=True`. |
| `evaluate314.py` | `ffb69eeae78604e3…` | The two adapters, tree-sitter-bash and mvdan/sh 3.14.1, over shell_reader's policy, and the run of the reader's suite. |
| `corpus_scripts.py` | `b5601f954a15ed72…` | Whole-script extraction, each workflow `run:` value through YAML, and the per-parser corpus results. |
| `diff_parsers.py` | `480dcaf0fa826d93…` | The per-script differences between the two parsers. |
| `oracle.py` | `aae47ef9efc4942b…` | The 76-entry oracle of Git commands. |
| `docs.py` | `1be5a431d9a94d79…` | The 27-document corpus at the frozen subject. |
| `worker.py` | `6487d0c626e07593…` | The bounded parser worker. |
| `parent.py` | `1d062b85079dd122…` | The worker's timing and its crash handling, against in-process parsing. |
| `spike.py` | `cf8b602985d031e7…` | The first spike, which gate.py and crash_doc.py load. |
| `gate.py` | `167f850f7c9cb297…` | The reproducer that segfaults with tree-sitter 0.26.0 and passes with 0.25.2. |
| `crash_doc.py` | `0d3c1f0b0c68454f…` | A single-document check, which does not reproduce the crash. |
