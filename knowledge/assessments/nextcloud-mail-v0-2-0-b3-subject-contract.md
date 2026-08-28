---
type: Source
title: Nextcloud Mail v0.2.0 B3 subject-contract candidate
description: Fail-closed candidate that binds the released Gnostoa and frozen Mail subjects while withholding B3 admission until independent semantic authority, a real task, an owner-approved ground-truth matrix, exact prompts and environment identities exist.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-28T09:35:32+03:00"
sources:
  - id: v0-2-0-release-work-item
    resource: https://github.com/ktogias/gnostoa/issues/146
    title: Publish Gnostoa v0.2.0 source and OCI release series
  - id: b3-independent-adoption-design
    resource: b3-independent-adoption-experiment-design.md
    title: B3 independent-adoption experiment design
  - id: v0-2-0-publication-result
    resource: v0-2-0-source-and-oci-publication-result.md
    title: v0.2.0 source and OCI publication result
  - id: frozen-mail-commit
    resource: https://github.com/ktogias/mail/commit/b54bd0e637497217e8fec85ad59fe8bdf58e52a8
    title: Frozen Nextcloud Mail mutation-workspace subject
x-project-knowledge:
  id: kit.assessment.nextcloud-mail-v0-2-0-b3-subject-contract
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0051-select-the-v0-2-0-source-and-oci-publication-series.md
    - kind: governed-by
      target: /decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md
    - kind: references
      target: /assessments/b3-independent-adoption-experiment-design.md
    - kind: references
      target: /assessments/v0-2-0-source-and-oci-publication-result.md
    - kind: references
      target: /assessments/nextcloud-mail-post-remediation-fresh-rerun-design.md
    - kind: references
      target: /assessments/nextcloud-mail-post-remediation-fresh-rerun-result.md
---

# Nextcloud Mail v0.2.0 B3 subject-contract candidate

## Authority and current disposition

[Decision 0051](../decisions/0051-select-the-v0-2-0-source-and-oci-publication-series.md)
requires a separate exact-subject contract after release reconciliation. The
[B3 experiment design](b3-independent-adoption-experiment-design.md) requires
that contract to bind not only immutable technical subjects, but also one real
task, one eligible independent human owner, an owner-approved ground-truth
matrix, exact prompts, permissions, environment and tool identities.

This knowledge-only candidate binds every technical identity that already
exists and records the remaining authority gaps without predicting or inventing
them. Its current dispositions are:

- immutable Gnostoa and Mail subject binding: `PASS`;
- strict B3 candidate eligibility: `BLOCKED`;
- experiment execution authority: `NOT GRANTED`.

This record is not a B3 run, owner approval, upstream assignment, application
change, provider effect or evidence of independent adoption. B3 has not begun.

## Frozen technical subjects

These identities are exact and non-substitutable for this candidate.

| Authority | Exact subject | Disposition |
|---|---|---|
| Released Gnostoa documentation and source | annotated tag `v0.2.0`; tag object `6d0357e075744ee316c725554d2e2c920b19a4dc`; commit `39aa4f25bdf46811600d4a0f6f9c0da52b73c542`; tree `866c8c489c9052c566bd65b6e798567d4a284f16`; public-surface digest `sha256:a85ac8dde00f1ed8fb0425de08597828e97c246ec17ce6556f3f222b27ddb1c1` | `FROZEN` |
| Immutable Gnostoa execution subject | `ghcr.io/ktogias/gnostoa@sha256:f89bf32c0c4b86bac71fa008579b2385e6ae39bf4822f685479c4f2cc22bfca4`; `linux/amd64`; runtime source revision `39aa4f25bdf46811600d4a0f6f9c0da52b73c542` | `FROZEN` |
| Build provenance | GitHub attestation `43531953`; registry attestation object `sha256:8acee8391bf85f86d653b93a54efb4854f3ea4d21d4de722d482c3b04a26c229` | `FROZEN` |
| Integrated release-verifier authority | protected Gnostoa commit `194aa1cbc342487ee72f8b912e69a5729d8aa568`; tree `cb9284913483c717d3df1908af1c7956ce73ab4f`; canonical release read-back run `33145955880` | `READ BACK` |
| Nextcloud Mail mutation workspace | repository `https://github.com/ktogias/mail`; commit `b54bd0e637497217e8fec85ad59fe8bdf58e52a8`; tree `b400a791f90415f2ce761c2f8412bcd4d6cded5e` | `FROZEN` |
| Upstream semantic and Change Request authority | repository `https://github.com/nextcloud/mail` | `EXTERNAL`; no upstream effect is authorized here |

The released source revision is the documentation authority. Protected current
Gnostoa `main` is only release-verifier and contract-preparation authority; it
must not silently replace the `v0.2.0` documentation bytes in the experiment.
The OCI digest, not the human-facing `0.2.0` tag, is the execution authority.
No mutable alias, including `latest`, is admitted.

## Candidate eligibility read

The target is a real pre-existing project independently owned from Gnostoa, and
the frozen fork permits a reversible local mutation workspace. Those facts do
not by themselves satisfy strict B3 eligibility.

