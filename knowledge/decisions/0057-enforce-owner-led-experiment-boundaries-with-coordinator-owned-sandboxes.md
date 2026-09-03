---
type: Decision
title: Enforce owner-led experiment boundaries with coordinator-owned sandboxes
description: Select a Gnostoa-self experiment architecture that separates execution, frozen handoff and deterministic packaging into testable trust domains, uses coordinator-owned isolation and fails closed when the claimed boundary cannot be enforced.
status: draft
generated:
  by: chatgpt/gpt-5.6-sol
  at: "2026-09-02T20:09:00Z"
sources:
  - id: experiment-runner-work-item
    resource: https://github.com/ktogias/gnostoa/issues/164
    title: Harden owner-led experiment runner write boundaries
  - id: phase-b-runner-observation
    resource: https://github.com/ktogias/gnostoa/issues/164#issuecomment-5468096262
    title: Phase-B sandbox-v3 boundary outcome
  - id: phase-c-root-cause-analysis
    resource: https://github.com/ktogias/gnostoa/issues/179#issuecomment-5513492802
    title: Complete Phase-C retrospective and root-cause analysis
  - id: whiteboard-architecture-authority
    resource: https://github.com/ktogias/gnostoa/issues/164#issuecomment-5517958538
    title: Accountable-owner whiteboard architecture authority
  - id: final-security-red
    resource: https://github.com/ktogias/gnostoa/issues/164#issuecomment-5522263656
    title: Final-security RED after full-GREEN static review
  - id: final-security-code-green
    resource: https://github.com/ktogias/gnostoa/issues/164#issuecomment-5522547836
    title: Final-security repair code-only GREEN
x-project-knowledge:
  id: kit.decision.0057.enforce-owner-led-experiment-boundaries-with-coordinator-owned-sandboxes
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0005-container-first-runtime.md
    - kind: governed-by
      target: /decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md
    - kind: governed-by
      target: /decisions/0018-adopt-evidence-gated-capability-evolution-for-gnostoa-self-governance.md
    - kind: governed-by
      target: /decisions/0053-require-lightweight-work-item-micro-retrospection.md
    - kind: derived-from
      target: /assessments/nextcloud-mail-phase-a-owner-led-adaptation-retrospective.md
---

# Enforce owner-led experiment boundaries with coordinator-owned sandboxes

## Context

The owner-led Mail experiments showed that prompt and tool permissions are not a
sufficient experiment boundary. Phase A allowed file-edit capability to write
after an intended stop. Phase B demonstrated a stronger one-off filesystem
sandbox but also exposed a precursor in which a broad read-only bind still made
unrelated host material visible. Phase C added further evidence: one namespace
mechanism was unavailable on a real host, executor identities drifted until
explicitly pinned, dependency material inflated an assumed candidate boundary,
and several derived identities were not durable enough to survive host loss.

The first #164 implementation then exposed additional classes of defect through
RED-before-GREEN review:

- coordinator-captured evidence could be substituted if its pathname lived in a
  writable experiment surface;
- deterministic packaging had independent publication and namespace-race
  failure modes that did not belong inside execution code; and
- a final authority-focused read-back after an otherwise fully green CI run found
  that read-only and writable bind sources could overlap, a hidden fixed timeout
  could kill only the Docker client rather than prove executor termination, and
  name-based failure cleanup could delete a foreign replacement after namespace
  races.

The accountable owner therefore authorized a whiteboard redesign rather than a
minimal patch to the original monolithic runner. The resulting contract is not
"one safer script". It is a sequence of separately testable trust domains with a
frozen handoff between untrusted execution and deterministic packaging, explicit
lifecycle termination, and ownership-checked publication/cleanup.

This Decision remains Gnostoa-self-only. It does not establish a generic adopter
sandbox, complete operating-system isolation, or semantic correctness of an
agent or its diagnosis.

## Alternatives considered

| Alternative | Material benefit | Material limitation | Disposition |
| --- | --- | --- | --- |
| Prompt/OpenCode permissions only | Lowest machinery | Same host authority remains available through shell/editor capabilities | Rejected |
| One monolithic runner including execution and packaging | Simple call graph | One component creates evidence, chooses candidate semantics and validates its own packaging; unrelated failure modes become coupled | Rejected |
| Separate runner and packager but packager accepts a mutable raw directory | Cleaner files | Packaging can observe a different subject from the one execution intended to hand off | Rejected |
| Tool-permission-only isolation | Useful defense in depth | Cannot mechanically hide arbitrary host reads/writes or container-control authority | Rejected as an isolation backend |
| Bubblewrap-only | Small Linux-native boundary | Namespace capability is unavailable on some real hosts; binary presence does not prove usable isolation | Rejected as sole backend; retained unqualified and fail-closed |
| OCI-only | Explicit mount/network namespace surface | Container daemon is a trusted host dependency and is not universal | Selected as the currently qualified backend, not as a universal backend guarantee |
| VM/microVM backend | Can provide a stronger host boundary | Establishes a different backend assurance contract and is not required to validate the current Gnostoa-self filesystem/network/evidence contract | Deferred as a separately qualified future backend, not rejected on cost grounds |
| Execution -> frozen handoff -> independent deterministic packaging | Separates authority, failure modes and verification; permits packaging tests without execution | Requires explicit handoff identity and more lifecycle machinery | Selected |

