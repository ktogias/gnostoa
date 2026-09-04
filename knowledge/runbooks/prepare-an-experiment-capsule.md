---
type: Runbook
title: Prepare an experiment capsule
description: Author a declarative experiment specification, prepare and qualify it offline into content-addressed capsules and an experiment lock, and read the structured blockers when preparation fails closed.
status: draft
generated:
  by: claude/opus-5
  at: "2026-09-04T15:40:00Z"
sources:
  - id: capsule-work-item
    resource: https://github.com/ktogias/gnostoa/issues/187
    title: Build declarative Experiment Capsule preparation and qualification system
x-project-knowledge:
  id: kit.runbook.prepare-an-experiment-capsule
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0059-compile-declarative-experiment-capsules-over-the-owner-led-runner.md
---

# Prepare an experiment capsule

## Outcome

A declarative experiment specification becomes content-addressed task capsules, generated
runner profiles and an experiment lock, or a structured `BLOCKED` result naming the missing
capability or input. No per-task Dockerfile is written by hand and no harness is repaired by
shell archaeology.

## Preconditions

- Frozen sources and references reachable in local no-remote Git object stores.
- Hidden oracles and identification keys inside the owner-private boundary.
- Immutable runtime image identities already present locally.
- Any build-preparation tool artifact already present locally; offline never acquires.

## Procedure

Author one specification. Intent is declared; everything mechanical is derived.

```json
{
  "schema": "gnostoa-experiment-spec/v1",
  "experiment": {"id": "...", "question": "...", "claim_boundary": "..."},
  "tasks": [{
    "id": "D1-example",
    "adapter": "python-pytest",
    "source": {"repository": "/path/to/mirror.git", "base_commit": "...", "base_tree": "..."},
    "reference": {"kind": "accepted-merge-commit", "commit": "...", "tree": "..."},
    "runtime": {"image": "sha256:...", "available_plugins": ["pytest"]},
    "oracle": {"path": "/private/oracle.py"},
    "semantics": {
      "requirement": "...",
      "discriminator": {"cases": ["test_..."]},
      "controls": [{"case": "test_...", "corroboration": {"path": "tests/test_x.py",
                                                          "value_substitutions": {"mine": "theirs"}}}]
    },
    "harness": {"preload_modules": [], "isolate_test_config": false},
    "execution": {"command": ["<the executor command; never the oracle invocation>"]},
    "expectations": {"base": {"failed": 1, "passed": 0}, "reference": {"failed": 0, "passed": 1}}
  }]
}
```

Adapters are never inferred. A reference may live in another object store via
`reference.repository`. Then prepare and inspect:

```sh
python -m tools.capsule.cli prepare EXPERIMENT_SPEC --workspace WORKSPACE --offline
python -m tools.capsule.cli status WORKSPACE
python -m tools.capsule.cli prepare EXPERIMENT_SPEC --workspace WORKSPACE --offline \
  --preflight-authority AUTHORITY.json
```

`prepare` is idempotent: an unchanged rerun reuses retained stage records, and a changed
input invalidates that stage and everything downstream. Only a *completed* stage is reusable.

Base/reference qualification runs the declared oracle and therefore needs a preflight authority
naming this experiment and the `base-reference-qualification` scope:

```json
{"schema": "gnostoa-preflight-authority/v1", "id": "...", "experiment_id": "...",
 "scope": ["base-reference-qualification"]}
```

Readiness is receipt-gated. `READY_FOR_OWNER_REVIEW` is reachable only when every required stage
carries a completed content-addressed receipt, and it writes the write-once `experiment.lock`.

## Verification

Preparation is correct when `status` reports the expected stage from retained state alone,
each generated runner profile is accepted by the runner's own validator, and every blocker is
one you intend. Read blockers as follows.

