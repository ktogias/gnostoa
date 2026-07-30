---
type: Requirement
title: Enforce reviewed change control
description: Integrated changes must carry proportionate problem, decision, verification and independent approval evidence.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-07-29T00:00:00Z"
x-project-knowledge:
  id: kit.requirement.reviewed-change-control
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0006-provider-neutral-change-governance.md
    - kind: verified-by
      target: /runbooks/maintain-the-kit.md
    - kind: implements
      target: /requirements/prevent-policy-drift.md
---

# Enforce reviewed change control

The toolkit must:

- publish a provider-neutral, machine-readable minimum change policy;
- use a stricter inherited policy for its own repository;
- reject a child policy that weakens branch protection, required checks,
  approval counts, human authority or agent restrictions;
- require a Change Request for integration and a Work Item when the change class
  requires durable problem context;
- require human semantic approval for normal, normative and critical changes;
- require expected behavior and applicable pre-change failure evidence;
- retain an explicit, audited emergency recovery path;
- keep repository-hosting adapters replaceable and outside the canonical
  provider-neutral contract.
- require the latest merge-candidate revision to pass centralized policy, fast,
  regression and applicable conditional evidence.
