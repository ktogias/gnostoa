---
type: Source
title: Deterministic public-surface digest source-authority result
description: Candidate-bound result for binding public-surface digest membership to declared source authority, with the measured host-state immunity, vendored sensitivity, fail-closed and three-way source-form equality evidence.
status: draft
generated:
  by: agent:claude-opus-5
  at: "2026-08-20T14:00:00Z"
sources:
  - id: digest-source-authority-work-item
    resource: https://github.com/ktogias/gnostoa/issues/66
    title: Make the public-surface digest authoritative by source form
x-project-knowledge:
  id: kit.assessment.deterministic-public-surface-digest-source-authority-result
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0029-define-authoritative-source-membership-for-the-public-surface-digest.md
    - kind: references
      target: /decisions/0028-bind-the-published-oci-runtime-source-to-the-git-candidate.md
---

# Deterministic public-surface digest source-authority result

**Candidate-time evidence.** Measured on `linux/amd64` only. Re-observe before any
publication.

## Subject

| | |
|---|---|
| Pre-change source | `0f377300ff3d77e6a304308a2b4d5358d321e2fd` |
| Pre-change clean digest | `sha256:2b4b5b358b6a9436d4c2d5007bbacac1d8fe29bba754495b6c80ccd81ad2863c` |
| Changed | digest membership acquisition only |
| Framing, ordering, exclusion order, return form | unchanged |

## Pre-change algorithm

Walk `PUBLIC_SURFACE_PATHS` on the physical filesystem, keeping every `is_file()`
result; sort by POSIX relative path; drop `IGNORED_PARTS` in any path part and
`IGNORED_SUFFIXES`; then for each survivor feed an 8-byte big-endian path length,
the UTF-8 path bytes, an 8-byte big-endian content length and the content bytes.
Empty selection raises. Membership was never bound to a source candidate.

## RED before implementation

All against the same authoritative candidate, baseline `sha256:2b4b5b35…`:

| | condition | measured |
|---|---|---|
| **D1** | `tools/.mypy_cache` present | `55540195…` — drifts |
| **D1** | `guidance/.ruff_cache` present | `3e4cd231…` — drifts |
| **D2** | arbitrary untracked file under `tools/` | `50faeb90…` — drifts |
| **D3** | `git rm --cached`, file left on disk | `2b4b5b35…` — **membership change missed** |
| **D4** | candidate names a selected path, file absent | `527ebc0f…` — **digests an incomplete source** |
| **D5** | metadata-free vendored source, clean | `2b4b5b35…` — already agreed with Git and X3 |

D5 is a compatibility fact to preserve, not a defect.

## Mechanism

Marker presence selects the mode, and presence alone:

```
lstat(<root>/.git) or lstat(<root>/.gnostoa-source-files)
   ├── either present  → M1: candidate_paths(root) ∩ PUBLIC_SURFACE_PATHS
   └── neither present → M2: physical files under PUBLIC_SURFACE_PATHS
```

Exclusions are applied to the selected paths afterwards, so membership authority
and digest exclusions stay two separate filters. There is no
`try candidate_paths(...) except: filesystem()` anywhere: a declaration that
cannot be read raises rather than degrading the root to M2.

## GREEN — M1, Git-backed

| | condition | result |
|---|---|---|
| **G0** | clean Git, pre-change source | `sha256:2b4b5b35…` — **exact baseline** |
| **G1** | `tools/.mypy_cache` | unchanged |
| **G2** | `guidance/.ruff_cache` | unchanged |
| **G3** | arbitrary untracked under `tools/` | unchanged |
| **G4** | tracked public content edit | changes |
| **G5** | staged public addition | changes |
| **G6** | staged deletion | changes |
| **G7** | `git rm --cached`, file retained on disk | **changes** — membership respected |
| **G8** | candidate path missing from the tree | **fails closed**, naming `tools/cli.py` |

G0 reproducing the pre-change baseline byte-for-byte is what establishes that the
framing is untouched and only membership acquisition changed.

## GREEN — other declared-candidate forms

**Git submodule.** `.knowledge-kit/.git` is a gitdir *file*, not a directory.
Selected as M1; with an untracked file and a `.mypy_cache` deliberately present,
the digest was `sha256:2b4b5b35…` — equal to the clean Git baseline.

**Packaged manifest.** A root with no `.git` and a valid 219-record
`.gnostoa-source-files`, contaminated with an extra `tools/` file and a
`.ruff_cache`, produced `sha256:2b4b5b35…` — equal to the clean Git baseline.

## GREEN — broken authority never degrades

| | condition | result |
|---|---|---|
| **B0** | manifest containing an unsafe `../` entry | fails, no fallback |
| **B0b** | manifest present but empty | fails, no fallback |
| **B1** | manifest is a symlink | fails, no fallback |
| **B2** | `.git` is a dangling gitdir pointer | fails, no fallback |
| **B2b** | `.git` is a garbage directory | fails, no fallback |

B0b fails through the empty-surface error rather than the authority error. Still
fail-closed and still no fallback, but the message differs from the other four;
recorded rather than smoothed over.

## GREEN — M2, metadata-free vendored

Constructed from the documented provider projection route — a source archive of
the exact commit, extracted, archive discarded.

| | condition | result |
|---|---|---|
| **V6** | neither marker present | M2 selected |
| **V0** | clean | `sha256:2b4b5b35…` — equals Git |
| **V1** | `tools/.mypy_cache` | unchanged |
| **V2** | `guidance/.ruff_cache` | unchanged |
| **V3** | arbitrary non-ignored extra under `tools/` | **changes** |
| **V4** | public file content edit | changes |
| **V5** | public file removal | changes |

**V3 is not a D-A failure.** It states that the vendored source has been
modified. Nothing in a metadata-free tree can prove an extra public file was not
part of the source, and hiding it would permit a modified vendored source to
carry an unchanged public digest.

## File-type boundary

The candidate contains **zero** tracked symlinks, and the public surface is 81 ×
`100644` plus 8 × `100755`. For regular files M1 and the pre-change walk select
identically — 89 files either way on a clean tree — so no supported current file
type changes behaviour and no new symlink policy is introduced. A dangling
symlink at a selected M1 path would now fail closed, which is clause O applied
rather than a separate rule.

## Non-claims

Not established: that a modified physical vendored tree is identical to the
original archive; that arbitrary vendored extras are ignored; complete source
identity; P4; OCI reproducibility; complete provenance; image reproducibility;
development hermeticity; complete OCI readiness; or publication authorization.
`v0.1.0` is unchanged, no source identity, version, tag or release is selected,
`deployable_artifact` remains `false`, and OCI publication remains unauthorized.

## Frozen OCI checkpoint

Decisions 0022–0028 remain the governing authorities and are unchanged. The
util-linux and pip blockers remain cleared for the measured `linux/amd64`
effective runtime; the pip layer-history residual remains governed by Decision
0026; the development host-context residual and the X3 named-`candidate`
raw-route substitution residual are unchanged. Deferred and untouched: CPython
vulnerability binding, licence and legal clearance, the Decision 0022/H UNKNOWN
observations, registry identity and permissions, publication, and the public OCI
security claim. Source-identity preparation remains paused.
