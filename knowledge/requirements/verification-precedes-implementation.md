---
type: Requirement
title: Verification precedes implementation
description: Every change defines proportionate observable evidence before implementation or records an explicit permitted exception.
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

# Verification precedes implementation

The toolkit must:

- require expected behavior before implementation for every change class;
- require test-first evidence when behavior is executable and automatable;
- require a failing reproducer before a defect fix;
- require failing behavioral or conformance evidence for normative and critical
  executable changes;
- require post-event regression evidence for emergency changes;
- keep required tests deterministic, behavior-oriented and blocking when flaky;
- reject child policies that weaken inherited evidence or timing;
- use human semantic verification instead of artificial tests for
  non-executable claims;
- keep technology-specific frameworks and portfolio choices in project or
  module specializations.
