---
type: Source
title: Nextcloud Mail v0.2.0 owner-led adoption trial baseline
description: Bounded baseline for an early-stage real-project trial using the immutable Gnostoa v0.2.0 release, the frozen Mail workspace and human:ktogias as initial semantic and evaluation authority.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-28T10:28:59+03:00"
sources:
  - id: staged-evidence-decision
    resource: ../decisions/0052-use-staged-evidence-maturity-for-early-adoption-trials.md
    title: Use staged evidence maturity for early adoption trials
  - id: v0-2-0-release-work-item
    resource: https://github.com/ktogias/gnostoa/issues/146
    title: Publish Gnostoa v0.2.0 source and OCI release series
  - id: v0-2-0-publication-result
    resource: v0-2-0-source-and-oci-publication-result.md
    title: v0.2.0 source and OCI publication result
  - id: frozen-mail-commit
    resource: https://github.com/ktogias/mail/commit/b54bd0e637497217e8fec85ad59fe8bdf58e52a8
    title: Frozen Nextcloud Mail mutation-workspace subject
x-project-knowledge:
  id: kit.assessment.nextcloud-mail-v0-2-0-owner-led-adoption-trial-baseline
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0052-use-staged-evidence-maturity-for-early-adoption-trials.md
    - kind: governed-by
      target: /decisions/0050-separate-adoption-observations-from-readiness-and-owner-disposition.md
    - kind: references
      target: /decisions/0051-select-the-v0-2-0-source-and-oci-publication-series.md
    - kind: references
      target: /assessments/b3-independent-adoption-experiment-design.md
    - kind: references
      target: /assessments/v0-2-0-source-and-oci-publication-result.md
    - kind: references
      target: /assessments/nextcloud-mail-post-remediation-fresh-rerun-result.md
---

# Nextcloud Mail v0.2.0 owner-led adoption trial baseline

## Classification and authority

This record replaces the attempted strict-independent candidate for the current
early-stage experiment. Under
[Decision 0052](../decisions/0052-use-staged-evidence-maturity-for-early-adoption-trials.md),
the trial is classified as:

- evidence class: `OWNER-LED`;
- accountable project-side authority: `human:ktogias`;
- immutable technical baseline: `PASS`;
- baseline admission: `ADMITTED`;
- experiment execution: `NOT STARTED`.

`human:ktogias` may select the initial real task, supply the lightweight
semantic baseline, answer owner-only questions, review the agent's understanding
and produce the initial value assessment. This authority is sufficient for this
trial because the purpose is early product learning in a real project in which
the maintainer is involved.

This is not evidence of independent adoption or upstream acceptance. The
historical strict B3 design remains a later, richer evidence class and is not a
gate for this run.

## Frozen technical baseline

These identities are exact and non-substitutable for the owner-led trial.

| Authority | Exact subject | Disposition |
|---|---|---|
| Released Gnostoa documentation and source | annotated tag `v0.2.0`; tag object `6d0357e075744ee316c725554d2e2c920b19a4dc`; commit `39aa4f25bdf46811600d4a0f6f9c0da52b73c542`; tree `866c8c489c9052c566bd65b6e798567d4a284f16`; public-surface digest `sha256:a85ac8dde00f1ed8fb0425de08597828e97c246ec17ce6556f3f222b27ddb1c1` | `FROZEN` |
| Immutable Gnostoa execution subject | `ghcr.io/ktogias/gnostoa@sha256:f89bf32c0c4b86bac71fa008579b2385e6ae39bf4822f685479c4f2cc22bfca4`; exactly `linux/amd64`; runtime source revision `39aa4f25bdf46811600d4a0f6f9c0da52b73c542` | `FROZEN` |
| Build provenance | GitHub attestation `43531953`; registry attestation object `sha256:8acee8391bf85f86d653b93a54efb4854f3ea4d21d4de722d482c3b04a26c229` | `FROZEN` |
| Integrated release-verifier authority | protected Gnostoa commit `194aa1cbc342487ee72f8b912e69a5729d8aa568`; tree `cb9284913483c717d3df1908af1c7956ce73ab4f`; release read-back run `33145955880` | `READ BACK` |
| Nextcloud Mail mutation workspace | repository `https://github.com/ktogias/mail`; commit `b54bd0e637497217e8fec85ad59fe8bdf58e52a8`; tree `b400a791f90415f2ce761c2f8412bcd4d6cded5e` | `FROZEN` |
| Final upstream Change Request authority | repository `https://github.com/nextcloud/mail` and its maintainers | `EXTERNAL`; no upstream effect is implied or authorized |

