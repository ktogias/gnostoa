# Compatibility and upgrade status

This page is a derived navigation projection of the current compatibility
boundary and canonical versioning contracts. It is deliberately narrower than
a release promise.

## Current baseline

`v0.1.0` remains the historical first source-only identity, `v0.1.1` remains
the historical first OCI publication, and `v0.1.2` remains the historical
B3-readiness patch. The current pre-stable release identity is
[`v0.2.0`](https://github.com/ktogias/gnostoa/releases/tag/v0.2.0), bound to
commit `39aa4f25bdf46811600d4a0f6f9c0da52b73c542`, tree
`866c8c489c9052c566bd65b6e798567d4a284f16` and source public-surface digest
`sha256:a85ac8dde00f1ed8fb0425de08597828e97c246ec17ce6556f3f222b27ddb1c1`.
Its public `linux/amd64` OCI artifact is
`ghcr.io/ktogias/gnostoa@sha256:f89bf32c0c4b86bac71fa008579b2385e6ae39bf4822f685479c4f2cc22bfca4`.
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

## Current released minor

[Decisions 0047](../knowledge/decisions/0047-select-a-bounded-adoption-completion-check.md)
and [0050](../knowledge/decisions/0050-separate-adoption-observations-from-readiness-and-owner-disposition.md)
added the `knowledge adoption-check` command and the
`gnostoa-adoption-check/v2` result contract. Decision 0051 and the
[publication result](../knowledge/assessments/v0-2-0-source-and-oci-publication-result.md)
bind that additive capability to the immutable v0.2.0 source and OCI subjects.
Consumers must still use the immutable digest above rather than treating a
version label as the artifact identity.

The released source rejects duplicate keys in standalone YAML and Markdown
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
| Python distribution | The wheel is execution-only. It must be paired with the exact separately pinned public-source root and its digest. `adoption-check` reads its result schema from that source and accepts an installed runtime only after the complete installed `tools` payload is byte-equal to the pinned source payload. |
| OCI distribution | The released `linux/amd64` v0.2.0 image must be pinned as `ghcr.io/ktogias/gnostoa@sha256:f89bf32c0c4b86bac71fa008579b2385e6ae39bf4822f685479c4f2cc22bfca4` and bound to the v0.2.0 source revision and public surface. The `0.2.0` tag alone is not the consumer identity, and no `latest` tag exists. |
| Knowledge bundles | A bundle is compatible only when it validates against the explicitly selected profile, schemas and policy set. |

The generic
[versioning and upgrade guidance](../guidance/reference/versioning-and-upgrades.md)
defines the intended PATCH, MINOR and MAJOR meanings for validation contracts.
It does not turn the pre-stable `v0.2.0` release into a long-term support or
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
validation and context-pack results. The smoke also creates a staged anonymous
adoption fixture and requires the clean installed wheel and source distribution
to produce a retained `gnostoa-adoption-check/v2` result with review readiness
`READY`; that remains mechanical readiness, not semantic adoption. Manifest
generation rejects a revision that differs from `HEAD` or a dirty Git tree. The
result contains filenames rather than local absolute paths. It is build
evidence, not a signature, attestation, published provenance record or
substitute for independent verification.

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
must not be inferred from the presence of the `v0.2.0` source tag or `0.2.0`
image tag. See the
[publication result](../knowledge/assessments/v0-2-0-source-and-oci-publication-result.md).
