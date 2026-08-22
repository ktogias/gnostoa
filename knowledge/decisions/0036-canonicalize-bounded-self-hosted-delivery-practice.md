---
type: Decision
title: Canonicalize bounded self-hosted delivery practice
description: Select one short Gnostoa-self ordinary-delivery runbook, explicit subject re-binding and compact task prompts while preserving the evidence-gated lifecycle and specialized release authorities.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-22T07:25:33Z"
sources:
  - id: delivery-practice-work-item
    resource: https://github.com/ktogias/gnostoa/issues/80
    title: Canonicalize bounded self-hosted delivery practice
x-project-knowledge:
  id: kit.decision.0036.canonicalize-bounded-self-hosted-delivery-practice
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md
    - kind: references
      target: /decisions/0018-adopt-evidence-gated-capability-evolution-for-gnostoa-self-governance.md
    - kind: references
      target: /lifecycles/evidence-gated-capability-evolution.md
    - kind: references
      target: /decisions/0024-separate-stable-navigation-from-volatile-state.md
    - kind: references
      target: /decisions/0035-accept-bounded-first-party-source-security-sufficiency-for-the-first-oci-candidate.md
    - kind: references
      target: /assessments/self-hosted-delivery-practice-retrospective.md
    - kind: governs
      target: /runbooks/deliver-bounded-self-hosted-slice.md
---

# Canonicalize bounded self-hosted delivery practice

Recorded by `codex/gpt-5` from the accountable maintainer's disposition. The
semantic choice is the maintainer's; this record is faithful transcription.

Scope: **ordinary bounded delivery of changes to Gnostoa itself.**

## Context

B2, source release, OCI/security preparation, drift reconciliation and G3
repeated an ordinary operational sequence that remained split across the
evidence-gated lifecycle, generic change guidance, a specialized release
runbook, failure records and candidate PRs. The bounded
[retrospective](../assessments/self-hosted-delivery-practice-retrospective.md)
found the epistemic method already canonical, but exact-head verification,
integrated read-back, subject re-binding and close-last operational practice
insufficiently discoverable as one ordinary route.

## Decision

**A.** Select one short self-only ordinary-delivery runbook:
[Deliver a bounded self-hosted slice](../runbooks/deliver-bounded-self-hosted-slice.md).

**B.** The existing
[evidence-gated capability-evolution lifecycle](../lifecycles/evidence-gated-capability-evolution.md)
remains authoritative for epistemic order, A–D gap classes,
selection/admission, oracle limits, falsifiable evolution and negative results.
The ordinary runbook links to those semantics and does not restate them.

**C.** Evidence binds to the **measured subject**, not merely to the commit SHA
that contained it.

**D.** A later SHA alone does not invalidate prior evidence. Reuse requires
explicit read-back proving the relevant executable, runtime, provider or other
measured subject unchanged.

**E.** A material subject change invalidates the affected evidence and requires
the **smallest affected replay**, not an automatic complete replay. Unaffected
evidence may be retained only after explicit re-binding.

**F.** Repository preparation and provider-effect authority are distinct.
Selection, an integrated preparation diff, local verification or a green
provider run does not authorize a merge or another external effect.

**G.** Verification of an exact PR head and observation of integrated protected
main are distinct evidence. Squash or merge integration creates a new revision
whose source and relevant subject must be read back.

**H.** Provider command success is not provider truth. Required job execution,
the effect, integrated state and lifecycle state are read back authoritatively;
`SKIPPED` is never reported as `PASS`.

**I.** Provider effects are followed by bounded reconciliation. A Work Item that
must survive integration remains open through merge, integrated/provider
read-back, subject re-binding and navigation reconciliation, and is closed last.

**J.** Stable workflow invariants belong in canonical repository knowledge.
Ordinary task prompts should normally carry only the task-specific delta:

- concrete task and any already-selected owner outcome;
- authoritative starting subject or references;
- admitted scope and exclusions;
- task-specific stop or preemption conditions;
- material evidence required;
- explicitly authorized effects, if any; and
- concise output required for the next owner decision.

**K.** There is no fixed prompt token or line limit. A large prompt remains
legitimate when its task-specific delta is genuinely large. Prompt compression
must not hide semantic choices, evidence, uncertainty or stop conditions.

**L.** For this route, `AGENTS.md` is routing only: it points to the lifecycle,
this runbook, Decision 0016, the current roadmap and the active Work Item. It
does not maintain a second epistemic mini-procedure.

**M.** Specialized release and publication semantics stay in their specialized
Decisions and runbooks. Source-defining versus downstream-publication gates,
freshness, tags, Releases, registries, provenance, signing and publication do
not enter the ordinary-delivery runbook.

**N.** The first naturally occurring eligible ordinary bounded slice will
falsify the route with a genuinely fresh agent and a task-specific prompt. No
development task is manufactured for that purpose. Any immediate read-only
orientation exercise is discoverability evidence only, not independent transfer
evidence.

**O.** This Decision is Gnostoa-self only. It creates no generic or adopter
workflow requirement and no transfer claim.

**P.** No workflow engine, provider adapter, state synchronizer, new evidence
primitive, policy, schema, CI mechanism or automated approval is selected.

**Q.** No G4 legal work, CPython refresh, source identity, version, tag, release,
package, OCI image, site publication or deployment authority is created.

## Consequences

- Ordinary delivery has one concise operational entry route without becoming a
  second lifecycle.
- Existing specialized runbooks and generic guidance remain authoritative for
  their own scopes.
- A SHA-only freshness heuristic is rejected in favour of explicit subject
  read-back and proportional evidence replay.
- Canonicalization remains falsifiable; fresh-agent orientation does not imply
  autonomous semantic correctness.
