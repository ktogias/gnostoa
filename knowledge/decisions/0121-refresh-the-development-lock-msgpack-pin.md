---
type: Decision
title: Refresh the development lock's msgpack pin for an unbounded memory leak
description: "msgpack 1.2.1, pinned in requirements/development.lock, is reported by the strict development audit under CVE-2026-114613 (GHSA-j586-36cw-2gc2): its C extension leaks a decoded map value when strict_map_key validation rejects a key. This Decision moves exactly that one pin to the fixed release 1.2.3, verified from its artefacts, as its own critical change. It grants no standing authority to refresh future pins."
status: draft
generated:
  by: anthropic/claude-opus-5-5
  at: "2026-10-27T17:39:56Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/466
    title: Refresh the development lock's msgpack to 1.2.3 and restore strict audit before #465
  - id: advisory
    resource: https://github.com/advisories/GHSA-j586-36cw-2gc2
    title: GHSA-j586-36cw-2gc2 (msgpack)
  - id: advisory-snapshot
    resource: https://github.com/ktogias/gnostoa/issues/466#issuecomment-6449189177
    title: The advisory record's exact bytes, published with their extraction rule
  - id: maintainer-advisory
    resource: https://github.com/msgpack/msgpack-python/security/advisories/GHSA-j586-36cw-2gc2
    title: The maintainer's advisory, whose affected range differs from the advisory record's
  - id: fixed-release
    resource: https://github.com/msgpack/msgpack-python/releases/tag/v1.2.3
    title: msgpack 1.2.3, the maintainer's patched release
  - id: pre-change-failure
    resource: https://github.com/ktogias/gnostoa/actions/runs/40546789579
    title: Protected main's verification run whose development audit failed on msgpack 1.2.1
  - id: owner-selection
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6448817834
    title: The owner's selection of Option A and its one-path boundary
  - id: binding
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6449080372
    title: "The Router's critical binding of #466 and its governing Decisions"
  - id: prior-art
    resource: ./0095-refresh-vulnerable-development-dependency-pins.md
    title: The earlier refresh of a vulnerable development pin, reused as the evidence pattern only
  - id: preparation
    resource: ./0090-require-pre-candidate-preparation-receipts-for-non-hook-authoring.md
    title: Exact-parent preparation receipts
  - id: runtime-boundary
    resource: ./0055-separate-runtime-lock-declaration-validity-from-image-observation.md
    title: The runtime lock's declaration boundary, which this change leaves untouched
  - id: reuse-review
    resource: ./0062-require-proportionate-prior-art-and-reuse-review.md
    title: Proportionate prior-art and reuse review
  - id: inheritance
    resource: ./0099-route-the-architecture-inheritance-gate-from-source.md
    title: The architecture inheritance gate
x-project-knowledge:
  id: kit.decision.0121.refresh-the-development-lock-msgpack-pin
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /decisions/0095-refresh-vulnerable-development-dependency-pins.md
    - kind: references
      target: /decisions/0090-require-pre-candidate-preparation-receipts-for-non-hook-authoring.md
    - kind: references
      target: /decisions/0055-separate-runtime-lock-declaration-validity-from-image-observation.md
    - kind: references
      target: /decisions/0062-require-proportionate-prior-art-and-reuse-review.md
    - kind: references
      target: /decisions/0099-route-the-architecture-inheritance-gate-from-source.md
---

# Refresh the development lock's msgpack pin for an unbounded memory leak

## Context

`requirements/development.lock` pinned `msgpack==1.2.1`, which reaches the toolchain as a
dependency of CacheControl, which `pip-audit` uses. On protected main
`4b6a7e8833b7e1dd65260bde11ce274c092df9bd`, verification run 40546789579 (source
`pre-change-failure`) ran `extended`'s 3,021 tests OK, then failed `development_audit`:
`msgpack 1.2.1`, CVE-2026-114613, alias GHSA-j586-36cw-2gc2, fix version 1.2.3. The
required `regression` gate failed with it, on main and on every candidate, because the pin
is byte-identical everywhere.

The advisory describes the C extension (`msgpack._cmsgpack`) leaking a decoded map value
when deserialization rejects a key under `strict_map_key=True`, the default. Repeated
malformed input can grow process memory without bound: a denial of service in a process
that deserializes untrusted data.

