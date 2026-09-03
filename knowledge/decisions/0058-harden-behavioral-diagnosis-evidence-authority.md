---
type: Decision
title: Harden behavioral diagnosis evidence authority and hypothesis reconciliation
description: Preserve the auditability benefit of Gnostoa's bounded behavior map while preventing task-semantic assumptions from being closed by evidence derived from those same assumptions.
status: draft
generated:
  by: chatgpt/gpt-5.6-sol
  at: "2026-09-03T17:57:00Z"
sources:
  - id: diagnosis-evidence-authority-work-item
    resource: https://github.com/ktogias/gnostoa/issues/182
    title: Harden behavioral diagnosis evidence authority and hypothesis reconciliation
  - id: phase-c-root-cause-analysis
    resource: https://github.com/ktogias/gnostoa/issues/179#issuecomment-5513492802
    title: Complete Phase-C retrospective and root-cause analysis
  - id: phase-c-evidence-index
    resource: https://github.com/ktogias/gnostoa/issues/179#issuecomment-5513616973
    title: Transcript evidence index — bounded public projection
  - id: behavioral-traceability-requirement
    resource: ../requirements/bounded-behavioral-traceability.md
    title: Require bounded behavioral traceability for applicable Gnostoa-self work
x-project-knowledge:
  id: kit.decision.0058.harden-behavioral-diagnosis-evidence-authority
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0018-adopt-evidence-gated-capability-evolution-for-gnostoa-self-governance.md
    - kind: governed-by
      target: /decisions/0056-run-a-bounded-behavioral-traceability-review-experiment.md
    - kind: references
      target: /requirements/bounded-behavioral-traceability.md
---

# Harden behavioral diagnosis evidence authority and hypothesis reconciliation

## Context

Decision 0056 and Work Item #170 introduced a compact Gnostoa-self behavior map
that made task obligations, implementation paths, evidence and reviewer
dispositions auditable. The first Phase-C use in #179 preserved that benefit but
exposed a narrower semantic failure.

The treatment arm explicitly recorded that the exact reproduced fixture was
unknown and represented its selected own-address-in-cc interpretation as an
`OPEN` assumption. It then authored a regression fixture that instantiated that
same interpretation. The fixture showed that the selected scenario was a real
bug and that the candidate repaired it, but it could not independently establish
that the selected scenario was the case described by the task. The map nevertheless
advanced the interpretation to `CONFIRMED`.

The same run exposed related forms of diagnostic circularity. A behavior-
classifying predicate on the suspected defect path was used as the definition of
correctness, materially plausible competing hypotheses were not retained through
resolution, and a different reviewer model inspected the candidate through the
executor's diagnosis and evidence path. Model diversity reduced model correlation
but did not provide independent task-semantic evidence.

The strongest result supported by #179 remains that the #170 checkpoint improved
auditability of the selected interpretation and its evidence path. One paired
trial does not establish that the checkpoint improves or harms correctness.

## Alternatives considered

| Alternative | Material benefit | Material limitation | Disposition |
| --- | --- | --- | --- |
| Keep the #170 contract unchanged and rely on reviewer judgment | No added ceremony or fields | #179 demonstrates that a structurally complete map can close around assumption-derived evidence without exposing the circularity | Rejected |
| Add only a prose sentence saying assumptions need independent evidence | Smallest textual change | Does not require the map to identify evidence authority/dependency or distinguish what an executor-authored fixture actually proves | Rejected as insufficient |
| Add bounded semantic typing and non-circular closure to the existing Gnostoa-self behavior map | Makes the demonstrated failure reviewable while preserving the existing small self-only surface | Adds a small amount of diagnostic bookkeeping for applicable ambiguous/high-risk tasks | Selected |
| Add a generic schema, validator, CLI or workflow engine now | Could mechanically validate richer structures | Exceeds the evidence and would confuse structural validation with semantic diagnosis; #179 supports no adopter-wide contract | Deferred; not admitted by this Decision |
| Treat a different reviewer model as sufficient independence | Cheap decorrelation | Reviewer may still consume the same candidate-authored framing and evidence; model difference is not evidence independence | Rejected |
| Require a hidden oracle for every implementation task | Strong independent behavioral evidence when available | Oracles are not generally available and would inflate ordinary product work into experiments | Rejected as a general workflow rule |

## Decision

### A. Preserve one bounded Gnostoa-self behavior-map contract

Extend the existing `bounded-behavioral-traceability` Requirement rather than
creating a second diagnosis framework. The rule remains Gnostoa-self-only and
risk-proportional. It introduces no public schema, generic workflow engine,
provider setting or adopter guarantee.

The behavior map remains a semantic review aid. Structural completeness does not
establish correctness, semantic completeness, model independence, human approval
or owner disposition.

### B. Distinguish task obligations, hypotheses and implementation claims

For applicable ambiguous or materially correctness-sensitive work, the map must
keep these concepts separate when they exist:

- **task obligation** — the observable behavior required by the authoritative task
  or project source;
- **semantic hypothesis/assumption** — a proposed explanation or interpretation
  that may still be wrong;
- **implementation claim** — what the proposed code or test says will happen.

