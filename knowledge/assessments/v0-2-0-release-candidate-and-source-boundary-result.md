---
type: Source
title: v0.2.0 release-candidate and source-boundary result
description: Candidate-bound Phase-1 result for the v0.2.0 version transition, affected first-party assurance replay and 14-member executable source boundary.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-27T10:08:00Z"
sources:
  - id: v0-2-0-release-work-item
    resource: https://github.com/ktogias/gnostoa/issues/146
    title: Publish Gnostoa v0.2.0 source and OCI release series
  - id: v0-2-0-release-decision
    resource: ../decisions/0051-select-the-v0-2-0-source-and-oci-publication-series.md
    title: Select the v0.2.0 source and OCI publication series
x-project-knowledge:
  id: kit.assessment.v0-2-0-release-candidate-and-source-boundary-result
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0051-select-the-v0-2-0-source-and-oci-publication-series.md
    - kind: references
      target: /assessments/first-party-source-security-falsification-and-profile-read-result.md
    - kind: references
      target: /assessments/v0-1-2-source-and-oci-publication-result.md
---

# v0.2.0 release-candidate and source-boundary result

## Scope and subject

This Phase-1 record covers only the proposed `v0.2.0` source candidate and the
affected first-party executable boundary required before source publication.
It begins from protected `main`
`6714d70772f021bd3e174510f16bcfc5230f168b`, tree
`42d0f1dd323c6ae99c9bbe01f54b346f937ab7a2`. The installed-artifact repair
starts from Pull Request head
`f06f5004fbc7a4672513ce9813d1fe03113598bf`, tree
`ed9588132dcea1b6c16af1384bbec97625098926`. Its final repaired head, integrated
commit, annotated tag and OCI digest must be recorded through provider read-back
rather than predicted here.

## Verification-first result

Two focused criteria were established before implementation:

1. the candidate package/runtime version must be `0.2.0`; and
2. exact candidate binding must include the two first-party modules introduced
   by the public adoption command and report a 14-member boundary.

Against the starting subject the tests failed for exactly those reasons: the
version remained `0.1.2`, both modules were absent from the bound manifest and
the workflow still required 12 members. After the bounded change, both focused
tests pass.

The first clean installed-artifact exercise then exposed a release-harness
regression: its isolated working directory was being used as the implicit
project root while its bounded fixtures remained under the source candidate.
The repair keeps execution isolated and supplies the source candidate as the
explicit project root. A focused regression test now binds this behavior, and
fresh wheel and source-distribution exercises return identical declared
results.

A later clean-wheel falsification found that the old release smoke was
insufficient: it passed while the installed `adoption-check` exited `2` before
retaining evidence because the execution-only wheel did not contain the
canonical result schema. Focused RED cases also established that the candidate
runtime label defaulted to `development`, explicit version drift was not
rejected and the public status still described candidate selection as pending.

The bounded repair preserves the execution-only wheel contract. An installed
runtime now acquires the schema from the exact pinned public source and must
prove bounded, complete byte equality between its installed `tools` payload and
that source before it can claim execution-subject coherence. Exact-candidate
runtime builds derive `0.2.0` from package metadata, reject a conflicting
explicit label and expose both CLI and OCI-label checks in provider evidence.
The release smoke now executes a real adoption check from clean wheel and source
distribution environments; both must retain a schema-valid READY result without
mutating the fixture project. Documentation now records Nextcloud Mail as the
selected B3 target, preserves the rejected attempts as controlled pre-B3
evidence, acknowledges that operational B3 work has begun and distinguishes it
from the new `v0.2.0` exact-subject rerun, which has not begun.

The native fallback was used because this execution environment exposes no OCI
engine. With the exact committed development lock, the Phase-1 candidate
currently reports:

- policy, CI-policy, guardrail and both knowledge-bundle checks: PASS;
- focused installed-artifact, version-binding and chronology repair criteria:
  10/10 PASS;
- adoption assurance/check portfolio: 68/68 PASS;
- complete Python portfolio: 252/252 PASS;
- clean wheel and source-distribution adoption checks: PASS with identical
  declared results;