The released `v0.2.0` source is the documentation authority and the OCI digest
is the execution authority. Current Gnostoa `main`, the human-facing image tag
and any mutable alias must not silently replace those subjects during the run.

## Lightweight per-run record

Task-specific facts do not need another release-series admission. Immediately
before an execution, retain one compact run record containing:

1. one real, bounded, reversible and non-critical Mail task selected by
   `human:ktogias`;
2. why the task matters to the project and what is explicitly out of scope;
3. the exact prompt, or a retained prompt artifact plus SHA-256 digest;
4. concise owner-known constraints, unresolved questions and acceptance
   criteria;
5. the disposable branch or worktree identity and permitted mutation boundary;
6. the model/session identity and a declaration of relevant prior context;
7. the verification commands that are materially available for the task; and
8. start time, stop conditions and retained evidence location.

A separate independent reviewer, a complete ground-truth matrix, a dedicated
auditor and exhaustive host inventory are not required. Environment or tool
versions are recorded when they materially affect interpretation or
reproduction.

A fresh session is preferred when the purpose includes public-surface
onboarding or discoverability. It is not a universal eligibility gate; any prior
context must simply be declared so the result is interpreted honestly.

## Execution and mutation boundary

The default run envelope is:

- one clean, disposable local branch or worktree from the frozen Mail subject;
- use of the immutable Gnostoa v0.2.0 documentation and OCI digest;
- local knowledge and application changes only within the selected task;
- no production credentials, deployment, package publication or destructive
  data operation;
- no push, upstream Pull Request, Issue mutation, assignment request or other
  remote effect without a later explicit owner authorization; and
- one owner checkpoint when the agent encounters a material semantic question
  or before a task result is treated as accepted.

Stop on frozen-subject drift, unsafe or irreversible scope, unavailable
material verification, need for protected credentials, or a semantic decision
outside the actual authority of `human:ktogias`.

## Result dimensions

The run reports dimensions separately rather than collapsing them into a single
pass:

| Dimension | Allowed result |
|---|---|
| Environment and subject eligibility | `PASS` / `BLOCKED` |
| Public orientation and route selection | `PASS` / `PARTIAL` / `FAIL` |
| Adoption mechanics | `PASS` / `PARTIAL` / `FAIL` / `NOT RUN` |
| Semantic fidelity against the owner baseline | `PASS` / `PARTIAL` / `FAIL` |
| Task verification | `PASS` / `PARTIAL` / `FAIL` / `NOT RUN` |
| Owner disposition | `ACCEPT` / `CORRECT` / `REJECT` |
| Owner-assessed utility | `POSITIVE` / `MIXED` / `NEGATIVE` / `UNKNOWN` |
| Durable adoption | `YES` / `NO` / `DEFERRED` |

Retain the exact prompt, material commands and exit codes, generated project
knowledge and context, initial and final Git state, verification results,
material owner interventions and the final scorecard. Do not retain private
chain of thought, credentials, secrets or irrelevant shell history.

## Feedback and claim boundary

The owner-led result may immediately support a preliminary assessment,
retrospective, remediation, new decision, another experiment or continued
Gnostoa evolution.

Any later upstream or project-participant feedback is added with its identity,
date, reviewed subject and scope. It may change the current interpretation but
does not retroactively transform the original evidence into an independent
experiment.

Permitted wording includes `owner-led`, `owner-assessed`, `single-project` and
`preliminary`. The result must not claim independent adoption, upstream
acceptance, general productivity gain, universal usability, population-level
reliability or product-market fit.

## Lifecycle boundary

This baseline changes no release identity, OCI artifact, provenance object,
Mail repository or upstream provider state. It admits the technical and
authority envelope only; it does not execute the trial.

Release-series lifecycle completion does not depend on task execution or
upstream feedback. The concrete run, result, retrospective and any external
feedback belong to later records and may proceed under the authority defined
here.
