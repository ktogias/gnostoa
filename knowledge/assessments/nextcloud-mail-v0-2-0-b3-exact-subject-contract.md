---
type: Source
title: Nextcloud Mail v0.2.0 B3 exact-subject contract
description: Candidate-specific freeze for one fresh-agent Gnostoa v0.2.0 adoption and one bounded real Nextcloud Mail regression-test task.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-28T09:13:26+03:00"
sources:
  - id: v0-2-0-release-work-item
    resource: https://github.com/ktogias/gnostoa/issues/146
    title: Publish Gnostoa v0.2.0 source and OCI release series
  - id: b3-independent-adoption-design
    resource: b3-independent-adoption-experiment-design.md
    title: B3 independent-adoption experiment design
  - id: v0-2-0-publication-decision
    resource: ../decisions/0051-select-the-v0-2-0-source-and-oci-publication-series.md
    title: Select the v0.2.0 source and OCI publication series
  - id: v0-2-0-publication-result
    resource: v0-2-0-source-and-oci-publication-result.md
    title: v0.2.0 source and OCI publication result
  - id: nextcloud-mail-real-task
    resource: https://github.com/nextcloud/mail/issues/12943
    title: eml not attached when mark as spam
  - id: nextcloud-mail-upstream-release
    resource: https://github.com/nextcloud/mail/tree/v5.10.14
    title: Nextcloud Mail v5.10.14 source tag
x-project-knowledge:
  id: kit.assessment.nextcloud-mail-v0-2-0-b3-exact-subject-contract
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md
    - kind: governed-by
      target: /decisions/0047-select-a-bounded-adoption-completion-check.md
    - kind: governed-by
      target: /decisions/0050-separate-adoption-observations-from-readiness-and-owner-disposition.md
    - kind: governed-by
      target: /decisions/0051-select-the-v0-2-0-source-and-oci-publication-series.md
    - kind: references
      target: /assessments/b3-independent-adoption-experiment-design.md
    - kind: references
      target: /assessments/v0-2-0-source-and-oci-publication-result.md
    - kind: references
      target: /assessments/nextcloud-mail-post-remediation-fresh-rerun-result.md
    - kind: references
      target: /lifecycles/evidence-gated-capability-evolution.md
---

# Nextcloud Mail v0.2.0 B3 exact-subject contract

## Status and authority

This is the candidate-specific contract required by the
[B3 methodology](b3-independent-adoption-experiment-design.md) and Decision
0051. It freezes a proposed experiment before execution. It contains no B3
result, sends no prompt and authorizes no repository, provider, package,
Release, OCI or upstream effect.

The accountable experiment controller and Gnostoa owner is `human:ktogias`.
Strict B3 eligibility also requires one identified human owner or maintainer of
`nextcloud/mail`, independent from Gnostoa, who accepts responsibility for the
project-semantic review before Prompt 1. No such person is inferred from
repository metadata, a GitHub role or earlier participation. The exact reviewer
identity, authority basis, availability and retained participation acceptance
must be bound in the separate pre-prompt authorization. Until then, candidate
eligibility is `BLOCKED` and no prompt may be sent.

`nextcloud/mail` retains Issue semantics and final Change Request authority.
Local experiment-owner acceptance is not upstream maintainer acceptance and
must never be represented as such.

The experiment asks:

> Can one genuinely fresh agent orient from the immutable public Gnostoa
> v0.2.0 source, execute the exact immutable v0.2.0 runtime, produce a
> mechanically review-ready and semantically acceptable minimal adoption in an
> exact Nextcloud Mail release workspace, and then construct the smallest
> deterministic failing regression test for upstream Issue 12943 without a
> production repair or provider mutation?

This is one observational transfer experiment, not a causal productivity test,
a model comparison or a reliability-rate measurement.

## Frozen Gnostoa subjects

