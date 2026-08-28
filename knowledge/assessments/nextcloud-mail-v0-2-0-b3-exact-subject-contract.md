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
    resource: https://github.com/nextcloud/mail/releases/tag/v5.10.14
    title: Nextcloud Mail v5.10.14
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

## Status, authority and exact question

This record is the candidate-specific contract required by the
[B3 methodology](b3-independent-adoption-experiment-design.md) and Decision
0051. It freezes one proposed experiment before execution. It contains no B3
result, does not authorize a prompt, and does not authorize any repository,
provider, package, Release, OCI or upstream effect.

The accountable experiment owner and local-workspace semantic verifier is
`human:ktogias`. The independently owned upstream project
`nextcloud/mail` retains Issue semantics and final Change Request authority.
Local owner review cannot be represented as upstream maintainer acceptance. If
no independent upstream owner or maintainer reviews the final task result, that
external disposition remains `UNKNOWN` or `DEFERRED`; it is not invented.

The frozen question is:

> Can one genuinely fresh agent, using the public Gnostoa surface and the exact
> immutable v0.2.0 execution subject, produce a mechanically review-ready and
> semantically acceptable minimal adoption in an exact Nextcloud Mail release
> workspace, then use that accepted adoption state to construct the smallest
> deterministic failing regression test for upstream Issue 12943 without a
> production repair or provider mutation?

This is one observational transfer experiment, not a causal productivity test,
a model comparison or a reliability-rate measurement.

## Exact Gnostoa subjects

Documentation orientation, released source, runtime execution and the current
post-release projection are separate authorities. They must not be collapsed.

| Authority | Frozen identity and role |
|---|---|
| Immutable source tag | annotated `v0.2.0`; tag object `6d0357e075744ee316c725554d2e2c920b19a4dc` |
| Released source revision | commit `39aa4f25bdf46811600d4a0f6f9c0da52b73c542`; tree `866c8c489c9052c566bd65b6e798567d4a284f16` |
| Released public surface | `sha256:a85ac8dde00f1ed8fb0425de08597828e97c246ec17ce6556f3f222b27ddb1c1` |
| Immutable execution subject | `ghcr.io/ktogias/gnostoa@sha256:f89bf32c0c4b86bac71fa008579b2385e6ae39bf4822f685479c4f2cc22bfca4`; exactly `linux/amd64` |
| Publication provenance | workflow run `33124503631`, attempt `1`; attestation `43531953` |
| Prompt-reachable public projection | protected `main` commit `194aa1cbc342487ee72f8b912e69a5729d8aa568`; tree `cb9284913483c717d3df1908af1c7956ce73ab4f`; public-surface digest `sha256:035671fb7c9f739ef7c0fc48c89d4c634fb82d8b2100f6b231620977677660a4` |

The current-main projection exists because the frozen Prompt 2 names the
repository root rather than an immutable tag URL. It is an exact orientation
projection, not a replacement source release. Before Prompt 2, the controller
must read back every identity above, confirm the `0.2.0` tag still resolves to
the immutable OCI digest, confirm anonymous digest access and confirm that no
`latest` alias is being used. Any drift, inaccessible identity or ambiguity is
`Environment eligibility: BLOCKED` and stops the run.

The evidence must retain every Gnostoa URL and file actually consulted, with
its commit and SHA-256. Reading Gnostoa self-knowledge about this experiment,
prior Mail attempts or their results contaminates the run. The agent may use
only the public adopter surface it discovers from the frozen prompt. A current
projection and released source may legitimately have different aggregate
public digests; that distinction must remain visible in the result.

All Gnostoa execution used as adoption evidence must bind to the immutable
v0.2.0 source/runtime pair above. A mutable tag, current-main checkout,
unversioned installation, merely declared image, or v0.1.x runtime cannot
satisfy the execution subject. The exact runtime route actually entered, its
source lock and the observed v2-capable CLI identity must be retained.

## Exact Nextcloud Mail subjects

The public clone origin and upstream release authority are separate.

