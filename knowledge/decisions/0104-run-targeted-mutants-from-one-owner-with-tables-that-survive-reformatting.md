---
type: Decision
title: Run targeted mutants from one owner, with tables that survive reformatting
description: Replace about twenty hand-maintained, per-PR mutation scripts with one owner, tools/mutation.py (knowledge mutants), which runs named mutant tables kept as data under tests/mutants. Python anchors are located by AST and other anchors by token sequence, so formatting cannot break them, and a fast-profile test fails as soon as any table's anchor no longer applies.
status: draft
generated:
  by: anthropic/claude-opus-5-5
  at: "2026-10-05T19:30:00Z"
sources:
  - id: incident
    resource: https://github.com/ktogias/gnostoa/issues/373
    title: Cheap static checks read only after candidate preparation cost ~66 min (RCA and permanent steps)
  - id: admission
    resource: https://github.com/ktogias/gnostoa/issues/373#issuecomment-6001439049
    title: Owner admission of S6 and S7 (2026-10-05)
  - id: lineage
    resource: https://github.com/ktogias/gnostoa/issues/373#issuecomment-6001470449
    title: S6 prior-art checkpoint and lineage table
  - id: broad-mutation
    resource: https://github.com/ktogias/gnostoa/issues/224
    title: Evaluate bounded repeatable mutation verification for qualification
  - id: cosmic-ray
    resource: https://github.com/sixty-north/cosmic-ray
    title: cosmic-ray 8.7.0 (MIT); operator-based mutation, left to #224
  - id: mutmut
    resource: https://github.com/boxed/mutmut
    title: mutmut 3.8.0 (BSD-3-Clause); operator-based mutation needing pytest, left to #224
x-project-knowledge:
  id: kit.decision.0104.run-targeted-mutants-from-one-owner-with-tables-that-survive-reformatting
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /decisions/0103-run-the-regression-and-smoke-suites-beside-extended-behind-the-regression-gate.md
---

# Run targeted mutants from one owner, with tables that survive reformatting

## Context

The agent's verification of a candidate kills a set of **targeted rule mutants**. Each is a named code change that a named test must kill, such as "a link is followed" or "the registry is read twice". Those mutants lived in about twenty hand-maintained scripts in the agent's scratchpad, from 2026-10-03 to 2026-10-05. Together the scripts held about 526 mutants, each script had its own copy of the runner, and every anchor was literal text.

On #369, `ruff --fix` and ordinary refactors silently changed anchored text. Five publication runs were refused only at the end of a ~13-minute pipeline, about 66 minutes in all (source `incident`). The owner admitted this fix on 2026-10-05 as a priority (source `admission`).

## Prior-art and reuse disposition

| Need | Candidate | Disposition |
|---|---|---|
| Broad, operator-based mutation | `cosmic-ray` (MIT), `mutmut` (BSD-3-Clause, needs pytest), `mutatest` (MIT, unmaintained since 2022) | **not used here**. None of them runs named, hand-written targeted mutants; broad mutation is #224's scope |
| A runner: isolated copy, named tests, timeout, parallel workers, KILLED / SURVIVED / NOT FOUND | the twenty scratch runners | **factored** into one owner |
| Locating a mutant | literal before/after text | **superseded**: Python anchors are matched by AST, other files by token sequence |
| Mutant definitions | Python dicts inside each script | **superseded** by data tables kept with the code |
| Loading a table | `tools/knowledge_common.load_yaml` | **consumed** |

## Decision

