---
type: Workflow
title: Create a project-area or module specialization
description: Add child vocabulary and constraints only when the project profile is insufficient.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-07-29T00:00:00Z"
x-project-knowledge:
  id: guidance.workflow.create-specialization
  owners:
    - team:gnostoa-maintainers
  scope:
    - generic-guidance
  relations:
    - kind: governed-by
      target: /guardrails/non-negotiable.md
    - kind: references
      target: /reference/versioning-and-upgrades.md
---

# Create a project-area or module specialization

## Outcome

A monotonic child profile expresses additional domain vocabulary or stricter
validation without copying or weakening the project profile.

## Preconditions

- A valid project profile already exists.
- At least one real concept cannot be represented clearly with the parent
  vocabulary or rules.
- The module owner accepts responsibility for the specialization.

## Procedure

1. Confirm that a specialization is necessary. A team, directory or code module
   alone is not sufficient justification.
2. Create `.knowledge/modules/<module>/profile.yaml`.
3. Extend `../../profile.yaml`.
4. Add a representative concept or failing validation test that demonstrates
   the missing parent capability before changing the profile.
5. Add only the new concept types, relationship kinds and required sections.
6. Do not repeat parent lists or rules.
7. Make the representative concept and tests pass.
8. Validate the bundle with the leaf profile.
9. For several sibling specializations sharing one bundle, create an aggregate
   validation profile extending each leaf. Do not make siblings inherit one
   another.
10. Version the specialization as its own validation contract.
11. If the specialization introduces a real integration, smoke, extended or
    deployable capability, strengthen the project CI policy and verification
    manifest in the same Change Request. Keep provider syntax outside the
    domain profile.

Minimal child:

```yaml
id: example-project.example-module
version: "0.1.0"
okf_version: "0.2"
extends:
  - ../../profile.yaml
concept_types: []
relation_kinds: []
rules: {}
type_rules: {}
```

## Verification

- Core, project and child types are all present in the resolved profile.
- The child cannot disable verification, uniqueness or link policies.
- Existing parent-only bundles remain valid.
- The specialization is used by real concepts and is not speculative taxonomy.
- Any added verification capability has an owned suite and centralized event
  mapping.

## Recovery

If the specialization merely duplicates its parent, remove it before release.
If a child requirement applies to unrelated projects, propose it to the generic
core through a separate decision rather than creating parallel copies.
