---
type: Source
title: Work Item 187 Experiment Capsule system v1 execution plan
description: Bounded execution plan for the declarative Experiment Capsule preparation and qualification layer above the owner-led runner, including scope limits, staged deliverables, Phase-D acceptance fixtures and explicit stop conditions.
status: draft
generated:
  by: claude/opus-5
  at: "2026-09-04T15:10:00Z"
sources:
  - id: capsule-work-item
    resource: https://github.com/ktogias/gnostoa/issues/187
    title: Build declarative Experiment Capsule preparation and qualification system
  - id: capsule-decision
    resource: https://github.com/ktogias/gnostoa/blob/main/knowledge/decisions/0059-compile-declarative-experiment-capsules-over-the-owner-led-runner.md
    title: Compile declarative Experiment Capsules over the owner-led runner
---

# Work Item 187 Experiment Capsule system v1 execution plan

Starting revision: `1da97de5374f6ad7d64d716e3dd0b7acafd4b1f2`, tree
`c0f22474404eb814fa3d929b2501580eb597288b`. Branch
`agent/build-experiment-capsule-system`. Governing decision: `0059`.

## Bounded scope

In scope: a `tools/capsule` package that compiles one declarative experiment specification
into content-addressed task capsules, runner profiles and an immutable experiment lock, or
into a structured `BLOCKED` result; adapters for `python-pytest`, `node-vitest` and
`generic-command`; a subject-preparation contract; semantic oracle prequalification;
BASE/REFERENCE qualification by cause; capability certificates; a resumable stage machine; a
small CLI.

Out of scope: any change to `tools/experiment` beyond additive reuse; any Phase-D launch,
executor, reviewer, model or scoring; any network or package acquisition; broad #15 workflow
automation; general language or build-system coverage.

## Deliverables

1. `schemas/experiment-spec.schema.json` and `schemas/experiment-lock.schema.json`.
2. `tools/capsule/identity.py` reusing `tools/experiment/evidence.py` canonical JSON and
   digests.
3. `tools/capsule/spec.py`, `stages.py`, `preparation.py`, `adapters/`,
   `oracle_qualification.py`, `qualification.py`, `certificates.py`, `compiler.py`, `cli.py`.
4. Phase-D acceptance fixtures under `tests/fixtures/experiment-capsule/`, derived from the
   frozen #183 shapes and carrying no hidden oracle or key content.
5. Unit and characterization tests under `tests/test_experiment_capsule*.py`.
6. Documentation: a runbook for preparing an experiment and the generated-artifact contract.

## Staged execution

**Stage 1 — RED.** Author failing characterization tests for: D1 declarative preload; D2 test
config isolation; D3 generated-artifact preparation detection; D4 semantic prequalification
blocking before execution freeze; D0 certificate reuse without rerun; stage resume and
downstream invalidation; certificate bound mismatch; and the no-handwritten-Dockerfile
property of the Phase-D path. Retain the failing run.

**Stage 2 — identity and spec.** Schemas, spec loading and validation, canonical identity.

**Stage 3 — stage machine.** Stage records, input closure digests, reuse and invalidation,
resume from retained files.

**Stage 4 — adapters and preparation.** Adapter contract, the three adapters, subject
preparation detection and deterministic generated artifacts, offline availability checks.

**Stage 5 — qualification.** Static qualification, semantic oracle prequalification,
BASE/REFERENCE qualification by cause with infrastructure and wrong-cause classes.

**Stage 6 — certificates, freeze and CLI.** Capability certificates with exact bound fitting,
execution freeze, experiment lock, `prepare`/`status`/`execute`.

**Stage 7 — verification.** Full offline suite, Ruff, mypy on the new package, knowledge
bundle validation, and the Phase-D fixture acceptance run.

**Stage 8 — one draft PR.** Summarize architecture, RED to GREEN evidence, fixture outcomes,
limitations and migration path. Stop for owner review. Do not merge.

## Acceptance evidence to retain

The Phase-D fixture run must show D0 reused, D1 and D2 prepared mechanically without oracle
or image identity change, D3 assigned a new runtime and preparation identity, and D4
`BLOCKED` at semantic prequalification before execution freeze, with the existing runner
validator accepting every generated profile.

## Stop conditions

Stop and report rather than widen if: a defect requires redesigning `tools/experiment`; a
required dependency is not locally available offline; Phase-D acceptance requires launching an
agent or model; the spec cannot express a fixture without inventing semantics; or the work
starts absorbing #15.
