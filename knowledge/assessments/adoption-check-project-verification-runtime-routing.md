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
the host. Those facts support a blocked native host attempt. They do not prove
that every authoritative Mail verification route was unavailable, and they do
not authorize treating the Gnostoa image as Mail's project runtime.

## Evidence-to-conclusion map

| ID | Observation or authority | Bounded conclusion |
|---|---|---|
| `R1` | All three rejected Mail attempts omitted or overextended required project-suite evidence; the two later runs encountered absent PHP/Composer. | `adoption-check` needs one fail-closed project-suite routing result, but host dependency absence alone is not enough when an already-declared container route may be viable. |
| `R2` | The #122 configuration used the Gnostoa toolkit OCI identity as the project verification image; #125 retained placeholder registry identities while executing Gnostoa natively. | Toolkit execution, declared project runtime and observed project execution must be separate fields; a declaration cannot produce coherence or execution `PASS`. |
| `R3` | The final rerun mechanically passed component policy/profile/bundle checks but never ran `check-runtime` or Mail suites. | Structural toolkit validation and project verification are independent required dimensions; neither can substitute for the other. |
| `R4` | The current schema requires one project image and the template supplies a placeholder, while public runtime guidance also recognizes isolated native execution. | The present manifest cannot truthfully represent the required generic image/container/native routing boundary without a later public-contract change or a narrower project-owned delegation contract. |
| `R5` | The current CI contract already declares `./ci/verify <suite>` as the shared adapter for project-owned suites. | Preserve that adapter as the normal execution boundary; do not make `adoption-check` a general container builder, service orchestrator or dependency installer. |
| `R6` | Decision 0047 requires direct measurement where mechanically possible and forbids expected/caller declarations from establishing execution. | Any routing extension needs a bound observation of the route actually entered; route metadata alone can select or constrain an attempt, never prove it ran. |

The evidence does not establish that Mail lacks an authoritative container
route, that its dependencies should be containerized, or that a project image
should be created. It establishes only that the experiment did not select,
execute and bind a project-owned route before classifying the suites.

## Generic fail-closed routing contract

### Authority and precedence

The project owns both its verification suites and the route used to execute
them. A future admitted contract must resolve only routes already declared by
project authority, in this precedence:

1. an existing project verification image pinned by registry digest;
2. an existing authoritative Dockerfile, Dev Container, Compose service or CI
   container route that the project already makes mechanically reproducible;
3. an existing authoritative isolated native route; or
4. no viable route, yielding `BLOCKED`.

File presence is not route authority. A dependency file, a Dockerfile fragment
or an unrelated CI step is not enough to synthesize or select a runner.
Documentation, an existing project verification manifest, and the project-owned
`ci/verify` adapter must agree on the route. Ambiguity or disagreement blocks
before suite execution and is reported for accountable-owner resolution.

Only an unavailable entrance may advance to the next already-declared route.
Once a route executes a suite, timeout or a test failure is `FAIL`; the checker
must not try a lower-priority route to obtain a green result. Missing native
host dependencies are one route-level unavailable result. They become the
aggregate `BLOCKED` conclusion only after no higher-priority declared route can
execute.

### Execution ownership

`adoption-check` normally invokes the existing project-owned
`./ci/verify <suite>` command without a shell. Project-owned `ci/verify` remains
responsible for entering an already-supported Dockerfile, Dev Container,
Compose, CI-container or isolated native environment. The Gnostoa wrapper may
launch an already-declared digest-pinned project image as a thin execution
adapter only if a later contract makes that exact behavior explicit; it must
not build an image, infer build arguments, provision services or translate
container definitions.

The normal `knowledge adoption-check` invocation gains no project-runtime
command, Dockerfile, dependency or image override. It derives the verification
manifest and `ci/verify` commands from the project root as Decision 0047 already
requires. Non-standard path overrides locate authority; they cannot declare a
route successful.

### Declaration versus observation

A project route declaration selects and constrains an attempt. It is not
execution evidence. The result must preserve at least these separate subjects:

- Gnostoa documentation source;
- Gnostoa toolkit source;
- Gnostoa executing runtime;
- selected adopter verification route and its project authority;
- observed adopter verification runtime; and
- each project-suite execution.

