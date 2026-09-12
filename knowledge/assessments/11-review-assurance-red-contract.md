---
type: Source
title: D11-R2A review-assurance RED-first execution contract
description: Verification-first contract for the bounded provider-neutral advisory review-assurance gate selected by Decision 0067.
status: draft
generated:
  by: agent:gpt-5.6-sol
  at: "2026-09-12T06:07:19Z"
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

The bounded task is `GNOSTOA/D11-R2A/P1` at exact base `9915357546e1665143b3a705533bb94812faee54`. It may add only Decision/task/assessment records, three review-assurance schemas, abstract/core and Gnostoa-self policy, flat file/model/policy/evaluator/CLI modules, focused tests/fixtures and minimum existing CLI/help routing for `knowledge review-check`.

It does not admit a live provider collector, reviewer orchestration, #10 registry, #15 workflow mechanics, provider mutation, merge enforcement, policy DSL, signing service or trusted native judge identity.

## Literal verification-first order

1. Converge Decision 0067, task envelope and this RED contract before production implementation.
2. Add the exact focused RED harness below while production review-assurance schemas, policies and executable modules are still absent.
3. Run the exact RED command and retain its commit SHA, nonzero exit, canonical bounded output bytes/SHA-256 and proof that production paths remain absent.
4. Complete every RED receipt field and run `python tests/test_review_assurance.py --verify-receipt` against the exact pre-production candidate. The verifier must return exit 0 with canonical `ok:true`; it must fail while receipt metadata is `PENDING`, when retained output/blob identities drift, or when the declared RED command no longer reproduces the receipt.
5. Only after the observed RED receipt and executable receipt verification converge may the task hand off to production implementation.
6. Preserve RED expectations unchanged through production implementation unless a later review explicitly changes Decision 0067 and records why.
7. Reach GREEN, then run mutation/permutation controls, complete suites, exact-candidate reviews and advisory dogfood.

The first R2A implementation is bootstrap. `current_advisory + candidate_under_test` is valid but assurance-incomplete and cannot PASS. Synthetic fixture-only historical replay may exercise normal policy/quorum/blocker/conflict and historical-pinning semantics. Real retained pre-R2A review evidence is characterized separately as `candidate_under_test`; it is never assigned a fabricated historical trusted R2A judge.

## Pre-registered RED harness

Create exactly these four focused pre-production artifacts in the RED commit:

```text
tests/test_review_assurance.py
tests/fixtures/review_check/cases.json
tests/fixtures/review_check/expected.json
tests/fixtures/review_check/red-observed-output.json
```

The first three are authored before the RED run. `red-observed-output.json` is populated only with exact canonical stdout bytes observed from that RED run and retained in the same RED commit; it is evidence, not an expected-output template.

The RED command is exactly:

```text
python tests/test_review_assurance.py
```

Before production review-assurance paths exist, the command must exit nonzero and must not SKIP/XFAIL the missing contract. The runner must turn expected missing-production failures into the canonical RED report defined below instead of leaking environment-specific traceback text.

### Canonical RED report bytes

The RED harness has one receipt-bearing output channel:

- **stdout** contains exactly one UTF-8 JSON object followed by exactly one LF (`0x0a`); no BOM and no bytes precede or follow it;
- serialization is Python `json.dumps(report, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"`;
- the stdout report object contains **only** stable test-result fields: `schema`, `phase`, `required_case_ids`, `failing_case_ids`, `unexpected_case_ids`, and `production_paths_absent`;
- all case-ID arrays are lexicographically sorted; paths, timestamps, hostnames, Python versions, tracebacks and timing are forbidden from the stdout report object;
- **stderr must be exactly zero bytes**. Any stderr output invalidates the RED receipt and blocks handoff;
- stdout has a hard maximum of **65,536 bytes**. **No truncation is permitted**: exceeding the limit invalidates the receipt rather than hashing a truncated stream;
- `bounded_output_sha256` is SHA-256 of the exact stdout report bytes described above, including the final LF and excluding stderr;
- exact stdout report bytes are retained byte-for-byte at `tests/fixtures/review_check/red-observed-output.json` in the RED commit. Its file SHA-256 must equal `bounded_output_sha256`.

