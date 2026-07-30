---
type: Runbook
title: Review the publication baseline
description: Conduct one bounded human semantic review of Gnostoa's canonical guidance and self-knowledge before public publication.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-07-30T00:00:00Z"
sources:
  - id: publication-baseline-work-item
    resource: https://github.com/ktogias/gnostoa/issues/1
    title: Prepare the protected Gnostoa publication baseline
x-project-knowledge:
  id: kit.runbook.review-publication-baseline
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: verifies
      target: /contracts/public-inheritance-surface.md
    - kind: verifies
      target: /requirements/reviewed-change-control.md
    - kind: references
      target: /decisions/0009-adopt-gnostoa-project-name.md
---

# Review the publication baseline

## Preconditions

- The source repository remains private.
- The pre-publication audit and its remediation Work Item are available.
- The review targets one immutable Change Request revision.
- An independent human reviewer is identified. The author and software agents
  do not count as independent approval.
- Automated policy, bundle, link, schema and test evidence is green for the
  reviewed revision.

## Procedure

1. Review the public inheritance boundary before reviewing individual
   documents. Reject vocabulary, controls or operating assumptions that belong
   only to a downstream project.
2. Review each row in the matrix against its canonical source. Use one of these
   outcomes:
   - `accept-draft`: coherent and safe to publish as explicitly unfinished;
   - `promotion-candidate`: authoritative enough to become `stable` after its
     human verification metadata is recorded;
   - `revise`: publication remains blocked until the linked concern is fixed.
3. Check source authority, internal consistency, genericity, ownership,
   lifecycle status and compatibility impact. Automated structural validation
   is evidence, not a substitute for semantic judgment.
4. Record the reviewer and outcome in the Change Request. Do not replace
   `pending` below or add `human:` metadata unless the named person actually
   completed that review.
5. For every promotion candidate, update the concept in a reviewed revision
   with explicit human verification. Keep exploratory or unsettled concepts as
   draft.
6. Resolve review conversations or defer them to linked Work Items. A deferred
   publication blocker keeps the repository private.

### Reusable guidance

| Canonical concept | Review focus | Outcome | Human verifier |
|---|---|---|---|
| [Non-negotiable guardrails](../../guidance/guardrails/non-negotiable.md) | Minimal portable invariants | pending | — |
| [Policy, guidance and self separation](../../guidance/patterns/policy-guidance-self-separation.md) | Authority boundaries and cognitive load | pending | — |
| [Protected short-lived change flow](../../guidance/patterns/protected-short-lived-change-flow.md) | Provider neutrality and enforceability | pending | — |
| [Tiered CI and local feedback](../../guidance/patterns/tiered-ci-and-local-feedback.md) | CI authority and feedback cost | pending | — |
| [Verification-first development](../../guidance/patterns/verification-first-development.md) | Proportionate evidence and exceptions | pending | — |
| [Established patterns](../../guidance/practices/established-patterns.md) | Accuracy and separation of concerns | pending | — |
| [Source authority and lifecycle](../../guidance/practices/source-authority-and-lifecycle.md) | Provenance and generated-content limits | pending | — |
| [Change classification and approval](../../guidance/reference/change-classification-and-approval.md) | Risk classes and approval semantics | pending | — |
| [Continuous-integration contract](../../guidance/reference/continuous-integration-contract.md) | Event, suite and evidence vocabulary | pending | — |
| [Profile authoring](../../guidance/reference/profile-authoring.md) | Inheritance and non-weakening rules | pending | — |
| [Repository layout and distribution](../../guidance/reference/repository-layout-and-distribution.md) | Portable placement and pinning choices | pending | — |
| [Runtime and distribution](../../guidance/reference/runtime-and-distribution.md) | Container-first contract and fallback | pending | — |
| [Testing and verification strategy](../../guidance/reference/testing-and-verification-strategy.md) | Behavior focus and test portfolio | pending | — |
| [Tool selection](../../guidance/reference/tool-selection.md) | Replaceability and optional-tool boundaries | pending | — |
| [Versioning and upgrades](../../guidance/reference/versioning-and-upgrades.md) | Compatibility and migration semantics | pending | — |
| [Adopt an existing project](../../guidance/workflows/adopt-existing-project.md) | Incremental adoption and legacy quarantine | pending | — |
| [Bootstrap a new project](../../guidance/workflows/bootstrap-new-project.md) | Minimal start and executable steps | pending | — |
| [Configure continuous integration](../../guidance/workflows/configure-continuous-integration.md) | Provider mapping and required evidence | pending | — |
| [Create a specialization](../../guidance/workflows/create-specialization.md) | Justified extension and scope isolation | pending | — |
| [Daily change loop](../../guidance/workflows/daily-change-loop.md) | Routine usability for people and agents | pending | — |
| [Develop with verification first](../../guidance/workflows/develop-verification-first.md) | Red/characterization/semantic paths | pending | — |
| [Propose, review and merge](../../guidance/workflows/propose-review-merge-change.md) | Complete protected change lifecycle | pending | — |

