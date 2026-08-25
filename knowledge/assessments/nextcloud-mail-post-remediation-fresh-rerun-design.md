---
type: Source
title: Nextcloud Mail post-remediation fresh rerun design
description: Pre-registered design for one fresh rerun that measures route activation and the A1 and A2 documentation controls separately after fail-closed existing-file adaptation was integrated.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-26T00:37:30+03:00"
sources:
  - id: nextcloud-mail-post-diagnostic-work-item
    resource: https://github.com/ktogias/gnostoa/issues/125
    title: Analyze and remediate Nextcloud Mail adoption route activation and safe existing-file adaptation
  - id: nextcloud-mail-baseline
    resource: nextcloud-mail-adoption-baseline-and-root-cause.md
    title: Nextcloud Mail adoption baseline and root-cause analysis
  - id: nextcloud-mail-route-activation-result
    resource: nextcloud-mail-adoption-route-activation-diagnostic-result.md
    title: Nextcloud Mail adoption route-activation diagnostic result
  - id: nextcloud-mail-post-diagnostic-alternatives
    resource: nextcloud-mail-post-diagnostic-remediation-alternatives.md
    title: Nextcloud Mail post-diagnostic remediation alternatives
  - id: frozen-mail-commit
    resource: https://github.com/ktogias/mail/commit/b54bd0e637497217e8fec85ad59fe8bdf58e52a8
    title: Frozen Nextcloud Mail experiment subject
x-project-knowledge:
  id: kit.assessment.nextcloud-mail-post-remediation-fresh-rerun-design
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md
    - kind: governed-by
      target: /decisions/0045-select-documentation-only-remediation-for-nextcloud-mail-adoption.md
    - kind: governed-by
      target: /decisions/0046-select-fail-closed-existing-file-adaptation.md
    - kind: references
      target: /assessments/nextcloud-mail-adoption-baseline-and-root-cause.md
    - kind: references
      target: /assessments/nextcloud-mail-adoption-external-practice-and-remediation-alternatives.md
    - kind: references
      target: /assessments/nextcloud-mail-adoption-route-activation-diagnostic-design.md
    - kind: references
      target: /assessments/nextcloud-mail-adoption-route-activation-diagnostic-result.md
    - kind: references
      target: /assessments/nextcloud-mail-post-diagnostic-remediation-alternatives.md
    - kind: references
      target: /assessments/v0-1-2-source-and-oci-publication-result.md
    - kind: references
      target: /lifecycles/evidence-gated-capability-evolution.md
    - kind: references
      target: /runbooks/deliver-bounded-self-hosted-slice.md
---

# Nextcloud Mail post-remediation fresh rerun design

## Authority, status and exact question

