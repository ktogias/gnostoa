---
type: Requirement
title: Enforce traceable change control
description: Integrated changes must carry a lightweight trace and proportionate verification, with stricter approval delegated to specializations.
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
    - kind: governed-by
      target: /decisions/0014-strengthen-gnostoa-self-governance.md
    - kind: verified-by
      target: /runbooks/maintain-the-kit.md
    - kind: implements
      target: /requirements/prevent-policy-drift.md
---

# Enforce traceable change control

The toolkit must:

- publish a provider-neutral, machine-readable minimum change policy;
- use an internal specialization requiring a Work Item, Decision and
  pre-implementation evidence chronology for normal, normative and critical
  Gnostoa changes, with emergency follow-up;
- reject a child policy that weakens branch protection, required checks,
  approval counts, human authority or agent restrictions;
- require a Change Request for integration and a Work Item when the change class
  requires durable problem context;
- support solo-maintainer self-review and maintainer review of community
  contributions without mandatory formal approval;
- require expected behavior and proportionate final evidence;
- keep Gnostoa's stricter self-policy outside the consumer inheritance surface;
- retain an explicit, audited emergency recovery path;
- keep repository-hosting adapters replaceable and outside the canonical
  provider-neutral contract;
- require the latest merge-candidate revision to pass centralized policy, fast,
  regression and applicable conditional evidence.
