---
type: Extension Point
title: Example extension point
description: Anonymous module extension point with explicit conformance requirements.
status: draft
generated:
  by: human:example-maintainer
  at: "2026-07-29T12:00:00Z"
x-project-knowledge:
  id: example.module.extension-point
  owners:
    - team:example-module
  scope:
    - example-project
    - example-module
  relations:
    - kind: owned-by
      target: /modules/example-module.md
    - kind: conforms-to
      target: /contracts/example-module-contract.md
    - kind: tested-by
      target: /verification/example-conformance-suite.md
---

# Example extension point

## Purpose

Allow implementations to vary behind a common contract.

## Inputs

Inputs are described in a linked, executable schema owned by the adopting
project.

## Outputs

Outputs are described in a linked, executable schema owned by the adopting
project.

## Errors

The project profile defines its domain-specific error vocabulary.

## Conformance

Implementations pass the
[example conformance suite](../verification/example-conformance-suite.md).