## Decision

### A. Use explicit trust domains and one-way dependencies

The Gnostoa-self implementation is decomposed into owning modules rather than a
private execution monolith:

```text
profile.py   backend.py   relay.py   capture.py   smoke.py
     \           |          |          |          /
                  execution.py
                       |
               executor terminates
                       v
                   handoff.py ---> evidence.py
                       |
                       v
                  packaging.py ---> evidence.py
```

The dependency rule is structural:

- `handoff` may depend on shared evidence primitives but not on execution,
  backend, relay, capture, smoke or packaging;
- `packaging` may depend on the verified-handoff and evidence domains but not on
  execution or sandbox machinery; and
- public `experiment_runner.py`, `experiment_handoff.py` and
  `experiment_packager.py` files are thin CLI adapters, not second
  implementations.

The import graph and thin-adapter property are executable test contracts. The
separation is therefore observable rather than a documentation promise.

### B. Terminate untrusted execution before evidence publication, candidate freezing or packaging

The trusted coordinator owns sandbox construction, exact inputs, credentials,
egress, evidence capture and lifecycle transitions. The experiment process runs
inside the admitted sandbox and has no authority to create or reconfigure that
sandbox.

Every real run profile declares an explicit positive `timeout_seconds`. There is
no hidden universal execution timeout. The coordinator gives the experiment
container a unique coordinator-owned name. Whether the command exits normally,
fails, or the Docker client times out, the coordinator must verify that the
named executor container is absent, reaping it with `rm -f` when necessary. If
absence cannot be established, the run is `BLOCKED` and coordinator-captured
stdout/stderr are not published as completed run evidence.

An unavailable requested backend likewise returns a non-zero `BLOCKED` run
outcome; backend unavailability is not a successful no-op.

Only after executor absence is established may the lifecycle continue:

```text
validate/probe/smoke
        -> run untrusted executor under explicit timeout
        -> verify/reap named executor container
        -> publish coordinator-captured run evidence
        -> freeze candidate handoff
        -> verify frozen handoff
        -> deterministic bounded package
        -> retain package attestation
```

Packaging never reads the live writable experiment workspace directly. This
ordering prevents the executor from concurrently changing the subject while the
packager decides which bytes constitute the candidate.

### C. Keep filesystem isolation mechanically enforced and fail closed

Every run profile declares resolved absolute roots for:

- admitted read-only inputs;
- one disposable writable project root;
- a bounded writable evidence root;
- explicitly writable temporary/cache roots; and
- excluded host surfaces.

The runner rejects `/` as a broad admitted read root, lexical traversal,
symlink-resolved roots and declared overlap with excluded surfaces. It also
requires every admitted read-only root to be disjoint from every writable
project/evidence/temporary surface in both ancestor directions. A second writable
bind must never make an allegedly read-only host subtree writable through another
container path.

Host source paths used in Docker bind mounts are also syntax-checked for the
selected `--mount` grammar. In particular, a source path containing `,` is
rejected before Docker invocation rather than being interpolated into a
comma-delimited mount specification with ambiguous semantics.

Real host Git metadata, unrelated repositories, prior agent state and user-home
material are not implicitly admitted.

For the currently qualified OCI backend, the coordinator uses a read-only
container root filesystem, drops capabilities, enables `no-new-privileges`,
mounts only declared roots and never mounts the Docker/container-control socket
inside the experiment. An unavailable required capability yields `BLOCKED`; it
does not silently degrade to unrestricted host execution.

### D. Treat the container daemon as coordinator authority, not experiment authority

OCI isolation depends on a host container runtime controlled by the trusted
coordinator. That daemon is inside the trusted computing base for this profile.
The security claim is therefore not "Docker is an adversarial boundary against
its administrator". The claim is that the untrusted experiment process is not
given daemon/control authority and is mechanically limited to the demonstrated
namespace/mount/network surface.

Bubblewrap remains visible to capability probing but is deliberately unqualified:
until its complete behavioral smoke passes under separate evidence, a Bubblewrap
request returns `BLOCKED` rather than being treated as an equivalent fallback.

