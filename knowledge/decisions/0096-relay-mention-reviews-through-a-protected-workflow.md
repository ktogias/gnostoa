---
type: Decision
title: Relay mention reviews through a protected workflow revision
description: Move the credential-bearing mention review behind a workflow_run relay so no admitted trigger can supply the workflow or the scripts it executes, and re-validate the event from the provider rather than from the relay payload.
status: draft
generated:
  by: anthropic/claude-opus-5
  at: "2026-10-01T08:00:00Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/339
    title: Decide whether review-event triggers may reach a credential-bearing job
  - id: owner-admission
    resource: https://github.com/ktogias/gnostoa/issues/339#issuecomment-5920277649
    title: Option C — untrusted trigger, privileged relay
  - id: bounded-review-context
    resource: ./0094-bound-claude-review-context.md
    title: Bound Claude review context by selecting agent mode
  - id: harden-actions
    resource: ./0093-harden-claude-code-github-actions-workflows.md
    title: Harden the Claude Code GitHub Actions workflows before integration
  - id: useful-l1
    resource: ./0086-implement-useful-l1-as-protected-source-github-current-state-reconciler.md
    title: Implement useful L1 as provider-neutral current-state reconciliation with a GitHub adapter
x-project-knowledge:
  id: kit.decision.0096.relay-mention-reviews-through-a-protected-workflow
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0093-harden-claude-code-github-actions-workflows.md
    - kind: governed-by
      target: /decisions/0094-bound-claude-review-context.md
    - kind: references
      target: /decisions/0086-implement-useful-l1-as-protected-source-github-current-state-reconciler.md
---

# Relay mention reviews through a protected workflow revision

## Context

Decision 0094 rule 21 keeps the candidate tree out of the credential-bearing mention
job by binding its checkout to `github.workflow_sha`. That premise holds only where
GitHub resolves the workflow from the default branch.

It does not hold for two of the four admitted triggers. Measured on this repository's
own run history:

| Event | Workflow resolved from |
|---|---|
| `issue_comment` | `branch=main` |
| `pull_request_review_comment` | `branch=<candidate>` |
| `pull_request_review` | `branch=<candidate>` |

So for those two events `github.workflow_sha` names a candidate revision, the checkout
binds it, and the job executes candidate `build_review_context.py` and `chunk_diff.py`.
The author-association gate offers nothing, because it is in the same
candidate-controlled file.

The exposure is not repository writes: every scope is read-only except
`id-token: write`. It is that a candidate-controlled *workflow file* can attach
`secrets.CLAUDE_CODE_OAUTH_TOKEN` to any step and exfiltrate it, and can mint an OIDC
token. The actor must already be able to push a branch, so the realistic causes are a
mistake, a compromised account, or an agent acting wrongly.

Rule 25a added a fail-closed guard before the checkout. It blocks an accidental
candidate revision, but it cannot bind a candidate that edits the file the guard lives
in. **A control inside a candidate-controlled workflow is not a boundary.**

## Prior-art and reuse disposition

The relay's *shape* is machinery this repository already runs; its admission is new
code, and this record says which is which. An earlier draft listed several modules
as reused that admission does not in fact call. CodeRabbit raised the provider-client
claim on #340, and on checking, the rest of the table had the same overstatement.

| Needed | Source | Relation |
|---|---|---|
| relay shape | `.github/workflows/review-current-state.yml`: `workflow_run` trigger, `if: github.ref == 'refs/heads/main'` per job, artifact handoff, per-job least privilege | **reused** as the pattern |
| artifact transfer | the vetted `upload-artifact` / `download-artifact` pins | **reused** |
| the reviewer, collector and publisher | the mention job's existing steps, unchanged apart from reading admission's outputs | **reused** |
| provider payload shapes | `ci/review_github_current_state.py` normalizers for issue comments, reviews and review comments | **consulted** for field names; not imported |
| provider reads in admission | `.github/review-context/admit_mention.py`'s own small standard-library client: retried, size-bounded, and bounded as a whole by abandoning a read at its timeout, as the collector does, since a socket timeout bounds one receive and a provider dripping bytes outlasted it (CodeAnt, #340) | **new** |