| Required condition | Current evidence | Disposition |
|---|---|---|
| Independently owned real project | upstream `nextcloud/mail` exists independently of Gnostoa | `PASS` |
| Named human with current semantic authority | no eligible person has accepted this exact experiment contract | `BLOCKED` |
| No prior Gnostoa adoption by that human owner | no owner attestation exists | `BLOCKED` |
| One real upcoming bounded, non-trivial, reversible and non-critical task | no exact task has been selected and accepted | `BLOCKED` |
| Objective verification or meaningful owner review | task-specific acceptance tests and review authority are absent | `BLOCKED` |
| Safe mutation authority | local unpushed mutation of the frozen fork can be bounded; application-task permission is still absent | `PARTIAL` |
| Owner availability for the pre-implementation checkpoint and final disposition | no exact reviewer commitment exists | `BLOCKED` |
| No production credentials or unsafe effects | the proposed local-only envelope requires none | `PASS` |

The overall eligibility result is therefore `BLOCKED`. Public Issue state,
labels such as `good first issue`, an unassigned field, historical maintainer
comments or the existence of a fork do not substitute for current human-owner
approval of the task and ground truth. Mutable provider observations may inform
candidate search, but they are not frozen semantic authority.

## Ground-truth matrix status

No task-specific matrix is frozen. The required evidence classes remain:

| Evidence class | Required agent behaviour | Current state |
|---|---|---|
| Repository-visible | discover from the exact Mail subject | task-specific rows absent |
| Supplied in the exact task prompt | preserve without reinterpretation | exact task prompt absent |
| Owner-only knowledge | ask when necessary and stop at the owner checkpoint | eligible owner absent |
| Genuinely unresolved | keep unresolved rather than inventing an answer | task-specific rows absent |

The future human project owner must approve every material row, its severity and
its evidence class before execution. Gnostoa maintainers cannot self-certify
Nextcloud Mail semantics on the upstream owner's behalf.

## Prompt, permissions and environment status

The exact experiment prompt is deliberately `UNBOUND`. Freezing only the prior
two-message adoption prompt while omitting the real application task would
repeat controlled pre-B3 adoption work, not satisfy this B3 contract. A partial
or placeholder prompt must not be sent to an experiment agent.

The maximum provisional mutation envelope is:

- a new clean local workspace at the frozen `ktogias/mail` commit and tree;
- one local, disposable experiment branch or worktree;
- no push, upstream Pull Request, Issue mutation, assignment request, Release,
  package publication, deployment, production credential or remote provider
  effect;
- no application implementation before the independent owner's knowledge and
  bounded-context checkpoint returns `ACCEPT` or an accepted correction plus
  explicit continuation authority; and
- no later upstream effect without a separate explicit authorization and the
  upstream project's own review process.

This envelope limits a future run; it does not grant application-task mutation
permission now.

The following execution identities are also `UNBOUND` and must be exact before
admission:

- fresh agent/model/session identity and contamination declaration;
- controller and independent read-only auditor identities;
- host operating system and architecture;
- Git, OCI engine, Python and task-relevant Mail toolchain versions;
- clean-workspace and network-access state;
- timestamps, evidence paths and SHA-256 manifest boundary; and
- permitted test commands, resource limits and stop conditions.

## Completion conditions for this candidate

This candidate can become an admitted exact B3 contract only after one bounded
update binds all of the following without moving the frozen technical subjects:

1. one named eligible independent human with current Nextcloud Mail semantic
   authority and explicit review availability;
2. one real task accepted by that owner, with no ambiguous assignment or active
   competing implementation;
3. one owner-approved ground-truth matrix and objective or meaningful review
   criteria;
4. the complete exact experiment prompt, including the real task-specific
   delta, permissions and questions that require an owner stop;
5. the exact fresh agent, controller, auditor, host and tool identities; and
6. the final evidence, timing, mutation, verification and stop boundaries.

If Nextcloud Mail cannot supply those conditions, strict B3 must select another
independently owned real project rather than weakening the pre-registered
eligibility rule or reclassifying Gnostoa-maintainer review as independent
project ownership.

## Stop conditions

Stop candidate preparation or future execution on any of these conditions:

- drift or ambiguity in a frozen Gnostoa or Mail identity;
- inaccessible released documentation, OCI digest or target source;
- no eligible independent owner or no current review commitment;
- task ambiguity, active competing work, unclear assignment or unsafe scope;
- missing owner approval of any material ground-truth row;
- incomplete prompt, permission, tool or environment binding;
- fresh-agent contamination or unavailable independent audit;
- need for production credentials, deployment or unapproved remote effects; or
- pressure to treat a narrative, label or plausible implementation as owner
  acceptance or technical evidence.

A stopped candidate remains `BLOCKED`; it is not repaired during measurement
and is never converted into a pass by retrospective interpretation.

## Lifecycle boundary

Work Item 146 remains `OPEN`. This candidate changes no release identity,
GitHub Release presentation, OCI artifact, provenance object, Mail repository or
upstream provider state. The separate knowledge-only release retrospection
remains later in the sequence and must preserve the lifecycle-parser finding
from the publication series.

The next accountable-owner disposition may authorize only continued preparation
of this exact candidate. It cannot authorize a B3 run until every blocked field
above is bound and independently approved.