**The stdout report and the RED receipt are deliberately different objects.** `bounded_output_sha256`, `red_output_artifact`, `red_commit`, command, exit code, stderr byte count and exact Git blob identities are receipt metadata recorded outside the stdout JSON. They are not fields in `red-observed-output.json` and are not part of the bytes being hashed. This prevents self-referential hashing. The receipt points to and authenticates the retained stdout report; the stdout report does not contain its own digest or path.

The stdout report `schema` is `gnostoa-review-assurance-red/v1`, `phase` is `RED`, and `required_case_ids` contains every required R-ID in this contract. The RED receipt is invalid if the retained report file differs from captured stdout, if stderr is nonempty, if a required R-ID is absent, if any retained RED artifact has a different Git blob identity, or if the report exceeds the byte limit. There is no executor-defined alternate capture/truncation convention.

### RED receipt — must be completed before production handoff

```text
red_commit: 97244d233e8c798c23a408ffe40f5eb96f252b40
command: python tests/test_review_assurance.py
exit_code: 1   # must be nonzero
stdout_bytes: 698
bounded_output_sha256: sha256:6584f3cde2f6916f90e39e825b768fbdbecb51958f734e5358bf9c6896207e9b
red_output_artifact: tests/fixtures/review_check/red-observed-output.json
stderr_bytes: 0   # must be 0
red_harness_blob: 02ba5e5fba45d60c5b9435f7d080f40fbe62940c
red_cases_blob: ea2b21fb6aec057ad19eb200df1c492464e0dfd9
red_expected_blob: 1e971fc7bce48d0f0b7067fa0cf3884d78f13cb3
red_output_blob: 1fe79157a85098c1f04b27dc1848752a306af63a
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
  - existing tools/cli.py has no review-check route/import/reference
```

`PENDING` in any scalar RED receipt field blocks production implementation handoff. After the receipt is populated, the exact verifier command is:

```text
python tests/test_review_assurance.py --verify-receipt
```

The verifier is pre-production handoff evidence. It re-runs the declared RED command, captures stdout/stderr as bytes, checks exit code and the 65,536-byte bound, compares stdout byte-for-byte with the retained output, verifies the stdout SHA-256, validates all four retained Git blob identities, and checks the canonical RED report still says `production_paths_absent:true` with every R-ID. The `red_commit` itself is additionally rebound through Git/provider exact-object readback and review; the local verifier validates that it is a canonical 40-hex identity but does not claim remote Git-object attestation.

The observed RED commit/output are evidence, not values to predict in this specification.

## Required RED matrix

### Policy and explicit no-review

| ID | Required behavior |
| --- | --- |
| R01 | Missing, unresolved or abstract policy plus zero observations cannot PASS. |
| R02 | Explicit `review_requirement:none` may PASS only with reason `POLICY_EXEMPT`. |
| R03 | Empty lists inside a required-review class do not silently become no-review. |
| R04 | A candidate-weakened supplied policy with the prior authority policy digest held fixed is rejected as unresolved/`INCOMPLETE`; unauthoritative candidate claims cannot replace the selected prior-effective authority policy. |

### Subject and time cut

| ID | Required behavior |
| --- | --- |
| R05 | Same head with a different merge-base is a different/non-counting reviewed subject. |
| R06 | Older-head review remains visible but cannot satisfy current exact-head policy. |
| R07 | Partial or unestablished subject binding remains visible but cannot satisfy exact-subject policy. |
| R08 | Any used observation, required-collection or qualification cut later than `EvaluationContext.as_of` is configuration error, with those cut classes exercised independently. |
| R09 | With RFC3339 cuts interpreted as UTC instants, finite freshness is `0 <= utc(as_of)-utc(cut) <= max_age`; exceeding the finite limit produces `INCOMPLETE`, never PASS. |
| R10 | A synthetic fixture-only `historical_replay` pins exact fixture authority and judge identities and refuses silent current substitution or a missing fixture-only marker, without claiming those identities were real historical production authority. |

### Collection completeness

