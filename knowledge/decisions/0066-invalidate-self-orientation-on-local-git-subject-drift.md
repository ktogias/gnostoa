---
type: Decision
title: Invalidate self-orientation on local Git subject drift
description: Add one self-only live Git subject observation so a retained D14 orientation snapshot cannot remain current after repository integration changes its bound subject.
status: draft
generated:
  by: agent:gpt-5.6-sol
  at: "2026-09-11T15:16:00Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/14
    title: Add reproducible goal-alignment and delivery-state projections
  - id: owner-admission
    resource: https://github.com/ktogias/gnostoa/issues/14#issuecomment-5637217420
    title: D14-O2 O2-A0 owner admission
  - id: d14-o1-decision
    resource: ./0065-run-a-bounded-gnostoa-self-orientation-snapshot.md
    title: Decision 0065
  - id: prior-art-policy
    resource: ./0062-require-proportionate-prior-art-and-reuse-review.md
    title: Decision 0062
  - id: post-merge-characterization
    resource: https://github.com/ktogias/gnostoa/issues/14#issuecomment-5635362923
    title: D14-O1 post-merge drift observation
  - id: claude-review
    resource: https://github.com/ktogias/gnostoa/issues/14#issuecomment-5637095406
    title: Supplied Claude review and root disposition
  - id: git-cli-license
    resource: https://github.com/git/git/blob/47ce80527c56f462cb97db4ca8125342204d3783/COPYING
    title: Git COPYING at inspected commit 47ce80527c56f462cb97db4ca8125342204d3783
  - id: gitpython-readme
    resource: https://github.com/gitpython-developers/GitPython/blob/dcb6b14a9f6af9ece60d014b84c154f83f6906c8/README.md
    title: GitPython README at inspected commit dcb6b14a9f6af9ece60d014b84c154f83f6906c8
  - id: gitpython-license
    resource: https://github.com/gitpython-developers/GitPython/blob/dcb6b14a9f6af9ece60d014b84c154f83f6906c8/LICENSE
    title: GitPython license at inspected commit dcb6b14a9f6af9ece60d014b84c154f83f6906c8
  - id: dulwich-project
    resource: https://github.com/jelmer/dulwich/blob/e27b0cc310ab4ebf1deee0f09ca027ad153ccc07/pyproject.toml
    title: Dulwich project metadata at inspected commit e27b0cc310ab4ebf1deee0f09ca027ad153ccc07
  - id: dulwich-license
    resource: https://github.com/jelmer/dulwich/blob/e27b0cc310ab4ebf1deee0f09ca027ad153ccc07/COPYING
    title: Dulwich license at inspected commit e27b0cc310ab4ebf1deee0f09ca027ad153ccc07
x-project-knowledge:
  id: kit.decision.0066.invalidate-self-orientation-on-local-git-subject-drift
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0005-container-first-runtime.md
    - kind: governed-by
      target: /decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md
    - kind: governed-by
      target: /decisions/0062-require-proportionate-prior-art-and-reuse-review.md
    - kind: references
      target: /decisions/0024-separate-stable-navigation-from-volatile-state.md
    - kind: references
      target: /decisions/0065-run-a-bounded-gnostoa-self-orientation-snapshot.md
    - kind: references
      target: /contracts/public-inheritance-surface.md
---

# Invalidate self-orientation on local Git subject drift

## Context

Decision 0065 deliberately produced one manually bound Gnostoa-self orientation
snapshot before introducing a generic projection capability. PR #238 integrated
that slice. Immediately after integration the retained snapshot still reported
`CURRENT`, remained bound to pre-merge commit
`1acf9bb448e7342bbf1b8a4cf16f3b2a86225f89`, and still recommended verifying
the already-merged candidate. This is retained characterization evidence rather
than a reason to rewrite the historical snapshot manually.

Issue #14 ultimately calls for reproducible source-bound projections, but the
owner admitted only O2-A0: the smallest live Git-subject guard needed to prevent
this concrete false-current state. The existing implementation remains under
`tasks/`; the broader packaged collector/evaluator architecture is not admitted.

