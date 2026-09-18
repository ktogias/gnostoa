---
type: Decision
title: Eliminate host persistence for protected review payloads and route bounded security gates
description: Move protected review payload transport to bounded stdin and container tmpfs, narrowly disposition reviewed public identities, and make applicable security evidence execute before integration.
status: draft
generated:
  by: openai/chatgpt
  at: "2026-09-17T14:22:00Z"
sources:
  - id: security-remediation-work-item
    resource: https://github.com/ktogias/gnostoa/issues/275
    title: Eliminate protected review payload persistence and gate secret regressions
  - id: security-observation-pilot
    resource: ./0041-pilot-supplemental-github-security-observation.md
    title: Decision 0041
  - id: protected-log-remediation
    resource: https://github.com/ktogias/gnostoa/pull/271
    title: Stop protected review payloads from reaching CI logs
  - id: codeql-cleartext-storage-query
    resource: https://codeql.github.com/codeql-query-help/python/py-clear-text-storage-sensitive-data/
    title: CodeQL clear-text storage of sensitive information query
  - id: detect-secrets-150
    resource: https://github.com/Yelp/detect-secrets/tree/v1.5.0
    title: detect-secrets v1.5.0
x-project-knowledge:
  id: kit.decision.0082.eliminate-host-persistence-for-protected-review-payloads-and-route-security-gates
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0041-pilot-supplemental-github-security-observation.md
    - kind: governed-by
      target: /decisions/0067-evaluate-semantic-review-assurance-through-bound-evidence.md
    - kind: references
      target: /requirements/centralized-ci-verifies-integration-candidates.md
---

# Eliminate host persistence for protected review payloads and route bounded security gates

## Context

Decision 0041 introduced GitHub-managed Python CodeQL as a supplemental,
non-blocking observation surface. Its route for a material future alert was
explicit: subject/applicability triage, owner admission, then one bounded
remediation. That condition now exists.

CodeQL alert #3 identifies the current protected consumer writing the delegated
review input and protected policy as clear-text files below host `/tmp` before
bind-mounting them into the immutable prior-integrated judge. The temporary root
is mode `0700`, the payload files are removed at context exit, and judge
execution is isolated, but those controls reduce exposure rather than remove
host persistence. The input can contain free-form provider and review material;
the finding is materially applicable and is not dismissed.

The separate clear-text logging alert was remediated by PR #271 at protected
`main` `e071ab60a418eddda5bf008004ee96faafbf1e7c`. This Decision preserves its
static-output rule and does not reopen or duplicate that change.

The scheduled `extended` run `35201025484` separately found 21 high-entropy
strings. Review of its retained report and source locations classified all 21 as
public Git commit/tree identities, OCI digests or public-surface digests. The
scanner behaved as designed; the defect is that reviewed benign identities were
not narrowly dispositioned and the same inexpensive observation was absent from
ordinary Pull Requests. The provider artifact is retention-bound, so the
sanitized path/line/type inventory and its single disposition are retained in
[`0082-secret-scan-triage-evidence.json`](../assessments/0082-secret-scan-triage-evidence.json).
That versioned record binds the exact workflow run attempt, event, head commit,
head tree and observation cut, and freezes the deterministic extraction and
ordering rule. It deliberately excludes candidate text and candidate-derived
hashes.

## Prior-art and reuse disposition

Reuse the existing immutable judge, Docker isolation flags, bounded tmpfs,
container cleanup, output limits and file-based `review-check` contract. The
prior-integrated image cannot be changed retroactively and its command expects
two file paths, so a fixed bridge inside that same container is the smallest
compatible mechanism. It receives one stdin envelope, creates the required
files only below the already bounded container tmpfs, and execs the unchanged
CLI. The bridge is fixed source: no payload value enters command arguments,
environment values or executable code.

Adapt the current selector-based Docker subprocess loop to write bounded stdin
while continuing to drain bounded stdout and stderr. Python's subprocess
documentation warns that one-sided pipe handling can deadlock; the loop must
therefore multiplex all three streams and retain the existing deadline and
container cleanup behavior. A host file, host `/dev/shm`, argv/environment
transport and encryption-at-rest are rejected respectively because they retain
host persistence, expose process metadata or add unnecessary key-management
surface.

