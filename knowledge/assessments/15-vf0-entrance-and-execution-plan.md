---
type: Source
title: VF0 entrance evidence and bounded execution plan
description: Exact-main missing-pre-evidence reproduction, evolving component evidence and unexecuted proof obligations for the proposed VF0 assurance gate.
status: draft
generated:
  by: agent:chatgpt
  at: "2026-09-27T15:46:50Z"
sources:
  - id: owner-scope
    resource: https://github.com/ktogias/gnostoa/issues/15#issuecomment-5803831361
    title: VF0 scope and sequencing
  - id: entrance-checkpoint
    resource: https://github.com/ktogias/gnostoa/issues/15#issuecomment-5816376488
    title: Pre-execution exact-main entrance contract
  - id: entrance-result
    resource: https://github.com/ktogias/gnostoa/issues/15#issuecomment-5816520445
    title: Verified VF0-E1 result and artifact identities
  - id: actual-run
    resource: https://github.com/ktogias/gnostoa/actions/runs/36015395550
    title: Actual parent-owned preparation entrance execution
x-project-knowledge:
  id: kit.assessment.15-vf0-entrance-and-execution-plan
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /decisions/0092-bind-verification-first-evidence-to-parent-owned-preparation.md
    - kind: references
      target: /requirements/bounded-behavioral-traceability.md
---

# VF0 entrance evidence and bounded execution plan

**VF0's enforcement gate is not implemented or active.** Private relation and
execution components (`tools/vf0_contract.py`, `tools/vf0_execution.py`, and
`tests/vf0_execution_oci_smoke.py`) are prospective S2a/S2b targets and do not
yet exist on `main`. This is the initial record for the existing Issue #15 child,
not a new Work Item, public contract or reduced-risk replacement.
The proposed [Decision 0092](../decisions/0092-bind-verification-first-evidence-to-parent-owned-preparation.md)
is separate from the observed experiment below.

## Exact observation

Subject: integrated #315 main `63fb3e7bf7a929c755250e6112f5a43a2b3db5c7`,
tree `fa4cb2db0ea072897391efd77deda95ac7e1f9a4`.
The evidence harness was committed separately at
`a7edb7bf3a44411b9a4097998a5b7224bcf08282`, path
`.github/vf0-entrance-reproduce.py`; it never entered main.

In an isolated throwaway clone, the exact parent-owned wrapper prepared a
synthetic new Python module without any prior-evidence receipt or provenance.
Its existing verifier accepted the resulting D0090 receipt. The new assertion
requiring rejection failed with `VF0_MISSING_PRE_EVIDENCE_WAS_ACCEPTED`.

| Observation | Actual result |
| --- | --- |
| Desired missing-pre-evidence rejection | RED: 1 assertion failure, 0 errors, 0 skips |
| Parent-tracked production and the four authority files tracked in that `63fb3e7b` run | Unchanged |
| Prepared delta | Only `tools/vf0_missing_evidence_probe.py` |
| Existing style/focused/diff checks | All four returned zero |
| Existing D0090 receipt verification | PASS |
| Empty candidate and stale-parent controls | Both correctly rejected |
| Preparation, style, focused check or verifier mocks | None |

The test module is synthetic input to the existing gate, not VF0 implementation
or a reproduction of #314's original analyzer defect. This result establishes a
missing new invariant, not a failure of D0090's existing normalization contract.
The capture workflow's success means it correctly retained the failing assertion;
it does not mean the proposed gate passed.

## Retention and reproduction

Artifact **10814840263**, `vf0-exact-main-entrance-20260924`, from the linked run,
expired **2026-10-01 14:48:40 UTC** and is no longer retained by the provider.
Its downloaded ZIP, canonical result and script identities were independently
checked locally before expiry:

| Object | SHA-256 |
| --- | --- |
| Artifact archive | `6cbeef0eedf53e2af27668bcd0122dbd6f2b8ec96b68e088ce230edeac1f82de` |
| `evidence/result.json` | `e909e8b3af1e2aed95d4eef7a964d9cddd7a31f0df528264d55e3cd4b132806e` |
| Predeclared reproducer | `f6bdd6c74a5cb9e098197831d1fa8541ae6f82b258d6a6b096b0da594d935337` |

The run also exported only the named main history. Empty-repository bundle
verification, fresh-clone full fsck and exact detached HEAD/tree/clean checks
passed on the producer and after local download. A nonexistent default branch
in the bundle caused a clone warning; explicit exact-commit checkout succeeded.
The artifact is experiment evidence, not an admitted production attestation.

Reproduce from the immutable script commit and exact subject above using the
retained workflow at `09957d875f7502b252fc047644c42b9c361d1550`. It builds the
repository development image, runs as a non-root UID without network or provider
credentials, and invokes real exact-parent preparation in a disposable clone.
After capture, both temporary support files were removed; support commit
`b65167703f4431f4bac96e6a2e7f0a4e1bda6a2f` has the original main tree.
History preserves the script even after artifact expiry. The scratch prepared
ref was released; no live candidate receipt is claimed from this experiment.

## Initial behavior map before production mutation

Task authority is the linked owner-selected VF0 scope. The mechanism paths below
are prospective; no new production implementation or independent reviewer result
exists at this checkpoint. The experiment is executor-authored evidence, not an
independent proof of test semantic sufficiency.

| ID | Required observable behavior | Proposed boundary / evidence | Execution and alignment | Executor / reviewer |
| --- | --- | --- | --- | --- |
| VF0-01 | Applicable semantic candidate without prior evidence is rejected | D0090 preparation; actual VF0-E1 entrance | RED; contradicts desired gate, supports gap diagnosis | Gap confirmed / PENDING |
| VF0-02 | RED uses unchanged parent production plus admitted evidence-only paths | Evidence producer; production-mutation and path-escape negatives | NOT RUN / UNKNOWN | PENDING / PENDING |
| VF0-03 | Matching hash or issuer label cannot authenticate a forged receipt | Trusted acquisition; unrelated run, wrong workflow, tampered archive and caller-hash negatives | NOT RUN / UNKNOWN | PENDING / PENDING |
| VF0-04 | Wrong parent/tree, policy, admission or retained test bytes rejects reuse | Parent-owned validator plus candidate relation | NOT RUN / UNKNOWN | PENDING / PENDING |
| VF0-05 | Modes obey effective class policy; late reconstruction cannot satisfy ordinary chronology | Mode matrix, forbidden downgrade and late-marker fixtures | NOT RUN / UNKNOWN | PENDING / PENDING |
| VF0-06 | Zero tests, skips, unrelated failures and timeouts cannot satisfy RED | Bound oracle and execution signals; non-vacuity negatives | NOT RUN / UNKNOWN | PENDING / PENDING |
| VF0-07 | Candidate cannot change the verifier or its trust inputs | Wrapper extraction and immutable authority membership | NOT RUN / UNKNOWN | PENDING / PENDING |
| VF0-08 | Independent CI reacquires provenance and checks the exact candidate | Real check-only provider consumer; end-to-end round trip | NOT RUN / UNKNOWN | PENDING / PENDING |
| VF0-09 | Valid evidence retains ordinary normalization and final verification | D0090 preparation/verification parity and valid mode fixtures | NOT RUN / UNKNOWN | PENDING / PENDING |
| VF0-10 | Bootstrap, artifact loss and rollback do not advertise false activation | Actual integrated-subject smoke and fail-closed availability tests | NOT RUN / UNKNOWN | PENDING / PENDING |

## Bounded execution plan

1. **Entrance complete:** retain actual VF0-E1, exact source and explicit limits.
2. **Decision/proof preparation:** reconcile the proposed acquisition boundary,
   trust configuration, admission inputs and version transition. Build a focused
   positive/negative provenance experiment before treating an acquired observation
   as trusted.