An implementation mechanism or test expectation cannot silently become the
meaning of the task merely because it is internally consistent.

A task-semantic hypothesis records a resolution state such as `OPEN`,
`SUPPORTED`, `REJECTED` or `CONFIRMED`, together with the evidence that justifies
that state. `CONFIRMED` is reserved for evidence whose authority and dependency
are sufficient to identify the task case, not merely a possible bug scenario.

### C. Type evidence by authority and dependency, not only execution result

Where evidence is used to resolve a task-semantic hypothesis, the map must expose
at least the distinction needed to review the #179 failure class:

- authoritative task/project evidence;
- pre-existing independent project evidence;
- executor-authored diagnostic evidence;
- executor-authored regression evidence derived from the same hypothesis;
- reviewer inference; and
- unknown/unclassified evidence.

The record also identifies when evidence was produced from, or materially depends
on, the hypothesis it is being used to resolve.

Execution state remains separate. A fixture may truthfully be `PASS` while its
semantic authority is insufficient to identify the reported case.

### D. Prohibit circular task-semantic closure

A task-semantic hypothesis must not become `CONFIRMED` solely from evidence that
was authored to instantiate that same hypothesis.

Such evidence may establish narrower propositions, including:

```text
base reproduction       the selected scenario exists on the frozen base
candidate correction    the candidate changes that selected scenario as intended
```

It does not by itself establish:

```text
task identification     the selected scenario is the case described by the task
```

Without authoritative or sufficiently independent discriminating evidence,
`task identification` remains `OPEN`/`UNKNOWN` and blocks review-ready status
when that identification is material to correctness. The executor may escalate
the unresolved question instead of inventing certainty.

### E. Retain and resolve material competing hypotheses before convenience selects the patch

When material ambiguity admits multiple plausible causes, the map retains the
material competing hypotheses known to the executor and, where feasible, one
discriminating observation or test for each. Rejected hypotheses retain the
reason and evidence that rejected them.

Implementation size, locality or convenience may influence which valid repair is
selected after the relevant cause is adequately established. Convenience alone
must not be used as evidence for rejecting the hypothesis that best explains the
task.

This rule does not require exhaustive hypothesis enumeration. It requires the
material alternatives actually identified or reasonably necessary to resolve the
recorded ambiguity to remain visible rather than disappearing without evidence.

### F. Treat behavior-classifying predicates on the questioned path as hypotheses

When a task concerns identity, classification, routing or another behavior whose
correctness is determined by an existing predicate, and that predicate is on the
suspected defect path, the map must not use the predicate itself as the unexamined
definition of correctness.

The predicate may be retained as an implementation dependency or hypothesis, but
its relevant behavior requires independent validation before it can close the
semantic question it classifies.

### G. Separate reviewer model diversity from evidence independence

For applicable high-risk or materially ambiguous behavioral work, review uses a
bounded two-pass sequence:

1. **Independent task-to-code pass.** Before consuming the executor's final
   diagnosis/map conclusions, the reviewer inspects the exact task and candidate
   and records materially plausible causes, affected paths or interpretation
   risks relevant to the acceptance question.
2. **Map reconciliation pass.** The reviewer then compares that independent view
   with the executor's hypotheses, evidence authority/dependency, rejected
   alternatives and final candidate.

A different model family or fresh context may reduce correlated reasoning but is
not represented as independent evidence. Reviewer inference remains typed as
reviewer inference.

Where a review relies on an executed-test claim, the retained evidence identifies
the command, exit status and bounded output identity when those are available and
material to the disposition. Lack of such execution evidence remains explicit.

The reviewer does not become a hidden oracle. If the task cannot be identified
from available authoritative or independent evidence, the correct result is an
explicit unresolved state or owner escalation.

### H. Verify the rule first with the #179 failure shape

Before semantic implementation, retain a sanitized focused RED derived from the
#179 failure shape. The RED must demonstrate that the current integrated contract
can represent an `OPEN` task-semantic assumption, a regression fixture derived
from that assumption and a passing candidate, yet has no contract requirement that
prevents that fixture from being used to close task identification.

GREEN is reached only when the smallest Requirement/reviewer-route change makes
that circular closure nonconforming while preserving the existing #170 blind
replay and supported auditability behavior.

No Mail-specific address, source path or implementation detail is required in the
canonical fixture.

## Consequences

- A behavior map can no longer treat `I reproduced my hypothesis` as equivalent
  to `my hypothesis identifies the task`.
- Passing executor-authored tests remain useful evidence but carry only the
  semantic authority they actually possess.
- Material competing hypotheses and evidence-based rejection remain auditable.
- A classifier suspected of causing the behavior cannot define correctness by
  circular reference.
- Reviewer model diversity remains useful decorrelation but is not mislabeled as
  evidence independence.
- The existing #170 auditability benefit and Gnostoa-self scope are preserved.
- #179 remains `INCONCLUSIVE / NO SEPARATION`; this Decision neither repairs nor
  rescores it and makes no new correctness-effect claim.
- Generic schemas, deterministic workflow mechanics, experiment replication and
  adopter/public-contract promotion remain separately owned by #15, #183 or a
  later separately admitted Work Item.
