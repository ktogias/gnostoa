---
type: Decision
title: Confine every branch and tag write to repository administrators
description: Two repository rulesets let only the repository admin role create, update, force-push or delete any branch or tag, so an installed app with write access, such as Amazon Q Developer, cannot place unreviewed code or workflows on any ref, or merge into main. Records the measured app permissions, the controls that already held, the gap they left, the rulesets and their verification.
status: draft
generated:
  by: anthropic/claude-opus-5-5
  at: "2026-10-07T09:42:00Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/383
    title: Record the rulesets that confine ref writes to repository administrators
  - id: app-permissions
    resource: https://api.github.com/apps/amazon-q-developer
    title: The Amazon Q Developer GitHub App's permissions and events
  - id: q-for-github
    resource: https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/amazon-q-for-github.html
    title: Amazon Q Developer for GitHub (Preview), its agents and slash commands
  - id: q-code-reviews
    resource: https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/github-code-reviews.html
    title: Reviewing code with Amazon Q Developer in GitHub, with its role prerequisite
  - id: q-configuration
    resource: https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/github-configuration.html
    title: Configuring registered installation details, which cannot change feature development
  - id: q-troubleshooting
    resource: https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/github-troubleshooting.html
    title: Branch protection rules prevent Amazon Q from creating a branch
  - id: suggested-changes
    resource: https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/reviewing-changes-in-pull-requests/incorporating-feedback-in-your-pull-request
    title: The person who applies a suggested change is the commit's committer
  - id: ruleset-rules
    resource: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets
    title: What each ruleset rule refuses to anyone without bypass permission
  - id: ruleset-bypass
    resource: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/creating-rulesets-for-a-repository
    title: Bypass permissions are granted for a ruleset
  - id: credentials-boundary
    resource: https://github.com/ktogias/gnostoa/issues/15#issuecomment-5979363503
    title: The owner's agent credentials boundary of 2026-10-04
  - id: provider-enforcement-0013
    resource: ./0013-defer-provider-enforcement-while-private.md
    title: Provider enforcement deferred while the repository was private
  - id: analyzer-readback-0091
    resource: ./0091-add-authenticated-provider-neutral-analyzer-readback.md
    title: The analyzer-readback environment, which must admit only main
  - id: claude-credential-0097
    resource: ./0097-scope-the-claude-credential-to-the-protected-branch.md
    title: The Claude credential scoped to the protected branch through an environment
x-project-knowledge:
  id: kit.decision.0106.confine-every-branch-and-tag-write-to-repository-administrators
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /decisions/0013-defer-provider-enforcement-while-private.md
    - kind: references
      target: /decisions/0091-add-authenticated-provider-neutral-analyzer-readback.md
    - kind: references
      target: /decisions/0097-scope-the-claude-credential-to-the-protected-branch.md
---

# Confine every branch and tag write to repository administrators

## Context

On 2026-10-07 the owner installed Amazon Q Developer to add its review to the agent
review cycle of Gnostoa-self Pull Requests. Measured that day:

- **The app's permissions** (`GET /apps/amazon-q-developer`) are write on
  `actions`, `checks`, `contents`, `issues`, `pull_requests` and `workflows`, and
  read on `administration`, `metadata` and `organization_administration`. An
  installer accepts them whole; it cannot narrow them.
- **Its documented behaviour** (AWS, preview):
  - It reviews on its own only when a Pull Request opens or reopens.
  - `/q review` asks for a review.
  - `/q` with free text makes it commit to the Pull Request's source branch.
  - "Commit suggestion" lets a user commit one of its suggested fixes.
  - `/q dev`, or the `Amazon Q development agent` label, makes it implement an
    Issue and open a Pull Request from a branch it creates.
  - Feature development cannot be switched off: "Feature development
    configuration cannot currently be modified". Only reviews can be toggled, and
    only after registering the installation with an AWS account.
  - A role gate of Write, Maintain or Admin is documented for starting a review.
    None is documented for `/q dev`.
- **The repository is public**, so anyone can open an Issue or comment.

**What already held**, read back on 2026-10-07:

- **`main`.** Its required checks, `policy`, `fast`, `regression` and `smoke`, are
  bound to GitHub Actions (`app_id` 15368), so a check run another app posts cannot
  satisfy them. Its classic protection, as the owner read it in the settings, also
  requires:
  - a Pull Request;
  - up-to-date branches;
  - resolved conversations.

  "Do not allow bypassing the above settings" is on, and force pushes and
  deletions are off. The ruleset "Require CodeQL on main" applies. `CODEOWNERS`
  assigns every path to the owner.
