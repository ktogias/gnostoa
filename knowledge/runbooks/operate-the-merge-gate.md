---
type: Runbook
title: Operate the merge gate
description: How Gnostoa's main branch is protected under MA0 Phase 1a. It records the identities, every GitHub and Codex setting with its read-back, the host's helpers, the normal merge procedure, break glass, and rotation and recovery.
status: draft
generated:
  by: anthropic/claude-opus-5-5
  at: "2026-10-08T02:40:00Z"
x-project-knowledge:
  id: kit.runbook.operate-the-merge-gate
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /decisions/0110-bind-every-merge-to-the-owner-s-approval-of-the-exact-head.md
---

# Operate the merge gate

Under MA0 Phase 1a, no actor can merge into `main` without the owner's approval,
except through break glass, which only the owner can use. That covers the
orchestrating agent, Amazon Q, any review bot and any developer, and GitHub enforces
it. GitHub keeps an approval across a push that leaves the diff unchanged, so
binding it to the exact head is the merge procedure's step until Phase 1b's required
check enforces it.
[Decision 0110](../decisions/0110-bind-every-merge-to-the-owner-s-approval-of-the-exact-head.md)
records why. The work items are #15, for MA0, and #398, for this record.

Everything below was read back on 2026-10-08 unless a step says otherwise.

## Preconditions

The gate depends on the identities, settings and host files below. Each was read back on 2026-10-08.

### Identities

| Identity | Kind | It does | It cannot | Credential |
|---|---|---|---|---|
| `ktogias` | the owner, the only admin and the only code owner | approves the exact head of a PR, which is the merge instruction; edits settings | approve a PR that it authored | the owner's own login; no token of it is on any agent host |
| `gnostoa-agent` | GitHub App, ID 5230694, installation 169050684, bot user `gnostoa-agent[bot]` (id 339367847) | pushes branches; commits under its bot identity; resolves review threads; dispatches and reads the analyzer readback; merges an approved PR | merge without the owner's approval; push to `main` | a private key on the agent host; one-hour installation tokens |
| `gnostoa-agent-user` | machine user (a real account, id 339381282), **Write** role here; it is a collaborator on this repository alone, which is what limits its token | opens PRs; posts review triggers | push any branch (ruleset 24640984); merge without the owner's approval (R-main); count as a code owner | a classic token with `public_repo` scope only, which **expires 2027-01-06**; that scope is account-wide, so the account is never added to another repository |
| `gnostoa-break-glass` | GitHub App, ID 5230732 | merges a PR that bypasses R-main, in an emergency only | bypass the classic protection or the CodeQL ruleset | a private key held **offline** by the owner, never on an agent host |

Why the work is split between two agent identities: Codex, Amazon Q and CodeAnt
skip PRs that a bot opened, and they ignore review requests a bot posts. Calibration
showed it (Verification). The machine user is therefore the PR author and the requester, and
the App does the rest.

### GitHub settings

#### The App `gnostoa-agent`

Created at <https://github.com/settings/apps/new>:
- **Homepage:** `https://github.com/ktogias/gnostoa`.
- **Webhook:** inactive.
- **Installable:** only on this account.
- **Installed:** on the selected repository `ktogias/gnostoa` only.

Repository permissions, as read back from the App's own `GET /app`:

| Permission | Access |
|---|---|
| Contents | write |
| Pull requests | write |
| Issues | write |
| Workflows | write |
| Actions | read |
| Checks | read |
| Commit statuses (`statuses`) | read |
| Code scanning alerts (`security_events`) | read |
| Metadata | read |
| Everything else, including Administration, Deployments, Environments and Secrets | none |

Its icon is the Gnostoa mark, which #399 adds to the repository (#397).

#### The App `gnostoa-break-glass`

Created the same way. It has Contents and Pull requests write, and Metadata read.
It is installed on `ktogias/gnostoa` only, and its icon is the break-glass mark.
Its private key is kept offline by the owner.

#### The machine user `gnostoa-agent-user`

1. **The account.** A separate GitHub account, with a separate address and 2FA. Its
   bio says it is the machine account of the agent, operated by `@ktogias`. GitHub's
   terms allow one free machine account per person.
