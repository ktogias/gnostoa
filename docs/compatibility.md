# Compatibility and upgrade status

This page is a derived navigation projection of the current compatibility
boundary and canonical versioning contracts. It is deliberately narrower than
a release promise.

## Current baseline

`v0.1.0` remains the historical first source-only identity, and `v0.1.1`
remains the historical first OCI publication. The current pre-stable release
identity is [`v0.1.2`](https://github.com/ktogias/gnostoa/releases/tag/v0.1.2),
bound to commit `56f6c5ede9ff1d6585404d102aba8413994a2697`, tree
`6db26c9ce2eeaa82882bac82312f675ee19e6d0a` and source public-surface digest
`sha256:bd8078467b0189d535f222072253e1ef9e8f5fb780f55b56269738cb8f4ef095`.
Its public `linux/amd64` OCI artifact is
`ghcr.io/ktogias/gnostoa@sha256:0cd31a2a649c4ffede8972680c6779c981decf5ce8605f749fa7d58751472f80`.
The exact source identity, public-surface digest and OCI manifest digest are
distinct authorities. No `latest` tag, Python package or documentation site is
published.

Evaluation must therefore pin all of the following together:

- the exact source revision;
- the deterministic public-surface digest;
- the wheel, source-distribution or image digest;
- the project profile and schema identities; and
- the consuming project's toolkit lock.

Changing one identity requires revalidation. A matching version label alone is
not evidence that two artifacts or source trees are equivalent.

## Current released patch

[Decision 0043](../knowledge/decisions/0043-prepare-a-bounded-v0-1-2-b3-readiness-candidate.md)
prepared the `0.1.2` source/runtime candidate. Decision 0044 and the
[publication result](../knowledge/assessments/v0-1-2-source-and-oci-publication-result.md)
bind the later source and OCI publication effects. Consumers must still use
the immutable digest above rather than treating a version label as the
artifact identity.

The candidate rejects duplicate keys in standalone YAML and Markdown
frontmatter. YAML 1.2 requires unique mapping keys, so this is documented as
fail-closed handling of ambiguous invalid input; valid unique-key inputs are not
intended to change. A file that relied on last-key-wins behavior must remove the
duplicate and retain one explicit value before validation.

The declared native source floor remains Python 3.11. Centralized source tests
exercise CPython 3.11 and 3.12, while the current development and released OCI
runtime route remains Python 3.12. This establishes no support claim for another
interpreter, operating system or architecture.

## Compatibility layers

| Layer | Current rule |
|---|---|
| JSON Schema identity | Public schema IDs use a versioned `/schemas/v1/` namespace. A breaking schema contract requires a new major path and migration guidance. |
| Profile and policy contracts | Each profile or policy has its own version. A consumer pins the exact revision and verifies that specialization does not weaken inherited constraints. |
| Python distribution | The wheel is execution-only. It must be paired with the exact separately pinned public-source root and its digest. |
| OCI distribution | The released `linux/amd64` v0.1.2 image must be pinned as `ghcr.io/ktogias/gnostoa@sha256:0cd31a2a649c4ffede8972680c6779c981decf5ce8605f749fa7d58751472f80` and bound to the v0.1.2 source revision and public surface. The `0.1.2` tag alone is not the consumer identity, and no `latest` tag exists. |
| Knowledge bundles | A bundle is compatible only when it validates against the explicitly selected profile, schemas and policy set. |

The generic
[versioning and upgrade guidance](../guidance/reference/versioning-and-upgrades.md)
defines the intended PATCH, MINOR and MAJOR meanings for validation contracts.
It does not turn the pre-stable `v0.1.2` release into a long-term support or
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

The current release has no demonstrated compatibility matrix with an older
or newer release, automated migration tool, deprecation window, support
lifetime or rollback guarantee. Dependency/security scans and coverage evidence
are bounded release-candidate signals. Exact-lock Python license inventories and
CycloneDX 1.6 SBOMs now exist, but they do not cover base-image/system packages,
and do not constitute legal compatibility review. The Python locks now admit
only committed SHA-256 wheel identities, and the evidence records the exact
wheel selected for the current Python/platform environment. That prevents
unlisted package bytes but does not authenticate publishers, guarantee index
availability or establish release provenance. The published image carries
bounded runtime, provenance and digest-verification evidence, but availability
is not production readiness, deployment authorization, exact rebuild
reproducibility, general security or qualified legal clearance. These limits
must not be inferred from the presence of the `v0.1.2` source tag or `0.1.2`
image tag. See the
[publication result](../knowledge/assessments/v0-1-2-source-and-oci-publication-result.md).
