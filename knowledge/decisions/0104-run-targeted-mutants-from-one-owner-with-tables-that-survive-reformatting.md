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
   - **Run:** each mutant is applied in an isolated copy of the root, without `.git` or caches. The table's tests run with a scrubbed environment and a timeout, in parallel workers (`--jobs`). The result is reported as `KILLED`, `SURVIVED`, `NOT FOUND`, `AMBIGUOUS` or `INVALID`. The command exits non-zero unless every mutant is killed.
2. **Anchors survive reformatting.**
   - In a Python file, an anchor that parses is located by AST:
     - a single expression, matched among the file's expressions;
     - a statement or a run of consecutive statements, matched within one block.

     Whitespace, line breaks, comments and trailing commas do not matter. A statement replacement is re-indented to the matched statement's indentation.
   - An anchor that does not parse, and any non-Python file, is located by token sequence: runs of word characters and single punctuation marks, with whitespace ignored.
   - An anchor that matches nowhere is `NOT FOUND`. One that matches more than once is `AMBIGUOUS`.
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
- **After the change,** those tests pass. The verification-workflow table checks clean, and all nine of its mutants are killed.

## Consequences

- One runner to harden, instead of twenty copies.
- An anchor broken by a refactor fails in seconds where the change is made, not after a ~13-minute pipeline.
- Targeted mutants become durable guards of the rules they name, versioned and reviewed with the code.
