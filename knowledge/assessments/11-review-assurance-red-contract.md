---
type: Source
title: D11-R2A review-assurance RED-first execution contract
description: Verification-first contract for the bounded provider-neutral advisory review-assurance gate selected by Decision 0067.
status: draft
generated:
  by: agent:gpt-5.6-sol
  at: "2026-09-11T23:42:51Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/11
    title: Semantic capture reconciliation and rationale completeness
  - id: decision
    resource: ../decisions/0067-evaluate-semantic-review-assurance-through-bound-evidence.md
    title: Decision 0067
  - id: owner-approval
    resource: https://github.com/ktogias/gnostoa/issues/11#issuecomment-5641780494
    title: Owner approval of R8 architecture and convergence-loop process
  - id: architecture-convergence
    resource: https://github.com/ktogias/gnostoa/issues/11#issuecomment-5641717198
    title: D11-R2A architecture convergence record
x-project-knowledge:
  id: kit.assessment.11-review-assurance-red-contract
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0067-evaluate-semantic-review-assurance-through-bound-evidence.md
    - kind: governed-by
      target: /requirements/verification-precedes-implementation.md
    - kind: references
      target: /decisions/0061-retain-individual-agent-review-dispositions.md
---

# D11-R2A review-assurance RED-first execution contract

## Identity and scope

The bounded task is `GNOSTOA/D11-R2A/P1` at exact base `9915357546e1665143b3a705533bb94812faee54`. It may add only the Decision/task/assessment records, three review-assurance schemas, abstract/core and Gnostoa-self policy, flat file/model/policy/evaluator/CLI modules, focused tests/fixtures and the minimum existing CLI/help routing needed for `knowledge review-check`.

It does not admit a live provider collector, reviewer orchestration, #10 registry, #15 workflow mechanics, provider mutation, merge enforcement, policy DSL, signing service or trusted native judge identity.

## Literal verification-first order

1. Converge the Decision, task envelope and this RED contract before production implementation.
2. Add the exact focused RED harness below while the production review-assurance schemas, policies and executable modules are still absent.
3. Run the exact RED command and retain its commit SHA, nonzero exit, bounded output SHA-256 and proof that the production paths remain absent.
4. Only after the RED receipt is complete may the task hand off to a production implementation agent.
5. Preserve the RED expectations unchanged through production implementation unless a later review explicitly changes Decision 0067 and records the reason.
6. Reach GREEN, then run mutation/permutation controls, complete suites, exact-candidate reviews and advisory dogfood.

The first R2A implementation is bootstrap. A current-advisory invocation whose judge relation is `candidate_under_test` is valid but assurance-incomplete and cannot PASS. Synthetic fixture-only historical replay may exercise normal policy/quorum/blocker/conflict and historical pinning semantics. Real retained pre-R2A review evidence is characterized separately as `candidate_under_test`; it is never assigned a fabricated historical trusted R2A judge.

## Pre-registered RED harness

Create only these focused pre-production test artifacts in the RED commit:

```text
tests/test_review_assurance.py
tests/fixtures/review_check/cases.json
tests/fixtures/review_check/expected.json
```

The test file uses the standard-library `unittest` runner and invokes the future public route as an external command where CLI behavior is under test; pure-contract cases may import the future modules only after they exist. The RED command is exactly:

```text
python tests/test_review_assurance.py
```

Before production review-assurance paths exist, the command must exit nonzero and must not SKIP/XFAIL the missing contract. The retained bounded output must identify failing R2A case IDs rather than treating absence as success.

### RED receipt — must be completed before production handoff

```text
red_commit: PENDING
command: python tests/test_review_assurance.py
exit_code: PENDING   # must be nonzero
bounded_output_sha256: PENDING
production_paths_absent:
  - schemas/review-check-input.schema.json
  - schemas/review-policy.schema.json
  - schemas/review-gate-result.schema.json
  - core/review-policy.yaml
  - policy/review-policy.yaml
  - tools/review_model.py
  - tools/review_policy.py
  - tools/review_evaluate.py
  - tools/review_adapter_file.py
  - tools/review_check.py
```

`PENDING` in any RED receipt field blocks production implementation handoff. The observed RED commit and output are evidence, not values to predict in this specification.

## Required RED matrix

### Policy and explicit no-review

