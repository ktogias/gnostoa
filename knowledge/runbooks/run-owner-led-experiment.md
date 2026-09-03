---
type: Runbook
title: Run a bounded owner-led experiment
description: Use the Gnostoa-self experiment trust-domain pipeline without widening filesystem, credential, network, lifecycle, handoff or package authority during a controlled owner-led trial.
status: draft
generated:
  by: chatgpt/gpt-5.6-sol
  at: "2026-09-02T20:55:00Z"
sources:
  - id: runner-work-item
    resource: https://github.com/ktogias/gnostoa/issues/164
    title: Harden owner-led experiment runner write boundaries
  - id: final-security-red
    resource: https://github.com/ktogias/gnostoa/issues/164#issuecomment-5522263656
    title: Final-security RED after full-GREEN static review
  - id: final-security-code-green
    resource: https://github.com/ktogias/gnostoa/issues/164#issuecomment-5522547836
    title: Final-security repair code-only GREEN
  - id: evidence-publication-red
    resource: https://github.com/ktogias/gnostoa/issues/164#issuecomment-5523078440
    title: Final evidence-publication RED
  - id: evidence-publication-code-green
    resource: https://github.com/ktogias/gnostoa/issues/164#issuecomment-5523192829
    title: Evidence-root namespace repair code-only GREEN
  - id: relay-evidence-red
    resource: https://github.com/ktogias/gnostoa/issues/164#issuecomment-5523325006
    title: Restricted-network evidence completeness RED
  - id: relay-evidence-green
    resource: https://github.com/ktogias/gnostoa/issues/164#issuecomment-5523430235
    title: Restricted-network evidence completeness repair full GREEN
  - id: docker-object-ownership-red
    resource: https://github.com/ktogias/gnostoa/issues/164#issuecomment-5523578087
    title: Docker control-plane ownership authoritative RED
  - id: docker-object-ownership-green
    resource: https://github.com/ktogias/gnostoa/issues/164#issuecomment-5523862673
    title: Docker control-plane ownership code-only GREEN
x-project-knowledge:
  id: kit.runbook.run-bounded-owner-led-experiment
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0057-enforce-owner-led-experiment-boundaries-with-coordinator-owned-sandboxes.md
    - kind: governed-by
      target: /decisions/0005-container-first-runtime.md
    - kind: depends-on
      target: /lifecycles/evidence-gated-capability-evolution.md
---

# Run a bounded owner-led experiment

**Scope: Gnostoa-self controlled experiments only.** This runbook does not create
a public adopter sandbox contract, claim complete host isolation, or make an
agent's semantic diagnosis correct.

The trusted coordinator owns sandbox construction, host/container control,
network relay, executor lifecycle, evidence capture, candidate freezing and
package publication. The untrusted experiment process must not receive
container-control authority or the ability to widen its declared boundary.

## Trust-domain lifecycle

Use the components as a sequence, not as interchangeable helpers:

```text
validate profile / probe backend / boundary smoke
                    |
                    v
       docker create executor -> retain ID
                    |
                    v
        start/attach owned executor ID
                    |
       exit / timeout / failure occurs
                    |
                    v
      inspect/reap/verify absence by ID
                    |
         restricted network only
                    v
       stop relay ID / verify Running=false
                    |
          capture final relay log
                    |
                    v
      publish coordinator run evidence
                    |
                    v
       freeze candidate handoff
                    |
             verify handoff
                    |
                    v
     deterministic bounded package
                    |
          retain attestation
```

Packaging must never read the live mutable experiment workspace. If the owned
executor container ID has not been proved absent, do not publish completed run
evidence or start `freeze`. For restricted networking, an active or unverifiably
stopped relay ID is also a stop: capture final network evidence only after the
relay has been verified `Running=false`. If `freeze` has not produced a
verifiable handoff, do not start packaging.

## Coordinator CLI surfaces

### Execution

```text
python tools/experiment_runner.py validate-profile --profile PROFILE
python tools/experiment_runner.py probe --backend auto|oci|bwrap
python tools/experiment_runner.py smoke --backend auto|oci|bwrap --network restricted
python tools/experiment_runner.py run --profile PROFILE --backend auto|oci|bwrap -- COMMAND ...
```

