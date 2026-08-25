---
type: Source
title: Nextcloud Mail adoption route-activation diagnostic design
description: Pre-registered design for one activation-controlled test of the existing-project A1 adoption guidance.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-25T17:13:23Z"
sources:
  - id: nextcloud-mail-route-activation-work-item
    resource: https://github.com/ktogias/gnostoa/issues/122
    title: Pre-register a Nextcloud Mail route-activation diagnostic
x-project-knowledge:
  id: kit.assessment.nextcloud-mail-adoption-route-activation-diagnostic-design
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md
    - kind: references
      target: /decisions/0045-select-documentation-only-remediation-for-nextcloud-mail-adoption.md
    - kind: references
      target: /assessments/nextcloud-mail-adoption-baseline-and-root-cause.md
    - kind: references
      target: /lifecycles/evidence-gated-capability-evolution.md
    - kind: references
      target: /runbooks/deliver-bounded-self-hosted-slice.md
---

# Nextcloud Mail adoption route-activation diagnostic design

## Status and authority

This record pre-registers one future diagnostic. It contains no result and does
not authorize execution. [Work Item #122](https://github.com/ktogias/gnostoa/issues/122)
owns its design, a later separately authorized run and one reconciliation.
[Work Item #117](https://github.com/ktogias/gnostoa/issues/117) is closed and
must not be reopened, corrected or reinterpreted by this diagnostic.

[Decision 0016](../decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md)
governs bounded external-transfer experiments. [Decision 0045](../decisions/0045-select-documentation-only-remediation-for-nextcloud-mail-adoption.md)
remains the historical A1 selection and falsifiable-benefit authority. The
[completed #117 assessment](nextcloud-mail-adoption-baseline-and-root-cause.md)
owns the earlier baseline, remediation comparison and rejected frozen rerun.
This design selects no new normative behavior or mechanism, so those existing
Decision records satisfy the `normal`, knowledge-only admission.

## Exact question and limits

The diagnostic answers only:

> Once a fresh agent is explicitly told to study Gnostoa and follow its
> documented existing-project adoption workflow, can it use the A1 guidance to
> produce the smallest valid adoption without solution-specific hints or
> maintainer correction?

It isolates route activation and guidance usability. It does not retest naked
discoverability from the original `adopt` prompt and cannot establish general
adoption value, productivity, reliability, causation, B3, Decision-0036
satisfaction, or a model/vendor comparison.

## Frozen prompts

The experiment-agent conversation contains exactly two prompts.

Prompt 1:

`clone https://github.com/ktogias/mail`

Prompt 2:

`Study https://github.com/ktogias/gnostoa. Then adopt it in the already cloned mail repository, following the documented existing-project adoption workflow.`

Do not add paths, filenames, commands, digests, expected artifacts, validation
instructions, known failures, ownership answers, evidence checklists or earlier
experiment context to that conversation.

## Frozen starting subjects

### Nextcloud Mail

| Field | Frozen value |
|---|---|
| Repository | `https://github.com/ktogias/mail` |
| Commit | `b54bd0e637497217e8fec85ad59fe8bdf58e52a8` |
| Tree | `b400a791f90415f2ce761c2f8412bcd4d6cded5e` |
| Clone | Clean clone; shallow is acceptable if required |
| Authority | Local workspace mutation only; no Mail provider effect |

### Gnostoa

| Field | Frozen preparation value |
|---|---|
| Protected-main commit | `5ecfc1a4953e05fa57520241a9d6b64289432fde` |
| Protected-main tree | `347d48aa06132936661efc8eb9ee98a8ffc20964` |
| Public-surface digest | `sha256:a107c33d5465d71628805d55c62ea3b9aa77a51776b59ece47577c4af02d5757` |
| Separate immutable execution subject | `ghcr.io/ktogias/gnostoa@sha256:0cd31a2a649c4ffede8972680c6779c981decf5ce8605f749fa7d58751472f80` |

Before execution, bind the exact documentation subject actually consulted and
the exact supported execution subject actually run as separate observations.
If the preparation commit has been followed by knowledge-only revisions,
explicitly read back whether the public documentation subject is unchanged; do
not silently substitute a newer commit. Merely declaring the OCI reference is
not evidence that its bytes executed.

## Eligibility and contamination controls

The run is eligible only when all of these hold:

- the agent/session is genuinely new, with no prior Gnostoa, Mail experiment,
  #117, Decision 0045, weather-note or retrospective context;
- the filesystem workspace is new and empty before Prompt 1;
- no copied Mail or Gnostoa checkout and no prior adoption artifact is present;
- no local development image such as `gnostoa:v0.1.2-dev` is used as the
  execution subject;
- the broad environment class is Git and Docker available, PHP and Composer
  unavailable, where practical;
- every environment deviation is recorded before the run;
- mutation authority is confined to the local Mail workspace;
- no push, PR, Issue, Release, package or provider mutation occurs; and
- no application feature is implemented.

The agent must use Gnostoa's public adopter route. Reading experiment-specific
Gnostoa self-knowledge, including the #117 assessments or this design,
contaminates the run and must be reported separately. The public router's
self-knowledge exclusion is itself observed orientation behavior. Do not
preload or privately explain that boundary beyond the two prompts.

## Future execution contract

Only after accountable acceptance and integration of this design:

1. record the environment, deviations and start time outside the agent
   conversation;
2. send Prompt 1 only;
3. after the clone response, send Prompt 2 only;
4. allow one autonomous first attempt;
5. provide no correction, clarification, hint or evidence request before
   preserving the first response;
6. if ownership or commitment clarification is requested, preserve that
   request as the first-attempt result before answering anything;
7. immediately preserve the complete conversation/tool transcript and audit
   the resulting workspace independently and read-only;
8. do not continue or repair the same agent and count that continuation as
   diagnostic evidence; and
9. reconcile the experiment once.

A missing or ambiguous material prerequisite is recorded under the outcome
dimensions below; it must not be replaced by manual simulation, invented output
or a plausible narrative.

## Measurement contract

The independent record must include:

- environment eligibility, deviations, elapsed time and retry count;
- exact Mail commit, tree, Git state and mutation boundary;
- route activation: whether Gnostoa was fetched or consulted;
- exact public pages or files consulted and any self-knowledge contamination;
- the selected native, source-built or immutable-OCI execution route;
- substantive commands, working directories and exit codes;
- created files and their SHA-256 hashes;
- structural-validation result;
- bounded-context result and artifact hash;
- project-suite result, including truthful `BLOCKED` classification;
- ownership, provenance and unresolved-fact handling;
- unsupported inventions, readiness or completion claims;
- experiment-agent evidence binding;
- owner corrections and acceptance; and
- durable-adoption disposition.

Report each dimension independently:

| Dimension | Allowed result |
|---|---|
| Environment | `PASS / BLOCKED` |
| Route activation | `PASS / PARTIAL / FAIL` |
| Public orientation | `PASS / PARTIAL / FAIL` |
| Technical execution | `PASS / PARTIAL / FAIL / NOT RUN` |
| Structural validation | `PASS / FAIL / NOT RUN` |
| Bounded context | `PASS / FAIL / NOT RUN` |
| Project suites | `PASS / FAIL / BLOCKED / NOT RUN` |
| Semantic fidelity | `PASS / PARTIAL / FAIL` |
| Agent evidence binding | `PASS / PARTIAL / FAIL` |
| Owner acceptance | `ACCEPT / CORRECT / REJECT` |
| Measured utility | `POSITIVE / MIXED / NEGATIVE / UNKNOWN` |
| Durable adoption | `YES / NO / DEFERRED` |
| A1 content-level effectiveness | `SUPPORTED / NOT SUPPORTED / NOT TESTED` |

There is no aggregate `PASS` and no reliability or causal rate.

## Pre-registered interpretation

- If the public adoption route is not consulted, A1 content remains `NOT
  TESTED`.
- If the route is consulted but mechanics fail, record the exact guidance or
  tooling boundary reached.
- If adoption validates and bounded context is generated, the result supports
  only bounded A1 usability after explicit route activation.
- A correct stop for missing ownership or commitment may be semantic success
  without technical completion.
- A result different from #117 does not by itself prove that prompt wording or
  A1 caused the difference.

The final evidence must keep experiment evidence, agent-supplied evidence and
human-owner semantic acceptance distinct.

## Current stop point and exclusions

This slice ends after an exact draft pre-registration candidate and provider
verification. It does not run a fresh agent, modify adopter guidance, select or
implement remediation, mutate Mail, create a release or perform any publication
or provider effect beyond the Work Item and draft PR needed for repository
review.

It admits no generator, initializer, `knowledge init`, preflight command, new
schema or file format, CLI alias, compatibility layer, ownership default,
mutable image tag, B3 claim or Decision-0036 claim. Execution requires a later
accountable-owner authorization over the integrated design.
