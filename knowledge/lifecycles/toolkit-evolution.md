---
type: Lifecycle
title: Toolkit evolution
description: Evolution stages and evidence gates for the generic toolkit.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-07-29T00:00:00Z"
x-project-knowledge:
  id: kit.lifecycle.evolution
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /contracts/public-inheritance-surface.md
    - kind: governed-by
      target: /decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md
    - kind: references
      target: /runbooks/maintain-the-kit.md
---

# Toolkit evolution

The reusable foundation includes the core profile, monotonic inheritance,
schemas, validation, templates, deterministic context packs, anonymous
examples, reusable guidance, an OCI runtime, a Development Container,
provider-neutral inherited change control and CI integration.
The inherited policy also defines proportionate verification intent and evidence
requirements without selecting project test frameworks.
Provider-neutral CI policy now separates authoritative candidate gates,
project-declared verification capabilities, provider adapters and advisory
local hooks.

Further evolution is evidence-gated:

1. improve source inventory and provenance;
2. strengthen the minimum verified navigation spine;
3. test module specialization on real workflows;
4. evaluate draft generation;
5. evaluate deterministic and self-updating orientation caches;
6. evaluate temporal graph retrieval;
7. evaluate enterprise catalog projection when governance requires it.

Promotion depends on correctness, token use, repository exploration, human
review time and maintenance cost. Optional derived layers remain disposable.

## Human-agent workflow bootstrap

B1 demonstrated the need for durable task context, explicit handoffs, bounded
plans, checkpoint/resume, safe restart and guided semantic review. It did not
validate a complete workflow-platform architecture.
[Decision 0016](../decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md)
therefore keeps that full platform outside the first-publication gate and evolves
it through bounded self-hosted slices.

**Decision 0016 owns the authoritative numbered increment sequence.** It is not
restated here; read it there, so there is only one authority for it.

The operating method by which each bounded slice moves from evidence through
research, selection, admission, experiment and disposition is canonical in
[Evidence-gated capability evolution](evidence-gated-capability-evolution.md),
adopted for Gnostoa self-governance by
[Decision 0018](../decisions/0018-adopt-evidence-gated-capability-evolution-for-gnostoa-self-governance.md).

Each slice must preserve B1's material defect detection and recovery while
reducing owner work, evidence amplification and resume cost. One delivery item
and one enabling slice may be active at a time.
