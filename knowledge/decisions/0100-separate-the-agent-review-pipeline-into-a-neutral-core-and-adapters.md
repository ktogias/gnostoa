---
type: Decision
title: Separate the agent review pipeline into a provider- and agent-neutral core and adapters
description: Move the mention-review pipeline's rules into a provider- and agent-neutral core that reuses Decision 0086's subject vocabulary, behind small role ports, with a GitHub adapter, a Claude Code adapter and one shared hardened GitHub REST client merged from the five that exist.
status: draft
generated:
  by: anthropic/claude-opus-5-5
  at: "2026-10-03T00:30:00Z"
sources:
  - id: lineage
    resource: https://github.com/ktogias/gnostoa/pull/353#issuecomment-5961758337
    title: Architecture-inheritance lineage table for the pipeline (owner-approved)
  - id: lineage-amendment
    resource: https://github.com/ktogias/gnostoa/pull/353#issuecomment-5962081616
    title: Amendment 1, row 3 becomes a merge of the hardened GitHub clients
  - id: gate
    resource: https://github.com/ktogias/gnostoa/issues/15#issuecomment-5919462524
    title: Mandatory implementation entrance gate, architecture inheritance
  - id: rca
    resource: ../assessments/15-review-pipeline-abstraction-recurrence-rca.md
    title: Review-pipeline abstraction recurrence RCA
  - id: subject-pattern
    resource: ./0086-implement-useful-l1-as-protected-source-github-current-state-reconciler.md
    title: Provider-neutral core plus provider adapters
  - id: reviewdog
    resource: https://github.com/reviewdog/reviewdog
    title: reviewdog (MIT); role-specific CommentService and DiffService interfaces
  - id: pr-agent
    resource: https://github.com/The-PR-Agent/pr-agent
    title: PR-Agent (MIT); one broad GitProvider base class across many hosts
x-project-knowledge:
  id: kit.decision.0100.separate-the-agent-review-pipeline-into-a-neutral-core-and-adapters
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0086-implement-useful-l1-as-protected-source-github-current-state-reconciler.md
    - kind: governed-by
      target: /decisions/0096-relay-mention-reviews-through-a-protected-workflow.md
    - kind: governed-by
      target: /decisions/0098-post-claude-reviews-from-a-least-privilege-job.md
---

# Separate the agent review pipeline into a provider- and agent-neutral core and adapters

## Context

The mention-review pipeline was built through #326, #329, #330, #340 and #353. It now
holds about 4,150 lines on `main`, all under `.github/`. Its rules are written against
GitHub's and Claude Code's native vocabulary:
- **admission** against GitHub event names, `author_association` values and REST paths;
- **context collection** against the compare and contents payloads, plus an inline
  `gh api` shell step;
- **publication** against the Claude Code execution envelope;
- **delivery** against the issue-comments endpoint and `github-actions[bot]`.

So a second provider or a second agent would have to change shared logic or duplicate
it. The architecture-inheritance gate exists to stop exactly this, and it did not
activate. See the RCA, and Decision 0099 for the routing fix.

The owner admitted the whole-pipeline refactor inside #353, approved the lineage table,
and directed two things:
- merge the hardened GitHub REST clients, keeping the strongest elements of each;
- bring all of the coupled code on `main` under the refactor.

## Prior-art and reuse disposition

The lineage table on #353 is the disposition record, together with its amendment.
External prior art:
- **reviewdog** (MIT): small role-specific interfaces, a comment service and a diff
  service. **Adapted as the shape:** one port per role.
- **PR-Agent** (MIT): one broad `GitProvider` base class with dozens of methods across
  many hosts. **Rejected as the shape:** a broad provider class forces every adapter
  to implement everything, and it blurs which responsibility a host must satisfy.

No code is copied from either. Inside the repository:
- **Decision 0086's vocabulary is consumed.**
- **The useful-L1 and analyzer-readback GitHub clients are merged** with the pipeline's
  three into one.
- **No agent-dispatch contract is created.** #325 W0 owns it.

## Decision

1. **A neutral core.** The core comprises `tools/agent_review_model.py`,
   `tools/agent_review_paths.py`, `tools/agent_review_admission.py`,
   `tools/agent_review_context.py`, `tools/agent_review_base.py` (the base-revision
   collection, split from the context so each stays one subject),
   `tools/agent_review_report.py` and `tools/agent_review_delivery.py`. It is standard library only and implementation-
   private. It names no provider, no agent and no CI system. It owns every rule now
   spread through the scripts and the inline shell:
   - admission's binding, trust, digest, window and withholding rules;
   - the bounded context: artefacts, manifests, quoting, chunking and degraded-context
     notices;
   - the report record and the cross-job handoff;
   - public rendering and sanitising;
   - the post-once delivery algorithm;
   - path confinement.

   Each rule keeps the meaning that Decisions 0094 and 0096–0098 gave it. **This
   Decision moves rules; it does not change them.**
