---
type: Source
title: Issues 309/313 analyzer-readback RED-first execution contract
description: Predeclare failing contracts for the paired DeepSource and Codacy authenticated readback slice before production implementation.
status: draft
generated:
  by: openai/gpt-5.6-sol
  at: "2026-09-23T13:05:00Z"
sources:
  - id: decision
    resource: /decisions/0091-add-authenticated-provider-neutral-analyzer-readback.md
    title: Add authenticated provider-neutral analyzer readback before critical Q0 activation
  - id: deepsource-work-item
    resource: https://github.com/ktogias/gnostoa/issues/309
    title: DeepSource authenticated full-report readback
  - id: codacy-work-item
    resource: https://github.com/ktogias/gnostoa/issues/313
    title: Codacy authenticated PR readback
x-project-knowledge:
  id: kit.assessment.309-313.analyzer-readback-red-contract
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
---

# Issues 309/313 analyzer-readback RED-first execution contract

## Subject

Protected parent: `074bd0499395986021b4c320ee9d23ec67859186`.

Implementation identity: `analyzer-readback-309-313`.

The first production candidate must be prepared from that exact parent or a
documented successor produced by this same bounded slice.

## RED contracts

Before production adapter code is accepted, tests must demonstrate these missing
behaviours:

| ID | Required failing contract |
| --- | --- |
| R1 | A normalized readback with a non-exact or malformed requested head is rejected. |
| R2 | `COMPLETE` coverage cannot disagree with retained count or provider total. |
| R3 | Partial pagination cannot become an empty clean report. |
| R4 | DeepSource `FULL_RUN` rejects a returned commit that differs from the requested exact head. |
| R5 | DeepSource `DIFF_LOCAL` cannot be promoted to authenticated `FULL_RUN`. |
| R6 | Codacy readback is `INCOMPLETE` when exact PR-head binding cannot be proven. |
| R7 | Provider tokens never appear in normalized output, retained URLs or bounded exceptions. |
| R8 | Off-origin redirects are rejected before an Authorization header can cross origins. |
| R9 | Malformed provider payloads fail closed without fabricating zero findings. |
| R10 | Finding identity, severity, rule, message, location and native reference survive normalization without provider vocabulary entering the common reducer. |
| R11 | Analyzer readback has no mutation route: no trigger, comment, dismissal, configuration or Git/provider write method is exposed. |
| R12 | PR #312 dogfood can retain exact-head provider evidence or an explicit incomplete limitation without guessing from GitHub check counts. |

## Intended implementation shape

Keep the first slice flat and auditable:

- `tools/analyzer_readback.py`: normalized model validation and bounded
  serialization only;
- `tools/analyzer_deepsource.py`: DeepSource authenticated acquisition;
- `tools/analyzer_codacy.py`: Codacy authenticated acquisition;
- focused tests in `tests/test_analyzer_readback.py`;
- guardrail ownership and this Decision/index update.

Do not modify R2A semantic evaluation or the useful-L1 reducer merely to host
provider acquisition.

## Verification

The implementation candidate must run the Decision 0090 preparation surface with
a focused profile that covers the new tests, then pass repository style and the
ordinary authoritative CI gates. The retained preparation receipt and exact
candidate SHA remain distinct from later external review evidence.