### E. Inject only run-specific configuration and credentials

The experiment receives a clean or explicitly allowlisted environment. Required
provider credentials are injected only by declared environment name. Prior user
home, session state, provider CLI state, cookies, tokens and unrelated
configuration are not inherited by default and are never retained as canonical
secret-bearing evidence.

The run identity binds the immutable runtime image, executor identity/version,
model and auxiliary-model declaration where applicable, non-secret
configuration digest, requested backend, resolved backend, explicit timeout and
exact command argv. Requested and resolved backend identities remain distinct
when `auto` selects a concrete backend.

### F. Keep network control separate and truthful

Filesystem isolation is not represented as network isolation.

`network.mode: none` uses a no-network experiment namespace.

For `network.mode: restricted`, the experiment joins an internal-only network
and receives proxy variables pointing to a coordinator-owned CONNECT relay. The
relay alone joins an external network and admits only exact predeclared
`host:port` destinations. The smoke contract must demonstrate both admitted
configured egress and refused undeclared/direct egress.

The model-provider connection is an admitted external dependency. A restricted
profile is therefore not offline execution. If the required network topology or
relay cannot be enforced, the run is `BLOCKED`/`FAIL`; broader host networking
must not be reported as equivalent.

### G. Keep coordinator-captured evidence outside the experiment write surface

Stdout and stderr are captured first into coordinator-private staging that does
not overlap any admitted/mounted experiment root. They are published create-only
into the bounded evidence root only after the executor has terminated and the
coordinator has verified that the named experiment container is absent.

This prevents an untrusted experiment from unlinking or replacing a pathname and
causing the coordinator to hash replacement bytes. A process may still cause a
fail-closed denial by pre-creating a reserved output name in a surface it can
write; such a collision is not converted into evidence substitution or overwrite.

Every generated evidence identity includes SHA-256, byte count, producer
identity/version, producer configuration digest and declared derivation inputs.
A bare digest is not a portable evidence identity.

### H. Freeze a path-neutral candidate handoff after execution

The handoff component copies the post-execution candidate into its own frozen
bundle and emits a canonical path-neutral `handoff.json` manifest. The manifest
records ordered member identity, normalized mode, file byte count/SHA-256,
symlink target without dereferencing, producer identity/configuration and
explicit input identities.

Source traversal uses no-follow opens and descriptor-relative operations.
Regular files are fstat-checked before and after copy/hash; directories and
symlinks are similarly checked for replacement. Symlinks are preserved as
symlinks and their external targets are never copied implicitly.

The bundle destination is create-only. Once its parent directory is opened, the
open parent descriptor is authoritative for creation and cleanup. The coordinator
captures the inode identity of the newly created bundle immediately after
creation. Cleanup may recurse only through an already-retained bundle descriptor,
or through a bundle reopened relative to that retained parent after verifying
that its inode still matches the created bundle. A same-name foreign replacement
is never cleanup authority.

The caller-visible parent pathname is checked against the opened parent inode
before the commit point. Parent replacement therefore fails closed while the
coordinator can still remove only its own created bundle from the retained old
parent. The canonical manifest is written last as the bundle commit marker.

A later `verify` invocation may use a pathname to locate retained evidence, but
that locator is canonicalized before a verified `manifest_path`, `bundle_root`
and `snapshot_root` are returned. Trust comes from that canonical retained
location plus re-verification of the manifest, complete member set and content
identities, not from a lexical alias. This is evidence verification, not a claim
that ordinary filesystem paths become immutable storage forever.

### I. Package only a verified frozen handoff

The packager accepts `--handoff`; it has no raw-workspace packaging interface.
It re-verifies the handoff before and after package construction and performs
output-inside-handoff containment against the canonical verified bundle root,
not a caller-supplied symlink alias.

Package construction is deterministic PAX tar with:

- handoff-defined member order;
- normalized uid/gid/user/group/mtime/mode metadata;
- no symlink dereference;
- descriptor-bound snapshot file reads with digest/size rechecks; and
- a hard streaming byte ceiling enforced before a write could exceed the
  configured archive limit.

The complete archive is never materialized in memory merely to measure size.
`check-size` remains available for other materialized objects, but the packager
itself enforces its limit while streaming.

Package staging, hashing and publication remain bound to an opened destination
parent and an open staging file descriptor. The packager records the staging
inode when the create-only temporary name is allocated. Hashing does not reopen
staging by pathname. Before publication, the staging name must still resolve to
that owned inode. Final publication is a create-only link within the same opened
parent and verifies that the published inode is the staged inode.

Failure cleanup follows the same ownership rule: a staging or output name is
unlinked only if it still resolves to the inode created by the packager. A
same-name foreign replacement is retained. Parent-namespace replacement and
foreign-output collision therefore fail closed without redirecting publication
or deleting foreign state.

