---
type: Project
title: Gnostoa
description: Self-description of Gnostoa, the generic project knowledge toolkit.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-15T00:00:00Z"
sources:
  - id: publication-baseline-change-request
    resource: https://github.com/ktogias/gnostoa/pull/2
    title: Prepare the Gnostoa publication baseline
  - id: final-publication-baseline-disposition
    resource: https://github.com/ktogias/gnostoa/pull/2#issuecomment-5294119830
    title: Final exact-head owner disposition for PR 2
  - id: source-publication-disclosure-view-v4
    resource: https://github.com/ktogias/gnostoa/pull/2#issuecomment-5296808873
    title: Public-exposure decision view V4
  - id: cumulative-publication-candidate
    resource: https://github.com/ktogias/gnostoa/pull/23
    title: Cumulative first-publication candidate
  - id: public-source-baseline
    resource: https://github.com/ktogias/gnostoa/commit/cda51dad6a719da43d8465a3f0f270021c357d96
    title: Integrated protected public source baseline
  - id: source-name-screening
    resource: ../assessments/gnostoa-source-name-screening.md
    title: Gnostoa source-publication name-risk screening
x-project-knowledge:
  id: kit.project
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: contains
      target: /architecture/knowledge-surfaces.md
    - kind: governed-by
      target: /contracts/public-inheritance-surface.md
    - kind: implements
      target: /requirements/prevent-policy-drift.md
    - kind: implements
      target: /requirements/reviewed-change-control.md
    - kind: implements
      target: /requirements/verification-precedes-implementation.md
    - kind: implements
      target: /requirements/centralized-ci-verifies-integration-candidates.md
    - kind: contains
      target: /lifecycles/toolkit-evolution.md
    - kind: references
      target: /assessments/gnostoa-self-dogfood-bootstrap-assessment.md
    - kind: references
      target: /assessments/first-publication-provider-audit.md
    - kind: references
      target: /assessments/gnostoa-source-name-screening.md
    - kind: references
      target: /assessments/human-agent-governance-scope-and-evolution.md
    - kind: references
      target: /runbooks/prepare-first-publication.md
---

# Gnostoa

Gnostoa provides a technology-neutral profile, validation tools, reusable
operating guidance and anonymous examples for Git-native project knowledge.

Gnostoa's public value is its complete reusable public surface: normative
profiles, policies and schemas; supporting validation tools and runtime
behavior; operating guidance, workflows and patterns; anonymous templates and
examples; and documented CI integration. The public contract binds these
artifacts into a coherent inheritance surface and versions that surface as a
unit. It defines what consumers may rely on, inherit or consult, while
preserving each artifact's distinct authority rather than making every artifact
equally normative.

Its internal design history and maintenance procedures stay in this
self-knowledge bundle so consumers do not pay for irrelevant context.

## Current public source baseline

On 2026-08-16 the first source-publication Work Item completed. Public,
protected `main` is at exact commit
`cda51dad6a719da43d8465a3f0f270021c357d96`; cumulative PR #23 is integrated
and Issue #1 is closed. The repository exposes a bounded pre-release source
baseline, not a package, OCI image, documentation-site release, stable concept
promotion or production-readiness claim.

### Publication provenance

The accountable owner accepted PR #2 head
`2b0945c2c2882fb4cf35a5e7e08ad3134addacf6` as the inner publication baseline.
Its canonical-target manifest is
`94bfefc7bfedec54c83e4edb8986577336fe22403e5cd4bac02d609a6370f02f`.
That exact acceptance remains immutable provenance; it was not a merge,
visibility change, stable-concept promotion or artifact release.

Follow-up publication work accumulated through PRs #16–#23 and was reconciled
into the protected public baseline above. PR #2 and PRs #16–#22 remain absorbed
provenance: useful review and implementation history carried into PR #23, not
discarded branches or independent current release candidates.

### First-release surface

The bounded release surface contains:

- versioned schemas and the generic and Gnostoa profiles;
- deterministic bundle, policy and guardrail validation;
- inherited non-weakening change-control and CI-policy checks;
- bounded context-pack and documentation projections;
- provider-neutral guidance, anonymous examples and templates;
- the native command surface plus a pinned, non-root OCI route; and
- an evidence-bounded account of Gnostoa as its own first reference consumer.

The release does not claim independent adoption, net productivity gain,
production maturity, complete workflow automation, effective external
compatibility or migration contracts, or stable status for the current draft
knowledge corpus. Issues 5–15 are not automatically first-publication blockers;
only a concrete security, legal, correctness or exposure defect can make their
scope a prerequisite.

### Completed source-publication boundary

The publication cleanup, exact cumulative review, bounded name-risk
disposition, disclosure, visibility transition, protection, anonymous
read-back and protected integration are complete for the source baseline at
`cda51dad6a719da43d8465a3f0f270021c357d96`. The dated
[provider audit](../assessments/first-publication-provider-audit.md), disclosure
views and PR records remain immutable evidence of their observed stages; they
are not current gates.

The source-only name-risk disposition is not legal or registry clearance.
Independent or professional review still gates stable artifact branding,
trade-mark filing and commercial reliance.

PR #4 remains useful Research input for Issue #3. It is retained outside the
first-publication baseline because its current head is conflicting and its
eight review findings remain unresolved. Parking or closing that PR must retain
its exact head, branch, findings and restart conditions; it is not a rejection
or deletion of the work.

Package, image and site release remain separate. OS/base-image inventory,
legal compatibility review, publisher identity and signed provenance are not
silently represented as complete by source publication.

### Next validation path

[Issue #24](https://github.com/ktogias/gnostoa/issues/24) now applies the toolkit
to one small, predeclared Gnostoa change with a bounded evidence and human
attention budget.
The need for durable context, handoffs, bounded plans and safe resume is already
demonstrated. [Decision 0016](../decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md)
uses B2 to select and dogfood the minimum task-envelope/current-projection
slice. B2 compares assurance, decision time, review rounds, evidence
amplification, owner effort, recovery and escaped defects with the measured B1
manual bootstrap. The raw Issue #12 and PR #2 ledger remains historical
evidence, not the expected contributor workflow. B3 then tests one bounded
adoption in an independently owned project. External value claims are earned
from B3 evidence rather than inferred from the size of Gnostoa's own ledger.

The bounded findings and scope interpretation from the external shared
conversation are recorded in the
[human-agent governance assessment](../assessments/human-agent-governance-scope-and-evolution.md).
