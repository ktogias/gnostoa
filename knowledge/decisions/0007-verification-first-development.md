---
type: Decision
title: Use proportionate verification without universal TDD
description: Require reliable evidence before integration while keeping test-first optional in the lightweight baseline.
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

# Use proportionate verification without universal TDD

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

Adopt proportionate verification as the generic invariant:

1. State observable expected behavior early enough to guide a bounded change.
2. Require reliable final evidence before integration.
3. Prefer test-first Red-Green-Refactor for new executable behavior, defects,
   policies and contracts when it improves design or prevents regression.
4. Prefer characterization coverage before behavior-preserving refactoring.
5. Use structural validation plus accountable human semantic review for
   non-executable knowledge; do not create ceremonial unit tests for prose.
6. Require emergency post-event evidence through the audited emergency class.

The community-light baseline does not require proof of test authoring order,
formal test-first exceptions or failing evidence for every change. It records
`when-applicable` failing evidence and requires final evidence before merge.
Projects can strengthen evidence timing to `before-implementation` and require
failing evidence in a specialization.

For this toolkit, changes to `tools/`, `schemas/`, `core/` and `policy/` should
normally use focused conformance evidence first. Bug fixes should normally
begin with a reproducer and refactors with a characterization suite. When that
sequence adds no useful confidence, the Change Request may simply explain the
final evidence used.

## Consequences

- Tests become executable behavioral evidence rather than coverage decoration.
- Developers and agents receive a smaller, more precise implementation target.
- Mechanical and prose-only work avoids low-value test proliferation.
- Change Requests record expected behavior and proportionate final evidence.
- Test suites remain reviewed production assets and add maintenance cost.
- Flaky, slow or implementation-coupled tests undermine the feedback loop and
  must be treated as defects.
- Enforcement is hybrid: schemas and CI validate declared policy and outcomes;
  maintainers validate relevance and semantic correctness.
