---
type: Runbook
title: Deliver a bounded self-hosted slice
description: Short Gnostoa-self operational route from current-subject orientation through exact-candidate verification, authorized integration, subject re-binding and close-last reconciliation.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-22T07:25:33Z"
sources:
  - id: delivery-practice-work-item
    resource: https://github.com/ktogias/gnostoa/issues/80
    title: Canonicalize bounded self-hosted delivery practice
  - id: agent-execution-recovery-work-item
    resource: https://github.com/ktogias/gnostoa/issues/308
    title: Enforce a single active implementation identity per Work Item across sessions
x-project-knowledge:
  id: kit.runbook.deliver-bounded-self-hosted-slice
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0036-canonicalize-bounded-self-hosted-delivery-practice.md
    - kind: governed-by
      target: /decisions/0053-require-lightweight-work-item-micro-retrospection.md
    - kind: governed-by
      target: /decisions/0058-harden-behavioral-diagnosis-evidence-authority.md
    - kind: governed-by
      target: /decisions/0061-retain-individual-agent-review-dispositions.md
    - kind: governed-by
      target: /decisions/0062-require-proportionate-prior-art-and-reuse-review.md
    - kind: depends-on
      target: /lifecycles/evidence-gated-capability-evolution.md
    - kind: references
      target: /requirements/retrospective-findings-require-explicit-admission.md
    - kind: references
      target: /requirements/bounded-behavioral-traceability.md
    - kind: references
      target: /decisions/0024-separate-stable-navigation-from-volatile-state.md
    - kind: references
      target: /decisions/0090-require-pre-candidate-preparation-receipts-for-non-hook-authoring.md
    - kind: references
      target: /runbooks/maintain-the-kit.md
    - kind: references
      target: /runbooks/publish-source-only-release.md
---

# Deliver a bounded self-hosted slice

**Scope: ordinary changes to Gnostoa itself.** This is an operational route, not
a second lifecycle and not adopter guidance. The
[evidence-gated lifecycle](../lifecycles/evidence-gated-capability-evolution.md)
owns epistemic order, gap classes, selection/admission and oracle limits.

## Compact task input

An ordinary task prompt normally supplies only the concrete task or selected
owner outcome, authoritative starting subject, admitted scope and exclusions,
task-specific stop conditions, material evidence, authorized effects and the
result needed for the next owner decision. There is no fixed length limit.

## Preconditions

- The current source and provider subject can be read back.
- The concrete task, admitted scope and accountable owner are known.
- Any required Work Item, Decision and pre-implementation evidence are present
  before implementation begins.
- When the proposed work originates from a finding, its finding provenance and
  admission state can be identified separately from the evidence that discovered
  it.

## Prior-art and reuse checkpoint

Before creating or materially revising an Issue, Decision or PR, and before new
code or implementation, check existing project work and suitable external
projects for the same bounded need. Apply this checkpoint before the procedure's
create/admission steps, including finding capture. Prefer using, adapting or
composing an existing suitable mechanism; justify the remaining custom work.

First inspect the current Work Item, related PRs, Decisions and relevant project
knowledge, then consult primary project documentation and license sources for
plausible external alternatives. Preserve one compact assessment in the owning
Work Item, Decision or PR, linked from subsequent steps. Research may be prepared
locally before that first record is created. A separate report, fixed source
count or new issue solely for the search is not required. Retain:

- the question, scope, research date and the sources/search boundary inspected;
- plausible candidates, the versions or revisions inspected, intended use and
  relevant capabilities, limitations and operational/maintenance cost;
