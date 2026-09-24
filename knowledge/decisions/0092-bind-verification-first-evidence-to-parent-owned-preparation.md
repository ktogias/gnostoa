---
type: Decision
title: Bind verification-first evidence to parent-owned preparation
description: Proposed bounded VF0 authority evolution, separating authenticated pre-change observation from receipt integrity, candidate preparation and human authority.
status: draft
generated:
  by: agent:chatgpt
  at: "2026-09-24T14:55:00Z"
sources:
  - id: owning-work
    resource: https://github.com/ktogias/gnostoa/issues/15#issuecomment-5803831361
    title: Owner-selected VF0 scope and admission boundary
  - id: entrance-result
    resource: https://github.com/ktogias/gnostoa/issues/15#issuecomment-5816520445
    title: Exact-main missing-evidence preparation entrance result
  - id: records-checkpoint
    resource: https://github.com/ktogias/gnostoa/issues/15#issuecomment-5816546629
    title: Decision and plan pre-edit structural checkpoint
  - id: owner-provider-neutral-direction
    resource: https://github.com/ktogias/gnostoa/pull/319#issuecomment-5821298046
    title: Native A6 approval read-back and owner-selected abstraction requirements
x-project-knowledge:
  id: kit.decision.0092.bind-verification-first-evidence-to-parent-owned-preparation
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /decisions/0090-require-pre-candidate-preparation-receipts-for-non-hook-authoring.md
    - kind: references
      target: /decisions/0007-verification-first-development.md
    - kind: derived-from
      target: /failure-modes/verification-first-chronology-bypass-during-recovery.md
    - kind: references
      target: /assessments/15-vf0-entrance-and-execution-plan.md
---

# Bind verification-first evidence to parent-owned preparation

**Proposal, not an effective gate or implementation-completion claim.** The owner
selected VF0 and authorized autonomous continuation after #315. This record
makes the proposed mechanism and remaining proof obligations reviewable; it does
not attribute separate approval of these new design details to the owner.

## Context

The [entrance experiment](../assessments/15-vf0-entrance-and-execution-plan.md)
ran the actual integrated Decision 0090 prepare/verify path. It accepted a
synthetic semantic candidate without pre-change evidence. Its existing Ruff and
final-verification contract worked; the additional VF0 invariant is not enforced.

The aggregate enforcement change is **critical**. Keeping this first record
non-executable does not lower the eventual assurance-gate risk. Scope is private
Gnostoa-self preparation and its independent CI consumer, not the public CLI,
#308 writer leases, reviewer qualification, secret migration or a workflow engine.
VF0 remains the mandatory #15 child before #318 and the next critical activation.

## Decision

The following is the proposed design, not an activated enforcement contract.

### 1. Reuse the existing authority and the effective policy

Extend the exact-parent `ci/prepare-candidate` path, not a parallel publisher.
Any helper, policy or manifest that decides VF0 eligibility joins the immutable
parent-owned authority set and must be extracted before candidate code executes.
An editable helper import must never replace the parent's authority.

Consume the effective core and Gnostoa change-control rules. An independently
admitted change class and scope are inputs, not choices inferred from whichever
receipt is easiest to obtain. Unknown applicability denies the compliance claim.

| Mode | Permitted observation | Must not become |
| --- | --- | --- |
| RED | Exact parent production plus admitted evidence-only delta; expected non-vacuous failure | Any nonzero exit, missing import, timeout, zero tests or skip |
| CHARACTERIZATION | Parent behavior observed green where policy permits the classified behavior-preserving change | A substitute for required failing evidence |
| STRUCTURAL | Unmet non-executable criterion with accountable review where executable failure is inapplicable | A bypass for changed executable or normative behavior |
| EMERGENCY_POST_EVENT | Effective emergency admission with its declared follow-up obligation | An executor-selected escape from ordinary chronology |

An explicitly late reconstruction remains useful evidence but cannot satisfy
ordinary chronology compliance. No receipt proves private editor-keystroke order
or discovers an undisclosed private edit. The claim is restricted to authenticated
pre-change observation acquired before compliant preparation/publication.

### 2. Bind evidence, result and its real acquisition

The receipt binds Work Item, Decision and admission identities; policy identity;
exact parent commit/tree; evidence mode; exact evidence delta/tree and permitted
paths; command/oracle identity; observed structured result and non-vacuity
signals; and producer/execution/retention identities. Subsequent preparation
binds the exact receipt and retained evidence bytes, plus the compatible semantic
scope. Replacing the test, parent, policy or admission invalidates that relation.