2. **The subject vocabulary is Decision 0086's.** A review subject is:
   - `provider{id, adapter}`;
   - an opaque `repository`;
   - an `item{kind, id}`;
   - a `change_request{kind, id}` when there is one;
   - exact `head_commit` and `base_commit`.

   Kinds and ids are opaque strings, chosen by the adapter.
3. **Small role ports, not a provider class.** The core consumes protocols, one per
   role:
   - a request source: re-read the relayed object, and read a change request's live
     revisions;
   - a change source: comparison, base listing and contents, commits, unified diff;
   - a comment sink: create, and find by marker and author;
   - a summary sink.

   An adapter implements only the roles its host needs.
4. **Adapters translate at the boundary.**
   - `tools/agent_review_github.py` translates GitHub's native events, items, Pull
     Requests, compare and contents payloads, and comment identity into the core's
     vocabulary.
   - `tools/agent_review_claude_code.py` translates the Claude Code execution envelope
     into the core's report record.
   - Mention tokens, trusted associations, the trigger's identity and the admitted
     events are adapter configuration, not core constants.
5. **One shared GitHub REST client.** `tools/github_rest.py` merges five clients:
   - `ci/review_github_current_state.GitHubRestClient`;
   - `ci/analyzer_readback.GitHubReadClient`;
   - admission's reader, the collector's and the poster's.

   It keeps the strongest element of each, as listed in the amendment:
   - the `api.github.com` allowlist on the request and on every redirect, with an
     unredirected credential;
   - a whole-operation deadline, with a cap on abandoned workers;
   - bounded response and error-detail sizes;
   - rate-limit classification, with bounded pauses;
   - retries for idempotent reads only;
   - bounded pagination that reports its coverage;
   - media-type selection and bounded streaming;
   - separate read and write error types.

   Every consumer uses it.
6. **Agent dispatch stays composition.** The Claude Code action step remains the
   Claude-specific wiring in `claude.yml`. The core defines no agent-invocation
   interface. When #325 W0 defines `AgentDispatchAdapter`, it consumes this core's
   request and report types; it does not re-implement them.
7. **Entrypoints are thin.** `.github/review-context/` holds only GitHub Actions
   composition. Each entrypoint reads Actions environment values, builds the GitHub
   adapter and calls the core. The inline context shell becomes one Python entrypoint.
   Steps run with `PYTHONPATH` set to the protected checkout, as `review-current-
   state.yml` already does.
8. **Delivered in stages inside #353.** Each stage is its own verified commit:
   1. delivery and the agent report;
   2. the shared GitHub client;
   3. admission;
   4. context collection;
   5. the neutrality falsifiers across the whole pipeline.

## Delivery status