The runner also exposes bounded coordinator utilities:

```text
attest --artifact PATH --producer-id ID --producer-version VERSION \
       --config-sha256 SHA256 [--input ID=SHA256 ...]
check-size --path PATH --max-bytes BYTES
```

`_relay` is an internal coordinator helper and is not experiment-facing.

### Frozen handoff

After the executor ID has been proved absent and, for restricted mode, the relay
ID has been quiesced and its final log retained:

```text
python tools/experiment_handoff.py freeze \
  --root /absolute/disposable-candidate \
  --bundle /absolute/create-only/handoff-run-N \
  --input run-result=<64-hex-digest> \
  --input task=<64-hex-digest>
```

Then verify the retained subject independently:

```text
python tools/experiment_handoff.py verify \
  --handoff /absolute/create-only/handoff-run-N/handoff.json
```

### Deterministic package

The packager accepts a verified handoff only. There is deliberately no raw-root
package command:

```text
python tools/experiment_packager.py \
  --handoff /absolute/create-only/handoff-run-N/handoff.json \
  --output /absolute/create-only/candidate.tar \
  --max-bytes BYTES
```

Retain the packager JSON result together with the archive. The result binds the
archive SHA-256/byte count to the packager producer/version/configuration, the
handoff identity and the handoff's declared inputs.

## Profile contract

A run profile uses schema `gnostoa-experiment-runner-profile/v1` and declares
absolute prepared surfaces plus identity/provenance and an explicit lifecycle
limit:

```yaml
schema: gnostoa-experiment-runner-profile/v1
read_only_roots:
  - /absolute/prepared-input
project_root: /absolute/disposable-project
evidence_root: /absolute/evidence
temporary_roots:
  - /absolute/run-cache
excluded_roots:
  - /absolute/orchestration-private
environment_allowlist:
  - LANG
  - LC_ALL
credential_environment:
  - OPENCODE_API_KEY
input_identities:
  - prepared-tree=<64-hex-digest>
  - frozen-task=<64-hex-digest>
executor:
  id: opencode
  version: "1.18.26"
  config_sha256: <64-hex-digest>
  model: opencode/big-pickle
  small_model: opencode/big-pickle
network:
  mode: restricted
  allow:
    - opencode.ai:443
runtime:
  image: local-executor@sha256:<64-hex-digest>
  relay_image: gnostoa-runner@sha256:<64-hex-digest>
timeout_seconds: 1800
archive_limit_bytes: 67108864
```

The values above are illustrative. `timeout_seconds` is a required positive
per-run policy value; there is no universal Gnostoa execution timeout.
`archive_limit_bytes` is likewise a per-run policy parameter, not a universal
Gnostoa constant. `input_identities` are stable declared identities propagated
into retained run-output attestations. Executor provenance is separate from the
immutable runtime image that is actually launched.

## Preconditions

1. The owning Work Item and Decision/Plan explicitly admit the experiment.
2. Task, admitted inputs, excluded surfaces, executor/model configuration,
   timeout and runtime identity are frozen as required by that experiment.
3. Runtime and relay images already exist locally and are identified immutably;
   the runner must not silently turn a missing image into an unrecorded pull.
4. Required credential environment names are explicit and secret values remain
   outside canonical evidence.
5. Every declared input has an `id=sha256` identity and executor provenance has
   at least `id`, `version` and `config_sha256`.
6. Dependencies that are not candidate source are prepared outside the candidate
   root and admitted separately as read-only inputs where required.
7. No admitted read-only root overlaps any writable project, evidence or
   temporary root in either ancestor direction.
8. Host paths used as Docker bind sources are valid for the selected `--mount`
   grammar; the current profile rejects `,` in those source paths.
9. `validate-profile` returns `VALID`.
10. `probe` returns `AVAILABLE` for the intended backend.
11. The exact runner/runtime candidate passes the full boundary smoke for that
    backend before experiment evidence is accepted.

A failed capability probe is `BLOCKED`. Never fall back to an unrestricted host
process and never report a weaker backend/network route as equivalent.

## Procedure

