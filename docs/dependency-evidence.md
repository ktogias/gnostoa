# Dependency license and SBOM evidence

This page is a derived navigation projection of the exact machine-readable
reports. The lock files, installed distribution metadata and generated CI
artifacts remain the evidence rather than this explanation.

The scheduled or manually dispatched `extended` suite records four
machine-readable dependency-transparency reports alongside the vulnerability,
coverage, static-analysis and tracked-tree secret-scan reports:

| Report | Exact scope |
|---|---|
| `runtime-license-inventory.json` | Installed Python distributions named by `requirements/runtime.lock` |
| `development-license-inventory.json` | Installed Python distributions named by `requirements/development.lock` |
| `runtime-sbom.cdx.json` | CycloneDX 1.6 representation of the runtime inventory |
| `development-sbom.cdx.json` | CycloneDX 1.6 representation of the development inventory |

Run the same collector locally from the exact development environment:

```bash
GNOSTOA_QUALITY_OUTPUT=/tmp/gnostoa-quality-evidence ./ci/verify extended
```

`quality-summary.json` content-addresses every report and records counts rather
than replacing the detailed evidence. Each inventory binds an exact lock entry
to an installed distribution name and version. A missing distribution, a
version mismatch, an invalid modern `License-Expression` or a completely absent
license declaration fails the gate.

Modern SPDX expressions are preserved and validated. Older `License` fields
and Trove classifiers are recorded with their source and marked for manual
review. Ambiguous declarations remain plain license names in the SBOM instead
of being silently converted into a more precise SPDX expression. This makes the
unknown visible; it does not resolve it by inference.

The SBOM producer uses stable package URLs, deterministic component references
and a source/lock-derived UUID. It omits a wall-clock timestamp, then validates
the result against the strict CycloneDX 1.6 JSON schema. Re-running against the
same source revision, locks and installed distribution metadata therefore
produces byte-stable reports.

## Deliberate limits

- Package metadata is supplier-declared inventory evidence, not legal advice,
  license compatibility approval or proof that every file has one license.
- The reports do not inventory the Python interpreter, Debian/base-image
  packages, the pinned `git` system package, hosted services or untracked build
  inputs.
- Exact names and versions are not package-artifact identity. Until the lock
  files contain artifact hashes, an index could serve different bytes under the
  same version and invalidate the evidence.
- The SBOM describes the flat exact lock sets. It does not invent a direct or
  transitive dependency graph that the current lock format does not record.
- The reports are unsigned CI artifacts with limited retention. They are not a
  release attestation, provenance statement or publication authorization.

Complete OCI/system-component inventory, manual license review, lock artifact
hashes and release provenance remain required before artifact publication.