| ID | Required behavior |
| --- | --- |
| R01 | Missing, unresolved or abstract policy plus zero observations cannot PASS. |
| R02 | Explicit `review_requirement:none` may PASS only with reason `POLICY_EXEMPT`. |
| R03 | Empty lists inside a required-review class do not silently become no-review. |
| R04 | A weakened policy copy in candidate paths cannot replace the selected prior-effective authority policy. |

### Subject and time cut

| ID | Required behavior |
| --- | --- |
| R05 | Same head with a different merge-base is a different/non-counting reviewed subject. |
| R06 | Older-head review remains visible but cannot satisfy current exact-head policy. |
| R07 | Partial or unestablished subject binding remains visible but cannot satisfy exact-subject policy. |
| R08 | Any used observation/collection/qualification cut later than `EvaluationContext.as_of` is configuration error. |
| R09 | With RFC3339 cuts interpreted as UTC instants, finite freshness is `0 <= utc(as_of)-utc(cut) <= max_age`; exceeding the finite limit produces `INCOMPLETE`, never PASS. |
| R10 | A synthetic fixture-only `historical_replay` pins exact fixture authority and judge identities and refuses silent current substitution, without claiming those fixture identities were real historical production authority. |

### Collection completeness

| ID | Required behavior |
| --- | --- |
| R11 | Omitted policy-required source produces unmet/`INCOMPLETE` evidence. |
| R12 | Required `PARTIAL`, `RATE_LIMITED`, `UNAVAILABLE` or `ERROR` source prevents PASS. |
| R13 | Silence, truncation, rate limit or unavailable retrieval never normalizes to no-findings. |
| R14 | Optional unavailable source remains visible but need not block when every actual requirement is independently satisfied. |
| R15 | Incomplete collection cannot manufacture absence, blocker resolution or quorum. |

### Qualification and quorum

| ID | Required behavior |
| --- | --- |
| R16 | Capability/domain claims inside `ReviewObservation` do not qualify the observation. |
| R17 | Wrong or unaccepted authority/qualification digest cannot satisfy quorum. |
| R18 | `unestablished`, `revoked` or freshness-expired qualification cannot count. |
| R19 | Multiple observations from one established opaque domain ID contribute one distinct domain. |
| R20 | Two separately established opaque domain IDs can satisfy a two-domain quorum. |
| R21 | Owner-authored review does not count when effective policy says false. |
| R22 | Evaluator emits no human owner acceptance or merge authorization. |

### Normalization, blockers and conflicts

| ID | Required behavior |
| --- | --- |
| R23 | Positive prose without an admitted native recommendation state normalizes to `UNKNOWN`, never inferred `APPROVE`. |
| R24 | Eligible current `REQUEST_CHANGES` yields `BLOCKED`. |
| R25 | A known blocker is not masked by another missing required source. |
| R26 | Anonymous, unrecognized or non-current evidence gets neither automatic veto nor quorum authority. |
| R27 | Unresolved thread blocks only according to policy; unknown thread state can remain incomplete. |
| R28 | Within one invocation and one selected valid policy whose `conflicts` section declares the applicable recommendation pair, two eligible conflicting review dispositions produce `CONFLICTING`, distinct from `INCOMPLETE`; policies themselves are never compared. |

### Replay, determinism and result fidelity

| ID | Required behavior |
| --- | --- |
| R29 | Proven ordered revisions of one native object may supersede an older revision. |
| R30 | Ambiguous reissue/revision lineage remains visible and is not silently collapsed. |
| R31 | Observation ordering and duplicate placement do not alter the semantic result. |
| R32 | Per-reviewer attribution, recommendation and finding references remain distinct in result assessments. |
| R33 | PASS reason is `POLICY_EXEMPT` or `REQUIREMENTS_SATISFIED`, never an unqualified generic PASS. |
| R34 | Every semantic R2A result carries `binding:false`. |

### Judge, authority and bootstrap

