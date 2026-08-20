---
type: Source
title: OCI Git-candidate source-binding result
description: Candidate-bound result for binding the published runtime's Gnostoa source payload and packaged candidate manifest to the authoritative Git candidate, with the measured contamination-immunity, parity and fail-closed evidence.
status: draft
generated:
  by: agent:claude-opus-5
  at: "2026-08-20T09:30:00Z"
sources:
  - id: source-binding-work-item
    resource: https://github.com/ktogias/gnostoa/issues/64
    title: Bind the published OCI runtime to the Git source candidate
x-project-knowledge:
  id: kit.assessment.oci-git-candidate-source-binding-result
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0028-bind-the-published-oci-runtime-source-to-the-git-candidate.md
    - kind: references
      target: /decisions/0027-remove-pip-and-ensurepip-from-the-published-gnostoa-oci-runtime.md
---

# OCI Git-candidate source-binding result

**Candidate-time evidence.** Measured on `linux/amd64` only. Re-observe before any
publication.

## Subject

| | |
|---|---|
| Pre-change source | `11dea1f3a0421232f2db1f385d4347f4e3bbbcdb` |
| Pre-change public-surface digest | `sha256:06bd57bd36aedaa6f5ccade414eefdc960d00e2d2982e4325bd4b2f7a7676ff6` |
| Post-change public-surface digest | `sha256:2b4b5b358b6a9436d4c2d5007bbacac1d8fe29bba754495b6c80ccd81ad2863c` |
| Route bound | the published `runtime` target only |
| Interpreter, base image | unchanged |

## What the owner required

The packaged candidate manifest must represent the same authoritative candidate
path set the checkout uses — `git ls-files --cached --deduplicate` — so `S4 == S1`;
and repository-derived executable or importable runtime source must come only from
that candidate. General rootfs purity was **not** required, and the public-surface
digest was **not** redefined.

## Mechanism

One self-owned helper acquires the candidate once and drives both outputs:

```
git ls-files --cached --deduplicate -z | LC_ALL=C sort -z
   ├── candidate/meta/.gnostoa-source-files   (the manifest the image ships)
   └── candidate/source/                      (the source the image is built from)
```

The helper rejects unsupported index entry modes, fails closed on a candidate path
missing from the working tree, materialises the payload with current working-tree
contents, verifies the materialised modes against the index, computes the manifest
digest, and invokes the build with a bounded named context plus that digest. Inside
the build the digest is verified, the payload path set is recomputed under the same
ordering and compared byte for byte against the manifest, and only then does any
Python installation run.

## RED before implementation

**Packaged candidate.** Identical Git source produced different manifests depending
on local state; untracked and ignored paths entered the manifest and became live
inputs to the project's own candidate text scans; and even a clean checkout gave
`S4 (213) ⊊ S1 (214)`, omitting the tracked `.gitignore`.

**Runtime import surface.** A module placed in `tools/` was correctly excluded from
the manifest and remained **importable**, because the editable install maps a
directory rather than a file list.

**Build-time source.** An untracked root `pip.py` shadowed `python -m pip` and took
over the runtime dependency-install step, terminating the build at the controlled
sentinel's exit code. First affected instruction: the dependency-install `RUN`
immediately following the ordinary context copy.

Recorded as source/provenance correctness failures. **Not** exploitability claims:
each required a file in the builder's own checkout, and the supported command
output never changed.

## GREEN after implementation

Measured on a clean checkout and on a checkout carrying every contaminant class at
once — ignored bytecode, an ignored tool cache, an arbitrary untracked file, a root
`sitecustomize.py`, a module inside the installed package, and the `pip.py` shadow —
with **no tracked source difference between them**:

| | clean | contaminated |
|---|---|---|
| `S4 == S1` | **yes** | **yes** |
| payload == manifest (checked in-build) | **yes** | **yes** |
| tracked `.gitignore` in manifest | **yes** | **yes** |
| tracked `.dockerignore` in manifest | **yes** | **yes** |
| local module in payload | absent | **absent** |
| local module importable | no | **no** |
| local module in package listing | no | **no** |
| untracked file in payload | absent | **absent** |
| `pip.py` shadow in payload | absent | **absent** |
| build-time shadow executions | 0 | **0** |
| build-time `sitecustomize` executions | 0 | **0** |

Both checkouts produced the **same manifest digest**, which is the intended
property: host contamination must not change the artifact.

### Source payload equality, exactly stated

