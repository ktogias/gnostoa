---
type: Guardrail
title: Non-negotiable project knowledge guardrails
description: Minimum rules that protect portability, authority, inheritance and bounded context.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-07-29T00:00:00Z"
x-project-knowledge:
  id: guidance.guardrail.non-negotiable
  owners:
    - team:gnostoa-maintainers
  scope:
    - generic-guidance
  relations:
    - kind: enforced-by
      target: /patterns/policy-guidance-self-separation.md
    - kind: applies-to
      target: /workflows/daily-change-loop.md
---

# Non-negotiable project knowledge guardrails

## Risk

Without explicit gates, profiles drift, generated text becomes authoritative,
project taxonomies leak into the generic core and agents consume excessive or
irrelevant context.

## Rule

1. Parent profiles may not be silently weakened.
2. Stable concepts require human verification.
3. Concept IDs are unique and persistent.
4. Broken knowledge links fail validation.
5. Generated content begins as draft.
6. Native executable artifacts are linked, not duplicated into prose.
7. Derived sites, indexes, graphs and context packs are never canonical.
8. Dependencies are pinned to immutable versions.
9. Specializations exist only for demonstrated additional rules or vocabulary.
10. Agents load task-specific guidance and never the whole corpus by default.
11. Toolkit-internal knowledge is not inherited by adopting projects.
12. Raw legacy Markdown remains outside the bundle until it conforms.
13. Profiles and canonical knowledge paths have accountable review ownership.
14. Project and CI execution use an OCI image pinned by digest by default.
15. Runtime image and toolkit source/profile revisions match.
16. Concrete implementation and test tools live in the narrowest applicable
    project or module specialization.
17. The default integration branch is protected from direct push, force push
    and deletion.
18. Every integrated change uses a bounded branch, Change Request, required
    checks and resolved review conversations.
19. A Change Request may be the complete change record. Separate Work Items,
    Decisions and formal approvals exist only when the effective policy or
    durable context requires them.
20. Agents may author changes but may not bypass controls or satisfy a human
    approval or stable-verification gate.
21. Expected observable behavior and proportionate verification evidence exist
    before integration.
22. Test-first, defect reproduction and characterization evidence are preferred
    when they materially reduce risk and become mandatory only through the
    effective change class or a stricter specialization.
23. Required tests assert observable behavior, are deterministic, and block
    integration when flaky.
24. Coverage alone is never acceptance evidence; non-executable knowledge uses
    structural validation and accountable human verification.
25. Centralized CI is authoritative; local hooks provide advisory bounded
    feedback through the same project-owned commands.
26. The latest Change Request and merge-candidate revisions pass policy, fast,
    regression and applicable conditional evidence before integration.
27. CI dependencies are immutable, permissions are minimal, and untrusted
    changes receive no privileged secrets.
28. Delivery gates exist only for declared deployable artifacts and promote the
    exact verified CI artifact without rebuilding it between environments.
29. One bounded Execution Plan carries live state only when policy or
    continuity requires it; Work Items, Decisions, repositories and Change
    Requests retain their distinct authority.
30. Resume reconciles the plan with the repository, and unfinished work is
    handed off only from an explicit clean committed checkpoint.
31. Prompts, private reasoning, raw transcripts and exhaustive activity logs
    are not canonical project knowledge.

## Enforcement

Automatable rules are enforced by profiles, schemas, validator tests and CI.
Semantic rules use accountable ownership, optional required review and the
machine-readable
[`policy/guardrails.yaml`](../../policy/guardrails.yaml) coverage manifest.
Change-flow rules are expressed in inherited `core/change-control.yaml` policy
and validated against monotonic specializations.
CI event and suite rules are expressed in inherited
`core/continuous-integration.yaml`; project capabilities and commands are
declared in a validated verification manifest.
Agent behavior is routed by a short `AGENTS.md`, not by duplicating this entire
document into every prompt.
Execution Plans are validated and reconciled through the shared task command;
provider fields are managed projections, not independent sources of truth.

## Exceptions

An exception records scope, rationale, owner, expiry or reconsideration trigger
and compensating control in the Change Request or emergency record. Use a
Decision when an exception is durable or changes policy. An exception never
edits or disables the generic parent policy for unrelated consumers.
Emergency integration additionally requires a scoped authorized human,
compensating controls and the post-event Work Item and review defined by the
[change workflow](../workflows/propose-review-merge-change.md).
