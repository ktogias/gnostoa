---
type: Pattern
title: Verification-first development
description: Define observable evidence before implementation and apply test-first techniques wherever behavior is executable.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-07-29T00:00:00Z"
sources:
  - id: dora-continuous-delivery
    resource: https://dora.dev/capabilities/continuous-delivery/
    title: DORA continuous delivery
  - id: tdd
    resource: https://martinfowler.com/bliki/TestDrivenDevelopment.html
    title: Test-driven development
  - id: google-review-tests
    resource: https://google.github.io/eng-practices/review/reviewer/looking-for.html#tests
    title: Google engineering practices - reviewing tests
  - id: google-sre-testing
    resource: https://sre.google/sre-book/testing-reliability/
    title: Google SRE - testing for reliability
x-project-knowledge:
  id: guidance.pattern.verification-first-development
  owners:
    - team:gnostoa-maintainers
  scope:
    - generic-guidance
  relations:
    - kind: applies-to
      target: /reference/testing-and-verification-strategy.md
    - kind: guides
      target: /workflows/develop-verification-first.md
    - kind: applies-to
      target: /workflows/propose-review-merge-change.md
---

# Verification-first development

## Context

Tests added only after an implementation may confirm its accidental structure
instead of independently specifying intended behavior. Universal TDD is also
too blunt for a technology-neutral project: code, schemas, policies, contracts,
knowledge, generated projections, exploratory spikes and emergency restoration
do not share one verification surface.

## Pattern

Before implementation, define:

1. the observable expected behavior or retained invariant;
2. the smallest evidence that can distinguish success from failure;
3. the pre-change failure, unmet criterion or characterization baseline;
4. the verification level, exact command and accountable semantic reviewer.

When behavior is executable and automatable, use a short
Red-Green-Refactor loop:

- **Red:** run evidence that fails for the intended reason.
- **Green:** make the smallest coherent change that satisfies it.
- **Refactor:** improve structure while all relevant evidence remains green.

Use a failing regression reproducer for a defect, characterization tests before
behavior-preserving refactoring, conformance examples before contract or policy
implementation, and structural validation plus human verification for
non-executable knowledge. A test-first exception must name its permitted class,
rationale and follow-up evidence.

Reviewers verify that the evidence would fail when behavior is broken. CI
verifies the integrated outcome. Neither commit order nor coverage percentage
alone proves test quality.

## Consequences

- Expected behavior becomes a compact shared target for developers and agents.
- Defects and policy changes retain executable regression evidence.
- Refactoring becomes safer because existing behavior is characterized first.
- Non-executable knowledge avoids artificial tests while retaining human
  accountability.
- Tests add code and maintenance cost, so redundant, flaky, slow or
  implementation-coupled evidence must be repaired or removed.
- Test tools and portfolio shape remain project or module specialization
  choices.
