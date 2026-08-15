# Compatibility and upgrade status

This page is a derived navigation projection of the current compatibility
boundary and canonical versioning contracts. It is deliberately narrower than
a release promise.

## Current baseline

No Gnostoa package, image or documentation site has been released. The source
currently identifies itself as `0.1.0`, but that version is still a release
candidate rather than an established compatibility baseline. Evaluation must
therefore pin all of the following together:

- the exact source revision;
- the deterministic public-surface digest;
- the wheel, source-distribution or image digest;
- the project profile and schema identities; and
- the consuming project's toolkit lock.

Changing one identity requires revalidation. A matching version label alone is
not evidence that two artifacts or source trees are equivalent.

## Compatibility layers

| Layer | Current rule |
|---|---|
| JSON Schema identity | Public schema IDs use a versioned `/schemas/v1/` namespace. A breaking schema contract requires a new major path and migration guidance. |
| Profile and policy contracts | Each profile or policy has its own version. A consumer pins the exact revision and verifies that specialization does not weaken inherited constraints. |
| Python distribution | The wheel is execution-only. It must be paired with the exact separately pinned public-source root and its digest. |
| OCI distribution | A released consumer image must be pinned by immutable digest and bound to the same source revision and public surface. No image has been released yet. |
| Knowledge bundles | A bundle is compatible only when it validates against the explicitly selected profile, schemas and policy set. |

The generic
[versioning and upgrade guidance](../guidance/reference/versioning-and-upgrades.md)
defines the intended PATCH, MINOR and MAJOR meanings for validation contracts.
It does not turn the unpublished `0.1.0` candidate into a long-term support or
cross-version compatibility promise.

## Safe evaluation upgrade

For an evaluation or future release transition:

1. retain the previous source, artifact and lock identities for rollback;
2. stage the proposed source and executable artifact under new exact pins;
3. verify archive metadata, commands, license and notice against that source;
4. validate the runtime lock and every affected profile, policy and bundle;
5. compare validation and bounded-context results and inspect changed
   enforcement;
6. migrate explicitly when a schema or policy contract requires it; and
7. switch pins only after the new evidence is accepted through the consuming
   project's own change process.

A source-root path is only a location. It does not authenticate the source or
the executable. Mutable branches, tags and local image names are not adequate
upgrade identities.

## Release evidence

The repository release smoke can write a deterministic JSON evidence manifest
after both the wheel and source distribution pass clean-install checks:

```bash
python ci/release_smoke.py \
  --output-dir /tmp/gnostoa-dist \
  --source-revision <exact-git-object-id> \
  --evidence-manifest /tmp/gnostoa-release-evidence.json
```

The manifest records package identity, console commands, source revision,
public-surface digest, artifact and metadata hashes, and hashes of the declared
validation and context-pack results. Manifest generation rejects a revision
that differs from `HEAD` or a dirty Git tree. The result contains filenames
rather than local absolute paths. It is build evidence, not a signature,
attestation, published provenance record or substitute for independent
verification.

## Not yet promised

The current candidate has no demonstrated compatibility matrix with an older
or newer release, automated migration tool, deprecation window, support
lifetime or rollback guarantee. Dependency/security scans and coverage evidence
are bounded release-candidate signals. Exact-lock Python license inventories and
CycloneDX 1.6 SBOMs now exist, but they do not cover base-image/system packages,
and do not constitute legal compatibility review. The Python locks now admit
only committed SHA-256 wheel identities, and the evidence records the exact
wheel selected for the current Python/platform environment. That prevents
unlisted package bytes but does not authenticate publishers, guarantee index
availability or establish release provenance. These limits must be resolved or
carried explicitly before artifact publication; they must not be inferred from
the presence of a `0.1.0` version.