### Toolkit self-knowledge

| Canonical concept | Review focus | Outcome | Human verifier |
|---|---|---|---|
| [Knowledge surfaces](../architecture/knowledge-surfaces.md) | Public, guidance and self boundaries | pending | — |
| [Public inheritance surface](../contracts/public-inheritance-surface.md) | Consumer contract and failure semantics | pending | — |
| [OKF as canonical format](../decisions/0001-okf-as-canonical-format.md) | Canonical-format rationale and cost | pending | — |
| [Profile inheritance](../decisions/0002-profile-inheritance.md) | Extension semantics and compatibility | pending | — |
| [Derived retrieval layers](../decisions/0003-derived-retrieval-layers.md) | Replaceability and authority | pending | — |
| [Self-hosted surfaces](../decisions/0004-self-host-policy-guidance-and-knowledge.md) | Drift prevention without consumer leakage | pending | — |
| [Container-first runtime](../decisions/0005-container-first-runtime.md) | Language neutrality and operational cost | pending | — |
| [Provider-neutral governance](../decisions/0006-provider-neutral-change-governance.md) | Bootstrap exception and protection | pending | — |
| [Verification-first development](../decisions/0007-verification-first-development.md) | Evidence requirements and exceptions | pending | — |
| [Authoritative tiered CI](../decisions/0008-authoritative-tiered-continuous-integration.md) | Central authority and provider mapping | pending | — |
| [Gnostoa project name](../decisions/0009-adopt-gnostoa-project-name.md) | Identity, genericity and clearance | pending | — |
| [Apache-2.0 licensing](../decisions/0010-license-gnostoa-under-apache-2.0.md) | License scope and downstream independence | pending | — |
| [Initial copyright ownership](../decisions/0011-record-initial-copyright-ownership.md) | Ownership and contribution model | pending | — |
| [Versioned schema identifiers](../decisions/0012-use-versioned-public-schema-identifiers.md) | Permanence, ownership and version policy | pending | — |
| [Deferred private-repository enforcement](../decisions/0013-defer-provider-enforcement-while-private.md) | Provider limitation, expiry and compensating controls | pending | — |
| [Toolkit evolution](../lifecycles/toolkit-evolution.md) | Lifecycle stages and drift controls | pending | — |
| [Gnostoa project](../project/gnostoa.md) | Product purpose and scope | pending | — |
| [Centralized CI verifies candidates](../requirements/centralized-ci-verifies-integration-candidates.md) | Required candidate evidence | pending | — |
| [Prevent policy drift](../requirements/prevent-policy-drift.md) | Mechanical and semantic enforcement | pending | — |
| [Reviewed change control](../requirements/reviewed-change-control.md) | Independent authority and traceability | pending | — |
| [Verification precedes implementation](../requirements/verification-precedes-implementation.md) | Observable intent and evidence timing | pending | — |
| [Maintain the toolkit](maintain-the-kit.md) | Executable maintainer workflow | pending | — |

## Verification

- The matrix links every canonical concept exactly through its source path.
- No row remains `pending` at the publication gate.
- Every `revise` outcome is resolved in the reviewed revision or linked to a
  Work Item that explicitly keeps publication blocked.
- Stable concepts contain actual `human:` verification metadata.
- The independent reviewer approves the latest Change Request revision after
  required CI and CODEOWNER checks pass.
- Repository visibility remains private until the final source-only audit
  reports GO.

## Recovery

If review scope becomes too large, keep the repository private and split
revisions by canonical surface without weakening the complete-matrix gate. If a
reviewer withdraws or new commits invalidate approval, return affected rows to
`pending` and repeat review on the latest revision.