A matching digest proves integrity, not producer authentication. Neither a caller
supplied hash, `trusted` boolean, issuer label nor timestamp is a trust root.
The semantic verifier consumes an observation obtained by the trusted acquisition
boundary; arbitrary JSON deserialization must not produce such an observation.

### Provider-neutral implementation boundary

VF0 follows the existing [Decision 0016](0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md)
portable-state/effect separation and [Decision 0086](0086-implement-useful-l1-as-protected-source-github-current-state-reconciler.md)
common-reducer/adapter pattern. GitHub is the first concrete acquisition adapter,
not the domain model. These are requirements for the eventual implementation,
not a new public schema, an implemented API or a production-admission claim.

Keep a deterministic, network-free semantic core over provider-neutral concepts:

| Concept | Common responsibility |
| --- | --- |
| Admission request | Exact subject/parent, Work Item/Decision/policy revisions, classified scope/mode, evidence plan, requested effect, identity and expiry |
| Admission observation | Observed disposition and principal, exact approved request, raw record/revision references, provenance, coverage and freshness; not inferred human presence |
| Execution/evidence reference | Provider and instance namespace, opaque repository/run/attempt/artifact identities, exact source/material digests and observed execution result |
| Human action link | Display label, relation and safe UI URL bound to the referenced subject; navigation only, never approval authority |

Separate read-only admission acquisition, evidence acquisition and action-link
resolution behind narrow interfaces. The composition boundary selects an
explicitly admitted adapter; the core must not inspect native URL paths, parse
GitHub approval comments, assume integer IDs, import provider SDKs or branch on
GitHub/GitLab workflow fields. Preserve opaque IDs with provider-instance and
repository scope; their magnitude or lexical order is not chronology. A missing
attempt identity must not be fabricated as attempt 1.

The adapter owns authenticated transport, native APIs and pagination, source
and protection metadata, native-event parsing, artifact retrieval and UI routes.
GitHub Environments, required-reviewer settings, numeric IDs, workflow YAML,
permission names and the A6 comment format stay in its specialization. Raw
provider records remain retrievable evidence; normalization must not discard
unavailable fields, ambiguous identity, provenance limitations or weaker
protection. A caller-created observation or `trusted` flag cannot satisfy the
admitted acquisition boundary merely because it has the common shape.

Declare the adapter's supported guarantees and their observed evidence: exact
request binding, record coverage, attempt identity/currentness, source and
protection revalidation, retention and approval/execution credential separation.
The common policy decides which guarantees are required. Unsupported, unknown
or contradictory required guarantees deny compliance rather than selecting a
weaker common denominator. Report human authorship, native publisher identity
and authority independently. An API `approved` state is not by itself evidence
of a non-delegated human credential.

