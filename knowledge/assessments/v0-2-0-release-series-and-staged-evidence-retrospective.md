---
type: Source
title: v0.2.0 release-series and staged-evidence transition retrospective
description: Bounded retrospective over the v0.2.0 source and OCI publication, reconciliation and staged-evidence transition, retaining lessons and backlog hypotheses without selecting implementation.
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

## Boundary and evidence

Observed at protected `main` commit
`52e21722e2d24fc73e5b10e14996c127209e2599`, tree
`79d06b4d4e3e96d3c42b5b8436e8e7eb3c9ca38d`, after PR #152. The window covers
Work Item #146, PRs #147–#152, the immutable source/OCI effects and their
provider read-backs.

The immutable release remains tag object
`6d0357e075744ee316c725554d2e2c920b19a4dc`, source commit
`39aa4f25bdf46811600d4a0f6f9c0da52b73c542`, tree
`866c8c489c9052c566bd65b6e798567d4a284f16`, and OCI consumer identity
`ghcr.io/ktogias/gnostoa@sha256:f89bf32c0c4b86bac71fa008579b2385e6ae39bf4822f685479c4f2cc22bfca4`.
Publication run `33124503631` attempt 1, attestation `43531953`, integrated
release-route read-back `33145955880`, and the integrated staged-evidence tree
above provide the provider boundary.

A maintainer-provided technical assessment dated 27 August 2026 is an attributed
external input, not canonical provider truth. Its executed usability findings
inform hypotheses; its time-bound counts are not current metrics, and its
synthetic adopter is not treated as a real adoption result.

## Result

| Dimension | Result |
|---|---|
| Source and OCI publication | `PASS` — immutable identities and one authorized publication were read back. |
| Reconciliation | `PASS` — verifier, projections and Release presentation bind the digest. |
| Owner-led baseline | `PASS` — Decision 0052 and the Mail baseline are integrated and provider verified. |
| Independent adoption | `NOT CLAIMED` — deferred to later maturity. |
| Value in a real task | `UNKNOWN` — the first admitted `OWNER-LED` task has not run. |

The technical series succeeded. The process was mixed: strong controls caught
real defects and bounded irreversible effects, while coordination and evidence
work grew faster than new real-project value evidence.

## What worked

- **Release falsification caught a product defect.** The strengthened smoke test
  exposed an installed-artifact path that could terminate before retaining the
  new adoption evidence. It was repaired before publication.
- **Provider read-back replaced inferred success.** Tag, Release, OCI digest,
  provenance and anonymous digest access were checked at their authorities;
  `latest` remained absent and no replacement publication occurred.
- **Publication became one-shot and fail closed.** Workflow-origin, actor,
  triggering-actor and `GITHUB_RUN_ATTEMPT == 1` checks bounded the write effect.
- **Exact-tree acceptance survived integration.** Accepted and squash-integrated
  trees were equal, followed by integrated-main Verification and CodeQL.
- **Negative evidence enabled correction.** Historical Mail results remained
  `REJECT` / `UNKNOWN` / `NO`; Decision 0052 selected proportionate
  `OWNER-LED` learning without relabelling them as success.

## What created friction

- The strict independent-B3 contract was disproportionate before owner-involved
  real-project value had been demonstrated; PRs #151 and #152 briefly encoded
  competing paths.
- Repeated wording, metadata and exact-head changes amplified evidence volume and
  made the owner the serial integration bottleneck.
- GitHub treated a lifecycle keyword beside a Work Item reference as an effect
  even inside a negative sentence; provider-parsed bodies and merge payloads are
  mutation surfaces.
- Current prose and tests pinned the old strict-B3 chronology too literally;
  historical evidence and current projections had to be separated.
- The external assessment reproduced the quick start and strong technical hygiene
  but encountered repeated synthetic-adopter setup friction. The real utility
  question remains unanswered.

## Durable lessons

1. Retain exact identity, one-shot authority and provider read-back at
   irreversible boundaries; these controls earned their cost.
2. Match rigor to claim and maturity: `OWNER-LED` supports preliminary learning,
   while `INDEPENDENT` supports stronger later claims.
3. Test semantic invariants rather than volatile chronology wording.
4. Treat human attention as finite; more evidence is not automatically more
   assurance.
5. Once a release boundary is safe, prioritize a real product task before adding
   assurance machinery unless a concrete blocker appears.

Decisions 0051 and 0052 already own the stable policy. No new Decision is
selected.

## Retained backlog hypotheses

| Priority | Hypothesis | Admission trigger | Disposition |
|---|---|---|---|
| P0 | Run one real bounded `OWNER-LED` task and measure practical value. | Owner selects a reversible Mail task and compact run record. | Next product-learning candidate; not started. |
| P1 | Separate adopter `InvalidInput` from tool `InternalError` and expose a concise reason. | Real trial or focused characterization reproduces material ambiguity. | Retain; not selected. |
| P1 | Add non-authoritative diagnostics and clearer CLI/path guidance. | Real trial repeats serial setup or route-selection friction. | Retain; not selected. |
| P2 | Decompose the largest adoption functions. | Review defects, change pressure or a second maintainer needs smaller seams. | Defer; not selected. |
| Later | Execute strict `INDEPENDENT` adoption. | Wider use or stronger public claims require external authority. | Separate future admission. |

The external assessment's line and word ratios are not permanent budgets. They
support only the qualitative hypothesis that assurance grew faster than measured
user value.

## Next owner-led trial

Bind one real reversible task, exact prompt, frozen Mail subject, model/session
context, owner constraints, available verification and stop conditions. Record:

- orientation time and attempts;
- incorrect assumptions, especially invented owners, provenance or semantics;
- owner questions and interventions;
- knowledge/context artifacts actually used;
- task verification and unresolved risk;
- owner disposition, owner-assessed utility and durable-adoption result.

Do not force strict mechanical `READY` merely to exercise machinery. Use it only
when its project-side integration is material to the selected task. The trial
must test practical value and onboarding friction.

## Disposition and non-conclusions

The `v0.2.0` release is technically successful and reconciled. Its immutable and
one-shot controls remain. Decision 0052 is the appropriate maturity correction,
and practical utility in one real task is the next unresolved product question.
The backlog is recorded but not implemented.

This record does not establish independent adoption, upstream acceptance,
product-market fit, productivity gain, production readiness or general security.
It does not execute the trial, mutate Mail, contact upstream, publish an artifact,
implement backlog items or change the lifecycle state of Work Item 146.
