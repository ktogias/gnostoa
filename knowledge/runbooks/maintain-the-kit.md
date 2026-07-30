---
type: Runbook
title: Maintain the toolkit
description: Change procedure for the generic toolkit and its public inheritance surface.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-07-29T00:00:00Z"
x-project-knowledge:
  id: kit.runbook.maintain
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /contracts/public-inheritance-surface.md
    - kind: verifies
      target: /requirements/prevent-policy-drift.md
    - kind: verifies
      target: /requirements/verification-precedes-implementation.md
    - kind: verifies
      target: /requirements/centralized-ci-verifies-integration-candidates.md
---

# Maintain the toolkit

## Preconditions

- Classify the change as generic policy, reusable guidance, toolkit-internal
  knowledge or an anonymous example.
- Identify affected consumers and whether the public contract changes.
- Classify the change using `policy/change-control.yaml` and create the required
  Work Item and Decision evidence.
- Read the [public inheritance contract](../contracts/public-inheritance-surface.md)
  and the relevant route in [`guidance/index.md`](../../guidance/index.md).
- State expected observable behavior and the pre-change evidence required by
  the [verification-first workflow](../../guidance/workflows/develop-verification-first.md).

## Procedure

1. Create a short-lived branch and Change Request through the
   [generic change workflow](../../guidance/workflows/propose-review-merge-change.md).
2. For a bug, run a reproducer before the fix. For a behavior-preserving
   refactor, establish green characterization tests before editing structure.
3. For changes to `tools/`, `schemas/`, `core/` or `policy/`, add and run the
   focused failing behavioral or conformance test before implementation.
4. Change the canonical artifact in its owning surface.
5. Update rationale, guidance and the guardrail coverage manifest when the
   normative behavior changes.
6. Use structural validation and human semantic verification for
   non-executable knowledge; do not add ceremonial tests for prose.
7. Keep real project vocabulary in a separate specialization repository.
8. Record migrations and version impact for public-surface changes.
9. Run `knowledge check-change-policy`; do not lower inherited controls.
10. Run `knowledge check-ci-policy` with `policy/verification.yaml`; keep hooks
    advisory and provider adapters synchronized with generic event semantics.
11. For runtime or CI changes, build the runtime image and run the complete self-check
   inside it.
12. Exercise `./ci/verify fast`, regression and applicable conditional suites.
13. Obtain the approvals required by the self-policy. An author or agent does not
   approve its own change.

## Verification

Run the unit tests, validate anonymous examples, validate both the reusable
guidance and self-knowledge bundles, and check guardrail coverage. Review the
diff for real project names and accidental duplicated authority.

Runtime, distribution and CI changes additionally require a pinned-base check,
non-root image check, container smoke test, CI-policy validation and inspection
of provider event/security mappings.

Until the first baseline commit and remote exist, follow the bootstrap exception
recorded in
[`Decision 0006`](../decisions/0006-provider-neutral-change-governance.md).
After publication, absence of repository protection is a failed verification.

## Recovery

If a change weakens compatibility or leaks project-specific knowledge, keep the
last compatible public version, move the leaked content to its specialization
and publish a corrected version with migration guidance.
If emergency controls are used, restore protection immediately and require the
Work Item and independent human follow-up review defined by the policy.
