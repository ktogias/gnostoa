---
type: Source
title: Self-hosted delivery practice retrospective
description: Bounded retrospective over B2, source release, OCI preparation, drift reconciliation and G3, identifying the ordinary Gnostoa-self delivery rules mature enough for one canonical operational route.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-22T07:25:33Z"
sources:
  - id: delivery-practice-work-item
    resource: https://github.com/ktogias/gnostoa/issues/80
    title: Canonicalize bounded self-hosted delivery practice
x-project-knowledge:
  id: kit.assessment.self-hosted-delivery-practice-retrospective
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0036-canonicalize-bounded-self-hosted-delivery-practice.md
    - kind: references
      target: /decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md
    - kind: references
      target: /decisions/0018-adopt-evidence-gated-capability-evolution-for-gnostoa-self-governance.md
    - kind: references
      target: /lifecycles/evidence-gated-capability-evolution.md
    - kind: references
      target: /decisions/0024-separate-stable-navigation-from-volatile-state.md
    - kind: references
      target: /decisions/0035-accept-bounded-first-party-source-security-sufficiency-for-the-first-oci-candidate.md
---

# Self-hosted delivery practice retrospective

## Observation boundary

The read-only retrospective was performed at protected main
`328657b0459e8061cee1631f5e776c242ecba8e8`, Git tree
`564ca4f9bf2351e06eab34ebc96f81422d3a4c75`, with public digest
`sha256:bdda49f6953efa3816b0d88ea26ee6738911152bf38800848444072701c55cd6`.
The exact measured G3 executable subject remained
`f3b9954dd72edb5f98167cb7f607ed24eb280a05`; the later main revision was a
knowledge-only re-binding, not a silently substituted security subject.

The evidence window covered the durable B2 records, source-only release and its
canonical runbook, current-state drift reconciliation, OCI/security preparation,
and Decisions 0028–0035. Representative integrated provider records included
PRs #28, #30, #45, #47, #49, #65, #69, #75, #77 and #79. Historical transcripts
and raw provider ledgers were not replayed.

## Classification result

The retrospective used six classes: already canonical and discoverable (A),
canonical but poorly discoverable (B), repeated and mature enough to promote
(C), domain-specific (D), incident-specific or experimental (E), and obsolete or
duplicated (F).

| Result | Operating rule |
|---|---|
| A | Orient from canonical repository and provider state. |
| A | Keep evidence, research, owner selection, admission, implementation, result and promotion distinct. |
| A | Ask oracle, mechanism, observation-binding and routing questions in the lifecycle's order. |
| A | Prefer the smallest falsifiable implementation and accept negative results. |
| B | Bind evidence to the actual subject and exact candidate; the rule existed but its ordinary operational route was dispersed. |
| C | A later SHA alone does not invalidate evidence; explicit unchanged-subject re-binding may reuse it, and material change triggers the smallest affected replay. |
| A | Classify the concrete proposed surface before implementation and reclassify upward when scope expands. |
| C | Repository preparation and provider-effect authority are distinct. |
| A | Command success is not provider truth. |
| A | Workflow success does not prove each intended job executed; skipped is not PASS. |
| C | PR-head verification and integrated-main observation are distinct evidence. |
| C | Provider read-back and reconciliation precede Work Item closure; close the Work Item last. |
| D | Provider-derived parsing surfaces and source-release mutation ordering remain specialized release knowledge. |
| A | Stable canonical knowledge does not mirror live provider lifecycle state. |
| A | Replaceable projections do not predict their own future provider effects. |
| D | Security and dependency freshness checks remain at their specialized material boundaries. |
| A | Owner-semantic and oracle questions do not receive manufactured executable evidence. |
| A | One incident does not justify a generic mechanism. |
| A | Human semantic review remains bounded authority at semantic and oracle limits. |
| A | Human attention is constrained; evidence amplification is a failure mode. |
| C | Stable workflow invariants belong in repository knowledge; ordinary prompts normally carry task-specific delta. |
| D | Source-defining and downstream-publication gates remain publication-specific. |

No recurring rule was promoted merely because it appeared frequently. The
promoted set had either survived multiple slices or received independent
re-binding/replay. Incident-specific task-envelope experiments, GitHub parsing
details and publication-security gates remain evidence or specialized procedure.

## Discoverability and duplication finding

The evidence-gated lifecycle already owns epistemic semantics and is routed from
`AGENTS.md`. Generic change and verification guidance already owns public change
practice. The source-release runbook already owns tag, Release and known
provider-transformation detail.

What was missing was one ordinary Gnostoa-self operational route spanning exact
candidate verification, exact-head provider checks, authorized integration,
integrated/provider read-back, subject re-binding, reconciliation and Work Item
closure. Agents otherwise had to infer that route from specialized release
instructions and recent PR evidence. The same gap caused task prompts to repeat
stable workflow prose.

`AGENTS.md` also repeated the lifecycle's four-step epistemic mini-procedure.
That duplication should become routing to the lifecycle and the ordinary
runbook, not another synchronized summary.

## Accepted canonical shape

The smallest sufficient consolidation is:

1. the existing evidence-gated lifecycle remains the sole authority for
   epistemic order, gap classes, selection/admission, oracle limits,
   falsification and negative results;
2. one short ordinary-delivery runbook owns operational ordering and subject
   re-binding for Gnostoa-self slices;
3. specialized release/publication runbooks retain their domain rules;
4. `AGENTS.md` routes rather than reproduces the method; and
5. this assessment preserves the evidence and rejected generalizations.

No workflow engine, provider adapter, evidence primitive, policy, schema, CI job
or adopter-facing process is selected.

## Fresh-agent falsification contract

Canonicalization is a claim until it is exercised. Do not manufacture a task to
make it pass. On the first naturally occurring eligible ordinary bounded slice,
give a genuinely fresh agent repository access, no conversation transcript and
only the task-specific delta. The prompt has no fixed length limit, but should
not restate the stable workflow.

The agent should discover the lifecycle and ordinary runbook, reconstruct the
change class and required records, distinguish already-selected semantics from
owner decisions, identify exact-candidate and provider verification, require
integrated read-back and reconciliation, and stop at the correct owner boundary.
Success demonstrates orientation and process reconstruction, not autonomous
semantic correctness or transfer to adopters. An immediate read-only orientation
exercise on this canonicalization would be discoverability evidence only.

## Non-conclusions

This retrospective does not promote the method to adopter guidance, make provider
effects mechanically enforced, replace human review, reopen G3, clear G4 or
CPython residuals, select source identity, or authorize release or publication.
