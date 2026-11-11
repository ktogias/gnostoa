---
type: Source
title: "Supervisor rulebook, runtime and architecture themes"
description: "Themes 4, 10, 11, 13 and 14 of the supervisor agent's handoff-safe rulebook (47 rules), copied from the published #325 records with two review corrections, and loaded by theme."
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
  id: kit.assessment.supervisor-rulebook-runtime-architecture
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0004-self-host-policy-guidance-and-knowledge.md
---

# Supervisor rulebook: runtime and architecture

Themes 4, 10, 11, 13 and 14 of the supervisor rulebook: 47 rules, copied unchanged from the published records [#325 6805345513](https://github.com/ktogias/gnostoa/issues/325#issuecomment-6805345513) and [#325 6805346585](https://github.com/ktogias/gnostoa/issues/325#issuecomment-6805346585), except two rules corrected in review (R-RUN-04 and R-SEC-03; see the index's [review corrections](supervisor-rulebook-index.md#review-corrections)). Each theme keeps its published number and each rule its id. Start at the [index](supervisor-rulebook-index.md) for the conventions, the other themes and the manifest of source notes.

Owner directions remain authoritative in their linked GitHub records; where a rule here differs from a linked record, the record wins. The review corrections named above are the exception: each replaces a published line of the rulebook's own source records that review found wrong, so for those lines this file applies.

## 4. Container-first and runtime

### R-RUN-01 (active): Container first, always: run all repository code in the AGENTS.md container route; native only as a recorded fallback that continues.
- **Why:** native host runs produced false failures and missed tools, and three review records needed correction (#305). Owner (2026-09-22, in English translation): "Why don't you bring up a container?" And (2026-11-10): "Container first. Not immediate failure when there is no container!"
- **How to apply:**
  - This covers tests, reviews, `ci/*` tools, the merge guard and repository scripts. Host pilot tooling is the only exception.
  - If the container route is unavailable, run natively, record the reason and continue. If tools or config are missing, fix the Dockerfiles.
  - Every subagent brief that runs repository code says: "Container first (Owner): run repository code in the AGENTS.md container route; native only as a recorded fallback."
- **Origin:** 2026-09-22 to 2026-11-10; #305, #489; #325 6776769134, 6777035587. Memory: run-container-route-by-default.

### R-RUN-02 (active): Bind each run to the code under review; development-container green is not runtime green.
- **Why:** the runtime image lacks the development working directory, PYTHONPATH and pip. A test run from `tests/` can import the image's installed tools instead of the checkout.
- **How to apply:**
  - For changes to `tools/`, `pyproject.toml` or the CLI, build the runtime through `ci/build-runtime`, and run `self-check` from a directory that is not a checkout, with no mount.
  - Set PYTHONPATH to the checkout for behaviour runs in the development image.
  - Read the provider's verification after every push.
- **Origin:** 2026-08-16 to 2026-10-31; #25, #353, #426, #460. Memory: dev-container-hides-cwd-bugs, behaviour-runs-need-the-checkout-on-pythonpath.

### R-RUN-03 (active): Prepare candidates exactly as AGENTS.md requires, and know its traps.
- **Why:** each trap cost a failed round (#320, #329).
- **How to apply:**
  - `prepare` needs HEAD to be the exact parent, with the delta uncommitted. After a Ruff fix, commit the prepared tree itself.
  - `ci/build-runtime` materializes only tracked paths: `git add` new files before `self-check`.
  - A bare 40-hex value in YAML trips the secret scanner. Use the repository's allowlist pragma with a reason.
- **Origin:** 2026-09-26 to 2026-10-10; #320, #329. Memory: gnostoa-candidate-prep-practicalities.

### R-RUN-04 (active): Verify locally in order: prepare, cheap gates, then the heavy suites one at a time; no local regression suite.
- **Why:** the same tests ran twelve times per round in one serial process, and a late failure cost a whole rerun. The Owner approved "proposal A" (2026-10-05).
- **How to apply:**
  - First prepare, and verify the exact prepared tree. Then `policy`, `security-fast` and `smoke`. Then `extended`, the runtime build with `self-check`, and the mutants, one at a time (R-RUN-07, R-LIVE-04).
  - Commit, push and seal only if all pass. Release the receipt either way.
  - The publishing script belongs in the repository, not on the host (R-ARCH-04).
- **Origin:** 2026-10-05 to 2026-10-12; #369, #370, #371, #374. Memory: verification-process-a.

### R-RUN-05 (active): Check the image before every round, and rebuild the development image after a lock change.
- **Why:** images can be pruned mid-round, after which every step exits 125. `extended` refuses an image built from an older lock.
- **How to apply:**
  - At round start, inspect the image id and stop if it is missing. Treat exit 125 as an infrastructure failure, and rerun under new labels.
  - Restore a lost tag only onto the identical image id; otherwise rebuild from the exact main tree.
  - After a lock change merges, rebuild before the next round, and point every script at the new image.
- **Origin:** 2026-10-27 to 2026-10-30; #467, #471. Memory: check-the-image-before-a-round, rebuild-dev-image-after-a-lock-change.

### R-RUN-06 (active): Mount absolute paths only, and stop orphaned containers yourself.
- **Why:** the shell can reset its working directory between calls, so a `$PWD` mount can bind another agent's tree read-write. Stopping a background client leaves its container running against the tree.
- **How to apply:**
  - Put the absolute clone path in every mount.
  - After stopping a docker-backed task, list the running containers with their mounts, and stop any that still mount the tree. Name long runs so they can be stopped by name.
- **Origin:** 2026-10-01 to 2026-10-17; #423. Memory: never-mount-pwd, taskstop-leaves-containers.

### R-RUN-07 (active): Protect host resources: no scratch on RAM-backed filesystems, one heavy job at a time, prune job copies.
- **Why:** clones in a RAM-backed temporary directory crashed the host with out-of-memory errors. Owner (2026-10-09, in English translation): "Clean [the temporary directory] now and don't write anything there! The machine keeps crashing with OOM!" Two parallel preparations were later killed and took unrelated workloads down. Runner job copies filled the disk.
- **How to apply:**
  - Keep scratch on disk, never in tmpfs or shared-memory mounts. Keep one disposable clone at a time.
  - Run one qualification round at a time, and no mutant or collector run beside a preparation. Check free memory and disk before long rounds.
  - After a runner's record is written, prune its job copies with the reviewed prune tool, dry run first.
  - Record a killed attempt; never hide it.
- **Origin:** 2026-10-09 to 2026-11-03; #408, #425, #478. Memory: never-write-to-tmp, one-qualification-round-at-a-time, prune-runner-job-copies.

### R-RUN-08 (active): Never `rm -rf` a variable path, not even a folder created moments earlier.
- **Why:** the user's ban is absolute. "It was just created" is the kind of exception the rule exists to remove (#471).
- **How to apply:** after a wrong copy, write to a new uniquely named folder and mark the old one superseded. Prune only through reviewed tools. Read every compound command for `rm` before sending it.
- **Origin:** 2026-10-30; #471. Memory: no-rm-rf-even-a-fresh-path.

### R-RUN-09 (active): Shape commands for the host's permission check: one external effect per command, script files, no inline `-c` scripts.
- **Why:** local refusals are rare and random (50 of 33,549 calls), but each one stopped a lane. Inline `sh -c` or `python -c` scripts, and loops of `docker run --rm` with inline scripts, are refused because the check cannot see inside them. The Owner allowed `docker run --rm` (2026-11-02).
- **How to apply:**
  - Never bundle effects, such as a reply plus a resolve. Push fast-forward by default.
  - Write probes as script files. Run container scripts with an explicit entrypoint and `python -I`.
  - In a non-interactive lane, avoid redirects and compound pipes, and write files from Python.
  - After a refusal, record it once on GitHub, mark that leg NOT_RUN, never reshape it, and continue independent work. For a removal-check refusal, ask the Owner for Manual mode and presence at the prompt.
- **Origin:** 2026-10-23 to 2026-11-11; #429; #389 6565877817; #325 6503687608, 6566845265. Memory: classifier-base-rates-and-command-shape, host-refuses-inline-c-scripts, headless-lane-bash-shapes, owner-allows-docker-rm.

### R-RUN-10 (active): Format the whole tree before a round, and replay the suppression scan (M13) after formatting.
- **Why:** one unformatted file makes the prepared tree differ from the commit, so the receipts never bind (#481). `ruff format` can move a justification comment off its marker line (#489).
- **How to apply:**
  - Run `ruff format --check .` on the whole tree before committing a candidate.
  - Keep marker lines within 88 characters, comment included. Replay M13 on the formatted diff, and expect zero unjustified markers.
- **Origin:** 2026-11-04 to 2026-11-10; #481, #489. Memory: unformatted-file-unbinds-receipts, ruff-format-moves-justifications.

## 10. Handoffs, waits and liveness

### R-LIVE-01 (active): Resume from durable state in the defined order, and look for newer turns before redoing work.
- **Why:** Gnostoa is designed so that a fresh actor resumes from durable records, not from conversation. A handover note can predate the last Implementer turn.
- **How to apply:**
  - Follow the Decision 0016 resume card: the card, `docs/roadmap.md`, the live issue and PR bodies, then the task envelope. Read every #14 and #15 entry since the last one read.
  - A provider-body digest is `sha256(body.rstrip("\n") + "\n")`.
  - After a restart, read the local status, runbook and handover first. Before acting, list the returns and dispatches since the handover, and the newest published round folders.
- **Origin:** 2026-11-09 to 2026-11-10; #12, #14, #15, #25; #325 6740754876, 6743051836; #389 6767954607. Memory: gnostoa-resume-route, maint-takeover-20261109, handover-may-predate-the-last-turn.

### R-LIVE-02 (active): Open routes are obligations: advance every read-only part before standing by.
- **Why:** reading a Router disposition as "nothing due" stalled #389 for an hour (Owner RCA 6167193206).
- **How to apply:** list each open route after any disposition. Post evidence replies the Router can bind, even without an assignment. Recheck the obligations on every watcher timeout. Never invent an effect.
- **Origin:** 2026-10-14 to 2026-10-23; #451; #389 6166109204, 6167193206. Memory: open-routes-are-obligations.

### R-LIVE-03 (active): At every external wait, put spare capacity on the highest-ranked independent ready job, and record it.
- **Why:** the Owner's standing addendum (#325 6664909896).
- **How to apply:** checkpoint the primary work. Record one line per checkpoint, telling queued, assigned, started and completed apart. Carry that line in each push or progress record.
- **Origin:** 2026-11-05; #325 6664909896. Memory: verified-work-during-waits.

### R-LIVE-04 (active): Remove cycle-time losses: prepare in the background, never wait unboundedly for reviewers, and end every handoff with `next:`.
- **Why:** measured round-time losses on #460 (Owner, #325 6396981523). Turns ended at milestones with queued work, and the session idled (#325 6399318182, 6498368703).
- **How to apply:**
  - Prepare in the background from the review results already available. A newly material finding supersedes the preparation.
  - Record a stalled reviewer as stalled; never make "all reviewers reported" a mandatory wait (Router 6397228124).
  - Run mypy at GREEN. Do not run heavy suites side by side. Never time stages from commit dates.
  - End every handoff with a `next:` line: either the authorized next step, started in the same turn, or one pending-task record (actor, subject, authority, next action, completion predicate).
- **Origin:** 2026-10-25 to 2026-10-29; #460; #325 6396981523, 6399318182, 6498368703. Memory: cycle-time-rules.

### R-LIVE-05 (active): Give every blocking wait one sanitized GitHub record at its start, and update it at resolution.
- **Why:** asking only in the session left the Router and the PAO blind (Owner, #441 6269039728). Owner (in English translation): "Look at your instructions. You must publish all your requests, acks, state and blocking notifications. What are you doing?"
- **How to apply:**
  - Post one marked comment on the PR or issue: the actor, the exact head, what ran and what was refused, the bounded command, a no-bypass statement, the requested decision and its surface, and the next actor.
  - Update the same record at resolution. No repeated status comments.
  - Host-only details stay local (R-REC-02). If publication itself is blocked, report PUBLICATION_BLOCKED in the session.
- **Origin:** 2026-10-19 to 2026-10-23; #445; #441 6269039728, 6269244801. Memory: publish-host-blockers.

### R-LIVE-06 (active): Every nudge and every liveness firing is an incident: record it, find the root cause and add a mechanical fix.
- **Why:** work must advance with no external message. A manual request to the Router, or a liveness firing, hides a missing mechanism (Owner, 2026-11-11, who also complained of "many idle minutes", in English translation).
- **How to apply:**
  - Before any guidance request to the Router, add an incident row to the lessons ledger and cite "Incident: #N". The publish gate refuses the request otherwise.
  - For each liveness firing, add a ledger row with the timeline, root causes, fix with its guard, and status. Check this at every check-in.
  - Prefer fixing the mechanism over nudging.
- **Origin:** 2026-11-11; #489; #325 6795066222, 6800366395. Memory: every-nudge-is-an-incident, rca-every-liveness-firing.

### R-LIVE-07 (active): Resume on your own after a usage-limit pause, and keep a recurring self check-in armed.
- **Why:** a paused supervisor must not need a human prompt to resume (Owner, 2026-11-10: there should be no need to write "continue").
- **How to apply:** keep a recurring check-in that reads the status and handover, re-arms the monitors, checks the Implementer and the Router/PAO, and advances the agreed order. Session-bound schedulers expire, so re-create them before expiry. A host-level mechanism is still an open item.
- **Origin:** 2026-11-10. Memory: continue-after-quota-without-prompt.

### R-LIVE-08 (active): Start a watcher from an API timestamp, and read the PR directly when it goes quiet.
- **Why:** a hand-typed start time 20 minutes late skipped every review and left the agent idle for 45 minutes (#422).
- **How to apply:** use the seal comment's `created_at` minus a minute, or a UTC time captured with the push. After a quiet timeout, read the PR once before waiting again.
- **Origin:** 2026-10-11 to 2026-10-12; #422 6129038544. Memory: watcher-since-from-api.

### R-LIVE-09 (active): A scheduled Actions cron is not a cadence: quote measured gaps, never "hourly".
- **Why:** an hourly cron on this repository fired about once every five hours (median gap 5.3 h, maximum 10.4 h).
- **How to apply:** re-measure from the workflow's scheduled runs, paginated, before relying on it in a liveness or recovery claim.
- **Origin:** 2026-09-21 to 2026-10-13; #407; #426 6143022975. Memory: github-cron-is-not-a-cadence.

### R-LIVE-10 (active): Consume only the signal versions read this turn for the current head.
- **Why:** dispatch manifests repeat a signal once per observed head. Consuming older copies claims reads that never happened (#490).
- **How to apply:** keep head-bound signals only when their head is the current head. Keep comment signals only when `<id>@<updated_at>` matches a live read made this turn. Never infer consumption from age.
- **Origin:** 2026-11-11; #490. Memory: consume-only-current-head-signal-versions.

## 11. Architecture, reuse and scope

### R-ARCH-01 (active): Before the first production edit, read every new #14/#15 entry, post the lineage table, and publish the Decision.
- **Why:** a 4,150-line provider-coupled review pipeline reached main without the lineage check, and the Owner had to restate the rule. An admission plus a RED is not enough to start editing (2026-10-31 slip).
- **How to apply:**
  - Read every #14 (Ariadne) and #15 entry since the last one read, paginated.
  - Order: selection and RED, then the lineage and Decision records, then edits. Run the behaviour baseline before editing.
  - Check provider and agent seams against Decision 0086's vocabulary and the existing adapters.
  - After a slip: stop, keep the diff read-only, and disclose it with times. Never call it test-first.
- **Origin:** 2026-09-30 to 2026-10-31; #14, #15, #325; #389 6543603713. Memory: architecture-inheritance-gate, decision-and-lineage-before-the-first-edit.

### R-ARCH-02 (active): Reuse before write: find the owning module and extend it; never copy.
- **Why:** six owned responsibilities were re-implemented in one round (#364). A shared execution rule existed in nine copies, and review rounds hardened only the newest. Owner (2026-10-04, in English translation): "Don't forget, in whatever you build, to create, reuse and extend the appropriate abstractions."
- **How to apply:** for each finding, ask which module owns the responsibility. A reviewer's patch marks the location, not the design. In the lineage table, an existing implementation is "factor", not "created".
- **Origin:** 2026-10-04 to 2026-10-05; #364, #365, #367. Memory: reuse-before-write, authority-execution-was-copied.

### R-ARCH-03 (active): A review-driven helper is new code: run the prior-art checkpoint first, and stop at the third hardening of one family.
- **Why:** helpers written as review fixes duplicated an existing owner and drifted, with four defects measured (Owner RCA, #365 6218126933).
- **How to apply:** any new top-level def in a production diff triggers the checkpoint. "Factor later" needs an Owner or Router admission. Notify the PAO at T1 and T2. Count hardenings from the first review-driven one.
- **Origin:** 2026-10-16 to 2026-11-06; #436, #480; #365 6218126933. Memory: review-fixes-are-new-code.

### R-ARCH-04 (active): Every reusable tool goes into the Gnostoa repository, never a temporary host location.
- **Why:** the admitted parallel mutant runner lived in a temporary directory and was lost (incident #425). Owner (2026-10-12, in English translation): "The runner MUST BE PART OF GNOSTOA AND NOT TEMPORARY ... STOP MAKING AND THROWING AWAY DERIVATIVES."
- **How to apply:** search the repository and its open PRs for an owner first. Restore a lost capability from the repository, and open a Work Item. Disclose a tool outside the repository as a regression. The move itself still needs admission.
- **Origin:** 2026-10-09 to 2026-10-12; #374, #380, #425. Memory: build-into-gnostoa-never-temporary.

### R-ARCH-05 (active): Everything lives in Gnostoa as a provider-agnostic core with per-provider adapters.
- **Why:** host pilot mechanisms became tied to specific providers, and could not move to CI runners or other providers (Owner, 2026-11-10, #325 6777216690).
- **How to apply:**
  - Provider types: the git host, the CI host, the model and agent runtimes, and the host runtime. Build on Decision 0006, `policy/guardrails.yaml` and the existing adapters.
  - Host tooling is interim and must name its Gnostoa port. The pilot apply gate refuses a design without a "Gnostoa port" section.
  - Keep cores free of provider names: `tools/review_reconcile.py` must not contain "github" anywhere, because a protected test reads its source.
- **Origin:** 2026-11-06 to 2026-11-10; #325 6777216690. Memory: everything-in-gnostoa-provider-agnostic, review-reconcile-is-provider-neutral.

### R-ARCH-06 (active): Stop when a fix needs a path the Owner did not admit, even with CI red and the fix obvious.
- **Why:** admitted and prohibited paths are the unit of authorization. A silent crossing cannot be reviewed.
- **How to apply:** finish what the admitted paths allow and verify it. Then stop, naming the path, why it is a real dependency, and the edit it would need.
- **Origin:** 2026-08-20. Memory: stop-on-unadmitted-path.

### R-ARCH-07 (active): Preparation admits REDs, characterization and evidence, not a local production implementation.
- **Why:** authoring a whole slice locally under a preparation route was recorded as unadmitted (Router 6539186276).
- **How to apply:** stop at the failing tests, the characterization and the analysis. Propose a bounded implementation step if it would de-risk the decision. Derive pass counts with the skips included.
- **Origin:** 2026-10-31; 6539186276. Memory: preparation-is-not-implementation.

### R-ARCH-08 (active): Scope a change from every reader: search bare names and every use of each constant.
- **Why:** tests call private functions by string name, so a search for `name(` misses them (#470). A "report-only" version bump also changed an inventory member's value (#389).
- **How to apply:** search the bare name across `tools/` and `tests/` before a signature change. Search every use of each touched constant, including emitted values, pinned literals and consumers. Run the whole module suite.
- **Origin:** 2026-10-23 to 2026-10-30; #470; #389 6372664518. Memory: grep-the-bare-name-before-a-signature-change, trace-a-version-constant-before-scoping.

### R-ARCH-09 (active): Include the known hidden scope couplings: pinned workflow-step digests and the merge-evidence import set.
- **Why:** a workflow step change failed a pinned digest outside the admitted envelope (#221). A new import into merge evidence forces three files, one of them an integration test with inherited findings.
- **How to apply:** put `tests/test_tools.py`'s digest line for the job in the envelope, and reproduce main's pinned value first. For a merge-evidence import, list `verification.yml`, the smoke digest in `tests/test_tools.py` and `tests/test_review_assurance_integration.py`, and count the test's findings as a cost.
- **Origin:** 2026-11-02 to 2026-11-10; #221; #389 6589968036, 6761333802. Memory: workflow-steps-are-digest-pinned, merge-evidence-import-forces-three-files.

## 13. Security and credentials

### R-SEC-01 (active): Agents hold only restricted tokens; Owner authority is exercised only in the Owner's own browser.
- **Why:** an agent token that can approve a deployment or administer the repository defeats the approval boundary (Owner decision, 2026-10-04).
- **How to apply:** at session start, check the token type, and probe that an admin-only endpoint answers 403. Never approve a deployment. Never automate the Owner's browser profile.
- **Origin:** 2026-10-04 to 2026-10-08; #15 5979363503. Memory: agent-credentials-boundary.

### R-SEC-02 (active): No token on a command line; keep observation on a read-only route, separate from effects.
- **Why:** a token in git's argv and JWTs in argv broke the runbook's host rules. The shell token pattern was refused, and all token effects were held (#439, #440).
- **How to apply:**
  - Authenticated git goes through the agent git wrapper. API calls go through the runbook's App and machine-user functions, with an on-disk temporary directory.
  - Watch with an in-process, read-only App watcher.
  - The retired routes and their incident history are in the linked records.
- **Origin:** 2026-10-15 to 2026-10-19; #436, #439, #440; 6251848713, 6254732878, 6256220085. Memory: git-fetch-through-agent-git, bstar-write-route, app-watcher, gh-execution-route-conflict.

### R-SEC-03 (active): Run credential-touching helpers isolated: `python3 -I`, outside any checkout, with no names that shadow the standard library.
- **Why:** a helper run from an untrusted PR clone imported the checkout's `json.py` (#400). A probe named `typing.py` shadowed the standard library for 126 modules (#389).
- **How to apply:** use `python3 -I`, and run from a neutral directory. `-P` alone still reads `PYTHONPATH`, so keep it for probe scripts that need `PYTHONPATH`, never for a credential-touching helper. Test helpers from a directory holding a planted `json.py`. Give helper scripts distinctive names. When many modules fail oddly at once, check the harness first.
- **Origin:** 2026-10-08 to 2026-11-02; #389, #400. Memory: helpers-never-import-from-cwd, scripts-never-shadow-stdlib.

### R-SEC-04 (active): Exercise a control against its own attack, with a narrow positive control.
- **Why:** three security controls on #327 failed to stop exactly what they named, while passing their own tests.
- **How to apply:** add the case the control exists to refuse, and assert the refusal. Show that the assertion fails when the control is removed. Make the mutation as narrow as the claim. Assert the observable effect.
- **Origin:** 2026-09-28 to 2026-10-29; #327, #330, #389. Memory: exercise-a-control-against-its-own-attack.

### R-SEC-05 (active): When a hardening round produces a new finding of the same class, remove the capability; read the dependency's security docs first.
- **Why:** an allowlist cannot constrain a shell, and a denylist cannot enumerate the unknown. Three escalations came from patching inside a flagged shape (#327).
- **How to apply:** ask which capability makes the class possible, and whether the work needs it. For a credential-bearing third-party Action, read its own `docs/security.md` at the pinned SHA before writing containment.
- **Origin:** 2026-10-06; #327, #369. Memory: remove-the-shape-not-the-instance, read-the-action-security-docs-first.

### R-SEC-06 (active): A credential boundary is where the secret is scoped, not what a candidate-editable YAML declares.
- **Why:** `permissions: {}` in an editable workflow is not a boundary (#340).
- **How to apply:** read the secret's scope (repository or environment) and the environment's deployment branch policy before any "cannot reach a credential" claim.
- **Origin:** 2026-10-01; #340. Memory: check-where-the-secret-lives.

### R-SEC-07 (active): A called workflow receives environment secrets only when the caller passes them by name.
- **Why:** an unpassed secret resolves empty with no error, so a fail-closed verdict silently denied (#426). The opposite claim reached a proposal (Router 6538593071).
- **How to apply:** name every secret the callee reads in the caller's `secrets:` (not `inherit`), with `required: true` in the callee. Prove it once live from the job log. Quote the provider's docs before claiming credential behaviour.
- **Origin:** 2026-10-13 to 2026-10-31; #426 6151068319; 6538593071. Memory: reusable-workflow-secrets, reusable-workflow-environment-secrets.

### R-SEC-08 (active): Command-line git config is only a default; use the environment controls Git reads first.
- **Why:** a repository-local `protocol.<name>.allow` beats `-c protocol.allow=never` (#446).
- **How to apply:** prefer `GIT_ALLOW_PROTOCOL=""`, `GIT_CONFIG_NOSYSTEM` and `GIT_CONFIG_GLOBAL`. Build each probe's adversary to re-allow what the defence denies, and measure each defence alone. State a Git version only from a primary source.
- **Origin:** 2026-10-21; #446 6317385619. Memory: command-line-git-config-is-not-an-override.

### R-SEC-09 (active): Calibrate a credential probe live, on both the granted and the refused path.
- **Why:** a type-violating probe body read 67 repositories as writable, because the API validates the schema before authorization (#364).
- **How to apply:** after any probe change, run the credential check live and read every row and scope entry. Send the exact body to a repository the token cannot write.
- **Origin:** #364. Memory: calibrate-both-paths.

### R-SEC-10 (active): After any credential change, run every step of the convergence checklist once.
- **Why:** the analyzer readback broke silently and went unrun for three days (2026-10-04).
- **How to apply:** record each step's result. Name a step that cannot run as a blocker. Prefer signals that arrive automatically over steps an agent must trigger.
- **Origin:** 2026-10-04 to 2026-10-07; #379, #384. Memory: recheck-the-checklist-after-a-credential-change.

### R-SEC-11 (active): The local secret scan reads tracked files only; name leak probes neutrally.
- **Why:** a new untracked test file escaped the pre-push scan, and a probe named like a secret fired the keyword rule (#418).
- **How to apply:** commit first, or scan in the prepared clone. Name probes like `LEAK_PROBE`, never with secret-like names, and say in a comment why the value exists.
- **Origin:** 2026-10-10; #418. Memory: secret-scan-reads-tracked-files.

### R-SEC-12 (superseded): Ref rulesets let only the admin role write refs; a new writer needs an Owner bypass entry.
- **Why:** a public repository with an always-on bot agent needed every ref write restricted (2026-10-07).
- **How to apply:** a "Cannot create ref" refusal means the actor is not admin; never ask for an app allow-list entry to fix it. Superseded: merges by R-MRG-02, and push identities by R-AUTH-07.
- **Origin:** 2026-10-07 to 2026-10-08; #383, #384, #388. Memory: ref-rulesets-admin-only.

## 14. Pilot operations

### R-PILOT-01 (active): Keep a single writer: the headless adapter is the Implementer; the interactive session is supervisor and fallback only.
- **Why:** two Implementers in one checkout would duplicate effects (plan, #325 6740754876).
- **How to apply:** the supervisor does not act on Router dispatches, push or post as the Implementer, or edit the checkout. It watches the stop rules (waiting loops, the no-op share, the daily cap, a second writer), the acceptance window and Owner messages, and falls back only on a stop rule.
- **Origin:** 2026-11-10; #325 6740754876, 6761055250. Memory: implementer-runtime-switch-20261110.

### R-PILOT-02 (active): The supervisor, its subagents and the Implementer share one usage pool: at most one heavy subagent, and the Implementer's critical path first.
- **Why:** heavy staging subagents starved the Implementer and stopped the #490 chain (2026-11-10 to 11).
- **How to apply:** run a heavy subagent only to unblock the critical path, and do small one-offs directly. Defer nice-to-have staging while the Implementer is mid-chain. After a usage-limit event, check that the Implementer lane relaunches.
- **Origin:** 2026-11-10 to 2026-11-11; #490. Memory: shared-claude-quota-with-implementer.

### R-PILOT-03 (active): Stop sewing and unpicking: freeze host tooling to agreed-behaviour restores and real bugs, verified on the live end-to-end path.
- **Why:** most pilot churn fixed the supervisor's own earlier restrictions (Owner, 2026-11-10: "Sew and unpick", in English translation). Owner (in English translation): "Implement them going forward. Do not introduce problems in order to fix them later! ... If another role or tool or wiring is needed to ensure it, let's build it."
- **How to apply:** add no new gates, brakes or restrictions without an open proposal the Owner approves. Exercise every host change on the real path (dispatch, turn, PR, merge) and on the end-to-end flow suite before applying it. Every design names the decisions it touches. Spend the effort on closing PRs.
- **Origin:** 2026-11-10; #325, #396, #487, #489. Memory: stop-sew-and-unpick.

### R-PILOT-04 (active): In-design pilot fixes that pass every gate apply without a fresh session approval.
- **Why:** fixes waited hours for approval while the adapter stalled (Owner, 2026-11-10).
- **How to apply:** allowed only when the change fixes a defect within an approved design, adds no capability, permission, credential or unit, passes RED, GREEN, a kill-check and the overlay suites, has a backup and a rollback, and gets one host-free #325 record. Anything new is still asked. Host tooling is only for autonomy blockers and safety brakes, and lessons go into Gnostoa early.
- **Origin:** 2026-11-10; #325. Memory: standing-approval-pilot-fixes.

### R-PILOT-05 (active): Never run pilot test suites in place: a verification run must not change the system it verifies.
- **Why:** in-place runs wrote the live pilot state and took its lock.
- **How to apply:** run pilot suites through the read-only overlay runner (a private namespace, no network, a fresh label per run). After an unavoidable in-place run, inspect the observation state and the next tick.
- **Origin:** 2026-11-10. Memory: pilot-tests-write-live-state.

### R-PILOT-06 (active): Before any runtime handoff, inventory the implicit duties in both directions, and transfer each with its brake.
- **Why:** simple tooling worked only because one expensive interactive agent integrated and damped everything implicitly (#325 6743051836).
- **How to apply:** list each implicit responsibility with its opposite: what it does, and what it refrains from. Name the component and the test that will carry each. Put the brakes in the provider-neutral dispatch. Add no new tooling generation without a measured net benefit.
- **Origin:** 2026-11-06 to 2026-11-09; #325 6743051836. Memory: runtime-handoff-inventory.
