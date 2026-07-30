---
type: Decision
title: Require verification-first development without universal TDD
description: Define expected behavior and proportionate evidence before implementation while avoiding artificial tests for non-executable changes.
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
  id: kit.decision.0007.verification-first-development
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: implements
      target: /requirements/verification-precedes-implementation.md
    - kind: governs
      target: /runbooks/maintain-the-kit.md
    - kind: references
      target: /decisions/0006-provider-neutral-change-governance.md
---

# Require verification-first development without universal TDD

## Context

The toolkit already requires passing checks, synchronized tests and reviewed
guardrail coverage. It does not require expected behavior or failure evidence
to exist before implementation. A passing test added after the code can confirm
the implementation it observed rather than independently specify the intended
behavior.

Strict TDD for every diff is not a suitable generic rule. Mechanical edits,
semantic prose, discovery spikes and emergency restoration have different
verification surfaces. Artificial tests for them increase maintenance cost
without increasing confidence. Git history also cannot reliably prove authoring
chronology after squash or rebase.

## Decision

Adopt verification-first development as the generic invariant:

1. State observable expected behavior and acceptance evidence before changing
   the implementation.
2. Use test-first Red-Green-Refactor when behavior is executable and
   automatable.
3. Reproduce a defect with a failing regression test before its fix.
4. Establish characterization coverage before behavior-preserving refactoring.
5. Define failing conformance or policy evidence before changing schemas,
   profiles, contracts or guardrails.
6. Use structural validation plus accountable human semantic review for
   non-executable knowledge; do not create ceremonial unit tests for prose.
7. Permit exploratory work without test-first evidence only when it is
   time-boxed and cannot integrate as supported behavior until verified.
8. Permit emergency post-event evidence only through the existing audited
   emergency class.

Express minimum verification intent and timing in the inherited change-control
policy. Let projects strengthen the requirements and choose stack-specific test
tools in their narrowest specialization.

For this toolkit, changes to `tools/`, `schemas/`, `core/` and `policy/` use
test-first evidence. Bug fixes begin with a reproducer. Refactors begin with a
green characterization suite. Reviewers confirm that a proposed test would fail
when the behavior is broken; CI confirms the final state, but does not claim to
prove chronology.

## Consequences

- Tests become executable behavioral evidence rather than coverage decoration.
- Developers and agents receive a smaller, more precise implementation target.
- Mechanical and prose-only work avoids low-value test proliferation.
- Change Requests must record expected behavior and pre-change evidence.
- Test suites remain reviewed production assets and add maintenance cost.
- Flaky, slow or implementation-coupled tests undermine the feedback loop and
  must be treated as defects.
- Enforcement is hybrid: schemas and CI validate declared policy and outcomes;
  reviewers validate chronology, relevance and semantic correctness.