`S1 == repository-derived payload == S4`. Three build-generated classes are outside
that equality, and they are named rather than hidden behind a broad exclusion:
`.gnostoa-source-files` (the manifest itself), `.evidence/*` (the install report)
and `gnostoa.egg-info/*` (editable-install metadata). All three are generated by
the build, none is a candidate path, and each is Git-ignored.

## Fail-closed behaviour

A wrong manifest digest is **rejected**. A payload that does not match the manifest
is **rejected** before any Python installation. A missing candidate context or
missing digest fails the build. A candidate path absent from the working tree fails
the helper and names the path. An unsupported Git index entry mode fails the helper.

## Named-context substitution

`COPY --from=candidate` is an image reference when no named context supplies it.
Measured, with a decoy image literally named `candidate:latest` in the local
image store carrying its own self-consistent source and manifest:

| route | outcome |
|---|---|
| provider verification before the call sites moved | failed pulling `docker.io/library/candidate:latest` |
| raw `docker build --target runtime .`, decoy present | **rejected** at the in-build check |
| `ci/build-runtime`, decoy present | **builds correctly** — decoy absent, `S4 == S1 == 219`, self-check `OK` |

The explicitly supplied named context takes precedence over a same-named image,
so the documented route is unaffected. The unsupported raw route fails, and it
fails at the in-build equality and digest checks rather than at the substitution
itself. This is why that check is inside the build.

## Working-tree and path-set semantics

An uncommitted edit to a tracked file **reaches the artifact**: source content is
the current working tree, not committed blobs, so work in progress remains
buildable. A staged path-set change propagates identically to `S1`, the payload,
the manifest and its digest.

## Materialisation fidelity

Regular-file bytes, executable and non-executable modes, and symlinks-as-symlinks
are all preserved, with the Git index — not the local filesystem — as the authority
for the expected mode. Paths containing spaces and literal newlines are handled.
The current candidate contains no submodules or gitlinks; those fail closed rather
than receiving invented packaging semantics.

## Four requirements that proved load-bearing

Recorded because three of them produced real failures during this work and the
fourth produced a silent one:

1. **Locale-independent ordering.** A builder locale that sorts dot-files
   differently from the container produced a spurious payload/manifest mismatch.
   Both sides must order under `LC_ALL=C`.
2. **Symlink-safe presence.** A guard that follows symlinks reports a relative
   symlink as a missing candidate path.
3. **No `.dockerignore` at the wrapper root.** A wrapper-root ignore file silently
   reduced a payload from 214 to 197 paths while the manifest still claimed 214.
   This is why the in-build equality check is required rather than optional.
4. **NUL-safe comparison.** A line-based comparison reports a false mismatch on a
   path containing a newline.

## Revision identity

The image labels a commit only when the build verified that its source is that
commit's source. Measured behaviour of the six cases:

| case | asserted ref | outcome | `image.revision` |
|---|---|---|---|
| local build, clean tree | none | builds | `development` |
| local build, edited tracked file | none | builds | `development` |
| exact revision, clean tree | current `HEAD` | builds | the exact SHA |
| exact revision, edited tracked file | current `HEAD` | **exit 7** | — |
| unresolvable revision | `deadbeef…` | **exit 7** | — |
| resolvable revision that is not `HEAD` | an ancestor | **exit 7** | — |

An unasserted build is labelled `development` rather than resolved to `HEAD`,
because the source is the working tree and tracked files may carry uncommitted
edits. A failed assertion is a build failure; it never degrades to `development`
under the same command.

## Runtime parity

Against the pre-change baseline, with only the intended source-authority
differences: interpreter version, base image digest, OS package inventory, runtime
Python distribution set, runtime user and uid/gid, entrypoint, command, working
directory, capability bounding set and privileged-file set are all **unchanged**;
the pip and `ensurepip` removal from the previous slice remains in force with no
component entry points; and the documented runtime commands pass. Image identity
equality is not required and is not claimed.

Intended differences: the manifest is now exactly the candidate rather than a
filesystem enumeration, tracked `.gitignore` is now present in it, the build
definition changed, and the helper, Decision, tests and documentation are new
source.

## Development route — explicit residual

The development target deliberately keeps the ordinary local build context, needs
no candidate context, and requires no devcontainer change. It builds, retains its
development-lock pip, `ensurepip` and tooling, and passes the canonical
development-container verification.