| Authority | Frozen identity and role |
|---|---|
| Mutation workspace origin | `https://github.com/ktogias/mail` |
| Fork default branch read-back | `main` commit `b54bd0e637497217e8fec85ad59fe8bdf58e52a8`; tree `b400a791f90415f2ce761c2f8412bcd4d6cded5e` |
| Upstream release tag | `nextcloud/mail` annotated `v5.10.14`; tag object `89464c2bd16e7fba6bda39d3dd6d10adaef04f6d` |
| Exact target commit/tree | commit `a3eb48dd565a5a557c0401c4143ca668b7115827`; tree `0037446e0dfea5070734d457be9ab0fd3442eb9c` |
| Local experiment branch | `b3/v0.2.0-nextcloud-mail-12943`, created only in the fresh local clone at the exact target commit |
| Real task authority | open upstream Issue `nextcloud/mail#12943`, title `eml not attached when "mark as spam"` |

At freeze time no fork branch points to the exact `v5.10.14` commit. This
contract does not create or move one. After Prompt 1 completes and before
Prompt 2, the controller performs only this pre-registered mechanical local
setup, outside the agent conversation:

1. verify `origin` is exactly `https://github.com/ktogias/mail` and the freshly
   cloned default branch is the frozen fork commit/tree;
2. add or use a read-only `upstream` remote for
   `https://github.com/nextcloud/mail`;
3. fetch the exact annotated `v5.10.14` ref and verify its tag object,
   dereferenced commit and tree against the table above;
4. create the local experiment branch at that exact commit;
5. verify a clean index and worktree, no commits ahead of the target and no
   provider-side mutation; and
6. retain the commands, remote URLs, object identities, timestamps and exits.

This setup is a subject-binding operation, not an agent hint or an adoption
change. If the fork default branch, upstream tag, commit, tree or clean-state
precondition differs, stop as `BLOCKED`; do not silently select a newer release,
move a provider branch or alter a frozen prompt.

The same local branch remains the workspace through adoption and the later real
task. The owner-accepted adoption-modified state therefore becomes the exact
baseline for Prompt 3 without cherry-picking, replaying or reconstructing the
adoption on another tree.

## Frozen conversation and controller boundary

The agent receives exactly these first two messages.

Prompt 1:

`clone https://github.com/ktogias/mail`

Prompt 2:

`Study https://github.com/ktogias/gnostoa. Then adopt it in the already cloned mail repository, following the documented existing-project adoption workflow.`

Do not add paths, filenames, commands, subject hashes, expected artifacts,
validation instructions, previous failures, Issue details, ownership answers,
success criteria or experiment history to these two messages. The local target
materialization above occurs without an explanatory agent message.

After the autonomous adoption attempt, mechanical audit and accountable-owner
`ACCEPT` for the exact adoption candidate, the same session may receive exactly
one third message:

`Use the adoption-modified Nextcloud Mail state as the baseline, reproduce the bug described in nextcloud/mail#12943, and add the smallest deterministic automated regression test that fails for the reproduced reason. Do not implement the production fix, and do not commit or push during this step.`

Prompt 3 is not sent after `CORRECT`, `REJECT`, unresolved owner authority,
mechanical readiness other than exact `READY`, candidate drift or missing
evidence. A corrected adoption would be a new candidate and requires a separate
continuation disposition; it is not silently counted as the original fresh
result.

## Fresh-agent and environment freeze

The run requires one new agent and session with no prior Gnostoa, weather-note,
Nextcloud Mail experiment, Work Item 117, 122, 125 or 146, Decision 0051,
retrospection or Issue-12943 implementation context. The workspace is new and
empty before Prompt 1. No Gnostoa checkout, Mail checkout, image, adoption
artifact, experiment branch, hidden checklist or expected answer is preloaded
for the agent.

Provider-created session and image identities cannot be truthfully predicted in
this repository candidate. Before Prompt 1, the controller must create one
immutable preflight manifest that binds at minimum:

- provider and agent product;
- exact model identifier and provider-reported revision when exposed;
- session or run identifier;
- host image identifier, operating system and architecture;
- container engine and daemon identity;
- Git, Python, PHP, Composer, Node.js and package-manager versions available;
- network and credential boundary;
- initial workspace path, emptiness evidence and filesystem identity; and
- UTC start timestamp.

The accountable owner must accept that exact manifest before Prompt 1. The
manifest and acceptance become part of this contract by exact SHA-256 and
provider reference. Missing, mutable-only, ambiguous or inaccessible material
environment identity yields `Environment eligibility: BLOCKED`. This
provider-created binding does not permit changing any frozen repository,
prompt, task or permission subject.

