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

## Consequences

Acceptance requires every row of the
[initial behavior map](../assessments/15-vf0-entrance-and-execution-plan.md#initial-behavior-map-before-production-mutation)
to have aligned executed support, an actual authenticated producer/consumer round
trip, rejection of self-consistent but untrusted receipts, ordinary parent-bound
preparation parity,
critical-scope semantic review and exact integrated-subject reconciliation.

Semantic adequacy of a test/oracle and legitimacy of human admission are not
proved by cryptographic hashes or a process exit code. Preserve accountable human
review and explicitly declared oracle limits. No protection against a hostile
provider administrator or container-runtime/kernel compromise is asserted.

Rollback withdraws the VF0 compliance/activation claim and blocks dependent
advancement; it cannot silently restore v1-only preparation while advertising an
enforced verification-first gate. No #318 or Q0 activation is authorized here.
