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

## Decision

1. **No host payload persistence.** Canonicalize the protected input and policy
   into one JSON envelope in memory. Reject it before process creation when it
   exceeds a fixed byte bound. Do not write either document to a host file,
   mount, argv, environment, stdout, stderr or exception message.
2. **Bounded simultaneous pipe handling.** Extend the existing Docker runner
   with optional input bytes. When input exists, attach Docker stdin, stream it
   in bounded non-blocking chunks while draining stdout/stderr, close the pipe
   after the final byte, and preserve the single deadline, output limits,
   kill/reap and container cleanup semantics. Every started `docker run` has a
   predeclared non-payload name as well as a CID file; abort cleanup retries by
   CID when available and otherwise by that name. An unconfirmed cleanup does
   not proactively unlink the CID file before propagating and reports the
   predeclared recovery name. Calls without input receive a closed stdin rather
   than inheriting the caller's stream.
3. **Fixed in-container bridge.** Run the authority-bound image with the existing
   security arguments and a fixed Python bridge. The bridge validates the closed
   envelope shape, uses restrictive creation semantics below `/tmp`, writes the
   two CLI inputs only to the container tmpfs, and execs `tools.cli review-check`
   without a shell or payload interpolation. The existing network, read-only
   root, capability, identity, surface and semantic-result checks remain
   unchanged.
4. **Narrow public-identity disposition.** Add line-scoped pragmas to the exact
   reviewed YAML/Python public identities. Preserve the bytes of protected
   authority JSON and record only its exact remaining candidate hashes in the
   audited baseline. Bind the only two baseline-authorized JSON paths to their
   reviewed SHA-256 file identities, so changing a protected document and its
   baseline together still fails closed. The excluded baseline accepts only
   its closed scanner schema; unknown top-level, plugin, filter or candidate
   fields fail closed. A stale baseline entry, malformed entry,
   non-false-positive entry or new candidate fails closed. Inline pragmas remain
   explicit, review-visible declarations rather than self-authenticating proof
   that a value is public: additions or changes require semantic review. This
   candidate-owned gate does not claim to sandbox a malicious author who can
   also rewrite the gate itself.
5. **One reusable tracked-tree scan.** Factor the scan/baseline comparison into
   one repository-owned command that emits only candidate metadata, never the
   candidate value or candidate-derived hash. Validate every scanner argument
   as a repository-relative regular file, terminate option parsing before those
   arguments, translate candidate-enumeration failures, and bound stdout/stderr
   while reading rather than after buffering. Acquire each candidate through
   descriptor-relative `O_NOFOLLOW` traversal into a private, disposable scan
   snapshot. Open the final candidate non-blocking so a FIFO replacement cannot
   stall acquisition, enforce per-file, cumulative-byte and acquisition-time
   bounds, verify stable inode and file metadata across the copy, and re-traverse
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
   runs natively as an inexpensive independent exact-head gate and may execute
   concurrently with image-building jobs. For applicable candidates, `extended`
   reruns that same implementation inside the development image; the native
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
   A candidate change to `tools/extended_route.py` independently forces `RUN`
   before the candidate-owned router is consulted. Topic branches are verified
   by the Pull Request event only; the workflow's `push` event is restricted to
   protected `main`, so a duplicate topic-push run cannot publish skipped jobs
   under the same required context names.
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

## Verification contract

Pre-implementation RED evidence and the final candidate must demonstrate:

- the protected consumer invokes no host payload write or payload bind mount;
- input exceeding the bound is rejected without starting Docker;
- large bounded input and output are multiplexed without deadlock, and early
  stdin closure, timeout and output overflow terminate and clean up safely;
- stdin setup and output-overflow aborts use the predeclared container identity;
  failed cleanup is retried and leaves a reported recovery identity;
- payload sentinels occur only in the stdin bytes supplied to the mocked/fake
  child, not argv, environment, output or exceptions;
- the bridge is fixed, uses the existing tmpfs, and preserves the exact
  authority-bound judge invocation and result;
- the reviewed tree has zero unresolved secret candidates, while an injected
  candidate, stale baseline, unknown baseline field, unauthorized baseline
  entry and candidate scanner-module shadow fail;
- snapshot acquisition rejects per-file/cumulative overflow and timeout; an
  in-place or ancestor-directory replacement cannot change the private bytes
  presented to the scanner; a FIFO replacement fails without blocking; and the
  disposable snapshot is removed after the scan;
- protected JSON file identities are unchanged;
- every relevant provider event/path class maps deterministically to `RUN` or
  `NOT_APPLICABLE`, high-risk PRs actually execute `extended`, no topic-push
  duplicate can satisfy a required name with a skipped job, and the structural
  oracle rejects disabled, non-blocking or wrongly native suite steps;
- policy, fast, regression, smoke, runtime self-check and applicable extended
  verification pass against the exact candidate.

Provider subjects are deliberately complementary. `security-fast`, routing,
`extended`, and smoke bind the Pull Request head so the sealed source itself is
observed. Policy, fast, Python compatibility, and regression use the provider's
merge candidate to establish integration compatibility. Regression requires the
results from both subjects; neither set alone is convergence evidence.

Tests establish the mechanics they execute. Only GitHub provider read-back can
establish alert closure, exact-head job status and the later effective required
check.

## Consequences

- Sensitive protected-review material is no longer persisted on the host by the
  live outer consumer; the compatibility files exist only in the disposable
  container tmpfs.
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