The current public-surface digest contract includes the whole `tools/` tree.
Moving an internal self-only subsystem there would therefore create a public
surface effect. O2-A0 must not make that architectural choice implicitly.

## Decision

1. Keep O2-A0 in the existing self-only `tasks/gnostoa_orientation.py` and its
   focused test file. Do not create a new orientation package, public command,
   schema, provider adapter or reusable adopter surface.
2. Preserve `build_manifest` as deterministic evaluation over already supplied
   inputs. The live CLI boundary additionally observes the repository's exact
   Git `HEAD` commit once, validates that identity, and derives the tree from
   that immutable observed commit using the Git client supplied by the
   container-first runtime.
3. Bind the observed commit and tree into the emitted machine manifest's
   evaluation evidence. If either differs from the snapshot's declared subject,
   add a stable diagnostic and classify the result as at least `STALE`; it must
   never be `CURRENT`.
4. If the CLI cannot establish the repository root, commit or tree, fail closed.
   Lack of a required live Git subject may not be converted into `CURRENT` or a
   guessed next action.
5. Git observation is read-only, shell-free, bounded by a short timeout and
   rooted at the explicit `--repository-root`. Strip inherited `GIT_*`
   repository-selection/control variables, then set only the bounded Git and
   locale controls required by this observer. The observed repository top level
   must equal that explicit root after resolution; a containing repository is
   not silently accepted.
6. Add direct regression coverage for local path confinement, including `..`
   traversal and a symlink that resolves outside the explicit repository root.
7. Keep the already-stale committed D14-O1 snapshot as a real regression fixture.
   The first O2-A0 behavioral discriminator is that invoking the live projector
   against the current checkout cannot report that old subject as `CURRENT`.
8. Keep `PUBLIC_SURFACE_PATHS` unchanged. O2-A0 neither moves code into `tools/`
   nor changes the public-surface contract. Any future installed-but-self-only
   module location requires an explicit later architectural/public-surface
   decision.
9. Verify through the container-first path. The pinned OCI tooling environment
   is primary release/CI evidence; the Development Container is the maintainer
   environment; native execution is bounded fallback/equivalence evidence and
   cannot be the sole acceptance basis.

## Alternatives considered

### Proportionate prior-art and license fit for Git observation

Decision 0062 requires reusable alternatives, intended-use licensing and the
remaining need for custom work to be explicit before a Gnostoa-self mechanism is
accepted. That checkpoint was missing when O2-A0 was first implemented and was
identified by Qodo's independent review of exact head
`1337c82e28256f265b4c28b1fe41980e2cf7e832`. The following bounded assessment
repairs the record without rewriting that chronology as if it had happened
before implementation.

- **Git CLI — selected existing component.** Upstream Git was inspected at
  `47ce80527c56f462cb97db4ca8125342204d3783`. Its `COPYING` identifies the
  project as **GPL-2.0-only**. O2-A0 does not copy, import or link Git source into
  Gnostoa; it invokes the already-pinned Git executable as a separate runtime
  process. Git's own license text distinguishes running the program and mere
  aggregation from covered derivative work. On this intended boundary the
  separately licensed executable can coexist with Gnostoa's Apache-2.0 source;
  runtime-image third-party notice and redistribution obligations remain
  separately governed by `LICENSING.md`. This is a bounded intended-use
  assessment, not blanket legal clearance.
- **GitPython — compatible license, rejected dependency surface.** GitPython was
  inspected at `dcb6b14a9f6af9ece60d014b84c154f83f6906c8`; its license is
  **BSD-3-Clause**. Its README describes a Python Git-repository abstraction
  often backed by the `git` command-line program and says most operations still
  require the Git executable. The permissive license fits Gnostoa's Apache-2.0
  distribution, but adopting it would add GitPython plus its package dependency
  surface without removing the existing Git runtime dependency for this three-
  query read-only observer.