Recorded per stage, so that this draft does not read as describing work not yet done
(CodeAnt on #353):

| Stage | Status |
|---|---|
| 1. Delivery and the agent report | **Delivered.** Core: `agent_review_report`, `agent_review_delivery` and `agent_review_paths`. Adapters: Claude Code, plus GitHub's comment sink. |
| 2. The shared GitHub client | **Delivered.** `tools/github_rest.py` serves all five consumers, with one falsifier per element and a mutant that each falsifier kills. |
| 3. Admission | **Delivered.** Core: `agent_review_model` (the subject vocabulary and the continuation marker) and `agent_review_admission` (every admission rule, the relay payload and the request artefacts). Adapters: GitHub's request source and step outputs, plus the Claude Code mention and line budget. The entrypoint composes them. A test-only second provider, with string ids, merge requests and a role vocabulary, is admitted and refused by the unchanged core for the same reasons; each rule has a mutant that a test kills. |
| 4. Context collection | **4a delivered.** The collection step's 310-line inline shell is one entrypoint, `collect_context.py`. Its rules are in the core's `agent_review_context`: the guarded collector, the commit-count notice, the refusal-only fallback and the empty-diff verdicts. GitHub's `CompareSource` reads the comparison, its pages of commits and the unified diff through the shared client. A test-only second provider's change source, with its own fields, refusal and vocabulary, is assembled by the unchanged core. **4b delivered.** The base collector's rules are the core's `agent_review_base`, over `ChangedFile`, `BaseRecord`, `Listing` and `Contents`, and a `BaseSource` port: the merge base, the rename source, the blob check, the budget, the deadline, the hunkless verdicts and the per-path manifest. GitHub's comparison schema and contents API are the adapter's (`read_comparison`, `ContentsSource`), and the collector's entrypoint is its transport binding plus composition, 1,632 lines down to about 300. A test-only second provider's base source is collected by the unchanged core. **4c pending:** the chunker moves to the core. |
| 5. Whole-pipeline falsifiers | Pending. |

Two facts from stage 2 are recorded rather than smoothed over:
- **A chronology violation.** The shared client was written before its element tests.
  The RED evidence was then reconstructed against the prior subject and labelled as
  reconstructed, not as test-first.
- **Three elements dropped in the first draft.** The consumers' own existing tests
  caught each one:
  - naming a malformed body at every layer (the collector's);
  - never chaining a validation error that can quote the credential (analyzer
    readback's);
  - a per-consumer, not process-wide, registry of abandoned workers (the collector's).

  Each was restored, and each now has its own falsifier and mutant.
- **A leak none of the five had closed.** An HTTP error carries its open response, and
  none of the clients closed it. Every retried or reported error held a socket until
  garbage collection. The extended profile surfaced it as a `ResourceWarning` in an
  unrelated test's output. The shared client now releases each error once it is
  classified, with a falsifier and a mutant.
- **An abandoned write was retried.** Bounding a whole exchange abandons its worker
  rather than stopping it, so a create that outlives its bound can still land. The
  read-back before a retry proves only that the comment does not exist yet. The client
  now reports an abandoned exchange as *in flight*, the GitHub adapter carries that
  into the core's vocabulary, and delivery stops instead of creating again (Codex on
  #353). Each layer has a falsifier, and the client's two have mutants. L1, which
  renames the client's errors, kept the fact too, and reports such a publication as of
  unknown outcome rather than as not published (CodeAnt on #353).
- **A rerun of only the posting job could post the review twice.** The report was
  bound to its own attempt, but the delivery marker took the posting job's, and the
  read-back started minutes before the job. So a rerun after an uncertain create
  searched for another marker in too short a window, and posted again. The marker now
  carries the report's attempt, and the read-back starts where the run did (Codex on
  #353). Delivery also reads back before its first create, not only after a failure,
  because a rerun is a new process: it resumes a delivery rather than repeating it
  (Codex on #353).
- **A write that reached the provider was reported as not applied.** A server error,
  a broken transport or a success answer that could not be read each left a write
  that may well have been applied. The client now marks such a write as of unknown
  outcome. Only a refusal, or a request never sent, leaves it known. L1 reports an
  unknown outcome as such, while its own refusals before writing stay "not published"
  (CodeAnt on #353).
- **A cap that held only for sequential use.** A worker was counted only once
  abandoned, so concurrent requests could all pass the check first. Workers are now
  counted from their start, under a lock (CodeAnt on #353), with a falsifier and a
  mutant.

## Verification

**Falsifiers.** Each one failed first:
- **Structure:** core modules import only the standard library and each other, and
  they carry no provider, agent or CI vocabulary. This is a guard, not an oracle.
- **A second provider:** a test-only adapter translates materially different native
  shapes into the core's vocabulary. It uses non-numeric change ids, another kind name
  and another trust vocabulary. The unchanged core then admits, assembles context and
  delivers with the same semantic outcomes.
- **A second agent:** a test-only adapter for another output format drives the
  unchanged publisher and poster.
- **The shared client:** each listed element has a test that fails when that element
  is removed.
- **Replay:** the structural guard is run against `main`'s coupled scripts and
  rejects them. This is post-hoc evidence, not RED chronology.

**Existing tests.** The existing hardening tests keep their meaning and are retargeted
to where each rule now lives. A test that pinned shell text pins the same property
in Python.

## Consequences

- A new provider means one adapter implementing the role ports. A new agent means one
  output adapter, plus composition. **Neither changes a core module.**
- The pipeline's rules can be read in one place, apart from the transport.
- The useful-L1 and analyzer-readback adapters share the merged client. This does the
  client part of #286, which is not claimed closed. The neutrality of
  analyzer-readback's core stays with #318.
- **Known limit: GitHub Enterprise Server.** The GitHub adapter pins `api.github.com`
  and validates run URLs against `https://github.com`. A GitHub Enterprise Server
  deployment would need both made configurable from the workflow's own `api_url` and
  `server_url`. That is another deployment of the same provider, out of this slice's
  scope: no such deployment exists here, and the pins reject forged identities
  (CodeAnt on #353).
- **Known limit: the unified diff is read within 256 MiB.** The shell's `gh api`
  read it without a bound. The shared client bounds every read, so a larger diff now
  fails the step, as any failure other than the provider's refusal does: only a 406
  reaches the lossy per-file fallback. Its whole exchange is bounded at 120 seconds.
- **Known limit: the repository-name pattern admits dot segments.** The GitHub request
  source's owner/name pattern, moved unchanged from the admission script, accepts
  `../r`. The value is GitHub's own `github.repository`, which cannot be a dot segment,
  so nothing reaches the gap. Tightening the grammar would change a rule, which this
  Decision does not do. It is recorded here, found by the stage-3 mutation pass.
