---
type: Decision
title: Name the image's users by number
description: "The Dockerfile's four USER instructions name their user by number, root as 0:0 and kit as 10001:10001, so Hadolint's DL3066 holds; the uid, gid, name, home and every file owner stay, only the built images' Config.User changes, and the three tests that pin the Dockerfile's text follow it. Composed with T1 in #389's critical cutover."
status: draft
generated:
  by: anthropic/claude-opus-5-5
  at: "2026-10-31T17:58:00Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/389
    title: Keep merges possible while a vendor analyzer is unavailable
  - id: owner-closure
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6542636396
    title: "The owner's direction: resolve every recorded problem, carry no debt, activate as soon as possible"
  - id: return
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6543317786
    title: "The closure return: the identity treatment and its consumers, section 1"
  - id: identity
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6543348384
    title: The pre-change identity characterization of both targets
  - id: route
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6546253006
    title: "The Router's front plan: the finite four-USER, three-test repair, historical images left historical"
  - id: integration
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6546530247
    title: "The Router's integration route: the smallest coherent critical cutover"
  - id: t1
    resource: ./0124-bound-test-tools-two-complex-functions-and-repair-its-typing.md
    title: T1, the prerequisite that cleans the shared test file first
  - id: profile
    resource: ./0117-select-the-diagnostic-inventory-s-families-through-a-protected-profile.md
    title: The protected profile that pins Hadolint, unchanged
  - id: original-record
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6547077552
    title: This Decision's first published version, with its lineage and pre-change evidence
  - id: consumers
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6547220510
    title: "PAO's findings on the restoration harness's local boundary and the devcontainer's uid remapping"
  - id: correction-route
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6547289283
    title: "The Router's route for the two consumer boundaries"
x-project-knowledge:
  id: kit.decision.0125.name-the-image-s-users-by-number
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /decisions/0124-bound-test-tools-two-complex-functions-and-repair-its-typing.md
    - kind: references
      target: /decisions/0117-select-the-diagnostic-inventory-s-families-through-a-protected-profile.md
---

# Name the image's users by number

## Context

The `Dockerfile` switches user four times, by name: `USER root` at lines 128 and 139, before
each target's privileged steps, and `USER kit` at lines 133 and 153, which drops privilege
before the image is handed on. The pinned Hadolint, run the way the inventory's producer runs
it, lists DL3066 at each, "Non-numeric user-id may not be resolvable by host system" (source
`profile`). A name resolves only through the image's `/etc/passwd`; a host or an orchestrator
reading `Config.User` cannot tell that `kit` is not root without it.

The `base` stage already creates `kit` with uid and gid 10001. With an explicit group, a
numeric `USER` resolves to the same identity as the name. The pre-change characterization
showed that `--user 10001:10001` gives the same uid, gid, groups, name, home, umask and file
owners as `USER kit` in both targets (source `identity`).

## Decision

1. **The four `USER` instructions name their user by number:**
   - `USER root` becomes `USER 0:0`, at lines 128 and 139;
   - `USER kit` becomes `USER 10001:10001`, at lines 133 and 153.
2. **Everything that names `kit` stays:** `groupadd --gid 10001 kit`, `useradd --uid 10001`,
   `--chown=kit:kit`, and the devcontainer's `remoteUser: kit`. The name still resolves, and
   DL3066 reads only `USER`. The devcontainer's `updateRemoteUserUID: true` is, however, a
   consumer of `USER` (source `consumers`). By the client's source, after remapping `kit` to
   the host's uid and gid, it restores the image's `Config.User`. That was `kit`, which would
   follow the remapped uid; it becomes `10001:10001`, which would not. Its behaviour is
   characterized before this consumer is called unchanged (see Verification).
3. **The three tests that pin the `Dockerfile`'s text follow it,** each keeping its intent:
   - `tests/test_repository_scope.py`: root is taken before the runtime's removals, and
     dropped again after them;
   - `tests/test_tool_acquisition.py`: the development tools are installed before the drop;
   - `tests/test_tools.py`'s `test_runtime_image_contract_is_pinned_and_non_root`: the image
     ends as the non-root user. This hunk sits on T1's head (source `t1`).
