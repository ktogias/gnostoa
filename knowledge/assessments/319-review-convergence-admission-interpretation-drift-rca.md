---
type: Source
title: PR 319 review-convergence admission interpretation-drift incident RCA
description: Root-cause analysis of repeated unnecessary owner-admission gates during PR 319 review convergence, with bounded prevention and mitigation findings.
status: draft
generated:
  by: openai/gpt-5.6-sol
  at: "2026-09-25T15:16:00Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/15
    title: Deterministic workflow and VF0 work item
  - id: pull-request
    resource: https://github.com/ktogias/gnostoa/pull/319
    title: VF0 implementation candidate
  - id: incident-capture
    resource: https://github.com/ktogias/gnostoa/pull/319#issuecomment-5834877196
    title: Incident capture
  - id: explicit-admission-requirement
    resource: ../requirements/retrospective-findings-require-explicit-admission.md
    title: Require explicit admission for retrospective findings
  - id: finding-admission-integration
    resource: https://github.com/ktogias/gnostoa/commit/ce283fb2bbacf3dba8b3f70179e16c75a104ebcd
    title: Finding-admission integration, 2026-08-29
  - id: pre-incident-agents-state
    resource: https://github.com/ktogias/gnostoa/commit/074bd0499395986021b4c320ee9d23ec67859186
    title: AGENTS state before the September 24 recovery merge
  - id: september-24-agents-state
    resource: https://github.com/ktogias/gnostoa/commit/63fb3e7bf7a929c755250e6112f5a43a2b3db5c7
    title: September 24 recovery and verification-first safeguards
x-project-knowledge:
  id: kit.assessment.319-review-convergence-admission-interpretation-drift-rca
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0053-require-lightweight-work-item-micro-retrospection.md
    - kind: references
      target: /requirements/retrospective-findings-require-explicit-admission.md
    - kind: references
      target: /decisions/0061-retain-individual-agent-review-dispositions.md
    - kind: references
      target: /runbooks/invoke-external-reviewers.md
    - kind: references
      target: /failure-modes/verification-first-chronology-bypass-during-recovery.md
---

# PR 319 review-convergence admission interpretation-drift incident RCA

## Executive conclusion

PR #319 exposed a **process interpretation failure**, not a newly introduced
repository rule. The repository record did not contain a blanket #15 / D0092
implementation admission: the one-time D0090 bootstrap-preparation approval was
bound to its frozen parent, file set, patch, tools and runtime, and later findings
remained subject to their effective bounded authority. In the active task the
owner also explicitly directed autonomous continuation through review convergence
within the currently authorized scope. The executor nevertheless began treating
each new analyzer or reviewer finding as necessarily outside whatever effective
admission or continuation authority covered the candidate. That interrupted the
previous autonomous review-convergence loop and repeatedly returned ordinary
in-scope remediation to the owner.

Historical read-back falsifies the hypothesis that governance changed on
September 24 or 25:

- the explicit-admission Requirement entered protected history on **2026-08-29**
  at `ce283fb...` and has not changed since;
- the `AGENTS.md` stop rule for **unadmitted findings** was already present in the
  September 23 state `074bd049...`;
- the September 24 integration `63fb3e7...` added recovery and verification-first
  safeguards, not a new per-finding approval rule.

The proximate cause was therefore **interpretation drift**: admission was keyed
to the novelty of an observation instead of to whether the proposed repair
expanded the current effective outcome, scope, authority or effect boundary.

The incident failed safe with respect to authority: no unauthorized merge,
activation, producer admission, policy weakening or source mutation occurred at
the stop points. It still failed operationally because it consumed owner
attention, interrupted autonomy and made review convergence potentially
non-terminating.

## Expected versus observed workflow

The established operating pattern was:

> admitted bounded slice → implement → CI/review → repair still-valid in-scope
> findings → rerun CI/review → repeat until convergence → return to the owner at
> the next real human authority/effect gate.

A separate owner decision remains appropriate when a finding changes what is
being built or what effects are permitted: a new capability or independent
outcome, another Work Item/Decision, broader public/provider semantics, policy or
authority changes, a new external effect, activation, Ready/merge or another
protected transition.

During PR #319 the executor instead requested new admissions for:

1. analyzer findings on the VF0 candidate while the task carried bounded review-convergence authority;
2. Codex finding `4105633211`, a restrictive-`umask` edge case in that same
   implementation;
