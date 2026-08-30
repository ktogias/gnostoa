---
type: Source
title: Adoption-check project-verification runtime routing
description: Bounded analysis of the fail-closed boundary between the Gnostoa toolkit runtime and an adopter project's verification runtime.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-26T12:11:39+03:00"
sources:
  - id: project-verification-routing-work-item
    resource: https://github.com/ktogias/gnostoa/issues/133
    title: Determine fail-closed adopter project-verification routing
  - id: adoption-completion-decision
    resource: ../decisions/0047-select-a-bounded-adoption-completion-check.md
    title: Select a bounded adoption-completion check
  - id: adoption-completion-analysis
    resource: nextcloud-mail-adoption-completion-gate-analysis.md
    title: Nextcloud Mail adoption-completion gate analysis
  - id: post-remediation-mail-result
    resource: nextcloud-mail-post-remediation-fresh-rerun-result.md
    title: Nextcloud Mail post-remediation fresh rerun result
  - id: public-inheritance-contract
    resource: ../contracts/public-inheritance-surface.md
    title: Public inheritance surface
  - id: continuous-integration-contract
    resource: ../../guidance/reference/continuous-integration-contract.md
    title: Continuous-integration contract
  - id: runtime-and-distribution
    resource: ../../guidance/reference/runtime-and-distribution.md
    title: Runtime and distribution modes
x-project-knowledge:
  id: kit.assessment.adoption-check-project-verification-runtime-routing
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
    - kind: references
      target: /runbooks/deliver-bounded-self-hosted-slice.md
    - kind: references
      target: /contracts/public-inheritance-surface.md
    - kind: references
      target: /assessments/nextcloud-mail-adoption-completion-gate-analysis.md
    - kind: derived-from
      target: /assessments/nextcloud-mail-post-remediation-fresh-rerun-result.md
---

# Adoption-check project-verification runtime routing

## Authority, scope and cursor