The [A6 read-back](https://github.com/ktogias/gnostoa/pull/319#issuecomment-5821298046)
observed a real request-bound native approval and successful diagnostic job.
It does not establish full credential separation or independently revalidated
post-approval protections. Its single-attempt pilot and no-production scope
remain adapter-specific experimental constraints, not universal workflow rules.
Do not promote its GitHub-shaped diagnostic manifest into the common contract.

Acceptance requires conformance evidence for a network-free
core; two distinct synthetic provider mappings producing equivalent common
outcomes; opaque/colliding native identities; missing/ambiguous coverage or
capabilities; and unchanged authority under link changes. Reject an action-link
mapping bound to the wrong subject without changing an otherwise valid approval's
disposition. A missing UI link alone must not turn an otherwise valid approval
into an authorization denial. Synthetic mappings demonstrate
contract isolation, not live support for a second provider. These tests are
**NOT RUN** in this records-only clarification and do not replace any original
VF0 behavior-map obligation. Human handoffs follow the delivery runbook's
[direct-action-link convention](../runbooks/deliver-bounded-self-hosted-slice.md#human-action-handoff).

### 3. Prove a bounded provider-backed acquisition route first

The proposed first production acquisition route is a prior-integrated,
explicitly pinned evidence runner and independent provider read-back. The
provider adapter must reacquire repository, workflow source/revision, run/attempt,
job outcomes, artifact identity and archive digest from the authenticated provider
origin. It must check them against parent-owned trust configuration, not values
asserted inside the artifact. Hash the complete downloaded archive and compare
its SHA-256 with the independently reacquired provider digest before opening or
parsing the archive, extracting members or executing any supplied content. A
missing, malformed or mismatched digest rejects the archive; successful download
alone is insufficient. A successful unrelated or support-branch workflow
is not an admitted producer. The entrance helper is experimental evidence only.

The runner evaluates an exact parent plus an admitted evidence-only delta. It
must reject production-byte changes, undeclared paths and altered authority
before execution. Evidence code runs outside the controller's writable metadata,
output/receipt store and credentials. The controller, not the test process,
records the observed exit and bounded outputs. Isolation must be demonstrated
against the declared threat model; read-only remote permissions alone are not
an OS sandbox. Interpreter/runtime identities and relevant execution limits
belong to the bound execution, not to an unverified caller declaration.

For the first GitHub adapter, require HTTPS with certificate and hostname
validation for every metadata and artifact request, including signed downloads
that carry no API credential. Authenticate credential-bearing requests only to
the admitted API origin. A signed asset URL may be followed only through the
bounded provider-authorized handoff; do not forward the API credential to its
asset host or relax TLS validation. Validate exact workflow source and
repository/run relationships, pin the admitted integrated producer revision,
reject arbitrary URLs/redirected credentials, and treat missing, ambiguous or
expired artifacts as unavailable evidence. Use provider identity as the acquisition mechanism;
do not introduce a signing service or a caller-owned signing key merely to make
an envelope look authenticated. Offline downloaded files alone remain diagnostic.
The core receipt/policy/candidate relation remains provider-neutral.

The independent check-only CI consumer must repeat the admitted acquisition and
candidate/evidence binding. It does not trust an agent's retained local digest
or a prior green status. It grants neither human admission nor merge authority.
Provider evidence retention/availability becomes an explicit operational cost;
no offline or expired-artifact acceptance is implied by this proposal.

#### Parent-owned trust and admission inputs

The proposed trust configuration is a closed, versioned part of the immutable
parent-owned authority, loaded before candidate execution. It binds the admitted
API origin, adapter/provider-instance identity and opaque repository identity
(numeric in the GitHub adapter); prior-integrated producer revision, workflow
path and relevant source/dependency closure; permitted event and caller
identities; publisher job role and publication-record protocol; runtime pins;
and bounded acquisition, member and retention requirements. An exact source pin
must be accompanied by its admitted integration identity. Neither a branch name
nor successful execution proves that integration or admission. Changing these
inputs is authority evolution, not an ordinary candidate-supplied configuration.

Work Item, Decision, class, scope and evidence-mode admission come from the
applicable authority contract through separately authenticated, exact records.
Bind their raw identities and effective policy revision, admitted evidence-only
paths, oracle/non-vacuity obligations and chronology disposition. A producer
checks this admission; it cannot create it or choose a weaker class or mode.
An authenticated comment author is not automatically an independently dispositive
human event: the applicable contract must identify the actor, record, revision
and effect. Missing, changed, ambiguous or ineffective required admission denies
compliance. This proposal does not implement that event-acquisition contract or
attribute human approval to the executor's diagnostic records.

#### Attempt identity remains a separate proof obligation

The [VF0-E3 result](../assessments/15-vf0-entrance-and-execution-plan.md#vf0-e3-attempt-attribution-and-a-rejected-timestamp-hypothesis)
rejects the proposed strict upload-step timestamp relation for both genuine
attempts. Artifact metadata associates a run, not an attempt. A filename,
payload attempt, timestamp window or matching caller digest cannot close that
gap. Do not widen an interval after observing this failure or replace provenance
with timestamp coincidence.

The next proposed experiment uses a closed publication record from a pinned,
admitted publisher-only execution context. It must bind repository, run,
attempt and publisher job identity to the artifact ID and complete archive
digest, as well as the admitted input and observation identities. Resolve the
publisher job through the exact-attempt provider endpoint and pinned source;
reacquire its bounded publication record independently of the artifact payload,
then compare it with provider artifact metadata and the downloaded bytes.
The artifact name may be runtime-derived as an additional consistency check,
never as the trust root.

Candidate/test execution must not write, interleave with or spoof that publisher
channel. Arbitrary test logs and uploader-looking text are inadmissible; the E3
manual transcription is diagnostic only. The exact closed protocol, trusted
emission and parser boundaries, source closure and adversarial conformance remain
to be established before this route can produce an authenticated observation.
No production log parser is selected merely because the fixed diagnostic logs
contained matching values.

The first proposed production route accepts only the explicitly requested,
current latest run attempt, after its required jobs completed successfully with
complete coverage. An in-progress newer attempt does not permit reuse of an
older completed one. Re-read the run,
attempt, publisher and artifact identities after acquisition. Any newer attempt,
changed identity, missing/duplicate/conflicting publication record, incomplete
coverage or unavailable/expired material denies the current acquisition; never
fall back silently to an older artifact. Historical replay remains separate from
current compliance. The independent CI consumer must enforce the same identity
and admission relation, not trust the preparer's snapshot.

### 4. Keep bootstrap and activation explicit

Current Decision 0090 deliberately rejects changes to its own authority. VF0's
introducing candidate must therefore use a separately declared authority-evolution
path, not its modified wrapper to attest itself. Preserve the current entrance
RED and verify the new mechanisms before activation. The first trusted producer
cannot attest itself as already integrated while still a mutable candidate.

After an authorized bootstrap integration, prove a real producer/consumer round
trip and its negative controls on that actual subject before declaring VF0 active
or advancing #318. Failure leaves VF0 incomplete, not a successful documentation
substitute. Existing v1 preparation receipts remain historical D0090 evidence;
they are not silently upgraded to verification-first receipts.

## Alternatives, reuse and license boundary

Research date: 2026-09-24. Reuse Decision 0090's exact-parent wrapper, Git object
identity, strict bounded execution and retention patterns under this repository's
Apache-2.0 and NOTICE terms. The [execution plan](../assessments/15-vf0-entrance-and-execution-plan.md)
retains the local observations and proof obligations.

[pre-commit](https://pre-commit.com/#temporarily-disabling-hooks) supplies useful
local feedback, but documented hook bypass does not close API/non-hook authoring.
A native externally retained digest alone leaves the same provenance gap.
[in-toto's stable specification](https://in-toto.io/docs/specs/) informs explicit
step/material/product and functionary separation; its [Python license](https://github.com/in-toto/in-toto/blob/develop/LICENSE)
is Apache-2.0. It does not define Gnostoa's evidence modes or admission semantics.
[SLSA v1.2 provenance](https://slsa.dev/spec/v1.2/build-provenance) informs the
separation of caller parameters from signer/builder trust, not RED sufficiency.

The [GitHub artifact API](https://docs.github.com/en/rest/actions/artifacts)
exposes run-associated artifact metadata and download operations. The
[Actions secure-use reference](https://docs.github.com/en/actions/reference/security/secure-use)
informs separation of untrusted execution from credentials and protected state.
These are reference-only uses: no third-party code/schema is copied and no new
package, key service or policy engine is acquired. External metadata capability
is not proof that the proposed Gnostoa acquisition route already works.

The attempt-binding follow-up also inspected the
[pinned uploader's declared outputs](https://github.com/actions/upload-artifact/blob/ea165f8d65b6e75b540449e92b4886f43607fa02/action.yml)
and actual exact-job provider logs. This is reference/service reuse, with no
third-party implementation or schema copied. Human-oriented log wording has a
maintenance and spoofing cost; the diagnostic consistency result does not admit
an arbitrary-log parser or remove the closed-publisher proof obligation.

## Consequences

Acceptance requires every row of the
[initial behavior map](../assessments/15-vf0-entrance-and-execution-plan.md#initial-behavior-map-before-production-mutation)
to have aligned executed support, an actual authenticated producer/consumer round
trip, rejection of self-consistent but untrusted receipts, ordinary parent-bound
preparation parity,
critical-scope semantic review and exact integrated-subject reconciliation.

All ten initial rows describe executable gate behavior, including the handling
of a `STRUCTURAL`-mode receipt; none is exempt from executed support. A
non-executable source criterion carried by that mode is a different object: it
requires the mode table's accountable review, not a ceremonial executable test.
That review does not count as executed gate evidence or replace the mode-policy
and preparation-parity tests in VF0-05 and VF0-09.

Semantic adequacy of a test/oracle and legitimacy of human admission are not
proved by cryptographic hashes or a process exit code. Preserve accountable human
review and explicitly declared oracle limits. No protection against a hostile
provider administrator or container-runtime/kernel compromise is asserted.

Rollback withdraws the VF0 compliance/activation claim and blocks dependent
advancement; it cannot silently restore v1-only preparation while advertising an
enforced verification-first gate. No #318 or Q0 activation is authorized here.
