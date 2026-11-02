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
  - id: replay
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6547496699
    title: The devcontainer's uid-remap replay, which demonstrated the default-process regression
  - id: package-return
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6547730956
    title: "The compatibility package's preparation: the installed client, the real DIFF, the seams"
  - id: package-delta
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6549613356
    title: "The corrected admission delta, scope revision 2: the exact factoring hunks and identities"
  - id: package-route
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6550916593
    title: "The Router's reconciled five-path packet, scope revision 2"
  - id: owner-package
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6565729702
    title: "The owner's admission of the five-path compatibility package"
  - id: m17-blocker
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6589001006
    title: "#477's merge blocker, measured: M17 counts DeepSource's full-run findings in the PR's touched files"
  - id: review-477
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6588287035
    title: "#477's review round 1: the restoration job's failed import and the residue probe's missing image"
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
   follow the remapped uid; it becomes `10001:10001`, which would not. The replay and the
   installed client confirmed it: on a host whose uid is not 10001, the container's default
   process became the nameless uid 10001 and lost HOME, workspace writes and `git config`
   (sources `replay`, `package-return`). Item 5 repairs it.
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
     change is refused there, before an authority is rebound. Item 6 adapts that boundary,
     and only that boundary.
   - The uid and gid, Hadolint's configuration and pin, the profile, and every pragma or
     ignore stay. The Dockerfile family stays inactive until the cutover activates it.
5. **The devcontainer starts as `kit`** (source `owner-package`).
   - `.devcontainer/devcontainer.json` gains `"containerUser": "kit"`. Its `remoteUser`,
     `updateRemoteUserUID` and every other setting stay.
   - The client starts the container as that name, which follows the remapped uid.
   - `tests/test_tools.py`'s devcontainer contract pins it.
6. **The restoration harness's local boundary accepts exactly `kit` and `10001:10001`.**
   - `_verify_local_candidate`'s identity check takes either user, and nothing else.
   - The operating system and architecture, the exact image id, the revision and source
     binding, the public surface and the 10001:10001 uid and gid checks stay.
   - Its three private accesses move to the existing `patch.object(spec=True,
     new_callable=...)` idiom and to the original plan's `daemon_image`. There is no API,
     suppression or alias change.
   - `main` is factored within the same file (source `package-delta`), into:
     - one fresh `_CandidateRun` per call;
     - the private helpers `_build_candidate_plan`, `_tmp_residue_issue` and
       `_inspect_then_remove`.

     The daemon image is taken from the original plan before the plan is validated.
   - **The one behaviour difference:** only when the original plan builder itself raises,
     so that no plan exists, does a later tmp-volume residue probe lack the image. It then
     reports that it has no daemon image, before any Docker run, instead of probing with the
     module constant. The run already fails on that path.
   - `tools/review_current.py`, `tools/review_outer.py` and the historical pins stay.
   - `tests/test_current_advisory_restoration_runtime.py` gains two behavioural tests.
     - The first has a refusing fake that answers only the verifier's exact argvs. It takes
       the private `_verify_local_candidate` from the smoke module's own namespace,
       `vars(smoke)`, rather than by attribute access, and imports no other test module: the
       restoration job runs this file with only the restoration source on its path. It
       covers both accepted users and the root,
       malformed, field-count, OS, architecture, revision, image, uid, gid and surface
       negatives.
     - The second pins the residue probe's report when no daemon image was recorded.
7. **A persistent account invariant:** `test_runtime_image_contract_is_pinned_and_non_root`
   asserts the four `USER` instructions are `0:0`, then the account's `uid:gid`, then `0:0`,
   then `uid:gid` again. The account is the one `groupadd` and `useradd` create.

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
- **After items 5 to 7, on the package's own head:**
  - **The installed client:** pre, post and post-repair, at host uid 1000. The 10001 control
    stays the updater replay, not a full-client run, because this host has no 10001 account.
    Its bind-folder ownership denial stays recorded as such, never as access.
  - **The restoration verifier:** unchanged, it accepts, refuses and refuses on the
    historical, numeric and root images. Repaired, it accepts, accepts and refuses. Every
    negative of item 6's test is refused.
  - **The invariant:** it holds on the candidate, and fails on the measured drift mutants,
    M-uid and M-both.
  - **The factoring:** the same v1 and v2 characterization harness, run against the
    factored smoke, gives identical rows. Each changed function measures 15 or below.
  - **The rest:** the 142 test identities and outcomes, and the 15 of 17 kill set. The real
    collector's DIFF lists 0 findings.

## Consequences

- **What the repair settles:** the closure's four DL3066 findings.
- **What items 5 to 7 close:**
  - The numeric `USER` no longer follows the name. Item 5 gives the devcontainer back a
    named default user.
  - Item 7 makes an account change that `USER` does not follow fail a test.
  - Item 6 lets a numeric-`USER` restoration candidate qualify locally.
- **The limit that stays:** the full-client control at host uid 10001 is not executed on this
  host.
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

## Amendments

This text amends r2 (9,553 bytes, SHA-256
`aef2b42cb5b2abc132b5667ebe6fe9bd5358666b28ec73f8af93b5255c23f46e`), on the owner's admission
of the five-path compatibility package, scope revision 2 (source `owner-package`, prepared
in `package-return` and `package-delta`, and routed in `package-route`). Items 5 to 7 are
added, with `main`'s same-file factoring in item 6. Items 2 and 4, Verification and
Consequences follow them.

## Review corrections

This text, r4, corrects r3 (14207 bytes, SHA-256
`06b83a77606266a527c3ab14c15c19c5cf80faf0072daaf7e1c937cf3cad4634`), the version #477 published, on its first
review round (source `review-477`):

1. **The boundary test's route to the verifier:** r3 reached it through the shared
   `_original` helper, imported from `tests.test_quality_evidence_profile`. The restoration
   job runs this file with only the restoration source on its path, so that import failed
   there. The test now takes the verifier from the smoke module's own namespace.
2. **The residue probe without a plan:** r3 said that the probe then reports an inspection
   failure, but the code ran Docker with the image name `None`. The probe now reports the
   missing image before any Docker run, and a test pins that.

## Merge-admission repairs

M17 counts every analyzer finding the readback lists, with no waiver. For this `critical` change,
DeepSource's full run lists the issues in the whole files it touches, not only on its lines
(source `m17-blocker`). The test files' findings are repaired without suppression. Behaviour
changes in one place, the mode guard, which now also refuses an invalid mode under `python -O`:

- `tests/test_repository_scope.py`:
  - its `module()` helper and test doubles declare their types;
  - the `subprocess.run` doubles declare and forward the one call they replace, `check` included;
  - its own Git commands name Git by its full path;
  - two nested `with` statements are merged;
  - one helper is static;
  - a mock reads its iterator directly.
- `tests/test_current_advisory_restoration_runtime.py` reads `policy/guardrails.yaml` with
  `yaml.safe_load`. On that file it gives the same document as `BaseLoader`.
- `tests/test_tool_acquisition.py`'s mode guard raises instead of asserting, so it also holds under
  `python -O`, where an `assert` is removed.
