---
type: Decision
title: Admit merges through a required, provider-neutral merge-admission verdict
description: MA0 Phase 1b. A required check, merge-admission, admits a merge only when a provider-neutral, fail-closed verdict over the exact head finds every applicable criterion satisfied. Its evidence part is one completeness reducer over exact-subject receipts (#389 S1), which slice 1b.1 implements. GitHub specifics stay in an adapter, a dedicated App publishes the check from a main-only environment, and the owner's native approval of the exact head is the only per-merge human act, with no waiver.
status: draft
generated:
  by: anthropic/claude-opus-5-5
  at: "2026-10-09T07:15:00Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/407
    title: Require a provider-neutral merge-admission verdict on the exact head (MA0 Phase 1b)
  - id: admission-package
    resource: https://github.com/ktogias/gnostoa/issues/407#issuecomment-6069729619
    title: The admission package, its lineage at 795920f and its prior art
  - id: owner-decisions
    resource: https://github.com/ktogias/gnostoa/issues/407#issuecomment-6076064688
    title: The owner's decisions on the package
  - id: phase-1b-handoff
    resource: https://github.com/ktogias/gnostoa/issues/398#issuecomment-6061573600
    title: The owner's Phase 1b handoff, its seams and its safety invariants
  - id: ma0-revision
    resource: https://github.com/ktogias/gnostoa/issues/15#issuecomment-6048360846
    title: The MA0 revision, with the merge-admission criteria M1-M16
  - id: completeness-owner
    resource: https://github.com/ktogias/gnostoa/issues/389
    title: Fail closed when required assurance evidence is missing, stale or incomplete
x-project-knowledge:
  id: kit.decision.0112.admit-merges-through-a-required-provider-neutral-merge-admission-verdict
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /decisions/0110-bind-every-merge-to-the-owner-s-approval-of-the-exact-head.md
    - kind: governed-by
      target: /decisions/0006-provider-neutral-change-governance.md
    - kind: implements
      target: /requirements/reviewed-change-control.md
    - kind: references
      target: /decisions/0086-implement-useful-l1-as-protected-source-github-current-state-reconciler.md
    - kind: references
      target: /decisions/0091-add-authenticated-provider-neutral-analyzer-readback.md
---

# Admit merges through a required, provider-neutral merge-admission verdict

## Context

[Decision 0110](0110-bind-every-merge-to-the-owner-s-approval-of-the-exact-head.md)
(MA0 Phase 1a) makes the owner's native approval of a pull request required on
`main`. It leaves the rest to the merge procedure and the agent's convergence report:
- the approval's `commit_id` against the head;
- the analyzer readback;
- the analyzers' findings;
- the seal;
- close-last.

Its "Successor: Phase 1b" defers a required check that enforces them, under a
reuse contract:
- consume `tools/github_rest.py`;
- consume Decision 0086's current-state observation;
- consume #389's completeness receipts and #369's trusted execution once they exist;
- add only the provider-neutral verdict.

The evidence part of the merge criteria (M2–M8 in the MA0 revision) is #389 S1's
completeness verdict: "one reducer, not two". No such reducer existed at `795920f`.

## Decision

This Decision is a Gnostoa-self/GitHub specialization. It does not alter the
provider-neutral public change-governance contract of
[Decision 0006](0006-provider-neutral-change-governance.md).

1. **A required check, `merge-admission`, admits each merge.** It passes only when a
   verdict over the exact head finds every applicable criterion satisfied. The
   verdict is provider-neutral and deterministic, and has no network access or side
   effect. It fails closed: missing, stale, partial, unavailable and unknown evidence
   deny. GitHub's vocabulary is translated in an adapter, which consumes the existing
   observation, readback and transport owners. It adds no second observer, reducer or
   REST client.
2. **One completeness reducer** supplies the verdict's evidence part
   (`knowledge assurance-check`, #389 S1):
   - A project declaration names, for each change class, the required evidence as
     coverage items (`policy/assurance-evidence.yaml`).
   - An item is covered only by a current `COMPLETE` receipt for the exact
     repository, change request and head. Otherwise it is `MISSING`, `STALE`,
     `PARTIAL`, `INCOMPLETE`, `SKIPPED`, `RATE_LIMITED`, `UNAVAILABLE` or `ERROR`.
   - Receipts that disagree fail closed at the worse status.
   - The receipt statuses are Decision 0091's coverage statuses, which contain
     Decision 0086's, plus `SKIPPED`.
   - The reducer fetches nothing and grants nothing.
3. **The owner's native approval of the exact head is the only per-merge human act.**
   - What the approval rests on:
     - reviewer convergence: item 4's subset is criteria of the verdict, and the
       rest is in the agent's convergence report;
     - justified suppressions, which the verdict lists;
     - changes to the gate's trust roots, which the verdict lists;
     - the analyzer findings, which the verdict lists and which deny it (M17).
   - Channel C, the environment attestation of MA0 design decision 2, is not used
     for merges. **There is no evidence waiver**: when required evidence is
     unavailable, the merge waits, or goes through break glass with its mandatory
     follow-up.
4. **Reviewer convergence (M11) is enforced as its deterministic subset in this
   phase:**
   - no unresolved thread;
   - no effective `CHANGES_REQUESTED`;
   - the readback and the analyzers, as coverage items of the declaration that the
     reducer covers (M2–M8).

   The convergence of the reviewers themselves stays in the agent's convergence
   report until MA0 Phase 2's per-reviewer adapters.
5. **Publication.** A dedicated App, `gnostoa-ma0`, posts the check from a main-only
   environment. It is woken by Decision 0096's relay pattern and a sweep, and the
   requirement in R-main is pinned to that App, so a same-named check from any other
   source cannot satisfy it.
6. **A post-merge audit** opens the emergency follow-up Work Item for any merge
   without a green `merge-admission` on its head.

## Consequences

- **The phase lands in slices** (#407). Each is admitted separately and merged under
  Phase 1a's procedure:

  | Slice | Contents | Status |
  |---|---|---|
  | 1b.1 | the completeness reducer and declaration | implemented with this Decision |
  | 1b.2 | the verdict (`knowledge merge-admission`) | implemented |
  | 1b.3a | the GitHub evidence adapter's snapshot and identity (`knowledge merge-evidence`) | implemented |
  | 1b.3b | the changed content (suppressions, trust roots) and the receipts, in four PRs: 1b.3b-1 check receipts, 1b.3b-2 the analyzer receipt, 1b.3b-3 Work Item existence and reference integrity, 1b.3b-4 the changed content | 1b.3b-1 merged (#415); 1b.3b-2 admitted (#407, 6101607240); the others each need admission |
  | 1b.3c | SonarCloud's readback (#359) | not yet admitted |
  | 1b.4 | publication and activation | not yet admitted |
  | 1b.5 | the post-merge audit | not yet admitted |

- **Until 1b.4 activates the check, nothing changes for merges.** Decision 0110's
  procedure and the convergence report still govern them.
- **While an item has no producer, the reducer reports it `MISSING`.** SonarCloud's
  inventory is one such item until 1b.3c. So once the check is required, a merge
  waits for its evidence rather than passing without it.
- **The verdict's input is a normalized evidence document,** which the GitHub
  adapter (1b.3) produces. It names the change's subject and lifecycle, its class
  and links, the declared candidate, the declarer, the author and the required approvers, the
  reviews, the threads, the closing references, the new suppressions, the
  trust-root changes, the analyzer findings, and the receipts for the reducer. Every list the adapter
  reads from the provider carries its coverage, so "not read" cannot pass as
  "none": the suppressions and trust-root changes, like the threads and the
  closing references, deny unless their coverage is `COMPLETE`, and M15 is a
  criterion. Finding closing references
  is the adapter's job, since the keyword syntax is the provider's. The verdict
  denies unless their coverage is complete and none is found. The approval rule is
  runbook step 8's: each required approver's latest review, of any state, approves
  the exact head. A pending review is not submitted and is ignored. A review's
  commit is an exact SHA, as the subject's is, or null, as GitHub reports it once
  the commit is garbage-collected or force-deleted; a null commit approves no
  head. The required approvers are distinct. Timestamps are compared in
  whole seconds. Reviews by one reviewer that share the latest second and disagree
  in what a criterion reads (the opinion for M11, the opinion and commit for M16)
  have no order, so they deny. Mapping a deleted account, GitHub's null `user`, to
  a stable reviewer identity is the 1b.3 adapter's job.
- **The approval is bound to the class's rules.** M16 reads `minimum_approvals` and
  `independent_approval` from the effective policy, as M14 reads the link rules.
  In an independent class, the change's author and declarer can be neither a
  required approver nor an approver: any approval by either denies
  (`may_approve_own_change: false`).
- **Each required approver must approve; the adapter names exactly them.** The
  verdict requires every listed approver's latest review to approve the head, and
  at least the class's minimum to be listed. A class whose minimum is zero, as in
  the core policy, needs no approver. Who they are, and that each is a
  person, is the adapter's to establish (a 1b.3 acceptance case). It must take
  them from the protected target's code owners, never from the candidate, since a
  provider account's type does not tell a person from a machine user. An
  any-of-several owner rule would need the contract to carry eligible approvers
  and a count, which this slice does not.
- **The GitHub evidence adapter (1b.3a) reads one L1 snapshot and the protected
  target.** It reads nothing from the provider itself:
  - L1 (Decision 0086), asked for merge evidence, adds the pull request's draft,
    merged, target, default branch, author and bounded body, and its commits and
    changed files with their coverage. Both lists come from the comparison of the
    subject's exact base and head commits, which L1 already reads for the merge
    base, so neither can be another head's. An empty comparison is empty, not an
    error. **The supported domain is up to 250 commits and fewer than 300
    files.** A comparison's one page holds at most 250 commits, the cap the pull
    request's commit list had, so fewer commits than the total is `PARTIAL`. It
    lists at most 300 files, so 300 or more is `PARTIAL`, and the run fails. The
    owner accepted that file domain for initial MA0, and a larger one is a
    separately owned extension (#407, 6084981368). L1 also marks each conversation
    comment `edited` from GraphQL's `lastEditedAt`. A comment it cannot mark makes
    the conversation `PARTIAL`. The advisory's snapshot is unchanged.
  - The project root is a checkout of the protected target, whose change policy,
    `policy/merge-authorities.yaml` and CODEOWNERS apply, never the candidate's.
  - The seal is the declarer's last unedited top-level comment whose first line
    is `Exact review candidate: <sha>`. Unedited means GraphQL records no edit,
    since timestamps in whole seconds cannot show an edit made in the comment's
    own second, and the timestamps agree.
  - Logins are compared without case, and only their ASCII letters fold, so a
    Unicode compatibility character matches no other account. The roster and the
    declarer must be in GitHub's login syntax.
  - The required approvers are each changed file's code owners on the human
    roster (owner decision 2 on #407). A rule whose owners include no rostered
    person fails the run. The CODEOWNERS reader follows GitHub's documented
    rules, inline comments and ownerless rules included, and refuses the syntax
    GitHub skips. A pattern with an empty segment, such as `//sensitive`, or a
    `.` or `..` segment fails the run, since git matches nothing for it (#407,
    6092909419). Wildcards are read only in GitHub's documented forms: `*`
    alone or as the last segment, which is not recursive, `*.ext` as the only
    segment, and `**` as a leading or middle segment. Any other wildcard, such
    as `docs/guides*`, fails the run (#407, 6095614968).
  - The class, Work Item and Decision come from the change-request template's
    `## Change control` fields (owner decision 3), read as CommonMark ([Decision
    0113](0113-read-pull-request-descriptions-with-a-commonmark-parser.md)). The
    fields are the items of the one top-level section's top-level bullet lists,
    so code, HTML blocks and comments are never fields. The section is closed:
    every top-level item must open with a paragraph that begins with exactly
    one of the template's four labels, `Class:`, `Work Item:`, `Decision:` and
    `Accountable owner:`, each at most once, and any other item, a top-level
    ordered list included, fails the run (#407, 6092909419). The closed set
    makes no field required: which are is the change class's policy. An item's field is its first paragraph; a continuation
    paragraph is not read (#407, 6085825905). The section's heading is
    compared by its visible text. GitHub may render Markdown inside a raw HTML
    element, such as a collapsed `<details>`, and CommonMark does not track HTML
    nesting. So any raw HTML tag of an element that can hold content, anywhere
    before the section's end, fails the run, as the owner chose over modelling
    HTML5 nesting (#407, 6086999580). Comments and void elements, such as `<br>`,
    hold nothing and are allowed there. A Change control item holding raw HTML
    other than a comment, in its label or its value, fails the run before it is
    read, since how a void element renders differs, `<wbr>` joining text and
    `<br>` breaking it (#407, 6087507517 and 6087484196). Inline code showing a
    tag is code, not raw HTML. A comment in a value is skipped, so the text
    around it joins. A field's value is its visible text and inline code: a link's
    target is never read, so an empty link contributes nothing, and a Decision
    counts only by the id it shows. That is the owner's re-slice decision under
    #402 (#407, 6085478125). A Work Item value is only `#N` entries in ASCII
    digits, and a Decision value only four-digit ids, each separated by commas
    or spaces. Any other value, such as an issue URL, an invisible character or
    prose, fails the run, as the owner chose over reading identifiers out of
    free text (#407, 6086766086 and 6088050686). A visible `#N` whose link points
    elsewhere is still read as `#N`. Two 1b.3b acceptance cases must be closed
    before 1b.4 activates the gate: whether each Work Item exists, as an issue
    rather than a pull request (#407, 6085101448 and 6085110011), and, proposed
    and pending the owner's admission, whether a link's label and target agree,
    its reference integrity (#407, 6085507735). A Decision counts only when the
    protected target has its record, and a truncated description fails the run.
  - Closing references are GitHub's keywords in the title, the body and every
    commit message, read in the raw text, code and comments included. The
    asymmetry with the class and links is deliberate. Reading a hidden field
    could satisfy M14, so code is skipped there. Reporting a hidden keyword can
    only deny M12, while missing one would let a merge close a Work Item. An
    issue linked by hand in the Development sidebar closes on merge too, so L1
    also reads GraphQL's `closingIssuesReferences`, through the same pager and in
    each readback pass. Each listed issue is found, and M12's coverage is
    `COMPLETE` only when that read and the commit list are complete, the title
    was read, and every commit message was read whole (#407, 6086122133).
    Whether the relation can change after the verdict, with the head unchanged,
    is 1b.4's and 1b.5's concern (#407, 6086106156).
  - The protected target is the repository's default branch, which the change
    policy declares protected.
  - The check items have receipts (1b.3b-1). `policy/merge-required-checks.yaml`,
    read from the protected target, names for each of the declaration's
    `verification-checks` and `codeql` items the GitHub check run that gives
    it, by app id and name: R-main's four checks from GitHub Actions, and
    GitHub Advanced Security's `CodeQL`, whose conclusion applies the
    code-scanning ruleset's threshold. A check of the same name from another
    app does not count. No two (requirement, coverage item) pairs, within or
    across requirements, may name the same app id and name: such a manifest is
    refused, so one run cannot satisfy two declared checks (owner selection for
    `gr-415-shared-check-key`, #15, 6099845892). The rule is this manifest's
    only; a receipt in the provider-neutral contract may still cover several
    items. The latest run on the exact head gives the receipt;
    when several runs carry an item's key, as when two check suites post the
    same name, the item is `COMPLETE` only if every one succeeded, and
    `PARTIAL` if any did not, so a later success cannot hide another current run
    (#407, 6097059408). The owner accepted the possible cost: if the provider
    lists a failed attempt beside its successful re-run, the item denies until
    a new commit (#407, 6097259307 and 6097251980). Whether it does is not yet
    shown. Recovery by re-run within one check suite, with distinct suites
    still unable to mask a failure, is a successor acceptance case before 1b.4
    activates MA0; any L1 extension it needs is admitted separately. For a
    single run, `success` is `COMPLETE`. `skipped` or `neutral` is `SKIPPED`, since a check
    that did not run is not evidence (I10). Pending or any other conclusion is
    `INCOMPLETE`, and an ambiguous latest state is `PARTIAL`. An item with no
    run has no receipt, so the reducer makes it `MISSING`, and a checks read
    that is not `COMPLETE`, commit statuses included, gives every item its
    status, since an incomplete source can only deny. Tests keep the manifest
    equal to the declaration's items and to R-main's recorded checks. A snapshot
    whose provider is not `github` fails the run (the owner's review 5478389359
    on #413).
  - The analyzer items have receipts (1b.3b-2), from the authenticated
    readback's bundle (Decisions 0091 and 0107), read back through the readback
    module's own contract: a recorded readback is valid only if `build_readback`
    rebuilds it exactly. A bundle bound to the exact repository, pull request and
    head gives each item the receipt of its readback's own coverage, whatever its
    findings; readbacks map to items by provider and scope (DeepSource diff and
    full, Codacy). A bundle that is not bound to the subject gives every item
    `INCOMPLETE`, a missing readback gives its item no receipt (`MISSING`), and an
    unknown or repeated readback fails the run. Without a bundle the items stay
    `MISSING`. The bundle file is read inside the project root, as every path
    the command reads, and authenticating it is 1b.4's publisher's.
  - **M17: no unresolved analyzer finding** (the owner's selection, #407,
    6101607240). The evidence lists the findings, each with its item, and their
    coverage: `COMPLETE` only when all three readbacks are present and complete.
    M17 denies unless that coverage is `COMPLETE` and the list is empty. Every
    listed finding counts, a suppressed one included, with no waiver; whether a
    justified suppression can discharge one is 1b.3b-4's (M13). The verdict lists
    the findings for the approval.
  - Until 1b.3c, SonarCloud's items stay
    `MISSING`, and until 1b.3b-4 the suppressions and trust-root changes are
    `UNAVAILABLE`, so the verdict denies rather than passing them vacuously.
    The analyzer-findings rule for 1b.3b-2 is the owner's (#407, 6096770145):
    a bound, complete readback gives a complete coverage receipt whatever its
    findings, the findings stay explicit in the evidence, and the verdict
    denies while any unresolved finding remains, with no waiver.
- **The effective change policy is the candidate's own.** Its whole inheritance
  chain is confined to the project root, through the parent-reference resolver
  that Decision 0033 established for profiles and that both loaders now share. The
  policy must also match the change-control schema, so a malformed requirement
  cannot read as "not required". The inheritance walk is bounded at eight
  policies before a parent is opened, so a long chain fails the run with that
  reason instead of reaching the interpreter's recursion limit.
- **The head-move invariant (d) of the owner's acceptance list** (#398,
  6061573600) is 1b.4's, not the verdict's. The check is posted on the exact head
  commit, so a new head has no passing check, and the App's merge names the head
  it expects.
- **The two commands share one command-line boundary,** `tools/verdict_cli.py`,
  factored from 1b.1's: bounded strict input on standard input, the project-root
  confinement, the write and flush inside the guard, and exit 2 for every failed
  run. Slice 1b.2 adds both of its files to SB2 (21 → 23). The owners it also
  imports, `tools/check_change_policy.py` and `tools/knowledge_common.py`, are
  already members.
- **SB2 grows by two files.** `knowledge assurance-check` is a supported entrypoint, so
  `tools/assurance_completeness.py` and the vocabulary it imports,
  `tools/analyzer_readback.py`, join the executable-candidate binding (19 → 21 files).
  Under [Decision 0035](0035-accept-bounded-first-party-source-security-sufficiency-for-the-first-oci-candidate.md),
  the next OCI candidate's G3 re-binding replays the affected boundary for them.
- **More owner configuration** is needed by 1b.3 and 1b.4: `SONAR_TOKEN`, the
  `gnostoa-ma0` App and its environment, and the requirement in R-main.

## What this supersedes or revises

- **MA0 design decisions 1, 3 and 4 (#15, 5979363503):**
  - the owner exception on every merge;
  - the attestation kinds;
  - the declared-class confirmation.

  They are superseded by item 3. Decision 2's channel C is no longer used for
  merges, a further step beyond Decision 0110's item 3.
- **Decisions 0107 and 0091 §8:** the readback becomes a required input of the
  verdict, failing closed. It is still not a required check of its own.
- **Decision 0067** is unchanged: R2A stays advisory, at most an input.