Two alternatives were weighed and not taken. Importing `ci/review_github_current_state.py`
into the privileged job would pull a 61 KB module and its dependency install into a
credential-bearing path for a handful of reads. Fetching through the mention job's
shell helper `api_to_file` would put the trust boundary in inline shell, which the
suite cannot exercise on its own. Admission therefore carries a deliberately small
client of its own, so that every refusal it makes is unit-testable against a fixture
that refuses what the provider refuses. That is a second provider client in the job,
stated here rather than hidden.

Withdrawing the two triggers (#339 option A) was not selected at first, because it
deletes the capability Decision 0094 rules 14, 17 and 18 were written for. The relay
kept them, bound by the provider re-read of rule 4. That binding did not converge: each
review round found another way through it. The owner then selected the withdrawal
(option (b) on #339, 2026-10-01), and rule 13 records it. The relay remains, for the two
events whose trigger runs from the default branch.

## Decision

1. **The privileged reviewer runs only from a protected workflow revision.** Its sole
   trigger is `workflow_run` on the trigger workflow. GitHub resolves a `workflow_run`
   handler from the default branch, which this repository has observed directly: of
   the last twelve `review-current-state.yml` runs, all ten `workflow_run` runs
   reported `head_branch=main` while their triggering runs were on Pull Request
   branches. The job additionally asserts `github.ref` is the default branch, so the
   property is stated in the workflow rather than only inherited from the platform.
   The pinned `claude-code-action` classifies `workflow_run` as an automation event and
   runs agent mode for it when a `prompt` is supplied, so the reviewer itself is
   unchanged.

2. **The admitted triggers move to a workflow that references nothing.** The trigger
   workflow declares `permissions: {}` at both levels and references no secret, so
   *as committed* it holds no credential, and the relay never depends on anything it
   says beyond an identifier.

   That is a statement about the committed file, **not a credential boundary**. Both
   admitted events run the trigger from the default branch (rule 13), but anyone who
   can push a branch can push *another* workflow that reads repository secrets, and
   nothing in any one file can prevent it. The credential boundary is set out below,
   under *What the relay does not establish*.

3. **The relay payload is a pointer, never a decision.** The trigger records only the
   event kind, the id of the comment or issue, and `request_sha256`, a digest of the
   request text GitHub delivered (rule 4). Admission uses the digest only to refuse,
   never to admit: one that matches admits exactly what admission re-read, so the
   payload still decides nothing (CodeRabbit, #340). The privileged job re-reads
   that object from the provider and re-establishes, from the provider's answer alone:
   that it carries the mention, that its author's association is admitted, that the
   Pull Request head is not a fork, and the head and base revisions. This re-validation
   is the new trust boundary; one that trusted the payload for anything beyond an
   identifier would make the relay decorative. Identifiers are validated as positive
   integers before they reach a URL.

4. **The payload is bound to what GitHub recorded about the triggering run.** The
   triggering run's `event`, workflow `path`, `triggering_actor` and `created_at` are
   set by GitHub and delivered on the `workflow_run` event, so a candidate cannot forge
   them. Admission refuses unless the run came from the trigger workflow's own file,
   the payload's event kind equals the one GitHub recorded, and the re-read mention was
   written by the triggering actor.

   The *triggering* actor, not the run's `actor`. GitHub keeps the original `actor`
   when someone else reruns a run and changes only `triggering_actor`, as measured
   in this repository (`knowledge/assessments/v0-2-0-source-and-oci-publication-result.md`;
   PR #149 added triggering-actor guards for it). Bound to the original actor, any
   maintainer could replay another person's earlier request under that person's
   name. So a rerun is admitted when the mention's author requests it, and anyone
   else asks with a mention of their own. Codex read the refusal of another person's
   rerun as a contradiction of the rerun sentence below (#340), and that sentence now
   says whose rerun passes.

   Without these bindings the relay has a spoofing gap: a collaborator could add a
   workflow carrying the trigger's *name* on `push`, have it upload a payload naming
   someone else's earlier mention, and start a review nobody asked for now.

   The review events needed more than these bindings, because their trigger ran from
   the candidate's branch and its author chose which object it named. Successive
   versions bound the object to the Pull Request GitHub recorded for the run, to the
   occurrence that triggered it, and to the actor's latest mention on that Pull
   Request. Each review round on #340 found another way through, the last through a
   mitigation added inside the binding (Codex). Those events are withdrawn (rule 13),
   and with them every binding that existed only for them.

   One binding is kept for the two events that remain: the relayed object must be
   **the occurrence that triggered the run**. By GitHub's clock on both sides -- the
   object's own `created_at` and the run's `workflow_run.created_at` -- it must have
   come to be at most fifteen minutes before the run, and at most sixty seconds after
   it, which allows for the two clocks' rounding. A run is created seconds after
   its event (three were measured here), so the window is margin, not tolerance for a
   guess, and a rerun keeps the run's original creation time, so a rerun by the
   mention's author still passes (rule 4 refuses anyone else's). Their
   trigger is the default branch's, so this now guards a stale relay rather than a
   hostile one.

   The occurrence is bound by its **content** as well as its identity. Admission
   re-reads the object, and the trigger first recorded only identities, so an edit
   between the event and that re-read changed the request that was reviewed while
   every check above still passed (CodeAnt, #340). Anyone with write access can edit a
   comment, and so can an app holding `issues: write`. The trigger now records
   `request_sha256`, a digest of the request text as GitHub delivered it in the event
   (a comment's body, or an opened issue's title and body). Admission refuses a re-read
   whose digest differs, or a payload that recorded none. A forged digest can only
   refuse: one that matches admits exactly what admission re-read. Measured before
   relying on it: for 34 unedited comments on this repository, the body the Events API
   delivered was byte-identical to the REST re-read. That is the Events API, not the
   webhook file itself, and none of the 34 held a CRLF; a mismatch there would refuse,
   not admit, and is a post-merge live check.

5. **The comparison is the Pull Request as it stands.** Both remaining events happen
   on the conversation, not on a revision, so admission reads the live head and base,
   and refuses a fork-controlled head (Decision 0094 rule 9). The review events had
   compared the revision the event described -- a submitted review's `commit_id`, an
   inline comment's recorded head and base -- and that machinery was withdrawn with
   them (rule 13). A request with no Pull Request has no comparison. Decision 0094
   rule 13 still shows both revisions, equal: the protected revision the job runs and
   checked out (`github.sha`), passed to admission by the workflow. Without it the
   request is refused. Writing neither, as admission first did, printed blank Base
   and Head lines (Codex, #340).

6. **The request reaches the reviewer as artefacts, not as prompt text.** Under
   `workflow_run`, `github.event` describes the triggering run, so every body, title,
   path and hunk the prompt used to interpolate would have rendered empty and the
   reviewer would have received a request with no text. Admission writes them instead
   as bounded files under `.gnostoa-review-context/request/` -- `request`, `title`
   and `item`, each present even when empty -- and the prompt names them. The title
   and the item are context, bounded at 8 KiB each. The request is the one artefact
   not cut. Every slice of an oversized request dropped the ask somewhere: a prefix
   lost a mention placed after pasted logs, a slice from the mention lost a question
   after them, and a first-and-last-half slice lost one in the middle (Codex, three
   times, #340). No bounded slice can be shown to keep the ask. The request is
   bounded where it is written: GitHub limits a comment or an issue body to 65,536
   characters, and admission reads the provider's answer within its 1 MiB bound.
   Forwarded whole, a request on one long line still hid its tail, because the
   reviewer's Read tool truncates a line past `chunk_diff.LINE_CAP` (Codex, #340). Long
   lines are hard-wrapped and each continuation is marked, as the diff's are. A marker
   alone cannot say which lines continue, since a quoted reply begins with `>` too, so
   a note at the end names every continuation by line number and the request
   reconstructs exactly.

   This tightens Decision 0094 rules 3 and 19 rather than only preserving them: the
   prompt now interpolates identity values alone (a repository name, item numbers and
   40-character revisions), so no candidate-written text reaches the one input the
   reviewer cannot treat as material under review. The static prompt shrank from 4076
   to 2927 bytes. Decision 0094 rule 15's withholding is kept and made exact: the
   *item's* author is judged separately from the *mention's* author, so a trusted
   collaborator asking about an outside contributor's Pull Request does not forward
   that contributor's text.

7. **The relay's artifact is downloaded outside the workspace, after the checkout.**
   `actions/checkout` clears the workspace, so an artifact placed there first would be
   deleted; and extracting a candidate-produced archive into the workspace would let it
   land beside the committed scripts the job is about to run. It is downloaded into
   `runner.temp`, which is outside the checkout and denied to the reviewer's Read tool,
   and the download pin is the one this repository already vets.

   The job starts only for a run GitHub recorded as an admitted event of the trigger's
   own path. `workflow_run` matches the trigger by *name*, so without that condition a
   same-named workflow on any branch, a fork's `pull_request` run included, started
   the credential-bearing job. That job downloaded and extracted the run's archive
   before admission refused it. Both admitted events resolve the trigger from the
   default branch, so an archive that reaches the extractor was built by protected
   code. CodeAnt read the archive as protected-built before that condition existed, and
   checking that reading against the job's own gate is what exposed the gap (#340).
   Admission still treats the archive as untrusted, because a candidate is not limited
   to what `upload-artifact` would produce: any step in a trigger job can upload
   through the artifact service directly. The pinned extractor (`download-artifact` v5.0.0) is past
   the zip-slip fix for CVE-2024-42471 (GHSA-6q32-hq47-5qq3, fixed in 4.1.7), so an
   entry cannot be written outside the download directory. Admission does not rest on
   that alone. It reads the payload without following a link, only as a regular file,
   and bounded at 4 KiB -- a real payload is about 150 bytes -- so a symlink cannot make
   it read a file of the candidate's choosing, a FIFO cannot hang it, and a large
   payload cannot exhaust it. It creates the request directory itself and refuses one
   that already exists, so nothing planted in its place can redirect the artefacts.
   Each is tested against its own attack, and each test was seen to fail with its
   control removed. The files are also opened `O_EXCL|O_NOFOLLOW`; that layer is
   untested, because with the directory freshly created it can only matter against a
   concurrent writer inside the job, which no test can stage and nothing in the job is.

8. **The trigger filters, and the reviewer runs only on a trigger that succeeded.**
   Both are efficiency controls, not admissions. The trigger's job runs only for a
   mention by a trusted association, so the review bots' many comments conclude as
   `skipped`; the privileged job runs only for a triggering run that concluded
   `success`. A successful conclusion admits nothing until the event has been
   re-established from the provider.

9. **Admission fails closed.** A payload that is missing, malformed, disagrees with what
   GitHub recorded, or names an object that cannot be read back is refused, with the
   reason on one line. An unavailable answer is not an admission, and partial provider
   coverage is not coverage -- the rule the current-state collector already applies.

10. **Decision 0094 rule 25a is superseded, not retained.** Its guard compared the
    workflow revision to the default branch from inside the workflow. With the relay
    the privileged workflow cannot be candidate-supplied at all, so the guard protects
    nothing that is still reachable, and keeping it would suggest the relay needs it.

11. **The protected checkout names no ref.** Decision 0094 rule 8 bound it to
    `github.workflow_sha`, the default-branch revision the run was bound to, because a
    ref-less checkout on the review triggers followed the candidate's merge ref. The
    relay's job runs only on `workflow_run`. There GitHub sets `github.ref` to the
    default branch and `github.sha` to the default-branch commit the run was created
    for, and a ref-less checkout fetches exactly `github.sha`: the same protected
    revision, still fixed at creation rather than resolved at execution. The named
    ref added only an expression, which SonarCloud (S7631) cannot tell from a fork's
    head in a privileged trigger, and which failed its quality gate on #340. A test
    pins the absence, together with the single `workflow_run` trigger it depends on.

12. **Withdrawn with the review events (rule 13).** It bounded the listing pages
    admission read to find the actor's latest review mention, and named the Git commit
    object as the way to confirm a submitted review's commit. No listing is read any
    more, and every provider answer is held to the 1 MiB single-object bound.

13. **The review events are withdrawn.** Owner decision on #339, 2026-10-01 (option
    (b) of three: accept the documented residual, withdraw the events, or keep
    hardening). For `pull_request_review` and `pull_request_review_comment` the trigger
    workflow is resolved from the Pull Request branch, so the Pull Request's author
    can edit it and choose which object the protected job re-reads. Admission had to
    bind that object to the event that really triggered the run, from evidence the
    candidate's trigger could influence. The bindings of rule 4 were each answered by
    a new way through, so the problem was the binding itself, not any one version of
    it. The trigger now admits `issue_comment` and `issues` only, both run from the
    default branch, and admission refuses any other recorded event. Consequence: a
    mention inside a pull-request review or an inline review comment no longer starts
    a review; a mention in the Pull Request's conversation still does. A test pins
    the trigger set, the refusal, and the absence of every value GitHub recorded only
    for the review events.

## What the relay does not establish

The relay closes the **workflow-revision** boundary: the credential-bearing reviewer can
no longer run a revision a candidate supplies. It does not close the **credential**
boundary, and an earlier draft of rule 2 said it did. Codex raised this on #340, and it
was verified against the repository:

- `CLAUDE_CODE_OAUTH_TOKEN` is a **repository** secret. GitHub makes repository secrets
  available to workflows run from any same-repository branch, whatever triggers them.
- *At the time,* `claude-code-review.yml` ran on `pull_request` and passed that secret
  to the candidate's own workflow revision on every same-repository Pull Request. That
  is the hole #339 describes, without needing a review event at all. Decision 0097 has
  since withdrawn that workflow.
- The only collaborator with write access is the owner. In practice the actors who can
  author a same-repository branch are the owner and the agents that push with the
  owner's credentials; a prompt-injected agent writing a workflow is the realistic case.

The boundary that holds is a credential that candidate-resolved workflows cannot reach:
the token as an **environment** secret, in an environment whose deployment branch policy
admits only the default branch. This repository already uses that pattern
(`analyzer-readback`: branch policy `main`). The relay is what makes that environment
usable for mention reviews: its privileged job runs on the default branch and so passes
the policy, while a candidate's trigger, whatever it is edited to say, does not.

So the relay is **necessary but not sufficient**. Completing the boundary needs two
things outside this change:

1. The owner moves the secret into such an environment. This is an account setting,
   and the value is unreadable to agents by design.
2. The automatic review is reworked, because on `pull_request` it would lose the
   secret. The same relay pattern applies.

Both were captured as #342. The owner selected scoping the credential and withdrawing
the automatic review; Decision 0097 records it and completes this boundary.

## Partial supersession of Decision 0094

Decision 0094's change context is unchanged -- the diff, the commit log, the
changed-file summaries, the `base/` bytes with their manifest, and their bounds. Its
request inputs are not: the request, title and item arrive
as separately bounded artefacts (rule 6 above), and review and inline-comment requests
are withdrawn (rule 13 above). These rules now hold through the relay:

| 0094 rule | Now established by |
|---|---|
| 4 -- the prompt forwards the request | admission writes `request/request`; the prompt sends the reviewer there first |
| 8 -- the checkout binds `github.workflow_sha` | a ref-less checkout of `github.sha`, the same revision under `workflow_run` (rule 11 above) |
| 9 -- no fork-controlled head | admission, from the provider's answer |
| 11 -- every admitted trigger is covered | admission's re-read of each of the two remaining events; the review events are withdrawn (rule 13 above) |
| 14, 17 -- inline location and original identity | withdrawn with inline review comments (rule 13 above) |
| 15 -- external item text is withheld | admission, judging the item's author separately from the mention's |
| 18 -- a submitted review's commit is the comparison head | withdrawn with submitted reviews (rule 13 above); the comparison is the live Pull Request (rule 5) |
| 19 -- every interpolated context is classified | tightened to identity values only |
| 21 -- no candidate tree in the credential job | structurally, because the job cannot be candidate-supplied |
| 25a -- refuse an unprotected workflow revision | superseded (rule 10 above) |

## Consequences

The exfiltration path is removed structurally rather than mitigated. The price, set by
rule 13, is that a mention inside an inline review comment or a submitted review body no
longer starts a review: such a request is made in the Pull Request's conversation
instead, where the relay's trigger runs from the default branch.

The cost is one more workflow and a re-validation step that must be treated as
security-critical. `workflow_run` runs do not attach checks to the Pull Request, which
Decision 0094 already accepted when it moved delivery off the Pull Request, but it does
make the run less discoverable. The relay adds one hop of latency.

## What this Decision does not change

It does not alter the change context the reviewer is given or its bounds -- the diff,
the commit log, the changed-file summaries and the `base/` bytes with their manifest,
as Decision 0094 sets them -- nor the publish path or the `base/` contract. It does change the request the reviewer receives: the
request, title and item arrive as separately bounded artefacts instead of prompt text
(rule 6), and a mention in a review or an inline review comment is no longer admitted,
so there is no inline location to forward (rule 13). It does not grant the reviewer any
new authority, and it does not make an agent review a human approval.