- regression and smoke portfolios: PASS; and
- extended quality portfolio: PASS, including formatting, lint, configured
  static typing, strict documentation, dependency and secret checks, and
  75.23% branch-aware coverage against a 65% floor.

Container source/runtime/vendored equality, provider jobs and CodeQL remain
required exact-head evidence and are not inferred from these local results.

## Re-derived executable boundary

The unified CLI directly exposes `adoption-check`; that route uses
`tools/adoption_check.py` and `tools/adoption_assurance.py` in addition to the
previous 12-member boundary. The proposed complete candidate set is:

| Path | Candidate SHA-256 |
| --- | --- |
| `tools/adoption_assurance.py` | `e5eb50cc43ba3f212e4543d09df584cef2680a363cd5f872bcf36f42a414a79b` |
| `tools/adoption_check.py` | `bf55db5d4d998b23cb7ab6ee336c89a9f9ef9d31978c268bcbb7f42420feff78` |
| `tools/build_context_pack.py` | `54339d70f04824605a8e7bee0fb8bce02906523109e1c012a20eb312b9cac1cb` |
| `tools/build_docs.py` | `e22de87395da6ff5e32428ed9b8cfc123a3512136aeb12f939868fa68f049676` |
| `tools/check_change_policy.py` | `6659c3680ad5ec0ca325f9a4b41fda7ef71b8c8f31ea584624c0c53f5587e156` |
| `tools/check_ci_policy.py` | `9c0ba59484a81e6f9aa00296557e7b66ec698c1e6d44d9df8047563f4882484c` |
| `tools/check_guardrails.py` | `dd4839c528451421fa5757468fd4bbc7c9ea475325d22b9e630d884d0fce7ab9` |
| `tools/check_runtime_lock.py` | `15cc878aea0a1eda46af40e443f2d87f6123d8def1eb7d22cb1b05649b308c8a` |
| `tools/cli.py` | `8d698a1acccbf9a3622f20954e35e6377217030f387beea058b46c7e4a26fef1` |
| `tools/knowledge_common.py` | `fbbcc38fb82aa572cd92c683ad983fda7398761a9c08b94cbce5d0080d6eb5ed` |
| `tools/repository_scope.py` | `a61fc494a84cad5cad6923f072dc05fd2edb41162cf45c7446eb05303d73e5c4` |
| `tools/self_check.py` | `c0f7c63107c941b5bbfc89d4399c5a197f9c0939c06e5b8012c3aeeaa9b54824` |
| `tools/task_envelope.py` | `da5644815c1ed19d79f320c3c2758a4877f105d440d0a0206650ec8f92f06204` |
| `tools/validate_bundle.py` | `7d728446c8a34e7515c626b1c3b8af6cfafee38318616a44a86303af3beb5ca1` |

The candidate public-surface digest measured from the working source is
`sha256:a85ac8dde00f1ed8fb0425de08597828e97c246ec17ce6556f3f222b27ddb1c1`.
It must be remeasured from the exact committed and provider-checked candidate.

## Affected assurance replay

The replay covered the complete 14-member set and the 68 focused adoption
tests. The added route retains the already reviewed local Git/process,
subject-binding and evidence-publication contracts. The bounded static inventory
found no newly supported network, credential, archive-extraction or privilege
effect. Expected local process and platform interfaces remain subject to their
focused failure-path tests and later CodeQL/provider verification.

This is a bounded falsification result, not a declaration that the source is
secure, complete or independently attested. Base/runtime freshness, dependency
observations and immutable artifact verification remain separate release gates.

## Disposition and remaining gates

The Phase-1 candidate has completed its local verification portfolio. It is not
yet accepted, integrated, tagged or published. Before the source effect:

- exact-head local and provider verification must complete;
- the 14-member source/runtime/vendored manifests must be byte-equal;
- affected CodeQL and release freshness must be read back;
- the accountable owner must accept the exact candidate and effect envelope.

OCI workflow binding, registry publication, digest verification, provenance,
public projection and B3 subject freeze remain later phases of Work Item #146.
