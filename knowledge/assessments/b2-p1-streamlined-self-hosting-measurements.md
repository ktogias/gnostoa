---
type: Source
title: B2/P1 streamlined self-hosting measurements
description: Mechanically derived measurements for the first B2 slice, compared with the recorded B1 self-dogfood baseline, with owner review time left pending.
status: draft
generated:
  by: agent:claude-opus-5
  at: "2026-08-16T03:26:00Z"
sources:
  - id: streamlined-self-hosting-experiment
    resource: https://github.com/ktogias/gnostoa/issues/24
    title: Run one bounded B2 streamlined self-hosting experiment
  - id: b2-p1-change-request
    resource: https://github.com/ktogias/gnostoa/pull/25
    title: B2 — add a validated task envelope and current projection
x-project-knowledge:
  id: kit.assessment.b2-p1-streamlined-self-hosting-measurements
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md
    - kind: derived-from
      target: /assessments/gnostoa-self-dogfood-bootstrap-assessment.md
    - kind: references
      target: /failure-modes/reverse-centaur-review-overload.md
---

# B2/P1 streamlined self-hosting measurements

## Measurement boundary

This record covers **B2/P1** only: the first increment of the Decision 0016
sequence, delivered as PR #25 and durably tracked by the `GNOSTOA/B2/P1` task
envelope at checkpoint 6. It does not cover B2 as a whole, and it is not an
acceptance record.

The task envelope does **not** contain the candidate identity. A committed
envelope cannot carry its own commit identity without a self-reference, so the
candidate is supplied at projection time and is currently bound by the Change
Request head and the derived current projection. This record is subject to the
same constraint and therefore names no revision of its own.

Two different surfaces are measured here, and they are not interchangeable:

- the **implementation delta** is every change under review except this record
  and its fixture. It is what a reviewer reads for correctness, and it is
  stable against edits to this record; and
- the **complete human-review surface** additionally includes this record and
  its fixture. Because writing that total into this record would change it,
  the complete figure is reported only by the provider and the Change Request
  body, against the exact head.

Every figure below is mechanically derived from the repository and the provider
API. One required metric, active owner review time, cannot be derived and is
left explicitly pending. It is not estimated.

## Recorded B1 baseline

From the exact provider extraction on 2026-08-15 recorded in the
[self-dogfood bootstrap assessment](gnostoa-self-dogfood-bootstrap-assessment.md):

| Metric | B1 |
|---|---:|
| Provider comments on the two main threads | 407 |
| Comment-body characters on those threads | 2,580,461 |
| Comment corpus words (all threads) | ~289,449 |
| Repository text words | ~40,131 |
| Evidence amplification (comment words ÷ repository text words) | ~7.2 : 1 |
| Formal Change Request reviews and inline review comments | 0 |
| Elapsed span | ~17 days (2026-07-30 → 2026-08-15) |

## B2/P1 measurements at checkpoint 6

| Metric | B2/P1 | B1 comparison |
|---|---:|---|
| Provider comments on the change | **0** | 407 |
| Current task projection words | **618** | — |
| Change Request body words | reported in the Change Request against the exact head | — |
| Foreground evidence words | sum of the two rows above, reported in the Change Request | ~289,449 comment words |
| Changed normative words added | 6,338 | — |
| Evidence amplification (foreground words ÷ changed normative words) | reported in the Change Request | ~7.2 : 1 on a different denominator |
| Implementation delta | 22 files, +2,618 / −149 | — |
| — normative surfaces | 16 files, +1,686 / −98 | — |
| — tests | 2 files, +889 / −17 | — |
| — documentation and packaging | 4 files, +43 / −34 | — |
| Commits on the candidate branch | 6 | — |
| Completed owner review rounds | **3** untimed pre-review rounds, one an independent read-only audit; timed disposition pending | 0 formal reviews |
| Semantic decisions requested / answered | 2 / 2 | not separately recorded |
| Effect authorizations requested / granted | 4 / 4 | not separately recorded |
| Material defects caught before integration | **4** defect families | multiple |
| Evidence defects corrected in owner review | **2** | not separately recorded |
| Known escaped defects | **0 known before integration; post-integration observation pending** | — |
| False-ready outcomes | **4** | not separately recorded |
| False-block outcomes | 0 | not separately recorded |
| Elapsed to checkpoint 6 | see note below | ~17 days (provider-visible) |
| Integrated | no | yes |

