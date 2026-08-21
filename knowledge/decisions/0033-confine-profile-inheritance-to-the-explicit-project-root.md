---
type: Decision
title: Confine profile inheritance to the explicit project root
description: Bound project-controlled profile inheritance by one explicit project root, requiring relative references whose canonical targets stay inside that root and refusing escapes before the parent file is read.
status: draft
generated:
  by: agent:claude-opus-5
  at: "2026-08-20T23:30:00Z"
sources:
  - id: profile-read-boundary-work-item
    resource: https://github.com/ktogias/gnostoa/issues/74
    title: Confine profile inheritance to the project root
x-project-knowledge:
  id: kit.decision.0033.confine-profile-inheritance-to-the-explicit-project-root
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /decisions/0022-define-the-security-boundary-for-the-first-gnostoa-oci-publication.md
    - kind: references
      target: /assessments/first-party-source-security-falsification-and-profile-read-result.md
---

# Confine profile inheritance to the explicit project root

Recorded by `agent:claude-opus-5` from the accountable maintainer's exact
disposition. The semantic choice is the maintainer's; this record is faithful
transcription, not a further approval step.

Scope: **first-party profile-inheritance read authority.**

## Context

Decision 0022/K states the OCI security boundary establishes nothing about
Gnostoa-source vulnerability binding. A bounded G3 falsification study closed
that gap for one property and demonstrated a concrete defect. The candidate-time
evidence lives in the
[falsification and profile-read result](../assessments/first-party-source-security-falsification-and-profile-read-result.md).

## Decision

**A.** The G3 study demonstrated a supported-runtime first-party read of files
outside the project authority, driven by project-controlled profile inheritance.

**B.** Profile `extends` is **project-controlled input**, not operator input.

**C.** Supported profile inheritance is bound by **one explicit `project_root`**,
held constant for the whole chain.

**D.** `extends` values must be **relative** filesystem references.

**E.** `..` is permitted when the final canonical target stays within
`project_root`. The invariant is containment, not the absence of traversal.

**F.** Absolute parent references are rejected.

**G.** Relative traversal whose resolved target leaves `project_root` is
rejected.

**H.** Symlink resolution whose final target leaves `project_root` is rejected.

**I.** In-root symlinks are **not** categorically prohibited.

**J.** Containment is checked **before** the parent file is opened or parsed, so
a rejected reference cannot leak the bytes it names.

**K.** There is **no unrestricted fallback**. A root that cannot be established,
or a reference that escapes it, fails.

**L.** The documented `.knowledge/profile.yaml` → `../.knowledge-kit/core/profile.yaml`
inheritance remains valid.

**M.** Module → project inheritance inside the same root remains valid.

**N.** Monotonic deep merge and inheritance-cycle detection are unchanged.

**O.** Supported CLI callers bind the same root consistently — a bundle is never
validated under one authority and rendered under another.

**P.** `check-runtime` reuses its existing explicit `--project-root`.

**Q.** `validate` and `context-pack` gain an explicit `--project-root` defaulting
to the working directory, because the documented container and native routes
execute from the project root.

**R.** Programmatic profile-loading callers must supply `project_root`
explicitly. Omission is a call-contract error; the loader does not infer the
project authority from the profile directory or from an inheritance reference.

**S.** The Markdown outside-root existence oracle is **not** resolved here.

**T.** The S1–S8 G3 sufficiency model remains **experimental** until a
post-remediation replay.

**U.** Source identity remains paused. **V.** OCI publication remains
unauthorized. **W.** `deployable_artifact` remains `false`.

## Relation to Decision 0002

Decision 0002 remains authoritative for monotonic profile inheritance and is not
rewritten. This Decision adds the filesystem-authority boundary that inheritance
always needed and never had.

## This is a public behavioural tightening

Profiles that previously loaded will now fail:

- absolute parent paths;
- parents intentionally outside the project root;
- symlinked parents whose canonical target leaves the root.

**Migration:** materialise or pin the parent inside the project root and
reference it relatively. `..` keeps working while the target stays in-root. This
is pre-stable, but it is a real public change and is not described as backward
compatible.

## Consequences

- Programmatic callers bind the root explicitly. The `validate` and
  `context-pack` command-line interfaces acquire it from `--project-root`, whose
  documented default is the current working project directory; `check-runtime`
  reuses its pre-existing option. Repository tests bind their root explicitly.
- `self_check` was found binding no root at all while validating repository
  bundles. It now passes the repository root it had already resolved.
- Diagnostics name the offending reference and the root, never the content of
  the refused file. That distinction is the security property, not a style
  choice: the pre-change error for an outside non-YAML parent contained a
  fragment of that file.
- The Markdown reference boundary is a separate, still-undecided authority. This
  Decision deliberately leaves it, and the existence oracle it produces, in
  place.