1. **One owner, `tools/mutation.py`, exposed as `knowledge mutants`.** It loads a mutant table and either checks it (`--check`) or runs it.
   - **Check:** every anchor must apply exactly once, and every mutated Python file must still compile.
   - **Run:**
     - **The baseline comes first.** The table's tests first run unmutated, in isolated copies, as many at once as the mutants will run. Only if every copy passes does a failure say anything about a mutant. Otherwise no mutant runs, and each that applies is `NOT RUN`.
       - The baseline ends before any mutant starts.
       - It runs as wide as the mutants because a suite that cannot share the machine with itself, holding a fixed port or lock, would otherwise "kill" mutants through contention.
     - **One copy per mutant.** Each mutant is applied in its own isolated copy of the root.
     - **The copy is faithful, and its Git stays in it.** Every copy is taken from one snapshot of the root, made when the run starts. It keeps the repository's own `.git` directory, so tests that read Git see the same history and tracked files as in place. Its configuration keeps only the repository's format: `[core]`'s format keys and `[extensions]`. Its hooks are removed. A work tree, an include, a filter, a hook or any other program the repository configured therefore neither routes Git elsewhere nor runs. It leaves out caches, and any `.git` *file*, because such a file points at metadata other worktrees share. A `commondir`, which shares another repository's directory, refuses the copy.
     - **No path through a link.** A mutant whose path passes through a symbolic link is `REFUSED`, by the check and by the run, because writing through it would change a file outside the copy. A table path with a backslash or a colon is refused when the table loads, because a path checked as POSIX would be read natively elsewhere.
     - **What the tests do stays in the copy.**
       - A copy holding a link that resolves outside it is refused, and the baseline reports why. The link is resolved in full, through any links it passes.
       - Output beyond 16 MiB stops the tests, as a timeout does. It is measured after every wait, so tests that pass the limit and exit within one poll are caught too.
     - **How the tests run.** They run with a scrubbed environment, in parallel workers (`--jobs`). They have a positive, finite timeout that ends their whole process group.
     - **The result** is `KILLED`, `SURVIVED`, `NOT RUN`, `REFUSED`, `NOT FOUND`, `AMBIGUOUS` or `INVALID`. The command exits non-zero unless every mutant is killed.
2. **Anchors survive reformatting.**
   - In a Python file, an anchor that parses is located by AST:
     - a single expression, matched among the file's expressions;
     - a statement or a run of consecutive statements, matched within one block.

     Whitespace, line breaks, comments and trailing commas do not matter. A decorated definition's statement includes its decorators.
   - An anchor that does not parse, and any non-Python file, is located by token sequence: runs of word characters and single punctuation marks, with whitespace ignored.
   - An anchor that matches nowhere is `NOT FOUND`. One that matches more than once is `AMBIGUOUS`.
   - A replacement is dedented. Its later lines keep their indentation relative to its first line, starting from the indentation of the line where the match starts. It therefore fits a reflowed file whose structure follows relative indentation, as YAML's does. It keeps the table's indentation width, not the file's.
3. **Tables are data, kept with the code they guard**, as `tests/mutants/*.yaml`. Each table names:
   - its id;
   - the unittest modules that must kill its mutants;
   - for each mutant, its name, a repository-relative path, a `find` anchor and a `replace` text.
4. **A stale anchor fails at once.** `tests/test_mutant_tables.py` runs the check over every table, so it runs in the `fast`, `regression` and `extended` profiles, in the git hooks and in provider CI. A refactor that breaks an anchor must update the table in the same change. That is the permanent fix for the cause in #373.
5. **The scratch scripts are retired.**
   - The first table, `tests/mutants/verification-workflow.yaml`, holds the nine mutants that guard Decision 0103's gate.
   - #369's mutants move into a table with #369.
   - Mutant sets for already-merged work are not migrated: their anchors have drifted, and the merged work is guarded by its tests.

   After #369 lands, the responsibility registry it adds lists this owner.

## Verification

- **Before the owner exists,** its tests fail. They cover:
  - an anchor found after reformatting;
  - a statement run;
  - an expression;
  - a token-sequence anchor in YAML;
  - `NOT FOUND`, `AMBIGUOUS` and `INVALID`;
  - `KILLED` and `SURVIVED` on a small fixture project;
  - a timeout;
  - parallel workers;
  - table validation.
- **After the change,** those tests pass. The verification-workflow table checks clean, and all nine of its mutants are reported killed.
- **Review of `8ad4b4b`, round 2.** Codex and CodeAnt found seven defects in the first version:
  - test failures were credited without a clean baseline, so a misspelled or unimportable test module killed every mutant;
  - a path through a symbolic link was written through, to a file outside the copy;
  - a timeout ended the test runner but not its children;
  - a timeout of zero or less was accepted;
  - a decorated definition was matched without its decorators;
  - a token-sequence replacement doubled the document's indentation.

  Each has a test that failed first, on the unchanged runner, and a mutant in `tests/mutants/mutation.yaml`.
