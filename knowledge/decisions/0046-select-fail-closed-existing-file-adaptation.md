---
type: Decision
title: Select fail-closed existing-file adaptation
description: Select the narrow documentation-only preservation contract demonstrated by the Nextcloud Mail adoption evidence without adding a routing or executable mechanism.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-25T20:43:51Z"
sources:
  - id: post-diagnostic-remediation-work-item
    resource: https://github.com/ktogias/gnostoa/issues/125
    title: Analyze and remediate Nextcloud Mail adoption route activation and safe existing-file adaptation
  - id: post-diagnostic-remediation-alternatives
    resource: ../assessments/nextcloud-mail-post-diagnostic-remediation-alternatives.md
    title: Nextcloud Mail post-diagnostic remediation alternatives
  - id: route-activation-diagnostic-result
    resource: ../assessments/nextcloud-mail-adoption-route-activation-diagnostic-result.md
    title: Nextcloud Mail adoption route-activation diagnostic result
x-project-knowledge:
  id: kit.decision.0046.select-fail-closed-existing-file-adaptation
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md
    - kind: references
      target: /decisions/0045-select-documentation-only-remediation-for-nextcloud-mail-adoption.md
    - kind: references
      target: /assessments/nextcloud-mail-post-diagnostic-remediation-alternatives.md
    - kind: references
      target: /assessments/nextcloud-mail-adoption-route-activation-diagnostic-result.md
---

# Select fail-closed existing-file adaptation

Recorded by `codex/gpt-5` from the accountable maintainer's selection. The
narrowed Alternative A2 scope and its exclusions are owner semantics; this
record does not reinterpret Decision 0045 or the rejected Mail adoption result.

## Context

The route-activation diagnostic replaced Mail's existing 152-line `AGENTS.md`
with the 24-line Gnostoa router, removing project-specific architecture,
verification, Git and SPDX/REUSE instructions. The
[post-diagnostic alternatives assessment](../assessments/nextcloud-mail-post-diagnostic-remediation-alternatives.md)
classifies this as both an agent error and demonstrated guidance friction: the
template-to-target map did not state a fail-closed preservation postcondition
for an existing authoritative target.

Current `README.md`, the adoption guide and `guidance/index.md` already link the
existing-project workflow directly. The diagnostic nevertheless selected the
bootstrap route. That named-route behavior remains a separate measurement for a
later rerun; adding another public front door is not justified by this result.

The admitted six-path change is `normative` because generic adopter guidance
and a public reusable template change meaning. It changes no schema, validator,
CLI, runtime or provider behavior.

## Decision

**A. Select A2-narrow.** Select only documentation-based, fail-closed
preservation and adaptation of existing authoritative project files. Before a
mapped target is written, its existence and project authority must be
inspected. A reusable template is adaptation material, not permission to
replace existing authority.

**B. Preserve or stop.** An existing `AGENTS.md` retains its project-specific
instructions and receives only missing Gnostoa routing when edit authority is
clear and the instructions do not conflict. Unrelated content and ordering are
retained where practical, and the before/after identities or diff are evidence.
Contradictory instructions are never silently reconciled. A conflict or unclear
authority requires preserving the file, recording the conflict and stopping for
accountable-owner resolution.

**C. Bound the rule.** The same inventory and no-blind-overwrite boundary
applies to mapped policy, CI and verification targets. It does not claim that
prose can mechanically merge their semantics. Existing unknown-owner and
commitment stops, source/runtime-lock verification and final staged-gitlink
equality remain distinct controls and are neither duplicated nor weakened.

**D. Do not add a front door.** No new `README.md`, adoption-guide,
`guidance/index.md` or equivalent routing change is selected. The later rerun
must continue to measure whether a fresh agent follows the explicitly named
existing-project workflow.

**E. Leave other alternatives unselected.** A0 leaves the demonstrated
destructive-adaptation boundary unchanged. A1-front-door-only duplicates
already-present routing and does not address safe adaptation. A3's executable
preflight and A4's initializer or generator add unjustified public contracts
and maintenance surface. None is admitted by this Decision.

**F. Require falsification.** Documentation cannot guarantee compliance. One
later separately admitted fresh rerun must test whether the named route is
consulted, existing Mail authority is preserved or produces an owner stop, and
the other frozen success criteria remain satisfied. Until then, no improvement,
causation, general adoption value, B3 or Decision-0036 result is claimed.

**G. Admitted surface.** Admit only:

- `guidance/workflows/adopt-existing-project.md` as semantic authority;
- the minimum operational warning in
  `guidance/workflows/bootstrap-new-project.md`;
- the minimum adaptation warning in `templates/AGENTS.project.md`;
- one focused contract test in `tests/test_tools.py`;
- this Decision; and
- `knowledge/index.md` navigation.

No Mail change, rerun, schema, validator, CLI, runtime, workflow, provider,
release or OCI effect is authorized.

## Consequences

- Existing authoritative project content is the default preserved state;
  semantic conflict remains an accountable-owner question.
- The existing-project workflow owns the reusable rule. Bootstrap and the
  template carry only enough warning to reach and honor it.
- Structural tests prove that the public contract is present, not that an agent
  follows it or that adoption value improves.
- Decision 0045 remains the historical A1 selection authority. Its central
  existing-project slice remains untested, not failed.
