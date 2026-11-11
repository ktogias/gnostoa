---
type: Source
title: "Supervisor rulebook, evidence and gates themes"
description: "Themes 3, 5, 6 and 9 of the supervisor agent's handoff-safe rulebook (47 rules), copied from the published #325 records with one review correction, and loaded by theme."
status: draft
generated:
  by: anthropic/claude-opus-5-5
  at: "2026-11-11T20:27:00Z"
sources:
  - id: rulebook-part-1
    resource: https://github.com/ktogias/gnostoa/issues/325#issuecomment-6805345513
    title: "Supervisor rulebook (handoff-safe), part 1 of 2"
  - id: rulebook-part-2
    resource: https://github.com/ktogias/gnostoa/issues/325#issuecomment-6805346585
    title: "Supervisor rulebook (handoff-safe), part 2 of 2"
  - id: rulebook-addendum-1
    resource: https://github.com/ktogias/gnostoa/issues/325#issuecomment-6805360817
    title: "Supervisor rulebook, addendum 1 (R-GATE-05)"
  - id: rulebook-addendum-2
    resource: https://github.com/ktogias/gnostoa/issues/325#issuecomment-6805985258
    title: "Supervisor rulebook, addendum 2 (R-EVD-11)"
  - id: owner-decision
    resource: https://github.com/ktogias/gnostoa/issues/325#issuecomment-6806047559
    title: "Owner decision (relayed) of 2026-11-11 on the rulebook's thematic files"
x-project-knowledge:
  id: kit.assessment.supervisor-rulebook-evidence-gates
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0004-self-host-policy-guidance-and-knowledge.md
---

# Supervisor rulebook: evidence and gates