- **Review of `d887443`, round 3.**
  - **Codex: the baseline overlapped the mutants.** With more than one worker, a mutant started before the baseline ended. Tests that failed first:
    - the baseline must end before any mutant starts;
    - it must run as wide as the mutants;
    - no mutant may run after it fails.

    A characterization shows the concrete harm: a suite holding an exclusive lock "killed" two mutants it cannot detect, in two of three runs.
  - **Round 4, on `99bfe52`.**
    - Codex and CodeAnt: output past the limit was not counted when the tests exited within one poll. A test that failed first now catches it.
    - Codacy's Semgrep: the resolved `git` call in a test fixture gets the repository's `nosemgrep` pragma.
  - **Round 8, on `aedb94f`, rebased onto `main` after #375 merged.**
    - Codex, CodeRabbit: a multi-line replacement took the file's first line ending, not the matched line's.
    - CodeAnt: a `.git/hooks` that is a symbolic link survived, because `rmtree` refuses a link and its error was ignored.
    - Both have a test that failed first. The hooks test first passed for the wrong reason, asserting after its scratch directory was gone. It was repaired before the fix.
    - The copied configuration is replaced by a new file, never written through a link.
  - **Round 7, on `d56d583`.**
    - **Codex P1: copies of a live root.** The baseline and the mutants each copied the live root, so an edit during the run gave them different subjects. Every copy is now taken from one snapshot.
    - **Codex P2: execution through the copied metadata.** A filter or a hook ran from the copied `.git`. The copy's configuration is now reduced to the repository's format, and its hooks removed. This also covers round 6's routes, the work tree and the include, so they are no longer refused but dropped.
    - **CodeAnt: CRLF files rewritten as LF.** A CRLF file was rewritten as LF, which a byte-sensitive test detects. Line endings are now kept.
    - **Found while fixing that.** Anchors split lines with `str.splitlines`, which breaks at a form feed where Python does not, so a matched span could fall on the wrong line. Lines are now split as Python counts them.

    Each has a test that failed first. One test fixture failed for the wrong reason at first: in Git's configuration `;` starts a comment, so the filter command was cut short. It was repaired before the implementation.
  - **Round 6, on `4068c40`.**
    - Codex: the copied `.git` could route Git outside the copy, through a `core.worktree`, an `include`, a `config.worktree` or a `commondir`. On `4068c40` a test's `git clean` removed a file outside the copy. Such a copy is now refused. A test failed first.
    - CodeAnt: a file that is not UTF-8 aborted `check` and `run`. It is now reported as `NOT FOUND`. A test failed first.
    - Two boundaries are stated: the runner does not sandbox the tests, which run as the caller, so the publication flow runs it with the root mounted read-only; and it runs on POSIX only. The owner confirmed the first on 2026-10-06. A sandbox for the tests would be a separate Work Item.
  - **Round 5, on `2c156a9`.**
    - CodeAnt: a missing `--root` crashed with a traceback, and a failed copy escaped `run`. Now the first is a usage error, exit 2, and the second credits nothing (`NOT RUN`). Each has a test that failed first.
    - SonarCloud: the module-name pattern uses `\w` under `re.ASCII`, and an exception test has one call that can raise.
    - Two bounds are stated rather than changed: a token anchor can match a comment, which fails loudly, and the output limit is measured once per poll.
  - **CodeAnt: three ways out of the copy.** Windows-style table paths, unbounded test output, and links that resolve outside the copy. An absolute link let a test write outside on `d887443`. Each has a test that failed first.
- **The nine round-1 kills were not evidence.** The new baseline then failed on the verification-workflow table itself. Two `tests.test_tools` tests read Git metadata (`git ls-files`, and the tracked-file scope), and a copy without `.git` fails them. So on `8ad4b4b` every one of the nine mutants was "killed" by those two errors, not by its own change.
  - The copy now keeps the repository's `.git` directory, with a test that failed first.
  - With that copy, all nine are killed for their own reasons.
- **The scratch runners this owner replaces had the same defect.** They also copied without `.git`. Each of their test sets was run unmutated in such a copy, on its current subject:
  - #371's set failed, the same two errors, so the nine mutants of Decision 0103's gate were never evidenced before this change;
  - every other set passed: #356 and the review-admission sets, #362/#364's credential sets, `github_rest`, and #368's set.

## Consequences

- One runner to harden, instead of twenty copies.
- An anchor broken by a refactor fails in seconds where the change is made, not after a ~13-minute pipeline.
- Targeted mutants become durable guards of the rules they name, versioned and reviewed with the code.
