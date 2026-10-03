---
type: Decision
title: Post Claude reviews from a least-privilege job, and keep write credentials out of the reviewer
description: Give the reviewer job only its own read-only token, so no write-capable App token reaches the model, and deliver each finished review as a comment in the thread it was requested in, from a separate job that runs no model and holds one write scope.
status: draft
generated:
  by: anthropic/claude-opus-5-5
  at: "2026-10-02T20:00:00Z"
sources:
  - id: credential-work-item
    resource: https://github.com/ktogias/gnostoa/issues/352
    title: Keep a write-capable token out of the job that runs the Claude reviewer
  - id: delivery-work-item
    resource: https://github.com/ktogias/gnostoa/issues/348
    title: Deliver Claude mention reviews where they were requested, and machine-readably
  - id: owner-admission
    resource: https://github.com/ktogias/gnostoa/issues/352#issuecomment-5959472829
    title: Owner selects both, together
  - id: harden-actions
    resource: ./0093-harden-claude-code-github-actions-workflows.md
    title: Harden the Claude Code GitHub Actions workflows before integration
  - id: bound-context
    resource: ./0094-bound-claude-review-context.md
    title: Bound Claude review context
  - id: relay
    resource: ./0096-relay-mention-reviews-through-a-protected-workflow.md
    title: Relay mention reviews through a protected workflow revision
  - id: pwn-requests
    resource: https://securitylab.github.com/resources/github-actions-preventing-pwn-requests/
    title: "GitHub Security Lab: Keeping your GitHub Actions and workflows secure, part 1"
x-project-knowledge:
  id: kit.decision.0098.post-claude-reviews-from-a-least-privilege-job
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0093-harden-claude-code-github-actions-workflows.md
    - kind: governed-by
      target: /decisions/0094-bound-claude-review-context.md
    - kind: governed-by
      target: /decisions/0096-relay-mention-reviews-through-a-protected-workflow.md
---

# Post Claude reviews from a least-privilege job, and keep write credentials out of the reviewer

## Context

Two problems surfaced in the live verification of the relay on 2026-10-02.

