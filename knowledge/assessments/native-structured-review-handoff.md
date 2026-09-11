---
type: Source
title: Native structured review handoff evaluation
description: Second bounded review-exchange trial with native schema output, exact-command startup qualification and observed successor commands.
status: draft
generated:
  by: agent:codex
  at: "2026-09-11T07:15:00Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/235
    title: Selected second trial and initial N01–N06 behavior map
  - id: previous-result
    resource: https://github.com/ktogias/gnostoa/pull/234
    title: Integrated first review exchange experiment
x-project-knowledge:
  id: kit.assessment.native-structured-review-handoff
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0064-evaluate-native-structured-review-handoff.md
    - kind: references
      target: /assessments/portable-review-exchange-evaluation.md
---

# Native structured review handoff evaluation

## Subject and boundary

Work Item #235 is the separately owner-selected second trial. Integration base
`ac4ba46ad4884b3a166ffd4c4b8c5b189fd5e147` preserves the approved first-trial
tree `8eb6547871ea65d7d2298a6c801d83aee970c96a`. Its original oracle, native
archives and `NARROW` result remain unchanged. This checkpoint records
construction; live outcomes are initially **NOT RUN**.

The historical review subject remains PR #228 head
`6ee2deb9584ebb9a8f4fa4076fef10f9500903b9`, tree
`c468e8d9bf8b9b47f87cc5b3c7a89d8dc1bae4ba`. It is distinct from this fixture's
implementation candidate. The root starts A and B and may collect B at the end;
B must perform its own `collect`/`view` calls to meet the handoff question.
No complete autonomous coordinator replacement or protected execution is claimed.

## Initial evidence

An independent agent derived seven result-consumption tests from the selected
contract and official native result documentation before the adapter correction.
On the old adapter they produced five passing methods and two behavioral
assertion failures, with zero execution errors: valid structured native input
reached `collect` and the persisted view but remained pending. Negative controls
passing under blanket rejection did not establish discrimination by themselves.

The correction adds one declared `claude-structured` adapter. It requires a
unique successful native result and its `structured_output` object, then uses
the existing domain validation. It never repairs missing output from explanatory
prose. The existing Codex adapter remains strict; native `--output-schema` is
used to request its complete JSON final response.

The old Codex config error was separately reproduced with empty stdin. The same
options without two incomplete MCP override pairs reached the deliberate
`No prompt provided via stdin.` sentinel. Version-pinned official source places
this exit after config/auth handling but before model startup. The final planned
argv was rechecked the same way. This qualifies config loading, not inference,
schema acceptance or zero local initialization effects. The schema separately
passed local Draft7 validation; actual native generation remains to be measured.

## Behavioral traceability at construction checkpoint

| ID | Required behavior | Current evidence / alignment |
|---|---|---|
| N01 | Exact invocation qualification, honest failure classification | Old/new native no-model discriminant and final argv sentinel observed; actual startup NOT RUN. |
| N02 | Strict native structured response consumption | Pre-change 2 behavioral failures; corrected 7-method container replay PASS. Mutation review pending. |
| N03 | Original evidence and failure preservation | First archives/oracle unchanged; new tests retain exact native bytes. |
| N04 | Successor performs collect/view and reconstructs durable context | Frozen A/B assignments prepared; live tool evidence NOT RUN. |
| N05 | Pending, dissent, source and separate dispositions survive | New controlled checks exercise original records, stale state and pending eligible B; live result NOT RUN. |
| N06 | Two-assignment/time/cost boundary | New live calls NOT RUN; no paid API fallback authorized. |

Executor and reviewer final dispositions remain PENDING at this checkpoint.
The final packet must replace these prospective cells with actual evidence and
retain this construction chronology. Tests of synthetic captures do not establish
native tool availability, successful live handoff or review quality.
