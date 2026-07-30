---
type: Reference
title: Testing and verification strategy
description: Map change impact and artifact authority to the smallest reliable evidence portfolio.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-07-29T00:00:00Z"
sources:
  - id: practical-test-pyramid
    resource: https://martinfowler.com/articles/practical-test-pyramid.html
    title: The Practical Test Pyramid
  - id: google-review-tests
    resource: https://google.github.io/eng-practices/review/reviewer/looking-for.html#tests
    title: Google engineering practices - reviewing tests
  - id: google-sre-testing
    resource: https://sre.google/sre-book/testing-reliability/
    title: Google SRE - testing for reliability
x-project-knowledge:
  id: guidance.reference.testing-and-verification-strategy
  owners:
    - team:gnostoa-maintainers
  scope:
    - generic-guidance
  relations:
    - kind: operationalizes
      target: /patterns/verification-first-development.md
    - kind: guides
      target: /workflows/develop-verification-first.md
    - kind: applies-to
      target: /reference/change-classification-and-approval.md
    - kind: applies-to
      target: /reference/continuous-integration-contract.md
---

# Testing and verification strategy

## Purpose

Select proportionate, fast and maintainable evidence without forcing a
particular language, test framework, coverage product or fixed portfolio shape.

## Content

The generic policy uses these evidence requirements:

| Change class | Automated evidence | Failing evidence | Timing |
|---|---|---|---|
| `mechanical` | Existing checks | Optional | Before merge |
| `normal` | Required when automatable | When applicable, especially defects | Before merge |
| `normative` | Required when automatable | When applicable | Before merge |
| `critical` | Required | When applicable | Before merge |
| `emergency` | Required | Required follow-up regression | Post-event exception |

Evidence types own different questions:

| Evidence | Question |
|---|---|
| Focused/unit | Does one small observable behavior hold? |
| Property/schema | Do invariants hold across valid, boundary and invalid inputs? |
| Characterization | What behavior must a refactor preserve? |
| Contract/conformance | Do provider and consumer agree at the boundary? |
| Integration | Do owned components collaborate correctly? |
| End-to-end/smoke | Does the critical path work in a representative system? |
| Structural validation | Does policy, knowledge or configuration conform? |
| Human semantic verification | Is a non-executable claim correct and authoritative? |
| Operational observation | Does deployed behavior remain safe under real conditions? |

Prefer the lowest-cost evidence that gives the required confidence. Keep many
fast focused checks, fewer broad integration checks and a small number of
critical-path end-to-end checks, but adapt the portfolio to the project. Avoid
duplicating the same assertion at every level.

Required tests:

- assert observable behavior rather than implementation details;
- are deterministic and isolated where practical;
- cover success, boundary, invalid input and failure semantics as applicable;
- would fail when the intended behavior is broken;
- produce actionable output and fast feedback;
- are reviewed as maintained source artifacts;
- block integration when flaky until fixed or explicitly quarantined through a
  reviewed, expiring exception.

Coverage helps locate untested areas but coverage alone is not acceptance
evidence. A high percentage can coexist with assertions that never detect broken
behavior.

## Usage

For a new project, establish one fast focused suite, one contract or integration
boundary and one critical smoke path before expanding. For an existing project,
start with high-impact characterization tests around the pilot area rather than
attempting blanket coverage.

Record stack-specific frameworks, test commands, environments, reliability
targets, mandatory test-first rules and contract tooling in project or module
specializations. Keep the generic evidence vocabulary unchanged so developers
and agents can traverse projects consistently.

Map the resulting portfolio to `fast`, `regression`, applicable conditional and
scheduled suites through the project verification manifest. Central CI owns
required integration evidence; hooks reuse only a bounded subset for local
feedback.
