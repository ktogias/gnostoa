---
type: Source
title: v0.2.0 release-series and staged-evidence transition retrospective
description: Bounded knowledge-only retrospective over the v0.2.0 source and OCI publication, reconciliation, provider lifecycle incidents and staged-evidence transition, preserving durable lessons without selecting backlog implementation.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-28T14:13:36+03:00"
sources:
  - id: retrospective-work-item
    resource: https://github.com/ktogias/gnostoa/issues/153
    title: Retrospect the v0.2.0 release series and staged-evidence transition
  - id: release-work-item
    resource: https://github.com/ktogias/gnostoa/issues/146
    title: Publish Gnostoa v0.2.0 source and OCI release series
  - id: release-candidate
    resource: https://github.com/ktogias/gnostoa/pull/147
    title: Prepare the v0.2.0 release candidate
  - id: publication-binding
    resource: https://github.com/ktogias/gnostoa/pull/148
    title: Bind the v0.2.0 OCI publication workflow
  - id: rerun-authority-correction
    resource: https://github.com/ktogias/gnostoa/pull/149
    title: Reject OCI publication reruns
  - id: release-reconciliation
    resource: https://github.com/ktogias/gnostoa/pull/150
    title: Reconcile the v0.2.0 source and OCI publication result
  - id: staged-evidence-integration
    resource: https://github.com/ktogias/gnostoa/pull/152
    title: Adopt staged evidence maturity and the owner-led trial baseline
x-project-knowledge:
  id: kit.assessment.v0-2-0-release-series-and-staged-evidence-retrospective
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0051-select-the-v0-2-0-source-and-oci-publication-series.md
    - kind: governed-by
      target: /decisions/0052-use-staged-evidence-maturity-for-early-adoption-trials.md
    - kind: references
      target: /assessments/v0-2-0-release-candidate-and-source-boundary-result.md
    - kind: references
      target: /assessments/v0-2-0-source-and-oci-publication-result.md
    - kind: references
      target: /assessments/nextcloud-mail-v0-2-0-owner-led-adoption-trial-baseline.md
    - kind: references
      target: /failure-modes/publication-baseline-review-drift.md
    - kind: references
      target: /failure-modes/reverse-centaur-review-overload.md
---

# v0.2.0 release-series and staged-evidence transition retrospective

## Observation boundary

This retrospective is bounded to protected `main`
`52e21722e2d24fc73e5b10e14996c127209e2599`, Git tree
`79d06b4d4e3e96d3c42b5b8436e8e7eb3c9ca38d`, after integration of PR #152.
It covers the release Work Item #146, PRs #147–#152, the immutable source and
OCI effects, their provider read-backs, and the transition from the strict B3
closeout path to staged evidence under Decision 0052.

The immutable release subjects remain:

- annotated tag `v0.2.0`, tag object
  `6d0357e075744ee316c725554d2e2c920b19a4dc`;
- source commit `39aa4f25bdf46811600d4a0f6f9c0da52b73c542`, tree
  `866c8c489c9052c566bd65b6e798567d4a284f16`;
- OCI consumer identity
  `ghcr.io/ktogias/gnostoa@sha256:f89bf32c0c4b86bac71fa008579b2385e6ae39bf4822f685479c4f2cc22bfca4`;
- publication run `33124503631`, attempt 1, and provenance attestation
  `43531953`;
- integrated release reconciliation commit
  `194aa1cbc342487ee72f8b912e69a5729d8aa568`, tree
  `cb9284913483c717d3df1908af1c7956ce73ab4f`;
- integrated release-route read-back run `33145955880`; and
- integrated staged-evidence baseline commit
  `52e21722e2d24fc73e5b10e14996c127209e2599`, tree
  `79d06b4d4e3e96d3c42b5b8436e8e7eb3c9ca38d`.

A maintainer-provided technical assessment dated 27 August 2026 was also read.
It is an attributed external input retained outside the repository, not a
canonical provider record. Its executed observations and usability findings are
used as hypotheses where they agree with durable evidence; its time-bound line,
word and test counts are not promoted as current project metrics. The assessment
itself states that its synthetic adopter is not a substitute for a real
owner-led or independent adoption trial.

No historical transcript or private chain of thought was reconstructed. No
release, image, Mail or upstream state was mutated for this retrospective.

## Outcome summary

