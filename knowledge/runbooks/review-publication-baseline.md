---
type: Runbook
title: Review the pre-publication source baseline
description: Run an owner-led review of Gnostoa's mandatory canonical-source manifest before integration or source publication.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-07-30T00:00:00Z"
sources:
  - id: publication-baseline-work-item
    resource: https://github.com/ktogias/gnostoa/issues/1
    title: Prepare the Gnostoa publication baseline
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

# Review the pre-publication source baseline

## Purpose and scope

This runbook governs accountable-owner semantic review of one exact private
pre-publication source-baseline candidate. Its immediate decision is whether
that candidate may be accepted and integrated into the default branch as a
private source baseline. It does not itself authorize a repository-visibility
change, source publication or publication of a package, OCI image or site.

The publication lifecycle keeps these states distinct:

1. **Candidate preparation:** a private Change Request assembles and verifies
   a proposed source revision.
2. **Owner acceptance:** the accountable owner accepts the semantics of one
   exact candidate revision.
3. **Default-branch integration:** the accepted revision becomes the private
   integrated source baseline.
4. **Repository visibility and source publication:** a separate authorized
   provider change makes the selected source revision public.
5. **Artifact or site publication:** separately verified packages, images or
   documentation projections are released through their own gates.

Completion of one state never implies or authorizes the next.

The `Reusable guidance` and `Toolkit self-knowledge` matrices below together
form the mandatory canonical-source traversal manifest for this review. They
mirror the direct canonical targets linked by `guidance/index.md` and
`knowledge/index.md`; every such target must appear exactly once in the
applicable matrix. A missing, duplicate, inaccessible or unclassified
canonical target is a publication blocker. This runbook is the controlling
procedure and is not a row in its own manifest.

Review material has four distinct roles:

- **Direct semantic-review targets** are the canonical sources named by the
  two matrices. The accountable owner judges their meaning and suitability.
- **Supporting executable evidence** includes relevant code, schemas, policy,
  tests, configuration and CI results. Follow it when it bears on a target;
  it is not automatically another semantic-review row.
- **Selected history** includes applicable accepted Decisions, Work Items and
  owner records used to understand authority or rationale. Historical records
  remain evidence and are not silently rewritten or automatically rereviewed.
- **Derived projections** include generated sites, search views, context packs
  and mutable session summaries. They are non-canonical and receive separate
  semantic review only when selected as actual publication artifacts.

The accountable owner alone records semantic comments, dispositions and the
final decision for the exact candidate. Agents may preserve exact text,
assemble context, analyze, recommend and record evidence, but cannot supply an
owner disposition. CI may verify declared machine-checkable properties but
cannot establish semantic sufficiency. No separate per-row sign-off ledger is
required: durable review comments and dispositions plus the final exact-revision
decision provide the review trace without duplicating signatures or
attestations for every matrix row.

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

1. Reconcile both matrices with `guidance/index.md` and `knowledge/index.md`.
   Stop on a missing, duplicate, inaccessible or unclassified canonical target.
2. Review the public inheritance boundary before reviewing individual
   documents. Reject vocabulary, controls or operating assumptions that belong
   only to a downstream project.
3. Traverse each matrix row once for the exact candidate revision. Revisit a
   row only when its source changes or an unresolved blocker requires rework.
   Record actionable concerns as Pull Request comments or linked Work Items.
4. Check source authority, internal consistency, genericity, ownership,
   lifecycle status and compatibility impact. Automated structural validation
   is evidence, not a substitute for semantic judgment.
5. Resolve publication blockers in the Change Request. Do not add `human:`
   metadata unless the named person actually verified a concept being promoted
   to `stable`.
6. For every promotion candidate, update the concept in a reviewed revision
   with explicit human verification. Keep exploratory or unsettled concepts as
   draft.
7. Resolve review conversations or track non-blocking follow-up separately. A
   deferred publication blocker keeps the repository private.
8. Reconcile the final exact candidate, affected rows, supporting evidence and
   open follow-up. The accountable owner records the final semantic decision;
   a source-only publication audit records `GO` or `NO-GO` separately.

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
| [Publication-baseline review drift](../failure-modes/publication-baseline-review-drift.md) | Critical-path containment, authority boundaries and recovery | — | — |
| [Gnostoa project](../project/gnostoa.md) | Product purpose and scope | — | — |
| [Centralized CI verifies candidates](../requirements/centralized-ci-verifies-integration-candidates.md) | Required candidate evidence | — | — |
| [Prevent policy drift](../requirements/prevent-policy-drift.md) | Mechanical and semantic enforcement | — | — |
| [Traceable change control](../requirements/reviewed-change-control.md) | Solo/community usability and traceability | — | — |
| [Verification precedes integration](../requirements/verification-precedes-implementation.md) | Observable intent and evidence timing | — | — |
| [Maintain the toolkit](maintain-the-kit.md) | Executable maintainer workflow | — | — |

## Verification

- The two matrices match their canonical indexes, and every direct target is
  classified and linked exactly once through its source path.
- The accountable owner traversed the matrix and resolved all publication
  blockers without a separate per-row attestation exercise.
- Supporting evidence, selected history and derived projections retain their
  distinct authority and are not promoted into canonical targets implicitly.
- Stable concepts contain actual `human:` verification metadata.
- Required CI passes on the latest Change Request revision.
- Repository visibility remains private until the final source-only audit
  reports GO.

## Recovery

If review scope becomes too large, keep the repository private and split
revisions by canonical surface. If material new commits arrive after review,
revisit the affected concepts and latest diff; no fixed waiting period applies.
