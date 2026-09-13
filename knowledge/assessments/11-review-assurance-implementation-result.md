---
type: Source
title: D11-R2A advisory semantic review assurance implementation result
description: Corrected exact-subject implementation, verification, review-evidence and post-approval convergence result for the bounded D11-R2A P1 advisory review-assurance gate.
status: draft
generated:
  by: openai/gpt-5.6-sol
  at: "2026-09-12T19:37:20Z"
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
  - id: post-approval-rca
    resource: https://github.com/ktogias/gnostoa/issues/11#issuecomment-5648009539
    title: D11-R2A post-approval review-cut and oracle-strength retrospective
  - id: corrective-verification
    resource: https://github.com/ktogias/gnostoa/actions/runs/34714268858
    title: Corrective exact-head verification run
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

## Current result

`GNOSTOA/D11-R2A/P1` now has a corrected implementation/guardrail subject at exact commit
`456267d93c59f5a2ca161a7fef04938348bc8683`, tree
`eeb72672b1a4e1503519f5f3faa945d8b0b13659`.

GitHub Actions run
[`34714268858`](https://github.com/ktogias/gnostoa/actions/runs/34714268858)
completed successfully on that exact subject for:

- `policy`;
- `fast`, including the unchanged historical R01-R45 GREEN harness and the new post-RED discriminating property regressions;
- Python 3.11 source compatibility;
- Python 3.12 source/install compatibility, canonical Ruff formatting and strict mypy over the review trust domain;
- `regression`; and
- `smoke`, including exact executable-candidate binding.

`extended` was **SKIPPED** and is not represented as PASS.

This corrected technical subject is mechanical evidence only. It is not accountable-owner semantic acceptance, a completed final review-evidence cut, merge authorization, publication authority or a provider-required semantic-review check. Evidence/state finalization after this subject creates a later exact candidate that must itself pass required CI before final review collection begins.

## Why the earlier convergence statement was superseded

The earlier implementation result correctly recorded what had been observed at the time, but its conclusion that P1 was ready for accountable-owner review proved too strong.

The historical sequence remains factual:

- production code converged at `f08b3e00e52c73333cdf356fb45374fb4e2ebbbe`;
- GitHub Actions run
  [`34692238908`](https://github.com/ktogias/gnostoa/actions/runs/34692238908)
  succeeded on that exact subject;
- CodeRabbit comment `5645773763` reported no BLOCKING/MATERIAL finding in that review pass;
- later dogfood/finalization/ready subjects also passed their then-applicable checks; and
- accountable-owner approval `5647591088` was recorded for exact source head
  `45befab9d65da2cb68fec916101071818ebac4ec`.

However, the PR was still Draft when that approval was recorded. After it transitioned to Ready, new material Sourcery and Qodo review findings arrived on the **same unchanged source SHA**. The source subject was stable, but the available review-evidence set was not yet complete. Merge protection blocked integration before main changed.

Issue #11 comment `5648009539` is the durable post-approval RCA. Its central correction is:

> review readiness and owner-approval freshness bind both the immutable candidate subject and a reconciled review-evidence cut.

A later material finding makes the approval stale even if the Git SHA does not change. The historical approval remains a real event; it is not current merge authorization for the corrected candidate.

## Immutable RED chronology is preserved

The authoritative pre-production RED receipt remains commit
`97244d233e8c798c23a408ffe40f5eb96f252b40`. At that commit:

- `python tests/test_review_assurance.py` exited `1`;
- stdout was exactly 698 bytes with SHA-256
  `6584f3cde2f6916f90e39e825b768fbdbecb51958f734e5358bf9c6896207e9b`;
- stderr was zero bytes; and
- R01-R45 failed while production review-assurance paths were absent.

The four receipt-bearing RED artifacts were **not modified** during corrective convergence:

```text
tests/test_review_assurance.py
tests/fixtures/review_check/cases.json
tests/fixtures/review_check/expected.json
tests/fixtures/review_check/red-observed-output.json
```

The same historical harness remains GREEN after production implementation. The corrective work adds separate post-RED regression/property tests rather than rewriting the evidence that established verification-first chronology.

This distinction matters because the post-approval RCA showed that a named R-ID can exist without sufficiently discriminating every wrong implementation allowed by that prose requirement. The immutable RED record proves chronology; the additional property suite strengthens current oracle quality.

## Corrective defects and dispositions

The post-approval review/read-back confirmed the following material implementation defects on the previously approved head and corrected them in the current technical subject.

### Duplicate retained identities

Previously:

- duplicate `observation_id` silently used first-wins behavior; and
- duplicate collection `source_id` silently used last-wins behavior.

The same evidence in a different order could therefore alter semantic evaluation.

Now:

- exact duplicate observations are idempotent;
- conflicting duplicate observation identities are configuration errors;
- exact duplicate collection-source records are idempotent;
- conflicting duplicate collection-source identities are configuration errors; and
- collection output is canonically ordered.

### Revision-lineage authority

Previously, caller-supplied `native.object_id` plus numeric revision could establish a replacement lineage strongly enough for a higher revision to supersede a lower one.

P1 has no independently established real-provider lineage authority. The corrected boundary therefore refuses to derive such authority from caller fields:

- multiple same-object real/non-fixture observations remain visible but carry `revision_lineage_unproven` and cannot count for blocker/conflict/quorum authority;
- only explicitly synthetic `fixture_only` replay may exercise fixture-proven numeric supersession semantics; and
- equal/ambiguous fixture revisions remain non-authoritative.

A future real provider-lineage acquisition contract requires separate admission and evidence.

### Qualification identity

Qualification lookup is authority-bearing. Repeated `(reviewer_id, source_id)` entries are therefore rejected as ambiguous configuration rather than allowed to contribute multiple domains according to input order.

### Explicit no-review precedence

`review_requirement:none` is now applied before blocker/conflict/collection/quorum semantics. An exempt mechanical change cannot be converted into `BLOCKED` or `CONFLICTING` merely because retained review evidence exists.

### Change-class override semantics

Source-policy inheritance retains the repository's existing monotonic `deep_merge` behavior. A selected change-class specialization is different: an explicit list value replaces the inherited list. The mechanical class therefore truly resolves to:

- `review_requirement:none`;
- no required review source;
- no required review capability; and
- quorum zero.

### Bootstrap reason invariance

After basic input/context/subject shape validation, every well-formed P1 `current_advisory` invocation reaches the shared fail-closed bootstrap result before caller-authored policy/judge material can select another semantic reason:

```text
outcome = INCOMPLETE
reason = BOOTSTRAP_PROTECTED_AUTHORITY_UNAVAILABLE
binding = false
```

P1 still has no protected prior-integrated current-advisory authority acquisition path and cannot manufacture one from candidate input.

## Post-RED oracle-strengthening evidence

The corrective suite explicitly tests properties that the earlier named matrix did not discriminate strongly enough.

`tests/test_review_assurance_property_regressions.py` now exercises, among other cases:

- R01 abstract/unresolved policy and zero-observation variants;
- R14 optional-source outage visibility without false blocking;
- R26 unrecognized evidence with no quorum, blocker or conflict authority;
- R31 actual observation permutations and duplicate placement with canonical-result equality;
- R32 preservation of reviewer attribution, raw recommendation, normalized recommendation, findings and normalization provenance;
- R42 exact subject/authority/judge/`binding:false` fidelity plus canonical JSON round-trip;
- R43 through the public file-mode CLI path with network creation explicitly forbidden;
- R44 a closed, typed canonical error envelope;
- R45 independent forged `admitted`, normalized-recommendation, adapter-id, adapter-version, rule-id and raw-state-digest claims; and
- duplicate qualification identity ambiguity.

Focused integration regressions separately cover duplicate observation/source ordering, policy-exemption precedence, mechanical list replacement, bootstrap-reason precedence and unproven real revision lineage.

This is not a claim of exhaustive mutation coverage. It is evidence that the specific contract-bearing failure classes exposed by the post-approval review now have discriminating controls rather than only named case IDs.

## Real-provider dogfood correction

The earlier dogfood narrative was too broad when it said no synthetic historical trusted judge was assigned to the real PR #239 provider records. The then-current helper actually evaluated those real records inside a fixture-only `historical_replay / prior_integrated` envelope. That was useful synthetic replay, but it could overstate the trust boundary of the real records.

The corrected dogfood separates the two concepts:

- real PR #239 records are normalized directly with their attributable provider/native fields;
- older-head behavior is characterized against PR #239 final head without assigning those records historical production authority; and
- current-advisory characterization uses `candidate_under_test`, remains `fixture_only:false`, and returns bootstrap `INCOMPLETE`.

The retained real records remain:

- Qodo review `5182705577`, native `COMMENTED`, older reviewed commit
  `1337c82e28256f265b4c28b1fe41980e2cf7e832`;
- Sourcery review `5182778419`, native `APPROVED`, older reviewed commit
  `204695d0647a0601f4fbae340e2fc86234dedfb3`;
- PR #239 final head `1fa8eb9ff1ae0604663f2611cd67fdedb97d88c9`;
- merge-base `a0b7c8a170942fce61ff3c08b350bc3d7ab0a2a0`.

They remain real evidence of native normalization and older-head attribution. They are not evidence that an R2A trusted historical judge existed before R2A itself.

## Governance and discoverability correction

The semantic-review assurance gate is now registered in `policy/guardrails.yaml` as `semantic-review-assurance`, linked to Decision 0067, the policies, three public schemas, evaluator/adapter/CLI implementation and the immutable plus post-RED test surfaces.

The guardrail update was itself diff-audited. Two accidental changes to unrelated historical test references were detected and removed before the technical subject was frozen; the final guardrail delta is limited to its version increment and the new R2A guardrail entry.

## Corrective exact-head verification

Exact technical subject:

```text
commit: 456267d93c59f5a2ca161a7fef04938348bc8683
tree:   eeb72672b1a4e1503519f5f3faa945d8b0b13659
run:    https://github.com/ktogias/gnostoa/actions/runs/34714268858
```

Observed result on that exact subject:

- `policy`: SUCCESS;
- `fast`: SUCCESS;
- Python 3.11 compatibility: SUCCESS;
- Python 3.12 compatibility: SUCCESS;
- Ruff: SUCCESS;
- strict mypy over the review trust domain: SUCCESS;
- clean installed-artifact smoke: SUCCESS;
- `regression`: SUCCESS;
- `smoke`: SUCCESS, including exact executable-candidate binding;
- `extended`: SKIPPED, not PASS.

GitHub Actions logs and run metadata are provider-managed evidence and may be subject to provider retention. The stable URL and exact subject/run identity are recorded here, while committed tests, policies and knowledge records preserve the bounded claims without pretending that provider logs are permanent archival storage.

## Retained boundary

The corrected P1 remains deliberately small and advisory. It does **not** add:

- live provider collection;
- reviewer trigger/wait/orchestration;
- Issue #10 reviewer registry or independence discovery;
- provider mutation or thread auto-resolution;
- human semantic acceptance;
- merge/release authority;
- a required provider merge check;
- a generic policy language;
- a trusted native current-advisory judge/acquisition path; or
- the future review-handoff/merge-readiness preflight selected for later #15 evaluation.

The latter is a roadmap consequence of this incident, not part of P1.

## Review-evidence and approval rule going forward

Final owner review now requires two current subjects:

1. the exact frozen candidate/base identity; and
2. a declared, reconciled review-evidence cut for that candidate.

The PR must become GitHub Ready **before** final review collection. All material findings in the declared collection are then fixed, rejected with evidence, deferred under explicit authority or accepted as residual risk. Only after that cut is recorded may accountable-owner semantic approval be requested.

Any material review evidence arriving after the accepted cut makes approval stale before merge, even if the source SHA is unchanged. A final provider/source read-back immediately precedes any separately authorized merge.

## Relationship to the earlier retrospective

`11-review-assurance-implementation-retrospective.md` remains a useful historical pre-approval implementation-convergence retrospective, especially for the CLI/shared-evaluator trust-boundary and CI-wiring incidents it captured. Its conclusion that the work had already succeeded must now be read as superseded by the later post-approval evidence.

For current process truth, use this corrected result together with Issue #11 post-approval RCA `5648009539` and the current task envelope. The later RCA is not retroactively inserted into the earlier historical narrative.

## Current disposition

The corrective implementation/guardrail subject is mechanically verified. Evidence/state finalization follows on a later exact head and must pass required CI again.

After that finalization candidate is frozen, the PR may transition from Draft to Ready **only to begin final review collection**. No new accountable-owner approval has yet been requested, and there is no current merge authorization.
