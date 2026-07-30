---
type: Workflow
title: Develop with verification first
description: Move one bounded change from observable intent through failing evidence to a maintainable verified result.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-07-29T00:00:00Z"
x-project-knowledge:
  id: guidance.workflow.develop-verification-first
  owners:
    - team:gnostoa-maintainers
  scope:
    - generic-guidance
  relations:
    - kind: operationalizes
      target: /patterns/verification-first-development.md
    - kind: depends-on
      target: /reference/testing-and-verification-strategy.md
    - kind: governed-by
      target: /guardrails/non-negotiable.md
---

# Develop with verification first

## Outcome

The change has an observable specification, pre-change evidence, the smallest
coherent implementation and a maintainable verification portfolio.

## Preconditions

- The change class and accountable owner are known.
- Expected behavior or the invariant to preserve can be stated.
- The authoritative executable or non-executable artifact is identified.
- The permitted verification requirements resolve from the inherited policy.

## Procedure

1. Write expected behavior, boundaries, failure semantics and explicit
   non-goals before implementation.
2. Select the smallest evidence level that can distinguish the intended result
   from a false positive.
3. Establish the pre-change state:
   - **Red** for new executable behavior, conformance or a reproduced defect;
   - a green characterization baseline for behavior-preserving refactoring;
   - an unmet structural criterion plus planned human review for
     non-executable knowledge.
4. Confirm the evidence fails or characterizes behavior for the intended
   reason. A test that passes before new behavior exists needs justification.
5. Implement the smallest coherent change needed to reach **Green**.
6. Refactor implementation and tests while focused evidence stays green.
7. Run fast focused checks first, then affected contract, integration, bundle,
   documentation, runtime and smoke checks.
8. Record exact commands, results and human semantic evidence in the Change
   Request. Do not use coverage alone as acceptance.
9. Review whether tests assert observable behavior, are deterministic, and
   would fail when behavior is broken.
10. Merge only after the required evidence and broader CI remain green.

Run the fast suite locally when useful, but treat centralized candidate checks
as authoritative. Map broader evidence through the inherited CI policy rather
than embedding provider events in test commands.

For an exploratory spike, record the question and time box. Discard it or add
normal verification before supported integration. For an emergency, restore
safety first and add the required reproducer and regression evidence in the
audited follow-up.

## Verification

- Expected behavior predates implementation or has a permitted recorded
  exception.
- Applicable Red evidence was observed and is linked.
- A refactor has characterization evidence and no intended behavior change.
- Non-executable knowledge has structural and accountable human verification.
- Required tests are deterministic, relevant and non-flaky.
- Focused feedback is available within the project target.

## Recovery

If a new test merely mirrors implementation, restate behavior from the consumer
boundary and replace it. If evidence is flaky, block or quarantine it through a
reviewed, expiring exception and create a repair Work Item. If pre-change
evidence cannot be produced, reclassify the change, explain why and obtain the
required reviewer before implementation continues.