**The review reached no one** (#348). Decision 0094 accepted that delivery is no
longer on the Pull Request: agent mode has no comment tool, and Decision 0093 rule 4
keeps `GITHUB_TOKEN` read-only, so the report went only to the run's step summary.
GitHub has no API for job summaries. Measured on live run 37042164980, the summary
answered 404 both anonymously and with a token. So a requester had to open the run, and
no agent or CLI could read the answer at all.

**The reviewer held a write-capable token anyway** (#352). This was verified in the
pinned action at `anthropics/claude-code-action@9171db3e`. With `id-token: write` and
no `github_token`:

- The action exchanges OIDC for a Claude GitHub App installation token, requesting
  `contents`, `pull_requests` and `issues` **write** (`src/github/token.ts`).
- Agent mode writes that token into the checkout's `.git/config` as the remote URL
  (`src/github/operations/git-config.ts:132-133`).
- It also exports the token into the Claude CLI's environment.
- The workflow's deny rules did not cover the workspace's `.git/**`.

Decision 0093 had recorded that "the App token remains write-capable by upstream
design" and relied on the actor and association gates. Those gates decide who may
*start* a review. They do nothing about a model that, steered by content it reviews,
copies a token it can read into the report it publishes.

## Prior-art and reuse disposition

| Need | Prior art | Disposition |
|---|---|---|
| produce unprivileged, publish from a separate privileged step | `.github/workflows/review-current-state.yml`: a read-only `collect` job, an artifact, and a `publish` job with only `pull-requests: write` | **reused** as the pattern |
| the pattern's rationale and limits | GitHub Security Lab, *Preventing pwn requests*: artifacts derived from untrusted data are themselves untrusted | **followed** |
| report extraction and fencing | `.github/review-context/publish_report.py` | **extended** with a handoff |
| redaction of credential shapes | the pinned action's `src/github/utils/sanitizer.ts` (MIT) | **consulted**; its patterns are re-expressed, not imported |
| skipping the App-token exchange | the action's own `github_token` input (`OVERRIDE_GITHUB_TOKEN`) | **reused** |

## Decision

1. **The reviewer job holds no write-capable credential.** The action is given the job's
   own read-only token (`github_token: ${{ github.token }}`), which skips the OIDC
   exchange entirely. `id-token: write` is removed, and `additional_permissions` with it,
   since only the exchange read it. The action's write-permission check still passes on
   that token: measured live, `GET .../collaborators/{actor}/permission` answered HTTP
   200 with `admin` for a read-only `GITHUB_TOKEN`. The reviewer's deny rules now also
   cover `**/.git/**`, in depth.

2. **No grant names a tool that cannot exist.** Under `workflow_run` the action never
   installs its CI server, which needs an entity event on a Pull Request
   (`src/mcp/install-mcp-server.ts`). The three `mcp__github_ci__*` grants are removed.

3. **The report crosses jobs as an artifact, and the identities do not.** The reviewer's
   publisher writes the bounded report and its status (`complete`, `incomplete` or
   `unavailable`) to a handoff directory, uploaded as `claude-review-report` for one day.
   The status is the commit record. It is written last, after the whole report, and
   it states whether the report was cut, because sanitising can shrink a cut report
   below any length that would show the cut.
   The upload happens only once admission has resolved an item. The item, the Pull
   Request, the reviewed revision and the reviewer's outcome reach the posting job as
   **job outputs from admission and from the action step**, never through the artifact,
   which the model wrote.

4. **A finished review is posted from a least-privilege job, one per kind of item.**
   `post-to-pull-request` holds `pull-requests: write`, and `post-to-issue` holds
   `issues: write`, each with `contents: read` and nothing else. Each job:
   - runs only after the reviewer job and only from the default branch;
   - runs no model, names no environment and references no secret;
   - checks out the protected revision without persisting credentials;
   - posts with `.github/review-context/post_report.py`, as `github-actions[bot]`.

   A comment made with `GITHUB_TOKEN` starts no workflow run, so a posted review cannot
   re-trigger the relay. Its author association is not one admission admits either:
   `CONTRIBUTOR` or `NONE`, never `OWNER`, `MEMBER` or `COLLABORATOR`.

5. **What is posted is rendered from trusted facts and neutralised text.** The handoff is
   read as untrusted: through a directory confined by the shared `within`, without
   following links, as bounded regular files. Outside the fence go only the run's URL,
   the reviewed revision and the notices the script writes itself. Inside it:
   - the text sits in a fence no line can close, with backtick runs over eight capped;
   - every mention's at-sign becomes U+FF20, so no one is pinged and no bot acts on a
     raw-text match;
   - bidirectional, zero-width and control characters become visible escapes;
   - credential shapes are redacted and the redaction is stated, because a comment,
     unlike a step summary, is not masked. Shapes are matched across invisible
     characters, so a token split by one is redacted rather than escaped into view.
     A match runs on to the end of its word, with no word boundaries, so two tokens
     written back to back cannot leave a secret part behind.
     This catches disclosure, not a deliberate encoder. A text that spells a secret
     out evades any pattern, and the control against that is rule 1;
   - the whole body stays under the provider's 65,536-character limit.

   Every identity the script posts with is validated first: the repository, the item
   number, the revision, and a run URL of this repository.

6. **One new comment per request, not a sticky one, and never two.** A sticky comment
   would race without a concurrency group (Decision 0093 rule 6). Under the shared
   `github-actions[bot]` identity it could be overwritten, and it would lose the
   per-request record.

   Creating a comment is not idempotent. A timeout or a 5xx can arrive after the
   provider created it. So every body starts with a marker for the run and its
   attempt. Before any retry, the item is read back for a comment by
   `github-actions[bot]` that starts with that marker: by that author only, since
   anyone may comment a copy of it. When the read-back fails, the job fails rather than
   posting again. A missing comment is visible as a failed job; a duplicate is not.

7. **A failure is answered; a refusal is not.** When the reviewer fails after admission,
   the posting job posts a notice with the run's link. A refused request gets no comment,
   because a refusal may answer a request nobody should be able to cause a public
   reply to.

## Partial supersession of Decisions 0093 and 0094

| Rule | Now |
|---|---|
| 0093 rule 4: workflow token read-only plus `id-token: write` | The reviewer job is read-only **without** `id-token` (rule 1 above). `GITHUB_TOKEN` write is admitted only in the posting jobs, which run no model and hold no secret (rule 4 above). |
| 0093 Consequence: the App token remains write-capable | No App token is obtained (rule 1 above). |
| 0094 *Accepted trade: delivery is no longer on the Pull Request* | Withdrawn: the review is delivered in its thread (rule 4 above), and the step summary remains. |
| 0094 rule 22: the report is published with render-time fetches removed | Extended to comments (rule 5 above). |

Decisions 0096 and 0097 are unchanged. The posting jobs never name the `claude-review`
environment, so the credential reaches the reviewer job alone.

## Consequences

- A mention's review appears in the issue or Pull Request where it was asked, as
  `github-actions[bot]`. The step summary still holds it, rendered for the run's reader.
- The comment shows the report as literal monospace text, and its mentions are
  neutralised. Headings and `file:line` references are not rendered, the cost Decision
  0094 already accepted for the summary.
- A workflow file now holds `GITHUB_TOKEN` write scope, which Decision 0093 had kept out.
  It is confined to jobs that execute only this repository's default-branch scripts on
  untrusted text, never untrusted code.

## Verification

`tests/test_claude_actions_workflows.py` pins:

- the reviewer job's exact permissions, its `github_token`, and its `.git/**` deny
  rules;
- the absence of `additional_permissions` and of the CI grants;
- the posting jobs' exact permissions, dependency, guards and pinned actions, with no
  environment, secret or credential-persisting checkout;
- the rendering: a fence, neutralised mentions, escaped invisible characters, stated
  redaction (including a token split by invisible characters), worst-case size, and only
  trusted facts outside the fence;
- the poster's refusals: a symlinked handoff and invalid identities;
- the retry: a lost response, a 5xx after creation and a refused connection each leave
  one comment; a planted marker is ignored; a failed read-back posts nothing more.

Live, after merge: a mention is answered by a comment from `github-actions[bot]` in the
same thread, and that comment starts no relay run.