2. **Access.** `ktogias` invited it to `ktogias/gnostoa` with the **Write** role,
   and it accepted. Read back: `role_name: write`.
3. **The token.** A classic token (<https://github.com/settings/tokens/new>) with
   **`public_repo`** only, expiring 2027-01-06. A fine-grained token cannot write
   to a personal repository on which its owner is only a collaborator.

#### CODEOWNERS

`.github/CODEOWNERS` begins with `* @ktogias`. So the owner is the only code owner,
and R-main's code-owner rule makes the owner's approval the only one that counts.

#### Rulesets

**R-main**, `main merge gate (MA0)` (24687961), active on `~DEFAULT_BRANCH`. Its
only bypass actor is `gnostoa-break-glass`, as an Integration with mode
`pull_request`. Its bypass list and rules, as the API returns them:

```json
{"conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
"bypass_actors": [
  {"actor_id": 5230732, "actor_type": "Integration", "bypass_mode": "pull_request"}
],
"rules": [
  {"type": "deletion"},
  {"type": "non_fast_forward"},
  {"type": "required_linear_history"},
  {"type": "pull_request", "parameters": {
    "required_approving_review_count": 1,
    "dismiss_stale_reviews_on_push": true,
    "require_code_owner_review": true,
    "require_last_push_approval": true,
    "required_review_thread_resolution": true,
    "require_extra_approval_for_unattributed_changes": true,
    "allowed_merge_methods": ["squash"],
    "required_reviewers": []
  }},
  {"type": "required_status_checks", "parameters": {
    "strict_required_status_checks_policy": true,
    "do_not_enforce_on_create": false,
    "required_status_checks": [
      {"context": "policy", "integration_id": 15368},
      {"context": "fast", "integration_id": 15368},
      {"context": "regression", "integration_id": 15368},
      {"context": "smoke", "integration_id": 15368}
    ]
  }}
]}
```

The other rulesets:

| Ruleset | Target | Bypass actors | Rules |
|---|---|---|---|
| `Only admins write branches` (24640984) | every branch except `main` | the admin role, and `gnostoa-agent` (Integration 5230694); both `always` | creation, update, deletion, non-fast-forward |
| `Only admins write tags` (24640985) | every tag | the admin role | creation, update, deletion, non-fast-forward |
| `Require CodeQL on main` (23699912) | `~DEFAULT_BRANCH` | none | code scanning: CodeQL, errors and high-or-higher security alerts |

**Who can read what.** The App reads each ruleset and its rules, but GitHub omits
`bypass_actors` from its read, as it does for anyone without Administration access.
The bypass lists above were read back with an admin-capable credential on
2026-10-08 (#15, 6050406535).

**Classic branch protection on `main`** stays in force until Phase 1b. The owner
read it back on 2026-10-08 (rule 81822439), since its settings come only from the
protection endpoint, which returns 403 to the App. It requires:
- a pull request, with no approvals required (R-main requires the approval);
- the four checks `policy`, `fast`, `regression` and `smoke` from GitHub Actions, on an up-to-date branch;
- conversations resolved;
- no bypass, administrators included ("Do not allow bypassing the above settings");
- no force pushes and no deletions.

It does not require signed commits, linear history (R-main does), deployments, or a
locked branch. As the App, `GET /repos/ktogias/gnostoa/branches/main` shows
`protected: true` and the four checks from app 15368, with
`enforcement_level: everyone`.

**Repository merge settings:** squash only, auto-merge off, and branches deleted on
merge. A squash commit takes its title from the PR's title, or from its one commit's
(`squash_merge_commit_title: COMMIT_OR_PR_TITLE`), and its message from the commits'
messages (`squash_merge_commit_message: COMMIT_MESSAGES`).

#### What the owner's own tokens look like now

The owner revoked the agents' former fine-grained PAT, and the unused comment-only
PAT, on 2026-10-08. The host's default `gh` credential now fails with 401 by design:
an agent command that forgets to name an identity stops instead of acting as the
owner.

### Codex and the review bots

- **Codex** (<https://chatgpt.com>, in Settings, "Code review"). A review is
  requested by an `@codex review` comment.
  - Codex accepts that comment from `gnostoa-agent-user` (calibrated on #396). It
    refuses the App's: "create a Codex account and connect to github".
  - When the machine user opened #400, the connector also answered "To use Codex
    here, create an environment for this repo", and then reviewed the machine
    user's `@codex review` (its summary says "Manual request"). So the review ran
    without an environment.
  - The owner connected the machine user under ChatGPT's GitHub connector
    ("Connect another account"), as a second account beside the owner's. The
    owner confirmed it on 2026-10-08.
- **Amazon Q:** reviews a new PR, and again on the exact text `/q review` from the
  machine user. It ignores the App's comments. Never post any other `/q` text, since
  that can make it commit.
- **CodeAnt:** skips PRs that a bot opened, and answers `@codeant-ai: review` from
  the machine user.
- **The Claude review relay** admits an `OWNER`, `MEMBER` or `COLLABORATOR` comment.
  The machine user is a `COLLABORATOR` and needs no change; the App is not admitted.
- **Others** (Sourcery, cubic, Greptile, CodeRabbit, Kody, CodeReviewBot.ai) review
  automatically within their quotas. A quota-limited reviewer counts only when it is
  available.
- **Approvals by bots** (for example Sourcery's APPROVED) do not satisfy R-main,
  which requires the code owner. A push dismisses them as stale.

### The agent host

| Path | What it is | Mode |
|---|---|---|
| `~/.config/gnostoa-agent/private-key.pem` | `gnostoa-agent`'s private key | `0600` |
| `~/.config/gnostoa-agent/machine-user-token` | `gnostoa-agent-user`'s classic token | `0600` |
| `~/.config/gnostoa-agent/bin/agent-jwt.sh` | prints a nine-minute App JWT, signed with `openssl` (RS256) | `0700` |
| `~/.config/gnostoa-agent/bin/agent-token.sh` | prints a one-hour installation token for `ktogias/gnostoa` only: it sends the JWT with `curl` and reads the token from the response with `python3` | `0700` |
| `~/.config/gnostoa-agent/bin/agent-git.sh` | runs `git` with the App's token through a credential helper; it blanks the inherited helpers, so no token is ever on a command line or in output | `0700` |

The procedure needs `gh`, `git`, `jq`, `curl`, `openssl`, `python3`, `cat`, `cmp`, `rm` and
`mktemp` on the fixed system path below, besides the system's `/usr/bin/env` and
`/bin/sh`. `jq` runs in the calling shell, from the host's trusted `PATH`, and reads
the list of reviews outside the guarded body, so it never holds a token.

**Temporary debt.** `as_app`, `as_machine_user`, break glass's isolated shell and the
`gh api`/`jq` steps below are Phase-1a operational procedures, not a permanent API,
trusted-execution, observation or gate engine. They are consumed or replaced when
their owners land: trusted execution by #369, which is not yet integrated, and the
GitHub calls, observations and merge admission by Phase 1b's canonical adapter
(Decision 0110, "Successor: Phase 1b"). Until then, their safety invariants hold as
written here.

**Rules on the host:**
- A token is never printed, logged or passed on a command line. It is captured into
  `GH_TOKEN` inside one of the functions below, for one `gh` command, and never with xtrace (`set -x`) on, nor in a recorded
  session: under xtrace, the shell prints the command as expanded, token included.
- The host's `PATH` is trusted. It resolves every program that holds a token or the App's key: `gh`,
  `git`, `cat`, `curl`, `openssl` and `python3`. A host whose `PATH` cannot be
  trusted is compromised (Recovery).
- `gh` runs only through two functions, defined once per shell: `as_app` acts as
  the App, and `as_machine_user`, for review triggers, as the machine user. Each
  body is a subshell. It makes an empty configuration directory first, so no program
  but `gh` runs while the token is set. A failed or empty mint stops it before `gh`,
  rather than letting `gh` fall back to a stored login, as a `gh` command prefixed
  with a captured token would.
  The token never exists in the calling shell, even when a command is interrupted.
  Each body runs in a fresh `/bin/sh`, started by absolute path through `env -i`,
  which passes on only `HOME` and `TMPDIR`, and sets `PATH` to AGENTS.md's fixed
  system path, so no entry of the caller's `PATH`, such as a writable virtualenv or
  `.`, is searched. A name with a slash is never
  looked up as a function, so no function, alias or variable of the calling shell
  reaches the body: not a `gh`, `test`, `mktemp` or even `command` function, not
  `GH_HOST`, `GH_REPO` or `GH_DEBUG`, and not a read-only `GH_CONFIG_DIR`. Inside
  the fresh shell, nothing can shadow anything, so the body needs no `command`
  prefix. The calling shell itself, which defines and calls these functions, is
  trusted: a hostile shell could redefine the functions themselves. The body traps the same signals as AGENTS.md's preparation helper,
  `HUP` included. On exit, by any path, it unsets the token and then removes the
  directory `mktemp` made, with whatever `gh` wrote there. That directory is held
  in `created` before the clean-up is set, so nothing else is removed. Define them again after any change to this section, since a
  shell keeps the definitions it already has:
  ```sh
  as_app() {
    /usr/bin/env -i PATH=/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin \
      HOME="$HOME" TMPDIR="${TMPDIR:-/tmp}" /bin/sh -c '
      cleanup() { unset GH_TOKEN; rm -rf -- "$created"; }
      trap "exit 130" INT
      trap "exit 143" TERM
      trap "exit 129" HUP
      created=$(mktemp -d) || exit
      trap cleanup EXIT
      GH_CONFIG_DIR=$created && export GH_CONFIG_DIR \
        && GH_TOKEN=$(~/.config/gnostoa-agent/bin/agent-token.sh) \
        && test -n "$GH_TOKEN" && export GH_TOKEN && gh "$@"
    ' as_app "$@"
  }
  as_machine_user() {
    /usr/bin/env -i PATH=/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin \
      HOME="$HOME" TMPDIR="${TMPDIR:-/tmp}" /bin/sh -c '
      cleanup() { unset GH_TOKEN; rm -rf -- "$created"; }
      trap "exit 130" INT
      trap "exit 143" TERM
      trap "exit 129" HUP
      created=$(mktemp -d) || exit
      trap cleanup EXIT
      GH_CONFIG_DIR=$created && export GH_CONFIG_DIR \
        && GH_TOKEN=$(cat ~/.config/gnostoa-agent/machine-user-token) \
        && test -n "$GH_TOKEN" && export GH_TOKEN && gh "$@"
    ' as_machine_user "$@"
  }
  ```
- Every helper and the token file are named by their full path, so they work from
  any directory, including an agent's isolated clone.
- Commits in an agent's clone are authored by
  `gnostoa-agent[bot] <339367847+gnostoa-agent[bot]@users.noreply.github.com>`, and
  pushed with
  `~/.config/gnostoa-agent/bin/agent-git.sh push https://github.com/ktogias/gnostoa.git HEAD:<branch>`.
- The repository's activity log shows who pushed. Read it, rather than trusting a
  push that merely succeeded: both the admin and the App can write branches.

Versioning these helpers as repository tools is a follow-up (#398's scope boundary).

## Procedure

### The normal merge

1. **Branch and commits.** The agent works in an isolated clone and commits as
   `gnostoa-agent[bot]`. It pushes the branch with
   `~/.config/gnostoa-agent/bin/agent-git.sh`.
2. **The PR.** The machine user opens it (`gh pr create` with its token). Never open
   a PR as the owner: the owner could not approve it.
3. **The seal.** The App posts `Exact review candidate: <40-hex head>`.
4. **Reviews.** The machine user posts `@codex review`, `@codeant-ai: review`, the
   Claude request and `/q review`.
5. **Rounds.**
   - Each finding gets its own reply: fixed with its commit, or declined with
     evidence. Only the threads replied to are resolved.
   - Every fix is a new head, so a new seal and new review requests follow.
   - The pre-merge check and the exact-head analyzer readback must both be clean:
     `BOUND`, every analyzer `COMPLETE`, 0 findings.
   - The pre-merge check is `premerge-check.sh`, a script in the agent's session
     workspace, not yet versioned; versioning it with the host's helpers is #398's
     follow-up. Until then, an agent without it checks the same, on the exact head:
     - the seal names the exact head;
     - every required check succeeded, by its latest run;
     - every other check run and status is green, and a green one carries no
       annotation or analyzer finding;
     - every review thread is resolved, read through every page;
     - no closing keyword is in what the squash merge will carry, nor in the PR's
       description. The check writes the PR's title and body, as it read them, to two
       files that step 8 compares with. A read that fails stops the check:
       ```sh
       as_app pr view <N> --json title --jq .title > <checked-subject>
       as_app pr view <N> --json body --jq .body > <checked-body>
       ```
6. **The convergence report.** The App posts it on the PR. It covers:
   - the seal;
   - the required checks;
   - the readback;
   - SonarCloud and Codacy;
   - the threads;
   - each available reviewer's verdict on the head;
   - each unavailable reviewer, quoting its text.
7. **The owner's approval.** The owner reviews and clicks **Approve** in GitHub on
   that exact head. A later push that changes the diff dismisses the approval, and a
   move of `main` makes the branch out of date. Either needs a new approval. A push
   that leaves the diff unchanged may keep it, which step 8 checks.
8. **The merge.** The App merges the SHA the owner approved, never just the PR's
   current head. `--match-head-commit` only checks the SHA it is given against the
   head, and a push that leaves the diff unchanged may not dismiss an approval. So
   `<approved>` is the `commit_id` of the owner's latest `APPROVED` review, which
   must also be the owner's latest review and equal the sealed head. Every page
   is read first (`--slurp`), since `--jq` with `--paginate` runs once per page and
   could choose a page's last review instead of the latest:
   ```sh
   as_app api repos/ktogias/gnostoa/pulls/<N>/reviews --paginate --slurp \
     | jq -r '[.[][] | select(.user.login == "ktogias")] | last | select(.state == "APPROVED") | .commit_id'
   ```
   Then it reads the PR's head, and compares the PR's title and body with the files
   the pre-merge check wrote. The title and description can be edited without moving
   the head, and they are untrusted text, so they pass only through files, never a
   command line. Each comparison runs only on a read that succeeded, since an empty
   file is not an empty title:
   ```sh
   as_app pr view <N> --json headRefOid --jq .headRefOid
   as_app pr view <N> --json title --jq .title > <current-subject> && cmp -s <current-subject> <checked-subject>
   as_app pr view <N> --json body --jq .body > <current-body> && cmp -s <current-body> <checked-body>
   ```
   Stop unless `<approved>`, the PR's head and the seal are one SHA, and both
   comparisons succeed. GitHub closes an issue that a closing keyword in the
   description names when the PR merges, whatever the squash message says. Only then
   does the App merge:
   ```sh
   as_app pr merge <N> --squash --match-head-commit <approved>
   ```
   The squash commit's message is the commits' messages, and its title the PR's title
   or its one commit's (Preconditions): `<approved>` binds the commits, and the
   comparison binds the title. No provider gate
   yet checks the approval's `commit_id` against the merged head: the platform keeps
   an approval across a push that leaves the diff unchanged. This step is that check
   until Phase 1b's required `merge-admission` check enforces it.
   GitHub refuses unless R-main, the classic protection and the CodeQL ruleset all
   hold. There is no `--admin`, because the App is not a bypass actor of R-main.
9. **After the merge.** A squash merge makes a new commit, so it cannot equal the
   PR's head. The agent checks two things instead. First, that the PR's recorded
   head equals `<approved>`, and reads the new commit `<merge>`:
   ```sh
   as_app pr view <N> --json headRefOid,mergeCommit --jq .headRefOid
   as_app pr view <N> --json headRefOid,mergeCommit --jq .mergeCommit.oid
   ```
   The first prints the PR's recorded head, the second `<merge>`. Second, that
   `<merge>` integrated that head. The branch was up to date with `main`, so the two
   trees are one. If the trees differ, stop: the squash carries something the owner
   did not approve. Record it on the Work Item and tell the owner:
   ```sh
   as_app api repos/ktogias/gnostoa/commits/<merge> --jq .commit.tree.sha
   as_app api repos/ktogias/gnostoa/commits/<approved> --jq .commit.tree.sha
   ```
   It records the outcome on the Work Item. A Work Item that
   survives the merge was only referenced (`Refs`, never a closing keyword).

### Break glass

**When.** Only when the normal procedure is impossible, not merely slow. For
example:
- An urgent fix must merge, and the owner's approval cannot be given. One case is a
  PR that the owner authored.
- Convergence cannot be reached for a reason outside the change, such as a broken
  reviewer.

Break glass is never for skipping a review that is late, or a finding nobody wants
to fix. A review thread is never the reason either: the owner can resolve any
thread, with the reason in a reply.

**What it bypasses: only R-main.** That means the code-owner approval and the
last-push approval. R-main's thread resolution and checks duplicate the classic
protection's, which still apply.

**What it does not bypass:**
- the classic protection, which still requires the four checks and resolved
  conversations, and whatever else it requires (Preconditions), so an emergency PR's
  threads are resolved first, each with its reason;
- the CodeQL ruleset.

If a required check itself is broken, break glass does not suffice while the classic
protection exists. The last resort is then the owner, as admin:
1. Read back the whole protection before changing it,
   `GET /repos/ktogias/gnostoa/branches/main/protection`, and keep the result.
2. Remove only the broken check from it, for the one merge. The security log
   records the change. R-main still requires the check of every normal merge, so
   only another break-glass merge could skip it; even so, hold every other merge until
   step 4: tell the agents to stop merging. After step 4, read the activity log for the window, and record any
   other merge in that window in the follow-up, for review.
3. Merge, as below.
4. Restore the protection at once, whether the merge succeeded or not: re-enter the
   settings step 1 read back, in Settings → Branches → the `main` rule, not only the
   four checks. They are re-entered by hand, since a read-back is not a body to send
   back: the endpoint's answer carries read-only fields that its update does not take.
   Read it back again, and repeat until the new read-back equals step 1's. If step 1's
   read-back differs from what Preconditions records, record the drift and update
   Preconditions in the follow-up. After an interrupted session, restoring it is the
   first thing done.
5. Record both changes, and both read-backs, in the follow-up.

**How.** Only the owner does it, and no agent ever holds the key:
1. Bring the offline key of `gnostoa-break-glass` (App ID 5230732) to a trusted
   machine.
2. Have a minting script there, at an absolute path, here
   `~/break-glass/break-glass-token.sh`. The owner writes it on that machine, from
   GitHub's own documentation, and it is never copied from the agent host, which may
   be the compromised one. It does three things:
   1. It signs a JWT with the offline key, as
      [Generating a JSON Web Token (JWT) for a GitHub App](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-json-web-token-jwt-for-a-github-app)
      describes: RS256, `iat` 60 seconds in the past, `exp` at most ten minutes on,
      and `iss` the App ID 5230732.
   2. With that JWT as its bearer, it finds the App's installation with
      `GET /repos/ktogias/gnostoa/installation`.
   3. It requests a token with
      `POST /app/installations/<installation>/access_tokens` and the body
      `{"repositories": ["gnostoa"]}`, as
      [Generating an installation access token for a GitHub App](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app)
      describes, and prints only the response's `token`, for capture.

   The token lasts one hour.
3. Read back the classic protection, as the owner, before the merge:
   `GET /repos/ktogias/gnostoa/branches/main/protection`. Once break glass bypasses
   R-main, it is the only layer that still requires the four checks. It must
   require them, as Preconditions records (`policy`, `fast`, `regression` and
   `smoke` from app 15368, strict, with `enforcement_level: everyone`), except in the
   last resort, where it must differ from Preconditions by exactly the check the
   owner removed. Any other difference: stop, and restore it to require the four
   checks, as Preconditions records, before going on.
4. Merge the exact head, capturing the token for this one command, with xtrace off
   and outside any recorded session. Run the script by its absolute path, never a
   relative one, so that no same-named script in the current directory runs while
   the key is present. The command line and the shell's history then hold `$(...)`,
   never the token. `<head>` is the head the owner has just reviewed, read from
   `GET /repos/ktogias/gnostoa/pulls/<N>` (`head.sha`) and recorded in the
   follow-up; GitHub refuses the merge if the head has moved since. The owner then
   reads its commits' messages from `GET /repos/ktogias/gnostoa/pulls/<N>/commits`,
   and last, just before the merge, reads `GET /repos/ktogias/gnostoa/pulls/<N>` again.
   The owner stops unless that read's `head.sha` is still `<head>`, and stops if the
   commits' messages, or that read's `title` or `body`, carry a closing keyword.
   GitHub closes an issue that one names in the description, and the repository
   builds the squash commit from the commits' messages and its title from the PR's
   title or its one commit's (Preconditions). `<head>` binds the commits but not the
   title or the description, so those are read last. Each step runs
   only if the one before succeeded, and `gh` runs
   with an empty configuration directory, made before the mint so that no other
   program runs while the token is set. So a failed or empty mint stops the merge
   instead of letting `gh` fall back to a stored login, which would merge as the
   owner rather than as `gnostoa-break-glass[bot]`. The block runs in a fresh
   `/bin/sh`, as the two functions do, so the token never exists in the interactive
   shell, and nothing of the owner's shell reaches it. Interrupting it, for example
   with Ctrl-C, cannot leave the token behind. The block's status is the merge's, so
   a failure is not reported as success:
   ```sh
   /usr/bin/env -i PATH=/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin \
      HOME="$HOME" TMPDIR="${TMPDIR:-/tmp}" /bin/sh -c '
     cleanup() { unset GH_TOKEN; rm -rf -- "$created"; }
     trap "exit 130" INT
     trap "exit 143" TERM
     trap "exit 129" HUP
     created=$(mktemp -d) || exit
     trap cleanup EXIT
     GH_CONFIG_DIR=$created && export GH_CONFIG_DIR \
       && GH_TOKEN=$(~/break-glass/break-glass-token.sh) && test -n "$GH_TOKEN" \
       && export GH_TOKEN && gh api -X PUT \
       repos/ktogias/gnostoa/pulls/<N>/merge -f merge_method=squash -f sha=<head>
   ' break-glass
   ```
5. Remove the key from the machine.

**After.**
- Open the emergency follow-up Work Item and Decision that
  `policy/change-control.yaml` requires (`emergency.decision_record`). They name the
  PR, the reason, and what was not verified.
- The merge shows `gnostoa-break-glass[bot]` as its actor in the activity log, so it
  is auditable.
- The owner adds the merge to a record kept offline with the key: the date, the PR,
  the head merged and the merge commit. No agent identity can edit it, so a later
  compromise audit checks break-glass merges against it, since such a merge carries
  no approval.
- MA0 Phase 1b's post-merge audit will open this Work Item by itself, for any merge
  whose head lacked a green `merge-admission`.

## Verification

### What calibration showed (2026-10-08)

| Check | Result |
|---|---|
| The App creates and deletes a branch | allowed (`calibration/agent-push`; the activity log shows `gnostoa-agent[bot]`) |
| The App merges an unapproved PR (#395) | refused: "base branch policy prohibits the merge" |
| The App merges it with `--admin` | refused: "Waiting on code owner review from ktogias" |
| The machine user creates a branch | refused (422) |
| Codex, Amazon Q or CodeAnt on an App-authored PR, or on an App's trigger | none reviewed, or each refused (Codex and the review bots) |
| Codex, Amazon Q, CodeAnt and the Claude relay on the machine user's PR and triggers | all reviewed (#396) |
| A fine-grained PAT with Issues: write comments on a PR | refused (403); it would need Pull requests: write, which also allows approval |

### Re-verify the gate

After any change to an identity, a permission or a ruleset, and before relying on
the gate:
1. Read back each App's `GET /app` with its own JWT.
2. Read back the installation with `GET /repos/ktogias/gnostoa/installation`.
3. Read back each ruleset with `GET /repos/ktogias/gnostoa/rulesets/<id>`. The App
   reads the rules; GitHub omits `bypass_actors` for it, so the owner reads the
   bypass lists.
4. Read back the classic protection. As the App, `GET /repos/ktogias/gnostoa/branches/main`
   shows its required checks; as the owner,
   `GET /repos/ktogias/gnostoa/branches/main/protection` shows the rest.
5. Read back the machine user's `GET /user`, its `x-oauth-scopes` header, and its
   expiry in the `github-authentication-token-expiration` header.
6. As the App, read an unapproved PR's merge state with GraphQL:
   `mergeStateStatus` must be `BLOCKED`, `reviewDecision` `REVIEW_REQUIRED`, and
   `viewerCanMergeAsAdmin` `false`. No merge is attempted, since a weakened gate would
   let the attempt merge.

## Recovery

| Event | Action |
|---|---|
| The machine user's token approaches **2027-01-06** | The owner, signed in as the machine user, notes the old token's creation date in the owner's offline record of rotations first, then creates a new classic token (`public_repo`), writes it to `~/.config/gnostoa-agent/machine-user-token`, and revokes the old one. |
| The agent host may be compromised | Suspend the installation of `gnostoa-agent` first (its installation settings → Suspend). A token the host already minted would otherwise stay valid for up to an hour. Then record the compromised credential's creation date before revoking it, since revoking erases it: the App key's, in App settings → Private keys, and the machine user's token's, in its token settings. Then revoke its private key and the machine user's token. Generate a new key, and a new token, only for a clean host. Before unsuspending, audit every merge into `main` since the earliest suspected exposure; when that is unknown, since the earliest credential the compromised host or key could have held, across rotations, as the owner's offline record of rotations shows, since a routine rotation on a compromised host does not end the exposure. A "last good merge" is no anchor, since a compromise can predate it. For each merge, read its actor in the activity log; the owner's latest review on that PR must be `APPROVED`, its `commit_id` the PR's recorded head, and the integrated tree that head's, as the normal merge's steps 8 and 9 require, since an older approval can stand beside a later request for changes. A merge by `gnostoa-break-glass[bot]` carries no approval, so it passes only if the owner's offline record of each break glass names it, with its head and merge commit. Record any merge that fails a comparison, or that the owner did not approve, in the follow-up, for revert or disposition. Unsuspend the installation only after reading it back, and at least an hour after suspending it, when any token minted before has expired. |
| The App's key is rotated on schedule | Note the old key's creation date in the owner's offline record of rotations first, then generate a new key, install it at the same path, and delete the old key in the App's settings. |
| The break-glass key is lost or exposed | Suspend the installation of `gnostoa-break-glass` first (its installation settings → Suspend). That stops the App acting at once, including through a token already minted, which would otherwise stay valid for up to an hour. Then record the compromised credential's creation date before revoking it, since deleting it erases it: the key's, in App settings → Private keys. Then delete the key, and generate a new one offline. The App bypasses R-main, so a stolen key may already have merged: audit every merge into `main` since the earliest suspected exposure; when that is unknown, since the earliest credential the compromised host or key could have held, across rotations, as the owner's offline record of rotations shows, since a routine rotation on a compromised host does not end the exposure. A "last good merge" is no anchor, since a compromise can predate it. For each merge, read its actor in the activity log; the owner's latest review on that PR must be `APPROVED`, its `commit_id` the PR's recorded head, and the integrated tree that head's, as the normal merge's steps 8 and 9 require, since an older approval can stand beside a later request for changes. A merge by `gnostoa-break-glass[bot]` carries no approval, so it passes only if the owner's offline record of each break glass names it, with its head and merge commit. Any merge by `gnostoa-break-glass[bot]` that the owner did not make, or that fails a comparison, is recorded in the emergency follow-up, for revert or disposition. Then read the installation back, and only then unsuspend it, at least an hour after suspending it, when any token minted before has expired. |
| A reviewer changes whom it accepts | Run the calibration again (Verification), and record the result here. |
| An identity, permission or ruleset changes | Read it back, and update Preconditions and Verification in the same change. |
