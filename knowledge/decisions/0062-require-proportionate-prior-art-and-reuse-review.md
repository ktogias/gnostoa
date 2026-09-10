---
type: Decision
title: Require proportionate prior-art and reuse review before self-changes
description: Reuse one current bounded alternatives and licensing assessment across Gnostoa-self change transitions before authoring new mechanisms.
status: draft
generated:
  by: agent:codex
  at: "2026-09-10T14:59:43Z"
sources:
  - id: prior-art-work-item
    resource: https://github.com/ktogias/gnostoa/issues/231
    title: Require proportionate prior-art and reuse review before self-changes
  - id: madr
    resource: https://github.com/adr/madr/blob/2475fe1973f66a12aaf58a91d8fa7b42c0f5ea3d/template/adr-template.md
    title: MADR 4.0.0 template at its inspected commit
  - id: madr-license
    resource: https://github.com/adr/madr/blob/2475fe1973f66a12aaf58a91d8fa7b42c0f5ea3d/LICENSE
    title: MADR 4.0.0 declared license
  - id: zuul-gating
    resource: https://zuul-ci.org/docs/zuul/latest/gating.html
    title: Zuul project gating
x-project-knowledge:
  id: kit.decision.0062.require-proportionate-prior-art-and-reuse-review
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md
    - kind: governed-by
      target: /decisions/0018-adopt-evidence-gated-capability-evolution-for-gnostoa-self-governance.md
    - kind: governs
      target: /runbooks/deliver-bounded-self-hosted-slice.md
    - kind: references
      target: /lifecycles/evidence-gated-capability-evolution.md
    - kind: references
      target: /requirements/retrospective-findings-require-explicit-admission.md
---

# Require proportionate prior-art and reuse review before self-changes

## Context

The owner requested research into reusable, compatibly licensed projects before
Decisions, Issues, PRs and implementation, with established practices, patterns
and antipatterns considered when no suitable complete project is found. The
owner then accepted a proportionate checkpoint that reuses applicable research
across unchanged steps and instructed the agent to proceed. Work Item #231
captures that instruction and the admitted surface before implementation. This
agent-authored record does not approve the resulting candidate or promote it to
stable knowledge.

At source `bd961fa3d3ac7ab2c5588f047291e2ebd7ae92b4`, the lifecycle already
preferred existing deterministic mechanisms and the delivery runbook already
owned bounded research. Neither explicitly required an external-project and
license review before each named change transition. The router and coverage
manifest also lacked that explicit checkpoint. These unmet non-executable
criteria were recorded before editing; they are not software RED evidence.

## Considered options and reuse disposition

Research was reviewed on 2026-09-10 for this checkpoint, before creating #231.

- **Extend the existing delivery runbook and lifecycle: selected.** They already
  own change ordering and research. Keep one checkpoint and link it from the
  router and lifecycle instead of constructing another process engine.
- **Reuse MADR 4.0.0's considered-options pattern as a reference.** The inspected
  commit `2475fe1973f66a12aaf58a91d8fa7b42c0f5ea3d` declares
  `MIT OR CC0-1.0`; this change consults its structure without importing
  template text, a dependency or a new Decision schema. Existing Gnostoa
  frontmatter and human-verification semantics remain sufficient.
- **Inspect existing implementations for concrete mechanism choices.** Zuul's
  composed-change gating documentation, read at the linked unversioned URL on
  2026-09-10, is a useful research input to #136. This checkpoint
  does not select, install or establish license compatibility for a Zuul
  deployment. Each actual reuse needs its own version/use/obligation assessment.
- **Repeat a full external search at every artifact: rejected.** Unchanged scope
  can reuse the same bounded record; changed requirements, material environment,
  candidate or licensing facts require revalidation of affected conclusions.
- **Add a research service, generic schema or automatic acceptance gate:
  rejected for this slice.** The required result is an explicit, reviewable
  decision input. Record presence cannot prove search or semantic completeness.

The search is bounded. It does not establish that no other suitable projects
exist. Existing #171 owns outcome/repository fit and #176 owns known-procedure
recall; neither is implemented or superseded here. #11 retains the separate
Decision-authority inventory and #136 retains integration semantics.

## Decision

1. Require the delivery runbook's **Prior-art and reuse checkpoint** before
   creating or materially revising a Gnostoa-self Issue, Decision or PR, and
   before new code or implementation. Route it from `AGENTS.md` and the existing
   lifecycle. Reuse remains the first design option, with custom work justified
   by the observed residual need.
2. Retain one compact, linked assessment with the question/scope, inspected
   alternatives and sources, version and intended use, license/provenance
   obligations, fit and limitations, disposition and remaining uncertainty.
   No fixed source count or separate report is required.
3. Reuse a still-applicable assessment at subsequent transitions. Revalidate
   affected conclusions when their inputs change. An unavailable search or
   unresolved material compatibility question stays explicit and cannot be
   rewritten as clearance to acquire, copy, distribute or depend on the material.
4. When no suitable complete implementation is found in the bounded search,
   inspect relevant practices, patterns and antipatterns before designing the
   remaining custom work. External reputation or a license label alone does not
   establish fit, completeness or effectiveness at the actual accepting boundary.
5. Declare **review** enforcement in the kit-only guardrail manifest. Preserve
   the existing classification, admission, emergency, exact-candidate review and
   effect-authority rules. Research and approval evidence remain different facts.
6. Keep this normative change self-only: the existing runbook, lifecycle, router,
   guardrail manifest and this Decision/index. Add no executable mechanism,
   supported CLI, public/adopter contract, dependency or agent/provider binding.

## Consequences

The alternatives and reasons for custom work become discoverable before work
starts. Research already performed for a current question can serve its Issue,
Decision, PR and implementation without being recopied or repeated. License
inventory remains separate from compatibility of the intended use, as already
specified in `LICENSING.md`.

The checkpoint adds review effort. Revisit it if repeated searches, paperwork or
false blocking outweigh the avoided duplication; retain observed negative
results rather than adding automation to rescue the practice. Structural and
bundle checks can establish routing and record validity, not compliance by
future agents or a complete search of all available projects.

Human semantic review of the exact candidate and separate merge authorization
remain required by the delivery route. No existing Decision is promoted to
`stable`, no protected supervisor or integration queue is activated, and the
PR #229 guideline remains a separate change and review subject.