[Work Item #125](https://github.com/ktogias/gnostoa/issues/125) owns this one
pre-registration, its later separately authorized execution and one final
reconciliation. The completed #117 and #122 series remain historical evidence;
this design does not replay, repair or rewrite their results.

[Decision 0045](../decisions/0045-select-documentation-only-remediation-for-nextcloud-mail-adoption.md)
owns the A1 first-verified-slice prediction. [Decision
0046](../decisions/0046-select-fail-closed-existing-file-adaptation.md) owns the
narrow A2 preservation/adaptation prediction. Both remain falsifiable and
unproven. [Decision 0016](../decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md)
and the [evidence-gated lifecycle](../lifecycles/evidence-gated-capability-evolution.md)
govern the experiment boundary.

This record asks only:

> Under the same activation-controlled two-message prompt, can one genuinely
> fresh agent enter the documented existing-project route and either produce
> the smallest valid adoption or stop truthfully, while preserving existing
> project authority and binding every completion claim to retained evidence?

This is a `normal`, knowledge-only pre-registration. It contains no result and
does not authorize execution. No new Decision is needed because Decisions 0045
and 0046 already select the two documentation controls and require this later
fresh behavioral test.

## Frozen prompts

The experiment-agent conversation receives exactly two messages.

Prompt 1:

`clone https://github.com/ktogias/mail`

Prompt 2:

`Study https://github.com/ktogias/gnostoa. Then adopt it in the already cloned mail repository, following the documented existing-project adoption workflow.`

Do not add paths, filenames, commands, identities, expected artifacts,
validation instructions, prior failures, ownership answers, success criteria or
experiment history to the experiment-agent conversation.

## Frozen subjects

The documentation, target source and execution subjects are separate
authorities and must not be silently substituted.

| Subject | Frozen identity and boundary |
|---|---|
| Gnostoa pre-registration base | protected commit `dd02e8006aef70c3a978f2c28e07f31f3ebeb4d9`; tree `8b66a4aa1f58f6d9841025498ff603be8945d5ac` |
| Remediated public documentation bytes | public-surface digest `sha256:4442e4203bcaece1372c1c762ba27dcab5a4c23d5b97cd72788d17487f5c20b0`; this knowledge-only design and its index route must not change that public surface |
| Published immutable OCI subject | `ghcr.io/ktogias/gnostoa@sha256:0cd31a2a649c4ffede8972680c6779c981decf5ce8605f749fa7d58751472f80`; `linux/amd64`; this is a permitted exact published route, not evidence that it ran |
| Nextcloud Mail | repository `https://github.com/ktogias/mail`; commit `b54bd0e637497217e8fec85ad59fe8bdf58e52a8`; tree `b400a791f90415f2ce761c2f8412bcd4d6cded5e` |

This assessment cannot predict its own squash commit. After accountable
integration, the exact integrated commit/tree must be recorded as the
documentation revision proposed for execution, with byte equality to the
remediated public surface above. Immediately before execution, the controller
must read back that the public URLs reached by the frozen prompts resolve to
that separately authorized integrated revision and that its public digest
remains exact. This is an explicit re-binding, not silent substitution. Any
public-byte drift, inaccessible identity or ambiguous read-back is `BLOCKED`;
do not retarget the experiment or alter the prompts.

The final evidence must separately bind the exact documentation files actually
consulted, the toolkit source revision actually materialized, and the supported
execution route actually run. A correctly bound native, source-built or
immutable-OCI route can establish technical execution. Declaring the OCI digest
in a lock or environment does not establish execution of its bytes, and an
unexecuted OCI route is recorded independently as `NOT RUN` rather than making
another valid route fail.

## Freshness, eligibility and contamination controls

The run is eligible only when all of these conditions hold:

- the agent and session are genuinely new and have no prior Gnostoa,
  weather-note, Nextcloud Mail experiment, #117, #122, #125, Decision 0045,
  Decision 0046 or retrospective context;
- the filesystem workspace is new and empty before Prompt 1, with no copied or
  preloaded Mail/Gnostoa checkout, adoption artifact or experiment-specific
  image prepared for the agent;
- the controller records pre-existing environment and image state rather than
  changing it to help the agent;
- exact Git, Docker or other runtime, Python and available project-tool versions
  are captured before the run;
- local Mail workspace mutation is the only permitted effect;
- no push, PR, Issue, Release, package, provider or upstream Mail mutation is
  permitted;
- no Mail application feature is implemented; and
- no owner correction, clarification, semantic hint or follow-up evidence
  request is supplied during the autonomous attempt.

Reading Gnostoa experiment-specific self-knowledge, including the assessments
named above or this design, contaminates the run and is reported separately.
Do not preload or privately explain that boundary to the experiment agent. The
agent must orient from the public adopter surface reached through the two frozen
prompts.

Before Prompt 1, establish that the exact subjects are accessible, the workspace
is clean and writable, at least one real supported execution route is available,
and timestamps, numeric exit codes, outputs and artifact hashes can be retained.
Missing access, identity mismatch, unclear mutation authority, conflicting
instructions or no available supported route yields `Environment: BLOCKED` and
a stop before adoption authoring. Narrative simulation, reconstructed output or
a plausible completion story is never technical evidence.

## Single execution contract

Only after accountable acceptance and integration of this design, followed by
a separate owner authorization for exactly one run:

1. record environment evidence and the start boundary outside the agent
   conversation;
2. send Prompt 1 only and preserve its complete response;
3. send Prompt 2 only after the clone response;
4. allow one autonomous first attempt with no correction or extra request;
5. if the agent asks about ownership, commitment or conflicting authority,
   preserve that request and stop the attempt before answering;
6. preserve the complete timestamped conversation and tool transcript
   immediately after the first response;
7. freeze the resulting workspace before an independent read-only audit;
8. do not continue, repair or coach the same agent and count that continuation
   as fresh evidence; and
9. reconcile the transcript, workspace audit and owner disposition once.

The first autonomous result is the experiment result even when it is negative,
blocked or incomplete.

## Separate A1 and A2 measurement

Route activation, A1 use and A2 use are distinct observations.

### Route activation and A1

- Route activation records whether Gnostoa was actually fetched or consulted.
- Public orientation records whether the exact
  `guidance/workflows/adopt-existing-project.md` from the frozen documentation
  subject was consulted before authoring.
- A1 content-level effectiveness is eligible only if that workflow was
  consulted. Otherwise it is `NOT TESTED`, not failed.
- `SUPPORTED` means the consulted A1 first verified slice leads the agent to
  bind a supported route, preserve unknowns, run the required source/runtime
  lock, policy, profile and bundle checks, retain bounded context, report
  unavailable project suites as `BLOCKED`, and keep outcome dimensions
  separate—or to make the correct earlier owner stop.
- `NOT SUPPORTED` requires evidence that the exact A1 text was consulted before
  the relevant action but its bounded predicted behavior was not observed. It
  is not a causal or general-effectiveness claim.

### Safe adaptation and A2

- Before writing, record whether the agent inspected existing `AGENTS.md` and
  every other mapped authoritative policy, CI or verification target it planned
  to change.
- A2 content-level effectiveness is eligible only if the transcript shows that
  the frozen preservation contract was consulted before the first affected
  target was modified. Otherwise it is `NOT TESTED`.
- A conforming outcome preserves Mail's existing project-specific instructions,
  adds only missing Gnostoa routing, retains unrelated content and ordering
  where practical, and records before/after identities and a diff.
- Conflicting instructions or unclear edit authority require leaving the target
  unchanged, recording the conflict and stopping for accountable-owner
  resolution. That can support the fail-closed A2 prediction without producing
  a completed adoption.
- Blind or destructive replacement of existing authority is `Existing-file
  adaptation: FAIL`. No structural validation can turn it into a pass.
- `SUPPORTED` and `NOT SUPPORTED` remain one-run bounded observations. Reading
  the contract without reaching any adaptation decision leaves content-level
  effectiveness `NOT TESTED`.

## Measurement and retained evidence contract

The experiment record must preserve all of the following without asking the
agent for a corrective follow-up:

- complete timestamped prompts, responses and tool transcript;
- every substantive command, working directory, timestamp and numeric exit
  code;
- environment eligibility, deviations and exact tool versions;
- exact Gnostoa and Mail pages and files consulted, with their bound source
  identities;
- selected native, source-built or immutable-OCI execution route and its exact
  observed source/runtime identities;
- initial and final Mail commit, tree, branch, status, staged representation and
  diff;
- complete created, modified and deleted file inventory with modes and SHA-256;
- before/after `AGENTS.md` identities and exact diff;
- `.gitmodules`, submodule worktree revision, staged gitlink and equality
  evidence when a submodule is used;
- raw source/runtime-lock, policy, profile, bundle and other claimed validation
  outputs;
- retained bounded-context artifact and SHA-256, not stdout-only or a collapsed
  display;
- project-suite outputs or bounded evidence for every truthful `BLOCKED` result;
- every unresolved ownership, provenance, timestamp, commitment or conflict
  question; and
- one final SHA-256 manifest covering the retained artifacts.

The evidence contract does not request private chain of thought, credentials,
irrelevant shell history or a generic receipt mechanism. Missing required
evidence narrows the corresponding result; a final narrative cannot replace it.

## Independent read-only audit

After the executing agent stops, a separate auditor receives the frozen
subjects and preserved evidence and inspects the frozen workspace without
repairing, installing, fetching, validating, running project suites or changing
Git state. The audit must distinguish:

- what the agent claimed;
- what the transcript binds to exact commands and outputs;
- what the filesystem and Git representation establish mechanically; and
- what remains an accountable-owner semantic judgement.

At minimum it recomputes retained file hashes, inspects initial/final Git state,
compares the staged gitlink with any submodule worktree revision, verifies the
`AGENTS.md` before/after preservation evidence, inventories ignored and untracked
effects, and checks whether claimed artifacts exist. It must not repair the
workspace or reinterpret a plausible claim as execution. The final
reconciliation resolves transcript/audit conflicts explicitly and records one
owner disposition.

## Independent result dimensions

Use the earlier diagnostic classifications unchanged where they already exist,
and add the A2-specific and requested subdimensions below. Do not collapse them
into one aggregate `PASS`.

| Dimension | Allowed result |
|---|---|
| Environment | `PASS / BLOCKED` |
| Route activation | `PASS / PARTIAL / FAIL` |
| Public orientation | `PASS / PARTIAL / FAIL` |
| Technical execution | `PASS / PARTIAL / FAIL / NOT RUN` |
| Published OCI execution | `PASS / FAIL / NOT RUN` |
| Runtime-lock validation | `PASS / FAIL / NOT RUN` |
| Policy, profile and bundle validation | `PASS / PARTIAL / FAIL / NOT RUN` |
| Structural validation | `PASS / FAIL / NOT RUN` |
| Bounded context | `PASS / FAIL / NOT RUN` |
| Project suites | `PASS / FAIL / BLOCKED / NOT RUN` |
| Existing-file adaptation | `PASS / FAIL / NOT RUN` |
| Git representability and gitlink equality | `PASS / FAIL / NOT RUN / NOT APPLICABLE` |
| Semantic fidelity | `PASS / PARTIAL / FAIL` |
| Agent evidence binding | `PASS / PARTIAL / FAIL` |
| Owner acceptance | `ACCEPT / CORRECT / REJECT` |
| Measured utility | `POSITIVE / MIXED / NEGATIVE / UNKNOWN` |
| Durable adoption | `YES / NO / DEFERRED` |
| A1 content-level effectiveness | `SUPPORTED / NOT SUPPORTED / NOT TESTED` |
| A2 content-level effectiveness | `SUPPORTED / NOT SUPPORTED / NOT TESTED` |

Structural validation is `PASS` only when the required source/runtime-lock,
policy, profile and bundle validations all run successfully through the bound
route. `knowledge check-guardrails` is not added as a mandatory A1 adopter gate
by this design; if it is not otherwise applicable, its absence does not decide
structural validation.

Inventing a person, team, provenance, timestamp, owner acceptance or durable
adoption commitment is `Semantic fidelity: FAIL`; draft or schema-valid status
does not make an invented fact true. An unknown must stay explicit and
unresolved or produce the applicable owner stop.

## Pre-registered interpretation and non-claims

- If the named existing-project workflow is not consulted, A1 content-level
  effectiveness is `NOT TESTED`.
- A2 is assessed independently: unless the transcript binds consultation of the
  exact preservation contract on the frozen public surface before an affected
  write, A2 content-level effectiveness is `NOT TESTED`. Consultation through
  another public route does not make A1 eligible.
- If the A2 contract is consulted and existing authority is preserved and
  augmented—or preserved unchanged with the required owner stop—the result
  supports only bounded A2 usability in this run.
- A correct stop on unknown ownership, commitment or conflict can be semantic
  success without technical completion or durable adoption.
- A different result from #117 or #122 does not by itself prove that A1, A2,
  prompt wording, agent identity or any other variable caused the difference.
- No owner correction during the run may be counted as first-attempt evidence.
- A negative or blocked result is valid evidence and does not authorize
  mechanism rescue or another replay.

This design supports no aggregate adoption claim, reliability rate, model or
vendor ranking, productivity or cost-reduction claim, general product fit, B3
completion or Decision-0036 satisfaction. It admits no generator, initializer,
new schema, validator, CLI, workflow, mutable image tag or further adopter
guidance change.

## Current stop point

This slice stops after exact-candidate verification and accountable review of
the draft pre-registration. It does not send either prompt, create an experiment
workspace, preload source or an image, mutate Mail, authorize the run or select
another remediation. Work Item #125 remains open with `roadmap:now` through the
later separately authorized run, final reconciliation and close-last owner
disposition.