| ID | Required behavior |
| --- | --- |
| R11 | Omitted policy-required source produces unmet/`INCOMPLETE` evidence. |
| R12 | Required `PARTIAL`, `RATE_LIMITED`, `UNAVAILABLE` or `ERROR` source prevents PASS, with each state exercised independently. |
| R13 | Silence, truncation, rate limit or unavailable retrieval never normalizes to no-findings. |
| R14 | Optional unavailable source remains visible but need not block when every actual requirement is independently satisfied. |
| R15 | Incomplete collection cannot manufacture absence, blocker resolution or quorum. |

### Qualification and quorum

| ID | Required behavior |
| --- | --- |
| R16 | Capability/domain claims inside input review evidence do not qualify the observation. |
| R17 | Wrong or unaccepted authority/qualification digest cannot satisfy quorum. |
| R18 | `unestablished`, `revoked` or freshness-expired qualification cannot count, with each condition exercised independently. |
| R19 | Multiple observations from one established opaque domain ID contribute one distinct domain. |
| R20 | Two separately established opaque domain IDs can satisfy a two-domain quorum. |
| R21 | Owner-authored review does not count when effective policy says false. |
| R22 | Evaluator emits no human owner acceptance or merge authorization. |

### Normalization, blockers and conflicts

| ID | Required behavior |
| --- | --- |
| R23 | Positive prose without an admitted native recommendation state normalizes to `UNKNOWN`, never inferred `APPROVE`. |
| R24 | Eligible current adapter-derived `REQUEST_CHANGES` yields `BLOCKED`. |
| R25 | A known eligible blocker is not masked by another missing required source. |
| R26 | Evidence that is partially/unestablished subject-bound, anonymous, policy-unrecognized, non-current, or lacks active-adapter-derived normalization provenance remains visible but has no blocker or conflict authority; it also cannot satisfy quorum merely by existing. |
| R27 | Unresolved thread blocks only according to policy; unknown thread state can remain incomplete. |
| R28 | Within one invocation and one selected valid policy whose `conflicts` section declares the applicable recommendation pair, two eligible conflicting review dispositions produce `CONFLICTING`, distinct from `INCOMPLETE`; policies themselves are never compared. |
| R45 | Caller/fixture claims a forged normalized recommendation, `adapter_id`, `adapter_version`, `rule_id`, raw-state digest or `admitted` flag that differs from active-adapter recomputation: the claim cannot create blocker/conflict authority and the mismatch fails closed as configuration error. |

### Replay, determinism and result fidelity

| ID | Required behavior |
| --- | --- |
| R29 | Proven ordered revisions of one native object may supersede an older revision. |
| R30 | Ambiguous reissue/revision lineage remains visible and is not silently collapsed. |
| R31 | Observation ordering and duplicate placement do not alter the semantic result. |
| R32 | Per-reviewer attribution, raw/native recommendation, normalized recommendation and finding references remain distinct in result assessments. |
| R33 | PASS reason is `POLICY_EXEMPT` or `REQUIREMENTS_SATISFIED`, never an unqualified generic PASS. |
| R34 | Every semantic R2A result carries `binding:false`. |

### Judge, authority and bootstrap

| ID | Required behavior |
| --- | --- |
| R35 | `current_advisory` with `judge_relation:candidate_under_test` is `INCOMPLETE` and cannot masquerade as `prior_integrated` or PASS. |
| R36 | Valid structured but unavailable, partial, mismatched, revoked, deprecated or unknown authority/judge material yields semantic `INCOMPLETE` and exit 3; revoked/deprecated/unknown judge status are exercised independently. |
| R37 | Candidate-changed runtime lock cannot select the authority-owned expected trusted judge. |
| R38 | Synthetic historical replay pins its exact fixture-only authority/judge identity. Independent mismatches of runtime image digest, public-surface digest and supported input-schema versions are non-trusted/`INCOMPLETE`; retained pre-R2A evidence is not reclassified as having a historical trusted R2A judge. |
| R39 | Native execution is not labelled v1 `prior_integrated` solely from current source-root/runtime-lock binding. |
| R40 | A later candidate that modifies review evaluator/schema/adapter cannot replace the separately selected prior-integrated judge. |

### CLI, configuration errors and effect boundary