1. **Prepare isolated surfaces.** Create a disposable project workspace, a
   distinct evidence root and declared temporary/cache roots. Do not use the real
   source checkout as the writable experiment workspace.
2. **Separate dependencies from candidate source.** Prefer immutable dependencies
   outside `project_root`; admit them separately. Do not rely on guessed names
   such as `node_modules` being excluded later.
3. **Bind identities and lifecycle policy.** Record exact task/input identities,
   executor/model configuration, immutable runtime/relay image identities and
   the explicit positive `timeout_seconds` before launch.
4. **Validate.** Reject broad `/` read admission, lexical traversal,
   symlink-resolved roots, excluded/admitted overlap, read-only/writable overlap,
   Docker mount-source grammar hazards, malformed egress targets or incomplete
   run identity.
5. **Probe.** The current implementation qualifies the coordinator-owned OCI
   route. Bubblewrap remains deliberately `BLOCKED` until separately qualified.
6. **Smoke.** Run the exact-candidate boundary smoke. Any status other than
   `PASS` is a stop for that backend/profile claim.
7. **Create and run the owned executor.** Before untrusted execution, the
   coordinator opens and inode-binds the declared evidence root and checks all
   reserved evidence names relative to that descriptor. It then runs `docker
   create` for the exact sandbox/command and records the full container ID
   returned by the trusted daemon. Only that returned ID is ownership authority.
   With the ID acquired, start the executor via `docker start --attach ID` under
   the profile's `timeout_seconds` and read its terminal exit state from the
   daemon by ID.
8. **Stop if executor ownership/absence or evidence namespace is unproven.**
   Normal exit, command failure, timeout and local Docker-client failure converge
   on the same gate: reap/inspect only the owned executor ID and verify its
   absence. If creation failed before an ID was returned, do not attempt cleanup
   through a generated/intended name. If absence cannot be proved, or if the
   caller-visible evidence-root path no longer identifies the pre-launch opened
   directory, treat the run as `BLOCKED`. Do not publish completed run evidence
   and do not freeze the candidate.
9. **Quiesce restricted-network evidence producer.** For `network.mode:
   restricted`, use the daemon-returned relay container ID: inspect running state,
   stop that ID if still active and verify `Running=false`. Only then capture
   `docker logs` by ID into coordinator-private staging. If relay state cannot be
   inspected, stopped or verified, treat the run as `BLOCKED`; do not retain an
   active-producer log snapshot as completed network evidence.
10. **Retain run evidence.** Only after executor absence, evidence-root identity
    and any required relay quiescence are established, publish `run-stdout.log`,
    `run-stderr.log`, `run-result.json` and, for restricted networking,
    `run-network.jsonl` create-only relative to the retained evidence-root
    descriptor. Record the SHA-256 identity of `run-result.json` as an input to
    the handoff where it is material to candidate derivation.
11. **Freeze.** Invoke `experiment_handoff.py freeze` on the exact post-run
    candidate root into a fresh create-only handoff bundle. Treat `BLOCKED` as a
    stop; do not package the live project instead.
12. **Verify.** Invoke `experiment_handoff.py verify` on the retained
    `handoff.json`. Verification canonicalizes the retained manifest location and
    recomputes the complete member/content identity; a lexical alias is not
    authority.
13. **Package.** Invoke `experiment_packager.py --handoff ... --max-bytes ...` to
    a fresh output name. The packager enforces the byte ceiling while streaming;
    `OVERSIZE`/`BLOCKED` is a stop and leaves no successful package claim.
14. **Retain package identity.** Keep archive bytes plus the structured package
    result. Do not replace that result with a bare SHA-256.
15. **Perform trial-specific closeout.** Run any oracle, semantic review,
    dependency recheck and accountable-owner lifecycle gates required by the
    experiment. The mechanical pipeline does not replace semantic disposition.

## Execution filesystem boundary

For the qualified OCI route, the coordinator launches the experiment with:

- a read-only container root filesystem;
- all Linux capabilities dropped and `no-new-privileges` enabled;
- admitted inputs mounted read-only under `/inputs/`;
- only the disposable project, evidence and declared temporary roots writable;
- excluded host roots not mounted;
- no Docker/container-control socket mounted into the experiment; and
- a clean environment populated only from declared ordinary/credential names.

