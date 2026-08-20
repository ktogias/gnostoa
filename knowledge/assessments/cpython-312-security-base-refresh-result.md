---
type: Source
title: CPython 3.12 security-base refresh result
description: Candidate-bound result for refreshing the first-party OCI runtime onto the released Python 3.12.14 official security base, with the measured interpreter, bundled-Expat, Debian-parity, preservation and residual evidence.
status: draft
generated:
  by: agent:claude-opus-5
  at: "2026-08-20T17:00:00Z"
sources:
  - id: cpython-base-refresh-work-item
    resource: https://github.com/ktogias/gnostoa/issues/68
    title: Refresh the official Python 3.12 OCI base for security fixes
x-project-knowledge:
  id: kit.assessment.cpython-312-security-base-refresh-result
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0030-refresh-the-official-python-312-base-for-cpython-security-fixes.md
    - kind: references
      target: /decisions/0022-define-the-security-boundary-for-the-first-gnostoa-oci-publication.md
---

# CPython 3.12 security-base refresh result

**Candidate-time evidence.** Measured on `linux/amd64` only. Re-observe before any
publication.

## Subject

| | |
|---|---|
| Pre-change source | `3163d61f8ff1c841e12aa62e52f6f3224aa60641` |
| Pre-change public digest | `sha256:72a824d04e5e5ac800bbe63f0f5c1fb217ec5ca3ef3e1edff0ec2c72a549c4c8` |
| Old base | `python:3.12-slim@sha256:57cd7c3a…` |
| New base | `python:3.12-slim@sha256:2c941e86…` |
| New `linux/amd64` platform | `sha256:876416ec…` |
| Implementation | one `Dockerfile` base-digest line |

## Decision-0022/D evidence

The bounded study examined the 32 security entries in the released Python 3.12.14.
**31 bind to the installed 3.12.13 state**; the remaining entry is documentation
regeneration. The affected code and components are present in the measured
runtime, and a fixed release exists in the same supported channel.

Binding rests on **direct source comparison and version binding**, not on
behavioural probes. 16 stdlib modules differ between 3.12.13 and 3.12.14, among
them:

- **CVE-2026-3644** — `http/cookies.py` gains `_has_control_character(key, val)`
  raising `CookieError`; absent in 3.12.13.
- **CVE-2026-2297** — `importlib/_bootstrap_external.py` adds
  `SourcelessFileLoader` to the `io.open_code()` isinstance tuple; absent in
  3.12.13.

Most behavioural probes attempted during the study were **non-discriminating** —
they raised the same result on both images because they reached a different
pre-existing check, or never reached the fixed path at all. They are recorded as
non-evidence rather than presented as confirmation.

**Decision 0022/F is not established.** No finding was demonstrated reachable
through the documented supported default runtime. That is a statement about what
was demonstrated, not a claim that CPython findings are harmless.

## Component boundary

`pyexpat.cpython-312-x86_64-linux-gnu.so` links **only libc** — no
`libexpat.so.1`. CPython therefore uses its **bundled** Expat, and the release's
libexpat update binds to that bundled copy. Debian's `libexpat1` was already
`2.8.3-1~deb13u1` in both images and is not used by Python. Treating this as a
system-library finding would have bound the wrong component.

| | baseline | candidate |
|---|---|---|
| CPython | **3.12.13** | **3.12.14** |
| Bundled Expat | **2.7.4** | **2.8.3** |
| CPython origin | upstream source, not dpkg-managed | unchanged |
| Debian suite | 13 trixie | 13 trixie |

## Whole-image delta

| | result |
|---|---|
| dpkg package count | 118 → 118 |
| dpkg **binary** versions | **identical**, 0 differences |
| dpkg **source** versions | **identical**, 82 source packages |
| util-linux family | `2.41.5-0+deb13u1` preserved |
| Git | `1:2.47.3-0+deb13u1` preserved |
| Python distributions | 8, unchanged |

The refresh moves **only** CPython and its bundled Expat. The util-linux and Git
pins succeeded as no-ops rather than needing revision, which is why no
compatibility adjustment was required.

## Preservation

| | result |
|---|---|
| `import pip` / `import ensurepip` | absent |
| pip entrypoints, bundled wheels, pip metadata | 0 / 0 / 0 |
| X3 `S1 == payload == S4` | GREEN |
| USER / uid / gid | `kit` 10001:10001 unchanged |
| ENTRYPOINT / CMD / WORKDIR | unchanged |
| `CapBnd` | `00000000a80425fb` unchanged |
| SUID/SGID | 11 files unchanged |
| `knowledge --help`, validation, context-pack, self-check | PASS |

The Decision 0026 lower-layer history residual is unchanged; no claim is made that
historical-layer bytes disappear.

## Public-contract digest

The clean public digest changes because **`Dockerfile` content changed**, not
because base-image bytes entered digest semantics. P4 remains unselected and image
bytes remain outside `public_surface_digest` membership. Git, runtime and vendored
forms are required to agree on the new value.

## Post-release residuals — DEFERRED, not accepted

Three CPython security findings were disclosed **after** the 3.12.14 release and
have **no released supported 3.12 fix** at the measured timestamp:

| CVE | issue | 3.12 status |
|---|---|---|
| CVE-2026-19672 tarfile extraction-filter bypass | gh-155999 | backport **open** |
| CVE-2026-15806 HTTPPasswordMgr URL-scheme scope | gh-155694 | backport **open** |
| CVE-2026-17084 stringprep / IDNA 2003 | gh-155292 | **no 3.12 backport exists** |

All three components are present in 3.12.14. Two have 3.12 backport pull requests
that are **open, not merged**; the third has none. An unreleased merge is not a
supported image update.

They are retained as bounded **Decision-0022/E residuals**: deferred, **not**
accepted as safe, **not** waived, with no security exception created and no claim
of absence or applicability safety. Their authoritative status must be re-read
before any later immutable-source or publication candidate, and if a released
supported 3.12 fix appears, Decision 0022/D must be re-evaluated against that
later candidate.

## Non-claims

The resulting image is **not** described as free of CPython vulnerabilities, fully
patched, secure, vulnerability-free or publication-ready. Not established:
Decision-0022/F clearance for every CPython path; absence of CPython residuals;
complete image security; complete OCI readiness; OCI reproducibility; complete
provenance; licence or legal clearance; multi-architecture security; or
publication authorization.

## Frozen OCI checkpoint

Decisions 0022–0029 remain the governing authorities and are unchanged. The
util-linux vendor-fixed blocker and the pip Decision-0022/D effective-runtime
blocker remain cleared. X3 P2/P5 source binding and D-A source-form public-digest
authority remain established. Residuals: pip lower-layer history, development
host-context dependence, the X3 raw named-`candidate` substitution bounded by
in-build checks, and the three post-3.12.14 CPython findings above. Deferred:
Decision-0022/H Debian unknowns, licence and legal clearance, registry identity
and permissions, publication, and the public OCI security claim. `v0.1.0` remains
immutable at `ee808572d3930ec3dc50d350ae1ed25a0236bb6b` and unrelated to this
image candidate; source-identity preparation remains paused;
`deployable_artifact` remains `false`.