Reuse `detect-secrets==1.5.0`, already hash-pinned in the development lock and
licensed Apache-2.0. Use its line-scoped inline allowlist for public literals in
comment-capable YAML/Python. Use an audited exact path/type/secret-hash baseline
only for the closed-schema, content-addressed JSON documents that must not be
mutated for scanner annotations. Do not add a broad hexadecimal filter, path
exclusion, second scanner or hosted service. The existing dependency introduces
no new acquisition, redistribution, attribution or NOTICE effect.

Two concrete snapshot alternatives were considered. Python `shutil.copytree`
(PSF License Version 2, compatible with this Apache-2.0 distribution and already
part of the runtime) re-resolves pathnames while copying; its symlink options do
not bind every component to opened directory descriptors or detect an in-place
change across the read. `git archive` plus Python `tarfile` would use Git's
GPL-2.0-only executable as an external development tool and the PSF-licensed
standard library. That process-level use is compatible because Git is neither
linked nor redistributed here, but it covers only a Git object tree, not the
supported packaged-manifest or caller-supplied tracked-path surfaces, and safe
tar extraction would add a second custom validation boundary. A new `rsync`
dependency was also rejected: its GPL-3.0-or-later program can be invoked as a
separate system tool without relicensing this project, but it is not locked or
guaranteed in the runtime and path-based copy still does not supply the required
descriptor binding. The selected standard-library implementation is therefore
shared across all supported source forms, adds no dependency, opens each path
relative to held directory descriptors with `O_NOFOLLOW | O_NONBLOCK`, and
checks stable metadata around the copy.

Keep GitHub-managed CodeQL default setup. Advanced setup is not required to fix
the source operation or to make the provider result a later protected-branch
gate. A green PR CodeQL result is not a branch-wide absence claim because
GitHub's PR attribution is diff-bound; default-branch alert inventory remains a
separate read-back.

## Owner-admitted staged containment — 2026-09-18