- license and provenance evidence for that use, including applicable dependency,
  distribution, attribution and NOTICE obligations; consult
  [the licensing contract](https://github.com/ktogias/gnostoa/blob/main/LICENSING.md) rather than treating an inventory
  or an "open source" label as compatibility clearance;
- the disposition: use, adapt, compose or implement the residual need, with
  reasons for rejecting material alternatives and remaining uncertainty.

Running an external service, adding a dependency and copying or distributing
material are different uses. Resolve material license uncertainty before the
affected acquisition, copying, dependency or distribution effect; record an
unavailable search as incomplete rather than inventing a negative result.
Research itself supplies no implementation admission or effect authority.

If no suitable complete project is found within the recorded search, inspect
relevant established practices, patterns and antipatterns before custom design.
State what transfers to this task and what still needs verification. An existing
checker, orchestration tool or template does not establish that its inputs are
authoritative, its invocation is unavoidable or its result has a real consumer.

At each later transition, reuse the assessment when its question, scope and
material inputs still apply. Revalidate affected conclusions when requirements,
candidate/version, license, environment or security/support facts change; avoid
both a stale blanket approval and a full repeated search for an unchanged need.
The reviewer checks applicability and rationale alongside the actual candidate.
This is review enforcement, not a software gate or proof of search completeness.
The existing emergency route retains its declared timing and follow-up.

## Procedure

1. **Orient and read back the current subject.** Start through `AGENTS.md`; bind
   protected source, provider lifecycle and the active Work Item without replaying
   raw conversations. Before creating another Work Item or PR for the same outcome,
   read provider state for an existing open same-purpose record. Resume it when it
   already owns the outcome; otherwise explicitly separate or supersede it before
   creating a competing canonical path. Use Decision 0016's resume route.
2. **Classify the observed gap.** Apply the
   [canonical lifecycle](../lifecycles/evidence-gated-capability-evolution.md);
   do not infer a new mechanism or implementation from research or selection.
3. **Check finding provenance and admission.** When the proposed change comes from
   a retrospective, experiment, evaluation, review, incident analysis or similar
   finding, apply the
   [explicit-admission requirement](../requirements/retrospective-findings-require-explicit-admission.md).
   Capture the observation in its owning evidence first. Resume the existing
   same-purpose Work Item when it already owns the outcome; otherwise create one
   focused tracked Work Item with desired outcome, bounded acceptance criteria,
   scope and explicit admission condition. Issue creation is capture, not
   implementation admission and does not automatically become active WIP or
   `roadmap:now`. A lesson without a concrete actionable outcome may remain
   knowledge-only. Stop before implementation until a separate observable owner
   admission selects the work under the current classification, Decision,
   pre-implementation evidence and effect boundary.
4. **Acquire bounded evidence or research.** Reuse or update the
   [prior-art assessment](#prior-art-and-reuse-checkpoint), load only what
   distinguishes the proposed result and preserve negative findings. Confirm
   its applicability again before a Decision, PR or implementation transition.
5. **Obtain an owner semantic choice when required.** Oracle or unresolved
   semantic limits remain human decisions.
6. **Name the proposed surface and class.** Use the generic
   [change workflow](../../guidance/workflows/propose-review-merge-change.md) and
   `policy/change-control.yaml`; reclassify upward if the real surface expands.
7. **Satisfy implementation admission.** Create or link required records and
   establish the applicable pre-implementation evidence before editing. A finding
   Work Item recorded for backlog capture satisfies durable tracking only; it does
   not satisfy this admission step until its separately declared admission state is
   observed.
8. **Make the smallest admitted change.** When the Requirement's applicability
   criteria hold, apply the
   [bounded behavioral-traceability requirement](../requirements/bounded-behavioral-traceability.md)
   and record its initial behavior map in the active Work Item or change record
   **before the first semantic production mutation**. Use explicit prospective,
   `NOT RUN`, `UNKNOWN` and `PENDING` states where candidate or evidence does not
   exist yet; re-bind the final candidate and evidence before review. An
   unresolved contradiction or unsupported narrowing blocks review-ready
   disposition. When material diagnostic ambiguity exists, keep task obligations,
   semantic hypotheses and implementation claims separate; retain the evidence
   authority/dependency needed to show what each item can actually establish.
   Then follow the
   [verification-first workflow](../../guidance/workflows/develop-verification-first.md)
   and keep specialized semantics in their owning runbooks.
9. **Verify the exact candidate.** Inspect the final diff, identify the measured
   subject, run applicable local/runtime checks and record actual results. For an
   applicable behavior map, independently reconcile the behavior map against the
   exact task, candidate and evidence. When the task has material diagnostic
   ambiguity or comparable high correctness risk, use a bounded two-pass reviewer
   route: **independent task-to-code pass** first, then **map reconciliation pass**.
   In the first pass, inspect the exact task and candidate before consuming the
   executor's final diagnosis/map conclusions and record materially plausible
   causes, affected paths or interpretation risks. In the second pass, compare
   that view with the executor's hypotheses, rejected alternatives, evidence
   authority/dependencies and final candidate. A different model or fresh context
   may reduce correlated blind spots but does not establish evidence independence.
   Reviewer inference remains inference; unresolved task identification remains
   unresolved rather than becoming acceptance. A passing test that preserves
   task-prohibited behavior remains a blocker. Apply
   [supplied-agent review capture](#supplied-agent-reviews) when reviews are
   received, including outside this exact-candidate checkpoint.
10. **Verify the exact PR head.** Provider checks must bind to that head; inspect
    required jobs individually. A successful run does not turn `SKIPPED` into
    `PASS`.
11. **Obtain authority for the exact effect.** Repository preparation and green
    evidence do not authorize merge or another provider mutation. For release or
    publication effects, follow the specialized runbook instead.
12. **Perform only the authorized effect.** If the Work Item must survive merge,
    keep provider metadata and the prospective merge message free of automatic
    closing semantics; the
    [source-release runbook](publish-source-only-release.md) records the known
    GitHub parsing precaution.
13. **Read back integrated and provider state.** PR-head verification and the
    integrated-main revision are separate observations. Read the exact protected
    revision, changed paths, provider jobs and lifecycle state.
14. **Re-bind the subject and reconcile.** A new SHA alone does not invalidate
    evidence. Prove the relevant subject unchanged before reuse; when it changed
    materially, replay only affected evidence. Re-read navigation under
    [Decision 0024](../decisions/0024-separate-stable-navigation-from-volatile-state.md).
15. **Record the micro-retrospective.** Before closure, answer briefly: what was
    expected; what actually happened; what surprised us or was detected late;
    which existing control worked or failed to activate; and whether one concrete
    improvement is worth considering later. The close-out comment is normally
    sufficient. A finding is not automatic implementation admission; route a
    concrete follow-up through step 3 rather than starting it automatically.
16. **Close the Work Item last.** Close only after integrated/provider read-back,
    subject re-binding, reconciliation and the micro-retrospective succeed; then
    record the next owner decision without starting it automatically.


## Conditional agent execution recovery playbook

This section records the recovery route used when an agent/cloud execution
environment cannot use the shorter ordinary path. It is **not** a general
delivery workflow and does not replace the procedure above, Decision 0090 or the
recommended Development Container.

### Capability preflight and route selection

Choose the shortest trustworthy route that the current environment actually
supports. In order of preference:

1. Reuse or create a normal exact Git checkout and use the repository's
   Development Container/local tooling, exact-parent `ci/prepare-candidate` and
   an ordinary guarded Git push.
2. Reuse an already materialized exact checkout from the current runtime only
   after verifying its `HEAD`, `HEAD^{tree}` and clean status against provider
   read-back.
3. Use the recovery mechanisms below only for a measured missing capability.
   A prior session's limitation is not evidence that the limitation still
   exists.

The recovery route became useful under combinations of these observed
constraints:

- the execution shell could not resolve or connect to `github.com`, even though
  the GitHub provider connector could read repository metadata;
- the connector could read UTF-8 files but could not materialize non-UTF-8 Git
  blobs or a complete repository archive directly;
- no exact local checkout existed for the current PR head;
- the local runtime temporarily lacked Docker, Ruff, mypy or the complete
  development environment required by the parent-owned preparation path;
- the available provider connector exposed Git-data/ref primitives but not every
  convenient transport operation, such as a directly usable binary archive or
  workflow-dispatch action;
- a long-running local process could outlive or be terminated independently of
  the visible chat execution, so detached work could not be treated as exclusive
  writer ownership.

If none of those constraints applies, do **not** create helper branches,
source-export workflows or provider-side preparation jobs merely to reproduce
this recovery route.

### Reuse local state only after identity checks

Before exporting source, inspect already materialized workspaces and retained
receipts. A directory name, previous chat statement or apparent clean tree is
not identity evidence. Require:

- exact provider PR/branch head read-back;
- `git rev-parse HEAD` equal to the required 40-character parent;
- `git rev-parse 'HEAD^{tree}'` equal to the provider-observed tree;
- an empty `git status --porcelain`;
- for a retained preparation receipt, successful parent-owned receipt
  verification against the exact parent, prepared tree and separately retained
  receipt digest.

A tree-equivalent checkout with a different commit SHA is useful for byte
comparison but is **not** an exact parent for Decision 0090 preparation. Acquire
the real commit object before issuing a parent-bound receipt.

### Exact-source acquisition fallback

When direct clone/fetch/archive materialization is unavailable but GitHub Actions
can check out the repository, use a temporary helper branch only as a transport
surface:

1. Start it at the exact required commit. Do not create a second implementation
   PR or treat the helper branch as implementation authority.
2. Use a pinned `actions/checkout`, `contents: read`,
   `persist-credentials: false`, and an explicit exact SHA.
3. Assert exact `HEAD`, exact `HEAD^{tree}` and a clean checkout before export.
4. Create a `git bundle`, run `git bundle verify`, retain its SHA-256 and upload
   it as a short-lived artifact.
5. After download, verify the artifact digest and bundle again, clone from it,
   check out the exact commit and repeat the head/tree/clean assertions.

Use this route because the direct transport is unavailable, not because bundles
are intrinsically preferable to `git clone` or an existing exact checkout.

### Local RED/GREEN and candidate shaping

Recovery may acquire exact source, inspect provider state and restore missing
tooling before behavioral evidence exists, because those operations do not
themselves mutate the semantic candidate. Before the **first semantic edit**,
record one compact chronology checkpoint:

- exact parent/head and change class;
- evidence mode: `RED`/reproducer, `CHARACTERIZATION`, non-executable
  `STRUCTURAL`, or an explicitly admitted `EMERGENCY_POST_EVENT` path;
- exact command or criterion and the expected pre-change result; and
- the observed pre-change result and why it distinguishes the intended change
  from a false positive.

For a reproduced defect or new executable/conformance behavior where failing
evidence is applicable, do not start the fix until RED has been observed on the
exact pre-change subject. A behavior-preserving refactor uses a green
characterization baseline instead; prose-only knowledge uses an unmet
structural/semantic criterion plus accountable review rather than a ceremonial
unit test.

If an agent discovers that a semantic candidate was already edited before the
required checkpoint, stop shaping the candidate. Preserve the intended
regression test separately, restore the affected production bytes to the exact
pre-change subject, and run that same evidence to establish a **late RED
reconstruction**. Then restore the candidate and prove GREEN. Record both the
late reconstruction and the chronology violation: reconstructed RED repairs the
evidence gap but does **not** retroactively make the original authoring sequence
verification-first.

Work from the exact parent checkout and keep provider state read-only while the
candidate is still local. Reproduce the declared RED/characterization on the
clean parent, apply only the admitted delta, then run the focused GREEN suite.
Before preparation, run the cheap deterministic checks available in the
environment: focused unit tests, `git diff --check`, Python compilation, Ruff
format/lint and strict mypy for affected trust domains where applicable.

Run permission-sensitive tests as the ordinary non-root development user.
Executing them as `root` can invalidate tests that intentionally rely on
filesystem permissions such as `chmod 000`.

Treat unpublished work left by another execution as an input candidate, not as
trusted completion. Compare it with the exact parent, inspect the diff, run the
same checks and keep only the selected canonical variant.

### Decision 0090 preparation

For a Python-affecting candidate, the ordinary preferred route remains the
exact-parent wrapper in the Development Container as documented in `AGENTS.md`
and Decision 0090.

If the local environment cannot provide the required Docker/development tooling,
a provider-side preparation fallback may be used with the same trust boundary:

- reconstruct one immutable candidate patch against the exact parent and bind
  its SHA-256 and exact changed-path set;
- run candidate code only in a **read-only** preparation job with the exact
  parent checkout and exact development dependencies;
- execute the parent-owned `ci/prepare-candidate`, retain the external receipt,
  receipt digest, prepared tree, normalized patch digest and changed paths;
- upload only the non-secret preparation evidence/artifact needed by the
  publication step;
- keep any write-capable job separate from the candidate-executing job.

The write-capable job must not execute candidate code. It may verify the
parent-owned receipt, apply the already prepared normalized patch, reconstruct
the exact prepared tree, inspect Git identity and perform the bounded Git
effect. If a normal local preparation environment is available, use it instead
of creating this provider-side fallback.

### Secret-bearing execution boundary

Never give provider secrets or an effect-capable credential to code checked out
from a mutable PR branch or a dispatch-selected arbitrary ref. A manual
credentialed workflow must execute its runner from protected/trusted integrated
source (for example current `main` or a separately prior-effective immutable
runtime). The PR number, requested candidate head and provider subject are data
inputs to that trusted runner, not the source from which the secret-bearing code
is loaded.

Pre-merge tests of a new credentialed adapter therefore use fakes/non-secret
paths. Real secret-backed dogfood waits until a trusted runner is available, or
uses an already prior-effective trusted runner. This rule is independent of
whether the repository is private or whether the dispatching actor has write
access.

### Trusted Environment secret migration and functional verification

When a new credentialed readback route uses a provider Environment as its
non-bypassable secret-admission boundary, configure and verify that boundary
before relying on the workflow:

1. create the named Environment with custom deployment-branch policies;
2. disable administrator bypass when the Decision requires a non-bypassable
   branch restriction;
3. admit only the protected/trusted execution branch (for Gnostoa-self
   analyzer readback, exactly `main`);
4. create the Environment-scoped secrets first;
5. read back only secret **names/metadata** and the Environment policy; never
   attempt to retrieve or retain secret values;
6. only after the Environment copies are confirmed, delete broader
   repository-level copies of the same secret names;
7. read back repository secret names and prove those broader copies are absent.

Do not reverse steps 4-6: deleting the only working credential copy before the
Environment copy exists creates avoidable recovery pressure.

If the credentialed workflow is new and does not yet exist on the trusted
integrated branch, do not weaken the Environment policy temporarily just to test
it from a candidate/helper ref. Functional credential verification has two safe
routes:

- use an already prior-effective trusted runner that references the Environment;
  or
- perform a direct **read-only maintainer-side provider probe** with the same
  credential value, supplied interactively to the process and never written to
  the repository, shell history, logs or retained evidence.

For a direct probe:

- read the token without terminal echo inside a disposable process (for
  example in-process `getpass` or a child-shell `read -rsp`);
- construct the provider's admitted authentication header in process, or deliver
  it through protected stdin/a file descriptor (for example curl's `--header @-`);
  never expand the credential into process arguments, including `curl -H` or
  a command-line assignment passed to `env`;
- disable shell tracing and HTTP verbose/debug output before accepting the
  value, and avoid broad environment export or persistent header/config files;
  stdin and descriptors reduce argv exposure, but do not protect against a
  hostile same-user debugger or administrator: use a trusted local process
  boundary;
- query an already-known repository/run/change-request subject through the same
  API origin and read surface used by the adapter;
- verify an exact non-secret subject identity in the response, not merely HTTP
  connectivity;
- classify rate limiting first using the provider's documented signals:
  HTTP 429, or a throttled 403 identified by headers such as
  `x-ratelimit-remaining: 0` / `retry-after` or a bounded rate-limit diagnostic;
  do not rotate, delete or overwrite a credential because a probe was throttled;
- after excluding rate limiting, distinguish 401 authentication rejection from
  403 access/permission denial; a denied 403 does not alone prove that the
  credential value is invalid. Stop verification-before-store on either denial
  and retain wrong/missing subject identity as a separate binding/readback failure;
- retain only a non-secret receipt: provider, endpoint class, subject identity,
  HTTP/auth outcome, observation time and whether exact binding succeeded;
- unset the credential and remove temporary response files immediately after the
  probe.

A direct probe proves that the token value is currently accepted for the
intended read scope. It does **not** prove that the GitHub Environment will inject
it into the future workflow. After integration, run the official trusted
Environment-bound workflow from `main`; that post-integration smoke proves the
combined Environment-policy, secret-injection, adapter and artifact path.

If the token value has already been stored in the Environment and neither the
owner nor another authorized secret manager retains it, GitHub cannot reveal it
again. Do not treat Environment-secret metadata as functional-auth evidence.
Rotate instead:

1. create a fresh provider token;
2. **before storing it**, run the bounded read-only exact-subject probe while the
   value is still available in memory/interactive shell state;
3. if the probe succeeds, write that exact value to the Environment secret;
4. read back only the secret name/update metadata;
5. unset/discard the local value;
6. revoke the superseded provider token when its identity is known and doing so
   cannot disrupt another consumer.

This **verify-before-store** order prevents a write-only secret store from
destroying the only opportunity for pre-merge functional validation.

Provider token type is part of the verification subject, not interchangeable
metadata. Probe the same API class the adapter will use. In particular, Codacy
API v3 PR-analysis readback requires an **account API token** supplied through
the `api-token` header; a repository token authorizes only a restricted subset
of v3 operations and must not be treated as equivalent. Apply the rate-limit
classification above before interpreting a denied adapter-surface probe. Once
throttling is excluded, a 401 authentication rejection or 403 access denial
blocks verification-before-store even if another Codacy endpoint accepts that
credential; inspect token type and scope rather than assuming every denial
requires rotation. Verify a new Codacy credential first against an
account-authenticated v3 endpoint and then against the exact repository/PR
analysis endpoint before storing it.

Never broaden an Environment from `main` to a helper/candidate branch merely to
move this smoke earlier. The absence of a pre-merge trusted runner is a lifecycle
fact, not a reason to weaken the secret boundary.

When giving a maintainer an interactive verification command, do **not** place
`exit`, `exec`, or persistent `set -e/-u/-o pipefail` state directly in the
parent interactive shell. A final `exit "$rc"` closes the maintainer's terminal,
and `set -e` can terminate the shell on an expected verification failure before
the result can be read. Put the verification in a disposable script or explicit
subshell instead; let only that child process exit, print the result, and keep the
parent terminal alive. Prefer a final interactive pause when the maintainer is
copying output manually.

### Atomic publication and concurrent-writer fencing

Immediately before any branch/ref mutation, re-read the implementation branch
head. Publish the prepared tree as one commit with the expected exact parent and
use an atomic guarded effect: an ordinary non-force fast-forward when possible,
or `git push --force-with-lease=<ref>:<expected-parent>` when a provider-side
transport requires it.

Do not publish a Python candidate through a sequence of per-file Contents API
commits: that exposes intermediate unprepared candidate states and breaks the
prepared-tree identity.

If the guarded effect fails because the branch moved, stop. Read the new head
and compare it with the prepared result:

- if another execution already published the **same prepared tree**, treat
  adoption as read-only reconciliation of an existing effect, never as permission
  to perform another write. Require attributable preparation provenance, verify
  the retained receipt with its separately retained digest under its exact
  parent-owned authority, and check that the published commit's **sole parent**
  equals the receipt-bound parent and its tree equals the prepared tree;
- compare the published commit's parent, not the published commit itself, with
  the receipt-bound parent. Record the observed commit and obtain its own
  exact-head CI/review evidence before continuing;
- if the parent, provenance or tree does not match, do not adopt tree equality
  alone as proof of prepared publication. Re-bind/reconcile the observed state
  and prepare any successor from the new exact parent; never replay the old
  receipt as authority for a new-parent write or force-write over another writer.

A same-tree no-op writer-epoch commit is an incident-recovery fence, not an
ordinary publication technique. Use it only when the owner explicitly directs a
takeover after observed concurrent-writer behavior and every participant is
expected to perform pre-write head checks. Do not create ping-pong no-op commits
as a liveness probe.

Chat/UI interruption is not evidence that an earlier execution stopped. On
resume, provider head/activity read-back comes before mutation. Unexpected head
movement is a blocking `CONCURRENT_WRITER` observation until reconciled.

### Exact-head review and CI reconciliation

After publication, verify branch and PR head equality and changed paths. Before
fresh external review, post the canonical unedited top-level seal whose first
line is:

`Exact review candidate: <40-character SHA>`

Trigger reviewers separately when their integration requires an isolated
trigger comment; do not combine multiple trigger commands into one comment.
Resolve findings against the exact reviewed head. Prefer one coherent prepared
follow-up for related findings over a stream of single-finding micro-commits.

A Decision 0090 receipt binds its prepared **tree** and exact preparation
parent. For an already-published direct child, verify the parent/tree/provenance
conditions above. For a later same-tree descendant, retain older preparation
evidence only as tree-level history, not as a receipt for the descendant's parent
or authority for another write. Re-bind the observed subject and re-run/re-read
its exact-head CI and review evidence; any successor publication requires
preparation bound to its own exact current parent.

Inspect the authoritative CI jobs individually. `SKIPPED`, `CANCELED` and
`SUCCESS` are distinct states. In particular, the repository's branch advisory
uses `cancel-in-progress: true`; older advisory jobs canceled after a newer push
to the same helper branch are stale-work cancellation, not test failures.

A PR branch update performed by a GitHub Actions job using `GITHUB_TOKEN` can
cause subsequent PR checks to require explicit owner approval in the GitHub UI.
Treat that approval as a provider safety checkpoint, not as evidence that the
candidate failed. Prefer an ordinary direct user/provider ref effect when it is
already available and safe; do not route through `GITHUB_TOKEN` merely to create
this approval step.

### Cleanup and restart

Keep helper branches and artifacts narrowly named, short-lived and free of
secrets. Do not delete the only copy of a source bundle, receipt or normalized
patch until its exact identities have been recorded and the intended provider
effect has been read back. After integration/reconciliation, remove obsolete
helper branches/artifacts according to provider capability and retention policy.

After a session interruption, reconstruct state in this order: provider PR/ref
head and current checks/reviews; exact local workspaces and any still-running
processes; retained receipts/artifacts; then the next safe effect. Never infer
completion from a chat transcript, a helper branch name or a detached process
alone.


## Supplied agent reviews

When agent reviews are supplied for Gnostoa work, whether the owner forwards
them or we commission them, record each reviewer before reporting the reviews
as handled. Use the owning PR or Work Item review record and keep the existing
capture, language and authorized-effect limits of this runbook. If publication
is unavailable or not authorized, retain the pending record in the active
change record rather than an ephemeral session note, state that limit
explicitly and publish it once the effect is authorized. Link an existing
sufficient record instead of duplicating it. A compact table normally suffices,
but a combined verdict must not replace individual dispositions.

For each supplied review, retain:

- Source or supplied attribution, reviewed subject/head and the reviewer's
  reported verification environment and date. Mark missing or unverified
  attribution, subject binding or environment explicitly; a supplied model name
  is not authenticated reviewer identity.
- Reported findings, including explicit no-findings reports, limitations and
  conditional recommendations. Do not infer "no findings" from silence.
- The reviewer's own overall recommendation, or that none was supplied.
- Our disposition of each finding and the review overall, with rationale,
  evidence links, resolution subject/head and remaining uncertainty. Distinguish
  addressed, accepted for follow-up, deferred, not adopted and unresolved items;
  agreement alone does not mean implementation is complete.

Shared findings may use one evidence link while retaining each reviewer's
attribution. Keep original recommendations separate from our conclusions.
Record corrections or superseding reviews explicitly rather than silently
rewriting history or treating an older-head review as review of a new head.
Distinguish reviewer-reported execution from our reproduction and from evidence
we have not inspected.

Agent recommendations do not supply human semantic acceptance, merge authority
or implementation admission. Apply the
[explicit-admission requirement](../requirements/retrospective-findings-require-explicit-admission.md)
to new work. Record capture and source validation are review practices; neither
establishes mandatory software enforcement or prevents future omissions.

## Verification

Use the repository's current policy and container routes rather than copying a
fixed suite here. Record exact-candidate and integrated-main results separately,
including public-surface digest, executable/runtime-subject equality and X3 when
applicable. Provider command success is not authoritative read-back.

## Recovery

On subject drift, a failed required job, an unexpected provider effect or scope
expansion, stop before the next effect. Read back the authoritative state,
reclassify or re-bind as applicable, and return to the owner rather than silently
retargeting the slice.

## Fresh-agent falsification

Run the retrospective's fresh-agent test on the first naturally occurring
eligible ordinary slice. The agent should reconstruct this route from repository
knowledge using only task-specific input. This tests discoverability and process
reconstruction, not semantic autonomy or adopter transfer.
