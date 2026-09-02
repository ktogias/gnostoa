---
type: Decision
title: Enforce owner-led experiment boundaries with coordinator-owned sandboxes
description: Select a Gnostoa-self runner architecture that uses a trusted coordinator, container-first isolation, fail-closed native fallback, bounded egress and producer-bound evidence without claiming hard isolation when the required backend is unavailable.
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

The owner-led Mail experiments demonstrated that prompt- and tool-level permissions
are not a sufficient execution boundary. Phase A allowed file-edit capability to
write after an intended stop. Phase B then demonstrated a materially stronger
one-off sandbox: admitted inputs were read-only, unrelated host material was
hidden, the disposable project remained writable and only the minimum provider
credential was injected. The same work also exposed a dangerous precursor in
which a broad read-only bind still made the whole host visible.

Phase C added further runner evidence. A namespace mechanism was unavailable in
one execution environment; executor and auxiliary-model identities drifted until
explicitly pinned; candidate packaging exceeded an assumed bound because the
dependency installation was treated as candidate payload; and host loss exposed
which derived identities had not been bound to their producer or published
independently. The final paired execution remained valid only after these
conditions were corrected and checked fail-closed.

These observations justify a reusable Gnostoa-self runner boundary. They do not
justify a generic adopter sandbox contract, a claim of complete operating-system
isolation or a new orchestration platform.

## Alternatives considered

| Alternative | Benefit | Material limitation | Disposition |
| --- | --- | --- | --- |
| Prompt and OpenCode permission controls only | Lowest operational cost | Shell and editor capability remain inside the same host authority; tool policy cannot hide arbitrary host reads or mechanically bound all writes | Rejected |
| Bubblewrap-only runner | Small Linux-native sandbox; Phase-B evidence exists | User namespaces are unavailable on some hosts and inside some containers; making it mandatory would contradict the container-first / native-fallback runtime strategy | Rejected as sole backend; retained as native fallback |
| OCI-container-only runner | Strong explicit mount and namespace surface; aligns with container-first runtime | A container daemon is a privileged coordinator dependency and is not universally available; Docker socket exposure would destroy the boundary | Rejected as the only backend; selected as primary backend |
| Full VM / microVM per run | Stronger host separation | Operational cost and platform dependency are disproportionate to the current owner-led experimental need | Deferred |
| Coordinator-owned OCI primary plus fail-closed native namespace fallback | Aligns with Decision 0005, keeps the agent away from host/container control APIs and permits recovery on compatible native hosts | Requires explicit capability probing and separate network relay policy; some hosts will correctly report BLOCKED | Selected |

## Decision

### A. Separate the trusted coordinator from the untrusted experiment process

The reusable profile has two authority planes:

- a **trusted coordinator** constructs the sandbox, verifies exact inputs,
  controls mounts, credentials, egress, packaging and final read-back; and
- an **experiment process** runs the agent inside the admitted namespace and
  has no authority to reconfigure that namespace, access the container daemon,
  obtain provider-management credentials or widen its own read/write/network
  surface.

The experiment process may edit freely inside its admitted writable project
root. The design does not require owner approval for every ordinary source edit.
The security property is the mechanically enforced boundary, not repeated
interactive confirmation.

### B. Use OCI as the primary backend and a native namespace sandbox only as a fallback

Consistent with Decision 0005, the primary Gnostoa-self runner uses a
coordinator-created OCI-compatible container or equivalent container runtime.
The agent never receives the daemon socket or a container-management client with
host authority.

A native Linux namespace backend such as Bubblewrap may be used as a fallback
only after an explicit capability probe proves the required namespace and bind
operations. A failed probe yields `BLOCKED`; it must not silently degrade to an
unrestricted host process.

Backend choice is retained as evidence for every run. Equivalent result claims
require the same declared runner contract even when the backend implementation
differs.

### C. Admit explicit read, write and evidence surfaces

Every run manifest declares resolved absolute roots for:

- read-only admitted inputs;
- the writable disposable project root;
- the writable evidence/output root, which may be a bounded subdirectory of the
  disposable project;
- explicitly writable temporary/cache roots; and
- excluded host surfaces.

The runner does not expose `/` as a broad read-only bind. Real host Git metadata,
unrelated repositories, prior agent session state and home-directory material are
excluded unless individually admitted.

Path admission is evaluated on resolved paths. Symlink, `..`, bind-mount or
nested-path tricks may not expand a declared root. A write outside declared
writable roots fails mechanically. A read of an excluded sentinel surface must
fail in the smoke test where the selected backend can enforce the read boundary.

