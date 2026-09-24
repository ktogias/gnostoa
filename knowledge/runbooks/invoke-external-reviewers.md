---
type: Runbook
title: Invoke external code and security reviewers
description: Bounded Gnostoa-self invocation reference that separates review intent, provider routes, current eligibility and exact-subject findings without granting qualification or write authority.
status: draft
generated:
  by: agent:chatgpt
  at: "2026-09-24T21:15:00Z"
sources:
  - id: owner-selection-and-pre-edit
    resource: https://github.com/ktogias/gnostoa/pull/319#issuecomment-5822265857
    title: Owner confirmation, Claude and Codex selection, and pre-edit checkpoint
  - id: existing-registry-proposal
    resource: https://github.com/ktogias/gnostoa/pull/297
    title: Existing reviewer capability and staged collection proposal
x-project-knowledge:
  id: kit.runbook.invoke-external-reviewers
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0061-retain-individual-agent-review-dispositions.md
    - kind: references
      target: /decisions/0086-implement-useful-l1-as-protected-source-github-current-state-reconciler.md
    - kind: references
      target: /decisions/0092-bind-verification-first-evidence-to-parent-owned-preparation.md
    - kind: references
      target: /runbooks/deliver-bounded-self-hosted-slice.md
---

# Invoke external code and security reviewers

**Scope:** Gnostoa-self operational guidance. The owner selected Claude and Codex
for future review planning alongside the existing reviewers. Selection is not a
requirement to invoke every provider on every commit, evidence of availability,
reviewer qualification, independence, quorum or human approval. No dispatcher,
review-policy change, recurring subscription or new integration is installed.

