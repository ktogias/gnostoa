---
type: Decision
title: Refresh the development lock's filelock and setuptools pins for four advisories
description: "filelock 3.32.3 and setuptools 83.0.0, pinned in requirements/development.lock, carry four advisories published on 2026-10-23 (GHSA-v4x8-3wr5-3wq8 high, GHSA-9vhv-jxww-xfm5, GHSA-567q-5qvw-pf92 and GHSA-xmj3-9gf7-h52w). This Decision moves exactly those two pins to their first patched releases, 4.2.1 and 84.1.0, verified from their artefacts, and the one pyproject.toml build-backend line that release builds require to match. It grants no standing authority to refresh future pins or to change pyproject.toml."
status: draft
generated:
  by: anthropic/claude-opus-5-5
  at: "2026-10-24T06:55:00Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/456
    title: Development-lock advisories fail the required regression gate
  - id: owner-selection
    resource: https://github.com/ktogias/gnostoa/issues/456#issuecomment-6380966048
    title: "The owner's selection of Option A: a separate critical repair in the single mutating lane"
  - id: route
    resource: https://github.com/ktogias/gnostoa/issues/456#issuecomment-6381041187
    title: "The Router's admitted boundary for the repair"
  - id: scope-request
    resource: https://github.com/ktogias/gnostoa/issues/456#issuecomment-6381050596
    title: The measured scope addition and its options
  - id: scope-packet
    resource: https://github.com/ktogias/gnostoa/issues/456#issuecomment-6381162498
    title: "The Router's S1 authority and preparation packet"
  - id: architecture-review
    resource: https://github.com/ktogias/gnostoa/issues/456#issuecomment-6381094909
    title: "The PAO's review of the scope addition"
  - id: owner-scope
    resource: https://github.com/ktogias/gnostoa/issues/456#issuecomment-6384962886
    title: "The owner's selection of S1: the backend line, its test literal, and the bounded preparation substitute"
  - id: advisory-snapshots-1
    resource: https://github.com/ktogias/gnostoa/issues/456#issuecomment-6381107895
    title: The exact snapshots of GHSA-v4x8-3wr5-3wq8 and GHSA-9vhv-jxww-xfm5, with their extraction rule
  - id: advisory-snapshots-2
    resource: https://github.com/ktogias/gnostoa/issues/456#issuecomment-6381108579
    title: The exact snapshots of GHSA-567q-5qvw-pf92 and GHSA-xmj3-9gf7-h52w, with their extraction rule
  - id: prior-art-certifi
    resource: ./0115-refresh-the-development-lock-certifi-for-a-compromised-root.md
    title: The certifi refresh, reused as the evidence pattern only
  - id: prior-art-urllib3
    resource: ./0095-refresh-vulnerable-development-dependency-pins.md
    title: The urllib3 refresh, reused for its fix-version and nothing-else-moves rules only
  - id: preparation
    resource: ./0090-require-pre-candidate-preparation-receipts-for-non-hook-authoring.md
    title: The pre-candidate preparation receipts, whose authority path this change touches
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
  id: kit.decision.0116.refresh-the-development-lock-filelock-and-setuptools-pins
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /decisions/0115-refresh-the-development-lock-certifi-for-a-compromised-root.md
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

# Refresh the development lock's filelock and setuptools pins for four advisories

## Context

`requirements/development.lock` pinned `filelock==3.32.3` and `setuptools==83.0.0`.
Four advisories against them were published on 2026-10-23. Because an advisory page can
change, each is bound to a retained snapshot: the exact body of `GET /advisories/<id>` on
GitHub's REST API, published on the Work Item with its extraction rule and SHA-256
(sources `advisory-snapshots-1` and `advisory-snapshots-2`).