4. **What stays unchanged** (source `return`, `route`):
   - Images built from pinned historical revisions keep `kit`, and so do their readers: eight
     publication workflows, `ci/verify`'s release `0.2.0` check, and those workflows' two
     tests.
   - Two authority-bound checks keep `kit`: `tools/review_current.py` and
     `tools/review_outer.py`. Each pulls an image by an authority-bound digest. An image
     built after this change carries `10001:10001`, and those checks refuse it, failing
     closed. The change that first binds an authority to such an image updates them with it.
   - The restoration harness, `ci/review_current_advisory_restoration_smoke.py`, keeps `kit`
     at a separate, earlier boundary (source `consumers`). It also takes a local candidate
     (`GNOSTOA_R2A_CANDIDATE_IMAGE`) and verifies it in `_verify_local_candidate` before any
     publication. Every current caller builds that candidate from the pinned source
     `315487e7`, so it still sees `kit`. A restoration candidate built from source after this
     change is refused there, before an authority is rebound. This change leaves that
     boundary unchanged; adapting it is a separate, finite disposition.
   - The uid and gid, Hadolint's configuration and pin, the profile, and every pragma or
     ignore stay. The Dockerfile family stays inactive until the cutover activates it.

## Verification

- **Before:**
  - The pinned Hadolint lists DL3066 at lines 128, 133, 139 and 153, on T1's head
    `55177756`, whose `Dockerfile` blob `5124174a` is `main`'s.
  - The identity characterization of both targets stands as recorded (source `identity`).
- **After, on the candidate head:**
  - The same Hadolint run lists 0 findings.
  - Both targets are built from the candidate. The same characterization script runs over
    them and over images built from T1's head. Every attribute is identical except
    `Config.User` (`kit` to `10001:10001`).
  - The build phase's `root` and `0:0` resolve to the same uid, gid and groups.
  - The three changed tests pass on the candidate, and fail on the pre-change `Dockerfile`.
    The three modules otherwise keep their test identities and outcomes.
  - The real collector's DIFF lists 0 findings.
  - The restoration harness's `_verify_local_candidate`, unchanged, is given each runtime
    image's own measured id, revision and public-surface digest. It accepts the image built
    from T1's head and refuses the candidate's ("local R2 candidate runtime identity
    changed"), at its `Config.User` check.
  - The devcontainer's uid remapping is replayed on both development images, with a host
    uid and gid of 10001 as the control and with one that differs. Each records the
    remapping, the default and remote processes' uid, gid, groups, name and HOME, and the
    workspace's permissions. A client that is not available is named as a limit.

## Consequences

- **What the repair settles:** the closure's four DL3066 findings.
- **What is left in the open:** the numeric `USER` no longer follows the name. If
  `useradd --uid` or `--gid` changed, or the devcontainer remapped `kit` to a host uid other
  than 10001, `USER 10001:10001` would not follow it, and the default user would lose its
  name and home. In the file, both sit at the same value. No new assertion is added here,
  because that is outside this finite scope. The gap is reported for routing, with the
  existing controls' measured responses.
- **The class and route:** critical, because it changes the runtime image. It integrates
  with T1 in the critical cutover (source `integration`).

## Corrections

This text amends the first published version (source `original-record`: 6,475 bytes,
SHA-256 `23b6c971fdd688e372c1da09104f474e68f8df980651bddac8646f43b54c834b`), on PAO's two
findings (source `consumers`) and the Router's route for them (source `correction-route`):

1. **The restoration harness:** the first version grouped it with the two checks that pull
   an authority-bound digest. It also verifies a local candidate before any publication,
   and that boundary is now stated, and characterized, separately.
2. **The devcontainer:** the first version listed `remoteUser: kit` as unchanged without its
   `updateRemoteUserUID` path, which restores the image's `USER` after remapping the uid.
   That path is now a consumer, with its own verification.