For a digest-pinned image, the expected image reference remains a declaration.
`PASS` requires an engine-observed content digest for the image actually used,
plus the suite process exit bound to that run. For a project-owned container
route, retain hashes of its authoritative definition and the observed runtime
or image identity produced by the executed project adapter. For an isolated
native route, retain the project adapter identity and directly measured
executable/toolchain versions and applicable lock identities. A missing or
unverifiable actual yields `BLOCKED`; copying expected values into a result
yields no pass.

The project adapter may need a small, machine-readable runtime-observation
handshake so `adoption-check` can bind the route actually entered to each suite
result. That observation is project-owned execution evidence, not independent
attestation or semantic truth. Its absence must block a complete mechanical
result rather than be replaced by manifest values or narrative output.

### Result and exit semantics

Decision 0047's existing process exits remain sufficient:

- exit `0` only when the toolkit checks, project-runtime observation and every
  required project suite pass, producing `READY FOR ACCOUNTABLE-OWNER REVIEW`;
- exit `1` for an executed suite, route-coherence or postcondition failure;
- exit `2` for invalid/unsafe invocation or an internal error; and
- exit `3` when every declared route is unavailable or a required runtime
  observation cannot be acquired.

The result needs separate project-verification dimensions:

- route declaration: `VALID`, `INVALID` or `ABSENT`;
- route selection: `PASS`, `BLOCKED` or `FAIL`;
- project-runtime observation: `PASS`, `BLOCKED` or `FAIL`;
- each route attempt: `NOT TRIED`, `UNAVAILABLE`, `ENTERED` or `FAIL`;
- each project suite: `PASS`, `FAIL`, `BLOCKED` or `NOT RUN`; and
- toolkit/project runtime separation: `PASS`, `BLOCKED` or `FAIL`.

These sit beside, and never replace, Decision 0047's toolkit identity,
structural, context, Git, evidence, semantic-review and durable-adoption
dimensions. A project-suite `PASS` is mechanical evidence for its declared
command only. It is not project truth, owner acceptance or durable adoption.

### Evidence, idempotence and safety

The adoption evidence bundle must retain the validated route declarations,
the exact `ci/verify` blob or file hash, route-attempt chronology, authority-file
hashes, directly observed runtime identities, commands, numeric exits,
stdout/stderr and suite results. It must identify which observations came from
Gnostoa and which came from the project adapter.

Routing adds no canonical writes. Repeating the check against an unchanged
candidate must not change project, toolkit, index or provider state. Existing
project suites may retain their already-owned effects; the before/after Git
postcondition and evidence record expose them. The checker never installs host
dependencies, builds an inferred image, writes a Dockerfile, commits a recipe,
publishes an image or starts undeclared services.

## Alternatives

### `V0` — leave all selection inside `ci/verify`

- **Strength:** preserves project authority, the existing suite interface and
  complex project-specific setup without a Gnostoa orchestrator.
- **Gap:** an opaque wrapper result cannot show which runtime executed, whether
  a declared image was preferred or whether missing host tools were considered
  only after viable container routes. It cannot independently distinguish a
  route declaration from an observation.
- **Disposition:** retain `ci/verify` as executor, but do not leave selection
  and evidence entirely opaque.

### `V1` — declare routing in `verification.yaml`

- **Strength:** gives `adoption-check` one validated project-owned authority
  from which to derive precedence, prevents prompt-specific route flags and can
  keep expected identities separate from observed actuals.
- **Gap:** the current schema represents only toolkit or one mandatory project
  image. A general list of build commands, service settings or native setup
  would become a new orchestration DSL and duplicate project authority.
- **Disposition:** recommended only as a narrow selector for already-owned
  routes, paired with `ci/verify` execution and runtime observation. Do not put
  container recipes or dependency-install commands in the manifest.

### `V2` — Gnostoa-managed container execution

- **Strength:** a thin runner can directly bind an already-declared immutable
  image digest and isolate host dependencies.
- **Gap:** interpreting Dockerfiles, Dev Containers or Compose would make
  Gnostoa responsible for build contexts, secrets, platforms, volumes,
  services, networks and cleanup. It would also bypass project-owned suite
  setup.
- **Disposition:** reject general management. A later implementation may admit
  only thin execution of an existing digest-pinned project image while still
  invoking `ci/verify` inside it; all build and service orchestration stays
  project-owned.

### `V3` — synthesize a temporary container

