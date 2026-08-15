---
type: Workflow
title: Develop with proportionate verification
description: Move one bounded change from observable intent to a maintainable result verified before integration.
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

# Develop with proportionate verification

## Outcome

The change has an observable specification, the smallest coherent
implementation and a maintainable verification portfolio before integration.

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
3. When useful or required by a specialization, establish the pre-change state:
   - **Red** for new executable behavior, conformance or a reproduced defect;
   - a green characterization baseline for behavior-preserving refactoring;
   - an unmet structural criterion plus planned human review for
     non-executable knowledge.
4. When using pre-change evidence, confirm it fails or characterizes behavior
   for the intended reason.
5. Implement the smallest coherent change needed to satisfy the expected
   behavior.
6. Refactor implementation and tests while focused evidence stays green.
7. Run fast focused checks first, then affected contract, integration, bundle,
   documentation, runtime and smoke checks.
8. Record exact commands, results and human semantic evidence needed to
   understand acceptance in the Change Request. Do not use coverage alone.
9. Review whether tests assert observable behavior, are deterministic, and
   would fail when behavior is broken.
10. Merge only after the required evidence and broader CI remain green.

Run the fast suite locally when useful, but treat centralized candidate checks
as authoritative. Map broader evidence through the inherited CI policy rather
than embedding provider events in test commands.

For an exploratory spike, record the question and time box. Discard it or add
normal verification before supported integration. For an emergency, restore
safety first and add the required regression evidence in the
audited follow-up.

## Verification

- Expected behavior and final evidence are present before integration.
- Applicable Red or characterization evidence is linked when used or required.
- A refactor has characterization evidence and no intended behavior change.
- Non-executable knowledge has structural and accountable human verification.
- Required tests are deterministic, relevant and non-flaky.
- Focused feedback is available within the project target.

## Recovery

If a new test merely mirrors implementation, restate behavior from the consumer
boundary and replace it. If evidence is flaky, block or quarantine it through a
bounded, expiring exception and create a repair Work Item. If required
pre-change evidence cannot be produced, follow the stricter specialization's
exception path or change that specialization through its normal governance
process.