Read-only roots and writable roots must be host-path disjoint in both ancestor
directions. This is validated before Docker command construction so a second
writable bind cannot silently grant write access to a subtree that another mount
calls read-only.

The current Docker `--mount` construction also rejects bind-source paths
containing `,`; they are not interpolated into a comma-delimited grammar with
ambiguous option semantics.

The Docker/container daemon is a **trusted coordinator dependency**. This profile
is not a claim that containers isolate an experiment from a hostile daemon or
host administrator.

## Docker object ownership boundary

A generated Docker name is never cleanup authority. Generated names may be used
only as creation labels or DNS aliases where the Docker topology needs them.
Destructive lifecycle operations use the full object IDs returned by successful
coordinator creation.

For a real executor, the coordinator acquires the container ID with `docker
create` before untrusted execution begins. `start --attach`, exit-state inspect,
forced reap and absence verification all target that ID. For restricted mode,
the internal network, external network and relay container are likewise retained
by daemon-returned IDs. If setup fails part-way, cleanup may target only IDs that
were actually returned before the failure; a failed creation with no returned ID
authorizes no guessed-name stop/remove.

The host-level smoke uses the same rule for its internal/external networks,
target container, relay container and adversarial probe container. This makes the
ownership invariant part of the behavior tested before reuse, rather than a
production-only convention.

## Executor lifecycle boundary

A real run has no hidden default timeout. `timeout_seconds` is an explicit
positive profile field and part of the run policy.

The executor container is created before it is started, and its daemon-returned
full ID is retained as the coordinator ownership handle. A timeout of the local
Docker client is not treated as proof that the executor stopped. Before any
completed run evidence is published, the coordinator verifies absence by that
owned ID; if the container still exists it is force-removed by ID and absence is
checked again. A failed, timed-out or unverifiable reap is a mechanical
`BLOCKED` condition.

An unavailable requested backend also returns non-zero `BLOCKED`. It must not be
mistaken for a successful run merely because no experiment process started.

## Network boundary

`network.mode: none` uses a no-network experiment namespace.

`network.mode: restricted` uses a coordinator-owned topology:

1. the experiment joins an internal-only network identified by its owned daemon
   network ID;
2. a trusted CONNECT relay joins that network and a separate externally connected
   network, with both networks retained by daemon IDs;
3. the experiment receives proxy variables naming the relay's DNS alias; and
4. the relay admits only exact predeclared `host:port` targets.

The smoke test must prove both admitted configured egress and refused
undeclared/direct egress. The provider connection is an admitted external
service, so this is not offline execution.

The relay is a concurrent evidence producer. After executor absence, the
coordinator inspects the owned relay ID, stops it if necessary and verifies
`Running=false` before retaining `docker logs` by that same ID. The stopped
container remains available until log capture completes and is removed by ID
only during final cleanup. An active relay log snapshot is not a completed
network-evidence state.

If the topology, relay policy, Docker-object ownership or relay-quiescence
lifecycle cannot be enforced, return `BLOCKED`/`FAIL`; never inherit host
networking or treat an active relay snapshot as equivalent.

## Coordinator evidence boundary

Command stdout/stderr are captured first in coordinator-private staging outside
all experiment-mounted roots. Before the experiment starts, the coordinator
opens the evidence-root directory without following a symlink, records its inode
identity and checks the reserved output names relative to that open directory.
The descriptor remains authoritative across execution, executor reap, relay
quiescence and publication.

After the owned executor container ID has been proved absent, the caller-visible
evidence-root pathname must still identify that same opened directory. Reserved
names are checked again. For restricted networking, the owned relay ID must then
be verified stopped and its logs captured into coordinator-private staging.
Stdout, stderr, optional network evidence and the final `run-result.json` commit
marker are then created create-only/no-follow relative to the retained
descriptor. The evidence directory is fsynced and its visible identity is checked
again after the commit marker.

A pre-existing regular file, symlink or other reserved evidence entry is a
fail-closed collision. Replacement of the evidence-root directory itself is also
a fail-closed namespace change; the coordinator does not redirect completed
evidence into the replacement. Use a fresh evidence root; do not overwrite
retained or foreign output.

