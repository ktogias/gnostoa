---
type: Runbook
title: Run a bounded owner-led experiment
description: Use the Gnostoa-self experiment trust-domain pipeline without widening filesystem, credential, network, handoff or package authority during a controlled owner-led trial.
status: draft
generated:
  by: chatgpt/gpt-5.6-sol
  at: "2026-09-02T20:55:00Z"
sources:
  - id: runner-work-item
    resource: https://github.com/ktogias/gnostoa/issues/164
    title: Harden owner-led experiment runner write boundaries
  - id: final-code-green
    resource: https://github.com/ktogias/gnostoa/issues/164#issuecomment-5521936064
    title: Final code-only GREEN
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
network relay, evidence capture, candidate freezing and package publication. The
untrusted experiment process must not receive container-control authority or the
ability to widen its declared boundary.

## Trust-domain lifecycle

Use the components as a sequence, not as interchangeable helpers:

```text
validate profile / probe backend / boundary smoke
                    |
                    v
          run untrusted executor
                    |
              executor exits
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

Packaging must never read the live mutable experiment workspace. If `run` has not
finished, do not start `freeze`; if `freeze` has not produced a verifiable
handoff, do not start packaging.

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

After the executor terminates:

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
absolute prepared surfaces plus identity/provenance:

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

The values are illustrative. `archive_limit_bytes` is a per-run policy parameter,
not a universal Gnostoa constant. `input_identities` are stable declared
identities propagated into retained run-output attestations. Executor provenance
is separate from the immutable runtime image that is actually launched.

## Preconditions

1. The owning Work Item and Decision/Plan explicitly admit the experiment.
2. Task, admitted inputs, excluded surfaces, executor/model configuration and
   runtime identity are frozen as required by that experiment.
3. Runtime and relay images already exist locally and are identified immutably;
   the runner must not silently turn a missing image into an unrecorded pull.
4. Required credential environment names are explicit and secret values remain
   outside canonical evidence.
5. Every declared input has an `id=sha256` identity and executor provenance has
   at least `id`, `version` and `config_sha256`.
6. Dependencies that are not candidate source are prepared outside the candidate
   root and admitted separately as read-only inputs where required.
7. `validate-profile` returns `VALID`.
8. `probe` returns `AVAILABLE` for the intended backend.
9. The exact runner/runtime candidate passes the full boundary smoke for that
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
3. **Bind identities.** Record exact task/input identities, executor/model
   configuration and immutable runtime/relay image identities before launch.
4. **Validate.** Reject broad `/` read admission, lexical traversal,
   symlink-resolved roots, excluded/admitted overlap, malformed egress targets or
   incomplete run identity.
5. **Probe.** The current implementation qualifies the coordinator-owned OCI
   route. Bubblewrap remains deliberately `BLOCKED` until separately qualified.
6. **Smoke.** Run the exact-candidate boundary smoke. Any status other than
   `PASS` is a stop for that backend/profile claim.
7. **Run.** Launch the exact admitted command. Wait for the runner to return; the
   executor must be terminated before candidate freezing begins.
8. **Retain run evidence.** Preserve `run-stdout.log`, `run-stderr.log`,
   `run-result.json` and, for restricted networking, `run-network.jsonl`. Record
   the SHA-256 identity of `run-result.json` as an input to the handoff where it
   is material to the candidate derivation.
9. **Freeze.** Invoke `experiment_handoff.py freeze` on the exact post-run
   candidate root into a fresh create-only handoff bundle. Treat `BLOCKED` as a
   stop; do not package the live project instead.
10. **Verify.** Invoke `experiment_handoff.py verify` on the retained
    `handoff.json`. Verification recomputes the complete member/content identity;
    the pathname alone is not authority.
11. **Package.** Invoke `experiment_packager.py --handoff ... --max-bytes ...` to
    a fresh output name. The packager enforces the byte ceiling while streaming;
    `OVERSIZE`/`BLOCKED` is a stop and leaves no successful package claim.
12. **Retain package identity.** Keep archive bytes plus the structured package
    result. Do not replace that result with a bare SHA-256.
13. **Perform trial-specific closeout.** Run any oracle, semantic review,
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

The Docker/container daemon is a **trusted coordinator dependency**. This profile
is not a claim that containers isolate an experiment from a hostile daemon or
host administrator.

## Network boundary

`network.mode: none` uses a no-network experiment namespace.

`network.mode: restricted` uses a coordinator-owned topology:

1. the experiment joins an internal-only network;
2. a trusted CONNECT relay joins that network and a separate external network;
3. the experiment receives proxy variables naming the relay; and
4. the relay admits only exact predeclared `host:port` targets.

The smoke test must prove both admitted configured egress and refused
undeclared/direct egress. The provider connection is an admitted external
service, so this is not offline execution. If the topology cannot be enforced,
return `BLOCKED`/`FAIL`; never inherit host networking and call it equivalent.

## Coordinator evidence boundary

Command stdout/stderr are captured first in coordinator-private staging outside
all experiment-mounted roots. They are published create-only into the evidence
root only after the executor terminates and are then attested. This prevents an
experiment from unlinking/replacing the capture pathname before the coordinator
hashes it.

A pre-existing reserved evidence name is a fail-closed collision. Use a fresh
evidence root; do not overwrite retained or foreign output.

Run attestations bind SHA-256, byte count, producer/version, run configuration
and declared input identities. `run_config_sha256` binds profile bytes, requested
backend, resolved backend and exact command argv. Requested and resolved backend
identities are retained separately.

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
- after opening the destination parent, creation/cleanup remain descriptor-bound.

If the caller-visible bundle parent is replaced before commit, freeze fails
closed and cleanup operates only on the originally opened directory. The
manifest is written last as the bundle commit marker.

`verify` uses a path to locate retained evidence but does not trust that path by
name: it reparses the manifest and recomputes the frozen snapshot member/content
identity. Treat later host-level mutation as evidence invalidation, not as an
implicitly immutable filesystem guarantee.

## Packaging boundary

The packager consumes a verified handoff only. It never chooses a candidate by
walking the mutable live project root.

Its archive contract is deterministic PAX tar with normalized uid/gid/user/group,
mtime and mode metadata, handoff-defined ordering and no symlink dereference.
Snapshot files are read through descriptor-relative no-follow opens and checked
against their handoff digest/size.

The configured byte limit is a **hard streaming ceiling**. A write that would
exceed it is refused before those bytes are written; the whole archive is not
allocated in memory to measure it. `check-size` remains useful for other already
materialized objects but is not a substitute for the packager's own streaming
limit.

Destination handling is also descriptor-bound:

- output parent is opened and identified before staging;
- staging is create-only in that opened directory;
- the staging file descriptor stays open through stream, fsync and hashing;
- hashing does not reopen the stage by pathname;
- final publication is a create-only link within the same opened directory;
- the published inode must equal the staged inode; and
- caller-visible parent replacement or foreign-output collision fails closed
  without deleting the foreign path.

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
  authority; never widen to `/` or disable path validation.
- **Backend `BLOCKED`:** stop or move to another already-qualified environment;
  never silently use unrestricted host execution.
- **Boundary smoke `FAIL`:** retain the smoke result and do not use that exact
  backend/candidate for experiment evidence.
- **Restricted egress failure:** retain available relay evidence; do not bypass
  the relay or inherit host networking.
- **Reserved evidence collision:** use a fresh evidence root; never overwrite.
- **Handoff `BLOCKED`:** discard/retain the incomplete bundle as diagnostic state
  per the owning plan; never package the live workspace as a workaround.
- **Handoff verification failure:** treat the retained subject as invalidated.
- **Package `OVERSIZE`:** stop. Change candidate boundary or size policy only
  through accountable authority.
- **Package publication collision/namespace change:** stop; do not delete or
  overwrite the foreign path.
- **Host loss:** reconstruct only from durable profile/input/executor/runtime,
  handoff and package identities. Do not infer a producer for a bare digest.

## Verification

The #164 capability is review-ready only when the **same exact candidate** passes:

1. unsafe baseline fixtures that still demonstrate the pre-runner failure modes;
2. architecture tests proving thin CLIs, no private execution monolith and the
   one-way handoff/packaging import graph;
3. focused runner/evidence-substitution/backend-identity regressions;
4. handoff tests for determinism, mutation, symlink no-dereference, create-only
   publication and parent-namespace replacement;
5. package tests for the fixed golden digest, normalized metadata, handoff-only
   input, mutation, oversize, foreign-output collision and parent replacement;
6. Python 3.11 and 3.12 source suites;
7. Ruff and strict mypy for the experiment trust domains;
8. the OCI host-level boundary smoke with every required check true;
9. normal Gnostoa `policy`, `fast`, `regression` and `smoke`; and
10. final exact PR executable-candidate binding.

A mechanical `PASS` proves only the tested Gnostoa-self boundary. It does not
prove semantic task correctness, model independence, resistance to a hostile
host/kernel/container administrator, or equivalence of an unqualified backend.