| ID | Required behavior |
| --- | --- |
| R35 | `current_advisory` with `judge_relation:candidate_under_test` is `INCOMPLETE` and cannot masquerade as `prior_integrated` or PASS. |
| R36 | Valid structured but unavailable, partial, mismatched, revoked, deprecated or unknown authority/judge material yields semantic `INCOMPLETE` and exit 3. |
| R37 | Candidate-changed runtime lock cannot select the authority-owned expected trusted judge. |
| R38 | Synthetic historical replay pins its exact fixture-only historical authority and judge identities; retained pre-R2A evidence is not reclassified as having a historical trusted R2A judge. |
| R39 | Native execution is not labelled v1 `prior_integrated` solely from current source-root/runtime-lock binding. |
| R40 | A later candidate that modifies review evaluator/schema cannot replace the separately selected prior-integrated judge. |

### CLI, configuration errors and effect boundary

| ID | Required behavior |
| --- | --- |
| R41 | Exit mapping is exactly PASS=0, BLOCKED=1, configuration/tool error=2, INCOMPLETE=3, CONFLICTING=4. |
| R42 | Semantic-result JSON is canonical; human text cannot erase outcome, reason, subject, authority or `binding:false`. |
| R43 | File-mode command performs no network/provider mutation, approval, merge or release effect. |
| R44 | Malformed invocation, malformed authority/judge record or unsupported input schema exits 2 and emits the canonical `error` envelope, never a semantic review-gate result. |

## Focused fixtures

Use retained PR #239 review history plus the two #11 CodeRabbit collection incidents as real pre-R2A examples, but store only bounded fields required by the test contract. Preserve raw/provider evidence by reference/digest where retained; do not manufacture provider messages from summaries and do not assign those real records a historical trusted R2A judge that did not exist.

Add synthetic minimal cases where real retained evidence does not exercise a predicate, including explicit policy exemption, single-policy reachable `CONFLICTING`, forged self-qualification, authority/judge mismatch, ordering invariance, and **historical authority/judge pinning**. Synthetic fixture authority/judge IDs are explicitly marked fixture-only and are never cited as historical production facts.

`cases.json` names every case by its R-ID and contains only supplied input/fixture references. `expected.json` maps each R-ID to the required semantic outcome/reason or error-envelope class plus exit code. The test runner must fail if a required R-ID is absent from either file.

## Mutation and discriminating controls after GREEN

Mutate one assurance fact at a time and require a discriminating result: remove one required source; change merge-base with same head; forge observation capability/domain; collapse two domains to one; alter policy or qualification digest; alter expected/acquired judge binding or judge status; move `as_of` across a freshness threshold; reorder observations; switch required review to explicit no-review. Controls must expose both false-PASS and false-BLOCK tendencies.

## Complete verification and review

After unchanged RED -> GREEN, run focused tests plus applicable repository `policy`, `fast`, `regression`, `smoke`, extended and container-first suites. Rebind the exact final candidate head/tree. Capture every external review separately under Decision 0061 and reconcile each material finding against the exact reviewed subject.

## Advisory dogfood

Bootstrap dogfood has three distinct claims and must not collapse them:

1. **synthetic historical-replay contract exercise:** use explicitly fixture-only authority/judge identities to demonstrate deterministic historical pinning, freshness, quorum, blocker and conflict semantics; this is a test fixture, not evidence that R2A existed historically;
2. **real retained pre-R2A characterization:** evaluate retained PR #239 / Issue #11 evidence with `judge_relation:candidate_under_test` to measure normalization, collection-completeness and result usefulness without fabricating historical trusted authority/judge facts;
3. **current-advisory bootstrap characterization:** demonstrate that the first implementation returns `INCOMPLETE` rather than PASS while no prior-integrated R2A judge exists.

After a real R2A authority/judge record has been integrated, factual historical replay of real R2A results and current-advisory PASS behavior become eligible post-bootstrap evaluation targets.

Measure false pass/block against owner semantic disposition where a comparable semantic judgment exists, subject/currentness classification error, collection handling, qualification/quorum error, normalization discrepancy, rate-limit/unavailability behavior, synthetic replay determinism, evidence/context burden and owner corrections.

## Completion boundary

The specification is implementation-handoff-ready only after its reviews converge and the RED receipt above is fully observed. The bounded slice is complete only when the Decision/task/implementation agree, all retained RED cases are GREEN without semantic weakening, mutation controls discriminate, complete applicable suites pass on the exact candidate, every material external finding is dispositioned, dogfood is retained honestly, and public output remains advisory with no provider or merge enforcement activated. Owner semantic acceptance and merge authorization remain separate.