3. **Evidence producer and verifier:** specify closed bounded inputs, preserve
   production equality and declared oracle identities, execute in demonstrated
   isolation, then retain observations outside candidate control. Keep the provider
   adapter separate from semantic policy logic. Establish focused RED first.
4. **D0090 authority evolution and CI:** wire the same authenticated relation into
   preparation and an independent check-only consumer. Preserve the v1 historical
   boundary and explicitly handle the introducing candidate's bootstrap.
5. **Critical acceptance and activation:** reconcile every map row with actual
   candidate/evidence, collect task-to-code and map-reconciliation reviews, obtain
   the exact integration effect, and verify a real integrated producer/consumer
   round trip. Only then consider VF0 closure and advancement to Issue #318.

No independent stage may claim the overall gate is active. Artifact availability,
test/oracle adequacy, actual admission and isolation are material proof obligations,
not satisfied by a document, function name, receipt schema or green unit test.

## Architecture-Inheritance lineage table (base `a94b8346499691b82993eeb3fe3e8f82ace7a2bb`)

Per the delivery runbook, every material VF0 responsibility is disposed against
its existing owner on `main` (`a94b8346499691b82993eeb3fe3e8f82ace7a2bb`) before
implementation slices (`S2a`, `S2b`, and follow-ups):

| Responsibility | Existing owner | Existing implementation/contract | Disposition | Proof/falsifier |
| --- | --- | --- | --- | --- |
| Exact tree materialization and snapshotting | `tools/exact_tree.py` | Git-object tree capture and materialization into ephemeral gitless directories (`main` `a94b8346`) | `consume` | S2a/S2b tests verify `tools/exact_tree.py` is called rather than re-implemented |
| Bounded process pipe draining and direct-child reaping | `tools/bounded_process.py` | Pipe-drain and direct-child-reap helper (`main` `a94b8346`) | `consume` | S2b tests verify `tools/bounded_process.py` handles pipe-drain/reap without duplicating it |
| Trusted executable lookup | `tools/trusted_path.py` | Safe executable resolution outside repo worktree (`main` `a94b8346`) | `consume` | S2b tests verify `tools/trusted_path.py` resolves host/container executables |
| VF0 normalized relation contract | None (new VF0 contract; existing `candidate_prepare.py` only checks D0090 normalization) | None on `main` (`a94b8346`); existing `candidate_prepare.py` lacks provider-neutral evidence-relation evaluation | `new-residual` | S2a introduces `tools/vf0_contract.py` with unit tests proving relation parity and negative rejections |
| VF0 bounded observation execution | `tools/experiment/backend.py`, `tools/experiment/execution.py`, `tools/review_current.py`, `tools/review_outer.py`, `tools/bounded_process.py` | `tools/experiment/*` execute experiment profiles; `tools/review_current.py` and `tools/review_outer.py` run protected-judge Docker/OCI containers for advisory review consumers; `tools/bounded_process.py` only drains/reaps direct children. None provides VF0's read-only gitless delta verification + `ci/verify` observation contract (`main` `a94b8346`) | `new-residual` | S2b introduces `tools/vf0_execution.py` and `tests/vf0_execution_oci_smoke.py` proving OCI isolation |
| Pre-candidate preparation receipt gate | `tools/candidate_prepare.py` | D0090 exact-parent preparation and receipt verification (`main` `a94b8346`) | `extend` | Later slice extends D0090 preparation with VF0 evidence binding; existing D0090 tests remain green |

*Note: Deferred Decision 0092 responsibilities (provider-backed artifact acquisition, independent check-only CI consumer, and authority evolution/bootstrap) are out of scope for S2a/S2b and will be disposed in their respective follow-up slices. Archival experiment and audit logs (`VF0-E2`–`VF0-E5`, `VF0-A7/A8`, `AUD14`–`AUD49`) from the superseded monolithic branch are omitted from this bounded S1 entrance plan.*