| ID | Required behavior |
| --- | --- |
| R41 | Exit mapping is exactly PASS=0, BLOCKED=1, configuration/tool error=2, INCOMPLETE=3, CONFLICTING=4. |
| R42 | Semantic-result JSON is canonical; human text cannot erase outcome, reason, subject, authority or `binding:false`. |
| R43 | File-mode command performs no network/provider mutation, approval, merge or release effect. |
| R44 | Malformed invocation, malformed authority/judge record or unsupported input schema exits 2 and emits the canonical `error` envelope, never a semantic review-gate result. |

## Focused fixtures

Use retained PR #239 review history plus the two #11 CodeRabbit collection incidents as real pre-R2A examples, storing only bounded fields required by the test contract. Preserve raw/provider evidence by reference/digest where retained; do not manufacture provider messages from summaries and do not assign those real records a historical trusted R2A judge that did not exist.

Add synthetic minimal cases where real retained evidence does not exercise a predicate, including explicit policy exemption, single-policy reachable `CONFLICTING`, forged self-qualification, authority/judge mismatch, ordering invariance, historical authority/judge pinning, and **forged normalization provenance**. Synthetic authority/judge IDs are explicitly fixture-only and never cited as historical production facts.

For normalization cases, retained/native recommendation state is input to the active file adapter. Any supplied normalized/provenance fields are adversarial claims. Expected authoritative normalization/provenance is recomputed by the selected adapter rule. `cases.json` must include at least one R45 mutant where the claimed normalized value/provenance conflicts with recomputation.

`cases.json` names every required case by R-ID and contains supplied input/fixture references. `expected.json` maps each R-ID to required semantic outcome/reason or error-envelope class plus exit code. A named R-ID may have bounded subvariants when one normative predicate enumerates multiple states; subvariants inherit the R-ID expectation unless `expected.json` explicitly supplies a stricter variant expectation. The runner fails if a required R-ID is absent from either file.

## Mutation and discriminating controls after GREEN

Mutate one assurance fact at a time and require a discriminating result: remove one required source; change merge-base with same head; forge observation capability/domain; collapse two domains to one; alter policy or qualification digest; alter each expected/acquired judge binding component or judge status; move `as_of` across a freshness threshold; forge normalized recommendation/provenance; reorder observations; switch required review to explicit no-review. Controls must expose both false-PASS and false-BLOCK tendencies.

## Complete verification and review

After unchanged RED -> GREEN, run focused tests plus applicable repository `policy`, `fast`, `regression`, `smoke`, extended and container-first suites. Rebind the exact final candidate head/tree. Capture every external review separately under Decision 0061 and reconcile each material finding against the exact reviewed subject.

## Advisory dogfood

Bootstrap dogfood has three distinct claims and must not collapse them:

1. **synthetic historical-replay contract exercise:** explicitly fixture-only authority/judge identities demonstrate deterministic historical pinning, freshness, quorum, blocker/conflict and normalization semantics; this is test evidence, not evidence that R2A existed historically;
2. **real retained pre-R2A characterization:** retained PR #239 / Issue #11 native evidence is processed by the candidate file adapter with `judge_relation:candidate_under_test` to measure normalization, collection completeness and result usefulness without fabricating historical trusted authority/judge facts;
3. **current-advisory bootstrap characterization:** first implementation returns `INCOMPLETE`, not PASS, while no prior-integrated R2A judge exists.

After a real R2A authority/judge record is integrated, factual historical replay of real R2A results and current-advisory PASS become eligible post-bootstrap evaluation targets.

Measure false pass/block against owner semantic disposition where comparable, subject/currentness classification error, collection handling, qualification/quorum error, normalization discrepancy, rate-limit/unavailability behavior, synthetic replay determinism, evidence/context burden and owner corrections.

## Completion boundary

The specification is implementation-handoff-ready only after reviews converge, every RED receipt scalar is fully observed, the exact `--verify-receipt` command succeeds on the pre-production candidate, and Git/provider readback confirms the recorded RED commit/artifact identities. The bounded slice is complete only when Decision/task/implementation agree, all retained RED cases are GREEN without semantic weakening, mutation controls discriminate, complete applicable suites pass on exact candidate, every material external finding is dispositioned, dogfood is retained honestly, and public output remains advisory with no provider or merge enforcement activated. Owner semantic acceptance and merge authorization remain separate.
