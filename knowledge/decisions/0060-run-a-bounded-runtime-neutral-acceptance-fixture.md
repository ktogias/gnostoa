---
type: Decision
title: Run a bounded runtime-neutral acceptance fixture
description: Construct one self-only deterministic fixture for scoped acceptance and adapter independence without activating a production control or selecting an agent provider.
status: draft
generated:
  by: agent:codex
  at: "2026-09-10T11:40:58Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/11
    title: Semantic capture reconciliation
  - id: fixture-admission
    resource: https://github.com/ktogias/gnostoa/issues/11#issuecomment-5618072832
    title: D11-F1 bounded fixture Decision and admission
x-project-knowledge:
  id: kit.decision.0060.run-a-bounded-runtime-neutral-acceptance-fixture
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md
    - kind: governed-by
      target: /decisions/0018-adopt-evidence-gated-capability-evolution-for-gnostoa-self-governance.md
    - kind: references
      target: /contracts/public-inheritance-surface.md
---

# Run a bounded runtime-neutral acceptance fixture

## Context and authority

The owner selected construction of the previously described small fixture after
review of the runtime-neutral managed-delivery proposal. The linked D11-F1
admission records that instruction, the source baseline, allowed paths and
effects, classification and initial behavior map before implementation. This
agent-authored Decision retains that bounded choice; it is not human semantic
verification of the resulting code.

The proposed supervisor's obligations must be independent of worker activity,
and a worker completion event must not itself authorize acceptance. A concrete
adapter may translate observations, but cannot define its own minimum required
capabilities or erase unknown state. Evidence producer and worker adherence are
different facts. These are the fixture's explicit hypotheses, not demonstrated
properties of the current daily workflow.

## Decision

1. Construct D11-F1 as **Gnostoa-self-only experimental test code** under
   `tests/fixtures/managed_acceptance/`, exercised by
   `tests/test_managed_acceptance_fixture.py`. Retain its assessment and native
   evidence under `knowledge/assessments/`. This does not add a supported CLI,
   public schema, policy, production gate or actual provider capability.
2. Classify this bounded diff as **normal**: it implements and tests a disposable
   model of a proposed control without granting real acceptance authority. A
   future live security/runtime/control implementation requires its own impact
   classification and admission. Do not infer that future changes are normal.
3. Freeze cases F01-F10 and their independently stated output oracle. Use two
   scripted adapters with different native event representations and the same
   candidate control and persisted-result reader. The workers are cooperative
   test doubles; no hostile-code or operating-system isolation claim follows.
4. Before implementing the corrected control, execute an intentionally defective
   completion-only baseline. Retain actual false acceptance and oracle failure.
   Missing imports/executables do not count as behavioral RED. This constructed
   counterexample is not a historical reproduction or an installed product bug.
5. After that evidence, implement the smallest corrected fixture and replay the
   unchanged oracle. A targeted completion-to-acceptance mutant must be rejected
   by that oracle. Keep acceptance and provenance measurement failures distinct.
6. Execute through the development container with network disabled and a
   read-only source mount. The fixture uses no LLM, service credentials, real
   provider effect, deployment, new repository, protection change or Phase-D
   launch. Ordinary review-branch, draft-PR and evidence recording effects stay
   separate from fixture execution; merge remains a separate owner act.
7. Preserve source, cases, oracle, counterexample and native outputs together.
   Hashes bind retained representations; they do not establish semantic truth.
   Report negative results without expanding the fixture to rescue a claim.

## Consequences and limits

The fixture can test the stated consumer behavior and expose coupling between
its two adapter mappings. It cannot establish production enforcement, real agent
compatibility, complete mediation, durable recovery under arbitrary crashes or
coverage of ordinary unregistered work. Passing scripted adapters is not real
provider portability. It does not close L10 or adopt the broader D11 design.

Human semantic review of the candidate and a later disposition remain required.
The broader design, real runtime integrations, hosting topology and operational
adoption stay outside this construction. No public promotion or requirement on
adopting projects follows from a positive experimental outcome.
