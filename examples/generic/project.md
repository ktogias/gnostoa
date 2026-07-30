---
type: Project
title: Example project
description: A small technology-neutral bundle used to validate the generic profile.
status: stable
generated:
  by: human:example-maintainer
  at: "2026-07-29T12:00:00Z"
verified:
  by: human:example-reviewer
  at: "2026-07-29T12:30:00Z"
x-project-knowledge:
  id: example.project
  owners:
    - team:example
  relations:
    - kind: contains
      target: /systems/processing-system.md
    - kind: governed-by
      target: /decisions/0001-processing-boundary.md
---

# Example project

This project exists only to demonstrate that the core profile does not depend
on an implementation language, cloud or organization.

See the [processing system](systems/processing-system.md) and the
[boundary decision](decisions/0001-processing-boundary.md).