- **Secrets.** The workflows use three secrets, and all of them live in two
  environments that admit only `main`:
  - `analyzer-readback` holds two of them (Decision 0091);
  - `claude-review` holds the third (Decision 0097).

  A third environment, `vf0-admission`, holds no secret, as the owner's read below
  shows. It admits one named branch and requires the owner's approval.
- **Publishing.** Seven workflows publish images with `packages: write` and
  `id-token: write`:
  - Six run only on a push to `main`.
  - The seventh, `publish-oci.yml`, runs only when dispatched. A dispatch is no
    ref write, so the rulesets below do not govern it. Its own `authorize` job
    does: it admits only the owner as both the actor and the triggering actor, a
    first run attempt, and `main`'s own workflow on `main`. Its publishing job
    pins `v0.2.0`'s tag object and commit.
- **Agent publication** fails closed on a foreign commit: a push that is not a
  fast-forward, or whose lease does not match, is refused.

**The gap was every other ref, and merging into `main`.**

- **Merging.** `main` requires no approval and no code owner's review. So any
  writer, an app included, could merge a green Pull Request whose conversations
  were resolved, its own too.
- **Every other ref.** An app with `contents` and `workflows` write could create
  branches and tags, commit to a Pull Request's branch, and add a workflow file.
  GitHub runs such a file on push, with the write token permissions it declares
  for itself, before any review.

Provider CI verifies content, by design, not who wrote a commit. The Work Item and
Decision gates are procedure, not a provider control on another author's change.

## Decision

The owner created two repository rulesets on 2026-10-07:

| Id | Name | Target | Rules | Bypass |
|---|---|---|---|---|
| `24640984` | Only admins write branches | every branch, `~ALL` | creation, update without fetch-and-merge, deletion, non-fast-forward | the repository admin role, always |
| `24640985` | Only admins write tags | every tag, `~ALL` | the same | the same |

So only an actor with the repository admin role can create, update, force-push or
delete any branch or tag. That includes merging into `main`, which updates it.
Requiring an approval instead would block every merge: Pull Requests are opened as
the owner, who cannot approve their own.

Any app outside the bypass list cannot commit, create a branch or tag, or merge.
Amazon Q's `/q dev`, its label and `/q` with free text each make Amazon Q write,
so the rules refuse them. That refusal is inferred, not exercised; two facts
support it:
- the probe below showed the rules evaluated for every writer;
- AWS's troubleshooting page states that branch protection rules prevent Amazon Q
  from creating its branch.

**"Commit suggestion" is different.** GitHub documents that "the person who
applies the suggested changes will be a co-author and the committer of the
commit". An administrator's click is therefore an administrator's write, and it
succeeds through the bypass. The rulesets do not stop it:
- **for agents**, the procedure below does;
- **for the owner**, a click is an owner's change like any other. This Decision
  does not restrict it. Change control governs it as it governs every change: a
  normal change needs a Work Item and a Decision first.

**What stays possible**, since it is no ref write: reviews, comments, Issues,
labels, check runs, and dispatching or re-running workflows. The controls above
bound each of these:
- required checks bound to GitHub Actions;
- secrets in environments;
- publishing only on a push to `main`, or through `publish-oci.yml`'s
  `authorize` job, which refuses a dispatch or re-run by anyone but the owner.

**How agents use Amazon Q** within the review cycle: they post exactly
`/q review`. They never post any other `/q` text, and never apply its label. They
never use "Commit suggestion" either, which the rulesets would not stop: an agent
acts as the administrator.

**The provider is authoritative.** The JSON below is evidence of what the owner
imported on 2026-10-07, not the rulesets' source. Their current state is read back
from the provider: `GET repos/ktogias/gnostoa/rulesets/{id}`.

The branch ruleset, `24640984`, as imported:

```json
{
  "name": "Only admins write branches",
  "target": "branch",
  "enforcement": "active",
  "bypass_actors": [
    { "actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always" }
  ],
  "conditions": { "ref_name": { "include": ["~ALL"], "exclude": [] } },
  "rules": [
    { "type": "creation" },
    { "type": "update", "parameters": { "update_allows_fetch_and_merge": false } },
    { "type": "deletion" },
    { "type": "non_fast_forward" }
  ]
}
```

The tag ruleset, `24640985`, as imported:

```json
{
  "name": "Only admins write tags",
  "target": "tag",
  "enforcement": "active",
  "bypass_actors": [
    { "actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always" }
  ],
  "conditions": { "ref_name": { "include": ["~ALL"], "exclude": [] } },
  "rules": [
    { "type": "creation" },
    { "type": "update", "parameters": { "update_allows_fetch_and_merge": false } },
    { "type": "deletion" },
    { "type": "non_fast_forward" }
  ]
}
```

