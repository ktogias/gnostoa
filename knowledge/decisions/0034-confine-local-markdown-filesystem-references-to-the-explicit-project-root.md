---
type: Decision
title: Confine local Markdown filesystem references to the explicit project root
description: Bound project-controlled local Markdown link validation by the existing explicit project root without changing relation-target semantics.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-21T19:18:08Z"
sources:
  - id: markdown-reference-authority-work-item
    resource: https://github.com/ktogias/gnostoa/issues/76
    title: Confine local Markdown references to the project root
x-project-knowledge:
  id: kit.decision.0034.confine-local-markdown-filesystem-references-to-the-explicit-project-root
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /decisions/0033-confine-profile-inheritance-to-the-explicit-project-root.md
    - kind: references
      target: /assessments/markdown-reference-authority-and-outside-root-observation-result.md
---

# Confine local Markdown filesystem references to the explicit project root

Recorded by `codex/gpt-5` from the accountable maintainer's exact disposition.
The semantic choice is the maintainer's; this record is faithful transcription,
not another approval step.

Scope: **first-party local Markdown filesystem-observation authority.**

## Context

The bounded G3 study that followed the profile-inheritance remediation measured
237 local Markdown references across the four supported self-check bundles. Of
those, 203 remain within their immediate bundle and 34 legitimately cross
project bundles or surfaces while staying inside the repository root. A
bundle-only boundary would break all 34; a project-root boundary breaks none.

The same study demonstrated three outside-root observation classes. A present
outside file suppressed a broken-link issue while an absent one produced it
(E1); outside directory and `index.md` state changed validation (E2); and an
in-project symlink made validation depend on its outside canonical target (E3).
No Markdown target-content read was demonstrated (E4 absent). The first outside
observation occurred during path canonicalisation, before the later directory
and existence checks.

## Decision

**A.** The bounded G3 study demonstrated E1, E2 and E3 outside-root filesystem
observation through project-controlled local Markdown references.

**B.** No Markdown target-content read was demonstrated.

**C.** Local Markdown filesystem authority is the existing explicit
`project_root` supplied to `validate_bundle`. No second Markdown authority
option is introduced.

**D.** Local Markdown links may cross bundles and project surfaces while their
authoritative targets remain inside `project_root`.

**E.** `/...` retains its existing bundle-rooted meaning. It does not name the
host filesystem root.

**F.** `..` remains permitted when the target authority stays inside
`project_root`. The invariant is containment, not absence of traversal.

**G.** An outside-root local reference is rejected or reported without
observing the outside target's existence, type, directory state, canonical
target metadata, `index.md` state or contents.

**H.** Same-document fragments and external URIs cause no local filesystem
observation. External link liveness is not checked.

**I.** Existing query and fragment stripping semantics are preserved for local
targets.

**J.** S1 is selected: canonical in-root symlinks remain supported.

**K.** A symlink whose destination would leave `project_root` is rejected after
reading only the in-root symlink's own metadata and link text, and before any
outside target metadata is observed.

**L.** In-root directory-to-`index.md` resolution remains supported, but
directory detection occurs only after the target is safely established inside
`project_root`.

**M.** The appended `index.md` target passes through the same bounded
canonicalisation because `index.md` may itself be a symlink.

**N.** Markdown link validation does not read target contents.

**O.** The existing `broken_links` rule remains the validation severity
mechanism for outside-authority local links.

**P.** No new security-policy or severity field is created.

**Q.** Shared `resolve_target` relation semantics are unchanged by this
Decision.

**R.** Concept-ID and path relation resolution, plus context-pack graph
traversal, are outside this slice.

**S.** This remediation does not establish that Gnostoa is secure or that
unknown first-party vulnerabilities are absent.

**T.** The S1-S8 G3 model remains provisional until the integrated
post-remediation replay is read back and separately dispositioned by the owner.

**U.** Source identity remains paused.

**V.** OCI publication remains unauthorized.

**W.** `deployable_artifact` remains `false`.

## Public compatibility and migration

This is a **critical public behavioural tightening and security correction**.
Previously accepted local Markdown links that intentionally traversed outside
the selected project root will fail after remediation.

Move or pin a local target inside `project_root` and use an in-project relative
link. For genuinely external material, use an explicit external URI or a
commit-aware reference. Cross-surface links inside one project, bundle-rooted
links, canonical in-root symlinks and in-root directory-to-`index.md` behavior
remain supported.

## Consequences

- Markdown validation needs one narrow resolver that performs lexical
  containment before any project-controlled target-specific filesystem access,
  then follows symlinks component by component only while authority remains
  inside the root.
- Present, absent, file, directory, indexed-directory and outside-symlink
  variants of one outside reference receive the same bounded authority failure.
- Shared relation-target resolution is deliberately untouched, avoiding a
  semantic change to concept relations or context-pack graph traversal.
- No generic filesystem sandbox, path-policy engine or new CI security job is
  selected.
- A successful focused replay may make the integrated candidate eligible for a
  separate final bounded G3 owner disposition. It does not create that
  disposition in this slice.
