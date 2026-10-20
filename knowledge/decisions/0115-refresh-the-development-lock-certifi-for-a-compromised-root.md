---
type: Decision
title: Refresh the development lock's certifi for a compromised root certificate
description: "certifi 2026.7.22, pinned in requirements/development.lock, bundles the emSign ECC Root CA - G3 root, and eight eMudhra intermediate CAs chaining to it were compromised (GHSA-6q48-6c7w-9gw2, critical). This Decision moves exactly that one pin to the fixed release 2026.10.19, verified from its artefact, as its own critical change. It grants no standing authority to refresh future pins."
status: draft
generated:
  by: anthropic/claude-opus-5-5
  at: "2026-10-20T21:16:35Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/445
    title: Update certifi in the development lock for GHSA-6q48-6c7w-9gw2
  - id: advisory
    resource: https://github.com/advisories/GHSA-6q48-6c7w-9gw2
    title: GHSA-6q48-6c7w-9gw2 (certifi)
  - id: owner-selection
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6301549275
    title: The owner's selection of Option A, class critical, and its execution boundary
  - id: route
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6301437613
    title: The Router's separate admission choice for #445
  - id: prior-art
    resource: ./0095-refresh-vulnerable-development-dependency-pins.md
    title: The earlier refresh of a vulnerable development pin, reused as evidence pattern only
  - id: binding
    resource: https://github.com/ktogias/gnostoa/issues/445#issuecomment-6301702228
    title: The Router's critical binding of #445 and its governing Decisions
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
  id: kit.decision.0115.refresh-the-development-lock-certifi-for-a-compromised-root
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

# Refresh the development lock's certifi for a compromised root certificate

## Context

`requirements/development.lock` pinned `certifi==2026.7.22`. Advisory
GHSA-6q48-6c7w-9gw2 (critical) reports that certifi bundles the `emSign ECC Root CA - G3`
root certificate, and that eight eMudhra intermediate CA certificates chaining to it were
compromised. A process trusting that bundle would accept certificates issued under a
compromised intermediate.

Because the advisory page can change, its content is bound to a retained snapshot.
`GET /advisories/GHSA-6q48-6c7w-9gw2` on GitHub's REST API was retrieved at
2026-10-20T21:48:11Z: 2,302 bytes, SHA-256
`744e6f07692b60127a7de335386ad71a2b6e27a27f6879d969ec6fc81a9705b7`. It records severity
`critical`, publication at 2026-10-20T19:35:05Z, no withdrawal, and for `certifi` the
vulnerable range `>= 2019.03.09, < 2026.10.19` with first patched version `2026.10.19`.

`ci/verify extended` fails its `development_audit` quality gate as a result, on main and
on every candidate, because the pin is byte-identical everywhere. The runtime lock is
unchanged and declares no `certifi`. That is a declaration, not an observation of any
image. Following Decision 0055, whether a published runtime image carried this bundle is
**UNKNOWN** here: no acquisition-bound inventory of a runtime image was observed. What
this change remediates, and demonstrates, is the development and CI toolchain.

This changes the toolchain's certificate trust, so it is a `critical` change (owner
selection #389 6301549275, superseding an earlier `normal`). It is its own change, the
single mutating lane, ahead of the admitted S2 A work.

## Prior-art and reuse disposition

No custom work was written. The repository already owns the mechanism that found this
(`pip_audit` behind `development_audit`) and the mechanism that fixes it (a wheel-only,
hash-required lock). Decision 0095 is reused as the **evidence pattern**: a pin verified
from its artefact, the audit recorded before and after, and the resolution proved. It is
not reused as authority: it grants no standing permission to refresh pins, and neither
does this Decision. The review is the proportionate one of Decision 0062, with the
inheritance routed as Decision 0099 requires. Decision 0055's runtime-lock boundary is
untouched: the runtime lock does not change.

The fix is the vendor's own release, so no alternative was weighed: removing one root
from a vendored bundle by hand, or pinning anything that keeps the root, would not close
the finding. The newest release, 2026.10.19, is also the advisory's fix version.

## Decision

1. **The lock records `certifi==2026.10.19` with the wheel's exact SHA-256,** and
   nothing else in either lock moves.

2. **The artefact is verified, not an API response.** The wheel
   `certifi-2026.10.19-py3-none-any.whl` was downloaded with a request that fails on an
   HTTP error, into a separate untrusted directory, and checked without executing it:

   | | |
   |---|---|
   | size | 136,464 bytes, matching the index's listed size |
   | SHA-256, computed locally | `42d35340cc5b9ba78e818ddbff0c5b1c2b779de448a340fd1b989f5fa8670e1b`, matching the index's listed digest |
   | metadata | `Name: certifi`, `Version: 2026.10.19`, `Requires-Python: >=3.7`, which covers the supported 3.11 and 3.12 |
   | index status | not yanked; the newest certifi release |
   | the fix itself | the bundled `certifi/cacert.pem` **no longer contains** `emSign ECC Root CA - G3`. The previous lock's 2026.7.22 wheel (SHA-256 `62f22742b58a1a33014a2b6b706588a8d7e2a88ae7bd1a6ebe8c992928483775`) **does** contain it |

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
   | before, main `37f220e44478c3d7fcb6462111865bb750df420d` | SHA-256 `2bf56715ff49de345619f1a9946cd90ba9b89c654f9d4ea6292615c867bf64fa`: **exit 1**, `certifi 2026.7.22 GHSA-6q48-6c7w-9gw2`, fix `2026.10.19` | SHA-256 `35e36da52f8b4fa19bfe4239d0918ebdb0b0a09b2ad72d087fb345b6f41a02ed`: exit 0, no known vulnerability |
   | after | SHA-256 `2a941975aa8210ce2ac54ed56377d63f4d3e9162a4a9df4c6289073202fbb805`: **exit 0**, no known vulnerability | unchanged: exit 0 |

4. **The resolution is proved, and the proof names its environment.** In an image built
   from the previous lock (installed `certifi 2026.7.22`), this command resolves with
   `--require-hashes` in force:

   ```
   python -m pip install --dry-run --quiet --report /tmp/pip-resolution.json \
     --requirement requirements/development.lock
   ```

   Its `install` list holds exactly one entry, `certifi 2026.10.19`. Every other pin is
   already satisfied at its locked version. The `development` image rebuilt from this
   lock installs it hash-checked.

5. **No standing update authority.** A later advisory is a later change, with its own
   class, evidence and owner approval.

## Consequences

- `development_audit` passes again, on main and on every candidate rebased onto it. The
  admitted S2 A work (#446) is reparented onto the integrated result, with its diff
  unchanged and its exact-parent receipts regenerated.
- Nothing in the runtime lock, the CI behaviour, the audit criteria or the suppressions
  changes.