## Alternatives not chosen

- **Allow-listing Amazon Q**, as AWS's troubleshooting page suggests: that grants
  the writes this Decision removes.
- **Relying on `main`'s protection alone**: it leaves every other ref open.
- **Disabling Q's features in the AWS console**: feature development cannot be
  disabled.
- **Uninstalling Amazon Q**: it gives up its review, which is the reason it was
  installed.

## Consequences

- **The rulesets do not constrain agents.** Bypass follows the user's role, not the
  token: agents act through the owner's restricted personal access token, whose user
  is the repository admin. The agent boundary stays where the credentials boundary
  put it: that token holds no Administration, Deployments, Environments or Secrets
  permission. If agents move to an account of their own, that account needs a
  bypass entry, or must work from a fork.
- **An agent steered by what it reviews stays the residual risk.** Decision 0097
  names it as the realistic case. "Commit suggestion" adds no path for an agent:
  - GitHub offers it in its web interface;
  - agents here work without the owner's browser (credentials boundary);
  - so an agent could apply a suggestion only by writing the change itself, and
    that is any agent write.

  The rulesets do not constrain such a write. The agents' procedure and change
  control do.
- **The bypass follows the role, not the person.** Any account later given the
  admin role inherits it, and with it unrestricted ref writes. Today the owner is
  the only collaborator (`GET repos/ktogias/gnostoa/collaborators`, 2026-10-07).
  Granting admin to anyone else is therefore also a change to this control.
- **A writer outside the bypass needs an entry first.** Today none exists: no
  workflow runs `git push` or requests `contents: write`. Dependabot would need one
  if its security updates are enabled.
- **The rulesets live in the provider, which is authoritative.** This record is
  evidence of their state on 2026-10-07; a later change shows in a read-back, not
  here. Changing them needs the owner and a token with Administration write, which
  agents do not hold.

## Verification

Read back and exercised on 2026-10-07:

- **The rulesets.** `GET repos/ktogias/gnostoa/rulesets/{24640984,24640985}`
  returned:
  - `enforcement: active`;
  - `include: ["~ALL"]`;
  - the four rules;
  - `bypass_actors: [{"actor_id":5,"actor_type":"RepositoryRole","bypass_mode":"always"}]`.
- **Role 5 is the admin role.** The provider names it. This GraphQL query returned,
  for both rulesets, `repositoryRoleDatabaseId: 5` and
  `repositoryRoleName: "admin"`, with `bypassMode: ALWAYS`:

  ```graphql
  query {
    repository(owner: "ktogias", name: "gnostoa") {
      rulesets(first: 10) {
        nodes {
          databaseId
          name
          bypassActors(first: 10) {
            nodes { bypassMode repositoryRoleName repositoryRoleDatabaseId }
          }
        }
      }
    }
  }
  ```
- **What the rules refuse.** GitHub's documentation defines each of the four rules:
  - "Restrict creations" reads: "Only users with bypass permissions can create
    branches or tags whose name matches the pattern you specify".
  - "Restrict updates" and "Restrict deletions" read the same for pushing and
    deleting.
  - "Block force pushes", the `non_fast_forward` rule, reads: "You can prevent
    users from force pushing to the targeted branches or tags".

  Bypass is granted for the ruleset as a whole: "You can grant certain roles,
  teams, or apps bypass permissions for your ruleset". The probe exercised
  creation and deletion; a force push was not exercised.
- **They apply to any branch name.** `GET repos/ktogias/gnostoa/rules/branches/probe-anything`
  listed `creation`, `update`, `deletion` and `non_fast_forward` from `24640984`.
- **They are evaluated for agents too.** A push creating, then deleting, a
  temporary branch through the agents' token succeeded, with GitHub reporting:
  - `Bypassed rule violations … Cannot create ref due to creations being restricted`;
  - `Cannot delete this branch`.

  So the rules are evaluated, and only the admin bypass let the push through.
- **The owner's read of the settings**, which the agents' token cannot read:
  - No repository secret is defined, for Actions or for Dependabot.
  - Only environments hold any. `claude-review` holds `CLAUDE_CODE_OAUTH_TOKEN`,
    and `analyzer-readback` holds `CODACY_API_TOKEN` and `DEEPSOURCE_API_TOKEN`.
  - `main`'s protection is as stated under Context.
- **Amazon Q's refusal was not exercised.** That would have needed giving it a
  write command.
