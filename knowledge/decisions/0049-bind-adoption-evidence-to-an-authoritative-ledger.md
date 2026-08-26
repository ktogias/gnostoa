---
type: Decision
title: Bind adoption evidence to an authoritative ledger
description: Repair adoption-check evidence integrity by keeping authoritative bytes in memory until suites finish, reconciling clean materialization, and emitting one external bundle commitment.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-26T21:35:29+03:00"
sources:
  - id: evidence-integrity-repair-work-item
    resource: https://github.com/ktogias/gnostoa/issues/141
    title: Repair adoption-check evidence bundle integrity
  - id: adoption-check-implementation-work-item
    resource: https://github.com/ktogias/gnostoa/issues/137
    title: Implement the bounded adoption completion check
  - id: adoption-check-implementation-pr
    resource: https://github.com/ktogias/gnostoa/pull/138
    title: Implement the bounded adoption completion check
  - id: adoption-completion-decision
    resource: 0047-select-a-bounded-adoption-completion-check.md
    title: Select a bounded adoption-completion check
  - id: runtime-observation-decision
    resource: 0048-select-project-adapter-runtime-observation-for-adoption-check.md
    title: Select project-adapter runtime observation for adoption-check
x-project-knowledge:
  id: kit.decision.0049.bind-adoption-evidence-to-an-authoritative-ledger
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md
    - kind: governed-by
      target: /decisions/0047-select-a-bounded-adoption-completion-check.md
    - kind: governed-by
      target: /decisions/0048-select-project-adapter-runtime-observation-for-adoption-check.md
    - kind: references
      target: /lifecycles/evidence-gated-capability-evolution.md
---

# Bind adoption evidence to an authoritative ledger

Recorded by `codex/gpt-5` from the accountable owner's release-blocking
integrity disposition in Work Item #141. This Decision admits only the
smallest repair to the implementation selected by
[Decision 0047](0047-select-a-bounded-adoption-completion-check.md) and the
runtime-observation handshake selected by
[Decision 0048](0048-select-project-adapter-runtime-observation-for-adoption-check.md).

## Context

The integrated implementation wrote authoritative component outputs, the
candidate patch and bounded context beneath the same temporary evidence root
whose pathname was disclosed to project-owned suites. A suite or descendant
running as the same operating-system user could therefore change or replace
those files. Finalization then hashed the pathname-visible final bytes, so a
coherent `SHA256SUMS` did not establish that the bundle contained the bytes
originally retained by Gnostoa.

Descriptor-bound acquisition protects the runtime-observation sidecar from
final-component and parent-directory substitution. It does not protect sibling
artifacts exposed in the suite-visible tree. Owner-only permission bits do not
separate mutually untrusted processes running under the same user identity.

## Decision

### A. Keep authoritative evidence in an immutable ledger

During execution, Gnostoa keeps each authoritative artifact in an in-memory,
append-only ledger. Every entry binds one normalized project-relative path,
the original immutable bytes, byte length, SHA-256 digest and bounded origin.
Duplicate paths are rejected. Project suites receive no pathname to this
ledger and no pathname to a partially materialized evidence bundle.

The suite-visible exchange contains only its fresh incoming observation
directory. Unexpected files, directories, links, devices, FIFOs or other paths
fail closed. Sidecar acquisition retains Decision 0048's held-directory
descriptor, basename-relative `O_NOFOLLOW` open, `fstat`, 64 KiB bound and
same-descriptor read. This repair does not claim to observe whether the
producer used atomic no-replace installation; that remains its obligation.

### B. Materialize once after project execution

Only after all project-suite attempts finish may Gnostoa construct
`adoption-check.json`, artifact metadata and `SHA256SUMS` from ledger entries.
It then materializes one fresh private staging tree through descriptor-relative,
no-follow, no-replace writes. It reopens and reconciles the exact paths, types,
lengths, digests and bytes against the ledger before atomically publishing the
previously absent final bundle. An unexpected path, replacement, mismatch or
reconciliation failure is an integrity/internal failure with exit `2`, no
readiness claim and no publication of a supposedly valid bundle.

### C. Add one external canonical bundle commitment

Decision 0047 admits a retained bundle and internal `SHA256SUMS`, but it does
not admit a public commitment outside that bundle's self-referential custody
boundary. Add exactly one success-only trusted-stdout record:

```text
EVIDENCE BUNDLE COMMITMENT: gnostoa-adoption-evidence-bundle/v1 sha256:<64 lowercase hexadecimal characters>
```

The committed payload is UTF-8 JSON serialized with sorted object keys and
compact separators, followed by one LF. Its top-level value is an array sorted
by normalized relative `path`. Each materialized regular file, including
`adoption-check.json` and `SHA256SUMS`, contributes exactly:
`{"bytes":<non-negative integer>,"path":"<path>","sha256":"sha256:<digest>"}`.
The stdout record is not stored inside the bundle and therefore is not an
entry. It is emitted only after successful no-replace publication and final
ledger reconciliation. Recomputing it later detects changed bundle bytes; the
record is neither provenance attestation nor semantic acceptance.

No other public result or exit contract changes. Exit `0` remains only `READY
FOR ACCOUNTABLE-OWNER REVIEW`; exit `1` is an executed mechanical failure;
exit `2` is unsafe invocation or internal/integrity failure; exit `3` is an
unavailable or incomplete prerequisite. Semantic owner review remains
`REQUIRED`, durable adoption remains `NOT DETERMINED`, and project runtime
observation remains project-reported rather than independently attested.

### D. Preserve the residual boundary

The ledger and descriptor-bound reconciliation prevent suite mutation of
authoritative pre-suite pathnames and detect mutation within the admitted
materialization protocol. They do not fully exclude an unrestricted persistent
malicious process running as the same user after publication. That process can
still alter ordinary filesystem custody; a previously emitted external
commitment makes later mutation detectable only when a trusted consumer retains
and recomputes it. Stronger exclusion requires operating-system isolation or a
separate external trust anchor and is not selected here.

## Consequences

- The implementation remains an adoption evidence check, not a generic receipt
  framework, sandbox, runtime selector, project adapter or container service.
- Gnostoa does not invent owners or project facts, overwrite canonical project
  files or collapse mechanical completeness into semantic truth.
- Project source, Git index, toolkit source and provider state remain
  non-mutating under the command's existing contract.
- The additive stdout commitment is a public compatibility change and requires
  a later source/runtime release before general consumption. No release is
  admitted by this Decision.
- The expanded executable subject still requires the smallest affected
  security replay and fresh SB2 admission before a future release relies on it.
- This Decision admits no Mail run, OCI effect, publication, provider-setting
  change or claim of broader same-user process isolation.
