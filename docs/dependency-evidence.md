# Dependency license and SBOM evidence

This page is a derived navigation projection of the exact machine-readable
reports. The lock files, installed distribution metadata and generated CI
artifacts remain the evidence rather than this explanation.

The scheduled or manually dispatched `extended` suite records six
machine-readable dependency-transparency reports alongside the vulnerability,
coverage, static-analysis and tracked-tree secret-scan reports:

| Report | Exact scope |
|---|---|
| `runtime-artifact-selection.json` | Exact runtime wheel selected by pip and admitted by the committed SHA-256 allow-list |
| `development-artifact-selection.json` | Exact development wheels selected by pip and admitted by the committed SHA-256 allow-list |
| `runtime-license-inventory.json` | Installed Python distributions named by `requirements/runtime.lock` |
| `development-license-inventory.json` | Installed Python distributions named by `requirements/development.lock` |
| `runtime-sbom.cdx.json` | CycloneDX 1.6 representation of the runtime inventory |
| `development-sbom.cdx.json` | CycloneDX 1.6 representation of the development inventory |

Run the same collector locally from the exact development environment:

```bash
GNOSTOA_QUALITY_OUTPUT=/tmp/gnostoa-quality-evidence ./ci/verify extended
```

`quality-summary.json` content-addresses every report and records counts rather
than replacing the detailed evidence. Both locks enable pip hash-checking mode,
admit only non-yanked wheels and carry SHA-256 allow-lists for every exact
direct and transitive requirement. Installation uses `--require-hashes` and
`--only-binary=:all:` explicitly, so missing hashes, unlisted bytes, undeclared
dependencies and source-distribution fallback fail closed.

The collector runs pip's supported dry-run installation report for the current
Python/platform environment, removes host-specific fields and verifies that
every selected wheel is present in the committed allow-list. Each inventory
then binds that selected wheel SHA-256 to the installed distribution name,
version and package-declared license metadata. A missing or yanked artifact,
hash mismatch, missing distribution, version mismatch, invalid modern
`License-Expression` or completely absent license declaration fails the gate.

Container builds also retain read-only pip version-1 install reports under
`/opt/gnostoa/.evidence/`. Those raw, environment-specific build diagnostics
are not the sanitized uploaded reports, a cross-platform lock or release
provenance; the development report contains only distributions newly installed
after the runtime layer.

Modern SPDX expressions are preserved and validated. Older `License` fields
and Trove classifiers are recorded with their source and marked for manual
review. Ambiguous declarations remain plain license names in the SBOM instead
of being silently converted into a more precise SPDX expression. This makes the
unknown visible; it does not resolve it by inference.

The SBOM producer uses stable package URLs, the selected wheel SHA-256,
deterministic component references and a source/lock/selection-derived UUID. It
omits a wall-clock timestamp, then validates the result against the strict
CycloneDX 1.6 JSON schema. Re-running against the same source revision, locks,
Python/platform selection and installed distribution metadata therefore
produces byte-stable reports.

Refresh one lock only when its exact pins are intentionally reviewed:

```bash
python -m tools.requirements_lock \
  --lock requirements/runtime.lock \
  --write
```

The refresh reads current non-yanked wheel identities from PyPI and rewrites
the whole lock only after every pin has at least one wheel. The resulting diff,
not the network response alone, is the reviewable admission record. Run the
same command separately for the development lock.

## Deliberate limits

- Package metadata is supplier-declared inventory evidence, not legal advice,
  license compatibility approval or proof that every file has one license.
- The reports do not inventory the Python interpreter, Debian/base-image
  packages, the pinned `git` system package, hosted services or untracked build
  inputs.
- The selected wheel SHA-256 establishes artifact identity for the recorded
  environment. A different admitted Python/platform environment may select a
  different committed wheel hash.
- The sanitized selection is a fresh resolver read-back; installed metadata
  confirms distribution name and version but does not independently re-hash
  installed files back into the wheel archive. The raw container build reports
  are supporting diagnostics, not signed installation provenance.
- Hash checking prevents unlisted bytes from entering this scope, but does not
  authenticate a publisher, guarantee index availability or establish release
  provenance.
- The summary checks every returned `pip-audit` row against the exact lock and
  lists any lock identities omitted from the provider's no-finding JSON. An
  omitted row is visible and is not silently counted as package-level evidence.
- The pip installation report is a supported pip interface, not a PyPA
  interoperability standard or a lock-file format.
- The SBOM describes the flat exact lock sets. It does not invent a direct or
  transitive dependency graph that the current lock format does not record.
- The reports are unsigned CI artifacts with limited retention. They are not a
  release attestation, provenance statement or publication authorization.

Complete OCI/system-component inventory, manual license review, publisher and
supply-chain assurance and release provenance remain required before artifact
publication.
