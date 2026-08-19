---
type: Source
title: util-linux security remediation result
description: Candidate-time evidence that the already-installed util-linux-derived packages were upgraded to the supported trixie-security versions, clearing Decision 0022's vendor-fixed-component blocker for the measured linux/amd64 candidate.
status: draft
generated:
  by: agent:claude-opus-5
  at: "2026-08-19T08:52:00Z"
sources:
  - id: remediation-work-item
    resource: https://github.com/ktogias/gnostoa/issues/54
    title: Apply the supported util-linux security update to the OCI runtime
  - id: debian-security-tracker
    resource: https://security-tracker.debian.org/tracker/data/json
    title: Debian Security Tracker data
x-project-knowledge:
  id: kit.assessment.util-linux-security-remediation-result
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0023-apply-the-supported-debian-util-linux-security-update-to-the-oci-runtime.md
    - kind: references
      target: /assessments/first-oci-runtime-security-boundary-evidence.md
---

# util-linux security remediation result

Candidate-time evidence. Vendor state changes; re-read before any publication.

## Admitted transaction

Entrance state on `linux/amd64`, Debian 13 trixie: **9** installed binary packages
derive from source `util-linux` at source version `2.41-5`. Target: source
`util-linux 2.41.5-0+deb13u1` from `Debian-Security:13/stable-security`, already
configured in the image — **no apt source change was needed**.

| Binary package | Installed | Target |
|---|---|---|
| `bsdutils` | `1:2.41-5` | `1:2.41.5-0+deb13u1` |
| `libblkid1` | `2.41-5` | `2.41.5-0+deb13u1` |
| `liblastlog2-2` | `2.41-5` | `2.41.5-0+deb13u1` |
| `libmount1` | `2.41-5` | `2.41.5-0+deb13u1` |
| `libsmartcols1` | `2.41-5` | `2.41.5-0+deb13u1` |
| `libuuid1` | `2.41-5` | `2.41.5-0+deb13u1` |
| `login` | `1:4.16.0-2+really2.41-5` | `1:4.16.0-2+really2.41.5-0+deb13u1` |
| `mount` | `2.41-5` | `2.41.5-0+deb13u1` |
| `util-linux` | `2.41-5` | `2.41.5-0+deb13u1` |

Three version forms for one source build — plain, epoch-bearing and `+really` —
so each is pinned explicitly. Simulated transaction before any edit: **9 upgraded,
0 newly installed, 0 to remove, 0 not upgraded.**

## Evidence

**RED → GREEN.** The same bounded assertion over *actual installed package state*
failed against the pre-remediation image for the intended reason — installed
binary and source versions did not equal the admitted target — and passes against
the remediated candidate for all nine packages, checking binary version, source
package, source version and architecture. A committed structural guard in the
existing Dockerfile test surface fails without the pins and passes with them.

**Complete dpkg delta.** 118 packages before and after; **identical package-name
set** (nothing added or removed); identical architecture set (all `amd64`);
**exactly 9 version changes, all with source `util-linux`**. No unrelated package
moved.

**Two independent no-cache builds.** Normalized complete package state
**identical**. Image IDs differ, which is expected: image-digest reproducibility
was not tested and is not claimed.

**Runtime boundary unchanged.** `uid=10001(kit)`, `ENTRYPOINT ["knowledge"]`,
`CapEff`/`CapPrm` `0`, bounding set `0xa80425fb` with `CAP_SYS_ADMIN` still absent,
0 usable fstab entries, 0 block devices, no udev/udisks/systemd, and the same 11
SUID/SGID files — identical before and after.

**Candidate-time vendor read-back** (tracker read `2026-08-19T08:39:21Z` and
`08:44:11Z`): before remediation, 7 of 29 resolved-with-fix trixie entries had the
installed version **below** the fixed version; after remediation, **0** remain
below. The two still-open entries are unchanged and remain separate residuals:
`CVE-2022-0563` (affected component not shipped — Debian's `chfn`/`chsh` come from
src `shadow`) and `CVE-2026-3184` (shipped but default preconditions absent,
Debian `nodsa: Minor issue`).

## Established

The demonstrated vendor-fixed util-linux publication-hygiene blocker from Decision
0022 is **remediated for the measured `linux/amd64` candidate**. The public-surface
digest changes from
`sha256:021f18107feb93be2d4c6e5d8dca7d73bf2247871fc100859ba576089f55772b` to the
candidate digest recorded in the Change Request, because `Dockerfile` is inside the
pinned surface.

`v0.1.0` continues to bind commit `ee808572d3930ec3dc50d350ae1ed25a0236bb6b` and
the digest above. **This candidate is a different source identity and is not
`v0.1.0`.** A new immutable source identity is therefore required before eventual
OCI publication — which does not make that release the next selected slice.

## Not established

Complete OCI readiness; complete image security; absence of vulnerabilities;
licence or legal clearance (still **NOT ESTABLISHED**); CPython, `pip` or
Gnostoa-source vulnerability binding; coverage of the Debian source packages
outside tracker coverage; non-`amd64` evidence; registry identity, permissions or
read-back; image-digest reproducibility; OS-package archival or byte-level
reproducibility; provenance; signing; attestation; production readiness.

Exact apt pins select versions only while those versions remain available from the
configured signed repository. No package bytes are archived and no hermetic OS
reconstruction is claimed.