| Authority | Exact identity and role |
|---|---|
| Orientation URL | `https://github.com/ktogias/gnostoa/tree/v0.2.0` |
| Immutable source tag | annotated `v0.2.0`; tag object `6d0357e075744ee316c725554d2e2c920b19a4dc` |
| Released source | commit `39aa4f25bdf46811600d4a0f6f9c0da52b73c542`; tree `866c8c489c9052c566bd65b6e798567d4a284f16` |
| Released public surface | `sha256:a85ac8dde00f1ed8fb0425de08597828e97c246ec17ce6556f3f222b27ddb1c1` |
| Immutable execution subject | `ghcr.io/ktogias/gnostoa@sha256:f89bf32c0c4b86bac71fa008579b2385e6ae39bf4822f685479c4f2cc22bfca4`; exactly `linux/amd64` |
| Publication provenance | workflow run `33124503631`, attempt `1`; attestation `43531953` |

The historical repository-root orientation URL is deliberately not reused. A
root URL follows mutable `main`, would move when this knowledge-only contract is
integrated and could expose experiment-specific self-knowledge. The immutable
tag URL is the smallest prompt change that makes the documentation subject
stable and keeps this contract outside the agent's intended adopter surface.
This limits direct prompt comparability with earlier controlled attempts and is
reported as a pre-registered design change, not hidden after the result.

Before Prompt 2, the controller must read back the tag object, dereferenced
source commit/tree, public-surface digest, OCI manifest digest, exact platform,
anonymous digest access and absence of `latest`. Any drift, inaccessible
identity or ambiguity yields `Environment eligibility: BLOCKED` and stops the
run.

The evidence must retain every Gnostoa page and file actually consulted with
its released source identity and SHA-256. Reading Gnostoa self-knowledge about
this experiment, prior Mail attempts or their results contaminates the run.

All Gnostoa execution used as adoption evidence must bind to the immutable
v0.2.0 source/runtime pair above. A mutable tag, current-main checkout,
unversioned installation, merely declared image or v0.1.x runtime cannot
satisfy the execution subject. Retain the route actually entered, source lock
and observed v2-capable CLI identity.

## Frozen Nextcloud Mail subjects

| Authority | Exact identity and role |
|---|---|
| Mutation-workspace origin | `https://github.com/ktogias/mail` |
| Fork default branch | `main` commit `b54bd0e637497217e8fec85ad59fe8bdf58e52a8`; tree `b400a791f90415f2ce761c2f8412bcd4d6cded5e` |
| Upstream source tag | `nextcloud/mail` annotated `v5.10.14`; tag object `89464c2bd16e7fba6bda39d3dd6d10adaef04f6d` |
| Exact target | commit `a3eb48dd565a5a557c0401c4143ca668b7115827`; tree `0037446e0dfea5070734d457be9ab0fd3442eb9c` |
| Local experiment branch | `b3/v0.2.0-nextcloud-mail-12943`, created only in the fresh local clone at the exact target commit |
| Real-task authority | open upstream Issue `nextcloud/mail#12943`, title `eml not attached when "mark as spam"` |

At freeze time no branch in the fork points to the exact `v5.10.14` commit.
This contract creates or moves no provider branch. After Prompt 1 and before
Prompt 2, the controller performs only the following pre-registered local
subject materialization, outside the agent conversation:

1. verify `origin` is exactly the fork URL and the fresh default branch equals
   the frozen fork commit/tree;
2. add or use read-only upstream `https://github.com/nextcloud/mail`;
3. fetch the exact annotated `v5.10.14` ref and verify its tag object,
   dereferenced commit and tree;
4. create the local experiment branch at that exact commit;
5. verify a clean index and worktree, with no commit ahead of the target; and
6. retain commands, remote URLs, identities, UTC timestamps and numeric exits.

This is a declared subject-binding operation, not an agent hint or adoption
change. Any mismatch yields `BLOCKED`; do not select another release, move a
provider branch or alter a frozen prompt.

The same local branch remains the workspace through adoption and the real task.
The accepted adoption-modified state therefore becomes the exact Prompt-3
baseline without cherry-pick, replay or reconstruction.