| Dimension | Result |
|---|---|
| Immutable source publication | `PASS` — exact annotated tag, source commit and tree read back. |
| Immutable OCI publication | `PASS` — one authorized attempt, digest-pinned `linux/amd64`, provenance and anonymous digest access read back. |
| Release reconciliation | `PASS` — repository verifier, public projections and GitHub Release presentation bind the published digest. |
| Owner-led baseline | `PASS` — Decision 0052 and the bounded Nextcloud Mail baseline are integrated and provider verified. |
| Independent adoption | `NOT CLAIMED` — the strict B3 method is deferred to a later maturity stage. |
| Product value in a real task | `UNKNOWN` — the first admitted `OWNER-LED` task run has not begun. |

The technical release series succeeded. The process result is mixed: the
controls prevented real defects and unauthorized effects, but the release and
experiment-boundary work accumulated disproportionate coordination, evidence
and wording overhead before producing new real-project value evidence.

## What worked

### 1. Falsification prevented a broken release

The strengthened release smoke exposed that the execution-only installed
artifact could terminate before retaining the evidence required by the new
`adoption-check` capability. The candidate was repaired before publication, and
the clean installed-artifact route was rerun. This was a direct product defect
caught by assurance machinery, not a ceremonial check.

### 2. Immutable identities and read-back made irreversible effects accountable

The series kept source selection, integration, tag creation, GitHub Release,
OCI publication and reconciliation distinct. Source and image identities were
read back from their authoritative providers rather than inferred from command
success. The image was consumed by digest, `latest` remained absent and no
replacement publication occurred.

### 3. Publication authority became fail closed

PR #148 bound publication to the exact main-hosted workflow and separated the
authorization job from the write-capable job. PR #149 added explicit checks for
the triggering actor and `GITHUB_RUN_ATTEMPT == 1`. The correction arrived after
the single valid publication, without treating the already published artifact
as invalid or authorizing a second dispatch.

### 4. Exact-tree acceptance survived squash integration

Candidate acceptance was bound to exact heads and trees. The integrated release
reconciliation tree equalled its accepted tree, and the staged-evidence tree
`79d06b4...` likewise survived squash integration unchanged. Post-merge
Verification and CodeQL then observed integrated `main`, rather than relying only
on PR-head evidence.

### 5. Negative evidence and claim boundaries enabled a strategy correction

The four historical Nextcloud Mail attempts retained their `REJECT`, `UNKNOWN`
and `NO` dispositions. Instead of relabelling them as success, Decision 0052
changed the present learning strategy: `OWNER-LED` evidence is proportionate for
early product learning, while `INDEPENDENT` evidence remains available for
stronger later claims. Upstream feedback became additive rather than an entry
gate.

## What created avoidable cost or risk

### 1. The strict B3 contract was applied at the wrong maturity stage

The initial path required an independent project authority, pre-approved semantic
criteria and extensive audit controls before Gnostoa had demonstrated practical
value in an owner-involved project. PR #151 and PR #152 temporarily represented
competing experiment contracts. Closing the former as superseded and partially
amending Decision 0051 were necessary cleanup, but the coordination cost was a
symptom of a maturity mismatch.

### 2. Evidence amplification consumed scarce human attention

Many small wording, metadata and exact-head changes invalidated earlier acceptance
claims and triggered another full provider portfolio. Temporary workflows,
repair commits and final empty binding commits were sometimes used to regain a
clean exact subject. The discipline protected correctness, but the aggregate
volume made the owner the serial integration bottleneck and increased the chance
of process mistakes.

### 3. Provider lifecycle parsing was a hidden mutation surface

A negative sentence containing a lifecycle keyword beside the Work Item
reference caused GitHub to alter the Work Item state. The text was later repaired
and the Work Item restored to `OPEN`. The lesson is narrower than a generic text
scanner: every provider-parsed title, body and merge payload is an effect surface,
and negation does not neutralize provider syntax.

### 4. Current-facing prose and literal tests were too tightly coupled

After Decision 0052 changed the current strategy, README, roadmap, status, the B3
chronology note and documentation tests still encoded the old strict-B3 sequence.
The tests correctly detected inconsistency, but they had pinned volatile wording
rather than the intended semantic boundary. Historical records and current
projections had to be separated explicitly.

### 5. Product evidence lagged behind governance evidence

The external assessment reproduced the quick start and found strong code and
supply-chain hygiene, while also needing repeated attempts to configure a
synthetic adopter and observing that strict `READY` requires project-side runtime
integration. Those findings are useful risk hypotheses, but the central question
remains unanswered: whether Gnostoa improves one real task enough to justify its
adoption and continued complexity.