The [deep review of PR #278](https://github.com/ktogias/gnostoa/pull/278#issuecomment-5728138715)
identified a missing execution boundary: the candidate's outer stdin bridge
execs the immutable promoted runtime, not this candidate's repaired inner
implementation. That runtime still materializes delegated input and policy in
its `/tmp`, which the isolated topology supplies through a host-backed Docker
volume. Changing the candidate bridge alone does not repair those immutable
bytes. Earlier whole-path non-persistence claims are withdrawn; the historical
live result is not evidence that this changed path is safe.

The [owner-admitted behavior map](https://github.com/ktogias/gnostoa/pull/278#issuecomment-5728228063)
accepts temporary `current_advisory` unavailability. After mandatory protected-main
acquisition and closed-schema/identity validation, a restriction-only catalog
compares the canonical JSON of **all nine acquired-consumer fields**. The
catalog is initially empty: current, historical and unknown transport identities
return one static canonical `TOOL_ERROR`, exit 2, before outer temporary
resources, image acquisition, Docker lifecycle effects or payload transfer.
Authority acquisition's own bounded repository read-back still occurs first;
containment does not claim that no acquisition I/O occurs.

The catalog cannot choose an authority or image and has no caller/environment
population path. A future entry needs a separately admitted, materialized and
promoted transport-compatible runtime, exact identity and live proof. The
existing image/revision/public-surface checks remain mandatory after that
restriction. Test-local catalog entries preserve hypothetical lifecycle coverage;
they do not admit an executable runtime or prove immutable-image safety.

Reuse the existing protected read-back, closed consumer validation, canonical
error codec and historical candidate/stale-selector probe. A shared tmpfs alone
still leaves the old prohibited payload bind mount; injecting candidate code
would replace protected execution authority. Both are rejected. This bounded
containment adds no dependency, changes no license/NOTICE obligations, publishes
no image and leaves both protected authority JSON documents byte-for-byte
unchanged.

`ci/review_outer_containment_smoke.py` exercises the real public refusal after
real provider authority acquisition, with tripwires on outer effects. Its receipt
states `containment_result=PASS`, `current_advisory=UNAVAILABLE`,
`live_evaluation=NOT_RUN` and `outer_docker_effects=NOT_RUN`. Success of this smoke
is not semantic success. `ci/review_outer_smoke.py` remains historical
live/restoration evidence and is no longer the active outer smoke. Provider
runtime restoration, exact live proof and default-branch alert read-back remain
later prerequisites; **#275 stays open**. No merge, publication, authority
promotion, alert dismissal or provider required-check change is admitted here.

| ID | Observable requirement | Executable contract | Evidence boundary |
|---|---|---|---|
| SEC-1C | Current, historical and unknown transport identities refuse before outer effects | `ReviewOuterContainmentTests` public route and CLI tests | Native RED-to-GREEN; provider containment receipt is separate |
| SEC-1A | Mandatory authority validation and complete exact identity precede unchanged image proofs | Catalog-field and image-proof tests; inherited read-back/poison tests | Hypothetical test admission is not production admission |
| SEC-1E | Receipt reports unavailable evaluation, not a live semantic pass | `ContainmentSmokeTests`; active containment smoke | Unit tests do not replace real protected-main read-back |
| SEC-4M | Security scan, routing and extended inspect the same provider event subject as regression | `MergeSubjectSecurityTests`; exact ordered job contracts | Synthetic divergent merge proves the latent gap, not a defect in the actual starting merge tree |

## Decision

1. **No host payload persistence.** The staged containment above is effective
   for the presently acquired immutable outer runtime. The restored-execution
   contract, which that runtime does not yet satisfy, is: canonicalize and bound the caller's outer
   review input before authority acquisition or Docker activity, send it to the
   prior-effective outer container only through stdin, and materialize the
   compatibility input only in an outer-container-only tmpfs. Inside that
   runtime, canonicalize the delegated protected input and policy into one
   bounded JSON envelope in memory and send it through stdin to the
   prior-integrated judge. Do not write any of those documents to a host file,
   bind mount, argv, environment, stdout, stderr or exception message. Disable
   Docker log persistence for the payload-bearing inner and outer containers,
   for the isolated daemon container, and as the isolated daemon's default, so
   attached result stdout is returned to the caller without being retained by
   either daemon's container-log storage.
2. **Bounded simultaneous pipe handling.** Extend the existing Docker runner
   with optional input bytes. When input exists, attach Docker stdin, stream it
   in bounded non-blocking chunks while draining stdout/stderr, close the pipe
   after the final byte, and preserve the single deadline, output limits,
   kill/reap and container cleanup semantics. Every started `docker run` has a
   predeclared non-payload name as well as a CID file; abort cleanup retries by
   CID when available and otherwise by that name. Abort is diagnostically
   subordinate: it never raises, so the triggering timeout, bounded-size or I/O
   failure stays the primary diagnostic and any reap or cleanup problem is
   appended as bounded secondary context. The predeclared recovery name is part
   of that context only when container removal is unconfirmed, because only then
   is a container left to recover. A
   container the runtime already removed under `--rm` is reconciled as
   successful absence through the bounded case-insensitive `no such container`
   response; every other bounded diagnostic stays fail-closed and retried. The
   cleanup diagnostic is read incrementally and the cleanup client is stopped as
   soon as the bound is reached, so a noisy client cannot buffer an unbounded
   stream. Discarding the CID file is itself subordinate and never raises; every
   abort path discards it once cleanup is confirmed and reports any discard
   problem as part of its own secondary context, while an unconfirmed cleanup
   does not proactively unlink it and leaves the recovery identity behind.
   Cleanup confirmation is therefore reported separately from client reaping: a
   reap that cannot be confirmed is secondary context only, and never withholds
   the discard or advertises a recovery identity for an already removed
   container. Retain the
   executable used to launch Docker, treat unreadable or malformed CID content
   as a name fallback, bound child reaping, and attempt container cleanup even
   when client reaping cannot be confirmed. Docker options before the image fail closed against the exact
   repository-used allowlist, including the `--mount` value option required by
   the B1.6 smoke. Caller-owned Docker `--name` and `--cidfile` options are
   rejected only in that option region; identically named arguments in the
   container command remain container data. The bounded timeout smoke
   requests its known name through the runner's validated identity parameter, so
   launch and fallback cleanup cannot disagree. Calls without input receive a
   closed stdin rather than inheriting the caller's stream.
   An incomplete pipe set is also a cleanup boundary. Both the Docker and
   scanner runners perform their existing bounded reap/reconciliation first,
   then attempt to close every surviving stream before reporting the original
   pipe-setup failure. A close error is static, role-only secondary context;
   it neither leaks exception content nor prevents the remaining closes.
   The fault-injection contract in `tests/test_protected_pipe_setup_cleanup.py`
   covers each absent pipe and close failure after uncertain reaping. These
   cases establish defensive lifecycle behavior, not a claim that normal
   `Popen(..., PIPE)` produces incomplete pipes or a new payload vulnerability.
3. **Fixed in-container bridges.** For a separately admitted compatible outer
   runtime, run each authority-bound image with fixed
   Python bridge code. The outer bridge reads bounded stdin, uses restrictive
   exclusive creation in a dedicated outer-only tmpfs, and execs the immutable
   `tools.review_live_entrypoint`. The inner bridge validates the closed envelope
   shape, uses the same restrictive creation semantics below its own `/tmp`
   tmpfs, writes the two CLI inputs there, and execs `tools.cli review-check`.
   Neither bridge uses a shell or interpolates payload content. The existing
   network, read-only root, capability, identity, surface and semantic-result
   checks remain unchanged. The candidate bridge must not be treated as proof
   that the old immutable outer image contains the repaired inner bridge.
4. **Narrow public-identity disposition.** Add line-scoped pragmas to the exact
   reviewed YAML/Python public identities. Preserve the bytes of protected
   authority JSON and record only its exact remaining candidate hashes in the
   audited baseline. Bind the only two baseline-authorized JSON paths to their
   reviewed SHA-256 file identities, so changing a protected document and its
   baseline together still fails closed. The excluded baseline accepts only
   its closed scanner schema. The baseline and scanner stdout share the same
   strict decoder and closed report-schema validation: duplicate names at any
   JSON depth, non-finite values including overflowing exponent forms, excessive
   nesting, unknown top-level/plugin/filter/candidate fields, and non-boolean
   candidate disposition values fail closed. Candidate identity includes an
   exact, bounded line number as well as path, rule and hash, so stale or
   arbitrary numeric audit metadata cannot suppress a finding. A stale baseline
   entry, malformed entry, non-false-positive entry or new candidate fails
   closed. Inline pragmas remain explicit, review-visible declarations rather
   than self-authenticating proof that a value is public: additions or changes
   require semantic review. This candidate-owned gate does not claim to sandbox
   a malicious author who can also rewrite the gate itself.
5. **One reusable tracked-tree scan.** Factor the scan/baseline comparison into
   one repository-owned command that emits only candidate metadata, never the
   candidate value or candidate-derived hash. Validate every scanner argument
   as a repository-relative regular file, terminate option parsing before those
   arguments, translate candidate-enumeration failures, and bound stdout/stderr
   while reading rather than after buffering. Acquire each candidate through
   descriptor-relative `O_NOFOLLOW` traversal into a private, disposable scan
   snapshot. Open the final candidate non-blocking so a FIFO replacement cannot
   stall acquisition, enforce per-file and cumulative-byte bounds plus the
   cooperative acquisition deadline qualified below, verify stable inode and file metadata across the copy, and re-traverse
   the complete path from the retained repository-root descriptor so replacement
   of an ancestor directory cannot validate a detached object. Invoke the pinned
   scanner with isolated Python module resolution so candidate files cannot
   shadow the dependency, and scan only the acquired bytes. The snapshot is
   deleted on exit and is distinct from the protected-review payload, which is
   never written on the host. `extended` reuses the command and retains a
   sanitized report plus counts of reviewed and unresolved candidates. The
   baseline manifest itself is the single exact scanner exclusion because
   scanning its candidate hashes would create a recursive, unstable baseline.
   A canonical scan requires that manifest to be part of the enumerated
   candidate set; only an explicit caller-scoped scan may add a separately
   supplied relative baseline to its disposable snapshot.
6. **Ordinary PR security gate.** Add `security-fast` as a visible provider job
   using the exact development lock and the shared scan command. It intentionally
   runs natively as an inexpensive independent provider-event-subject gate and may execute
   concurrently with image-building jobs. For applicable candidates, `extended`
   reruns that same implementation inside the development image on the same
   provider event/merge candidate; the native
   result does not substitute for containerized evidence. `regression` consumes
   its result with `always()` and fails unless it succeeded, so a failed scan
   cannot become a skipped-green downstream gate.
7. **Explicit extended applicability.** Add one always-running routing job. It
   reports `RUN` for schedule/manual and for Pull Request, merge-candidate or
   protected-integration changes that touch the declared maintained Python,
   CI/workflow, dependency, documentation, release-evidence or protected
   authority surfaces, including `.gitlab-ci.yml`, `.secrets.baseline`,
   `LICENSE`, `LICENSING.md`, `NOTICE`, `SUPPORT.md`,
   `THIRD_PARTY_NOTICES`, and the complete `policy/` tree. Otherwise it reports
   `NOT_APPLICABLE` and a bounded reason. The heavyweight job may remain
   conditionally skipped, but `regression` accepts only a successful applicable
   run or an exact `NOT_APPLICABLE`/skipped pair. Neither the router nor project
   records call that skip a pass.
   Schedule/manual events, an unavailable or unverifiable comparison base, and a
   candidate change to `tools/extended_route.py` independently force `RUN` in
   shell before a router is consulted. For the remaining valid-base route, the
   workflow materializes `tools/extended_route.py` from the exact comparison-base
   Git object outside the checkout and executes it as an isolated script. It does
   not import the candidate `tools` package or another candidate-controlled
   Python startup surface. The required-context
   workflow's `push` event is restricted to protected `main`. A separate
   topic-push advisory workflow preserves the inherited always-on branch-revision
   `policy` and `fast` suites under distinct `branch-advisory-*` names, so those
   runs cannot publish skipped jobs under Pull Request required-context names.
   Structural contracts bind the complete root key set, exact event maps,
   read-only permissions, concurrency and image environment, the exact eight-job
   required workflow inventory and two-job advisory inventory, every display
   name, job key, ordered complete step sequence, strategy/output map and exact
   dependency list. They reject any inserted, removed or changed step, extra job,
   workflow default or privilege, job/step environment override, renamed or
   duplicated context, or suite job that is disabled, non-blocking, wrongly native,
   dependency-skipped or wrapped by alternate shell/default behavior, while
   allowing only the exact declared `regression` and `extended` predicates.
8. **Provider CodeQL effect remains sequenced.** After this Decision and the
   implementation are integrated and provider read-back confirms clean
   exact-head/default-branch results, require the stable GitHub CodeQL result for
   protected integration at the provider. That setting change is a separate
   exact effect; this source candidate does not perform it or claim it already
   exists. Error/high findings block; lower-severity observations retain the
   bounded triage route unless later policy selects otherwise.
9. **Restore green before roadmap continuation.** Read back alert #3 as fixed and
   alert #4 as still fixed, and obtain a successful integrated applicable
   `extended` result before returning `roadmap:now` to #262. No alert dismissal
   substitutes for those observations.

### Finalizer error containment

The same primary-first rule also applies after normal pipe setup: each final
selector and stream close is attempted even when an earlier close raises an
`OSError`. Docker and scanner failures retain their original timeout, overflow
or I/O diagnostic, with static role-only close context. Otherwise successful
runner execution with failed local finalization is reported as a controlled
error, not success. The cleanup diagnostic preserves a known removal-command
exit status separately from bounded local close context; local close failure
alone is not evidence of a container left to recover. Unknown command completion
still fails closed, with reap attempted before returning its bounded diagnostic.
Input-only pipe absence is identified as input, not output failure. Fault-injected
contracts in [the finalizer suite](../../tests/test_protected_finalizer_errors.py)
cover timeout, overflow, I/O and normal completion at every tested closing
role; they establish these mechanics, not new live runtime availability.

### Owner-admitted bounded review follow-up

The [owner continuation](https://github.com/ktogias/gnostoa/pull/278#issuecomment-5730114348),
[prospective map and portal reconciliation](https://github.com/ktogias/gnostoa/pull/278#issuecomment-5730174137)
and [router scope clarification](https://github.com/ktogias/gnostoa/pull/278#issuecomment-5730704792)
admit the following repairs without restoring the contained runtime or changing
protected authority, dependencies, workflow fingerprints or required checks.

- Snapshot acquisition uses one **cooperative 60-second deadline**, checked
  around reads and writes, during every partial write, after source validation
  and before snapshot handoff. A syscall that returns after the deadline causes
  refusal, not scanner execution. A blocked filesystem syscall is not interrupted
  by this mechanism; chunk size and regular-file `O_NONBLOCK` do not bound its
  latency. The existing provider job timeout is an outer safeguard, not a
  60-second return guarantee. A hard-interruption worker is not selected.
- A completed runner must report CID-file discard failure as static subordinate
  finalization evidence. A leftover non-payload identity file does not imply
  an unremoved container or authorize a recovery operation.
- Cleanup diagnostics reserve bytes for the fixed close-failure roles before
  truncating their primary prefix, preserve bounded valid UTF-8 and retain the
  observed removal-command exit status independently of local close failures.
- Scanner OS diagnostics expose only a standard symbolic errno or `UNKNOWN`,
  never arbitrary exception text, filenames or payload. Length truncation alone
  is not sanitization.
- The protected judge opts into complete-envelope **write** validation. Premature
  stdin closure is a controlled transport failure with existing abort/cleanup;
  generic early-close behavior is retained. Pipe delivery does not establish
  consumer processing or semantic acceptance, which require separate validation.
- Routing rejects a would-block/incomplete input rather than classifying a
  prefix. Complete regular-file and blocking input, route classifications and
  the byte bound are unchanged. The current provider already redirects a regular
  file; this repair closes the separately reproduced nonblocking-input case.
- Subprocess launches explicitly use `shell=False` while retaining executable,
  argv, scanner option-termination and Docker-environment boundaries. This is
  audited hardening, not proof of a previous injection. The owner accepted the
  six constructor-only audit reports as false positives, not a global waiver.

The [follow-up contracts](../../tests/test_security_review_followup.py),
[protected-judge binding](../../tests/test_review_current_payload_transport.py)
and [workflow contracts](../../tests/test_tools.py) verify these boundaries.
Step-modifier tests begin with a valid real job, then use a test-local step-digest
binding to reach the independent semantic guard. Production fingerprints and
required gates remain intact. Qodo screenshot statuses are historical portal
observations, not fresh code review or evidence of candidate correctness.

## Verification contract

Pre-implementation RED evidence and the final candidate must demonstrate:

- the currently acquired immutable outer consumer refuses before outer
  temporary resources, Docker or payload transfer; independently simulated
  compatible-transport and candidate inner-bridge tests reject host payload
  writes/bind mounts and retain no payload sentinel after return, without
  claiming safe execution of the old immutable outer runtime;
- outer and inner input exceeding their bounds is rejected before authority or
  Docker effects;
- large bounded input and output are multiplexed without deadlock, and early
  stdin closure, timeout and output overflow terminate and clean up safely;
- stdin setup and output-overflow aborts use the predeclared container identity;
  failed cleanup is retried and leaves a reported recovery identity; malformed
  CID bytes fall back to the retained name/executable; and reaping is bounded
  without preventing the container-cleanup attempt;
- timeout and output-overflow failures survive a failed cleanup as the primary
  diagnostic, an already-absent container reconciles as successful cleanup, and
  every other bounded cleanup diagnostic is retried and reported;
- a failure to remove the CID file is reported as secondary context rather than
  replacing the primary failure, on the unavailable-pipes, timeout, output-
  overflow and stream I/O paths alike, and the cleanup diagnostic bound limits
  what is read rather than only what is retained;
- the tracked-tree scanner applies the same rule: a failed child reap is
  secondary context and never replaces the pipe, bounded-size, timeout or I/O
  failure that triggered it;
- payload sentinels occur only in the stdin bytes supplied to the mocked/fake
  child, not argv, environment, output or exceptions;
- payload-bearing inner/outer containers and the isolated daemon use
  non-persisting Docker logging while attached result stdout remains available;
- the candidate bridges are fixed and use container-only input tmpfs mounts;
  the incompatible immutable outer runtime remains unexecuted, so its historical
  live result is not counted as this candidate's restored-execution evidence;
- the reviewed tree has zero unresolved secret candidates, while an injected
  candidate, stale or wrong-line baseline, duplicate scanner/baseline JSON field,
  non-finite or overflowing numeric input, excessive baseline or scanner-output
  JSON nesting, unknown or
  unchecked report value, unauthorized baseline entry and candidate
  scanner-module shadow fail;
- snapshot acquisition rejects per-file/cumulative overflow and timeout; an
  in-place or ancestor-directory replacement cannot change the private bytes
  presented to the scanner; a FIFO replacement fails without blocking; and the
  disposable snapshot is removed after the scan;
- protected JSON file identities are unchanged;
- every relevant provider event/path class maps deterministically to `RUN` or
  `NOT_APPLICABLE`, high-risk PRs actually execute `extended`, no topic-push
  duplicate can satisfy a required name with a skipped job, topic pushes retain
  separately named advisory `policy`/`fast` evidence, and the structural oracle
  rejects disabled, non-blocking, shell-wrapped or wrongly native suite jobs
  and steps, inherited defaults/environment overrides, or suppressing event
  filters, inserted steps in any of the eight jobs, altered dependency lists,
  expanded permissions, extra/renamed/duplicated contexts, an unavailable-base
  route that would consult Python, or a valid-base route that imports the
  candidate package instead of the isolated comparison-base router;
- policy, fast, regression, smoke, runtime self-check and applicable extended
  verification pass against the exact candidate.

Provider subjects are deliberately aligned for integration safety.
`security-fast`, routing, `extended`, policy, fast, Python compatibility and
regression all use the triggering provider event subject (the merge candidate
for Pull Requests). Smoke separately binds the exact PR head for source/runtime
provenance. Regression requires successful security evidence for its own merged
subject, not merely a successful scan of an unmerged head. Neither subject's
checks alone establish review convergence.

Tests establish the mechanics they execute. Only GitHub provider read-back can
establish alert closure, exact-head job status and the later effective required
check.

## Consequences

- The public outer route does not transfer protected-review material into the
  incompatible runtime: it returns the static unavailable error first. This is
  containment with a deliberate availability cost, not restored live operation.
- The candidate transport's intended contract is application-level host-file,
  bind-mount and container-log non-persistence. Container tmpfs pages remain subject to the Docker
  host's swap policy; environments requiring a physical-RAM-only claim must
  enforce that separate host prerequisite.
- Reviewed public hashes remain reviewable without weakening entropy detection
  for new values.
- Ordinary PRs gain a fast secret-regression gate, while costly evidence remains
  explicit and conditionally routed.
- Decision 0041 remains the historical pilot authority and is supplemented, not
  rewritten. Provider automation still supplies observation rather than repair,
  merge, release or publication authority.
- PR #272 was integrated at protected `main`
  `850b6842077ac4eb4069174cf132663ff9acb9d6`. This candidate explicitly
  preserves its authoritative repository-root Ruff scope while adding the
  security gates; the overlap was reconciled before exact-base verification.

## Non-goals

This Decision does not change review schemas, evaluation semantics, protected
authority content, the immutable prior-integrated image, dependency versions,
release artifacts, OCI/GHCR state, attestations, automatic remediation or alert
dismissal. It does not claim that CodeQL, entropy scanning or a clean candidate
proves absence of vulnerabilities or secrets. It does not merge its own
candidate or authorize bypass of exact-head review.
