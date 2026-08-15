---
type: Workflow
title: Daily knowledge change loop
description: Keep code, executable contracts and reviewed knowledge synchronized through one change workflow.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-07-29T00:00:00Z"
x-project-knowledge:
  id: guidance.workflow.daily-change-loop
  owners:
    - team:gnostoa-maintainers
  scope:
    - generic-guidance
  relations:
    - kind: governed-by
      target: /guardrails/non-negotiable.md
    - kind: depends-on
      target: /practices/source-authority-and-lifecycle.md
    - kind: operationalizes
      target: /practices/established-patterns.md
    - kind: depends-on
      target: /workflows/propose-review-merge-change.md
    - kind: depends-on
      target: /workflows/configure-continuous-integration.md
---

# Daily knowledge change loop

## Outcome

Every significant project change leaves implementation, executable contracts,
decisions and navigational knowledge mutually traceable.

## Preconditions

- The project bundle and applicable profile validate.
- The task has a concept seed or bounded search scope.
- Relevant source owners are known.

## Procedure

1. Classify the change and establish its Change Request plus any additional
   records required through the
   [change workflow](propose-review-merge-change.md).
2. Start from the root index or a task-specific context pack.
3. Open only the relevant concepts.
4. Follow concept links to native code, schemas, tests and decisions.
5. Define expected behavior and proportionate evidence through the
   [verification-first workflow](develop-verification-first.md).
6. Make the source or implementation change.
7. Update affected contracts, decisions and knowledge concepts in the same
   Change Request.
8. Keep generated changes as draft until reviewed.
9. Mark replaced concepts `deprecated` and link their replacements; do not erase
   rationale.
10. Run profile, bundle, link, change-control, CI-policy and policy-coverage
    checks plus the applicable project verification suites.
11. For community contributions, obtain review from the accountable
    knowledge/source owner. For self-authored changes, inspect the final
    semantic diff and satisfy any stricter specialized gates.
12. Regenerate derived sites, search indexes, graphs and context packs after
    canonical changes merge.

## Verification

- Authoritative CI passes on the latest candidate using pinned profile,
  workflow and runtime versions.
- Stable changes contain human verification.
- No native schema is duplicated into prose.
- Derived artifacts can be deleted and rebuilt.
- A future reader can identify why the change was made and which source proves
  the result.

## Recovery

If code and knowledge disagree, do not guess which is authoritative. Revert the
incorrect change or record an explicit contradiction/open question and involve
the accountable owner.