Run attestations bind SHA-256, byte count, producer/version, run configuration
and declared input identities. `run_config_sha256` binds profile bytes, requested
backend, resolved backend and exact command argv; because the timeout is a
profile field it is part of the bound profile identity. Requested and resolved
backend identities are retained separately.

## Frozen handoff boundary

The handoff is a copied, frozen subject rather than a promise about the live
workspace.

During `freeze`:

- source entries are opened without following symlinks;
- regular files are fstat-checked before and after copy/hash;
- symlinks are preserved as symlinks and their targets are not dereferenced;
- canonical member identities are path-neutral and ordered deterministically;
- `handoff.json` binds tree identity, producer/configuration and declared inputs;
- the destination bundle is create-only; and
- after opening the destination parent, creation remains descriptor- and
  inode-owned until the manifest commit point.

The coordinator records the inode identity of the newly created bundle
immediately after `mkdir` and opens it relative to the retained parent
descriptor. Parent and bundle identities are rechecked before commit. A
same-name foreign replacement is never treated as the coordinator-created
bundle.

Failure before `handoff.json` is committed is deliberately non-destructive. An
already-created partial bundle may remain as diagnostic state; it is not a valid
handoff because the manifest commit marker is absent. Do not recursively delete
partial state through a later pathname lookup, and never delete a same-name
foreign replacement.

If the caller-visible bundle parent is replaced before commit, freeze fails
closed rather than redirecting creation into the replacement namespace. The
manifest is written last as the bundle commit marker.

`verify` canonicalizes the manifest locator before returning the retained
`manifest_path`, `bundle_root` and `snapshot_root`, then reparses the manifest and
recomputes the frozen snapshot member/content identity. Treat later host-level
mutation as evidence invalidation, not as an implicitly immutable filesystem
guarantee.

## Packaging boundary

The packager consumes a verified handoff only. It never chooses a candidate by
walking the mutable live project root. Output containment is checked against the
canonical verified bundle root, so a symlink alias cannot disguise an output
inside the handoff bundle.

Its archive contract is deterministic PAX tar with normalized uid/gid/user/group,
mtime and mode metadata, handoff-defined ordering and no symlink dereference.
Snapshot files are read through descriptor-relative no-follow opens and checked
against their handoff digest/size.

The configured byte limit is a **hard streaming ceiling**. A write that would
exceed it is refused before those bytes are written; the whole archive is not
allocated in memory to measure it. `check-size` remains useful for other already
materialized objects but is not a substitute for the packager's own streaming
limit.

Destination handling is descriptor-bound:

- the output parent is opened and identified before staging;
- qualified Linux staging uses an unnamed `O_TMPFILE`, so no staging pathname
  exists for another actor to replace;
- the staging descriptor stays open through stream, fsync and hashing;
- hashing never reopens staging by pathname;
- before publication the caller-visible parent must still identify the opened
  parent inode;
- final publication is a create-only link from the open staging descriptor into
  the retained parent;
- the published inode must equal the staged inode; and
- after successful create-only publication, later uncertainty does not trigger a
  destructive rollback by output pathname.

Caller-visible parent replacement and foreign-output collision therefore fail
closed without redirecting publication or deleting a foreign path. If unnamed
staging is unavailable, the qualified packaging route is `BLOCKED` rather than
silently falling back to weaker named staging.

A successful return binds the bytes at that commit point. It is not a promise
that a hostile root/administrator cannot later rewrite filesystem namespace or
retained storage.

## Candidate/dependency boundary

The handoff freezes exactly the root it is given; it has no universal exclusion
list. Therefore:

- keep immutable dependencies outside the candidate root whenever they are not
  intended candidate material;
- bind those dependencies as separate run inputs;
- if dependency content is physically inside the root passed to `freeze`, it is
  candidate content and will be frozen; and
- changing that boundary requires an explicit experiment decision, not a hidden
  `node_modules`/cache heuristic.

This preserves the Phase-C lesson without baking experiment-specific directory
names into Gnostoa.

## Golden determinism contract

The packaging test fixture has one fixed expected PAX-tar SHA-256. Independent
Python 3.11 and Python 3.12 hosted CI workers each freeze equivalent source trees
and must reproduce those exact bytes/digest.

