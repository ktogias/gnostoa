---
type: Source
title: B2/P1 streamlined self-hosting measurements
description: Mechanically derived measurements for the first B2 slice, compared with the recorded B1 self-dogfood baseline, with owner review time left pending.
status: draft
generated:
  by: agent:claude-opus-5
  at: "2026-08-16T00:52:00Z"
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

The exact candidate revision is carried by the task envelope and the Change
Request body rather than repeated here. A committed record cannot contain its
own commit identity without a self-reference, which is the same constraint the
resume workflow already documents for envelopes.

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

## B2/P1 measurements at checkpoint 3

| Metric | B2/P1 | B1 comparison |
|---|---:|---|
| Provider comments on the change | **0** | 407 |
| Foreground evidence words | **1,093** | ~289,449 comment words |
| — Change Request body | 680 | — |
| — Current task projection | 413 | — |
| Changed normative words added | 5,328 | — |
| Evidence amplification (foreground words ÷ changed normative words) | **~0.21 : 1** | ~7.2 : 1 on a different denominator |
| Changed lines, normative surfaces | +1,493 / −98 | — |
| Changed lines, tests | +666 / −17 | — |
| Changed lines, other | +43 / −34 | — |
| Commits on the candidate branch | 3 | — |
| Completed owner review rounds | **0** (first is pending) | 0 formal reviews |
| Semantic decisions requested / answered | 2 / 2 | not separately recorded |
| Effect authorizations requested / granted | 3 / 3 | not separately recorded |
| Material defects caught before integration | **1** | multiple |
| Known escaped defects | **0** | — |
| False-ready outcomes | **1** | not separately recorded |
| False-block outcomes | 0 | not separately recorded |
| Elapsed to checkpoint 3 | ~1.3 hours | ~17 days |
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

**Material defect caught before integration (1).** The declared runtime-target
gate was run against candidate `ef62a008` and failed. Task-envelope reference
resolution defaulted to the process working directory, so the required test
`test_duplicate_keys_and_nonportable_references_are_rejected` passed only when
the caller happened to run from a Gnostoa checkout. `knowledge self-check` is
both the `regression` suite and the documented consumer command, so the
packaged runtime image failed it out of the box.

**False-ready outcome (1).** That same candidate was presented as review-ready
while its own declared pre-merge gate was still unrun, and its evidence claimed
container verification that had not covered the runtime target. The gate caught
this before integration, but the ready signal was wrong when issued.

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
and one test fixture. Checkpoint 3 added no new product code — only a fixture,
a test and a documentation section.

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