| Advisory | Package | Severity | Vulnerable range | First patched | Snapshot SHA-256 |
|---|---|---|---|---|---|
| GHSA-v4x8-3wr5-3wq8 (CVE-2026-112940) | filelock | high | `>= 3.20.4, <= 4.2.0` | 4.2.1 | `3febff3b5661fd310f06d64bbc8ec1b8fc199e04e0851f3dd3f00840a5f5c4c1` |
| GHSA-9vhv-jxww-xfm5 (CVE-2026-112913) | filelock | low | `>= 3.20.4, <= 4.2.0` | 4.2.1 | `80807e4eadb9ff03fcff60f17eefe93e45a7161d8ee528384da544b57745bc84` |
| GHSA-567q-5qvw-pf92 (CVE-2026-112907) | filelock | low | `>= 3.22.0, <= 4.2.0` | 4.2.1 | `5eab7f91ea0e9c69e6fee5e71ca355a98a48255d2dacab1a0e8a9adc02ab6a26` |
| GHSA-xmj3-9gf7-h52w | setuptools | low | `>= 38.2.2, < 84.1.0` | 84.1.0 | `b7e8bb268a6dfa9b4ad46dcc84d3b802fa37334433e141e53493b7154f973ea9` |

None is withdrawn. The high filelock advisory concerns `ReadWriteLock`, whose SQLite
database is reopened by name. The other three concern Windows behaviour.

`ci/verify extended` fails its `development_audit` quality gate as a result, and the
required `regression` gate fails with it whenever `extended` is routed `RUN`. The runtime
lock is unchanged and declares neither package. Following Decision 0055, that is a
declaration, not an observation of any published image. This changes the development and
CI toolchain, including the release-build backend, so it is a `critical` change (owner
selection, source `owner-selection`), the single mutating lane ahead of #455.

## Prior-art and reuse disposition

No custom work was written. The repository already owns the mechanism that found this
(`pip_audit` behind `development_audit`) and the mechanism that fixes it: the wheel-only,
hash-required lock, re-rendered by its own `tools/requirements_lock.py` with PyPI's
non-yanked wheel digests. Decision 0115 is reused as the **evidence pattern**, and
Decision 0095 for its rules that the fix version is pinned and nothing else moves. Neither
is reused as authority: neither grants standing permission to refresh pins, and neither
does this Decision. The review is the proportionate one of Decision 0062, with the
inheritance routed as Decision 0099 requires.

The fixes are the vendors' own releases, so no alternative fix was weighed. Later
releases exist (filelock 4.2.2–4.2.4, setuptools 84.2.0–84.2.1). Their notes name no
security fix, so the first patched versions are pinned, as Decision 0095 does.

## Decision

1. **The lock records `filelock==4.2.1` and `setuptools==84.1.0`,** each with its wheel's
   exact SHA-256. `python -m tools.requirements_lock --lock requirements/development.lock
   --write` re-rendered the lock after the two version strings were set, and its output
   differs from the parent's in exactly those two entries.

2. **The artefacts are verified, not an API response.** Each wheel was downloaded with a
   request that fails on an HTTP error, into a separate untrusted directory, and read as
   a zip without executing it:

   | | filelock 4.2.1 | setuptools 84.1.0 |
   |---|---|---|
   | wheel | `filelock-4.2.1-py3-none-any.whl` | `setuptools-84.1.0-py3-none-any.whl` |
   | size | 162,455 bytes, matching the index | 819,380 bytes, matching the index |
   | SHA-256, computed locally | `7be2662e9e826b9bba28afc0f843a123280d799a2ea44bb5d35ccec67905ae44`, matching the index | `5231689c6ac8156cd155cfb98c3fd6fb252c3e7e9bd3d78b64d3c55f132624c9`, matching the index |
   | metadata | `Name: filelock`, `Version: 4.2.1`, `Requires-Python: >=3.11` | `Name: setuptools`, `Version: 84.1.0`, `Requires-Python: >=3.10` |
   | required dependencies | none | none |
   | index status | not yanked | not yanked |

   Both cover the supported Python 3.11 and 3.12.

3. **The consumers are compatible.** In the development image, `filelock` is required only
   by CacheControl 0.14.4's `filecache` extra, which pip-audit's cache uses. filelock
   4.0.0's breaking changes are confined to `SoftReadWriteLock`. CacheControl's file cache
   imports `BaseFileLock` and uses `FileLock(path + ".lock")`, and in an image built from
   this lock it stores, reads and deletes an entry under a `UnixFileLock`. `setuptools` is
   required by no installed distribution except through optional extras; the repository
   uses it as its build backend.