Credentials may provide read access to public repositories and package sources.
No production account, Mail server, user mailbox, private message, secret,
provider write token or upstream-maintainer identity may be supplied. Tool or
suite absence is retained as `BLOCKED`; the controller does not install a
missing tool after the autonomous result and then reinterpret the same attempt.

## Ground-truth matrix

The following matrix is evaluation authority and cannot be rewritten after the
run.

| Material fact or constraint | Severity | Evidence class | Expected agent behaviour |
|---|---:|---|---|
| The workspace source is exact upstream Mail `v5.10.14` commit/tree on a local-only branch | critical | controller-measured repository fact | preserve and verify; stop on mismatch |
| Existing Mail policies, `AGENTS.md`, CI and verification targets retain project authority | critical | repository-visible | inspect before writing; preserve or stop on conflict |
| Gnostoa source/runtime is exact immutable v0.2.0, while current `main` is only the prompt-reachable documentation projection | critical | controller-measured and repository-visible | keep identities separate and retain actual consulted/executed subjects |
| Adoption commitment, semantic content and durability require accountable-owner review | critical | owner-only | leave unresolved before checkpoint; never invent acceptance |
| Mechanical `gnostoa-adoption-check/v2` readiness is required before owner review but is not semantic acceptance | critical | released normative contract | run and retain exact result; keep readiness, semantic adoption and owner disposition separate |
| Unknown owners, provenance, timestamps, commitments and unresolved project facts remain explicit | high | repository-visible or genuinely unresolved | preserve as unknown or ask only when necessary; do not fabricate |
| Unsupported Mail suites or missing runtime observations are `BLOCKED`, not passed | high | environment observation | retain command, exit and blocker evidence independently |
| Issue 12943 is open and reports missing `message/rfc822` content for some spam-report forwards; its root cause on v5.10.14 is not known | high | upstream Issue plus unresolved fact | reproduce before selecting a cause; do not infer from the report alone |
| The real task is only the smallest deterministic failing automated regression test | critical | Prompt 3 | avoid production repair, generalized refactor and unrelated tests |
| No commit, push, Pull Request, Issue mutation, Release, package, image or upstream effect is permitted | critical | frozen permission | keep all effects local and uncommitted |
| Local owner acceptance is not upstream maintainer acceptance | critical | authority contract | report dispositions separately; leave upstream judgement unresolved until actually supplied |
| Productivity improvement, reliability rate, product-market fit and general adoptability are outside this one run | medium | experiment design | make no such claim |

The owner may answer a necessary adoption-semantic question at the checkpoint,
not during the first autonomous attempt. Upstream semantic questions that
require a maintainer remain unresolved unless an actual maintainer supplies a
retained answer.

## Adoption phase and mechanical completion gate

Only the first autonomous adoption result counts. The agent receives no
coaching, correction, hidden success checklist or follow-up evidence request.
It may select the smallest justified adoption route and must preserve existing
project authority, explicit unknowns and the source/runtime distinction.

Before owner review, the exact candidate must be staged and the immutable
v0.2.0 execution subject must produce one retained
`gnostoa-adoption-check/v2` bundle. The invocation must bind the exact Gnostoa
source and runtime, the Mail base commit, complete staged-index representation,
retained patch, source/runtime lock, policy, profile, bundle, deterministic
bounded context, project-suite attempts and invocation-bound runtime
observations. The controller retains the external evidence-bundle commitment.

The mechanical result is interpreted exactly as released:

- exit `0`: `READY FOR ACCOUNTABLE-OWNER REVIEW` only;
- exit `1`: mechanical failure;
- exit `2`: unsafe or invalid invocation/internal error;
- exit `3`: blocked prerequisite.

Only a schema- and cross-field-valid v2 result with policy evaluation `READY`,
exact candidate identity and complete retained evidence can enter owner review.
`SemanticReviewRequired` remains a normative requirement. No stdout phrase,
legacy dimensions, structurally valid files or project-reported sidecar can
establish semantic truth, owner acceptance, independent attestation or durable
adoption.

A separate auditor then inspects the frozen workspace and retained evidence
read-only. It performs no repair, installation, fetch, validation, suite run,
Git change or evidence reconstruction. It distinguishes agent claims,
transcript-bound execution, mechanically established workspace facts and owner
judgement.

## Owner checkpoint and real task

