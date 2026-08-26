---
type: Decision
title: Select project-adapter runtime observation for adoption-check
description: Preserve the project-owned verification entry and existing manifest while selecting one bound, non-overwriting runtime-observation sidecar for complete adoption-check evidence.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-26T13:10:03+03:00"
sources:
  - id: project-verification-routing-work-item
    resource: https://github.com/ktogias/gnostoa/issues/133
    title: Determine fail-closed adopter project-verification routing
  - id: project-verification-routing-assessment
    resource: ../assessments/adoption-check-project-verification-runtime-routing.md
    title: Adoption-check project-verification runtime routing
  - id: adoption-completion-decision
    resource: 0047-select-a-bounded-adoption-completion-check.md
    title: Select a bounded adoption-completion check
x-project-knowledge:
  id: kit.decision.0048.select-project-adapter-runtime-observation-for-adoption-check
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md
    - kind: governed-by
      target: /decisions/0047-select-a-bounded-adoption-completion-check.md
    - kind: references
      target: /lifecycles/evidence-gated-capability-evolution.md
    - kind: derived-from
      target: /assessments/adoption-check-project-verification-runtime-routing.md
---

# Select project-adapter runtime observation for adoption-check

Recorded by `codex/gpt-5` from the accountable maintainer's compatibility
selection. This Decision narrows how the future command selected by
[Decision 0047](0047-select-a-bounded-adoption-completion-check.md) may observe
project verification. It does not modify Decision 0047 or admit implementation.

## Context

The integrated
[runtime-routing assessment](../assessments/adoption-check-project-verification-runtime-routing.md)
keeps the Gnostoa toolkit runtime separate from the adopter project's
verification runtime. It finds that the project already owns one authoritative
suite boundary, normally `./ci/verify <suite>`, but an opaque process exit does
not establish which runtime that adapter actually used. Expected images and
caller-supplied identities are declarations, not observations.

The evidence does not justify a Gnostoa route selector, fallback order,
container runner, synthesized runtime or multi-route manifest language. The
accountable owner therefore selects the smallest no-manifest-change alternative:
the same project adapter that executes a suite reports one bounded runtime
observation bound to that invocation.

This two-path selection is a `normal`, knowledge-only change. It changes no
public byte, executable contract or runtime now. Any later implementation is a
separate normative admission.

## Decision

### A. Preserve project authority and the current manifest

Keep `verification.yaml` unchanged. Keep the validated suite command, normally
`./ci/verify <suite>`, as the sole project-owned authoritative entry point.
Gnostoa invokes that command without a shell and does not choose how it enters
an image, container, service or isolated-native environment.

Gnostoa must not select another route, fall back after unavailability or test
failure, infer authority from Dockerfile, Dev Container, Compose, CI or
dependency-file presence, install dependencies, synthesize a runtime or launch
an alternative container around the project adapter. An absent or ambiguous
authoritative entry remains `BLOCKED`.

### B. Select one opt-in sidecar handshake

For each adoption-check suite attempt, the caller:

1. generates a fresh 32-byte random invocation value encoded as 64 lowercase
   hexadecimal characters;
2. selects one absolute, initially absent sidecar path inside the new evidence
   bundle; and
3. invokes the exact validated suite command once, supplying only these
   handshake variables in addition to its ordinary environment:
   `GNOSTOA_ADOPTION_OBSERVATION_PATH` and
   `GNOSTOA_ADOPTION_INVOCATION_BINDING`.

The same `ci/verify` invocation that enters the project runtime and executes the
suite may publish exactly one observation at that path. No second probe or
stdout parser substitutes for the sidecar. The producer writes complete UTF-8
JSON through a temporary file in the same directory and atomically installs the
final regular file with no-replace semantics. An existing target, symlink,
non-regular file, partial publication or overwrite attempt is invalid. A
platform or adapter that cannot meet this boundary leaves the observation
unavailable and therefore `BLOCKED`.

The final sidecar is one JSON object of at most 64 KiB. Version 1 contains only
the following required top-level members:

```json
{
  "schema": "gnostoa-project-runtime-observation/v1",
  "suite": "fast",
  "invocation_binding": "<64 lowercase hexadecimal characters>",
  "route_kind": "native",
  "runtime_identity": [
    {"kind": "<identity kind>", "value": "<directly observed value>"}
  ],
  "measurement_method": {
    "kind": "<bounded method identifier>",
    "detail": "<how the running project route acquired the value>"
  },
  "origin": {
    "kind": "project-adapter",
    "entry": "./ci/verify"
  }
}
```