4. **The build backend's declaration moves with the pin.** `tools/release_smoke.py`
   builds with `python -m build --no-isolation`, so the backend is the lock's setuptools,
   and `build` refuses one that does not match `pyproject.toml`'s `[build-system]
   requires`. Measured on the parent tree, with setuptools 84.1.0 installed:

   | `pyproject.toml` `[build-system] requires` | `python -m build --no-isolation` |
   |---|---|
   | `setuptools==83.0.0`, unchanged | exit 1, `ERROR Missing dependencies: setuptools==83.0.0` |
   | `setuptools==84.1.0` | exit 0, both distributions built |

   So that one line becomes `requires = ["setuptools==84.1.0"]`. No other byte of
   `pyproject.toml` changes, including every Ruff section. The test
   `test_release_build_frontend_and_backend_are_pinned` expects the new version. `release
   smoke` passes on the parent in an image from the previous lock, and on this change in
   an image from this lock.

5. **The audit is recorded before and after, bound to the exact locks.** The commands are,
   literally:

   ```
   python -m pip_audit --no-deps --strict --progress-spinner off --requirement requirements/development.lock
   python -m pip_audit --no-deps --strict --progress-spinner off --requirement requirements/runtime.lock
   ```

   The environment is Python 3.12.14 and `pip-audit` 2.10.1, in the repository's
   `development` image.

   | | development lock | runtime lock |
   |---|---|---|
   | before, main `4e4ced3af63b4208bd31e814bab55cb4f8e28c98` | SHA-256 `2a941975aa8210ce2ac54ed56377d63f4d3e9162a4a9df4c6289073202fbb805`: **exit 1**, `Found 4 known vulnerabilities in 2 packages` (CVE-2026-112940, CVE-2026-112913, CVE-2026-112907, GHSA-xmj3-9gf7-h52w) | SHA-256 `35e36da52f8b4fa19bfe4239d0918ebdb0b0a09b2ad72d087fb345b6f41a02ed`: exit 0, no known vulnerability |
   | after | SHA-256 `8f2097c13606748878c3827788d2fa5f03fd6932fcbb1db89b2990925c03f85a`: **exit 0**, no known vulnerability | unchanged: exit 0 |

6. **The resolution is proved, and the proof names its environment.** In an image built
   from the previous lock, this command resolves. `--require-hashes` and `--only-binary
   :all:` are in force through the lock's own option lines, which `--requirement` reads.

   ```
   python -m pip install --dry-run --quiet --report /tmp/pip-resolution.json \
     --requirement requirements/development.lock
   ```

   Its `install` list holds exactly two entries, `filelock 4.2.1` and `setuptools 84.1.0`:
   no transitive distribution moves. In the `development` image rebuilt from this lock,
   all 68 of its pins are installed, hash-checked, at their locked versions:
   - 11 by the runtime lock's install, which runs first;
   - the other 57 by the development lock's own install report.

7. **Preparation authority.** `pyproject.toml` is a preparation-authority path of Decision
   0090, so the exact-parent preparation wrapper refuses this candidate, and that refusal is
   retained as a refusal. The owner selected S1 (source `owner-scope`, from the packet in
   source `scope-packet`): a bounded substitute for this repair only.

   **What the substitute provides:**
   - the frozen parent and the exact tree;
   - a proof that the only `pyproject.toml` change is `build-system.requires`, with every
     Ruff section byte-equal;
   - unchanged preparation, style and verification sources;
   - the parent's own `ci/style --check`, and the `fast` and `security-fast` profiles, run
     on a disposable exact-tree workspace with isolated Git configuration;
   - a before-and-after tree identity check.

   **What it does not provide:** an ordinary preparation receipt with a retention nonce, and
   `ci/style --fix` normalization.

   `tools/candidate_prepare.py` and its authority list are unchanged, and this grants no
   standing authority over `pyproject.toml`.

8. **No standing update authority.** A later advisory is a later change, with its own
   class, evidence and owner approval.

## Consequences

- `development_audit` passes again, and with it the required `regression` gate, on main
  and on every candidate rebased onto it. #455 is rebound onto the integrated result, with
  its diff unchanged and only its invalidated exact-parent and head evidence regenerated.
- The release-build backend is setuptools 84.1.0.
- Nothing in the runtime lock, the application code, the CI behaviour, the audit criteria
  or the suppressions changes.
