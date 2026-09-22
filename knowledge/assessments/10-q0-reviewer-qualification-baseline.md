---
type: Source
title: Q0 reviewer qualification and independence baseline
description: Source-bound candidate baseline for the first Gnostoa-self semantic-review qualification domains, staged behind prior-integrated runtime support.
status: draft
generated:
  by: openai/gpt-5.6-sol
  at: "2026-09-22T05:57:03Z"
sources:
  - id: owner-admission
    resource: https://github.com/ktogias/gnostoa/issues/10#issuecomment-5771806967
    title: Owner admission — Q0 reviewer qualification and independence baseline
  - id: q0-checkpoint
    resource: https://github.com/ktogias/gnostoa/issues/10#issuecomment-5706402207
    title: Q0 reviewer qualification, perspective coverage and currentness
  - id: candidate-json
    resource: ./10-q0-reviewer-qualification-baseline.json
    title: Machine-readable Q0 candidate baseline
  - id: decision
    resource: ../decisions/0088-establish-q0-reviewer-qualification-semantics.md
    title: Establish Q0 reviewer qualification semantics and stage protected activation
x-project-knowledge:
  id: kit.assessment.10-q0-reviewer-qualification-baseline
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0088-establish-q0-reviewer-qualification-semantics.md
---

# Q0 reviewer qualification and independence baseline

## Purpose

Turn the existing truthful negative qualification snapshot into a source-bound,
reviewable candidate baseline without manufacturing quorum or bypassing the protected
R2A trust chain.

The machine-readable companion is
[`10-q0-reviewer-qualification-baseline.json`](10-q0-reviewer-qualification-baseline.json).

## Selected independence property

The initial Gnostoa-self domain is an **authenticated external reviewer execution/source
boundary**. A candidate domain needs all of:

1. a distinct authenticated non-owner reviewer principal;
2. provider-controlled review execution separate from the accountable owner;
3. read-only semantic-review behavior for the evidence used to qualify it;
4. exact-head-attributable review behavior.

This is deliberately narrower than “independent intelligence”. It does not establish
different model families, prompts, training data or internal provider runtimes.

## Initial candidate cohort

| Reviewer identity | Source | Candidate independence domain | Capability | Owner relation | Important limitation |
| --- | --- | --- | --- | --- | --- |
| `coderabbitai[bot]` | `retained-review-evidence` | `github-app:coderabbitai` | `semantic-review` | `non_owner` | model/runtime diversity unestablished |
| `gitar-bot[bot]` | `retained-review-evidence` | `github-app:gitar-bot` | `semantic-review` | `non_owner` | model/runtime diversity unestablished |

The source evidence is retained in the JSON baseline. Both providers have produced
provider-authored semantic review artifacts on Gnostoa, expose distinct authenticated
GitHub application principals, and have exact-head review behavior. The qualifying
evidence used here does not include candidate mutation.

A later provider-state read-back exposed a separate recommendation-surface fact:
CodeRabbit and Gitar currently submit formal GitHub `COMMENTED` reviews, while Bito
has repeatedly submitted formal GitHub `APPROVED` reviews. This does not silently
expand the admitted Q0 qualification cohort. The JSON retains Bito only as observed
approval-capable source evidence; qualification of Bito or another source requires a
separate admitted authority update. Consequently Q0 qualification activation alone
does not promise R2A `PASS`.

## What qualification does not mean

An established entry does not mean that the provider:

- is available now;
- has quota now;
- is eligible for every PR;
- will produce `APPROVE`;
- is independent at the model-family level;
- may write source, approve, merge or perform another provider effect.

Those are separate facts and authority boundaries.

## Currentness and revocation

The selected future activation semantics are `not_age_sensitive` for the
qualification assertion itself. A slowly changing capability/independence assertion
must not require a daily authority rewrite merely because 24 hours passed.

Instead, explicit supersession/revocation is required when source identity, owner
relation, read-only reviewer behavior, capability or the selected independence
boundary materially changes or becomes contradicted.

Provider availability, quota and exact-subject eligibility remain volatile and are
reacquired by the #15 orchestration layer.

## Protected-runtime activation boundary

The live protected current-advisory outer runtime is identified by the current
protected bundle at `authority.expected_judge.source_revision`. Its embedded
protected-bundle schema accepts only an empty qualification array. Q0a therefore
binds to that authority field rather than copying its Git revision into the
candidate baseline.

Therefore PR #305 is a **dormant capability preparation**, not the protected
qualification effect:

- source schema gains the normalized non-empty qualification-entry shape;
- tests prove the future shape is closed;
- the candidate qualification data is retained;
- the live protected bundle stays empty.

After Q0a integration, a separately authorized runtime publication/qualification/
promotion sequence must make this schema prior-integrated before Q0b can change the
protected bundle.

## Relationship to PR #297

PR #297 remains separate. Its staged reviewer registry contains stable route identities
for CodeRabbit and Gitar; the Q0 JSON records candidate route bindings but labels them
`pending_pr297_registry_integration`.

Neither PR may treat the other's candidate-only data as protected authority.

After Q0 activation, PR #297 still needs acceptable exact-head review evidence under
unchanged R2A semantics. Qualification alone does not convert `COMMENTED` into
`APPROVE`.

## Verification boundary

This baseline is supported only when:

- the candidate JSON exactly matches the selected two-domain cohort;
- the protected-bundle source schema accepts the normalized future snapshot and
  rejects unknown/missing qualification fields;
- the live protected bundle remains empty during Q0a;
- all existing protected R2A and current-advisory tests remain green;
- fresh exact-head review converges.

No merge or runtime publication authority is supplied by this assessment.