Because the advisory record can change, its content is bound to a retained snapshot.
`GET /advisories/GHSA-j586-36cw-2gc2` on GitHub's REST API was retrieved at
2026-10-27T17:37:50Z: 5,053 bytes, SHA-256
`11239eaf2262f0ddd5ccc8f92083a42fb0e1fa262748a9d69eea208ea6e0602a`. Those exact bytes
are published on the Work Item (#466 comment 6449189177, source `advisory-snapshot`), with
the rule for extracting them. The record states severity `high`, `published_at`
2026-10-27T15:04:07Z, no withdrawal, and for `msgpack` the vulnerable range `< 1.2.3` with
first patched version `1.2.3`.

The record's range is its own. The maintainer's advisory (source `maintainer-advisory`)
leaves the earliest affected release unresolved and lists a reproduction on 1.2.2. This
Decision does not establish that 1.2.1 is exploitable, nor when the audit's data source
first carried the record. It acts on the strict audit's failure, which is a required gate.

The runtime lock is unchanged and declares no `msgpack`; its strict audit is clean. That
is a declaration, not an observation of any image. Following Decision 0055, whether a
published runtime image carried msgpack is **UNKNOWN** here. What this change remediates,
and demonstrates, is the development and CI toolchain.

This changes a security-relevant dependency of the toolchain, so it is a `critical`
change (owner selection #389 6448817834; Router binding #389 6449080372), its own change
in the single mutating lane, ahead of #465's re-parent.

## Evidence bindings

Each source this Decision relies on is bound by content, not by its URL alone. A provider
page or comment can change; a digest or an immutable identifier cannot.

| Source | What binds it | What it is used for |
|---|---|---|
| `advisory-snapshot` | 5,053 bytes, SHA-256 `11239eaf2262f0ddd5ccc8f92083a42fb0e1fa262748a9d69eea208ea6e0602a`, retrieved 2026-10-27T17:37:50Z, with its extraction rule (#466 comment 6449189177) | the advisory record's severity, range and fix version |
| `pre-change-failure` | run 40546789579, artifact 12752948679 (ZIP SHA-256 `fc8710ff4240d678974ac459edc3e3694d41bfb21720a21a4db9a73f9e807d3e`), whose `development-dependency-audit.json` member is 7,318 bytes, SHA-256 `7e23542e37a96c976a558e9b538db244445199106b9f41865dbe61ffa86d4919`. The provider retains the artifact until 2026-11-10T17:09:01Z | the failure on protected main before the change |
| the fixed release's two resolved wheels | the CPython 3.12 and 3.11 manylinux x86_64 wheels: each one's SHA-256 **computed locally** from the downloaded bytes, matching both the index's digest and the lock (Decision point 2) | the identity of what the supported images install |
| the fixed release's other lock entries | the remaining 88 of the lock's 90 `msgpack` hashes: **the index's listed digests** for the other non-yanked wheels, as `tools.requirements_lock` records them. They were not downloaded or computed locally here | hash-pinning on platforms the supported images do not use |
| the base and candidate locks | their SHA-256, in Decision point 3 | the before and after audits |
| `advisory`, `maintainer-advisory`, `fixed-release` | not bound: mutable provider pages | context only, including the affected-range caveat; no conclusion here rests on their current text |
| `owner-selection` | #389 comment 6448817834 by user 532328, read at 2026-10-27T18:35:53Z: its body is 3,938 bytes, SHA-256 `c7f12266246b972059a61a3b2b0c766dbac5174cf44795bca278d8207931e998` (the UTF-8 `body` field of the REST response), unedited at that read (`created_at` equals `updated_at`, 17:26:44Z) | the owner's selection, scope and priority |
| `binding` | #389 comment 6449080372 by user 339381282, read at the same time: its body is 6,521 bytes, SHA-256 `d39206568b536d0931ae4b9ea32e93e235a1c26b072f6427971675eda4315284` (the UTF-8 `body` field of the REST response), unedited at that read (`created_at` equals `updated_at`, 17:35:27Z) | the class, Work Item and governing Decisions |
| the resolution's environment (Decision point 4) | the image built from the previous lock, content-addressed image ID `sha256:0bef80071c872c7cf8d4a218154140ee8af54357cd62a4c535691e9fdb70aeec`, label revision `6cc4389e65ed41c4906f3ffb4446c6376d7ce6e9`; it is local to the preparing host and not published, so it binds the observation's identity, not a retrievable copy | where the dry-run resolution was run |

## Prior-art and reuse disposition

No custom work was written. The repository already owns the mechanism that found this
(`pip_audit` behind `development_audit`), the mechanism that fixes it (a wheel-only,
hash-required lock), and the mechanism that renders it (`tools.requirements_lock`, used
unchanged). Decision 0095 is reused as the **evidence pattern**: a pin verified from its
artefacts, the audit recorded before and after, the resolution proved, and a verification
image built from the candidate. Decisions 0115 and 0116 are the same pattern's later
instances. None of them is reused as authority: they grant no standing permission to
refresh pins, and neither does this Decision. Decision 0116's build-backend change and
preparation substitute do not apply: nothing here touches `pyproject.toml`, and ordinary
exact-parent preparation (Decision 0090) accepts this change. The review is the
proportionate one of Decision 0062, with the inheritance routed as Decision 0099 requires.

The fix is the maintainer's own patched release, so no alternative was weighed: patching
the C extension by hand, or suppressing the audit, would not close the finding.

## Decision

1. **The lock records `msgpack==1.2.3` with every non-yanked wheel's exact SHA-256,** and
   nothing else in either lock moves.
   Only the pin line was changed by hand; the unchanged
   `python -m tools.requirements_lock --lock requirements/development.lock --write` then
   rendered the lock. It has 68 pins before and after, the same header, and the `msgpack`
   entry is the only one that differs: its 65 wheel hashes become 90. The lock is 81,095
   bytes, SHA-256 `186a8cd74f108d90e776789110e90c528ec723caa6cd0e5fa9cfaf6413a9dfd8`.

2. **The artefacts are verified, not an API response.** The two wheels the toolchain's
   CPython 3.11 and 3.12 x86_64 images resolve were downloaded into a separate untrusted
   directory and checked without executing them:

   | | CPython 3.12 | CPython 3.11 |
   |---|---|---|
   | file | `msgpack-1.2.3-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl` | `msgpack-1.2.3-cp311-cp311-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl` |
   | size | 472,998 bytes, matching the index's listed size | 477,820 bytes, matching the index's listed size |
   | SHA-256, computed locally | `ede33b2892ceb976283e009ad12fa1834cfdf1f9c43ee9c97849fc588d00a618`, matching the index's digest and present in the lock | `382b219de3d436de3baba0f4b0c6d4336e8f5858d0eb047918b13b69a71c6c55`, matching the index's digest and present in the lock |
   | metadata | `Name: msgpack`, `Version: 1.2.3`, `Requires-Python: >=3.10`, `License-Expression: Apache-2.0`; it carries the C extension | the same |
   | index status | not yanked; uploaded 2026-09-29 | not yanked; uploaded 2026-09-29 |

   The lock's 90 `msgpack` hashes are exactly the index's 90 non-yanked wheels for 1.2.3.

3. **The audit is recorded before and after, bound to the exact locks.** The commands are,
   literally:

   ```
   python -m pip_audit --no-deps --strict --progress-spinner off --requirement requirements/development.lock
   python -m pip_audit --no-deps --strict --progress-spinner off --requirement requirements/runtime.lock
   ```

   The environment is Python 3.12.14 and `pip-audit` 2.10.1, in the repository's
   `development` image.

   | | development lock | runtime lock |
   |---|---|---|
   | before, main `4b6a7e8833b7e1dd65260bde11ce274c092df9bd` | SHA-256 `8f2097c13606748878c3827788d2fa5f03fd6932fcbb1db89b2990925c03f85a`: **exit 1**, `msgpack 1.2.1 CVE-2026-114613` (GHSA-j586-36cw-2gc2), fix `1.2.3` | SHA-256 `35e36da52f8b4fa19bfe4239d0918ebdb0b0a09b2ad72d087fb345b6f41a02ed`: exit 0, no known vulnerability |
   | after | SHA-256 `186a8cd74f108d90e776789110e90c528ec723caa6cd0e5fa9cfaf6413a9dfd8`: **exit 0**, no known vulnerability | unchanged: exit 0 |

4. **The resolution is proved, and the proof names its environment.** In the image built
   from the previous lock (installed `msgpack 1.2.1`; image revision
   `6cc4389e65ed41c4906f3ffb4446c6376d7ce6e9`), this command resolves. That image's own
   `requirements/development.lock` is the old one, so the command does not read it. Its
   input is **the candidate lock**: SHA-256
   `186a8cd74f108d90e776789110e90c528ec723caa6cd0e5fa9cfaf6413a9dfd8`, bind-mounted
   read-only into the container at `/lock`. The command passes no hash flag itself:
   `--require-hashes` and `--only-binary :all:` are in force through that lock's own option
   lines, which `--requirement` reads.

   ```
   python -m pip install --dry-run --quiet --report /tmp/pip-resolution.json \
     --requirement /lock
   ```

   Its `install` list holds exactly one entry, `msgpack 1.2.3`. Every other pin is already
   satisfied at its locked version.
   The `development` image rebuilt from this lock installs it hash-checked.

5. **No standing update authority.** A later advisory is a later change, with its own
   class, evidence and owner approval.

## Consequences

- `development_audit` passes again, on main and on every candidate rebased onto it. #465
  is re-parented once onto the integrated result, with its diff unchanged and its
  exact-parent receipts regenerated.
- Nothing in the runtime lock, `pyproject.toml`, the CI behaviour, the audit criteria or the
  suppressions changes.