### Why two figures moved out of this record

Earlier revisions stated a Change Request body word count and the foreground
sum inside this record. Both are self-referential: this record is part of the
change, so writing the totals here changes them, and the figures went stale
twice. They are now reported only in the Change Request, against the exact
head, using one stated method — whitespace-delimited tokens (`wc -w`) over the
Markdown source of the Change Request body and over the generated projection.
The projection word count is not self-referential and stays here.

### Elapsed time is three different measurements

Provider-visible elapsed time, active work time and final review time are not
interchangeable, and the earlier single "~3 hours" figure conflated them
against a B1 baseline that used provider-visible wall-clock time:

| Measurement | B2/P1 | B1 |
|---|---:|---:|
| Provider-visible elapsed, first candidate commit to current head | see the Change Request | ~17 days |
| Active work time | not instrumented | not instrumented |
| Final timed disposition | pending | not applicable |

Only the first row is comparable with B1. The other two were never
instrumented, and this record does not reconstruct them.

The amplification denominators are **not** the same measurement. B1 divided its
comment corpus by total repository text; B2/P1 divides foreground evidence by
the words this change actually added to normative surfaces. The directly
comparable figure is the provider comment count: 407 against 0.

## Pending human entry

- `active_owner_review_minutes`: **pending**. The envelope declares a 20-minute
  budget and a 6,000-character projection budget; whether the real review fits
  inside them is the primary open result of this slice.

Until that value exists, this record cannot state whether B2/P1 reduced owner
effort. It only shows that the foreground evidence surface and provider comment
volume are materially smaller.

## Defects, recovery and negative results

**Material defect 1 — working-directory dependence.** The declared
runtime-target gate was run against an earlier candidate and failed.
Task-envelope reference resolution defaulted to the process working directory,
so the required test
`test_duplicate_keys_and_nonportable_references_are_rejected` passed only when
the caller happened to run from a Gnostoa checkout. `knowledge self-check` is
both the `regression` suite and the documented consumer command, so the
packaged runtime image failed it out of the box. Caught by the declared gate.

**Material defect 2 — checkout-normalization fragility.** The first fixture for
the provider digest stored the issue body as raw Markdown bytes. A checkout
that rewrites line endings would have changed those bytes and broken the
required test, on a rule whose entire point is that no normalization applies.
Caught in owner review; the fixture is now JSON, so every line break inside the
body is an escape sequence and the parsed body is invariant under file
line-ending normalization. The test asserts that invariance directly.

**Material defect 3 — unbounded recursive alias traversal.** The duplicate-key
visitor walked the composed YAML node graph without cycle detection. A document
whose alias forms a cycle raised an uncaught `RecursionError` with a full
traceback and exit code 1, instead of the documented bounded validation error:

```yaml
recursive: &recursive
  - *recursive
```

This contradicted both the envelope's JSON-shaped schema and digest model and
the claimed fail-closed, no-traceback command contract. Caught in owner review
of the exact candidate.

The traversal now tracks the active path to reject cycles and remembers
completed nodes so a shared subgraph is inspected once. Acyclic aliases remain
ordinary supported YAML. A measured side effect: on a 22-level acyclic alias
document the previous traversal exceeded a three-million-node-visit budget,
while the corrected traversal completes immediately. That is a consequence of
visiting each node once, not a claim of general YAML hardening.

**Material defect family 4 — the CLI error boundary was narrower than the
input it accepted.** An independent read-only robustness audit of the exact
candidate confirmed five manifestations of one root cause: `validate_main` and
`project_main` caught only `KnowledgeFormatError`, `OSError` and
`json.JSONDecodeError`, while the code beneath them could raise four other
exception types. Each produced a full traceback and exit code 1 instead of the
documented bounded path.

| # | Input | Escaping exception | Raised in |
|---|---|---|---|
| A1 | invalid UTF-8 envelope bytes | `UnicodeDecodeError` | source decoding |
| A2 | ~500 nested levels in a 1 KB file | `RecursionError` | PyYAML's composer, before any project code |
| A3 | `resource: "https://["` | `ValueError` | `urlsplit()` |
| A4 | a `!!binary` value with checkpoint validation | `TypeError` | `json.dumps()` in the digest |
| A5 | valid JSON that is not a valid schema | `SchemaError` | JSON Schema construction |

