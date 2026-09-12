---
type: Source
title: D11-R2A advisory semantic review assurance implementation result
description: Exact-subject implementation, verification, review-convergence and real-provider dogfood result for the bounded D11-R2A P1 advisory review-assurance gate.
status: draft
generated:
  by: openai/gpt-5.6-sol
  at: "2026-09-12T12:26:00Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/11
    title: Semantic capture reconciliation and rationale completeness
  - id: pull-request
    resource: https://github.com/ktogias/gnostoa/pull/240
    title: D11-R2A implementation candidate
  - id: decision
    resource: ../decisions/0067-evaluate-semantic-review-assurance-through-bound-evidence.md
    title: Decision 0067
  - id: red-contract
    resource: 11-review-assurance-red-contract.md
    title: D11-R2A review-assurance RED-first execution contract
  - id: converged-review
    resource: https://github.com/ktogias/gnostoa/pull/240#issuecomment-5645773763
    title: CodeRabbit exact-head implementation convergence confirmation
x-project-knowledge:
  id: kit.assessment.11-review-assurance-implementation-result
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0067-evaluate-semantic-review-assurance-through-bound-evidence.md
    - kind: verifies
      target: /requirements/verification-precedes-implementation.md
    - kind: derived-from
      target: /assessments/11-review-assurance-red-contract.md
    - kind: references
      target: /decisions/0061-retain-individual-agent-review-dispositions.md
---

# D11-R2A advisory semantic review assurance implementation result

## Result

The bounded `GNOSTOA/D11-R2A/P1` slice now implements the Decision 0067 advisory semantic-review assurance gate over retained file evidence. The production implementation converged at exact commit
`f08b3e00e52c73333cdf356fb45374fb4e2ebbbe`, tree
`ccc4b1be4acfffd9fdb0060fb8a67a8d523fcdc1`.

The later exact evidence/dogfood head
`42df107ebbd609fc3816d3e00d606511fdcd396c` adds only retained PR #239 provider evidence and dogfood tests. It does not change the production evaluator, schemas or review policy after implementation convergence. These identities are intentionally kept separate from the immutable pre-production RED subject.

This result is mechanical and review evidence for accountable-owner semantic review. It is not owner acceptance, a merge authorization, a provider-required check, or evidence that Gnostoa already possesses a protected prior-integrated R2A authority acquisition path.

## Immutable RED-to-GREEN chronology

The authoritative pre-production RED receipt remains commit
`97244d233e8c798c23a408ffe40f5eb96f252b40`. At that commit:

- `python tests/test_review_assurance.py` exited `1`;
- stdout was exactly 698 bytes with SHA-256
  `6584f3cde2f6916f90e39e825b768fbdbecb51958f734e5358bf9c6896207e9b`;
- stderr was zero bytes;
- every pre-registered case R01-R45 failed because production review-assurance paths were absent; and
- the retained RED harness/cases/expected/output blobs were sealed by the receipt recorded in the RED contract.

Those four RED artifacts were not rewritten to obtain GREEN. The production implementation was added afterwards, and the same `python tests/test_review_assurance.py` oracle now reports:

```json
{"failing_case_ids":[],"phase":"GREEN","production_paths_absent":false,"required_case_ids":["R01","R02","R03","R04","R05","R06","R07","R08","R09","R10","R11","R12","R13","R14","R15","R16","R17","R18","R19","R20","R21","R22","R23","R24","R25","R26","R27","R28","R29","R30","R31","R32","R33","R34","R35","R36","R37","R38","R39","R40","R41","R42","R43","R44","R45"],"schema":"gnostoa-review-assurance-red/v1","unexpected_case_ids":[]}
```

The chronology therefore preserves the literal verification-first claim: the executable oracle and its expectations predate the production implementation that satisfies them.

## Implemented surface

P1 adds the deliberately small surface selected by Decision 0067:

```text
schemas/review-check-input.schema.json
schemas/review-policy.schema.json
schemas/review-gate-result.schema.json
core/review-policy.yaml
policy/review-policy.yaml
tools/review_model.py
tools/review_policy.py
tools/review_evaluate.py
tools/review_adapter_file.py
tools/review_check.py
knowledge review-check
```

The three public schemas keep the external contract small while internal Python modules remain flat and separately testable. `core/review-policy.yaml` is abstract/non-evaluatable; the Gnostoa-self project policy explicitly specializes change classes. The evaluator consumes existing change class rather than becoming a second change classifier.

The file adapter derives normalized recommendation and normalization provenance from retained native state. Caller-supplied normalized values, adapter identity, rule identity, raw-state digest or admission claims do not become authority. Qualification/domain/capability facts remain externally supplied bounded snapshots under Issue #10 semantics; R2A does not create a reviewer registry or infer independent domains from provider/model labels.

## Bootstrap trust boundary

Implementation review found that a merely deterministic file evaluator was not enough to support the stronger current-advisory anti-self-weakening claim. The initial CLI accepted a caller-selected `--policy`; a caller could pair a weaker schema-valid policy with caller-authored matching authority/qualification/judge claims. A first repair constrained the CLI, but direct `evaluate_documents()` still bypassed that restriction.

The final P1 boundary is therefore intentionally stricter and fail-closed:

- every well-formed `current_advisory` evaluation in the first/bootstrap implementation returns semantic `INCOMPLETE`;
- the reason is `BOOTSTRAP_PROTECTED_AUTHORITY_UNAVAILABLE`;
- every semantic result remains `binding:false`;
- neither caller-selected policy paths nor matching caller-authored authority/judge facts can manufacture current-advisory PASS; and
- `historical_replay` remains the explicit file/fixture route for deterministic replay and synthetic prior-integrated semantics.

