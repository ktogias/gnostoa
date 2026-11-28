---
type: Decision
title: Run targeted mutants from one owner, with tables that survive reformatting
description: "Slice 1 of replacing about twenty hand-maintained, per-PR mutation scripts with one owner, tools/mutation.py (knowledge mutants): delivers the mutant table schema, AST/token anchor engine, and --check gate, while mutant execution (run, tests/mutants, tests/test_mutant_tables.py) is deferred to subsequent slices."
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

1. **One owner, `tools/mutation.py`, exposed as `knowledge mutants`.** Adding `knowledge mutants` to `tools/cli.py` invalidates the prior Decision 0035 SB2/G3 binding for tools/cli.py and requires the smallest affected G3 replay before the next OCI publication candidate. It loads a mutant table (`load_table`) and either checks it (`check()` / `knowledge mutants --check`, delivered in slice 1) or runs it (`run`, deferred to a later slice).
   - **Slice 1 (delivered):** `load_table`, `apply`, `check`, `knowledge mutants --check`, and 23 focused unit tests in `tests/test_mutation.py`. Every anchor must apply exactly once, and every mutated Python file must still compile. A mutant whose path passes through a symbolic link is `REFUSED`, and a table path with a backslash or a colon is refused when the table loads.
   - **Deferred slices (`run`, `--tree`, `tools/exact_tree.py`, `tests/mutants/*.yaml`, `tests/test_mutant_tables.py`):**
     - **Run:**
       - **The baseline comes first.** The table's tests first run unmutated, in isolated copies, as many at once as the mutants will run. Only if every copy passes does a failure say anything about a mutant. Otherwise no mutant runs, and each that applies is `NOT RUN`.
       - **One copy per mutant.** Each mutant is applied in its own isolated copy of the root, with reduced Git metadata and scrubbed environment, in parallel workers (`--jobs`), with a positive finite timeout and 16 MiB output limit.
       - **The snapshot can be an exact tree.** With `--tree <full object name>`, the snapshot will hold that Git tree written by `tools/exact_tree.py` (Decision 0131).
2. **Anchors survive reformatting.**
   - In a Python file, an anchor that parses is located by AST:
     - a single expression, matched among the file's expressions;
     - a statement or a run of consecutive statements, matched within one block.

     Whitespace, line breaks, comments and trailing commas do not matter. A decorated definition's statement includes its decorators. A matched expression's own source must parse back to the anchor's expression, so an f-string's literal fragment is no string literal.
   - An anchor that does not parse, and any non-Python file, is located by token sequence: runs of word characters and single punctuation marks, with whitespace ignored.
   - An anchor that matches nowhere is `NOT FOUND`. One that matches more than once is `AMBIGUOUS`.
   - A replacement is dedented. Its later lines keep their indentation relative to its first line, starting from the indentation of the line where the match starts. It therefore fits a reflowed file whose structure follows relative indentation, as YAML's does. It keeps the table's indentation width, not the file's.
3. **Tables are data, kept with the code they guard** (deferred to `tests/mutants/*.yaml`). Each table names:
   - its id;
   - the unittest modules that must kill its mutants;
   - for each mutant, its name, a repository-relative path, a `find` anchor and a `replace` text.
4. **A stale anchor fails at once** (deferred to `tests/test_mutant_tables.py` in `fast`, `regression` and `extended` profiles). A refactor that breaks an anchor must update the table in the same change. That is the permanent fix for the cause in #373.
5. **The scratch scripts are retired** once the runner and tables land in later slices.

## Verification

- **Slice 1 (verified):** `tests/test_mutation.py` runs 23 focused unit tests covering:
  - an anchor found after reformatting;
  - a statement run;
  - an expression;
  - a token-sequence anchor in YAML;
  - `NOT FOUND`, `AMBIGUOUS`, `INVALID`, and `REFUSED` (symlink / path traversal);
  - `load_table` schema validation;
  - `check` / `knowledge mutants --check` CLI exit codes and output.
- **Deferred verification:** runner execution (`KILLED`, `SURVIVED`, `TIMED OUT`, `OUTPUT LIMIT`, `NOT RUN`), `--tree`, `tests/mutants/*.yaml`, and `tests/test_mutant_tables.py` belong to subsequent slices.

## Consequences

- One runner to harden, instead of twenty copies.
- An anchor broken by a refactor fails in seconds where the change is made, not after a ~13-minute pipeline.
- Targeted mutants become durable guards of the rules they name, versioned and reviewed with the code.
