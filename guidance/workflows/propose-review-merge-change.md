---
type: Workflow
title: Propose, review and merge a change
description: Carry one bounded change to protected integration with a lightweight trace and proportionate evidence.
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

A small change is integrated through a protected branch with enough rationale,
diff and verification evidence for a future developer or agent to reconstruct
why it happened.

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
3. Record or link a Decision only when policy requires it or the rationale must
   remain discoverable independently of the Change Request.
4. Create a short-lived branch from the current integration branch.
5. Open a draft Change Request early when feedback or agent/human handoff is
   useful.
6. Follow the
   [proportionate verification workflow](develop-verification-first.md): state expected
   behavior, make the smallest coherent implementation, and establish
   proportionate evidence before merge. Prefer failing or characterization
   evidence first when it materially reduces risk.
7. Complete the Change Request's class, motivation, scope, impact, evidence,
   rollback and linked
   artifacts. Reclassify upward if scope expands.
8. Run required validation, including the knowledge profile, bundle, policy
   coverage, change-control policy, CI policy and declared project suites where
   applicable.
9. Inspect the final diff and semantic impact. For a community contribution,
   obtain review from an accountable maintainer. Obtain independent human or
   CODEOWNER approvals only when the project specialization requires them;
   agents do not satisfy such a gate.
10. Resolve or explicitly defer every review conversation through a linked Work
    Item.
11. Merge when protection rules and the latest merge-candidate required checks
    pass, review conversations are resolved and any specialized approval gates
    are satisfied. Delete the topic branch and regenerate derived projections
    after canonical integration.

## Verification

- The Change Request records its class and verification evidence.
- Expected behavior and proportionate evidence are present before integration.
- Required Work Items and Decisions are linked, not duplicated.
- No agent or author is counted as independent approval when a specialization
  requires a different human reviewer.
- The integrated revision passed required checks.
- Canonical artifacts remain synchronized and derived artifacts reproducible.
- The branch did not become a parallel long-lived source of truth.

## Recovery

Revert through a new Change Request when an integrated change is incorrect.
For an emergency, limit the bypass to the affected incident, record the
accountable human and compensating controls, and create the Work Item and
follow-up review immediately after service restoration. A repository with no
baseline commit or remote may record one explicit bootstrap Decision; protection
becomes mandatory immediately after the baseline is published.