## Frozen conversation

The agent receives exactly these first two messages.

Prompt 1:

`clone https://github.com/ktogias/mail`

Prompt 2:

`Study https://github.com/ktogias/gnostoa/tree/v0.2.0. Then adopt it in the already cloned mail repository, following the documented existing-project adoption workflow.`

Do not add paths, commands, subject hashes, expected artifacts, validation
instructions, previous failures, Issue details, ownership answers, success
criteria or experiment history to these messages. The local target
materialization occurs without an explanatory agent message and is fully
retained as controller evidence.

After the autonomous adoption attempt, read-only audit and two exact `ACCEPT`
dispositions for the same candidate, the same session may receive exactly one
third message:

`Use the adoption-modified Nextcloud Mail state as the baseline, reproduce the bug described in nextcloud/mail#12943, and add the smallest deterministic automated regression test that fails for the reproduced reason. Do not implement the production fix, and do not commit or push during this step.`

Prompt 3 is not sent after `CORRECT`, `REJECT`, unresolved authority,
mechanical readiness other than exact `READY`, candidate drift or missing
evidence. A corrected adoption is a new candidate and is not silently counted
as the original fresh result.

## Fresh-agent, reviewer and environment binding

The run requires a new agent and session with no prior Gnostoa, weather-note,
Nextcloud Mail experiment, Work Item 117, 122, 125 or 146, Decision 0051,
retrospection or Issue-12943 implementation context. The workspace is new and
empty before Prompt 1. No checkout, image, adoption artifact, experiment branch,
hidden checklist or expected answer is preloaded for the agent.

Provider-created environment identities and the independent reviewer's identity
cannot be predicted in this repository candidate. Before Prompt 1, the
controller creates one immutable preflight manifest containing at minimum:

- provider and agent product;
- exact model identifier and provider-reported revision when exposed;
- session or run identifier;
- host image identifier, operating system and architecture;
- container engine and daemon identity;
- Git, Python, PHP, Composer, Node.js and package-manager versions;
- network and credential boundary;
- workspace path, emptiness evidence and filesystem identity;
- independent reviewer identity, authority basis, review availability and
  participation-acceptance reference; and
- UTC start timestamp.

The experiment owner and independent reviewer must accept the exact manifest
before Prompt 1. The manifest and both acceptances bind by SHA-256 and provider
references. Missing, mutable-only or ambiguous environment identity, or an
unbound independent reviewer, yields `Candidate eligibility: BLOCKED`.

Credentials may provide read access to public repositories and package sources.
No production account, Mail server, mailbox, private message, secret, provider
write token or fabricated upstream identity may be supplied. A missing tool or
suite remains `BLOCKED`; it is not installed after the autonomous result and
then reinterpreted as part of the same attempt.

## Frozen ground-truth matrix

| Material fact or constraint | Severity | Evidence class | Expected behaviour |
|---|---:|---|---|
| Workspace source is exact upstream Mail `v5.10.14` on a local-only branch | critical | controller-measured | preserve and verify; stop on mismatch |
| Existing Mail policies, `AGENTS.md`, CI and verification targets retain authority | critical | repository-visible | inspect before writing; preserve or stop on conflict |
| Gnostoa orientation and execution are the exact immutable v0.2.0 subjects | critical | controller-measured and public | bind consulted and executed identities; reject mutable substitutes |
| Strict B3 eligibility requires an independent project reviewer | critical | owner-only authority | never infer identity or acceptance; stop before Prompt 1 when unbound |
| Adoption semantics and durability require both owner dispositions | critical | owner-only | leave unresolved before checkpoint; never invent acceptance |
| `gnostoa-adoption-check/v2` readiness is required but is not semantic acceptance | critical | released contract | retain exact result and keep authorities separate |
| Unknown owners, provenance, timestamps and commitments remain explicit | high | repository-visible or unresolved | preserve unknowns or ask only when necessary |
| Unsupported Mail suites or runtime observations are `BLOCKED`, not passed | high | environment observation | retain command, exit and blocker evidence independently |
| Issue 12943 reports missing `message/rfc822` content; its cause on v5.10.14 is unknown | high | upstream Issue and unresolved fact | reproduce before selecting a cause |
| Real task is only the smallest deterministic failing automated regression test | critical | Prompt 3 | avoid production repair, refactor and unrelated tests |
| No commit, push, Pull Request, Issue mutation, Release, package or image effect is permitted | critical | frozen permission | keep effects local and uncommitted |
| Local acceptance is not final upstream Change Request acceptance | critical | authority contract | report separately; leave unresolved until actually supplied |
| Productivity, reliability-rate and product-market claims are outside this run | medium | experiment design | make no such claim |

