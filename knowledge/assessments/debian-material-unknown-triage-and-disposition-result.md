---
type: Source
title: Debian material-UNKNOWN triage and owner disposition result
description: Candidate-bound result classifying the shipped Debian source packages with no Security Tracker vulnerability rows by runtime materiality, and recording the owner disposition of the five material unknowns.
status: draft
generated:
  by: agent:claude-opus-5
  at: "2026-08-20T16:45:00Z"
sources:
  - id: debian-unknown-disposition-work-item
    resource: https://github.com/ktogias/gnostoa/issues/70
    title: Disposition the remaining material Debian security unknowns
x-project-knowledge:
  id: kit.assessment.debian-material-unknown-triage-and-disposition-result
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0031-accept-bounded-material-debian-security-uncertainty-for-the-first-oci-candidate.md
    - kind: references
      target: /decisions/0022-define-the-security-boundary-for-the-first-gnostoa-oci-publication.md
---

# Debian material-UNKNOWN triage and owner disposition result

**Candidate-time evidence.** Measured on `linux/amd64` only. Re-observe before any
publication.

## Subject

| | |
|---|---|
| Source | `b7c39b5ea8f9d8b40b527cc0832e769f4bf8cc00` |
| Public digest | `sha256:90f3c4d8724e8749662cbd4fdeeade3b3b3a0de8d8d2815c375cdbc5a1a127f5` |
| Base | `python:3.12-slim@sha256:2c941e86…` |
| CPython / bundled Expat | 3.12.14 / 2.8.3 |
| Debian inventory | 118 binary, 82 source |

Tracker observed `2026-08-20T16:10:12Z`; Debian security-support observed
`2026-08-20T16:13:21Z`.

## Two corrections this record exists to preserve

**Correction 1 — HTTP 200 is not a tracker entry.** Earlier evidence treated an
HTTP 200 response as implying a Security Tracker entry. That is false: the
tracker serves a package page with a version table even when no CVE rows exist.
The authoritative signal is **CVE-row presence**. Re-measured across all 82
source packages: **55 with rows, 27 without**. The earlier figure of 24
tracker-less packages is superseded and must not be carried forward.

**Correction 2 — a vacuous linkability sweep was rejected.** An
`objdump`/`readelf`-based dependency sweep reported that *no* shipped ELF
referenced any of the candidate libraries. That was an artifact: neither tool
exists in the slim runtime. It was caught because `libgcc_s.so.1` reported zero
references while having been *directly measured* as mapped by the running
interpreter. The sweep was re-run with `ldd`, which is present. The zero result
is not evidence and is not retained.

## D lane — shipment hygiene freshness

Using the image's own configured supported channel — `trixie`, `trixie-updates`,
`trixie-security` — a simulated upgrade reports **0 upgradable packages and 0
from the security suite**. The `0 below-fixed` baseline holds and **no new
Decision-0022/D blocker was found**.

## Debian security-support status

The authoritative trixie list (`security-support.deb13`, 32 entries) matches
exactly **one** shipped source package: `rust-sequoia-sqv`, marked **`supported`**.
No shipped package is `limited` or `non-supported`. All 27 tracker-less packages
are therefore **NORMAL** at the measured timestamp.

## Materiality evidence

| observation | result |
|---|---|
| Mapped by the supported default runtime | only `gcc-14` (`libgcc_s`, `libstdc++`) |
| Supported-runtime subprocess targets | only `git`, which links `libc`, `libpcre2-8`, `libz` — none of the 27 |
| SUID/SGID ownership | none of the 27; all 11 belong to `shadow`, `util-linux`, `pam` |
| SUID/SGID **dependency** | 10 of 11 load `libselinux` (7), `libcap-ng` (7), `libmd` (6) |
| File capabilities | **zero** capability-bearing files in the whole rootfs |
| Listening services | **0** |
| Supported network-I/O entrypoint | none — `urlopen` exists only in a non-entrypoint module |
| Runtime TLS trust material | `ca-certificates`, via `/usr/lib/ssl/cert.pem` → `/etc/ssl/certs/ca-certificates.crt` |

Shipped-ELF dependency closure (via `ldd`) for the 27's libraries: `libselinux`
116, `libcap-ng` 60, `libmd` 60, `libgcc_s` 14, `libstdc++` 12, `libxxhash` 12,
`libsemanage` 6, `libgdbm`/`libreadline`/`libdebconfclient` 2 each; `libpsl`,
`libunistring`, `libnghttp3`, `libkeyutils` **0**.

## H1 — material UNKNOWN (5)

| package | relevance | bounded reason |
|---|---|---|
| `gcc-14` | runtime-linked | `libgcc_s.so.1` and `libstdc++.so.6` are directly mapped by the supported runtime; 14 and 12 shipped ELFs depend on them |
| `ca-certificates` | trust-material | supplies the bundle at the interpreter's default certificate-verification path |
| `libselinux` | privilege-adjacent | loaded by 7 of the 11 setuid-root executables |
| `libcap-ng` | privilege-adjacent | loaded by 7 of the 11 setuid-root executables |
| `libmd` | privilege-adjacent | loaded by 6 of the 11 setuid-root executables |

For each: the Debian Security Tracker exposes **no source-package vulnerability
entry** at the measured timestamp, Debian security support is normal, and no
supported fixed version above the installed version exists. None is called safe,
unaffected or vulnerability-free. No supported-runtime exploitability is claimed
for any of them, and the trust bundle's presence is not evidence of TLS safety.

## H2 — bounded low-material residual UNKNOWN (22)

`adduser`, `base-passwd`, `cdebconf`, `debconf`, `debian-archive-keyring`,
`debianutils`, `gdbm`, `hostname`, `init-system-helpers`, `keyutils`,
`liberror-perl`, `libpsl`, `libsemanage`, `libunistring`, `mawk`, `netbase`,
`nghttp3`, `readline`, `rust-sequoia-sqv`, `sysvinit`, `tzdata`, `xxhash`.

H2 means only that the bounded study observed no default-runtime
direct/link/subprocess use, no project-controlled-input route, no SUID/SGID
ownership, no file capability, no material network or trust role, and normal
Debian security support. **It does not establish absence of vulnerability, and
these packages are not cleared.**

## H3 — none

No classification was blocked on a missing obtainable observation.

## Owner disposition

The five H1 subjects are accepted as **bounded residual uncertainty** for this
exact scoped first-publication boundary. This is acceptance of uncertainty only:
not safety, not clearance, not a Decision-0022/D or /F exception, not proof that
no undisclosed vulnerability exists, not general image-security approval, and not
publication authorization. The invalidation and revisit conditions are recorded
in Decision 0031.

## CPython freshness at disposition time

`python:3.12-slim` index unmoved; docker-library declares 3.12 → 3.12.14. The
3.12 backports for CVE-2026-19672 (`#156043`) and CVE-2026-15806 (`#155971`) are
**merged but unreleased**; CVE-2026-17084 has **no 3.12 backport**. A
merged-but-unreleased fix is not a supported update, so Decision-0022/D has not
reactivated — but another base refresh remains plausibly near-term.

## Non-claims

Not claimed: that Debian certifies these packages vulnerability-free; that no
undisclosed vulnerabilities exist; that the five H1 packages are safe; that H1
means unaffected or H2 means cleared; complete image security; licence or legal
clearance; CPython residual clearance; Gnostoa-source security clearance; OCI
readiness; or publication authorization. `deployable_artifact` remains `false`,
`v0.1.0` remains immutable and unrelated to this candidate, and source-identity
preparation remains paused.