Themes 3, 5, 6 and 9 of the supervisor rulebook: 47 rules, copied unchanged from the published records [#325 6805345513](https://github.com/ktogias/gnostoa/issues/325#issuecomment-6805345513) and [#325 6805346585](https://github.com/ktogias/gnostoa/issues/325#issuecomment-6805346585). R-EVD-11 comes from [#325 6805985258](https://github.com/ktogias/gnostoa/issues/325#issuecomment-6805985258) and closes its theme. R-GATE-05 comes from [#325 6805360817](https://github.com/ktogias/gnostoa/issues/325#issuecomment-6805360817) and closes its theme; one of its lines was corrected in review (see the index's [review corrections](supervisor-rulebook-index.md#review-corrections)). Each theme keeps its published number and each rule its id. Start at the [index](supervisor-rulebook-index.md) for the conventions, the other themes and the manifest of source notes.

Owner directions remain authoritative in their linked GitHub records; where a rule here differs from a linked record, the record wins.

## 3. Records, language and publication

### R-REC-01 (active): Write every record in English, and post every supervisor GitHub comment only through the supervisor's publish gate.
- **Why:** English is the project language. Records must be readable by every role and fit to port into Gnostoa (Owner, 2026-11-10).
- **How to apply:**
  - The gate runs, in order: a language check that refuses non-Latin letters, an attribution check, a disclosure scan, then the post as the App. Never post directly.
  - Quote the Owner in English translation. The session conversation may stay in the Owner's language.
  - If other roles' outputs show the same problem, propose the gate for the pilot's shared publication path.
- **Origin:** 2026-11-10; #325 6777077748. Memory: records-in-english-via-gate.

### R-REC-02 (active): Never publish host details on GitHub or any external service.
- **Why:** the repository is public. Paths, the hostname, disks, OS and package versions, unit names and personal files are reconnaissance and personal data, not Gnostoa evidence (Owner, 2026-11-09).
- **How to apply:**
  - Scan every body for home paths, the hostname, disk and mount names, versions, unit names, personal file names, other projects and email addresses. Replace them with a generic phrase.
  - Host maintenance and host-blocker records stay in local files. For host-only matters this overrides "GitHub record first".
  - Public posts carry only commit SHAs, PR and issue numbers, check names, repository-relative paths and role states.
- **Origin:** 2026-11-09; #325 6743690598, 6745162238. Memory: no-host-details-in-public-posts.

### R-REC-03 (active): Cite only ids returned by a post or a read-back.
- **Why:** a guessed comment id in a public correction is a fabricated reference (#417).
- **How to apply:**
  - Post the referenced comment first, capture its id, then build the referring body.
  - When the id cannot be known yet, write "the next comment" and edit the id in after the read-back.
- **Origin:** 2026-10-11; #417. Memory: cite-only-read-back-ids.

### R-REC-04 (active): Compute every number in a post with the script that writes the post.
- **Why:** hand-typed figures next to exact digests read as verified. There were three slips on #389 in one day.
- **How to apply:**
  - Generate counts, row indexes, byte sizes and digests in the posting script.
  - Fence byte-exact payloads unmodified. Check every number that is not an id against its source.
  - Never let a summary command discard an exit status. Record argv, the exit code and bounded output.
- **Origin:** 2026-10-28 to 2026-11-05; #389, #477. Memory: derive-every-number-in-a-post.

### R-REC-05 (active): A digest is evidence only next to the exact bytes and the extraction convention.
- **Why:** piping a jq-printed body into a hash adds a newline (#436). A digest published with a shortened table could not be reproduced and cost a round (#439).
- **How to apply:**
  - Compute a body digest from the raw API JSON's `body` field.
  - Publish the raw payload, the convention and the digest. A summary is extra, never a substitute.
  - Take every published time from its artifact, after the edit has landed.
- **Origin:** 2026-10-17 to 2026-10-18; #436; #439 6250502451. Memory: hash-the-exact-body, publish-the-bytes-you-hash.

### R-REC-06 (active): Run the strict published reader or verifier on your receipts before posting.
- **Why:** a checker with a silent fallback passed bytes the published rule did not produce, for 18 of 24 files (#389). Two published verifiers failed on their own receipts (2026-10-30).
- **How to apply:**
  - Write blocks so the published rule is literally true, or state the newline handling in the rule.
  - Verify with a reader that implements only the published rule. Treat any fallback in a checker as a defect.
  - Post only on PASS, and give every published file a unique name.
- **Origin:** 2026-10-24 to 2026-10-30; #389 6381564575. Memory: state-your-extraction-rule-against-the-strict-reader, dry-run-the-verifier-before-posting.

### R-REC-07 (active): Never change a file after publishing its digest; corrections go to a new versioned folder.
- **Why:** overwriting declared logs broke the binding the Router and PAO had acquired, and looked like substitution (#440).
- **How to apply:** treat the published folder as read-only. Write corrections to r2/, r3/ with their own checksums and README. Keep originals that cannot be regenerated byte-exactly.
- **Origin:** 2026-10-18; #440 6255851201. Memory: freeze-published-evidence.

### R-REC-08 (active): Quote options and figures from their latest source record.
- **Why:** merging two Owner options into one, and re-quoting a figure already withdrawn, both re-published wrong claims (#389).
- **How to apply:**
  - Copy each option's operative definition and cost from its defining record. Never describe two options together without checking each.
  - Before quoting an earlier figure, search the thread for corrections, and quote the latest surviving figure with its comment id.
- **Origin:** 2026-10-24 to 2026-10-31; #389 6375722141, 6542373287. Memory: quote-option-definitions-verbatim, reuse-the-latest-corrected-figure.

## 5. Merge and review process

### R-MRG-01 (active): The Implementer merges under the Owner's standing consent, after native exact-head approval, through the merge guard.
- **Why:** the Owner's standing consent (2026-10-19) covers every PR whose exact head carries the Owner's native APPROVED review, after the step-8 checks. The earlier "the Implementer never merges" rule was the supervisor's own design, and is superseded (R-AUTH-01).
- **How to apply:**
  - Run the step-8 reads, then the merge guard as one plain command. On PROCEED, re-read, then run `pr merge <N> --squash --match-head-commit <sha>`.
  - Use the newest merge-admission record on the head. After the guard, compare the head, title and body with the step-5 copies.
  - On an authentic guard refusal, do not retry: a new attempt needs a Router decision. If the host refuses, ask for Manual mode once for that exact call.
  - Post the pre-effect and step-9 records through the gates, and read them back.
- **Origin:** 2026-10-19 to 2026-11-11; #15 6190436196; #325 6779884597; #396, #487, #489, #490. Memory: standing-merge-consent, headless-implementer-never-merges.

### R-MRG-02 (active): Never merge with `--admin`.
- **Why:** an admin merge came 80 s after the Owner said the bypass was unwanted (#388). No actor, the agent included, may merge around the gate (Owner, 2026-10-08; Decision 0110).
- **How to apply:** run the pre-merge check before every convergence claim. Merges go through the App after the Owner's native exact-head approval.
- **Origin:** 2026-10-08; #388; #15 6048360846. Memory: no-admin-merges.

### R-MRG-03 (active): After a base sync, a carried-forward approval is not an exact-head approval.
- **Why:** a merge-from-main sync keeps the Owner's APPROVED review and re-points its commit id to the new head, while the review text names the old head (Router, #389 6792245950).
- **How to apply:** compare the head named in the review body with its commit id. Do not run the guard for the new head until a review is submitted after the push.
- **Origin:** 2026-11-11; #489; #389 6792245950. Memory: base-sync-carries-native-approval.

### R-MRG-04 (active): Prepare a base sync over the merge's first parent when the PR touches a preparation-authority path.
- **Why:** a PR that changes `pyproject.toml`, or another authority path, cannot be prepared over main.
- **How to apply:** check the PR's paths against the authority list. If one matches, prepare over the first parent (the PR head), and make sure main's delta touches none.
- **Origin:** 2026-11-11; #396, #487, #489; 6795572413. Memory: base-sync-prepare-over-first-parent.

### R-MRG-05 (active): Freeze a merge only once the head's own admission runs have settled; then merge within seconds.
- **Why:** freezing 30 s after an ALLOW let a second run start, and the guard refused (#476). The admission queue is repository-wide, so waiting for "none queued" can take hours (#478).
- **How to apply:**
  - Settle on the head's own `merge-admission` check runs: the newest is ALLOW, at least 45 s old, with none pending.
  - Freeze, re-check, and run the guarded merge in one script.
  - Post the pre-effect record before waiting, never between the freeze and the merge: a post wakes a run.
  - If the preflight refuses, record the hold once. Retry only if the Owner's decision allows it.
- **Origin:** 2026-11-02 to 2026-11-05; #476 6586115364; #478. Memory: freeze-after-admission-settles, merge-admission-queue-is-repo-wide.

### R-MRG-06 (active): A PR that must land before an approved sibling must not touch the sibling's insertion points.
- **Why:** a conflict on main forces a new head on the sibling, which costs its approval and its review round.
- **How to apply:** diff the sibling's files against yours, keep your inserts at least one unchanged line away, prove it with `git merge-tree`, and explain any odd ordering in the PR body.
- **Origin:** 2026-11-11; #489, #490. Memory: keep-an-approved-sibling-mergeable.

### R-MRG-07 (active): Re-parent stacked PRs after a squash merge, and prove tree identity.
- **Why:** the repository allows squash merges only and main is strict. Line-based merges of large test modules mispair hunks.
- **How to apply:**
  - A child that does not conflict: reset softly onto main, prepare again, push with a lease, and prove the new tree equals the reviewed tree.
  - A child that conflicts: merge per definition (per test method), not per line. Re-read the Decision text for statements the new base made false.
  - Ask the Owner again for any PR whose content changed.
- **Origin:** 2026-10-02; #329, #330, #340. Memory: landing-stacked-prs.

### R-MRG-08 (active): Trace a PR event through the whole admission path before predicting its effect.
- **Why:** an evidence-neutral description edit cannot supersede a standing ALLOW, because Decision 0133 coalesces it away. A workflow rerun writes new check-run ids.
- **How to apply:** trace the trigger, `subjects` (coalescing), `invalidate` and `admit` on protected main, and replay the evidence fields on the changed input.
- **Origin:** 2026-11-10; #407, #489; 6774495087. Memory: decision-0133-coalescing-swallows-neutral-edits.

### R-MRG-09 (active): While an exact-run exception is pending on a PR, post only issue comments there.
- **Why:** every review, review comment or PR edit fires a wake job on the head and adds an annotated run; issue comments do not (#437).
- **How to apply:** make no thread replies, PR edits or review requests while the exception is pending. At step 8, re-read every annotated run against the exception's predicate.
- **Origin:** 2026-10-17 to 2026-10-24; #437 6231552940; #455. Memory: review-events-add-annotated-runs.

### R-MRG-10 (active): The PR body must pass protected main's evidence collector.
- **Why:** a body without a Change control section, over 65,536 bytes, or with a bot-prepended HTML summary makes merge admission refuse, or never evaluate (#434, #436, #441, #447).
- **How to apply:**
  - Replay protected main's full `_change_control(body, load_decisions(<main export>), repo)` offline, not only the field parser.
  - Every PR that exercises merge admission carries Change control (Work Item and Decision). Copy the block from a live PR.
  - Keep bodies well under 64 KiB, put round history in comments, and check the byte length before every body edit.
  - A Decision cannot authorize its own merge: a PR that adds its own Decision is a route question at PR creation.
  - Never edit a frozen body yourself, and never shorten a body after an Owner risk selection or approval.
- **Origin:** 2026-10-15 to 2026-10-27; #434, #441, #443, #447; #436 6264726719. Memory: gate-exercising-pr-needs-change-control, replay-the-collector-not-the-field-parser, revix-body-blocks-merge-admission, pr-body-64kib-limit.

### R-MRG-11 (active): Bots rewrite PR bodies and their own comments in place; re-read after their last edit.
- **Why:** a body update was lost five seconds later to a bot's cached description (#406). Edited bot comments keep their id and creation time (#415, #436).
- **How to apply:**
  - Update the body only after the bot shows the head as reviewed, then re-read the body and its edit history.
  - Before a convergence report, re-read every bot comment updated after the seal. Treat a reused id as new content.
  - In body-editing scripts, stop on any failed assertion.
- **Origin:** 2026-10-08 to 2026-10-16; #406, #415, #436. Memory: bots-overwrite-pr-bodies, bots-edit-top-level-comments.

### R-MRG-12 (active): Post the unedited "Exact review candidate: <SHA>" receipt before requesting fresh external review.
- **Why:** AGENTS.md requires it, and it is M9's seal. Reviews requested without it were recorded as insufficient evidence (#473).
- **How to apply:** push, then the App's receipt, then the review requests. Never edit a receipt; a new head gets a new one.
- **Origin:** 2026-10-31; #473 6544205570. Memory: exact-candidate-before-fresh-review.

### R-MRG-13 (active): Ask the protected Claude reviewer to read, never to compute.
- **Why:** it runs read-only tools under a turn cap, so hash or count requests burn its turns (#478).
- **How to apply:** publish computations yourself and ask it to check the method. Give exact files and line numbers. Keep about 15 sites per part and post the parts one at a time. Commit-isolated parts must quote their own hunks.
- **Origin:** 2026-11-03 to 2026-11-05; #478, #479. Memory: claude-review-turn-cap.

### R-MRG-14 (active): Before calling a PR converged, list every check run and every commit status on the exact head, required or not.
- **Why:** an analyzer that reports by commit status was red while the PR was called ready (#329). The check-runs endpoint hides runs unless `filter=all` is set (#413, #415, #419).
- **How to apply:**
  - Read the check runs with `filter=all` and the commit statuses. An unfinished run counts as red, and a green-but-skipped status as NOT RUN.
  - Read analyzer verdicts from their status, dashboard or API, not from PR comments.
  - Dispose of a stuck provider run only with evidence on the exact head: a later completed run in the same suite, and a completed suite.
- **Origin:** 2026-09-19 to 2026-11-05; #329, #338, #413, #415, #419. Memory: every-signal-on-the-head, check-runs-filter-all.

### R-MRG-15 (active): A green reviewer check can mean "not run".
- **Why:** several review bots reported passing checks while declining to review (#329, #330).
- **How to apply:** read each bot's comment, not its check bucket. Say which reviewers ran, which declined, and why. For a stacked PR, name the checks that did not run.
- **Origin:** 2026-09-28 to 2026-10-29; #329, #330, #461. Memory: a-green-reviewer-check-can-mean-not-run.

### R-MRG-16 (active): A thread or review status claim needs a fresh native read immediately before it.
- **Why:** a watcher's silence missed bot comments. A false "no open threads" can mislead the Owner's merge checkpoint (#436).
- **How to apply:** run the unresolved-threads read and the since-filtered review-comments read right before the claim, and state the head SHA and the read time.
- **Origin:** 2026-10-17; #436 6243815637. Memory: read-threads-before-a-status-claim.

### R-MRG-17 (active): Dispose of review threads one at a time, keyed by the first comment's id.
- **Why:** batching by file or author mis-assigned two findings, one of them P1 (#327).
- **How to apply:** fetch each unresolved thread with its first comment's id, and read the body before replying. On a mis-assignment, unresolve the thread, say so plainly, then fix the finding.
- **Origin:** 2026-10-08; #327, #392. Memory: dispose-review-threads-one-at-a-time.

### R-MRG-18 (active): Fix every valid review finding; never propose shrinking the threat model to stop rounds.
- **Why:** after eight rounds the Owner asked for a plain explanation, then chose (in English translation) "Fix them all" (#364).
- **How to apply:** keep converging round by round. Before asking whether to stop, explain the problems plainly, grouped by family, with the real boundary.
- **Origin:** 2026-10-05 to 2026-10-06; #364. Memory: fix-every-review-finding.

### R-MRG-19 (active): Convergence means the required reviewers are clean, no inline finding is open and every signal is green; nitpicks are reported, not chased.
- **Why:** one bot posts fresh nitpicks on every head, so chasing them never ends. The Owner chose to merge with the nitpicks listed.
- **How to apply:**
  - Convergence: Codex, Claude, Amazon Q and Semgrep clean, no CodeAnt inline finding, every signal green. List the nitpicks in the merge question.
  - Verify each nitpick against the published head. Fix a cheap, real one only while a round is open anyway.
  - Capture behaviour unchanged from main as a Work Item.
- **Origin:** 2026-10-03 to 2026-10-23; #353, #355, #369, #436, #441. Memory: review-convergence-stopping-rule.

### R-MRG-20 (active): Decline only findings outside an Owner-approved boundary, and cite the boundary.
- **Why:** Owner-approved bounds stop endless rounds. Hostile local shells are out of scope (#400). `knowledge mutants` isolates its own writes but does not sandbox the tests it runs (#374). The reuse check guards accidental re-implementation, not deliberate obfuscation (#369; Owner, in English translation: "Yes. I agree. Continue like this.").
- **How to apply:**
  - Still fix accidental-environment findings, and every finding about the tool's own writes, copies or trusted execution.
  - Decline only findings whose scenario needs the excluded threat, citing the measurement and the boundary.
- **Origin:** 2026-10-05 to 2026-10-08; #369, #374, #400. Memory: hostile-local-shell-boundary, mutation-runner-boundary, reuse-check-scope-bound.

### R-MRG-21 (active): Triage findings by cause before proposing fixes, and repair only current-scope defects.
- **Why:** a "fix all 30 findings" packet was retracted after triage found 25 intentional findings, 5 analyzer mismatches and no defect (#389). Activation-time hardening and bot "rules" without a project contract are not current scope (Router 6532072075).
- **How to apply:**
  - Publish a per-cause table: defect, architecture, intentional, analyzer mismatch, uncertain; unconditional or change-dependent.
  - Implement the current-scope defects. Reply to the rest with measured facts, and keep them in the disposition record.
  - Escalate a credible security exposure at once; triage never delays containment.
- **Origin:** 2026-10-25 to 2026-10-30; #389 6404491858; #471 6532072075. Memory: triage-findings-before-proposing-fixes, repair-only-current-scope-findings.

### R-MRG-22 (active): Read the live setting and a real past result before changing what an irreversible operation carries.
- **Why:** pinning the squash subject and body without reading the repository's settings would have dropped `(#N)` and the commit history from every merge (#400).
- **How to apply:** read the repository's merge settings and the last merge commit's message. Prefer a check-before over an override. Pass untrusted provider text through files, never the command line.
- **Origin:** 2026-10-08; #399, #400. Memory: read-live-settings-before-changing-what-a-merge-carries.

### R-MRG-23 (active): After a failed or timed-out effect command, read back before retrying once.
- **Why:** a timed-out POST may have landed, and a blind retry duplicates a public post (#422). `gh pr merge` needs a git working directory and fails from a scratch folder (#490).
- **How to apply:** read the target first (comments since just before the attempt, or the PR's merged state). Re-mint the token on 401. Run merges from the checkout. Record the failed attempt.
- **Origin:** 2026-10-11 to 2026-11-11; #422, #490. Memory: timed-out-post-may-have-landed, gh-pr-merge-needs-a-git-cwd.

## 6. Evidence and claims

### R-EVD-01 (active): Never claim an absence or a count from a read that cannot prove it is exhaustive.
- **Why:** a first-100 thread read truncated silently, and a PR was called converged with two findings open (#330). Page-one comment reads hid new reviews. `--paginate --jq` aggregates per page (#413).
- **How to apply:** paginate every read. For aggregates, use `--paginate --slurp` and an external `jq`. When a gate contradicts a direct read, check the gate's query. Test helpers on multi-page input.
- **Origin:** 2026-09-30 to 2026-10-10; #330, #353, #413. Memory: a-count-from-an-unpaginated-read, gh-api-comments-are-paginated, paginate-jq-runs-per-page.

### R-EVD-02 (active): Before writing "none exists", look for the owner, and name the search that found nothing.
- **Why:** three false absence claims on #389 in one day needed public corrections. A claim that the host records only refusals was false: it records every decision (#440).
- **How to apply:**
  - Search `tools/`, `ci/`, `.github/` and `policy/` at exact main. Trace the producing workflow job through `ci/verify` to the tool.
  - Write "no producer found in <paths>", not "none exists".
  - For host permission claims, read the recorded decision for the exact call, and report executed, host-accepted and contract-conformant separately.
- **Origin:** 2026-10-14 to 2026-11-02; #389 6165697928; #440 6255160371; #441. Memory: find-the-owner-before-claiming-absence, host-records-every-decision.

### R-EVD-03 (active): State a decline or an impossibility at exactly the strength of its evidence.
- **Why:** "measured in two images" written as "cannot arise" was falsified (#453). "No public mock API does this" was false: `patch(..., spec=True, new_callable=factory)` hands the original to the factory (#389).
- **How to apply:**
  - Say "not observed in the measured cases" or "fail-closed". Claim impossibility only from primary documentation.
  - Check what the standard or the mechanism allows. A test that pins your own behaviour is not authority for it.
  - To wrap or fault-inject a private function without attribute access, use that `patch` factory form.
- **Origin:** 2026-10-23 to 2026-10-28; #453; #389 6480056885. Memory: measured-instances-are-not-impossibility, mock-factory-gets-the-original.

### R-EVD-04 (active): Measure complexity and time-bound claims on hostile input, and count the library's own calls.
- **Why:** a regex claimed to be linear was quadratic (#369). A deadline check inside a generator loop did not bound a bottom-up walk that scanned the whole tree before its first yield (#451).
- **How to apply:** time hostile fills at two sizes. List every syscall a library makes on your behalf, and count them under an already-spent budget. Pin the hostile shapes in a test.
- **Origin:** 2026-10-06 to 2026-11-10; #369, #489; #451 6330677193. Memory: measure-before-claiming-complexity, bound-the-traversal-not-the-callback.

### R-EVD-05 (active): A title or summary is never evidence; bind allowances to the artifact's semantic content.
- **Why:** accepting admission verdicts by check title let four incomplete claims pass under an allowed title (PAO 6525927969).
- **How to apply:** read the verdict claims, findings and readback rows, never only a title or a conclusion. A pending run is never evidence. Require that no new artifact appeared between the semantic read and the effect.
- **Origin:** 2026-10-30; 6525927969. Memory: a-title-is-never-evidence.

### R-EVD-06 (active): Judge every check from its own raw output, through the protected verifier.
- **Why:** a round wrapper's "all passed" aggregated nothing. A re-implemented receipt check passed three tampered receipts (PAO 6537983807).
- **How to apply:** read each step's own output file. Verify receipts with the protected `tools.candidate_prepare.verify_receipt` and the trusted digest. Reuse the owner; never re-implement it.
- **Origin:** 2026-10-31; #471 6537983807. Memory: judge-from-raw-outputs.

### R-EVD-07 (active): A check's output is evidence for one exact tree; never edit while a background check runs.
- **Why:** a backgrounded check mounts the live worktree, so an edit during the run mixes trees.
- **How to apply:** run final checks in the foreground, or edit nothing until they end. If the tree changes, stop the run and its container, mark its folder SUPERSEDED, and rerun under a new folder.
- **Origin:** 2026-10-30. Memory: background-checks-read-the-live-tree.

### R-EVD-08 (active): Round, collector and mutant labels must be unused before launch.
- **Why:** a reused round label silently overwrote an old round (#468).
- **How to apply:** refuse the launch if the label's folder or output exists, and chain the launch on that check. Include the base commit in the label. Read the round's own finish times before quoting a figure from it.
- **Origin:** 2026-10-26 to 2026-10-28; #468. Memory: unique-round-labels.

### R-EVD-09 (active): An evidence read must not perturb its subject.
- **Why:** a provenance read with `importlib.util.find_spec` imported the package and wrote bytecode, even in isolated mode (#389).
- **How to apply:** locate modules with `importlib.machinery.PathFinder.find_spec`. Record cache counts before and after; any new `__pycache__` is a STOP. Disclose a defective run, keep it, and rerun as r2.
- **Origin:** 2026-10-23; #389. Memory: a-provenance-read-can-perturb.

### R-EVD-10 (active): When porting a packet or a tool, audit every literal and re-measure every bound for the new subject.
- **Why:** ported executors carried a hard-coded expiry, and thread and run bounds measured on the old subject (#462, #470).
- **How to apply:** search the port for every date, time, id and number, and classify each. Re-measure page sizes, counts, windows and expected sets. Keep the builder's asserts. Add in-place mutation controls, and boundary controls one second before, at and after each expiry.
- **Origin:** 2026-10-27 to 2026-10-30; #462, #470. Memory: audit-every-literal-when-porting, a-ported-shape-carries-its-subjects-bounds.

### R-EVD-11 (active): Before relaying an agent's recommendation or decision request to the Owner, verify its facts against the live record.
- **Why:** on 2026-11-11 the supervisor relayed a portfolio batch that misdescribed 6 of 7 pull requests and recommended closing two of them on false grounds. An external review caught it (#325 6805973317, Incident 19). A relay lends the relayer's credibility to the claim.
- **How to apply:**
  - Read the real facts (titles, heads, linked items, and the mechanical evidence the policy requires) and include them in the relay.
  - State plainly when evidence is missing.
  - Design decider inputs so that they carry subject facts. Untrusted text is quoted and length-capped, but not omitted.
- **Origin:** 2026-11-11; #325 6805605998, 6805973317. Memory: verify-facts-before-relaying.

## 9. Gates, guards and lessons

### R-GATE-01 (active): Before a consequential call, classify it and bind it in a GitHub record, reusing the last accepted call shape.
- **Why:** a newly composed merge shape was re-sent in auto mode, and questions were asked only in the session (#444). The Owner ruled that Gnostoa must progress autonomously through authorized routine work (#429 6301470452).
- **How to apply:**
  - Classify: (a) an ordinary authorized effect; (b) missing Gnostoa approval or assurance; (c) needing host interactive permission; (d) facing a concrete host or policy refusal.
  - Bind the actor, target, head and expected state, approved operation, intended effect, required checks, host interface and helper provenance, in the GitHub record first.
  - Reuse the last accepted call for that effect, adapting only the PR, head and branch. For a merge, keep the inline approval, seal and head checks. A new shape needs admission.
  - No blanket Manual mode. One denial stops that goal: no resend, rewording, other actor, tool or route. Continue other work.
  - No feedback-loop blockers: no ACK of an ACK, no needless Owner round. Keep native evidence apart from host-reported evidence.
- **Origin:** 2026-10-20 to 2026-10-21; #429 6301470452; #444 6298364956. Memory: effect-point-checklist, reuse-the-accepted-merge-shape.

### R-GATE-02 (active): A gate is its own step: run it, read it, then act in a later call.
- **Why:** a direction gate chained with a push pushed past a PAO advisory (#428). A claim of byte identity was posted while the chained check printed False (#463).
- **How to apply:** run the direction gate (Owner, Router and PAO comments since the last read, on the PR and the route issues) alone, and read it. Chain only checks that exit non-zero on failure. Re-read bot-edited state right before a claim.
- **Origin:** 2026-10-13 to 2026-10-26; #428; #463 6409118878. Memory: gate-is-its-own-step, gate-a-post-on-the-check-result.

### R-GATE-03 (active): Bind every promise and every carried decision in the hashed preimage.
- **Why:** the Owner accepts a fingerprint, not prose. A promised cap was unbound (PAO 6414533149), and a merge packet's guard missed a cutover the merge performed (#461).
- **How to apply:** list every number, cap, identity and condition in the prose, and assert each is a preimage field the scripts enforce. Mutation-test the prose. List what the merge actually does, and make each Owner decision it carries a required field that the guard checks.
- **Origin:** 2026-10-26 to 2026-10-28; #461; #389 6414533149. Memory: bind-every-promise-in-the-preimage, bind-every-decision-the-effect-carries.

### R-GATE-04 (active): A lesson is closed only with a mechanical guard, an English record in Gnostoa and a memory note.
- **Why:** the same mistakes recurred because they were "closed" only in memory (Owner, 2026-11-10).
- **How to apply:**
  - Without a guard, mark the lesson OPEN in the lessons ledger, and build the guard next.
  - Live guards include the publish gate (language, attribution, disclosure), a tool-call hook that refuses direct posts and unguarded pilot applies, the stall detector, and the pilot apply gate.
  - Owner (2026-11-10, in English translation): "Record this too, so that we cannot bypass it."
- **Origin:** 2026-11-10; #325 6777125733. Memory: close-lessons-with-a-guard.

### R-GATE-05 (active): Every supervisor memory rule is also recorded in Gnostoa, and a guard lists any that are not.
- **Why:** a supervisor's memory lives on one host and is lost at a handoff. The Owner directed that every rule be recorded in Gnostoa (2026-11-11, in English translation): "All the rules you have in your memory must also be recorded in Gnostoa, so that in a future handoff they are not lost."
- **How to apply:**
  - Keep the rulebook (the index and its four theme files) and a manifest that maps each memory note, by digest, to its rule ids.
  - At every check-in, run the memory-export guard. It reports NEW and CHANGED notes.
  - Write each reported rule in English with no host details, append it as an addendum, update the manifest, and publish the addendum.
  - The rulebook is admitted into Gnostoa as a knowledge file linked from AGENTS.md (Ariadne queue row 1).
- **Origin:** 2026-11-11; #325 6805345513, 6805346585. Memory: memory-rules-exported-to-gnostoa.