3. Codex finding `4105815623`, a documentation-only correction to current
   focused-test totals.

The third case made the drift especially clear: no runtime, authority or effect
boundary was expanding, yet the same stop rule was applied again.

Provider-visible checkpoints include `5832272789`, `5834294462`, `5834607847`
and the incident capture `5834877196`.

## Prior-art and reuse

This RCA reuses existing Gnostoa incident-analysis patterns. The provider-label
RCA supplies the evidence/claim-boundary model; the verification-first recovery
failure mode supplies the distinction between an immediate operating correction
and later separately admitted normative/tooling changes. The existing
review-assurance retrospective already treats reviewer findings as inputs to
iterative candidate convergence. No new schema, dependency, bot or workflow
engine is selected here.

## Root-cause analysis

### Immediate cause: admission attached to the finding rather than the boundary

A finding is an observation/evidence unit. Admission authorizes a bounded desired
outcome and effect envelope. Multiple findings can be consumed while converging
one effective admission envelope when that envelope actually covers their repairs.
Treating each finding as a new admission unit regardless of that boundary converts
normal iterative review into a sequence of owner approvals.

### Contributing cause 1: asymmetric wording

The Requirement correctly says that an **unadmitted finding** must not silently
become implementation authority, but it does not explicitly state the converse:
a finding discovered during implementation/review does not require a new admission
when the current effective admission or explicit task authority already covers that
exact repair, it is necessary to satisfy the existing acceptance criteria, and it
does not broaden scope, authority or effects.

### Contributing cause 2: no retained active admission/effect envelope

The execution state did not carry a compact marker such as:

```text
work_item = #15
Decision = D0092
phase = REVIEW_CONVERGENCE
allowed = candidate/review remediation inside the admitted VF0 outcome
forbidden = Ready/merge, producer admission, VF0 activation, policy weakening
```

Without that retained envelope, each new review event was reclassified in
isolation.

### Contributing cause 3: recovery complexity amplified conservative rereading

PR #319 involved interrupted sessions, parallel writers, exact-source recovery,
D0090 preparation, analyzer read-back and temporary support workflows. Repeated
fail-closed rereading was appropriate for preventing unauthorized effects, but
the active admission envelope and the owner's explicit autonomous-continuation
direction were not reconciled with the stop rule.

### Contributing cause 4: safe-stop bias masked a usability failure

Each individual owner stop was locally safe. The aggregate behavior was not
assessed early enough. Repeated safe stops can still be a workflow defect when
they make an already authorized convergence loop unable to converge without
continuous human supervision.

### Contributing cause 5: no escalation decision test

Before escalating, the executor did not have to answer the concrete question:

> Would implementing this finding change the admitted desired outcome, Work
> Item/Decision, public/provider semantics, authority/effect boundary or protected
> transition?

Instead, “this is a new finding” became the effective escalation test.

## Five-whys summary

1. **Why were repeated owner approvals requested?** Each new finding was treated
   as fresh implementation admission.
2. **Why?** “Unadmitted finding” was interpreted per finding instead of relative
   to the active effective admission envelope.
3. **Why was that not rejected?** The Requirement exposes a strong STOP rule but
   no equally visible CONTINUE predicate for in-scope convergence.
4. **Why did it appear now?** Recovery/session complexity increased conservative
   rereading and the executor lost the previously established convergence state.
5. **Why did controls not catch it?** Existing controls strongly detect excess
   autonomy, but there was no symmetric control for unnecessary humanization of
   an already authorized loop.

## Impact

Confirmed effects:

- repeated unnecessary owner interruptions during one PR review loop;
- extra provider comments and admission handoffs;
- slower convergence and duplicated orchestration work;
- loss of the intended “continue autonomously until real human intervention is
  required” operating mode;
- risk of recursive gating whenever a new review cycle produces another finding.

Effects that did **not** occur:

- no unauthorized merge/Ready transition;
- no producer admission or VF0 activation;
- no policy/threshold weakening;
- no finding was silently dismissed;
- no source mutation occurred after a stop without the requested owner response.

The authority boundary therefore failed **safe**, but safety alone is not proof
that the workflow behaved correctly.

## Controls that worked

