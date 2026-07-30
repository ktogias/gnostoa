---
type: Requirement
title: Verification precedes integration
description: Every change carries proportionate observable evidence before integration; specializations may require test-first chronology.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-07-29T00:00:00Z"
x-project-knowledge:
  id: kit.requirement.verification-precedes-implementation
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0007-verification-first-development.md
    - kind: verified-by
      target: /runbooks/maintain-the-kit.md
    - kind: implements
      target: /requirements/prevent-policy-drift.md
---

# Verification precedes integration

The toolkit must:

- require expected behavior and final evidence before integration;
- recommend test-first evidence when behavior is executable and automatable;
- support failing reproducers, characterization and conformance evidence without
  requiring formal chronology in the community-light baseline;
- require post-event regression evidence for emergency changes;
- keep required tests deterministic, behavior-oriented and blocking when flaky;
- reject child policies that weaken inherited evidence or timing while allowing
  stricter specializations to require evidence before implementation;
- use human semantic verification instead of artificial tests for
  non-executable claims;
- keep technology-specific frameworks and portfolio choices in project or
  module specializations.
