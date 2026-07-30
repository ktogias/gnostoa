---
type: Runbook
title: Review the publication baseline
description: Traverse Gnostoa's canonical guidance and self-knowledge once before public publication without a formal sign-off ledger.
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
- The accountable owner performing the publication review is identified. The
  owner may also be the author; software agents provide evidence but do not
  replace human semantic judgment.
- Automated policy, bundle, link, schema and test evidence is green for the
  reviewed revision.

## Procedure

1. Review the public inheritance boundary before reviewing individual
   documents. Reject vocabulary, controls or operating assumptions that belong
   only to a downstream project.
2. Use the matrix to traverse each canonical source once. Record actionable
   concerns as Pull Request comments or linked Work Items. Per-row outcome,
   signature or attestation fields are not required.
3. Check source authority, internal consistency, genericity, ownership,
   lifecycle status and compatibility impact. Automated structural validation
   is evidence, not a substitute for semantic judgment.
4. Resolve publication blockers in the Change Request. Do not add `human:`
   metadata unless the named person actually verified a concept being promoted
   to `stable`.
5. For every promotion candidate, update the concept in a reviewed revision
   with explicit human verification. Keep exploratory or unsettled concepts as
   draft.
6. Resolve review conversations or track non-blocking follow-up separately. A
   deferred publication blocker keeps the repository private.

### Reusable guidance

| Canonical concept | Review focus | Optional note | Last checked by |
|---|---|---|---|
| [Non-negotiable guardrails](../../guidance/guardrails/non-negotiable.md) | Minimal portable invariants | — | — |
| [Policy, guidance and self separation](../../guidance/patterns/policy-guidance-self-separation.md) | Authority boundaries and cognitive load | — | — |
| [Protected lightweight change flow](../../guidance/patterns/protected-short-lived-change-flow.md) | Provider neutrality and low-friction enforceability | — | — |
| [Tiered CI and local feedback](../../guidance/patterns/tiered-ci-and-local-feedback.md) | CI authority and feedback cost | — | — |
| [Proportionate verification](../../guidance/patterns/verification-first-development.md) | Evidence proportionality and optional test-first paths | — | — |
| [Established patterns](../../guidance/practices/established-patterns.md) | Accuracy and separation of concerns | — | — |
| [Source authority and lifecycle](../../guidance/practices/source-authority-and-lifecycle.md) | Provenance and generated-content limits | — | — |
| [Change classification and review](../../guidance/reference/change-classification-and-approval.md) | Lightweight baseline and stricter specialization semantics | — | — |
| [Continuous-integration contract](../../guidance/reference/continuous-integration-contract.md) | Event, suite and evidence vocabulary | — | — |
| [Profile authoring](../../guidance/reference/profile-authoring.md) | Inheritance and non-weakening rules | — | — |
| [Repository layout and distribution](../../guidance/reference/repository-layout-and-distribution.md) | Portable placement and pinning choices | — | — |
| [Runtime and distribution](../../guidance/reference/runtime-and-distribution.md) | Container-first contract and fallback | — | — |
| [Testing and verification strategy](../../guidance/reference/testing-and-verification-strategy.md) | Behavior focus and test portfolio | — | — |
| [Tool selection](../../guidance/reference/tool-selection.md) | Replaceability and optional-tool boundaries | — | — |
| [Versioning and upgrades](../../guidance/reference/versioning-and-upgrades.md) | Compatibility and migration semantics | — | — |
| [Adopt an existing project](../../guidance/workflows/adopt-existing-project.md) | Incremental adoption and legacy quarantine | — | — |
| [Bootstrap a new project](../../guidance/workflows/bootstrap-new-project.md) | Minimal start and executable steps | — | — |
| [Configure continuous integration](../../guidance/workflows/configure-continuous-integration.md) | Provider mapping and required evidence | — | — |
| [Create a specialization](../../guidance/workflows/create-specialization.md) | Justified extension and scope isolation | — | — |
| [Daily change loop](../../guidance/workflows/daily-change-loop.md) | Routine usability for people and agents | — | — |
| [Develop with proportionate verification](../../guidance/workflows/develop-verification-first.md) | Final, Red, characterization and semantic paths | — | — |
| [Propose, review and merge](../../guidance/workflows/propose-review-merge-change.md) | Complete protected change lifecycle | — | — |

