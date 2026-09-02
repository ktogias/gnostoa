---
type: Runbook
title: Run a bounded owner-led experiment
description: Use the Gnostoa-self experiment runner without widening filesystem, credential, network or evidence authority when a controlled owner-led trial needs a reusable execution boundary.
status: draft
generated:
  by: chatgpt/gpt-5.6-sol
  at: "2026-09-02T20:55:00Z"
sources:
  - id: runner-work-item
    resource: https://github.com/ktogias/gnostoa/issues/164
    title: Harden owner-led experiment runner write boundaries
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
a public adopter sandbox contract and does not claim complete host isolation.
The trusted coordinator owns Docker/network construction; the experiment process
must not receive container-control authority or permission to widen its own
boundary.

## Runner surface

Use `python tools/experiment_runner.py` from a reviewed Gnostoa candidate. The
supported coordinator commands are:

```text
validate-profile --profile PROFILE
probe --backend auto|oci|bwrap
smoke --backend auto|oci|bwrap --network restricted
attest --artifact PATH --producer-id ID --producer-version VERSION \
       --config-sha256 SHA256 [--input ID=SHA256 ...]
check-size --path PATH --max-bytes BYTES
run --profile PROFILE --backend auto|oci|bwrap -- COMMAND ...
```

`_relay` is an internal coordinator helper, not an experiment-facing command.

## Profile contract

