---
type: Decision
title: Strengthen Gnostoa self-governance above the community baseline
description: Require durable issue, decision and test-first evidence for non-mechanical Gnostoa changes without exporting that cost to adopting projects.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-07-30T00:00:00Z"
sources:
  - id: publication-baseline-work-item
    resource: https://github.com/ktogias/gnostoa/issues/1
    title: Prepare the protected Gnostoa publication baseline
x-project-knowledge:
  id: kit.decision.0014.strengthen-gnostoa-self-governance
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /decisions/0006-provider-neutral-change-governance.md
    - kind: references
      target: /decisions/0007-verification-first-development.md
    - kind: governs
      target: /requirements/reviewed-change-control.md
    - kind: verified-by
      target: /runbooks/maintain-the-kit.md
---

# Strengthen Gnostoa self-governance above the community baseline

## Context

The public Gnostoa baseline must remain practical for solo maintainers and
small community projects. Requiring an issue, Decision and test-first chronology
for every adopting project would add process that many projects cannot sustain.

Gnostoa itself changes the schemas, policies and guidance inherited by other
projects. Its maintainers need durable rationale and evidence chronology when a
non-mechanical change alters that public surface. This is a concrete reason for
a toolkit-internal specialization, but not for strengthening the generic core.

Formal approvals, cooling-off periods and owner attestations remain unnecessary
while Gnostoa has one maintainer. They solve a different governance problem and
would not improve the issue, rationale or verification trace required here.

## Decision

Keep `core/change-control.yaml` as the community-light public baseline. Strengthen
only Gnostoa's `policy/change-control.yaml`:

- `mechanical` changes retain the lightweight baseline and do not require a
  separate Work Item or Decision;
- `normal`, `normative` and `critical` changes require a linked Work Item,
  normally a GitHub issue, and a linked Decision;
- applicable evidence for those changes is established before implementation;
- `normative` and `critical` changes require failing behavioral, conformance or
  structural evidence before implementation;
- an `emergency` may integrate first, but its Work Item, Decision and regression
  evidence are mandatory follow-up;
- required formal approvals remain zero for maintainer-authored changes;
  community contributions receive maintainer review.

The self-policy is internal Gnostoa knowledge. It is not part of the public
inheritance surface and must not be copied into consumer templates.

## Consequences

- Gnostoa carries more change-record and verification overhead than adopting
  projects by an explicit product choice.
- Each non-mechanical Gnostoa change leaves a durable problem statement,
  rationale and evidence chronology.
- Mechanical maintenance remains fast and does not need ceremonial records.
- Emergency restoration remains possible without a pre-event paperwork gate.
- Derived projects can independently select the same or another stricter
  specialization when their risk and industry context justify it.