[Work Item #133](https://github.com/ktogias/gnostoa/issues/133) owns this
bounded analysis. It started on `2026-08-26` from protected commit
`52705c79052b78fd27be3a71b367930c761f4fd4`, tree
`b3c153085fc8879204715b5c318d460e6698f2df`, after integration of
[Decision 0047](../decisions/0047-select-a-bounded-adoption-completion-check.md).
The Work Item was read back as open with `roadmap:now` at
`2026-08-26T12:07:01+03:00`; no pull request was then open. Provider state
after that cursor remains provider-authoritative.

This is a `normal`, knowledge-only determination before implementation of
`knowledge adoption-check`. It does not reopen or amend merged PR #131, select
a release, or change any public contract. Decision 0047 still owns the bounded
completion-check selection. This assessment identifies a project-runtime
precondition that its implementation admission must resolve. Nextcloud Mail is
evidence and a possible later falsification subject, never an implementation
fixture or a source of project-specific toolkit behavior.

## The unresolved boundary

Two verification subjects were conflated in the adoption evidence:

1. The **Gnostoa toolkit runtime** executes `knowledge check-runtime`, policy,
   profile, bundle and context operations. Its source revision, public surface
   and optional OCI identity are governed by the adopter toolkit lock.
2. The **adopter project verification runtime** executes the project's
   `./ci/verify <suite>` commands. Its language toolchains, services,
   dependency locks, container definitions and image identities belong to the
   adopter project, not to Gnostoa.

Passing the toolkit source/runtime-lock check proves no PHP, Composer, database
or other project-suite prerequisite. Conversely, executing project tests in a
project image proves nothing about which Gnostoa toolkit bytes performed the
structural checks. The two subjects require separate observations and separate
results.

The current public contracts expose the mismatch:

- `schemas/verification-manifest.schema.json` allows `runtime.mode` values
  `toolkit` and `project`; `project` currently requires one digest-pinned
  `runtime.image`.
- `templates/verification.project.yaml` consequently carries a placeholder
  project-image digest even when an adopter has not established such an image.
- `knowledge check-ci-policy` can compare that declared image with a
  provider-supplied expected image, but neither value observes execution.
- the continuous-integration contract already makes `./ci/verify <suite>` the
  project-owned adapter and keeps the toolkit-owned `policy` suite separate;
  it does not define how an adoption-time caller enters or observes a
  Dockerfile, Dev Container, Compose, CI-container or native project runtime.

In the final Mail rerun, the lock retained placeholder image values, the
published Gnostoa OCI image was not executed, and PHP/Composer were absent on
the host. Those facts do not establish which Mail-owned verification route was
authoritative or whether its entry point could execute. Missing host tools do
not establish that native host execution was intended, and they do not
authorize treating the Gnostoa image as Mail's project runtime.

## Evidence-to-conclusion map

| ID | Observation or authority | Bounded conclusion |
|---|---|---|
| `R1` | The baseline, #122 and #125 were the three attempts that reached mechanically substantive adoption work; each omitted or overextended required project-suite evidence. The separate #117 frozen rerun stopped before adoption mechanics. The two later substantive runs encountered absent PHP/Composer. | `adoption-check` needs one fail-closed project-suite result through the project's authoritative entry point. Host dependency absence is `BLOCKED` only when it prevents that entry point from executing; it does not identify the intended route. |
| `R2` | The #122 configuration used the Gnostoa toolkit OCI identity as the project verification image; #125 retained placeholder registry identities while executing Gnostoa natively. | Toolkit execution, declared project runtime and observed project execution must be separate fields; a declaration cannot produce coherence or execution `PASS`. |
| `R3` | The final rerun mechanically passed component policy/profile/bundle checks but never ran `check-runtime` or Mail suites. | Structural toolkit validation and project verification are independent required dimensions; neither can substitute for the other. |
| `R4` | The current schema requires one project image and the template supplies a placeholder, while public runtime guidance also recognizes isolated native execution. | The present manifest has a real compatibility gap between its image-shaped declaration and project-owned verification routes. The evidence does not determine whether that gap needs a manifest change or can be resolved by bounded evidence from the existing project adapter. |
| `R5` | The current CI contract already declares `./ci/verify <suite>` as the shared adapter for project-owned suites. | Preserve that adapter as the normal execution boundary; do not make `adoption-check` a general container builder, service orchestrator or dependency installer. |
| `R6` | Decision 0047 requires direct measurement where mechanically possible and forbids expected/caller declarations from establishing execution. | The authoritative project entry needs a bound observation of the runtime it actually used; declarations can constrain validation but never prove execution. |

The evidence does not establish that Mail lacks an authoritative container
route, that its dependencies should be containerized, or that a project image
should be created. It establishes only that the experiment did not execute and
bind one project-owned authoritative verification entry point before
classifying the suites.

## Generic fail-closed routing contract

### Project authority and one entry point

The project owns both its verification suites and how they enter their
verification runtime. It must expose one authoritative verification entry
point, normally the `./ci/verify <suite>` commands already declared by the
validated verification manifest. That project-owned adapter decides whether
and how to enter its declared digest-pinned image, Dockerfile, Dev Container,
Compose or CI service, or isolated native environment.

Gnostoa does not assign precedence among those route kinds. It does not select
an alternative, fall back after unavailability or test failure, infer authority
from file presence, or synthesize a runtime. A Dockerfile, dependency file,
Dev Container, Compose file or CI fragment is not authority merely because it
exists. An absent, ambiguous, unavailable or mechanically unobservable
authoritative entry point yields `BLOCKED` with retained evidence.

Once the authoritative entry executes a suite, its timeout or test failure is
`FAIL`; no different route is attempted to obtain a green result. Missing host
dependencies yield `BLOCKED` only when they prevent the project-owned entry
point from executing. Gnostoa must not infer from their absence that native
host execution was the project's intended route.

### Execution ownership

`adoption-check` invokes only the existing project-owned
`./ci/verify <suite>` command without a shell. Project-owned `ci/verify` remains
responsible for entering its authoritative digest-pinned image, Dockerfile,
Dev Container, Compose or CI-container route, or isolated native environment.
Gnostoa does not independently launch even a declared project image, build an
image, infer build arguments, provision services or translate container
definitions.

The normal `knowledge adoption-check` invocation gains no project-runtime
command, Dockerfile, dependency or image override. It derives the verification
manifest and `ci/verify` commands from the project root as Decision 0047 already
requires. Non-standard path overrides locate the entry-point authority; they
cannot choose another route or declare execution successful.

### Declaration versus observation

A project route or runtime declaration is an expected constraint. It is not
execution evidence. The result must preserve at least these separate subjects:

- Gnostoa documentation source;
- Gnostoa toolkit source;
- Gnostoa executing runtime;
- the adopter's authoritative verification entry and declared expectation;
- observed adopter verification runtime; and
- each project-suite execution.

For a digest-pinned image, the expected image reference remains a declaration.
`PASS` requires a bounded, mechanically validated observation of the image
actually used, including its content digest, plus the suite process exit bound
to that run. For another container or service route, retain the authoritative
entry-point identity and the observed runtime identity exposed by the executed
project adapter. For an isolated native route, retain that entry-point identity
and directly measured executable/toolchain versions and applicable lock
identities. A missing or unverifiable actual yields `BLOCKED`; copying expected
values into a result yields no pass.

The project adapter may need a small, machine-readable runtime-observation
handshake so `adoption-check` can bind the runtime actually used to each suite
result. Whether existing output can carry equivalent evidence safely must be
characterized before changing a manifest or adapter format. That observation
is project-owned execution evidence, not independent attestation or semantic
truth. Its absence must block a complete mechanical result rather than be
replaced by manifest values or narrative output.

### Result and exit semantics

Decision 0047's existing process exits remain sufficient:

- exit `0` only when the toolkit checks, project-runtime observation and every
  required project suite pass, producing `READY FOR ACCOUNTABLE-OWNER REVIEW`;
- exit `1` for an executed suite, route-coherence or postcondition failure;
- exit `2` for invalid/unsafe invocation or an internal error; and
- exit `3` when the authoritative project entry is absent, ambiguous or
  unavailable, or when a required runtime observation cannot be acquired.

The result needs separate project-verification dimensions:

- authoritative entry: `VALID`, `INVALID` or `ABSENT`;
- project-owned route entry: `ENTERED`, `BLOCKED` or `FAIL`;
- project-runtime observation: `PASS`, `BLOCKED` or `FAIL`;
- each project suite: `PASS`, `FAIL`, `BLOCKED` or `NOT RUN`; and
- toolkit/project runtime separation: `PASS`, `BLOCKED` or `FAIL`.

These sit beside, and never replace, Decision 0047's toolkit identity,
structural, context, Git, evidence, semantic-review and durable-adoption
dimensions. A project-suite `PASS` is mechanical evidence for its declared
command only. It is not project truth, owner acceptance or durable adoption.

### Evidence, idempotence and safety

The adoption evidence bundle must retain the authoritative-entry declaration,
the exact `ci/verify` blob or file hash, its command and attempt chronology,
before/after Git state, directly observed runtime identities, numeric exits,
stdout/stderr and suite results. It must identify which observations came from
Gnostoa and which came from the project adapter.

Routing adds no canonical writes. Repeating the check against an unchanged
candidate must not change project, toolkit, index or provider state. Existing
project suites may retain their already-owned effects; the before/after Git
postcondition and evidence record expose them. The checker never installs host
dependencies, builds an inferred image, writes a Dockerfile, commits a recipe,
publishes an image or starts undeclared services.

## Alternatives

### `V0` — leave runtime entry inside `ci/verify`

- **Strength:** preserves project authority, the existing suite interface and
  complex project-specific setup without a Gnostoa orchestrator or route
  selector.
- **Gap:** an opaque wrapper result cannot show which runtime executed and
  cannot distinguish a declaration from an observation.
- **Disposition:** retain `ci/verify` as the sole executor. Add or validate only
  the smallest bounded observation needed to make its actual runtime visible.

### `V1` — represent one selected authoritative route in `verification.yaml`

- **Strength:** could record one project-selected route and its observation
  requirements while keeping expected identities separate from observed
  actuals.
- **Gap:** the current schema represents only toolkit or one mandatory project
  image. Even a single-route representation is a public compatibility change;
  a route list, precedence model, build commands or service settings would
  become an unjustified orchestration DSL and duplicate project authority.
- **Disposition:** retain as a later compatibility option only if equivalent
  evidence cannot be obtained safely through the existing entry point. Do not
  preselect a schema change or put recipes and dependency-install commands in
  the manifest.

### `V2` — Gnostoa-managed container execution

- **Strength:** direct container control could bind a declared immutable image
  digest and isolate host dependencies.
- **Gap:** interpreting Dockerfiles, Dev Containers or Compose would make
  Gnostoa responsible for build contexts, secrets, platforms, volumes,
  services, networks and cleanup. It would also bypass project-owned suite
  setup.
- **Disposition:** reject. If a project uses an image, its authoritative
  `ci/verify` entry owns entry into that image; Gnostoa does not launch an
  alternative route around the adapter.

### `V3` — synthesize a temporary container

- **Strength:** could supply absent host dependencies in a synthetic fixture.
- **Gap:** dependency files and CI fragments do not define a complete,
  authoritative runtime. Synthesis invents base, packages, services, build
  order and security choices, and its passing result would not be the
  project's declared verification route.
- **Disposition:** rejected. No generator, inferred Dockerfile, temporary
  recipe, image publication or committed artifact is justified.

## Smallest recommended mechanism

Recommend **one project-owned authoritative entry plus bounded runtime
observation**:

1. preserve `./ci/verify <suite>` as the sole normal project-suite entry;
2. derive and validate that entry from the project root and existing
   verification manifest;
3. let the project adapter alone enter its selected image, container, service
   or isolated-native environment;
4. have `adoption-check` retain the adapter blob hash, exact command, numeric
   exit, stdout/stderr and before/after Git state, and validate a bounded
   observation of the runtime actually used; and
5. return `BLOCKED` when the authoritative entry or its runtime observation is
   absent, ambiguous or unavailable, without selecting or attempting a
   substitute.

This is smaller than a Gnostoa selector, runner or synthesized environment.
The current verification manifest's mandatory project-image shape remains a
real compatibility gap, but the evidence does not select its solution. The
smallest later compatibility choices are:

| Choice | Surface | Boundary |
|---|---|---|
| Existing adapter owns routing; no manifest-format change | Characterize whether `ci/verify` can expose sufficient bounded runtime evidence through its existing command/output contract. | Smallest if the observation is safe, unambiguous and bindable. |
| Represent only the selected authoritative route and observation requirements | Add the minimum manifest semantics needed to validate one project-selected expectation, while `ci/verify` still owns execution. | Justified only if the existing adapter contract cannot supply equivalent evidence; no route list or precedence. |
| Multi-route selector or route-list DSL | Gnostoa chooses or orders image, container, service and native alternatives. | Not supported by the evidence and rejected. |

Implementation is therefore **not yet admitted** under Decision 0047 alone.
Accountable-owner selection must first bind whether the existing adapter can
provide equivalent evidence without a format change or whether one selected
route/observation representation is necessary. This assessment creates no new
Decision and changes no existing selection.

## Prospective implementation and negative-test boundary

If the owner selects the recommendation, test-first characterization must
first determine whether the existing `ci/verify` command/output can carry an
unambiguous bound observation without a manifest-format change. Only if it
cannot may a later normative slice admit the minimum representation for one
project-selected route and its observation requirements. The resulting change
may touch `adoption-check`, focused tests and the existing adapter/guidance
contract; schema/checker/template changes are conditional, not preselected.
Exact observation semantics must be frozen before editing. No new
configuration file, route list, recipe language or provider adapter is
justified.

Focused tests must prove at least that:

1. a declared or caller-supplied image digest cannot produce route or runtime
   `PASS` without observed execution of that digest;
2. a Gnostoa toolkit image cannot satisfy an adopter project-runtime result;
3. only the project-owned authoritative entry is invoked; Gnostoa performs no
   alternate-route attempt after unavailability or test failure;
4. Dockerfile, Dev Container, Compose or CI file presence is not interpreted
   as route authority and causes no build, entry or synthesis;
5. an absent, ambiguous or unavailable authoritative entry is `BLOCKED`;
6. an executed project entry with no bound runtime observation is
   `BLOCKED`, not `PASS`;
7. an isolated native result records actual tool identities and becomes
   `BLOCKED` when its project-owned entry cannot execute because required tools
   are absent;
8. absent host PHP/Composer does not cause Gnostoa to assume that native host
   execution was intended or to choose another route;
9. no route writes a recipe, installs dependencies, changes canonical bytes or
   turns mechanical suite success into semantic acceptance; and
10. the entry attempt, exits, observations and hashes are retained on both
    `FAIL` and `BLOCKED` paths.

Compatibility review must cover existing manifests with `runtime.image`, the
placeholder project template, provider `expected-runtime-image` checks, native
projects and projects whose `ci/verify` already owns containers or services.
It must compare retaining the current manifest format with representing one
selected authoritative route; it must not assume a route selector is needed.
Any public schema, template, adapter or CLI change requires a later source and
runtime release before general consumers can rely on it. This analysis selects
no format, version or publication effect.

## Later falsification and stop

Nextcloud Mail may be used only after implementation and a separate
pre-registration. The later contract must freeze the same Mail source subject,
the exact new Gnostoa documentation/toolkit/runtime subjects, the authoritative
Mail verification entry visible at that source, the environment and the
evidence bundle. It must not generate or select a Mail container route or
pre-supply project facts.

The routing mechanism is falsified if it treats the Gnostoa runtime as Mail's
project runtime, invokes anything other than Mail's authoritative entry,
assumes native execution from missing host dependencies, selects or synthesizes
an alternate route, falls back after unavailability or test failure, accepts
declaration-only identity, loses entry/runtime evidence or returns
mechanical/semantic adoption acceptance. If Mail's authoritative entry is
absent, ambiguous, unavailable or unobservable, exit `3` with retained
`BLOCKED` evidence is the expected correct result, not a failed product claim.

No implementation, guidance/runtime change, Mail experiment, release, OCI
effect, B3 result, Decision-0036 result or Gnostoa self-verification Docker-build
efficiency work is admitted here. The next step is accountable-owner review of
this routing recommendation and its Decision-0047 compatibility boundary.