### Toolkit self-knowledge

| Canonical concept | Review focus | Optional note | Last checked by |
|---|---|---|---|
| [Knowledge surfaces](../architecture/knowledge-surfaces.md) | Public, guidance and self boundaries | — | — |
| [Public inheritance surface](../contracts/public-inheritance-surface.md) | Consumer contract and failure semantics | — | — |
| [OKF as canonical format](../decisions/0001-okf-as-canonical-format.md) | Canonical-format rationale and cost | — | — |
| [Profile inheritance](../decisions/0002-profile-inheritance.md) | Extension semantics and compatibility | — | — |
| [Derived retrieval layers](../decisions/0003-derived-retrieval-layers.md) | Replaceability and authority | — | — |
| [Self-hosted surfaces](../decisions/0004-self-host-policy-guidance-and-knowledge.md) | Drift prevention without consumer leakage | — | — |
| [Container-first runtime](../decisions/0005-container-first-runtime.md) | Language neutrality and operational cost | — | — |
| [Provider-neutral governance](../decisions/0006-provider-neutral-change-governance.md) | Bootstrap exception and protection | — | — |
| [Proportionate verification](../decisions/0007-verification-first-development.md) | Lightweight evidence requirements and stricter options | — | — |
| [Authoritative tiered CI](../decisions/0008-authoritative-tiered-continuous-integration.md) | Central authority and provider mapping | — | — |
| [Gnostoa project name](../decisions/0009-adopt-gnostoa-project-name.md) | Identity, genericity and clearance | — | — |
| [Apache-2.0 licensing](../decisions/0010-license-gnostoa-under-apache-2.0.md) | License scope and downstream independence | — | — |
| [Initial copyright ownership](../decisions/0011-record-initial-copyright-ownership.md) | Ownership and contribution model | — | — |
| [Versioned schema identifiers](../decisions/0012-use-versioned-public-schema-identifiers.md) | Permanence, ownership and version policy | — | — |
| [Deferred private-repository enforcement](../decisions/0013-defer-provider-enforcement-while-private.md) | Provider limitation, expiry and compensating controls | — | — |
| [Stricter Gnostoa self-governance](../decisions/0014-strengthen-gnostoa-self-governance.md) | Internal issue, Decision and evidence chronology without consumer leakage | — | — |
| [Toolkit evolution](../lifecycles/toolkit-evolution.md) | Lifecycle stages and drift controls | — | — |
| [Gnostoa project](../project/gnostoa.md) | Product purpose and scope | — | — |
| [Centralized CI verifies candidates](../requirements/centralized-ci-verifies-integration-candidates.md) | Required candidate evidence | — | — |
| [Prevent policy drift](../requirements/prevent-policy-drift.md) | Mechanical and semantic enforcement | — | — |
| [Traceable change control](../requirements/reviewed-change-control.md) | Solo/community usability and traceability | — | — |
| [Verification precedes integration](../requirements/verification-precedes-implementation.md) | Observable intent and evidence timing | — | — |
| [Maintain the toolkit](maintain-the-kit.md) | Executable maintainer workflow | — | — |

## Verification

- The matrix links every canonical concept exactly through its source path.
- The accountable owner traversed the matrix and resolved all publication
  blockers without a separate per-row attestation exercise.
- Stable concepts contain actual `human:` verification metadata.
- Required CI passes on the latest Change Request revision.
- Repository visibility remains private until the final source-only audit
  reports GO.

## Recovery

If review scope becomes too large, keep the repository private and split
revisions by canonical surface. If material new commits arrive after review,
revisit the affected concepts and latest diff; no fixed waiting period applies.