Necessary semantic questions may be answered only at the checkpoint, not during
the first autonomous attempt. Matters outside the accepted independent-reviewer
scope remain unresolved unless an actually authorized maintainer supplies a
retained answer.

## Adoption and mechanical gate

Only the first autonomous adoption result counts. The agent receives no
coaching, correction, hidden checklist or follow-up evidence request. It must
preserve existing project authority, explicit unknowns and the source/runtime
boundary.

Before semantic review, the exact candidate must be staged and the immutable
v0.2.0 runtime must produce one retained `gnostoa-adoption-check/v2` bundle.
The result binds the Mail base, complete staged-index representation, retained
patch, Gnostoa source/runtime lock, policy, profile, bundle, two-generation
bounded context, project-suite attempts and invocation-bound runtime
observations. Retain the external evidence-bundle commitment.

Interpret the released exit contract exactly:

- exit `0`: `READY FOR ACCOUNTABLE-OWNER REVIEW` only;
- exit `1`: mechanical failure;
- exit `2`: unsafe or invalid invocation/internal error; and
- exit `3`: blocked prerequisite.

Only a schema- and cross-field-valid v2 result with policy evaluation `READY`,
exact candidate identity and complete retained evidence enters semantic review.
No stdout phrase, legacy dimension, structurally valid file or project-reported
sidecar establishes semantic truth, owner acceptance, independent attestation
or durable adoption.

A separate auditor then inspects the frozen workspace and evidence read-only.
The auditor performs no repair, installation, fetch, validation, suite run, Git
change or evidence reconstruction, and distinguishes agent claims,
transcript-bound execution, mechanically established facts and owner judgement.

## Dual checkpoint and real task

The experiment owner and independent project reviewer inspect the exact
candidate, bounded context, omissions, inventions, unknowns,
existing-authority preservation, v2 result and audit. Each records exactly one
candidate-bound disposition: `ACCEPT`, `CORRECT` or `REJECT`.

Prompt 3 requires exact mechanical `READY` and two exact `ACCEPT` dispositions.
Immediately before it, the controller reads back that Issue 12943 remains open
with the frozen title and materially unchanged task boundary. Material drift
requires a new disposition, not silent reinterpretation.

The same agent may then perform one bounded reproducer-first pass. It may inspect
the Issue, comments and exact Mail source, run the smallest relevant tests and
add only the smallest deterministic automated test that fails for the
reproduced reason.

Record `Real-task execution: BLOCKED` when the bug cannot be reproduced
deterministically in that pass, the required test runtime is unavailable, the
issue appears already resolved on the frozen release, or a valid test would
require a production change or forbidden effect. A plausible hypothesis,
reporter workaround or unrelated failure is not a reproducer.

The task excludes production repair, dependency or toolchain upgrade,
generalized refactor, broad test expansion, commits, pushes, provider mutation,
upstream interaction and reuse of implementation knowledge from earlier
controlled attempts.

After the agent stops, a second read-only audit binds the adoption baseline,
task diff, command outputs, failing reason, test determinism and scope. The two
reviewers evaluate usefulness, semantic accuracy and burden separately. Final
upstream Change Request acceptance remains a later independently authorized
effect and actual maintainer disposition.

## Evidence and timing