`route_kind` classifies the route actually entered as `native`, `container`,
`service` or `composite`; it neither selects a route nor authorizes fallback.
`runtime_identity` is non-empty and records actual values acquired from that
runtime, not expected values copied from the manifest, lock or caller.
`measurement_method` identifies how those values were acquired and cannot be a
declaration or caller-input method. `origin` identifies the project adapter;
the caller binds it to the exact entry command and independently retained entry
file or blob hash. Duplicate or unknown top-level members are invalid under
version 1; later extension requires another schema version.

### C. Validate, retain and classify the observation

After the suite process exits, adoption-check must retain its numeric exit,
stdout, stderr and before/after Git state, then read only the exact caller-chosen
sidecar path. It validates the size, JSON shape, schema, suite, invocation
binding, route kind, non-empty runtime identity, measurement method and
project-adapter origin. It hashes and retains the exact sidecar bytes in the
non-overwriting evidence bundle.

The sidecar suite and invocation value must equal the command attempt that
produced it. Its origin entry must equal the invoked project command, whose hash
is measured independently by adoption-check. Any declared runtime expectation
may constrain the observed value and a mismatch fails coherence, but neither a
manifest value nor a caller-supplied expected identity can create an observation
or coherence `PASS`.

A valid sidecar is explicitly **project-reported runtime observation**. It is
not independent attestation, semantic truth or owner acceptance. Independent
digest-bound or platform evidence, when available, is acquired and reported as
a separate observation; the adapter cannot mark its own sidecar attested. In
its absence, independent attestation remains `NOT OBSERVED` without rewriting
the project-reported result.

Missing, malformed, mismatched, stale, declaration-only or origin-unbound
observation produces `project-runtime observation: BLOCKED` and overall exit
`3`, while retaining any separately observed suite exit. With a valid sidecar,
an executed suite failure keeps Decision 0047's exit `1`; unsafe invocation or
internal failure keeps exit `2`. Exit `0` remains only `READY FOR
ACCOUNTABLE-OWNER REVIEW`, never semantic or durable-adoption acceptance.

### D. Preserve ordinary adapter compatibility

Outside adoption-check, the two handshake variables are absent and existing
`ci/verify` behavior remains unchanged. An existing adapter that does not
implement the handshake may still run normally. When adoption-check invokes it,
the suite attempt and output are retained, but the absent sidecar prevents
complete evidence and returns `BLOCKED` with exit `3`.

The handshake adds no canonical adopter write: its path belongs to the
caller-owned, non-overwriting evidence bundle. Repeating adoption-check against
an unchanged candidate creates a separately bound evidence bundle and does not
modify project, toolkit, index or provider state.

### E. Leave broader mechanisms and unresolved compatibility unselected

Select no verification-manifest change, route field, route list, precedence or
fallback algorithm. Select no Gnostoa-managed container execution, service
orchestration, runtime synthesis, initializer or generator. The current
manifest's project-image compatibility limitation remains a recorded boundary;
this Decision does not make an incoherent declaration pass or predict its later
solution.

Decision 0047 remains unchanged. The future implementation must preserve its
toolkit/runtime identity separation, evidence bundle, semantic-owner gate,
negative tests and fresh-rerun falsification boundary. It must add focused tests
for absent, oversized, malformed, duplicate-key, wrong-schema, wrong-suite,
wrong-binding, invalid-origin, declaration-only, pre-existing-path and
overwrite cases, plus valid observations for project-owned route kinds. No Mail
fixture or experiment is admitted by those tests.

## Consequences

- The sidecar handshake is the smallest selected compatibility boundary: one
  existing entry point gains an opt-in observation channel, while route choice
  stays project-owned.
- The handshake and its versioned JSON are prospective additive public
  compatibility surfaces. Implementing them requires a later normative slice,
  verification-first evidence and eventual source/runtime release before
  external consumers can rely on them.
- A project-reported observation improves binding but is not provenance
  attestation and cannot establish owner authority, semantic truth, adoption
  value or durable commitment.
- No CLI, schema, manifest, template, guidance, adapter, runtime or release byte
  changes under this Decision-only slice. No Nextcloud Mail rerun, B3 result or
  Decision-0036 result is claimed.