Disposable Git metadata may be created inside the writable project workspace so
ordinary Git operations work without exposing the real repository metadata.

### D. Inject only run-specific configuration and credentials

The experiment process receives a clean or explicitly allowlisted environment.
Provider authentication, model configuration and other required secrets are
injected minimally for the run. Existing user home, prior OpenCode sessions,
provider CLI state and unrelated configuration are not inherited by default.

The run record retains configuration identities and secret-free provenance. It
never retains secret values, tokens, cookies, one-time codes or full credential
files as canonical evidence.

### E. Keep network control separate and truthful

Filesystem isolation is not represented as hard network isolation.

For a controlled experiment that requires restricted egress, the runner uses a
coordinator-owned deny-by-default network path or relay that admits only the
predeclared model-provider connection and records admitted/refused connection
attempts. Direct arbitrary egress from the experiment namespace is denied.

If the selected platform cannot enforce the declared network boundary, the run
is `BLOCKED` for that profile. A broader network may be used only under a
separately declared weaker profile; it cannot be reported as equivalent to the
restricted profile.

The model-provider connection is an admitted external dependency and is never
misrepresented as offline execution.

### F. Bind executors and generated evidence to their producers

The run manifest binds the executable path or immutable image identity, version,
model alias, auxiliary/small-model configuration where applicable, complete
non-secret configuration digest and runner-backend identity before launch.
Drift stops the run.

Every generated digest record includes, at minimum:

- output path or stable artifact identity;
- SHA-256 and byte count;
- producer identity and version;
- producer configuration digest;
- declared input identities sufficient to reconstruct the derivation; and
- the digest algorithm/version where ambiguity is possible.

A bare digest without the producer and declared derivation inputs is not a
complete portable evidence identity.

### G. Keep dependencies outside candidate payload unless explicitly admitted

Large dependency installations are immutable run inputs, not candidate source
payload, unless the experiment explicitly studies them.

The runner binds the dependency object independently from the candidate and
allows only declared volatile namespaces such as tool caches. Candidate
packaging verifies dependency identity before and after execution and excludes
the exact dependency root from the candidate archive.

Candidate and evidence packaging computes size before any helper allocates the
complete payload in memory. The configured archive limit is a run parameter, not
a universal 64 MiB Gnostoa constant. Oversize output fails before sealing; a
future streaming implementation may remove the in-memory helper constraint but
not the declared size policy.

### H. Require a reproducible capability and escape smoke test

Before the profile is reused, one focused smoke package must demonstrate, on
the selected backend:

1. admitted read-only input can be read;
2. write to admitted read-only input is denied;
3. writable project/evidence roots accept writes;
4. an outside write is denied;
5. an excluded read sentinel is denied where the backend claims read isolation;
6. symlink/path traversal cannot escape admitted roots;
7. inherited environment/configuration is reduced to the declared allowlist;
8. container/host control sockets are absent from the experiment process;
9. declared egress is admitted and an undeclared destination is refused for the
   restricted-network profile; and
10. generated evidence identities include producer and input bindings.

Capability probing and smoke evidence are separate from semantic task results.
A profile that cannot pass the smoke suite is unavailable, not partially green.

### I. Keep semantic and mechanical interventions separate

Run records retain separate counters for:

- material semantic owner interventions; and
- mechanical boundary controls, denials, stops and infrastructure corrections.

Mechanical enforcement does not count as semantic owner help. Conversely, a
semantic correction cannot be hidden as infrastructure troubleshooting.

### J. Keep the first implementation Gnostoa-self-only

This Decision authorizes no generic public sandbox schema, adopter requirement,
cloud runner, reusable orchestration service or claim that one backend is secure
for every threat model.

The first implementation is a Gnostoa-self profile and smoke package under
Work Item #164. Promotion or public inheritance requires separate evidence,
classification and Decision authority.

## Consequences

- Some environments will correctly report `BLOCKED` rather than run with a
  weaker boundary.
- The trusted coordinator becomes an explicit part of the experiment trust
  model and must be identified in evidence.
- OCI remains the primary route while native namespace execution remains a
  bounded recovery path, preserving Decision 0005.
- Network enforcement and filesystem enforcement are independently visible.
- Host loss is less damaging because derived artifacts carry producer and input
  identities instead of relying on local naming conventions.
- Dependency directories no longer inflate candidate identity merely because
  they share a filesystem root with the task checkout.
- The runner improves experimental validity and portability; it does not improve
  semantic diagnosis or substitute for the #179 follow-up triage retained in
  Work Item #180.
