---
type: Requirement
title: Require explicit admission for retrospective findings
description: Gnostoa findings must move from observation through focused tracking and a separate admission boundary before they can authorize implementation.
status: draft
generated:
  by: chatgpt/gpt-5.6-sol
  at: "2026-08-29T15:20:00+03:00"
sources:
  - id: finding-admission-work-item
    resource: https://github.com/ktogias/gnostoa/issues/165
    title: Enforce finding-to-implementation admission across Gnostoa development
  - id: phase-a-retrospective
    resource: https://github.com/ktogias/gnostoa/blob/main/knowledge/assessments/nextcloud-mail-phase-a-owner-led-adaptation-retrospective.md
    title: Nextcloud Mail Phase-A owner-led adaptation retrospective
x-project-knowledge:
  id: kit.requirement.retrospective-findings-require-explicit-admission
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0053-require-lightweight-work-item-micro-retrospection.md
    - kind: references
      target: /requirements/reviewed-change-control.md
    - kind: verified-by
      target: /runbooks/deliver-bounded-self-hosted-slice.md
    - kind: references
      target: /assessments/nextcloud-mail-phase-a-owner-led-adaptation-retrospective.md
---

# Require explicit admission for retrospective findings

Decision 0053 establishes that retrospective learning is retained without making
the suggested improvement automatically effective. For Gnostoa self-development,
that boundary is mandatory across retrospectives, experiments, evaluations,
reviews, incident analyses and comparable learning surfaces.

The canonical flow is:

> **Observation → retrospective finding → focused tracked Work Item → explicit admission condition → implementation only after separate admission.**

## Required workflow

1. **Observation.** Capture the observed behavior, evidence and claim boundary in
   the assessment, retrospective, evaluation, review or other owning evidence
   surface. Preserve negative results and uncertainty rather than turning them
   directly into a change request.
2. **Retrospective finding.** State the actionable finding separately from the
   evidence that produced it. A finding records learning; it is not implementation
   authority.
3. **Focused tracked Work Item.** Before creating a new issue, read provider state
   and **resume the existing same-purpose Work Item** when one already owns the
   outcome. Otherwise create one focused tracked Work Item with a desired outcome,
   bounded acceptance criteria, scope/exclusions and an explicit admission
   condition or state.
4. **Explicit admission condition.** The tracked Work Item must say what later
   observation or owner choice would justify implementation. **Issue creation is
   not implementation admission.** A capture-only Work Item does not automatically
   become active WIP, does not automatically receive `roadmap:now`, and does not
   authorize a branch, Pull Request or source mutation for the finding.
5. **Implementation only after separate admission.** Implementation may begin only
   after a separately observable owner/admission step re-binds current provider and
   source state, selects the outcome, applies the current change classification,
   confirms any required Decision authority and pre-implementation evidence, and
   declares the allowed effect boundary.

The ordinary verification-first, Change Request, exact-head CI, effect-authority,
read-back, reconciliation and close-last controls continue after admission. This
requirement adds a provenance/admission boundary; it does not replace those
controls.

## When no issue is required yet

A lesson, risk, method hypothesis or possible improvement that does not yet name a
concrete independently actionable outcome may remain **knowledge-only**. It should
stay in canonical knowledge with its admission condition until evidence or owner
selection makes focused work worth tracking. Creating speculative issues solely to
mirror every sentence of a retrospective is not required.

## Backlog versus active work

A Work Item created only to preserve a concrete finding is backlog capture. It
**does not automatically become active WIP** and should not automatically receive
`roadmap:now`. Promotion to active work is the separate admission event described
above. This prevents retrospective output from silently expanding current scope.

## Agent stop rule

When an agent encounters an unadmitted finding that suggests implementation, it
must stop before implementing that finding. It reads provider state, resumes the
same-purpose Work Item or creates the focused tracked Work Item if none exists,
records the admission condition, and returns to the admitted task. It must not
interpret issue creation, a green test unrelated to the finding, or the existence
of a suggested fix as implementation authority.

## Emergency boundary

The existing emergency route remains authoritative. This requirement does not
remove or delay contract-declared emergency effects; required follow-up records,
evidence and retrospective learning still use the ordinary emergency semantics in
`policy/change-control.yaml`.

## Enforcement

The invariant is routed through the top-level Gnostoa `AGENTS.md` and the bounded
self-hosted delivery runbook. Repository regression tests verify that the canonical
Requirement, router, runbook and knowledge index continue to expose the rule.
Generic consumer change-control schemas are not expanded solely to encode this
Gnostoa-self specialization.