These are counted as **one defect family**, not five defects. A2 is the reason
the earlier recursive-alias fix was insufficient on its own: the recursion
happens inside the parser, so no detector running after composition can reach
it.

The correction establishes a pre-parse input contract — an explicit byte-size
bound and an explicit nesting-depth bound measured with YAML's iterative
scanner before composition — and converts each demonstrated boundary exception
into a bounded diagnostic. A1, A2, A4 and A5 now exit 2 on stderr. A3 is
deliberately different: a malformed URL inside an otherwise parsable envelope
is a validation issue, so it exits 1 through the validation path. No
`except Exception` was added.

**Deferred finding — loader-semantic and merge-key gap (Family C).** The same
audit confirmed, and this slice does not fix, that duplicate-key detection and
object construction do not share fully equivalent key semantics: detection
compares composed key nodes under `SafeLoader`, while construction uses
`KnowledgeLoader`, which drops the timestamp resolver, and keys on constructed
Python values. Keys whose source text differs but whose constructed values
collide are therefore not flagged, and YAML merge keys (`<<`) are not
prohibited, so merged properties are invisible to the check. The fixed task
envelope schema, with `additionalProperties: false` throughout and no
date-, bool- or numeric-shaped key names, prevents every demonstrated case from
silently overriding a valid schema-relevant property. This is recorded as a
bounded follow-up, and the wording in the code and the public workflow no
longer claims that all semantically ambiguous YAML is rejected.

**Evidence defects corrected in owner review (2).** The review packet reported
a review surface measured before the measurement artifacts existed, which did
not match the provider's count for the exact head; and this record stated that
the task envelope carries the candidate identity, which it does not and cannot.
Both were evidence errors rather than product defects, and both would have
misinformed a timed review.

**False-ready outcomes (4).** An earlier candidate was presented as review-ready
while its own declared pre-merge gate was still unrun. A second packet was
presented for timed review with stale surface accounting. A third was presented
while the recursive-alias blocker was still present. A fourth was presented
while the wider error-boundary family was still present. None reached
integration, but all four ready signals were wrong when issued.

The pattern matters more than the count: every required suite was green each
time. Green checks were a necessary and repeatedly insufficient condition for
readiness, and each defect was found by a human or by a gate that the automated
suites did not run.

**Route asymmetry, recorded as a durable failure mode.** The development
container binds the source at `/workspace`, so it always supplies a repository
root by accident; the runtime target does not. Development-container green is
therefore not sufficient evidence for a change touching the CLI or `tools/`.

**Interruption recovery: successful.** A fresh actor with no prior conversation
context reconstructed the authoritative state from the Decision 0016 resume
card, the roadmap projection, the live Issue and Change Request bodies and the
task envelope, then verified base, dependency, candidate and checkpoint
identities before acting. No historical ledger was replayed. This is the first
direct evidence that the resume contract works for an actor that was not
present for the original work.

**Reproducibility gap found and closed.** The recorded provider dependency used
the ambiguous identity kind `provider-body-sha256` with no written
canonicalization rule; reproducing the digest required guessing among five
candidate rules. The kind is now `github-issue-body-utf8-sha256-v1` with an
exactly specified byte sequence and offline evidence.

## New maintenance and tooling surface

P1 as a whole adds: one JSON Schema, one public template, one tool module, two
CLI commands, one test module, one guidance workflow, one durable state file
and one test fixture. Checkpoints 5 and 6 corrected the validator traversal and
established the pre-parse input contract; the other post-review checkpoints
added no product code — only
tests, a fixture, documentation and this record.

This is the surface that must keep earning its place. Decision 0016's stop rule
applies: if an increment does not improve a named outcome, simplify, remove or
redesign it.

## Status against Issue #24 acceptance

Satisfied so far: the change and comparison method were fixed before
implementation; the exact base, candidate, evidence and dependencies remain
reconstructable without replaying conversations; no agent-produced evidence is
represented as human acceptance; a fresh reviewer can identify status, question
and next action from one bounded projection; both positive and negative results
are reported here.

Not yet satisfied: owner interaction cost is unmeasured until the review
happens, so the criterion that evidence amplification **and** owner interaction
fall materially below B1 is only half-evidenced.