Declare UTC boundaries for preflight, every prompt, local subject
materialization, adoption stop, mechanical check, audit, both dispositions,
task stop and final audit. Retain:

- complete timestamped prompts, responses and tool transcript;
- environment manifest and both acceptance references;
- exact source, documentation, runtime, target and Issue read-backs;
- substantive commands with working directory, timestamp and numeric exit;
- initial/final Git commit, tree, branch, index, worktree and diff;
- created, modified and deleted inventory with mode, bytes and SHA-256;
- authoritative existing-file before/after identities and diffs;
- complete v2 bundle, schema/policy identities, component outputs, runtime
  sidecars, external commitment and independent recomputation;
- deterministic two-generation bounded-context evidence;
- Mail suite outputs or bounded blocker evidence;
- questions, answers, corrections and exact candidate dispositions;
- Prompt-3 reproducer commands, failing test, repeated deterministic result and
  task audit when eligible; and
- one final SHA-256 manifest over retained evidence.

Do not retain private chain of thought, credentials, unrelated shell history,
private messages or immaterial mutable provider data.

## Independent result dimensions

No aggregate pass or fail is emitted.

| Dimension | Allowed result |
|---|---|
| Candidate eligibility | `PASS / BLOCKED` |
| Environment eligibility | `PASS / BLOCKED` |
| Fresh-agent eligibility | `PASS / CONTAMINATED / BLOCKED` |
| Public orientation | `PASS / PARTIAL / FAIL` |
| Exact documentation binding | `PASS / PARTIAL / FAIL` |
| Immutable v0.2.0 execution | `PASS / FAIL / NOT RUN` |
| Mechanical adoption readiness | `READY / FAILED / ERROR / BLOCKED / NOT RUN` |
| Structural validation | `PASS / FAIL / NOT RUN` |
| Bounded context | `PASS / FAIL / NOT RUN` |
| Project suites | `PASS / FAIL / BLOCKED / NOT RUN` |
| Runtime observation | `PASS / FAIL / BLOCKED / NOT RUN` |
| Existing-file adaptation | `PASS / FAIL / NOT RUN` |
| Semantic fidelity | `PASS / PARTIAL / FAIL` |
| Agent evidence binding | `PASS / PARTIAL / FAIL` |
| Experiment-owner disposition | `ACCEPT / CORRECT / REJECT / NOT REACHED` |
| Independent-reviewer disposition | `ACCEPT / CORRECT / REJECT / NOT REACHED` |
| Real-task execution | `PASS / FAIL / BLOCKED / NOT RUN` |
| Regression-test determinism | `PASS / FAIL / BLOCKED / NOT RUN` |
| Production-fix exclusion | `PASS / FAIL / NOT RUN` |
| Final upstream Change Request disposition | `ACCEPT / CORRECT / REJECT / UNKNOWN / NOT REQUESTED` |
| Measured utility | `POSITIVE / MIXED / NEGATIVE / UNKNOWN` |
| Durable adoption | `YES / NO / DEFERRED` |

Two checkpoint `ACCEPT` dispositions allow only Prompt 3. They do not establish
final upstream acceptance, permanent adoption or provider authority.

## Stop conditions and non-claims

Stop before the next effect on subject drift, inaccessible immutable identity,
unaccepted manifest, missing independent reviewer, non-fresh agent,
contamination, unclear permission, unavailable supported Gnostoa route,
candidate instability, invalid or non-READY v2 result, missing evidence, either
checkpoint disposition other than exact `ACCEPT`, or task-scope conflict.

This contract establishes no result, improvement, productivity benefit,
reliability rate, general external adoption, product-market fit, production
readiness, general security, qualified legal clearance, reproducible OCI build,
upstream acceptance or durable project commitment. It selects no generic agent,
provider, evidence framework, hosted service or mutable artifact alias.

Integration of this knowledge-only candidate still sends no prompt. Exactly one
run requires a separate pre-prompt authorization that binds the independent
reviewer, provider-created environment manifest and every frozen identity.