- **Strength:** could supply absent host dependencies in a synthetic fixture.
- **Gap:** dependency files and CI fragments do not define a complete,
  authoritative runtime. Synthesis invents base, packages, services, build
  order and security choices, and its passing result would not be the
  project's declared verification route.
- **Disposition:** rejected. No generator, inferred Dockerfile, temporary
  recipe, image publication or committed artifact is justified.

## Smallest recommended mechanism

Recommend a **narrow declarative selector plus project-owned execution and
observation**:

1. preserve `./ci/verify <suite>` as the sole normal project-suite entry;
2. let the validated verification manifest identify only already-authoritative
   candidate route kinds and immutable expectations, in the fixed
   image/container/native precedence above;
3. require the project adapter to enter the selected existing route and expose
   a bounded, machine-readable observation of the runtime actually used;
4. let `adoption-check` validate that observation, capture the suite result and
   aggregate unavailable routes without building or provisioning anything; and
5. block when a declaration lacks a measured counterpart or no declared route
   can execute.

This is smaller than a Gnostoa runner or synthesized environment, but it is not
already covered by Decision 0047's assumption that implementation changes no
existing project file format. The current verification schema cannot express
the generic route set, and the current `ci/verify` contract has no runtime
observation handshake. Therefore implementation is **not yet admitted** under
Decision 0047 alone. Accountable-owner selection must first bind the exact
minimal manifest and adapter compatibility change, or select a still-narrower
contract that supplies equivalent direct observations without changing those
surfaces. This assessment creates no new Decision and changes no selection.

## Prospective implementation and negative-test boundary

If the owner selects the recommendation, the smallest coherent implementation
must be reclassified as `normative` and is expected to touch the existing
verification schema/checker/template, the `ci/verify` template/contract,
`adoption-check`, focused tests and the existing adoption/CI guidance only.
Exact fields and observation format must be frozen before editing. No new
configuration file, recipe language or provider adapter is justified.

Focused tests must prove at least that:

1. a declared or caller-supplied image digest cannot produce route or runtime
   `PASS` without observed execution of that digest;
2. a Gnostoa toolkit image cannot satisfy an adopter project-runtime result;
3. a viable declared digest image is attempted before native host dependency
   checks;
4. an unavailable higher-priority route may fall through only to another
   already-declared route, while an executed test failure cannot fall through;
5. an undeclared Dockerfile, Dev Container, Compose file or CI fragment is not
   built, entered or converted into a route;
6. a declared project-container route with no bound runtime observation is
   `BLOCKED`, not `PASS`;
7. an isolated native result records actual tool identities and becomes
   `BLOCKED` when required tools are absent;
8. absent host PHP/Composer does not decide aggregate availability before all
   higher-priority declared routes are resolved;
9. no route writes a recipe, installs dependencies, changes canonical bytes or
   turns mechanical suite success into semantic acceptance; and
10. all route attempts, exits, observations and hashes are retained on both
    `FAIL` and `BLOCKED` paths.

Compatibility review must cover existing manifests with `runtime.image`, the
placeholder project template, provider `expected-runtime-image` checks, native
projects and projects whose `ci/verify` already owns containers or services.
Any public schema, template, adapter or CLI change requires a later source and
runtime release before general consumers can rely on it. This analysis selects
no version or publication effect.

## Later falsification and stop

Nextcloud Mail may be used only after implementation and a separate
pre-registration. The later contract must freeze the same Mail source subject,
the exact new Gnostoa documentation/toolkit/runtime subjects, the authoritative
Mail verification routes visible at that source, the environment and the
evidence bundle. It must not generate a Mail container route or pre-supply
project facts.

The routing mechanism is falsified if it treats the Gnostoa runtime as Mail's
project runtime, blocks on missing host dependencies before resolving an
already-declared viable route, executes an undeclared or synthesized route,
falls back after a real test failure, accepts declaration-only identity, loses
route evidence or returns mechanical/semantic adoption acceptance. If no
declared Mail route can execute, exit `3` with retained `BLOCKED` evidence is
the expected correct result, not a failed product claim.

No implementation, guidance/runtime change, Mail experiment, release, OCI
effect, B3 result, Decision-0036 result or Gnostoa self-verification Docker-build
efficiency work is admitted here. The next step is accountable-owner review of
this routing recommendation and its Decision-0047 compatibility boundary.
