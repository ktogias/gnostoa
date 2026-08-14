---
type: Project
title: Gnostoa
description: Self-description of Gnostoa, the generic project knowledge toolkit.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-14T00:00:00Z"
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

The exact source-baseline candidate at
`2b0945c2c2882fb4cf35a5e7e08ad3134addacf6` has completed accountable-owner
semantic review. Its canonical-target manifest is
`94bfefc7bfedec54c83e4edb8986577336fe22403e5cd4bac02d609a6370f02f`.
This is candidate acceptance for later protected integration, not a merge,
visibility change, stable-concept promotion or artifact release. The
repository remains private and PR 2 remains open, draft and unmerged.

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

As observed after provider-body reconciliation on 2026-08-14, the remaining
source-publication gates are:

1. an owner disposition on disclosure-set V4, which contains the branch
   history commit email, reconciled multilingual collaboration history and the
   explicitly unfinished stacked PR 4;
2. independent name and trademark clearance for `Gnostoa`;
3. a separately authorized and verified visibility-and-protection transition.
   The current private provider plan exposes no effective protection or
   ruleset on the three branches, so protection must be verified before any
   integration.

A bounded exact-string screening on 2026-08-14 found no obvious collision in
the accessible GitHub, PyPI, npm or indexed-web results; crates.io remained
inconclusive. This is not legal or registry clearance. Decision 0009 records
the official OBI, EUIPO/TMview and WIPO route still required for similar-mark,
goods-and-services and territory review. Gate 2 therefore remains open.

The PR 2 and Issue 1 provider descriptions are now reconciled to the accepted
head and completed review. Their exact body SHA-256 values are
`85e60269c7373183c1d87e396fed6fc2895a982f65fb62d936ede706f04a47a6` and
`d91fe04b19da2e7fefe496874b694a3f17e45d9c4d4738021e49f42761f36f5f`
respectively. That completed projection repair is not another semantic source
acceptance.

PR 4 may be finished, deferred or closed, or it may remain visible only as the
clearly labelled unfinished work described by an accepted disclosure set. It
must not appear to be accepted or release-ready accidentally.

### Next validation path

After the first release, B2 applies the same toolkit to one small, predeclared
Gnostoa change with a bounded evidence budget. It compares assurance,
decision time, review rounds, evidence amplification, owner effort, recovery
and escaped defects with the measured B1 manual bootstrap. B3 then tests one
bounded adoption in an independently owned project. External value claims are
earned from B3 evidence rather than inferred from the size of Gnostoa's own
ledger.