> **The development image is not covered by the filtered-source guarantee.** The
> same measured `pip.py` shadow still affects a development build. This is a
> deliberate residual: the property was selected for the first-party published
> runtime artifact, and extending it would need separate admission.

## Source archives

The route requires a Git checkout, because the candidate is read from Git. A plain
source archive without Git metadata remains outside this build route, and no claim
is made that a release tarball can reproduce it locally.

## Public-surface digest

The digest changes, because the build definition and the helper are inside the
pinned surface. Both the pre-change and post-change values were computed from
**fresh clean materialisations** with no ignored local cache beneath the surface
paths, and the in-image value was required to match the clean candidate value.

The clean-candidate value and the in-image value were measured and are equal:
`sha256:2b4b5b35…`. The value is unaffected by this record, because `knowledge/`
is not a surface path. The pre-change value is not pinned in any enforced file,
so nothing required updating.

**This establishes nothing about digest determinism.** The separately measured
defect — the digest can vary because ignored local caches exist under surface paths
— is untouched and remains the next expected disposition.

## How this was reached

Recorded because several steps here were corrections to this work, and a result
that hides them is a worse guide to the next slice than one that does not.

1. A read-only study established the S1→S4 chain and measured that the packaged
   manifest was a filesystem enumeration, not the candidate.
2. A read-only route precursor compared six implementation shapes and selected a
   pre-generated Git manifest over a secret-transported one, because build-secret
   contents do not participate in cache invalidation.
3. A read-only falsification tested whether manifest exclusion bounded the
   runtime import surface. It did not: the editable install maps a directory.
   One probe — a root `sitecustomize.py` — did **not** execute, and that negative
   result was recorded as a negative result.
4. Implementation proceeded under the filtered-source route. Four requirements
   surfaced as real failures: locale collation, symlink-following presence, tar
   argument order, and a NUL byte written literally into a generated Dockerfile.
5. An early reading of the wrapper-root `.dockerignore` hazard concluded there
   was no hazard. That reading was wrong — it used patterns that happen not to
   match under `source/`. A sharper test reduced a payload from 214 to 197 paths.
   The in-build equality check exists because of this, and is not optional.
6. A first assertion script sent stderr into captured stdout and prepended a
   traceback to a result string. Both the RED and GREEN measurements were retaken
   with the corrected instrument rather than reasoned about.
7. The conformance harness initially measured the pre-change source, because a
   local clone carries committed state; and it asserted a property of the
   development image that the Decision explicitly does not claim. Both were
   corrected — the second by recording the residual instead of asserting it away.
8. Provider verification then failed: four jobs still built the published runtime
   with raw `docker build`, which now fails closed. That was a genuine missing
   dependency of the change. Work stopped rather than editing an unadmitted path.
9. The owner re-admitted the slice with that one path, and on read-back found two
   defects this work had missed: NUL-safety was incomplete in three constructs
   that still reasoned in lines, and the revision label defaulted to `HEAD` —
   claiming a commit identity for a working-tree build.
10. Both were corrected. The line-oriented constructs were removed rather than
    patched, three of them by asking Git or `tar` for the guarantee directly. A
    tracked pathname containing a literal newline became a test fixture.
11. The property was then re-measured end to end, and the provider route was
    moved onto the helper.

## Maximum claim

> For the measured Gnostoa first-party OCI runtime build route, the
> repository-derived source payload and the packaged semantic candidate are both
> derived from the authoritative Git candidate path set using current tracked
> working-tree contents; measured ignored or untracked host-local source cannot
> enter that runtime source and import surface or the packaged candidate authority.

## Non-claims

Not established: complete hermetic build; rootfs purity; **development-image
hermeticity**; generic workspace isolation; OCI reproducibility; provenance;
source-archive build support; **deterministic public-surface digest**; complete OCI
readiness; complete image security; or publication authorization. `v0.1.0` is
unchanged, no source identity, version, tag or release is selected,
`deployable_artifact` remains `false`, no registry is selected, and OCI publication
remains unauthorized.

## Frozen OCI checkpoint

Decisions 0022–0027 remain the governing authorities and are unchanged. The
util-linux and pip blockers remain cleared for the measured `linux/amd64` effective
runtime, and the pip layer-history residual remains governed by Decision 0026.
Deferred and untouched: the deterministic public-contract-digest correction, CPython
vulnerability binding, licence and legal clearance, the Decision 0022/H UNKNOWN
observations, registry identity and permissions, publication, and the public OCI
security claim. Source-identity preparation remains paused.
