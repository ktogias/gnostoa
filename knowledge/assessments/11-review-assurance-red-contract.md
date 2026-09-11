---
type: Source
title: D11-R2A review-assurance RED-first execution contract
description: Verification-first contract for the bounded provider-neutral advisory review-assurance gate selected by Decision 0067.
status: draft
generated:
  by: agent:gpt-5.6-sol
  at: "2026-09-11T23:24:00Z"
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

1. Retain this Decision/task/RED specification on the candidate branch and converge it semantically before production implementation.
2. Add focused tests and fixtures while the production review-assurance schemas, policies and executable modules are still absent. Preserve the exact RED commit, commands and bounded failing output.
3. Add production files only after the RED record exists. The retained RED expectations remain unchanged unless a later review explicitly changes the governing Decision and records why.
4. Reach GREEN, then run mutation/permutation controls, complete project suites, exact-candidate reviews and advisory dogfood.

The first R2A implementation is bootstrap: any self-run `review-check` is `candidate_under_test` evidence only.

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
| R09 | A finite policy freshness limit that is exceeded produces `INCOMPLETE`, never PASS. |
| R10 | Historical replay uses its exact pinned historical authority and judge; current replacements are not silently substituted. |

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
| R19 | Multiple observations from one established domain contribute one distinct domain. |
| R20 | Two separately established domains can satisfy a two-domain quorum. |
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
| R28 | A focused alternate valid policy can produce `CONFLICTING`, distinct from `INCOMPLETE`. |

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
| R35 | First-implementation `candidate_under_test` cannot masquerade as `prior_integrated`. |
| R36 | Missing, partial, mismatched, revoked, deprecated, unknown or unsupported-schema judge binding fails closed. |
| R37 | Candidate-changed runtime lock cannot select the authority-owned expected trusted judge. |
| R38 | Historical replay pins its exact historical judge identity. |
| R39 | Native execution is not labelled v1 `prior_integrated` solely from current source-root/runtime-lock binding. |
| R40 | A later candidate that modifies review evaluator/schema cannot replace the separately selected prior-integrated judge. |

### CLI and effect boundary

| ID | Required behavior |
| --- | --- |
| R41 | Exit mapping is exactly PASS=0, BLOCKED=1, configuration/tool error=2, INCOMPLETE=3, CONFLICTING=4. |
| R42 | JSON is canonical; human text cannot erase outcome, reason, subject, authority or `binding:false`. |
| R43 | File-mode command performs no network/provider mutation, approval, merge or release effect. |

## Focused fixtures

Use retained PR #239 review history plus the two #11 CodeRabbit collection incidents as real examples, but store only the bounded fields required by the test contract. Preserve raw/provider evidence by reference/digest where retained; do not manufacture provider messages from summaries.

Add synthetic minimal cases only where a real retained case does not exercise the required predicate, especially explicit policy exemption, a reachable `CONFLICTING` policy, forged self-qualification, authority/judge mismatch and ordering invariance.

## Mutation and discriminating controls after GREEN

Mutate one assurance fact at a time and require a discriminating result: remove one required source; change merge-base with same head; forge observation capability/domain; collapse two domains to one; alter policy or qualification digest; alter expected/acquired judge binding or judge status; move `as_of` across a freshness threshold; reorder observations; switch required review to explicit no-review. Controls must expose both false-PASS and false-BLOCK tendencies.

## Complete verification and review

After unchanged RED -> GREEN, run focused tests plus applicable repository `policy`, `fast`, `regression`, `smoke`, extended and container-first suites. Rebind the exact final candidate head/tree. Capture every external review separately under Decision 0061 and reconcile each material finding against the exact reviewed subject.

## Advisory dogfood

Run two bounded modes:

1. **historical replay** over retained PR #239/#11 evidence with an exact historical `as_of`, authority and judge fixture identity;
2. **first-implementation self dogfood** over the candidate review evidence with `judge_relation:candidate_under_test`.

Measure false pass/block against owner semantic disposition, subject/currentness classification error, collection handling, qualification/quorum error, normalization discrepancy, rate-limit/unavailability behavior, historical replay reproducibility, evidence/context burden and owner corrections.

## Completion boundary

The bounded slice is complete only when the Decision/task/implementation agree, all retained RED cases are GREEN without semantic weakening, mutation controls discriminate, complete applicable suites pass on the exact candidate, every material external finding is dispositioned, dogfood is retained honestly, and public output remains advisory with no provider or merge enforcement activated. Owner semantic acceptance and merge authorization remain separate.