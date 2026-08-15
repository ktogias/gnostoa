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

## Current first-publication milestone

The first publication target is a bounded `v0.1.0` source, CLI, container and
documentation release. It is not the completion of the wider workflow vision.
The release should make the implemented validation foundation useful and
inspectable while presenting the self-dogfood bootstrap, its defect-discovery
value and its manual process cost honestly.

The accountable owner accepted PR #2 head
`2b0945c2c2882fb4cf35a5e7e08ad3134addacf6` as the inner publication baseline.
Its canonical-target manifest is
`94bfefc7bfedec54c83e4edb8986577336fe22403e5cd4bac02d609a6370f02f`.
That exact acceptance remains immutable provenance; it was not a merge,
visibility change, stable-concept promotion or artifact release.

Follow-up publication work was then accumulated through PRs #16–#23. The
pre-cleanup cumulative review basis is PR #23 head
`049446b4bfe27103da2d6a9f43531e621cfcbd80`, which contains the accepted PR #2
head and is 21 commits ahead and 0 behind the current private `main`. Its
policy, fast, regression, smoke and remote extended checks pass. This is
correlated technical evidence for a later exact owner review, not acceptance
of the cumulative source or authorization to integrate or publish it.

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

### Current GO gates

As observed by the 2026-08-15
[provider audit](../assessments/first-publication-provider-audit.md), the
remaining source-publication gates are:

1. commit and review the publication-cleanup candidate, then reconcile the
   exact cumulative PR body and Issue #1 with the same final head, scope,
   evidence and next action;
2. record an owner disposition on the current disclosure surface, including 11
   remote branches, 25 reachable commits, 49 Actions runs, four retained
   artifacts, the maintainer commit identity and the retained multilingual
   collaboration history;
3. **complete:** the owner-confirmed Decision 0009
   [name-risk screening](../assessments/gnostoa-source-name-screening.md)
   records a source-only `CONDITIONAL GO` for Greece, the EU and Nice classes
   9 and 42;
4. authorize the repository visibility change while leaving `main` unchanged,
   then enable and verify required protection before integration; and
5. re-run exact-head checks, anonymous-reader links and disclosure scans after
   the visibility transition and before the cumulative merge.

The completed 2026-08-15 screening found no exact `GNOSTOA` register result or
relevant exact third-party software identity in the bounded search. It retained
active `JOTSON` and `NEOTOA` records as differentiated residual risks and kept
crates.io inconclusive. This is explicit owner risk acceptance for source
visibility only, not legal or registry clearance. Independent or professional
review still gates stable artifact branding, trade-mark filing and commercial
reliance. Gate 3 is complete; it grants none of the remaining publication
effects.

Disclosure view V4 and the earlier PR #2/Issue #1 summaries remain historical
records of their exact earlier basis. They are no longer current enough to
authorize publication: V4 covered only 3 branches, 15 commits, 25 Actions runs
and no retained artifacts, while the current surface is larger.

PR #2 and PRs #16–#22 contain useful work and review history. Once an exact
comparison against the final cumulative candidate succeeds, they should be
described as **absorbed provenance**, not discarded work: their commits and
records are carried into one cumulative integration candidate and remain
linked for reconstruction. Their branches are not deleted before successful
integration and read-back.

PR #4 remains useful Research input for Issue #3. It is retained outside the
first-publication baseline because its current head is conflicting and its
eight review findings remain unresolved. Parking or closing that PR must retain
its exact head, branch, findings and restart conditions; it is not a rejection
or deletion of the work.

The source-publication gates above are distinct from package, image and site
release gates. Package metadata enrichment, authoritative release-smoke CI,
OS/base-image inventory, legal compatibility review and signed provenance may
follow a bounded source publication and are not silently represented as
complete by it.

### Next validation path

After the first release, B2 applies the same toolkit to one small, predeclared
Gnostoa change with a bounded evidence budget. It compares assurance,
decision time, review rounds, evidence amplification, owner effort, recovery
and escaped defects with the measured B1 manual bootstrap. B3 then tests one
bounded adoption in an independently owned project. External value claims are
earned from B3 evidence rather than inferred from the size of Gnostoa's own
ledger.
