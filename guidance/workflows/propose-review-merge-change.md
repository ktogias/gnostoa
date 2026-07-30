---
type: Workflow
title: Propose, review and merge a change
description: Carry one bounded change from problem statement to protected integration with proportionate evidence.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-07-29T00:00:00Z"
x-project-knowledge:
  id: guidance.workflow.propose-review-merge-change
  owners:
    - team:gnostoa-maintainers
  scope:
    - generic-guidance
  relations:
    - kind: operationalizes
      target: /patterns/protected-short-lived-change-flow.md
    - kind: depends-on
      target: /reference/change-classification-and-approval.md
    - kind: governed-by
      target: /guardrails/non-negotiable.md
    - kind: depends-on
      target: /workflows/develop-verification-first.md
---

# Propose, review and merge a change

## Outcome

A small change is integrated through a protected branch with enough linked
problem, decision, verification and approval evidence for a future developer or
agent to reconstruct why it happened.

## Preconditions

- The default integration branch is protected.
- The repository change-control policy resolves and validates.
- The accountable source or knowledge owner is identifiable.
- The task has a bounded desired outcome.

## Procedure

1. Classify the change as `mechanical`, `normal`, `normative`, `critical` or
   `emergency`.
2. Create or link a Work Item when the class requires it. Otherwise ensure the
   Change Request can stand alone as the problem record.
3. For a normative or critical change, record or link the governing Decision
   before requesting final approval.
4. Create a short-lived branch from the current integration branch.
5. Open a draft Change Request early when feedback or agent/human handoff is
   useful.
6. Follow the
   [verification-first workflow](develop-verification-first.md): record expected
   behavior, establish required failing evidence or characterization, then make
   the smallest coherent implementation, contract, test and knowledge update.
7. Complete the Change Request's class, motivation, scope, impact, evidence,
   rollback and linked
   artifacts. Reclassify upward if scope expands.
8. Run required validation, including the knowledge profile, bundle, policy
   coverage, change-control policy, CI policy and declared project suites where
   applicable.
9. Request the required human and CODEOWNER approvals. The author and its
   delegated agents do not count as independent approval.
10. Resolve or explicitly defer every review conversation through a linked Work
    Item.
11. Merge only when protection rules, the latest merge-candidate required
    checks and approvals pass.
    Delete the topic branch and regenerate derived projections after canonical
    integration.

## Verification

- The Change Request records its class and verification evidence.
- Expected behavior and required pre-change evidence precede implementation or
  carry a permitted explicit exception.
- Required Work Items and Decisions are linked, not duplicated.
- No author or agent self-approval satisfies an independent-human gate.
- The integrated revision passed required checks.
- Canonical artifacts remain synchronized and derived artifacts reproducible.
- The branch did not become a parallel long-lived source of truth.

## Recovery

Revert through a new Change Request when an integrated change is incorrect.
For an emergency, limit the bypass to the affected incident, record the
authorized human and compensating controls, and create the Work Item and
follow-up review immediately after service restoration. A repository with no
baseline commit or remote may record one explicit bootstrap Decision; protection
becomes mandatory immediately after the baseline is published.
