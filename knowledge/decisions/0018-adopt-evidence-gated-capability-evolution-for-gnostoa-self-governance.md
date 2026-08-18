---
type: Decision
title: Adopt evidence-gated capability evolution for Gnostoa self-governance
description: Adopt the failure-driven, evidence-gated capability-evolution method as canonical for maintaining and evolving Gnostoa itself, without promoting it to generic guidance for adopting projects.
status: draft
generated:
  by: human:ktogias
  at: "2026-08-18T10:15:00Z"
sources:
  - id: canonicalization-work-item
    resource: https://github.com/ktogias/gnostoa/issues/37
    title: Canonicalize and dogfood evidence-gated capability evolution
  - id: evidence-primitive-selection
    resource: https://github.com/ktogias/gnostoa/issues/35
    title: Select one bounded evidence primitive after the C4-v0 falsification
x-project-knowledge:
  id: kit.decision.0018.adopt-evidence-gated-capability-evolution-for-gnostoa-self-governance
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md
    - kind: governs
      target: /lifecycles/evidence-gated-capability-evolution.md
    - kind: references
      target: /contracts/public-inheritance-surface.md
    - kind: references
      target: /assessments/post-c4-evidence-boundary-selection.md
---

# Adopt evidence-gated capability evolution for Gnostoa self-governance

Recorded by `agent:claude-opus-5` from the accountable maintainer's disposition.
The semantic choice is the maintainer's; this record is faithful transcription.

## Context

Gnostoa has learned a repeatable way of evolving its own workflow, governance and
control capabilities, and it learned it from its own failures rather than from
design. B1 established the need. B2/P1 and B2/P2 measured what a bounded envelope
and projection do and do not provide. The post-effect drift record showed
authorized effects outrunning the projections that describe them. The
control-selection research produced a failure taxonomy. C4-v0 tested one selected
control and was **refuted**, and the post-C4 research then declined to select any
evidence primitive at all.

The resulting method is durable as evidence and scattered as method. A fresh
agent can reconstruct it, but only by synthesizing Decision 0016, several
assessments, a failure-mode record, the roadmap projections and a series of owner
dispositions. For a project whose stated goal includes bounded, durable
human-agent continuation, requiring that synthesis is itself a dogfooding
failure — and it is the kind of failure this project has repeatedly found to
precede wasted implementation.

What is missing is not more evidence. It is one canonical route.

## Decision

**A.** Gnostoa self-governance adopts an **evidence-gated, failure-driven
capability-evolution method**.

**B.** The method is **canonical for Gnostoa self-maintenance and agent
continuation**. A fresh agent must be routed to it before proposing
implementation of a new workflow, governance, evidence or control capability.

**C.** It is **not** generic or public guidance for adopting projects. It stays
outside the public inheritance surface, and outside `guidance/` and `templates/`.

**D.** Public or general promotion requires **independent transfer evidence and a
separate owner Decision**. Gnostoa self-dogfood success does not establish
adopter value.

**E.** **Negative experiment outcomes are valid**, and may **remove** rather than
enlarge a mechanism. A refuted hypothesis is a result, not a defect to be rescued
by adding features.

**F.** New capability or control implementation is **not inferred** merely
because a direction was researched or selected. Selected, admitted, implemented,
validated and promoted are five different states.

**G.** The method **does not replace human semantic judgement** where the
available oracle or evidence cannot establish the fact. Human review is not a
temporary defect to be automated away.

**H.** The routing precursor selected by Work Item #35 remains **selected for a
future experiment, and is not implemented and not activated** by this Decision.

This Decision **operationalizes and refines Decision 0016's capability loop**. It
does not amend Decision 0016's numbered increment sequence, and Decision 0016
remains the governing historical architecture.

## Consequences

- The method becomes discoverable through the ordinary repository entry route
  rather than through conversation history or an informed session.
- One canonical lifecycle record carries the method; the empirical records that
  produced it stay canonical for their own facts and are linked, not copied.
- Adopting projects gain nothing from this Decision, by design. That cost is
  accepted in exchange for not exporting a method that has been validated only
  against a single project's history.
- Canonical authority and knowledge-lifecycle maturity are **not** the same
  thing. The method is owner-adopted for self-governance while the lifecycle
  record's status remains `draft`; promoting that record to `stable` would be a
  distinct human verification choice under the repository's own rules.
- The method must not harden into doctrine. It records uncertainty and negative
  results, and a later slice may contradict it with evidence — which is the only
  way this Decision expects to be revised.
- Whether the canonicalization actually works is **not** established by this
  Decision. It is a claim to be falsified by a fresh-agent continuation test
  recorded alongside the lifecycle.
