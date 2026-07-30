---
type: Requirement
title: Prevent policy drift
description: Rules must remain discoverable, owned and covered by proportionate enforcement.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-07-29T00:00:00Z"
x-project-knowledge:
  id: kit.requirement.prevent-policy-drift
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /contracts/public-inheritance-surface.md
    - kind: verified-by
      target: /runbooks/maintain-the-kit.md
---

# Prevent policy drift

Each normative generic guardrail must have:

- a stable identifier and owner;
- a reusable explanation;
- an explicit enforcement mode;
- implementation and test references when it is automatable;
- review ownership when it requires human judgment.

CI must reject invalid manifests, missing references, invalid reusable or
self-knowledge bundles and weakened inherited policy.
