---
type: Source
title: pip security provenance and update-channel evidence
description: Candidate-bound evidence on how pip entered the measured OCI candidate, which authority designates it vulnerable, and which supported routes can and cannot supply a fix.
status: draft
generated:
  by: agent:claude-opus-5
  at: "2026-08-19T13:05:00Z"
sources:
  - id: update-channel-work-item
    resource: https://github.com/ktogias/gnostoa/issues/58
    title: Define the supported update-channel rule for base-bundled OCI components
  - id: oci-security-boundary-work-item
    resource: https://github.com/ktogias/gnostoa/issues/50
    title: Define the first OCI runtime security and residual-risk publication boundary
x-project-knowledge:
  id: kit.assessment.pip-security-provenance-and-update-channel-evidence
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0025-define-supported-update-channel-semantics-for-base-bundled-oci-components.md
    - kind: references
      target: /decisions/0022-define-the-security-boundary-for-the-first-gnostoa-oci-publication.md
    - kind: references
      target: /assessments/first-oci-runtime-security-boundary-evidence.md
---

# pip security provenance and update-channel evidence

**Candidate-time evidence, not a standing certification.** Advisory feeds, base
images and upstream bundles all change independently of this repository. Re-read
before any publication or remediation.

## Measured subject

| | |
|---|---|
| Source revision | `20d0d0322e529c824a92a5082f1d031b7436fdb3` |
| Base image | `python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de` |
| Platform | Debian 13 trixie, **`linux/amd64` only** |
| Interpreter | CPython 3.12.13 |
| Component under study | pip 25.0.1 |

The public-surface digest at that revision is recomputable with
`knowledge surface-digest` and is deliberately not restated here.

## Observation times

| Observation | UTC |
|---|---|
| Provenance, shipment and exposure measurement | 2026-08-19T12:32–12:36 |
| Advisory state (primary and aggregator) | 2026-08-19T12:34, re-read 12:59:08 |
| CPython `ensurepip` bundled version | 2026-08-19T12:35:14, re-read 12:59:08 |
| Upstream `python:3.12-slim` manifest | 2026-08-19T12:35:42, re-read 12:59:08 |
| Candidate rebuild confirming pip identity | 2026-08-19T13:00 |

The re-read found the material fact pattern **unchanged**.

## Provenance

pip entered the image through **CPython's bundled `ensurepip` wheel**, not through
a package-index download and not through anything Gnostoa does.

```
Gnostoa Dockerfile   ARG PYTHON_BASE_IMAGE=python:3.12-slim@sha256:57cd7c3a…
  → pinned base layer history: CPython 3.12.13 built from source,
    ./configure … --with-ensurepip
  → `make install` runs ensurepip, installing its bundled wheel
  → pip 25.0.1
```

Corroborating, each observed independently on the pinned image itself rather than
inferred from an upstream recipe:

- no `get-pip.py` step appears in the pinned image's build history;
- no `PYTHON_PIP_VERSION`, `PYTHON_GET_PIP_URL` or `PYTHON_GET_PIP_SHA256`
  environment variable exists;
- `ensurepip._PIP_VERSION` and `ensurepip.version()` both report `25.0.1`;
- the installed distribution records `INSTALLER: pip` with **no** `direct_url.json`;
- the bundled wheel's SHA-256 is **byte-identical** to the SHA-256 published for
  the corresponding pip wheel by the component's own index.

That last point is the sharpest fact in this record: the *artifact* is the same one
the component's index serves, while the *delivery path* was the interpreter's
source tarball.

**Known limit.** The pinned base carries no OCI labels, so the exact
`docker-library/python` source-commit → image-digest relation is **UNKNOWN** and is
not inferred. What is bound is the layer history recorded inside the pinned image.

## Advisory authority and findings

The authoritative source is the **component maintainer's own advisory database**;
the aggregator that surfaced the records is an aggregator, not the vendor. Ten
aggregator records resolve to **five distinct vulnerabilities**, each mirrored
twice, none withdrawn. Every primary record traces to the component project's own
pull requests and commits and to the upstream security-announce list.

| Vulnerability | Affected range | Fixed in | Installed version inside range |
|---|---|---|---|
| CVE-2025-8869 | from `0` | 25.3 | **yes** |
| CVE-2026-1703 | from `0` | 26.0 | **yes** |
| CVE-2026-3219 | from `0` | 26.1 | **yes** |
| CVE-2026-6357 | from `0` | 26.1 | **yes** |
| CVE-2026-8643 | from `0` | 26.1.2 | **yes** |

`26.1.2` is the lowest observed release fixing all five; later fixed releases also
exist and are compatible with the measured runtime.

