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
host paths and immutable runtime identities:

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
not a universal Gnostoa constant.

## Preconditions

1. The Work Item has explicit implementation/execution authority for the trial.
2. Exact task, inputs, executor/model configuration and excluded surfaces are
   frozen as required by the trial design.
3. Runtime and relay images are already present locally and are identified by
   immutable digest. The runner does not turn a missing image into an implicit
   registry pull.
4. Required credential environment names are explicit. Secret values remain
   outside retained canonical evidence.
5. `validate-profile` returns `VALID`.
6. `probe` returns `AVAILABLE` for the selected backend.
7. The same runner candidate passes the retained `smoke` package on that backend
   before it is reused for experiment evidence.

A failed capability probe is `BLOCKED`. Never fall back to an unrestricted host
process and never report a weaker network/filesystem route as equivalent.

## Filesystem boundary

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

## Network boundary

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

## Evidence and size boundary

The coordinator streams command stdout/stderr directly to the evidence root;
it does not collect unbounded command output in memory. Retained output
identities include SHA-256, byte count, producer ID/version, producer
configuration digest and declared input identities.

Before any later sealing/materialization helper is called, run `check-size` on
the already materialized candidate/archive path using the trial's configured
limit. The size check uses filesystem metadata rather than reading the full file
into memory. `OVERSIZE` is a stop condition; do not seal first and discover the
overshoot afterward.

The runner's `run` result keeps semantic owner interventions separate from
mechanical boundary controls. Mechanical denials, capability stops and sandbox
construction are not semantic owner assistance.

## Reuse boundary

The current implementation qualifies the coordinator-owned OCI route. A native
Bubblewrap route is visible to capability probing but remains fail-closed as
`BLOCKED` until it receives its own behavioral qualification. Do not describe
binary presence as a qualified fallback.

Reusing the runner for another experiment requires a new trial-specific profile
and authority. Passing this runbook's smoke package does not establish semantic
correctness of an agent, task interpretation or candidate.
