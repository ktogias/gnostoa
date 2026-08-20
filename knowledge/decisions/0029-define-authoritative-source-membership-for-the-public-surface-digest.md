---
type: Decision
title: Define authoritative source membership for the public-surface digest
description: Select declared-candidate membership for Git-backed and manifest-backed toolkit roots, define the metadata-free vendored source as its own physical public surface at digest time, and require broken source authority to fail rather than fall back.
status: draft
generated:
  by: agent:claude-opus-5
  at: "2026-08-20T14:00:00Z"
sources:
  - id: digest-source-authority-work-item
    resource: https://github.com/ktogias/gnostoa/issues/66
    title: Make the public-surface digest authoritative by source form
x-project-knowledge:
  id: kit.decision.0029.define-authoritative-source-membership-for-the-public-surface-digest
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /decisions/0028-bind-the-published-oci-runtime-source-to-the-git-candidate.md
    - kind: references
      target: /assessments/deterministic-public-surface-digest-source-authority-result.md
---

# Define authoritative source membership for the public-surface digest

Recorded by `agent:claude-opus-5` from the accountable maintainer's exact
disposition. The semantic choice is the maintainer's; this record is faithful
transcription, not a further approval step.

Scope: **public-contract digest membership authority only.**

## Context

`public_surface_digest` walked physical filesystem state under
`PUBLIC_SURFACE_PATHS` and never bound membership to an authoritative source
candidate. Measured on one unchanged Git candidate: a `tools/.mypy_cache`
produced `55540195…`, a `guidance/.ruff_cache` produced `3e4cd231…`, and an
arbitrary untracked file under `tools/` produced `50faeb90…`, against a clean
`2b4b5b35…`. Worse in the other direction, `git rm --cached` on a public file
whose bytes stayed on disk left the digest at `2b4b5b35…` — a real membership
change the contract identity did not notice. And a candidate that still named a
selected path whose file was gone returned a digest for the incomplete source
rather than refusing.

A preceding read-only precursor established that a candidate-derived membership
is exact for Git checkouts, Git submodules and the X3 packaged runtime, and that
it cannot acquire authority at all for a metadata-free vendored release — which
is a currently supported and currently working adoption route.

The candidate-time measurements live in the
[digest source-authority result](../assessments/deterministic-public-surface-digest-source-authority-result.md).

## Decision

**A.** `public_surface_digest` is **public inheritance / contract identity**. It
is not complete Git source identity, not OCI build-definition identity, not OCI
artifact identity and not provenance identity.

**B. P4 remains not selected.** Decision 0028/D stands.

**C. Mode M1 — declared-candidate source.** Applies when the toolkit root has
`.git` **or** `.gnostoa-source-files`.

**D.** M1 membership comes from `candidate_paths(root)`, intersected with
`PUBLIC_SURFACE_PATHS`.

**E.** Host-local files outside that candidate do not enter the M1 digest.

**F. A declared authority that cannot be read fails closed and never falls
back.** Marker *presence* selects the mode; whether reading it succeeds does not.
A malformed, unsafe, non-regular or unusable declaration must never be weaker
than no declaration at all.

**G. Mode M2 — metadata-free vendored source.** Applies only when **neither**
marker exists.

**H.** For M2 the physical files under `PUBLIC_SURFACE_PATHS`, after the explicit
generated-state exclusions, **are** the authoritative public source presented for
validation.

**I.** An extra non-ignored file under an M2 public-surface path is therefore a
**source modification** and changes the digest.

**J.** Removing or changing a physical M2 public file changes the digest.

**K.** Explicit generated classes stay outside digest authority in both modes.

**L.** `.mypy_cache` and `.ruff_cache` are added to `IGNORED_PARTS` **only**
because each was measured drifting the digest. No speculative class is added and
no generic ignore taxonomy is built.

**M.** Ignore semantics are otherwise unchanged. `IGNORED_SUFFIXES` stays
`{".pyc", ".pyo"}`. Candidate membership and digest exclusions remain two
separate filters applied in that order.

**N.** Content authority is unchanged: current readable source bytes, not Git
blobs. An uncommitted edit to a selected tracked public file still changes the
digest, consistent with Decision 0028/I.

**O.** A selected M1 candidate public path that is missing or unreadable **fails
closed**, naming the path. Digesting the remainder under the same candidate
identity would assert a source that is not present.

**P.** `git rm --cached` membership is respected even when the file remains on
disk.

**Q.** Vendored release support is retained. **R.** No vendored manifest is
selected. **S.** No release-model change: Decisions 0020 and 0021, the
source-release runbook, `v0.1.0` and provider source archives are untouched.

**T.** A reproducible native installation is **execution only**; the pinned
source root it points at inherits M1 or M2 by its own markers.

**U.** Clean source forms of one toolkit candidate must produce the same digest.

**V.** Source-archive membership is authoritative while the archive exists, but
**is not claimed observable after metadata-free extraction**. This is why M2
exists rather than a reconstructed member list.

**W.** `UNENFORCED_REVISIONS` is unchanged. Digest computation and enforcement
activation remain separate properties.

**X.** The X3 named-`candidate` raw-Docker substitution residual is unchanged and
no new guard is added.

**Y.** No CPython work. **Z.** No source identity, version, tag, release or
publication.

## The asymmetry is deliberate

Candidate-backed source excludes noncandidate extras **because authority proves
they are outside the source**. Metadata-free vendored source includes non-ignored
physical extras **because no authority proves they are outside it**. Hiding them
would allow a modified vendored source to carry an unchanged public digest, and
that vendored tree is usable as the matching pinned source root, including under
the native fallback.

This resolves the precursor's V4 ambiguity deliberately as **V1 for digest-time
authority**. The previous contract did not already say this; this Decision makes
the choice.

## Consequences

- The digest now answers a different question in M1: not "what is under these
  directories" but "what does this source declare is under these directories".
  For a clean checkout the two answers coincided — 89 files either way — which is
  why the clean digest is unchanged.
- Two previously invisible conditions now surface. `git rm --cached` with the
  file retained changes the digest, and a candidate path missing from the working
  tree fails instead of returning a digest. Both are behaviour changes, and both
  are the point.
- A vendored adopter who drops a scratch file under a public-surface path will
  see their digest move. That is a true statement about their source, not a
  defect, and the guidance now says so.
- Broken authority is now louder than absent authority. A corrupted `.git` or an
  unreadable manifest fails rather than silently producing a filesystem digest
  that looks legitimate.
- The two added ignore classes exclude **zero** currently tracked files, so they
  change no clean digest for any source form.
- `knowledge surface-digest --root .knowledge-kit` remains valid for every
  supported source form. No documented route requires new metadata.