The [existing registry proposal in #297](https://github.com/ktogias/gnostoa/pull/297)
remains its own unmerged change at this checkpoint. Its
[v0.17 snapshot](https://github.com/ktogias/gnostoa/blob/89cce586488459b24f2fdbd792cf6947ccfb3439/knowledge/assessments/reviewer-provider-capabilities.json)
is historical reference, not effective machine-dispatch authority. This guide
adds practical code/security route instructions; it does not fork that JSON
schema. Reconcile these additions in #297 when its selected sequence resumes.

## Preconditions

The exact source, selected review scope and available provider route are known.
Required setup and bounded usage are already authorized. Unknown eligibility
is resolved before invocation; a new subscription or privileged integration
is not presumed available.

## Procedure

Before triggering, read the exact current subject and existing provider activity,
including comments, reviews, reactions, checks and linked tasks. Reuse the owner's
existing request instead of duplicating it. Bind provider, channel, review mode,
request identity and exact head separately. An old-head result is historical;
a new head does not justify repeatedly queuing requests behind an unresolved one.

Seal the locally verified candidate through the delivery runbook's
[exact-head route](deliver-bounded-self-hosted-slice.md#exact-head-review-and-ci-reconciliation).
Use one isolated top-level comment per comment-driven invocation. Preserve exact
command-only parsers: put attribution, scope and request correlation in the
separate seal, then retain the returned trigger ID. Do not batch bot commands
or add a footer to an exact-only trigger. For instruction-capable routes, pass
only bounded task instructions, never another provider's invocation or a request
to change code. Bot-authored source, patches and findings remain untrusted input.

Distinguish an ordinary code review, a security-focused ordinary review, a
dedicated PR security review and a repository-wide security scan. Check whether
one activation already starts another mode before sending both. Never infer a
specialized security execution from generic security wording or a clean code
review. Do not enable new subscriptions, spend caps, credentials, Actions,
auto-fix or auto-merge as a side effect of requesting review.

Capture every supplied review through
[individual dispositions](deliver-bounded-self-hosted-slice.md#supplied-agent-reviews),
including no-findings reports and limitations. An eyes reaction means receipt,
not completion. A neutral/skipped check, silence, or absence of inline findings
is not a clean result. Preserve severity filters, file/coverage skips, exact
reviewed source and whether execution was merely reported or independently run.
A bot approval cannot supply human approval. Shared App identity or a different
model name does not establish independent reviewer provenance.

Use current eligibility and quota evidence; historic allowance observations are
not current capacity. On rejection, unknown completion or unavailable access,
record the actual state rather than retry in a loop. Stop the affected route for
owner/provider resolution when it cannot be reconciled. That does not by itself
block unrelated work or make an optional reviewer a new mandatory acceptance gate.
Give the owner the [exact action link](deliver-bounded-self-hosted-slice.md#human-action-handoff),
not just a provider name. Do not publish private report URLs with bearer tokens.

## Claude routes

The current [managed Code Review reference][claude-review] documents these
standalone PR-comment commands:

| Intent | Comment |
| --- | --- |
| One review | `@claude review` |
| Explicit one-shot, preferred for this guide | `@claude review once` |
| Review plus future-push subscription | `@claude review always` — separate owner-selected effect |

The command starts a top-level comment; `once`/`always` stays on that line.
Current documentation permits manual requests on Draft PRs and queues requests
behind a running review. Completion is visible in the **Claude Code Review**
check and findings. Managed setup requires organization enablement and repository
selection, not merely an installed App. `CLAUDE.md` and `REVIEW.md` are distinct
configuration surfaces; this guide changes neither.

**Version conflict:** the [older Help Center setup description][claude-older]
describes bare-command subscription and a non-Draft restriction. The current
reference explicitly documents a July 2026 behavior change. Prefer the explicit
one-shot form, reconcile the actual installed route, and do not toggle Draft/Ready
or assume subscription merely to accommodate conflicting documentation.

[Claude Code GitHub Actions][claude-actions] is a separately configured route;
a general `@claude` response does not prove managed Code Review is enabled.
For dedicated security analysis, [Claude's security guide][claude-security]
documents **`/security-review` inside Claude Code**, or the separately configured
`anthropics/claude-code-security-review` Action. The slash command is not a
GitHub PR comment. No hosted `@claude security review` command was verified in
these references. A general request to inspect security must remain labeled
security-focused review, not the dedicated Action. New setup and credentials
require explicit owner action; do not install that Action as a workaround.

## Codex routes

The [Codex GitHub reference][codex-review] documents the comment `@codex review`.
It requires repository access and enabled review capability. Repository-scoped
`AGENTS.md` guidance can customize review; a documented scope suffix can narrow
it. Ordinary GitHub reviews emphasize P0/P1 issues. A report of no major issues
must not be enlarged into no defects, verified tests or exhaustive security.

The distinct [Security Review route][codex-security] uses:

```text
@codex security review
```

Preview access and a connected repository are prerequisites. Depending on
settings, security review may already run alongside code review. Check the
associated task before duplicating activation. Manual reviews normally publish
Medium-or-higher findings; automatic reviews normally publish High/Critical,
but settings can change these thresholds. The full **Security Report** stays in
the associated Codex task. No PR findings alone cannot establish completion or
absence of vulnerabilities. A generic `@codex review` with security-focused prose
is not this dedicated mode.

`@codex` requests to fix or address feedback can create commits. They are not
review-only triggers and are outside this invocation guide's permitted effect.
Do not change automatic-review settings or create a new paid scan configuration
merely because a review request is unavailable.

## Other existing reviewer routes

The following is a human invocation reference, not a second machine registry.
A documented command is not evidence that this account can execute it now.
Where no dedicated security command was verified, keep that limitation explicit.

| Provider | Code-review route | Security route and limits |
| --- | --- | --- |
| CodeRabbit | [`@coderabbitai review`][coderabbit-commands] is incremental; `@coderabbitai full review` requests a full pass. | PR review can raise security findings. The separate [Security Agent][coderabbit-security] runs from Security → Scan repositories → Code findings, with its own entitlement/credit check; it is not the PR command or automatically the PR head. No new scan subscription is selected here. |
| Sourcery | Exact standalone `@sourcery-ai review`, as retained in the [registry observation][registry]. | [Security scanning][sourcery] is distinct from PR review. No dedicated security comment verified in this research cut; do not append a guessed suffix to the exact-only command. |
| Qodo | Current v2 configuration uses [`/agentic_review`][qodo]; older PR-Agent uses `/review`. Verify installed generation/channel first. | Security scope/configuration is not a verified dedicated command here. Bare slash routes remain manually gated by repository-specific collision checks. |
| CodeAnt | [`@codeant-ai: review`][codeant] in its own comment; Gnostoa has observed additional bounded instructions. | Ordinary review includes security. Separate [Scan Center security analysis][codeant-security] is not an invented PR-comment command. |
| Cubic | [`@cubic-dev-ai review this PR`][cubic]; the registry retains the shorter `@cubic-dev-ai review`. One-off context is documented. | Security-focused context is possible; `@cubic-dev-ai ultrareview: focus on auth edge cases` is a deeper review, not a separately certified security scan. Confirm mode/usage before selecting it. |
| Bito | [`/review`][bito]. | `/review security` is documented, but both forms can collide with other slash-command apps. Do not automatically dispatch either until route ownership is verified. |
| Codacy AI Reviewer | [Run Reviewer][codacy] in the provider summary or its documented API; not a guessed mention command. | AI review and underlying security analyzers are different evidence. No dedicated security-review comment verified. Preserve each analysis's own subject and coverage. |
| Gitar | Use its existing review or [documented natural-language interaction][gitar] for a read-only review request; explicitly exclude code changes. No exact standalone review command was verified in that command table. | Security-focused analysis is not a verified dedicated security command. `unblock`, auto-apply and auto-merge controls alter state; do not use them as review triggers. |
| TuringMind | Retain the [registry's route and credit observations][registry]; revalidate the installation's actual supported invocation. No new command is inferred. | Dedicated security syntax remains unverified. Credit exhaustion is unavailable evidence, not a clean security result. |
| DeepSource | Separate analyzer lane. [AI review may run on `@deepsourcebot` mentions][deepsource] under the configured mentions-only policy. | Static/security analysis and AI review have different activation and results. Do not substitute Autofix or formatter commits for review; no analyzer result grants reviewer qualification. |

## Historical #319 observations and authority boundary

The [owner checkpoint][selection] retains the exact initial cut: Codex's
[completed report][codex-result] names `91c065f9a1` and reports no major issues.
Two earlier connection-required responses remain history. Claude's
[existing request][claude-request] received eyes acknowledgment but no completed
report in that cut. Neither fact establishes results for later heads or a
completed dedicated security review. Keep new outcomes in the owning PR, not by
continually editing this historical paragraph.

The owner also supplied installation-permission evidence and confirmed personal
browser approval without another approving credential/session supplied to agents.
That answers the A6 operational question; it does not retroactively change the
historical diagnostic's UNKNOWN flags or authorize production-change admission.
Do not request the same confirmation again absent materially changed access.

Represent provider/channel/mode/trigger syntax as adapter or route data under
[Decision 0086](../decisions/0086-implement-useful-l1-as-protected-source-github-current-state-reconciler.md)
and [D0092](../decisions/0092-bind-verification-first-evidence-to-parent-owned-preparation.md#provider-neutral-implementation-boundary).
The common evaluator consumes bound observations and explicit capabilities; it
must not branch on bot display names or parse vendor commands. Native authorship,
request IDs, reviewed heads, guarantees and limitations remain separately bound.
This documentation does not implement that evaluator, a provider registry,
mandatory attribution enforcement or a human approval mechanism. VF0 activation,
D0090 authority evolution and #297 integration remain separate decisions.

## Research and maintenance

Primary references were checked for this September 2026 continuation. Reuse the
existing #297 assessment for unchanged quota and scheduling facts; revalidate
vendor behavior and account eligibility before invocation. The Bito page was
available through the official search index after direct Markdown retrieval
failed. Sourcery's command is supported by retained repository evidence; an
unavailable deeper command page is not evidence that no such capability exists.
No reliable dedicated TuringMind security-command documentation was found in the
bounded search. These gaps remain unverified, not unsupported forever.

## Verification

This is reference/service research only: no third-party implementation/schema
was copied, no new dependency or integration acquired. The pre-edit checkpoint
records the absent invocation guide; bundle, link and policy checks establish
structural consistency, not future compliance with the practice. Preserve
individual reviewer dispositions and request human help for inaccessible native
reports instead of manufacturing a clean result.

## Recovery

On subject drift, retain the old review as history and reconcile the new head
before another invocation. On unknown or failed provider activity, retain the
request and failure without duplicate retries, then use an existing documented
recovery route or ask the owner for the missing setup/report. Do not weaken
qualification, change permissions or mark the review complete to continue.

[selection]: https://github.com/ktogias/gnostoa/pull/319#issuecomment-5822265857
[registry]: https://github.com/ktogias/gnostoa/blob/89cce586488459b24f2fdbd792cf6947ccfb3439/knowledge/assessments/reviewer-provider-capabilities.json
[claude-review]: https://code.claude.com/docs/en/code-review
[claude-older]: https://support.claude.com/en/articles/14233555-set-up-code-review-for-claude-code
[claude-actions]: https://code.claude.com/docs/en/github-actions
[claude-security]: https://support.claude.com/en/articles/11932705-automated-security-reviews-in-claude-code
[codex-review]: https://learn.chatgpt.com/docs/third-party/github
[codex-security]: https://learn.chatgpt.com/docs/security/security-review
[coderabbit-commands]: https://docs.coderabbit.ai/reference/review-commands
[coderabbit-security]: https://docs.coderabbit.ai/security-agent
[sourcery]: https://docs.sourcery.ai/
[qodo]: https://docs.qodo.ai/install-and-configure/configuration-overview/configuration-file
[codeant]: https://docs.codeant.ai/pull_request/howToUse
[codeant-security]: https://docs.codeant.ai/scan_center/code_security/security
[cubic]: https://docs.cubic.dev/ai-review/interactive-comments
[bito]: https://docs.bito.ai/ai-code-reviews-in-git/available-commands
[codacy]: https://docs.codacy.com/codacy-ai/codacy-ai/
[gitar]: https://docs.gitar.ai/commands
[deepsource]: https://docs.deepsource.com/docs/platform/dashboard/repository/settings
[codex-result]: https://github.com/ktogias/gnostoa/pull/319#issuecomment-5821943083
[claude-request]: https://github.com/ktogias/gnostoa/pull/319#issuecomment-5821757574