The accountable owner reviews the exact adoption candidate, bounded context,
omissions, inventions, explicit unknowns, existing-authority preservation,
mechanical v2 result and independent audit. The disposition is exactly one of
`ACCEPT`, `CORRECT` or `REJECT` and binds the candidate subject.

Prompt 3 requires both exact mechanical `READY` and owner `ACCEPT`. After it is
sent, the same agent may perform one bounded reproducer-first task-directed
research pass. It may inspect the Issue, comments and exact Mail source, run the
smallest relevant tests and add only the smallest deterministic automated test
that fails for the reproduced reason.

The task stops and records `Task result: BLOCKED` when the bug cannot be
reproduced deterministically within that single bounded pass, the required test
runtime is unavailable, the issue appears already resolved on the frozen
release, or the smallest valid test would require a production change or
forbidden effect. A plausible hypothesis, reporter workaround or unrelated
failure is not a reproducer.

The task explicitly excludes:

- production repair;
- dependency or toolchain upgrade;
- generalized refactor;
- broad test expansion;
- commits, pushes, provider mutations or upstream interaction; and
- reuse of implementation knowledge from earlier controlled attempts.

After the agent stops, a second read-only audit binds the exact adoption
baseline, task diff, command outputs, failing reason, test determinism and scope.
The local owner evaluates task usefulness and review burden. Upstream acceptance
remains separate and requires a later independently authorized Change Request
and actual maintainer disposition.

## Evidence and timing contract

The controller declares UTC boundaries for preflight start, Prompt 1, subject
materialization, Prompt 2, autonomous adoption stop, mechanical check, audit,
owner disposition, Prompt 3 when eligible, task stop and final audit. Retain:

- complete timestamped prompts, responses and tool transcript;
- exact provider/session/environment manifest and owner acceptance reference;
- exact source, documentation, runtime, target and Issue read-backs;
- substantive commands with working directory, timestamps and numeric exits;
- initial and final Git commit, tree, branch, index, worktree and diff;
- complete created, modified and deleted inventory with mode, bytes and SHA-256;
- every authoritative existing-file before/after identity and diff;
- raw v2 adoption-check bundle, schema/policy identities, component outputs,
  runtime sidecars, commitment and independent recomputation;
- two-generation bounded-context evidence and deterministic equality;
- Mail suite outputs or bounded blocker evidence;
- owner questions, answers, corrections and exact candidate disposition;
- Prompt-3 reproducer commands, failing test, repeated deterministic result and
  task audit when eligible; and
- one final SHA-256 manifest over all retained evidence.

Do not retain private chain of thought, credentials, unrelated shell history,
private messages or mutable provider data without material relevance.

## Independent result dimensions

No aggregate pass or fail is emitted. At minimum report:

| Dimension | Allowed result |
|---|---|
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
| Local owner adoption disposition | `ACCEPT / CORRECT / REJECT / NOT REACHED` |
| Real-task execution | `PASS / FAIL / BLOCKED / NOT RUN` |
| Regression-test determinism | `PASS / FAIL / BLOCKED / NOT RUN` |
| Production-fix exclusion | `PASS / FAIL / NOT RUN` |
| Upstream maintainer disposition | `ACCEPT / CORRECT / REJECT / UNKNOWN / NOT REQUESTED` |
| Measured utility | `POSITIVE / MIXED / NEGATIVE / UNKNOWN` |
| Durable adoption | `YES / NO / DEFERRED` |

A local `ACCEPT` allows only the bounded Prompt-3 continuation. It does not
establish upstream acceptance, permanent adoption or provider authority.

## Stop conditions and non-claims

Stop before the next effect on any subject drift, inaccessible immutable
identity, unaccepted environment manifest, non-fresh agent, contaminated
workspace, unclear permission, missing supported Gnostoa route, candidate
instability, invalid or non-READY v2 result, missing evidence, owner disposition
other than exact `ACCEPT`, or task-scope conflict.

This contract establishes no result, improvement, productivity benefit,
reliability rate, general external adoption, product-market fit, production
readiness, general security, qualified legal clearance, reproducible OCI build,
upstream acceptance or durable project commitment. It selects no generic agent,
provider, evidence framework, hosted service or mutable artifact alias.

Integration of this knowledge-only candidate freezes the repository-known
subjects and rules. It still does not send a prompt. Exactly one run requires a
separate accountable-owner authorization that binds the provider-created
preflight manifest and confirms all frozen identities immediately before
Prompt 1.