The package result binds the archive bytes to packager producer/version/config,
the handoff manifest digest and the handoff's declared inputs.

### J. Make determinism independently executable

A fixed synthetic source tree has a committed golden PAX-tar SHA-256. CI freezes
independent equivalent trees and requires byte-identical output with that exact
digest on independent Python 3.11 and Python 3.12 hosted workers.

This is stronger than same-process repeatability but remains a bounded
cross-worker Linux/Python observation. It is not a universal statement about
every filesystem, Python implementation or future tar library version. A change
that intentionally changes package bytes must change the package contract and
golden identity explicitly rather than silently drifting.

### K. Keep dependencies outside the frozen candidate unless they are intentionally candidate material

Dependencies are run inputs, not candidate source, unless the experiment
explicitly studies them. The preferred design prepares dependency objects outside
the disposable candidate root and admits them separately as read-only inputs.

The handoff component does not guess that names such as `node_modules` are
non-candidate. If dependency material is physically inside the root passed to
`freeze`, it is candidate material and will be frozen. A trial that requires a
smaller candidate must prepare that boundary explicitly and bind excluded
immutable dependencies separately. There is no universal exclusion-name list.

### L. Require reproducible boundary and adversarial tests

Before reuse, the exact runner/runtime candidate must behaviorally demonstrate:

1. admitted input read succeeds;
2. write to read-only input is denied;
3. no read-only host root overlaps any writable project/evidence/temp bind;
4. project/evidence writes work only where admitted;
5. outside write is denied;
6. excluded read is denied where the backend claims read isolation;
7. symlink/path escape and mount-grammar edge cases do not widen the boundary;
8. inherited environment is reduced to the declared set;
9. container-control sockets are absent;
10. configured restricted egress succeeds and undeclared/direct egress fails;
11. generated evidence is producer/input-bound;
12. coordinator capture bytes cannot be substituted through a writable pathname;
13. a real run has an explicit positive timeout and named executor container;
14. timeout/backend failure is fail-closed and executor absence is verified
    before evidence publication;
15. handoff mutation, parent replacement and failure cleanup cannot redirect or
    delete a foreign replacement;
16. verified handoff canonicalization prevents lexical aliases from defeating
    package-output containment;
17. package mutation, oversize, parent replacement, staging replacement and
    foreign-output replacement all fail closed without deleting foreign state;
18. requested/resolved backend identities remain separately retained; and
19. the independent golden archive digest remains byte-stable on both supported
    hosted Python workers.

Capability probing, mechanical smoke and package determinism are separate from
semantic task correctness. A backend or candidate that cannot pass the relevant
contract is unavailable, not partially green.

### M. Keep semantic and mechanical interventions separate

Run records retain separate accounting for material semantic owner interventions
and mechanical controls/denials/infrastructure corrections. Mechanical boundary
enforcement is not semantic owner help, and a semantic correction cannot be
hidden as infrastructure troubleshooting.

### N. Keep the first implementation Gnostoa-self-only and bound the threat claim

This Decision authorizes no generic public sandbox schema, adopter requirement,
cloud orchestration service or universal security claim.

The demonstrated claim excludes compromise or hostile control of the host
kernel, root/administrator, container daemon or other actors with authority to
rewrite retained filesystem state after a successful verification/commit point.
It also does not make provider traffic private from the provider or make a model
semantically correct.

A VM/microVM or another backend may later provide a stronger host boundary, but
it must be separately qualified against the same logical contract and must
report its backend-specific assurance rather than inheriting OCI results by
analogy.

## Consequences

- Execution, evidence capture, candidate freezing and packaging now have distinct
  failure domains and tests.
- A real experiment cannot inherit a hidden universal timeout; timeout is explicit
  run policy and executor absence is a mechanical lifecycle gate.
- Read-only admission cannot be invalidated by a second writable bind to the same
  host subtree, and Docker mount-source grammar is validated before launch.
- Packaging can be tested on synthetic trees without launching an agent or
  sandbox.
- The packager cannot silently choose a different mutable workspace subject; it
  consumes a canonical verified frozen handoff.
- Namespace replacement, cleanup and publication races fail closed at ownership
  boundaries instead of redirecting or deleting foreign output.
- Deterministic archive bytes are independently testable through a fixed golden
  digest.
- Some environments correctly remain `BLOCKED`; portability is not achieved by
  weakening the claim.
- Host loss is less damaging because retained artifacts carry producer/config/
  input identities rather than relying on local names.
- The runner improves experimental validity and auditability. It does not improve
  semantic diagnosis, prove model independence, or replace the #179 follow-up
  triage retained in Work Item #180.