A changed golden digest is not updated as formatter churn. It means the package
byte contract changed and requires explicit review of the producer/configuration
identity and compatibility consequences.

The cross-worker result is bounded evidence for the tested Linux/Python/tarfile
surface, not proof of byte identity on every possible platform implementation.

## Recovery

- **Invalid profile:** fix the declaration/prepared surfaces under owning
  authority; never widen to `/`, allow read-only/writable overlap, pass unsafe
  mount-source syntax or disable path validation.
- **Backend `BLOCKED`:** stop or move to another already-qualified environment;
  never silently use unrestricted host execution.
- **Docker creation fails before an object ID is returned:** stop. Do not inspect,
  stop or remove a generated/intended name; no destructive ownership authority
  was acquired.
- **Executor timeout:** treat it as a mechanical stop until the owned executor ID
  is proved absent. Do not assume the Docker client timeout killed the executor.
- **Executor reap/absence cannot be verified by ID:** `BLOCKED`; retain diagnostics
  but do not publish completed run evidence or freeze the candidate.
- **Relay state/stop/quiescence cannot be verified by ID:** `BLOCKED`; do not
  retain an active-producer relay log as completed network evidence. The relay
  may be removed during cleanup only by its owned ID after any valid
  stopped-producer log capture.
- **Boundary smoke `FAIL`:** retain the smoke result and do not use that exact
  backend/candidate for experiment evidence.
- **Restricted egress failure:** retain only evidence that satisfies the same
  stopped-producer lifecycle; do not bypass the relay or inherit host networking.
- **Reserved evidence collision or evidence-root namespace change:** `BLOCKED`;
  use a fresh evidence root and never overwrite or redirect into replacement
  state.
- **Handoff `BLOCKED`:** retain incomplete coordinator-owned bundle state as
  diagnostic material when present; absence of `handoff.json` means it is not a
  handoff. Never delete a same-name foreign replacement and never package the
  live workspace as a workaround.
- **Handoff verification failure:** treat the retained subject as invalidated.
- **Package `OVERSIZE`:** stop. Change candidate boundary or size policy only
  through accountable authority.
- **Unnamed package staging unavailable, package output collision or output-parent
  namespace change:** stop; do not fall back to named staging, overwrite output
  or roll back a possibly replaced output name.
- **Host loss:** reconstruct only from durable profile/input/executor/runtime,
  handoff and package identities. Do not infer a producer for a bare digest.

## Verification

The #164 capability is review-ready only when the **same exact candidate** passes:

1. unsafe baseline fixtures that still demonstrate the pre-runner failure modes;
2. architecture tests proving thin CLIs, no private execution monolith and the
   one-way handoff/packaging import graph;
3. focused runner/evidence-substitution/backend-identity regressions, including
   reserved evidence-name collisions and evidence-root namespace replacement;
4. restricted-network lifecycle regression proving the relay ID is stopped and
   verified `Running=false` before final relay-log retention;
5. Docker object-ownership regressions proving failed creation never cleans up a
   guessed name, partial creation cleans only returned IDs, topology returns IDs,
   the executor ID is acquired before start, and smoke uses the same ownership
   rule;
6. final-security regressions for read-only/writable disjointness, mount grammar,
   explicit timeout, owned-ID reap and non-zero backend `BLOCKED`;
7. handoff tests for determinism, mutation, symlink no-dereference, create-only
   publication, parent-namespace replacement and non-destructive uncommitted
   failure state;
8. package tests for the fixed golden digest, normalized metadata, handoff-only
   input, canonical containment, mutation, oversize, parent replacement,
   unnamed staging and foreign-output replacement/publication behavior;
9. Python 3.11 and 3.12 source suites;
10. Ruff and strict mypy for the experiment trust domains;
11. the OCI host-level boundary smoke with every required check true;
12. normal Gnostoa `policy`, `fast`, `regression` and `smoke`; and
13. final exact PR executable-candidate binding.

A mechanical `PASS` proves only the tested Gnostoa-self boundary. It does not
prove semantic task correctness, model independence, resistance to a hostile
host/kernel/container administrator, or equivalence of an unqualified backend.