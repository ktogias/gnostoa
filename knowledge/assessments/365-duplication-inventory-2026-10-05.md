---
type: Source
title: Duplicated responsibilities in production code on 2026-10-05, measured, with proposals
description: A measured inventory of responsibilities implemented more than once in the toolkit's production Python on protected main 4618e1b. Four independent detectors were used; the findings are grouped into families, and each family has a proposed single owner, its migration route and its priority.
status: draft
generated:
  by: anthropic/claude-opus-5-5
  at: "2026-10-05T20:00:00Z"
sources:
  - id: owner-request
    resource: https://github.com/ktogias/gnostoa/issues/373
    title: Owner request on 2026-10-05 for a deep analysis of duplication, recorded with its results and proposals
  - id: reuse-class
    resource: https://github.com/ktogias/gnostoa/issues/365
    title: Detect and prevent re-implementation of responsibilities that already have an owner
  - id: trusted-execution
    resource: https://github.com/ktogias/gnostoa/issues/368
    title: One owner for trusted authority execution (the first family consolidated)
  - id: mutation-owner
    resource: https://github.com/ktogias/gnostoa/pull/374
    title: One owner for targeted mutants (the second family consolidated)
x-project-knowledge:
  id: kit.assessment.365-duplication-inventory-2026-10-05
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0053-require-lightweight-work-item-micro-retrospection.md
    - kind: references
      target: /assessments/15-2026-10-05-problems-and-solutions-log.md
---

# Duplicated responsibilities in production code on 2026-10-05

## Purpose, provenance and claim boundary