- explicit admission prevented silent scope expansion;
- fresh provider/head read-back prevented destructive parallel-writer effects;
- exact-parent D0090 preparation preserved candidate integrity;
- owner semantic oversight detected the behavior drift;
- Git history falsified the mistaken “a rule changed yesterday” hypothesis.

## Controls that were insufficient

- finding novelty was not distinguished from scope/effect novelty;
- `AGENTS.md` exposes STOP more visibly than CONTINUE for review convergence;
- no active-slice envelope survived interrupted/parallel execution;
- no escalation checklist required a concrete crossed boundary;
- progress reporting did not flag repeated owner gates as a possible process
  regression.

## Immediate operating mitigation

Until durable wording is separately selected and admitted, use this task-local
triage only after fresh read-back establishes the effective admission or explicit
task authority covering both the current candidate and the proposed repair:

| Classification | Meaning | Action |
| --- | --- | --- |
| `IN_SCOPE_REMEDIATION` | Required to meet existing acceptance criteria within the effective admission/task authority exact scope; no outcome/effect expansion | Repair autonomously inside that scope, re-prepare, rerun checks/reviews and continue convergence |
| `SCOPE_EXPANSION` | New capability/outcome/Work Item/Decision or materially broader semantics | Stop and request admission |
| `AUTHORITY_OR_EFFECT_CHANGE` | Policy/threshold/provider effect/activation/Ready/merge or other protected transition | Stop at the applicable human gate |
| `UNCERTAIN_BOUNDARY` | Evidence is insufficient to classify after fresh provider/source read-back | Stop with the specific uncertainty, not a generic per-finding approval request |

Before escalating, state **which boundary would be crossed**. “A reviewer found
something new” is not itself a boundary.

For `IN_SCOPE_REMEDIATION`, continue the normal loop: verify the finding against
the exact current head, preserve applicable pre-change evidence, make the
smallest repair, run ordinary exact-parent preparation, publish guardedly,
re-read fresh reviewers/analyzers, and repeat until convergence.

## Findings and prevention options

### F1 — A finding is not the unit of implementation admission

Admission should bind the selected outcome, scope and effect envelope. Multiple
review/analyzer findings may be consumed inside one effective envelope only while
that envelope or explicit task authority covers each proposed repair.

### F2 — Review convergence is part of implementation

Still-valid findings necessary to make the selected candidate satisfy its
existing criteria normally belong to the same implementation slice.

### F3 — Boundary expansion, not reviewer identity, triggers new admission

Codex, Claude, CodeQL, Sonar, Codacy, Gitar, a human reviewer or self-review are
all evidence sources. The source of the finding does not determine admission.

### F4 — Over-escalation is a real failure mode

A process can preserve authority perfectly while still regress in usability and
autonomy. Unnecessary human gates should be observable, not normalized as
harmless caution.

### F5 — Retain the admission/effect envelope across session recovery

Interrupted sessions and parallel-agent recovery should restore Work Item,
Decision, allowed outcome/effects, prohibited effects and current phase before
classifying new findings.

### F6 — Durable governance needs both STOP and CONTINUE predicates

Candidate future changes, **not admitted by this RCA**, are:

1. clarify the explicit-admission Requirement so in-scope review remediation is
   explicitly covered by the existing admission;
2. place a concise continuation rule beside the `AGENTS.md` stop rule;
3. add the four-way review-finding triage to the bounded delivery runbook;
4. add governance regression scenarios for both under-escalation and
   over-escalation;
5. only if later evidence justifies it, consider a machine-readable active
   admission envelope or escalation telemetry.

Do not add tooling merely because this single incident occurred.

## Success criteria for a future mitigation

A fresh agent should be able to:

- autonomously repair multiple independent reviewer findings that remain inside
  one effective bounded admission/task-authority envelope and reach review
  convergence without owner round trips; and
- stop reliably when a finding would expand scope, change authority/effects or
  cross a protected transition.

Success is **not** “fewer owner prompts” in isolation. Removing legitimate human
gates would be a regression. The target is accurate placement of human authority.

## Authority boundary

This RCA records the incident, causal analysis, immediate task-local triage and
candidate prevention options. It does not amend the explicit-admission
Requirement, `AGENTS.md`, Decision 0053, policy files, merge authority or the
activation model. Durable normative or executable mitigation remains subject to
the ordinary selection, admission, verification and review route.