| Code | Meaning | Fix |
| --- | --- | --- |
| `test-config-requires-absent-plugin` | repository test options need a plugin the runtime does not carry | declare `harness.isolate_test_config`, or qualify a runtime that provides it |
| `preparation-tool-undeclared` | the tree needs a build-generated file and no tool is declared | declare `runtime.preparation_tools` with a locally available artifact |
| `preparation-artifact-unavailable-offline` | the declared tool artifact is not present locally | make it locally available; preparation never downloads |
| `oracle-case-undeclared` | an oracle case has no declared role | declare it as a discriminator case or as a control |
| `oracle-control-not-corroborated` | a control asserts an expectation nothing corroborates | cite base-tree evidence, bind a prior qualification, or correct the oracle |
| `capability-bounds-not-certified` | the request exceeds the certified bounds | requalify; bounds are never widened to fit |
| `preparation-scheme-undeclared` | a build artifact is needed but no scheme is declared | declare `preparation.scheme`; the compiler never picks a versioning scheme for you |
| `materialised-subject-identity-mismatch` | retained subject bytes do not reconstruct to the declared tree | the workspace is stale or tampered; remove it and rerun |
| `capability-certificate-identity-mismatch` | the certificate file digest is not the declared one | bind the certificate you actually reviewed |
| `oracle-control-corroboration-symbol-required` | a citation names a file but no symbol | name the exact function whose behaviour is the evidence |
| `qualification-backend-unavailable` | the declared backend cannot qualify in v1 | only `local-python` is implemented; a containerised subject needs a runner-backed backend |
| `base-reference-qualification-failed` | observed outcome or cause differs from the frozen expectation | read the classification: `INFRASTRUCTURE`, `WRONG_CAUSE` or `COUNT_MISMATCH` |
| `preflight-authority-out-of-scope` | the authority does not name this experiment and scope | obtain an authority bound to this experiment |
| `readiness-missing-stage-receipts` | a required stage has no completed receipt | readiness is receipt-gated; complete the named stages |
| `execution-profile-admits-private-surface` | the executor profile could reach the reference, oracle or key | a containment defect; the capsule is refused until the surfaces are separated |
| `execution-command-not-declared` | the lock binds no executor command | declare `execution.command`; the oracle invocation is qualification-only and is never reused |
| `preparation-tool-not-used-by-scheme` | a producer artifact is declared that cannot change the produced bytes | remove it; the scheme is a Gnostoa-owned algorithm |
| `prior-qualification-receipt-not-current` | the receipt does not bind today's identities | requalify, or drop the prior-qualification claim |
| `qualification-backend-unavailable` | the declared backend is not one of the supported ones | use `local-python` or `oci` |
| `base-reference-qualification-requires-preflight-authority` | static preparation is complete | obtain explicit owner preflight authority |

A control blocker is the system refusing to guess. If no citation exists, the control is
probably over-strong for the subject, and the oracle needs a new identity rather than a
harness or runtime workaround.

## Trust domains

Qualification and experimental execution are separate domains and are never the same capsule.

| | qualification | execution |
| --- | --- | --- |
| sees BASE | yes | yes |
| sees REFERENCE | yes | **never** |
| sees the hidden oracle | yes | **never** |
| sees the identification key | yes | **never** |
| command | the compiled oracle invocation | the declared `execution.command` |
| sibling arm packet | not applicable | **never** |
| generated subject preparation | yes | yes, carried as an execution artifact |
| environment/credential envelope | qualification harness | declared `execution` envelope |

The compiler checks the execution profile against those forbidden surfaces before freezing, and
`execute` re-checks them before handing anything to the runner. If either check fails the capsule
is refused: handing an executor the known-correct reference would invalidate the experiment.

## Execute a frozen lock

The lock binds a **run plan**: the exact task x repetition x arm entries it authorises. `execute`
consumes those entries rather than re-deriving them, and each run receives only its own arm packet.

Real execution needs a **launch authority**, which is a different record from the preflight
authority and is bound to one exact lock:

```json
{"schema": "gnostoa-launch-authority/v1", "id": "...", "experiment_id": "...",
 "lock_sha256": "<the exact experiment.lock digest>",
 "scope": ["experimental-execution"], "max_runs": 4}
```

```sh
python -m tools.capsule.cli execute WORKSPACE --dry-run
python -m tools.capsule.cli execute WORKSPACE --authority LAUNCH_AUTHORITY.json
```

A stale authority for another lock, a preflight-only scope, or a plan larger than `max_runs` is
refused. `--dry-run` materialises every planned run without executing anything.

`execute` rebuilds each capsule from the lock, the content-addressed artifact store and the
declared private locators only. It performs no discovery and cannot reinterpret the lock.
Credential **names** travel in the lock; values come from the environment at run time and the
runner refuses to start if a declared name is absent.

## Recovery

Preparation never repairs itself. Correct the specification or make the missing artifact
locally available, then rerun `prepare` against the same workspace: unaffected stages are
reused and only the invalidated closure is recomputed. If a blocker names a semantic defect,
amend the semantic freeze deliberately and accept the new semantic identity rather than
editing generated artifacts.

## Boundaries

`prepare` never executes a hidden oracle without explicit preflight authority, never acquires
a dependency, and never repairs semantics. `execute` consumes an already-frozen lock and
cannot reinterpret it. Hidden oracle and key content stays inside the private workspace;
locks and logs carry identities and blocker codes only.