A run profile is local Gnostoa-self input with schema
`gnostoa-experiment-runner-profile/v1`. It declares absolute, already-created
host paths, input identities, executor/configuration provenance and immutable
runtime identities:

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
archive_limit_bytes: 67108864
```

The values above are illustrative. The archive limit is a per-run parameter,
not a universal Gnostoa constant. `input_identities` are stable declared
identities that every retained run-output digest carries forward. The executor
mapping records identity/provenance only; the immutable runtime image remains
the executable authority actually launched by the coordinator.

## Preconditions

1. The Work Item has explicit implementation/execution authority for the trial.
2. Exact task, inputs, executor/model configuration and excluded surfaces are
   frozen as required by the trial design.
3. Runtime and relay images are already present locally and are identified by
   immutable digest. The runner does not turn a missing image into an implicit
   registry pull.
4. Required credential environment names are explicit. Secret values remain
   outside retained canonical evidence.
5. Every declared run input has a stable `id=sha256` identity and executor
   provenance includes `id`, `version` and `config_sha256`.
6. `validate-profile` returns `VALID`.
7. `probe` returns `AVAILABLE` for the selected backend.
8. The same runner candidate passes the retained `smoke` package on that backend
   before it is reused for experiment evidence.

A failed capability probe is `BLOCKED`. Never fall back to an unrestricted host
process and never report a weaker network/filesystem route as equivalent.

## Procedure

1. Create a disposable project workspace, a separate evidence directory and any
   explicitly required temporary/cache directories. Do not reuse the real source
   checkout as the writable experiment workspace.
2. Materialize only the exact admitted read-only inputs and calculate the
   `input_identities` recorded in the profile.
3. Bind the executor/model configuration and immutable runtime/relay image
   identities before launch. Do not use mutable image tags for a real run.
4. Validate the profile. Any invalid path, broad `/` read root, symlink-resolved
   root, overlap with an excluded surface, malformed egress target or incomplete
   run identity is a stop.
5. Probe the required backend. For the current implementation only the
   coordinator-owned OCI route can become `AVAILABLE`; Bubblewrap remains
   visible but deliberately `BLOCKED` until separately qualified.
6. Run the boundary smoke on the exact runner/runtime candidate before reuse.
   A result other than `PASS` is a stop for that profile/backend claim.
7. Launch the exact admitted command with `run`. The remainder after `--` is
   appended as argv to the immutable image's configured entrypoint; it does not
   replace that entrypoint or create a second unbound executable authority.
8. Preserve `run-stdout.log`, `run-stderr.log`, `run-result.json` and, for the
   restricted-network profile, `run-network.jsonl` in the bounded evidence
   directory. The result binds backend/argv/profile into `run_config_sha256`,
   retains executor provenance and propagates all declared input identities into
   the generated output attestations.
9. If the experiment separately materializes a candidate/archive for sealing,
   run `check-size` on that exact materialized object before any helper reads the
   complete payload into memory. Treat `OVERSIZE` as a stop.
10. Perform the trial-specific post-run identity, dependency and lifecycle
    checks required by its owning Decision/Plan. The experiment runner does not
    replace semantic review, oracle execution or accountable-owner disposition.

### Filesystem boundary

For the OCI backend the coordinator launches the experiment with:

- a read-only container root filesystem;
- all Linux capabilities dropped and `no-new-privileges` enabled;
- admitted inputs mounted read-only under `/inputs/`;
- only the disposable project, evidence and declared temporary roots writable;
- excluded host roots not mounted at all;
- no Docker/container-control socket mounted into the experiment process; and
- a clean environment populated only from the declared ordinary and credential
  environment names.

The profile rejects `/` as a read root, lexical traversal and declared roots
whose path resolution crosses a symlink. Disposable Git metadata belongs inside
the writable project workspace; real host repository metadata is not implicitly
admitted.

### Network boundary

`network.mode: none` uses an isolated no-network container.

`network.mode: restricted` uses two coordinator-owned networks:

1. the experiment process joins an internal-only network;
2. a trusted CONNECT relay joins that network and a separate external network;
3. the experiment receives proxy variables naming only that relay; and
4. the relay admits only exact predeclared `host:port` targets and returns a
   refusal for everything else.

The relay uses blocking tunnel writes. It must not reproduce the Phase-C defect
where non-blocking `sendall` failures were mistaken for closed connections.
Restricted egress is therefore a real mechanical claim only when the smoke test
proves both an admitted connection and a refused undeclared connection. If the
executor ignores the proxy or the topology cannot be enforced, the run is
`BLOCKED` or `FAIL`, not silently widened.

The relay JSONL log is retained and content-addressed as network evidence for a
real restricted run; it records connection disposition without retaining
credential values.

### Evidence and size boundary

The coordinator streams command stdout/stderr directly to the evidence root;
it does not collect unbounded command output in memory. Retained output
identities include SHA-256, byte count, producer ID/version, run-configuration
digest and declared input identities. `run_config_sha256` binds the profile
digest, selected backend and exact command argv.

The run result may retain a metadata-only workspace-size observation when the
profile declares an archive limit. That observation is **not** an archive-size
substitute. Before any later sealing/materialization helper is called, run
`check-size` on the exact materialized candidate/archive path using the trial's
configured limit. The size check uses filesystem metadata rather than reading
the full file into memory. `OVERSIZE` is a stop condition; do not seal first and
discover the overshoot afterward.

The runner's `run` result keeps semantic owner interventions separate from
mechanical boundary controls. Mechanical mount/network/environment controls,
denials and capability stops are not semantic owner assistance.

### Reuse boundary

The current implementation qualifies the coordinator-owned OCI route. A native
Bubblewrap route is visible to capability probing but remains fail-closed as
`BLOCKED` until it receives its own behavioral qualification. Do not describe
binary presence as a qualified fallback.

Reusing the runner for another experiment requires a new trial-specific profile
and authority. Passing this runbook's smoke package does not establish semantic
correctness of an agent, task interpretation or candidate.

## Recovery

- **Invalid profile:** correct only the declaration or prepared disposable
  surfaces under the owning authority; do not relax validation or add `/` as a
  broad read root.
- **Backend `BLOCKED`:** stop the run. Install/qualify a permitted backend under
  separate authority or move to another already-qualified host. Never degrade to
  an unrestricted host process.
- **Boundary smoke `FAIL`:** retain the failed smoke output and investigate the
  mechanical control. Do not use the backend for experiment evidence until a
  later exact candidate passes the complete smoke package.
- **Restricted egress failure:** retain the relay evidence when available. Do not
  bypass the CONNECT relay, inherit host networking or describe a broader route
  as equivalent.
- **Existing evidence output:** treat `evidence-output-already-exists` as a stop;
  use a fresh evidence directory rather than overwriting retained artifacts.
- **Oversize candidate/archive:** stop before sealing. Change the admitted
  candidate boundary or size policy only through an accountable-owner decision;
  do not hide dependencies inside another unmeasured object.
- **Host loss:** reconstruct from the frozen profile/input/executor/runtime
  identities and published evidence. A bare digest whose producer or declared
  derivation is unknown is not silently reconstructed by inference.

## Verification

For the runner candidate itself, verification is complete only when all of the
following hold on the same candidate:

1. the unsafe baseline fixtures still demonstrate the pre-runner failure modes;
2. focused runner contract tests pass on supported Python versions;
3. Ruff formatting/lint and strict mypy pass for `tools/experiment_runner.py`;
4. the host-level OCI boundary smoke returns `PASS` with every required check
   true, including admitted exact egress, refused undeclared egress, excluded
   read denial, outside-write denial, symlink denial, clean environment and no
   container-control socket;
5. normal Gnostoa policy and source verification remain green; and
6. the final reviewed candidate is the same source head to which those results
   are bound.

A smoke `PASS` proves only the declared mechanical runner boundary on the tested
backend/candidate. It does not prove that a model will follow the task correctly,
that a behavioral map is semantically complete or that another host/runtime has
the same capability.
