---
type: Source
title: B2/P1 streamlined self-hosting measurements
description: Mechanically derived measurements for the first B2 slice, compared with the recorded B1 self-dogfood baseline, with owner review time left pending.
status: draft
generated:
  by: agent:claude-opus-5
  at: "2026-08-16T01:34:00Z"
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
envelope at checkpoint 3. It does not cover B2 as a whole, and it is not an
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

## B2/P1 measurements at checkpoint 4

| Metric | B2/P1 | B1 comparison |
|---|---:|---|
| Provider comments on the change | **0** | 407 |
| Foreground evidence words | **1,093** | ~289,449 comment words |
| — Change Request body | 680 | — |
| — Current task projection | 413 | — |
| Changed normative words added | 5,469 | — |
| Evidence amplification (foreground words ÷ changed normative words) | **~0.20 : 1** | ~7.2 : 1 on a different denominator |
| Implementation delta | 22 files, +2,223 / −149 | — |
| — normative surfaces | 16 files, +1,507 / −98 | — |
| — tests | 2 files, +673 / −17 | — |
| — documentation and packaging | 4 files, +43 / −34 | — |
| Commits on the candidate branch | 4 | — |
| Completed owner review rounds | **1** untimed reconciliation; timed disposition pending | 0 formal reviews |
| Semantic decisions requested / answered | 2 / 2 | not separately recorded |
| Effect authorizations requested / granted | 4 / 4 | not separately recorded |
| Material defects caught before integration | **2** | multiple |
| Evidence defects corrected in owner review | **2** | not separately recorded |
| Known escaped defects | **0** | — |
| False-ready outcomes | **2** | not separately recorded |
| False-block outcomes | 0 | not separately recorded |
| Elapsed to checkpoint 4 | ~2 hours | ~17 days |
| Integrated | no | yes |

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

**Evidence defects corrected in owner review (2).** The review packet reported
a review surface measured before the measurement artifacts existed, which did
not match the provider's count for the exact head; and this record stated that
the task envelope carries the candidate identity, which it does not and cannot.
Both were evidence errors rather than product defects, and both would have
misinformed a timed review.

**False-ready outcomes (2).** An earlier candidate was presented as review-ready
while its own declared pre-merge gate was still unrun. A later packet was
presented for timed review with stale surface accounting. Neither reached
integration, but both ready signals were wrong when issued.

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
and one test fixture. Checkpoints 3 and 4 added no new product code — only
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
