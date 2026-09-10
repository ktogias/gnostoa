---
type: Decision
title: Retain individual agent review findings and dispositions
description: Record each supplied reviewer separately in Gnostoa-self delivery while preserving subject binding, evidence provenance and human authority.
status: draft
generated:
  by: agent:codex
  at: "2026-09-10T13:23:53Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/11
    title: Semantic capture reconciliation and rationale completeness
  - id: individual-review-record
    resource: https://github.com/ktogias/gnostoa/pull/228#issuecomment-5619319298
    title: Individually recorded findings and dispositions for five supplied reviews
x-project-knowledge:
  id: kit.decision.0061.retain-individual-agent-review-dispositions
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0036-canonicalize-bounded-self-hosted-delivery-practice.md
    - kind: references
      target: /requirements/retrospective-findings-require-explicit-admission.md
    - kind: governs
      target: /runbooks/deliver-bounded-self-hosted-slice.md
---

# Retain individual agent review findings and dispositions

## Context

The owner explicitly requested that supplied agent reviews retain each agent's
findings and disposition, then requested a persistent guideline. This
agent-authored record captures that bounded instruction; it is not human
semantic approval of the resulting candidate or merge authorization.

At main `a1dfd461cfb90c403e5847e886a760f9943fcc54`, the delivery runbook
required exact-candidate review and inference limits but did not require a
separate record for every supplied reviewer. The initial aggregate handling of
PR #228 did not preserve all five reviewers' findings and recommendations
separately. The linked individual record corrects that omission. This unmet
semantic criterion was identified before editing the guideline; it is not a
software test failure or proof that prose can enforce future compliance.

## Decision

Adopt the [supplied-agent-review procedure](../runbooks/deliver-bounded-self-hosted-slice.md#supplied-agent-reviews)
for Gnostoa's own work. Capture each reviewer's source attribution, reviewed
subject, reported findings and recommendation, then preserve the executor's
reasoned disposition and evidence separately. Capture is triggered by receipt,
before reporting the reviews handled; it is not deferred to an eventual merge.

Keep the procedure in the existing self-hosted runbook, route to it from
`AGENTS.md`, and declare a kit-only, review-enforced guardrail. Classify the
change as **normative** because it adds a mandatory self-review practice and
policy coverage. Work Item #11 owns this bounded capture improvement. The test
fixture PR #228 and Decision 0060 remain a separate change; this guideline does
not require their integration.

Preserve the existing publication, finding-admission and human-approval
boundaries. Shared evidence may be linked without losing reviewer attribution.
An older-head recommendation is not automatically a newer-head review. Missing
provenance or unverified execution remains explicit uncertainty.

## Verification and limits

For this non-executable practice, use the recorded unmet criterion, independent
semantic review, existing bundle/guardrail/path validation and the applicable
container suites. Do not add prose-matching tests or describe structural checks
as enforcing actual capture. Human semantic review remains necessary.

## Consequences

This is Gnostoa-self guidance, not a generic adopter requirement, new schema,
workflow engine, reviewer identity service, automatic approval or L10 control.
Routine branch, draft-PR and bounded evidence preparation are within the owner's
instruction; stable promotion, merge and Work Item closure remain separate.
