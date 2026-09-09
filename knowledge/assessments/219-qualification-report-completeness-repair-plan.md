---
type: Source
title: Work Item 219 qualification report-completeness repair plan
description: Bounded critical-change plan for preserving terminal process validity and refusing incomplete or contradictory qualification reports without changing routing, receipt schemas, runner isolation or Phase-D authority.
status: draft
generated:
  by: openai/chatgpt
  at: "2026-09-09T10:20:00Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/219
    title: Preserve process failure and report completeness in qualification classification
  - id: implementation-admission
    resource: https://github.com/ktogias/gnostoa/issues/219
    title: Owner-admitted critical RED-to-GREEN implementation checkpoint
x-project-knowledge:
  id: kit.assessment.219-qualification-report-completeness-repair-plan
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0059-compile-declarative-experiment-capsules-over-the-owner-led-runner.md
    - kind: references
      target: /requirements/verification-precedes-implementation.md
    - kind: references
      target: /requirements/bounded-behavioral-traceability.md
---

# Work Item 219 qualification report-completeness repair plan

## Bound change

Implement the owner-admitted #219 critical repair from integrated commit
`6d8c4356866b3844f3439c7dc7ea374c39cfff2b`. Decision 0059 already requires
BASE/REFERENCE qualification by cause and states that collection, import and
infrastructure failure can never satisfy a prospective behavioral failure.

The changed production surface is limited to
`tools/capsule/qualification.py`. A focused test module establishes and pins the
process/report completion contract. No receipt schema, compiler routing,
adapter support, retained-evidence admissibility, experiment-runner isolation,
Phase-D material or launch authority changes are included.

## Existing defect and expected behavior

The OCI pytest normalizer currently discards terminal exit status when at least
one case line is present. Matching partial output followed by pytest internal
error can therefore reach `MATCH`. It also maps a pytest `ERROR` case into a
failed case and may infer `AssertionError`. The local Python backend accepts a
valid-looking final JSON line without checking whether its harness process
completed successfully.

The repair must preserve these distinctions:

| Observation | Required classification |
| --- | --- |
| completed pytest BASE assertion failure, exit 1 | eligible for normal cause/count comparison |
| completed pytest REFERENCE success, exit 0 | eligible for normal cause/count comparison |
| interruption/internal/usage/no-collection/unknown or signalled exit | infrastructure, even with matching case output |
| pytest `ERROR` case | infrastructure, not inferred assertion failure |
| contradictory exit/result pair | infrastructure |
| non-zero, timed-out or malformed local harness | infrastructure |

`nonzero => invalid` is explicitly rejected because pytest exit 1 is the normal
completed state for failing tests.

## RED before production mutation

Create tests only and retain the exact failing result on the unmodified
production implementation. The decisive REDs are:

1. failed discriminator line plus exit 3 currently becomes BASE `MATCH`;
2. passed line plus exit 3 currently becomes REFERENCE `MATCH`;
3. pytest `ERROR` plus exit 1 currently becomes an inferred assertion failure;
4. local non-zero process with a valid-looking JSON line is currently accepted;
5. timeout handling currently escapes instead of producing a structured
   infrastructure report.

Normal exit-1 BASE and exit-0 REFERENCE cases are non-vacuous positive controls.

## Selected minimal repair

Normalize terminal completion before semantic classification:

- recognize only pytest exits 0 and 1 as completed test-session states;
- refuse all other exit states before case output can support a match;
- preserve `ERROR` as an infrastructure-level report failure;
- require exit/result consistency (`0` cannot contain failed cases; `1` must
  contain at least one failed case);
- make local harness timeout/non-zero/non-object output return the existing
  structured uncollected report shape.

Keep `_classify` and the public receipt schema unchanged. This retains the
smallest seam: backend-specific execution normalizes trustworthy report input,
then the existing cause/count classifier operates on that input.

## Alternatives not selected

- **Reject every non-zero exit.** Incorrect because normal BASE failure uses
  pytest exit 1.
- **Change only `_classify`.** Too late: terminal status is already discarded
  and pytest `ERROR` has already been relabelled.
- **Add fields to receipt v1.** Unnecessary for current fresh-report completion
  and would collide with #216 historical evidence-admissibility design.
- **Redesign the runner or use a pytest plugin/JSON reporter.** Potential future
  hardening, but materially wider than the demonstrated defect.
- **Absorb Node, routing or prior-receipt work.** Owned by #218, #215 and #216.

## Risks and controls

The main compatibility risk is refusing output that older tests accidentally
accepted. Positive controls preserve the two valid v1 pytest terminal shapes.
Unknown/custom exit codes fail closed until explicitly supported. Detail strings
are diagnostic only and do not become new public authority.

Local harness validation remains bounded to its own producer: the embedded
harness is designed to emit one JSON object and terminate zero. A non-zero exit
therefore denotes producer failure regardless of a partial final line.

No historical receipt is rewritten or requalified. #216 separately determines
whether evidence produced by an invalid historical producer remains admissible.

## Verification and stop

1. retain focused RED on the unmodified implementation;
2. implement the minimal normalization repair;
3. run focused tests and the full source suite in the development container;
4. run Ruff and mypy gates and applicable policy/fast/regression/smoke checks;
5. inspect exact PR diff and provider exact-head results;
6. stop at an open review-ready PR.

Merge, issue closure, branch deletion and follow-on #216/#202 implementation
require separate owner disposition.