- **Dulwich — compatible selectable license, rejected breadth.** Dulwich was
  inspected at `e27b0cc310ab4ebf1deee0f09ca027ad153ccc07`; its project metadata
  describes it as a Python Git library and declares
  **Apache-2.0 OR GPL-2.0-or-later**. The Apache-2.0 option is compatible with
  Gnostoa's distribution, but using Dulwich would add a new Python Git-library
  dependency and a materially broader Git-semantics surface than O2-A0 needs.

**No new Python dependency** is selected. The residual custom work is the small
self-only adapter around the existing Git CLI: exact-root argv construction,
invocation-local `safe.directory`, bounded timeout/output, Git-environment
sanitization, coherent commit-to-tree binding, validation and fail-closed
error mapping. Neither GitPython nor Dulwich removes that Gnostoa-specific
policy/evidence boundary; both enlarge the dependency surface for no observed
O2-A0 benefit.

### Manually refresh or mark the committed D14-O1 snapshot stale

Rejected as the primary repair. It would repair one file while preserving the
failure mode that allowed an integrated change to leave an obsolete subject
labelled current. It would also erase the best real characterization fixture.

### Implement the full proposed O2-A collector/profile/replay subsystem now

Deferred. That design remains plausible, but O2-A0 can falsify the immediate
false-current behavior without first introducing a new package, source profile,
collector abstraction or replay subsystem. The broader architecture should be
justified by later provider and adopter needs rather than assumed from this one
failure.

### Move orientation code into `tools/orientation/` while calling it internal

Rejected for this slice. `tools/` is currently part of `PUBLIC_SURFACE_PATHS`,
so that move would have a public-surface effect and contradict the self-only
admission unless the surface contract changed explicitly.

### Infer the next action from Git history

Rejected. Git subject identity can invalidate a stale projection but cannot
supply provider-owned admission or semantic priority. Missing semantic/provider
facts remain unknown until a separately admitted source supplies them.

## Compatibility and security

The internal snapshot format, Markdown budget, source/fact groups, recorded
provider assurance and existing public CLI remain unchanged. Direct Python
callers that supply already-bound inputs keep deterministic behavior; the new
live check belongs to the CLI/self-host boundary.

Git commands use argument-vector execution rather than a shell, an explicit
resolved repository root, captured bounded text output and a short timeout. No
credential, network or provider capability is needed. Local source path
confinement remains resolve-based and gains direct traversal/symlink regression
coverage. Inherited `GIT_*` variables are removed before invocation;
`GIT_OPTIONAL_LOCKS=0`, `LC_ALL=C` and `LANG=C` are then set explicitly.

The first candidate OCI fast run exposed the expected bind-mount ownership
boundary: Git rejected `/workspace` as a dubious repository because the
container user differs from the host checkout owner. O2-A0 handles only that
container boundary with invocation-local
`git -c safe.directory=<exact-resolved-repository-root> ...`. It does not write
Git configuration, does not use `safe.directory=*`, and still verifies that the
observed Git top level exactly equals the explicit root before accepting commit
or tree identity.

## Consequences

A stale retained orientation file can continue to exist as historical evidence,
but the live projector can no longer truthfully call it current when the local
repository subject has moved. O2-A0 does not regenerate a correct next action;
it only prevents an obsolete one from being presented as current.

The slice depends on the existing local Git runtime component already pinned in
the primary OCI runtime. It adds no Python Git-library dependency. It does not
establish the generic Issue #14 projection contract, provider freshness,
automatic roadmap maintenance, semantic completeness or adopter utility.

## Revisit conditions

Revisit this Decision when one of the following is admitted:

- O2-B requires live hosting-provider observations;
- a reusable orientation package must be installed while remaining outside the
  inherited public surface;
- Git object-format support must move beyond the current D14-O1 40-hex internal
  subject contract;
- measured use shows that subject invalidation alone does not materially reduce
  stale-orientation errors;
- a generic source manifest/replay contract is promoted under Issue #14.