This is a bounded P1 specialization, not a claim that current-advisory PASS is permanently impossible. A later separately admitted change may enable it only after a protected prior-integrated authority acquisition path exists and is itself verified.

## Result and error fidelity

The implementation validates all three layers rather than trusting producer intent:

1. review-check input is validated against the input schema;
2. the selected effective policy is validated against the policy schema and semantic policy constraints; and
3. the evaluator's emitted semantic result is validated against `review-gate-result.schema.json` before its outcome is mapped to an exit code.

Malformed installed JSON Schemas are checked with Draft 2020-12 schema validation. Invalid installed schemas, policy-loading/inheritance failures and other configuration faults use the canonical error envelope and exit `2`; a malformed evaluator result becomes `TOOL_ERROR`, not a semantic PASS. Semantic exits remain exactly PASS=0, BLOCKED=1, error=2, INCOMPLETE=3 and CONFLICTING=4.

## Exact-head implementation verification

The converged production-code subject `f08b3e00e52c73333cdf356fb45374fb4e2ebbbe` was verified by GitHub Actions run `34692238908` on that exact head. Required jobs all succeeded:

- `policy`;
- `fast`, including the unchanged R01-R45 GREEN harness;
- Python 3.11 source compatibility;
- Python 3.12 including canonical Ruff formatting and strict mypy over the review trust domain;
- `regression`; and
- `smoke`, including exact executable-candidate binding.

The smoke lane ran 707 tests with three expected skips. It verified source/runtime/vendored public-surface equality at
`sha256:5607a4acbece4286e9ba5a720f07d9a12f9dcc6df6f7fff70dc10a7c0a603b79` and the explicit SB2 candidate extension from the historical 14-member set to 19 members by adding exactly the five review-assurance modules.

`extended` was skipped by workflow and is not counted as PASS.

## Exact-head implementation review reconciliation

CodeRabbit review evidence is retained as one reviewer family, never as proof of multiple independent review domains.

The important exact-head review sequence was:

- comment `5645676190`: MATERIAL finding that caller-selected `--policy` plus caller-authored authority could self-authorize current-advisory PASS; MINOR finding that invalid installed JSON Schema could escape the canonical error envelope;
- comment `5645705012`: after the CLI repair, MATERIAL finding that direct `evaluate_documents()` still preserved the same self-authorization path;
- comment `5645724030`: after moving the restriction into the shared evaluator boundary, zero BLOCKING and zero MATERIAL findings; its `IMPLEMENTATION_REVISION_REQUIRED` disposition was only because required CI was still incomplete at inspection time; and
- comment `5645773763`: on unchanged exact head `f08b3e00...`, after run `34692238908` completed successfully, zero BLOCKING/MATERIAL findings and explicit `IMPLEMENTATION_CONVERGED`.

These reviews improved the implementation but do not constitute human acceptance or an Issue #10-established independent review domain.

## Real-provider dogfood

P1 also dogfoods the implemented semantics against attributable pre-R2A GitHub review records from merged PR #239 rather than only synthetic fixtures.

The dogfood subject is real:

- repository: `ktogias/gnostoa`;
- pull request: `239`;
- final head: `1fa8eb9ff1ae0604663f2611cd67fdedb97d88c9`;
- merge-base: `a0b7c8a170942fce61ff3c08b350bc3d7ab0a2a0`.

The retained native review objects are:

- Qodo GitHub review `5182705577`, state `COMMENTED`, bound to commit
  `1337c82e28256f265b4c28b1fe41980e2cf7e832`; and
- Sourcery GitHub review `5182778419`, state `APPROVED`, bound to commit
  `204695d0647a0601f4fbae340e2fc86234dedfb3`.

Both reviews are genuine older-head evidence relative to PR #239's final head. That makes them useful adversarial dogfood: the adapter must preserve attribution and normalize native state, while the evaluator must not silently reinterpret them as final-head quorum.

Exact evidence head `42df107ebbd609fc3816d3e00d606511fdcd396c` passed workflow run `34692998501`. The fast suite ran 710 tests with two expected skips and explicitly passed all three dogfood discriminators:

- real native reviews normalize without invented authority;
- older-head reviews stay visible but do not count for the final-head subject; and
- current-advisory dogfood remains bootstrap `INCOMPLETE`.

The unchanged R01-R45 oracle also remained fully GREEN on this evidence head. No synthetic independence domain or fabricated historical trusted R2A judge was assigned to these provider records.

## Mutation and permutation evidence

P1 does not claim a generic mutation-testing percentage. The pre-registered R01-R45 matrix is instead deliberately discriminating: many cases change one authority, freshness, collection, subject, qualification, normalization or judge fact at a time, while R31 exercises ordering/duplicate-placement invariance. All pre-registered cases are GREEN without changing their expectations.

This is evidence that the evaluator distinguishes the selected failure modes; it is not evidence that every possible semantic mutation has been exhaustively tested.

## Boundary retained

The implemented P1 remains advisory and file-evidence-bound. It does **not** add:

- a live provider collector;
- reviewer trigger/wait/orchestration;
- Issue #10 reviewer registry/discovery;
- provider mutation or auto-resolution;
- human semantic acceptance;
- merge/release authority;
- a required provider merge check;
- a generic policy language; or
- a trusted native current-advisory judge/acquisition path.

A later enforcing consumer requires its own admitted design for protected acquisition, outage/bypass/recovery semantics and provider projection. The present result does not pre-authorize that work.

## Disposition

D11-R2A P1 is mechanically and implementation-review converged and is ready for **accountable-owner semantic review of the exact final PR #240 candidate** after the evidence-only finalization commit itself passes CI/review. Merge authorization remains separate.