## Durable lessons

1. **Keep strong exact-identity and provider-read-back controls at irreversible
   boundaries.** The release smoke, one-shot publication authority and digest
   read-back prevented or bounded concrete defects. These controls earned their
   cost.
2. **Match evidence rigor to the claim and product stage.** `OWNER-LED` evidence
   can support preliminary product learning without pretending to be independent
   adoption. Stronger controls belong with stronger later claims.
3. **Test semantic invariants, not one volatile chronology sentence.** Historical
   evidence should remain historically accurate; current projections should route
   to current authority and avoid predicting provider effects.
4. **Treat human attention as a finite verification resource.** New evidence,
   mechanisms and exact-head cycles require a demonstrated risk or decision need;
   volume is not assurance.
5. **After a release boundary is safe, prioritize real product learning.** The
   next substantive slice should measure a real task before expanding the
   assurance system again, unless a concrete safety or correctness blocker appears.

Decisions 0051 and 0052 already own the stable release and evidence-maturity
policies. This retrospective selects no new Decision.

## Prioritized backlog hypotheses

The following items are retained as hypotheses, not admitted implementations.

| Priority | Hypothesis | Admission trigger | Current disposition |
|---|---|---|---|
| P0 | Run one real bounded `OWNER-LED` task and measure orientation, semantic fidelity, owner intervention, verification and utility. | A concrete reversible Mail task and compact run record are selected by the owner. | `NEXT PRODUCT-LEARNING CANDIDATE`; not started. |
| P1 | Distinguish adopter `InvalidInput` from tool `InternalError` and expose a bounded human-readable reason. | Reproduction in the real trial or one focused characterization test demonstrates the ambiguity materially affects diagnosis. | `RETAIN`; not selected. |
| P1 | Add a non-authoritative diagnostic route and improve CLI/path guidance. | The real trial repeats serial one-error-per-run configuration or route-selection friction. | `RETAIN`; not selected. |
| P2 | Decompose the largest adoption functions and reduce single-maintainer review risk. | Material change pressure, repeated review defects or a second maintainer requires independently reviewable seams. | `DEFER`; not selected. |
| Later maturity | Execute a strict `INDEPENDENT` adoption experiment. | Wider use, publicity or claims require external task and evaluation authority. | `DEFER`; separate future admission. |

The synthetic assessment's line and word ratios are not accepted as permanent
budgets. They support the qualitative concern that internal assurance has grown
faster than measured user value. The real owner-led run should determine which
friction is product-critical before any broad simplification or refactor.

## Implications for the first owner-led trial

The next trial should remain compact and preserve the evidence class under which
it is produced. It should bind one real reversible task, exact prompt, frozen Mail
subject, model/session context, owner constraints, available verification and
stop conditions.

At minimum, record:

- time and attempts needed to orient and begin useful work;
- incorrect assumptions, especially invented owners, provenance or semantic
  facts;
- owner questions and interventions required;
- which generated knowledge or context artifacts were actually used;
- task verification results and unresolved risk;
- owner disposition: `ACCEPT`, `CORRECT` or `REJECT`;
- owner-assessed utility: `POSITIVE`, `MIXED`, `NEGATIVE` or `UNKNOWN`; and
- durable adoption: `YES`, `NO` or `DEFERRED`.

Do not force the strict mechanical `READY` route merely to exercise machinery.
Use it only where its project-side integration is material to the selected task.
The trial should test practical value and onboarding friction, not reward
compliance with the retrospective.

## Retrospective disposition

- The `v0.2.0` source and OCI release series is technically successful and
  reconciled.
- The one-shot publication, immutable identity, provenance and read-back controls
  are retained.
- The strict B3 closeout path was disproportionate for the current product stage;
  Decision 0052 is the appropriate correction.
- The main unresolved product question is practical utility in a real owner-led
  task.
- The backlog above is recorded but no item is implemented by this Work Item.
- Work Item 146 remains in its current lifecycle state pending separate provider
  reconciliation and an explicit owner lifecycle action.

## Non-conclusions and effect boundary

This retrospective does not establish independent adoption, upstream acceptance,
product-market fit, productivity gain, production readiness or general security.
It does not execute the owner-led trial, mutate Mail, contact upstream, publish or
replace an artifact, authorize a new release effect, implement backlog items or
change the lifecycle state of Work Item 146.