On 2026-10-05 the owner asked for a deep analysis of the code, to find duplication
beyond the two families already being consolidated: trusted execution (#368) and
targeted mutants (#374). The owner asked for the results and proposals to be
recorded for later reflection and evaluation. This document is that record.

**Governance.** This is an owner-selected formal retrospective analysis under
[Decision 0053](../decisions/0053-require-lightweight-work-item-micro-retrospection.md),
section C. Its findings remain evidence, not admitted implementation scope. Each family
is admitted separately, through its own Work Item and Decision.

- **Subject:** production Python on protected `main` at `4618e1b`: 101 files under
  `tools/`, `ci/`, `tasks/` and `.github/`, 45,435 lines and 1,219 top-level
  functions. Tests are noted separately.
- **Claim boundary:** the detectors find code that is the *same shape*, has the
  *same name*, or matches one of a *fixed set of line patterns*. Every count below
  names its detector, because they measure different things:
  - Detector C counts the modules with a line matching one of its 15 patterns, in
    `responsibility_signatures.py`, whatever shape surrounds that line. A
    responsibility it has no pattern for, such as F5's policy loading, has no C count.
  - Detectors A and B count helpers that share a name or a body.
  - Where both count the same responsibility, as for strict JSON, the A or B count is
    the mechanically mergeable part. Neither count is a complete inventory of a
    responsibility.
- **What no detector sees:** a responsibility implemented twice in shapes that share
  no name, no body and no line pattern. #365 records why the review analyzers missed
  such cases.
- **Status of a family:** each one listed here is a candidate. Its owner is chosen
  when a Work Item admits it.

## Method

| Detector | What it finds | Result |
|---|---|---|
| A. Same helper name | top-level functions with one name in two or more modules, compared by normalized AST | 77 names in 2–39 modules, 31 of them with a best pair similarity of 0.90 or more |
| B. Structural clones | identical function bodies with identifiers, constants, docstrings and annotations removed (≥ 5 statements); near clones at ≥ 0.90 similarity (≥ 8 statements) | 12 exact clone groups; 3 near clones |
| C. Responsibility signatures | lines that perform one responsibility, counted per module | 15 signatures |
| D. Textual duplicates | `pylint` 3.3.9 `duplicate-code` (R0801), ≥ 10 similar lines, imports, docstrings and comments ignored | 11 blocks |

### Retained detectors and their outputs

The four detectors and their exact outputs are kept, in their native formats, in
`365-duplication-inventory-2026-10-05-evidence/`.
Each runs over an extracted `git archive 4618e1b`:

| Detector | Script | Output | Interpreter |
|---|---|---|---|
| A and B | [`same_names_and_clones.py`](365-duplication-inventory-2026-10-05-evidence/same_names_and_clones.py) `<root>` | [`same-names-and-clones.json`](365-duplication-inventory-2026-10-05-evidence/same-names-and-clones.json) | CPython 3.14.7 |
| C | [`responsibility_signatures.py`](365-duplication-inventory-2026-10-05-evidence/responsibility_signatures.py) `<root>` | [`responsibility-signatures.txt.gz`](365-duplication-inventory-2026-10-05-evidence/responsibility-signatures.txt.gz) | any CPython 3.11 or later |
| D | [`duplicate_code.sh`](365-duplication-inventory-2026-10-05-evidence/duplicate_code.sh), from `<root>` | [`duplicate-code.txt.gz`](365-duplication-inventory-2026-10-05-evidence/duplicate-code.txt.gz) | pylint 3.3.9 |

Two outputs are gzip-compressed, because their exact bytes end lines with spaces or end
with a blank line, which the repository's whitespace check refuses; `gzip -dc` restores
them. [`index.json`](365-duplication-inventory-2026-10-05-evidence/index.json) records each output's SHA-256, of the uncompressed
bytes where compressed, with its script and interpreter.

The JSON output lists at most 45 same-name groups, 30 clone groups and 40 near clones.
How many there are in all, recorded by the same script with `--counts`, is in
[`same-names-and-clones-counts.json`](365-duplication-inventory-2026-10-05-evidence/same-names-and-clones-counts.json):
1,219 functions, 77 same-name groups (31 at 0.90 or more), 12 exact clone groups and 3
near-clone pairs (Codex and CodeRabbit on #375).

**Reproduced on 2026-10-06** from a fresh archive:
- **A and B:** byte-identical on CPython 3.14.7. Under 3.12 the similarity ratios differ, because `ast.dump`'s format changed in 3.13, though the clone groups do not.
- **C:** byte-identical.
- **D:** the same 11 blocks, over the same 22 module spans. Pylint orders files by directory listing, so the excerpt it prints for a block can differ.

## Families

### F1. Strict JSON parsing: highest priority

Several modules re-implement the same strict JSON reading: refusing duplicate keys,
refusing non-finite numbers, bounding document depth and checking RFC 3339 times.
They do it in identical shapes:

| Responsibility | Modules using it, any shape (C) | Shared helpers (A, B) |
|---|---|---|
| duplicate-key rejection (`object_pairs_hook`) | 9 | 6 identical bodies (B): `review_check`, `review_current`, `review_outer`, `review_protected`, `adoption_check`, `tasks/gnostoa_orientation`. `security_scan` shares the helper's name but not its body. `adoption_assurance` and `experiment/handoff` use other shapes |
| non-finite rejection (`parse_constant`) | 7 | `_reject_non_finite_constant` in 5 (A): `review_check`, `review_current`, `review_outer`, `review_protected`, `security_scan`. `adoption_assurance` and `adoption_check` use other shapes |
| finite float parsing | — | `_parse_finite_float`, 4 identical (A) |
| document depth bound | — | 2 identical (B: `review_check`, `review_live`), plus 1 near clone (0.92, `review_policy`) |
| strict RFC 3339 check | — | 3 identical (B: `review_check`, `review_live`, `review_outer`) |

So the duplicate-key baseline is **9 modules**, not 6: the 6 identical copies are the
ones that can merge mechanically (Codex on #375).

Detector D also finds 16- and 19-line duplicated blocks between `review_check` and
`review_live`.

**Why first:** these modules read untrusted review payloads, and parsing is a
security boundary. A fix applied to one copy does not reach the other five.

**Proposal:** one owner, `tools/strict_json.py`, covering bounded read, duplicate
keys, finite numbers, depth and RFC 3339. It would be registered with signatures
such as `object_pairs_hook` and `parse_constant`, and the existing copies counted as
debt that converges under #365.

### F2. Schema validation: owner proposed in #369

`Draft202012Validator` appears in 11 modules, on 28 lines. On `4618e1b` no owner exists yet. Detector A finds `_schema`
in 6 modules and `_schema_errors` in 3. #369 adds the owner,
`tools/schema_validation.py`, and counts these copies as debt for #365.

**Proposal:** no new owner. Converge the 11 modules on it after #369 lands.

### F3. HTTP clients for GitHub and the analyzers

| Pattern | Copies |
|---|---|
| `_mapping` | 7 (similarity 1.00/0.97) |
| `_text` | 4 |
| `_integer` | 3 |
| `_validate_api_url` | 3; the Codacy and DeepSource clients are exact clones |
| `_failure_completeness` | Codacy and DeepSource clients, exact clone |

HTTP requests are made in 7 modules. `tools/github_rest.py` owns GitHub's API, and
the Codacy, DeepSource and three debt modules make their own requests.

**Proposal:**
- extend the shared client to non-GitHub analyzer APIs, or add a sibling that shares
  its URL safety, bounded reads and error classes;
- add one owner of typed JSON field accessors (`_mapping`, `_text`, `_integer`).

### F4. Canonical JSON, hashing and time

| Helper | Copies |
|---|---|
| `_now` | 9 modules, identical (A); the current time is read in 12 modules (C) |
| `canonical_json` | 3 |
| `_sha` | 3 |
| `_sha256` | 2 |
| `_timestamp` | 3 |

`hashlib.sha256` appears in 21 modules.

**Why it matters:** the functions are small, but canonical JSON feeds digests. If two
copies drift, two parts of the toolkit compute different digests for the same
document.

**Proposal:** one owner, for example `tools/canonical.py`, holding canonical JSON,
the digest of a document and the current UTC time.

### F5. Policy document loading

| Pattern | Copies |
|---|---|
| `check_change_policy._load_change_policy` and `check_ci_policy._load_ci_policy` | exact clone, 23 statements |
| `_nested`, `_rank` | exact clones |
| `_assert_monotonic` | similar |
| `check_change_policy.main` and `check_guardrails.main` | 0.97 similar |

**Proposal:** one loader for inheritable policy documents: `extends` merge, ranks and
monotonic constraints.

### F6. Bounded process execution

| Pattern | Copies |
|---|---|
| `review_current._kill_and_reap` and `security_scan._terminate_and_reap` | exact clone |
| process-group kill | in `candidate_prepare`; #374's second round adds one to `tools/mutation.py`, because no owner exists yet |
| subprocess launches | 20 modules |

Many launches are legitimate, but timeout, output-bound and reap handling are written
locally each time.

**Proposal:** one owner of bounded subprocess execution: timeout, bounded output,
process-group termination and reap. It would sit beside `tools/trusted_execution.py`,
which owns *which* executable runs.

### F7. CI smoke harness

Detector D: 20- to 31-line duplicated blocks across five `ci/review_*_smoke.py`
scripts:
- `review_outer_smoke`;
- `review_outer_containment_smoke`;
- `review_live_smoke`;
- `review_current_advisory_restoration_smoke`;
- `review_b16_entrypoint_smoke`.

There are also 12- to 14-line blocks shared with `tools/review_outer`.

**Proposal:** a shared smoke harness module, for example `ci/lib/smoke.py`. It needs
care, because smoke scripts are evidence routes.

### F8. Experiment and capsule helpers

| Helper | Copies |
|---|---|
| `_same_object` | 4 (A): 3 in `tools/experiment/` (`capture`, `handoff`, `packaging`), 1 in `tools/capsule/effect_claim` |
| `_normalized_mode` | 2, exact (B): `tools/experiment/handoff`, `tools/experiment/packaging` |
| `assert_visible_directory` | 2, exact (B): `tools/experiment/capture`, `tools/experiment/handoff` |
| `_emit` | 3 (A): `tools/experiment/handoff`, `tools/experiment/packaging`, `tools/capsule/cli` |

**Proposal:** one shared module for both packages, since `tools/capsule/` holds a copy of
`_same_object` and of `_emit` too (CodeRabbit on #375). Low priority, since every copy
is in these two packages.

### F9. Already being consolidated

- **Trusted execution:** #368 / #369, with PR B, C and D to follow.
- **Targeted mutants:** #373 / #374.

The two identical `capsule` `_materialize` wrappers (`compiler`, `execute`) already
call the owner's `extract_tree` in #369. Only the error mapping remains local.

### Tests

Test helpers repeat too:

| Helper | Test modules |
|---|---|
| `_receipt` | 15 |
| `_load_workflow` | 7 |
| `_git` | 5 |
| `_fixtures` | 5 |
| `_named_step` | 5 |
| `_bundle` | 4 |

That is lower risk than production duplication, but it is the same cost: a fix to
one fixture does not reach the others.

**Proposal:** a `tests/support/` module per family, adopted when a test is next
touched.

## Not duplication

- `main`, `_parser` and `build_parser` appear in 39, 15 and 7 modules. Each command
  needs its own parser, and their similarity is low (average 0.17–0.47).
- Most `argparse` and `subprocess` use is ordinary.

## Proposed order

1. **F1, strict JSON.** A security boundary, with five or six identical copies.
2. **F3, HTTP clients and typed accessors.** Security-relevant: URL safety and
   bounded reads.
3. **F4, canonical JSON, digests and time.** Digest correctness.
4. **F2, schema validation.** The owner exists once #369 lands; only convergence is
   needed.
5. **F6, bounded process execution.**
6. **F5, policy loading.**
7. **F7, the CI smoke harness.**
8. **F8, experiment and capsule helpers.**
9. **Test support modules,** when touched.

Each family follows the same route as #368 and #374:
- a Work Item;
- a Decision;
- the prior-art checkpoint and lineage table;
- one owner, registered in `policy/owned-responsibilities.yaml` with its signatures;
- its existing copies counted as debt, so `knowledge reuse-check` refuses a new copy
  while the old ones converge.

None is admitted by this record. The owner admits each family.

## For later evaluation

Re-run the four detectors on the main of a later date, and compare per family:
- the number of copies;
- whether each proposed owner exists;
- whether each family's debt shrank;
- whether a new family appeared.

A family whose copies grew after its owner was registered means the registry's
signatures missed a shape.