### Upstream qualification preserved, not promoted

The primary advisory for **CVE-2025-8869** states that the issue lies in pip's
fallback tar-extraction path used only on interpreters that do not implement
PEP 706, that on a PEP 706 interpreter pip does not use the vulnerable fallback
code, and that using such an interpreter is among the listed mitigations. The
measured interpreter is CPython 3.12.13.

This is recorded exactly as the upstream states it. It is **not** promoted into
component absence: the same advisory still lists the installed version inside its
affected range, and Decision 0022/**C** separates reachability from shipment
hygiene. Establishing component absence would require the authoritative component
mapping contemplated by Decision 0022/**G**, which this record does not perform.

## Shipment facts

| Fact | Result |
|---|---|
| pip package code shipped | yes |
| pip console entry points shipped | yes (three) |
| Runtime user can import and invoke pip | yes |
| Runtime user can modify system site-packages | no |
| Documented `knowledge` entrypoint imports pip | **no** — entrypoint executed and loaded modules inspected |
| `tools/`, `ci/`, `core/` import pip at runtime | **no** |
| `ensurepip` bundled pip wheel present in the final runtime | **yes** |

**Two pip-code representations ship in the measured candidate**: the installed
distribution with its console scripts, and the wheel bundled under
`ensurepip/_bundled`. The installed distribution's own `RECORD` covers only the
former, so an uninstall of the active distribution provably cannot remove the
latter, and `ensurepip` remains able to reinstall the affected version.

## Channel comparison

| | Channel | Supplies a fixed release now | Delivered the current pip | Requires an image-definition change |
|---|---|---|---|---|
| A | Base-image refresh | **no** — upstream digest unchanged and still carries the affected version | indirectly, by carrying B's output | base digest |
| B | Interpreter `ensurepip` bundle | **no** — the 3.12 series bundles the affected version at the release tag *and* at branch head | **yes** | base or interpreter line |
| C | Component-native supported update route | **yes** — fixed releases published, integrity-bound and runtime-compatible | no | explicit build step |
| D | Gnostoa-introduced step | derivative of C | no | explicit build step |

**A and B are structurally unable to supply a fix while the candidate stays on the
current interpreter minor series**, because the base image's pip *is* that series'
`ensurepip` bundle.

## Candidate remediation shapes — evidence only, none selected

| | Shape | Recorded limitation |
|---|---|---|
| R1 | Explicit pinned upgrade of the active component | An active upgrade **alone** leaves the affected bundled wheel in place; it is therefore not by itself proven shipment-hygiene remediation |
| R2 | True removal from the final runtime | A naive uninstall **alone** is not component absence; both the installed distribution and the bundled wheel must be measured |
| R3 | Base-image refresh | Observed **not currently sufficient**; do not assume it without fresh candidate-time evidence |
| R4 | Newer interpreter line or future base | Not currently available in this series; couples to the separate, unresolved interpreter vulnerability-binding question and must not be absorbed into a component remediation without separate admission |
| R5 | Explicit owner exception | A semantic alternative permitted by Decision 0022/D; recorded, not recommended, not created |

**No shape is selected here.** Selection is a separate lifecycle effect requiring
its own admission.

## Corrected residual taxonomy

The earlier framing was too broad and is corrected:

- **Decision 0022/E** — at the current evidence boundary the specifically
  established no-fix, default-unreachable util-linux residual is **CVE-2026-3184**:
  affected code shipped, no fix in the measured suite state, and default-runtime
  prerequisites previously established absent.
- **Decision 0022/G** — **CVE-2022-0563** remains component-absent for the
  measured image mapping.
- **Decision 0022/H** — the roughly 110 other open, no-fix Debian observations
  whose default-runtime applicability was never established remain **UNKNOWN**.
  They are **not** E-class residuals, and they are not dispositioned here.

## Observation limits

- `linux/amd64` only; no other platform was measured.
- The exact upstream base recipe commit is UNKNOWN, as recorded above.
- Interpreter and application vulnerability binding remain outside this record.
- Detailed per-vulnerability exploitability was deliberately **not** studied,
  because Decision 0022/D applies regardless of default-runtime reachability.
- Advisory state, upstream bundles and base images move independently; every
  finding above is bound to the observation times listed.

## Conclusion

The facts are complete on both sides, and no further measurement can decide the
remaining question. What was left was the **meaning** of "the same supported
channel" in Decision 0022/D when a component's delivery path and its fixing route
are different but both officially supported. That is an owner-semantic choice, and
it is recorded in
[Decision 0025](../decisions/0025-define-supported-update-channel-semantics-for-base-bundled-oci-components.md).
