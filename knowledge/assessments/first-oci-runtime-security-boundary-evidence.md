---
type: Source
title: First OCI runtime security-boundary evidence
description: Timestamped decision-relevant evidence from two bounded read-only measurements of the v0.1.0 runtime image, covering the default-runtime privilege boundary, util-linux applicability and observed vendor-fix availability on linux/amd64.
status: draft
generated:
  by: agent:claude-opus-5
  at: "2026-08-18T23:40:00Z"
sources:
  - id: security-boundary-work-item
    resource: https://github.com/ktogias/gnostoa/issues/50
    title: Define the first OCI runtime security and residual-risk publication boundary
  - id: debian-security-tracker
    resource: https://security-tracker.debian.org/tracker/data/json
    title: Debian Security Tracker data
x-project-knowledge:
  id: kit.assessment.first-oci-runtime-security-boundary-evidence
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0022-define-the-security-boundary-for-the-first-gnostoa-oci-publication.md
    - kind: references
      target: /decisions/0020-establish-v0-1-0-as-the-first-source-only-pre-stable-release-identity.md
---

# First OCI runtime security-boundary evidence

Candidate-time evidence, not a standing certification. Security feeds change;
re-observe before any publication.

## Measured subject

| | |
|---|---|
| Source release | `v0.1.0` |
| Source commit | `ee808572d3930ec3dc50d350ae1ed25a0236bb6b` |
| Public-surface digest | `sha256:021f18107feb93be2d4c6e5d8dca7d73bf2247871fc100859ba576089f55772b` |
| Base image | `python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de` |
| Platform | Debian 13 trixie, **linux/amd64 only** |
| Interpreter | CPython 3.12.13 |

## Measured default-runtime boundary

Non-root `uid=10001(kit)`; `ENTRYPOINT ["knowledge"]`; `CapEff`, `CapPrm`,
`CapInh` all `0`; bounding set `0xa80425fb` with **`CAP_SYS_ADMIN` absent**;
`/etc/fstab` carries **0** usable entries; **0** block devices; **0** loop
devices; no udev, udisks2 or systemd. `apt-get update` is denied to the runtime
user.

## Component inventory boundary

118 dpkg-managed packages, reproducible across two independent no-cache builds
(identical normalized inventory). 118/118 carry readable copyright metadata (106
DEP-5-like, 12 free-form, 82 unique files, 3 shared/symlinked).

The dpkg list does **not** describe the image: CPython is **not** dpkg-managed
(`/usr/local`, 1,783 files without a dpkg owner). Nine Python distributions are
installed; `requirements/runtime.lock` pins **7**, so `pip` and `gnostoa` itself
sit outside existing dependency evidence, as does the interpreter.

## util-linux applicability, linux/amd64, measured default runtime

Nine studied findings:

- **2 — affected component not shipped.** `chfn`/`chsh` come from src `shadow`,
  not util-linux; no shipped util-linux-derived binary references `setpwnam`.
- **7 — shipped, but the known preconditions are absent** under the measured
  default runtime: SUID `mount(8)` findings need `CAP_SYS_ADMIN` and a mountable
  target or user-mountable fstab entry, none of which exist; the `login(1) -h`
  finding needs a network login service; the `libblkid` findings need a block
  device or partition-table input, and no shipped Python extension nor CPython
  links `libblkid`.
- **0 — observed as applicable under the measured default runtime.**
- **0 — remaining applicability UNKNOWN** among the nine.

**No claim is made that the image is secure, that these findings are irrelevant,
or that any particular version fixes everything.**

## Vendor status observed

Debian Security Tracker retrieved **2026-08-18T23:23:44Z** and re-read at
**2026-08-18T23:37:21Z**; the nine findings showed **no discrepancy** between the
two reads.

Per-suite state for the four newest findings: `trixie` → `2.41-5` **vulnerable**;
`trixie (security)` → `2.41.5-0+deb13u1` **fixed**; `sid` → `2.42.2-3` fixed.
Three are covered by **DSA-6442-1**. The tracker's JSON `status: resolved` refers
to the fix existing in the security suite and must not be read as the installed
version being unaffected — the per-suite table is the authoritative view.

**An applicable supported security update is available**: the image's own
configured sources offer `util-linux`, `mount` and `libblkid1` at
`2.41.5-0+deb13u1` from `trixie-security`, while the installed version is
`2.41-5`.

**A base-digest refresh alone does not fix this.** The current official
`python:3.12-slim` (observed digest `sha256:2c941e86…` at
`2026-08-18T23:16:44Z`, debian 13 trixie, amd64) also ships `2.41-5`.

## Observation limits

- **`linux/amd64` only.** No other architecture was measured.
- User-level container-package listing was **inaccessible** (`403`, token lacked
  `read:packages`).
- Vulnerability binding is **absent** for CPython, `pip` and Gnostoa source.
- 24 of 82 source packages have no tracker entry; absence of an entry is not
  absence of vulnerability.
- Image-digest reproducibility was **not tested**; only inventory reproducibility
  was established.
- Reachability of `libblkid` under consumer-supplied commands is bounded by
  observation, not proof.
- **Licence/legal conclusion remains NOT ESTABLISHED.** Metadata coverage was
  measured; no legal review was performed or claimed.

## Re-checking vendor state

Source: `https://security-tracker.debian.org/tracker/data/json` for machine
state, and the per-CVE tracker pages for descriptions and the per-suite table,
which the JSON dump omits. Package availability is re-checkable read-only with
`apt-cache policy` against the configured suites.
