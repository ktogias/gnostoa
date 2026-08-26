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
    {
      "kind": "native-executable",
      "role": "suite-runtime",
      "subject": "/absolute/path/to/executable",
      "value": {
        "sha256": "sha256:<64 lowercase hexadecimal characters>",
        "version": "<directly observed version>"
      },
      "measurement": {"method": "executable-sha256-and-version-v1"}
    },
    {
      "kind": "dependency-lock",
      "role": "suite-lock",
      "subject": "project-relative.lock",
      "value": {
        "sha256": "sha256:<64 lowercase hexadecimal characters>"
      },
      "measurement": {"method": "file-sha256-v1"}
    }
  ],
  "origin": {
    "kind": "project-adapter",
    "entry": "./ci/verify"
  }
}
```

The example contains placeholders and is not itself a valid observation.
Version 1 is a closed, mechanically decidable profile:

- `schema` is the exact literal shown above. `suite` is the invoked suite key
  from the validated verification manifest, uses 1--64 ASCII letters, digits,
  `.`, `_` or `-`, and equals that invocation. `invocation_binding` is exactly
  64 lowercase hexadecimal characters. `route_kind` is exactly `native`,
  `container`, `service` or `composite`; it classifies the route actually
  entered and neither selects a route nor authorizes fallback.
- `runtime_identity` has 1--16 items. Each item has exactly `kind`, `role`,
  `subject`, `value` and `measurement`; each `measurement` has exactly
  `method`. Items are unique by `(kind, role, subject)`. Every string other
  than the exact literals and hashes is 1--512 Unicode scalar values with no
  control characters; a `version` is further limited to 256. Native executable
  subjects are normalized absolute paths. Lock subjects are normalized
  project-relative POSIX paths with no empty, `.` or `..` component. Container
  subjects are 1--256 printable ASCII characters identifying the entered
  runtime instance.
- Version 1 admits only these bound identity profiles:

  | `kind` | `role` | exact value members | exact measurement method |
  | --- | --- | --- | --- |
  | `native-executable` | `suite-runtime` | `sha256`, `version` | `executable-sha256-and-version-v1` |
  | `dependency-lock` | `suite-lock` | `sha256` | `file-sha256-v1` |
  | `oci-image` | `suite-runtime` | `digest` | `entered-container-image-digest-v1` |

  Every `sha256` or `digest` value is the literal `sha256:` followed by 64
  lowercase hexadecimal characters. The executable method resolves the
  executable actually used for the suite payload, hashes those executable
  bytes and obtains the version from that executable in the entered native
  environment. A dispatch-only shell does not substitute for the payload
  runtime. The lock method hashes the applicable project dependency/toolchain
  lock consumed by that route. The container method starts from the entered
  container instance, uses the project adapter's container engine to resolve
  the immutable image digest for that instance, and never accepts an image
  tag, manifest expectation or caller value as the measurement.
- A complete `native` observation contains at least one
  `native-executable`/`suite-runtime` item for every applicable interpreter,
  compiler, package manager or test runner used by the suite payload, and at
  least one applicable `dependency-lock`/`suite-lock` item. If the adapter
  cannot identify and measure both the actual toolchain and its applicable
  lock, the native route is incomplete and `BLOCKED` in version 1.
- A complete `container` observation contains exactly one
  `oci-image`/`suite-runtime` item. Its immutable digest is measured from the
  container instance that entered the suite runtime. A tag, configured image
  string, lock value or expected digest is declaration-only and cannot satisfy
  this profile.
- `service` and `composite` remain recognized route classifications, but are
  unsupported in version 1. Their relevant execution components and roles
  cannot yet be bounded generically without selecting a new contract; they
  therefore produce `BLOCKED`, not an adapter-defined identity pass.
- `origin` has exactly `kind` and `entry`; `kind` is the exact literal
  `project-adapter`, and `entry` is the 1--512-character invoked project
  command. The caller binds it to that exact entry and independently retains
  its file or blob hash.

The JSON decoder rejects duplicate member names and unknown members at every
object level. It also rejects unknown enum values, profiles, roles, measurement
methods, value members and duplicate identity items. Later extension of any
vocabulary, route profile or object shape requires another schema version.
Caller-, manifest- or lock-supplied expected identities remain declarations:
copying one into a syntactically valid item does not establish its required
measurement and cannot independently produce observation or coherence `PASS`.

### C. Validate, retain and classify the observation

After the suite process exits, adoption-check must retain its numeric exit,
stdout, stderr and before/after Git state, then read only the exact caller-chosen
sidecar path. It validates the size, closed JSON shape, schema, suite,
invocation binding, route profile, complete bound identity set and
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

Missing, malformed, oversized, stale, wrong-schema, wrong-suite, wrong-binding,
invalid-origin, unknown, duplicate, unsupported, incomplete or
declaration-only observation produces `project-runtime observation: BLOCKED`
and overall exit `3`, while retaining any separately observed suite exit. A
complete measured observation that conflicts with an applicable mandatory
declared identity instead produces route coherence `FAIL` and overall exit
`1`. The distinction is whether the actual subject was first observed
completely: unavailable or invalid observation is `BLOCKED`; a complete actual
that contradicts its mandatory expectation is an executed coherence failure.

This operationalizes Decision 0047's unavailable/incoherent-subject boundary
and the integrated assessment's exit split without leaving "mismatched"
ambiguous: failure to acquire the required actual is exit `3`, while comparison
of a complete actual to an applicable mandatory declaration can fail with exit
`1`. With a complete coherent sidecar, an executed suite failure also keeps
Decision 0047's exit `1`; unsafe invocation or internal failure keeps exit `2`.
Exit `0` remains only `READY FOR ACCOUNTABLE-OWNER REVIEW`, never semantic or
durable-adoption acceptance.

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
for absent, oversized, malformed, duplicate or unknown members at every object
level, wrong-schema, wrong-suite, wrong-binding, invalid-origin,
declaration-only, pre-existing-path and overwrite cases. Route-profile tests
must reject tag-only container identity, invalid identity/method pairings and
native observations missing applicable executable/toolchain or lock identity;
must return `BLOCKED` for service/composite version 1 observations; must accept
complete measured native and container profiles; and must distinguish an
incomplete observation at exit `3` from a complete actual/mandatory-declaration
coherence conflict at exit `1`. No Mail fixture or experiment is admitted by
those tests.

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
