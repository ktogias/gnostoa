---
type: Conformance Suite
title: Example conformance suite
description: Anonymous behavioral checks shared by extension implementations.
status: draft
generated:
  by: human:example-maintainer
  at: "2026-07-29T12:00:00Z"
x-project-knowledge:
  id: example.module.verification.conformance
  owners:
    - team:example-module
  scope:
    - example-project
    - example-module
  relations:
    - kind: verifies
      target: /interfaces/example-extension-point.md
    - kind: verifies
      target: /contracts/example-module-contract.md
---

# Example conformance suite

The suite represents executable checks that all implementations must pass.

