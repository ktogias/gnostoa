---
type: Decision
title: Evaluate native structured review handoff
description: Qualify official tool startup and structured result exchange in a second bounded self-only trial with successor command evidence.
status: draft
generated:
  by: agent:codex
  at: "2026-09-11T07:12:00Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/235
    title: Selected second trial and pre-implementation behavior map
  - id: first-trial
    resource: https://github.com/ktogias/gnostoa/pull/234
    title: Integrated first experiment with narrower live result
  - id: prior-art
    resource: https://github.com/ktogias/gnostoa/issues/201#issuecomment-5626236985
    title: Version-bound reusable components and use boundaries
  - id: codex-exec
    resource: https://github.com/openai/codex/blob/rust-v0.154.0/codex-rs/exec/src/lib.rs
    title: Version-pinned native configuration and empty-stdin ordering
  - id: claude-structured
    resource: https://code.claude.com/docs/en/agent-sdk/structured-outputs
    title: Native structured result and error contract
x-project-knowledge:
  id: kit.decision.0064.evaluate-native-structured-review-handoff
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md
    - kind: governed-by
      target: /decisions/0018-adopt-evidence-gated-capability-evolution-for-gnostoa-self-governance.md
    - kind: references
      target: /decisions/0063-evaluate-portable-review-exchange-and-coordinator-replacement.md
---

# Evaluate native structured review handoff

## Context

The owner approved PR #234's exact candidate and explicitly instructed us to
start the proposed next experiment. Work Item #235 records that separate choice,
the integrated base, prospective paths and initial N01–N06 map. The first trial
remains complete with its narrower result and original evidence unchanged.

The next question is concrete: can native schema output be collected without
manual extraction, and can a fresh agent actually use the exchange commands to
continue from durable state without owner relay? This record is draft knowledge;
it does not approve the resulting candidate or promote a public capability.

## Decision

Reuse official Codex 0.154.0 `--output-schema` and Claude Code 2.1.267
`--json-schema`, existing Python primitives and the integrated test fixture.
Invoke unmodified tools with their existing account login. Import no SDK,
upstream source, new scheduler or subscription proxy. Existing version/use-bound
license and service assessments remain relevant; actual account entitlement and
availability are separate observations.

1. Make only a **normal, self-only experimental/test** extension: a declared
   structured-output adapter and domain schema, focused tests, and separate
   evidence/assessment. Preserve the first oracle and raw archives byte-for-byte.
   Public contracts, dependencies, policy, CI and production gates are unchanged.
2. Qualify the actual Codex invocation before dispatch with the source-justified
   empty-stdin sentinel. Distinguish configuration rejection from deliberately
   reaching the prompt check; neither is a successful model start. Validate schema
   bytes separately because native schema loading happens later. No equivalent
   no-inference Claude configuration probe is established by this Decision.
3. Freeze new independent expectations before changing the adapter. Retain
   valid-native-input failure against the old adapter, negative invalid-result
   controls, historical replay and a discriminating mutant. Missing infrastructure
   and invalid config are not behavioral RED for result consumption.
4. Consume a unique successful native structured result strictly. Missing,
   malformed or unsuccessful results remain pending with native bytes retained;
   do not salvage prose or code fences as an automatically collected review.
   Schema conformity establishes representation, not truth or review completeness.
5. Attempt at most two assignments against the same published historical PR #228
   subject: A is a source reviewer; B is a fresh successor reviewing coordinator.
   B must itself invoke the existing collection/view path and recover the original
   review plus pending work. Native tool-call evidence, not its final prose,
   establishes that consumption. B sees A's review and is not independent of it.
6. Root prepares and starts the two jobs and may collect B after termination.
   Report these retained duties; do not claim complete autonomous coordinator
   replacement. Tool permissions allow public local source reading and declared
   exchange operations only; no source or GitHub mutation occurs inside the trial.
7. Bound new setup effort to two hours and total live execution to 45 minutes,
   with one handoff, one round and no automatic assignment retries. Additional
   paid API spend remains forbidden under the owner's existing settings statement.
   Native internal retries, auxiliary models, list-price telemetry, account billing
   and UNKNOWN observations are distinct. No silent API fallback is allowed.

## Consequences

Update N01–N06 with actual outcomes, independent review and exact candidate
binding. Run applicable container checks before proposing the next draft PR.
Retain each reviewer finding/recommendation and executor disposition separately.
Publish a use/narrow/abandon result without inventing saved time. A negative live
result is a valid completion; exhausted limits do not authorize retries or scope
expansion. Future merge requires separate owner approval.

The fixture remains cooperative single-host glue, not hostile-process isolation,
protected acceptance, universal runtime portability or L10 closure. Related
#3/#10/#11/#201 retain their separate scopes and authority.
