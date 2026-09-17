---
type: Decision
title: Make repository-root Ruff scope authoritative before candidate sealing
description: Use one repository-root Ruff domain with explicit generated-path exclusions and one project-owned style entry point shared by CI and pre-candidate checks.
status: draft
generated:
  by: openai/chatgpt
  at: "2026-09-17T06:10:00Z"
sources:
  - id: work-item-262
    resource: https://github.com/ktogias/gnostoa/issues/262
    title: Align Ruff configured scope with enforced CI coverage
  - id: empirical-ruff-rca
    resource: https://github.com/ktogias/gnostoa/issues/262#issuecomment-5696790428
    title: Empirical Ruff candidate-churn RCA and bounded implementation plan
  - id: independent-scope-readback
    resource: https://github.com/ktogias/gnostoa/issues/262#issuecomment-5698007823
    title: Independent confirmation that tasks/ escapes the current PR Ruff gate
  - id: ruff-0160
    resource: https://pypi.org/project/ruff/0.16.0/
    title: Ruff 0.16.0 project and configuration reference
  - id: pre-commit-462
    resource: https://github.com/pre-commit/pre-commit/tree/9767b6c8211a6bf683875a0afcf2b390457a4b66
    title: pre-commit v4.6.2 inspected source
  - id: pre-commit-462-license
    resource: https://github.com/pre-commit/pre-commit/blob/9767b6c8211a6bf683875a0afcf2b390457a4b66/LICENSE
    title: pre-commit v4.6.2 MIT license
  - id: ruff-pre-commit-0160
    resource: https://github.com/astral-sh/ruff-pre-commit/tree/cb8c523fd4835aba42af70f4cad5568db4df0b6c
    title: ruff-pre-commit v0.16.0 inspected source
  - id: ruff-pre-commit-0160-mit
    resource: https://github.com/astral-sh/ruff-pre-commit/blob/cb8c523fd4835aba42af70f4cad5568db4df0b6c/LICENSE-MIT
    title: ruff-pre-commit v0.16.0 MIT license option
  - id: ruff-pre-commit-0160-apache
    resource: https://github.com/astral-sh/ruff-pre-commit/blob/cb8c523fd4835aba42af70f4cad5568db4df0b6c/LICENSE-APACHE
    title: ruff-pre-commit v0.16.0 Apache-2.0 license option
x-project-knowledge:
  id: kit.decision.0081.make-repository-root-ruff-scope-authoritative-before-candidate-sealing
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0008-authoritative-tiered-continuous-integration.md
    - kind: governed-by
      target: /decisions/0062-require-proportionate-prior-art-and-reuse-review.md
---

# Make repository-root Ruff scope authoritative before candidate sealing

## Context

Issue #262 records a structural mismatch between the Ruff domain configured in
`pyproject.toml` and the domain enforced by ordinary Pull Request verification.
The current GitHub workflow runs:

```text
python -m ruff format --check tools ci tests
python -m ruff check tools ci tests
```

The extended quality-evidence collector separately repeats the same handwritten
`tools`, `ci`, `tests` path list. `tasks/gnostoa_orientation.py` is Python source
but is outside both lists. The independent read-back recorded on #262 confirms
that repository-root Ruff formatting detects that file while the ordinary PR
Ruff gate remains green. The pre-push hook runs only `./ci/verify fast`, so it
also does not reproduce the mandatory Ruff gate.

The defect therefore has two coupled parts:

1. the authoritative style domain is duplicated as caller-owned path lists and
   can silently omit a new Python-bearing path; and
2. deterministic normalization happens after a candidate is minted often enough
   to create avoidable exact-head churn.

The measured #262 window found seven directly proven Ruff-failing candidate
SHAs among 49 commits, with a partial-repair cascade in which one remote Ruff
report named two files but only one was normalized before the next candidate.
That evidence makes early local/agent feedback useful, but CI must remain the
non-bypassable verifier.

This is a bounded normal verification/convergence change. It does not alter
R2A semantics, release authority, review-assurance semantics, Phase-D evidence
or provider settings.

## Prior-art and reuse disposition

Reuse the already pinned Ruff 0.16.0 tool and its native repository-root file
discovery/configuration model. Ruff already supports linting and formatting the
current directory recursively and reads project configuration from
`pyproject.toml`. No formatter framework, daemon, service, GitHub App or new
Python dependency is needed.

The selected adapter is a tiny repository-owned shell entry point because the
repository already uses `ci/*` executable surfaces and Git hooks. Its purpose is
composition only: invoke the existing pinned Ruff commands in one order over
one subject. It must not grow into a general preflight/orchestration framework.

Alternatives considered and licensing disposition:

- keeping a shared explicit top-level include list was rejected because adding a
  new Python-bearing top-level path would still require updating a second scope
  declaration;
- `pre-commit` **v4.6.2**, inspected at commit
  `9767b6c8211a6bf683875a0afcf2b390457a4b66`, is MIT licensed. It was considered
  as a generic local-hook framework. That license is compatible with inspection,
  use and redistribution subject to its notice terms, but this slice does not
  copy, package, depend on or distribute it. It was rejected because it adds a
  separate dependency, configuration and installation lifecycle when Gnostoa
  already owns repository hooks and a pinned Ruff executable;
- `ruff-pre-commit` **v0.16.0**, inspected at commit
  `cb8c523fd4835aba42af70f4cad5568db4df0b6c`, is offered under MIT or
  Apache-2.0. It was considered as the Ruff-specific adapter for a pre-commit
  installation. Its available licenses are compatible with the intended
  evaluation and potential use, but this slice does not copy, package, depend on
  or distribute it. It was rejected because it would add an external hook
  repository/revision lifecycle on top of the already pinned Ruff dependency
  without removing the need for Gnostoa's provider-side authoritative check;
- a CI bot that formats and commits changes was rejected because it would mint a
  new, unreviewed SHA and recreate the exact-head invalidation this work is meant
  to reduce;
- a new standalone required `style` job is intentionally deferred until the
  small shared surface is proven useful; #262 does not need a CI topology
  redesign to close the scope defect.

The selected implementation reuses only Ruff, which is already present in the
exact development lock. The rejected alternatives contributed design evidence
only. No source or configuration from them is copied into Gnostoa, so this
Decision introduces no new third-party distribution, attribution or NOTICE
obligation.

## Decision

1. **Repository root is the Ruff subject.** All project-owned Ruff format/lint
   invocations for Gnostoa source verification operate on `.` from the explicit
   repository root rather than naming `tools ci tests` or another positive
   top-level allow-list.
2. **Separate Git candidate membership from Ruff-specific exclusions.** Ruff
   keeps `respect-gitignore = true`, so genuinely ignored, untracked local
   material is neither checked nor rewritten. Generated-output Git patterns such
   as `/context-packs/`, `/dist/` and `/site/` are anchored to the repository
   root, so a later nested source path such as `pkg/dist/` remains eligible for
   the candidate. Before Ruff runs, the shared style surface fails closed when
   `git ls-files --cached --ignored --exclude-standard` reports a tracked
   Ruff-relevant input. Because Ruff also honors non-Git `.ignore` files, the
   surface additionally compares Ruff discovery with and without ignore-file
   handling and intersects the difference with the Git-tracked tree. An ignore
   rule therefore cannot silently remove any committed Ruff input from
   verification, while ignored untracked material remains outside the subject.
   The Git guard enumerates the pinned Ruff default input classes, including
   Python, notebooks, Markdown and Ruff configuration TOML. `pyproject.toml`
   separately declares the
   explicit Ruff exclusions instead of inheriting broad default output
   basenames. Cache, VCS, environment and tool-state directories that are
   intentionally recursive remain recursive-name exclusions, while generated
   output roots use slash-containing root-relative patterns such as `dist/**`.
3. **Add one bounded `ci/style` surface.** Both modes first reject tracked Ruff
   inputs hidden by Git or other Ruff-recognized ignore rules. `ci/style --check`
   then runs formatter check followed by lint check. `ci/style --fix` applies
   Ruff's ordinary safe lint fixes, then formats the same repository-root subject,
   then proves that the resulting subject is format/lint clean. Unsafe fixes are
   not enabled by this surface.
4. **CI consumes the shared check surface.** The ordinary Python 3.12
   compatibility gate invokes `./ci/style --check` instead of embedding its own
   Ruff path list. CI stays check-only and never writes candidate source.
5. **Pre-push consumes the same check surface.** The repository hook runs
   `./ci/style --check` before its existing bounded verification. This is the
   advisory local-feedback layer defined by the tiered-CI pattern, not a
   substitute for completion verification. A skipped or bypassed hook satisfies
   no required check; provider CI remains authoritative.
6. **Quality evidence uses the same candidate/root/config scope.** The extended
   suite first consumes `ci/style --check`, including its tracked-input ignore
   guards. The collector may then invoke Ruff directly to retain structured JSON
   diagnostics, but its Ruff subject remains `.` and its additional exclusions
   remain derived from `pyproject.toml` rather than another positive path list.
7. **Normalize before candidate sealing.** Agent guidance requires
   `./ci/style --fix` before creating/pushing a Python-affecting candidate, then
   focused contract tests after formatting and diff inspection before the SHA is
   treated as a review subject.
8. **Keep the slice bounded.** Do not add mypy scope work, a generic preflight
   engine, formatter service, auto-commit behavior, new provider settings or
   #15 orchestration semantics in #262.

## Verification contract

The implementation must retain executable evidence that:

- the old `tools ci tests` positive Ruff scope is absent from the ordinary PR
  gate and extended quality collector;
- `ci/style --check` and `--fix` use the repository root and reject unknown
  modes;
- the pre-push hook and ordinary PR workflow consume `ci/style --check`;
- ignore rules exclude genuinely untracked local material while the shared
  surface rejects any tracked Ruff input that Git or Ruff discovery would hide;
- generated top-level outputs are ignored or excluded by root-relative patterns
  while identically named directories nested beneath a source path remain
  discoverable by both Git and Ruff;
- `tasks/gnostoa_orientation.py` is inside the resulting Ruff domain; and
- a future Python-bearing top-level path is covered automatically unless an
  explicit configuration exclusion is added and reviewed.

The existing #262 provider comments are retained as the pre-implementation
failing/characterization evidence: repository-root Ruff detects drift under
`tasks/` while the old per-change gate does not.

## Post-integration effectiveness assessment

Exact-head verification establishes that one candidate implements this Decision
correctly. It does not by itself establish that the change reduces delivery
churn or adds enough value to retain. After PR #272 is integrated, a later agent
or developer must use this bounded assessment instead of inferring value from a
green CI result.

### Hypothesis and baseline

The value hypothesis is that one early, repository-root Ruff decision moves
deterministic style repairs before candidate sealing, while preserving complete
tracked-input coverage and leaving ignored untracked material untouched. The
expected observable effect is fewer Ruff-caused mutations and exact-head reruns
after a candidate has first been presented for external review.

The pre-implementation characterization is the #262 window: seven directly
proven Ruff-failing candidate SHAs among 49 commits, including one
partial-repair cascade. Commits and Pull Requests are different units, so that
ratio is directional context, not a statistically comparable control group.
Retain it to identify the failure shape; do not use it to manufacture a causal
percentage improvement.

### Cohort and observation window

Start the observation window at the integration commit for PR #272. Assess the
first ten subsequently integrated eligible Pull Requests, with a checkpoint no
later than 60 calendar days after that integration.

A Pull Request is eligible when its first sealed candidate either:

- changes a path reported from that exact SHA, under the exact development lock,
  by the pinned
  `python -m ruff check --show-files --no-respect-gitignore .` discovery command;
  or
- changes `pyproject.toml`, Git/Ruff ignore rules, `ci/style`, the pre-push hook,
  the ordinary provider workflow or the quality-evidence Ruff integration.

The **sealed candidate** is the first exact SHA explicitly recorded in the Pull
Request as ready for fresh external review. If that identity is not recorded,
mark the entry as missing evidence; do not reconstruct a favorable boundary
from later timestamps.

If fewer than ten eligible Pull Requests exist at the 60-day checkpoint,
publish the available observations as `INSUFFICIENT`. Do not silently extend the
window or claim success. A separately admitted follow-up may continue the
measurement.

### Evidence to retain for each eligible Pull Request

Record one row per Pull Request with:

1. the Pull Request URL, integration SHA, sealed-candidate SHA and final SHA;
2. every mutation after candidate sealing, bound to its commit and provider
   evidence;
3. each mutation classified as `RUFF_REPAIR`, `OTHER` or `MIXED`, with `MIXED`
   counted conservatively as Ruff-related;
4. the number of CI and fresh-review reruns caused solely by each Ruff-related
   mutation;
5. any partial-repair cascade, where a known Ruff report is not fully repaired
   before the next candidate;
6. any tracked Ruff input that escaped the gate, correctly ignored untracked
   input that was rejected or mutated, or second ordinary-CI scope authority;
   and
7. provider-reported `ci/style` duration when available, reported as a range and
   median across comparable jobs only.

Retain links to provider runs, review requests and findings rather than relying
on a narrative recollection. A local hook has no telemetry, so count a
pre-sealing local catch only when the Pull Request retains explicit evidence of
it; otherwise record it as unknown. Do not attribute general review latency or
all SHA changes to this control.

### Metrics and decision rule

Aggregate at least these metrics:

- eligible Pull Requests observed;
- Pull Requests with at least one post-sealing Ruff-related mutation;
- total post-sealing `RUFF_REPAIR` and `MIXED` mutations;
- exact-head CI/review reruns caused solely by those mutations;
- partial-repair cascades;
- tracked-input escapes;
- ignored-untracked false rejections or mutations;
- ordinary-CI scope-authority drift; and
- comparable `ci/style` duration range and median.

Classify the result as follows:

- `VALUE_SUPPORTED`: all ten eligible Pull Requests are observed; no
  tracked-input escape, ignored-untracked false rejection or mutation, or
  ordinary-CI scope-authority drift occurs; no partial-repair cascade occurs;
  and at least nine of the ten Pull Requests require no post-sealing
  Ruff-related mutation. This supports the value hypothesis but does not prove
  that the hook alone caused the outcome.
- `VALUE_NOT_SUPPORTED`: the complete ten-Pull-Request cohort does not meet the
  `VALUE_SUPPORTED` rule. Preserve the observed technical successes and costs;
  do not rewrite a missed threshold as success.
- `CONTROL_FAILURE`: any tracked-input escape, ignored-untracked false rejection
  or mutation, or ordinary-CI scope-authority drift occurs. This overrides
  cohort size and requires a finding with evidence and a focused proposed fix;
  remediation still follows ordinary admission and change control.
- `INSUFFICIENT`: the observation checkpoint arrives without ten eligible Pull
  Requests, or evidence gaps prevent the decision rule from being evaluated.

The result must be written to
`knowledge/assessments/0081-repository-root-ruff-effectiveness-result.md` and
linked back to this Decision. It must bind the PR #272 integration commit, list
the full cohort (including exclusions), present the per-PR evidence table and
metric totals, state the classification and limitations, and keep any new
finding separate as **finding / evidence / proposed fix**. The assessment may
recommend retention, revision or removal, but it does not authorize a code
change by itself.

## Consequences

- A new Python-bearing top-level directory no longer needs a CI workflow edit to
  receive Ruff coverage.
- Agents and maintainers get the same deterministic style decision before push
  that CI will later enforce, reducing avoidable candidate generations.
- Formatting remains capable of changing source-shape proof surfaces; callers
  must still rerun focused tests after `--fix` rather than treating formatting as
  semantically invisible.
- Git ignore rules define which untracked local material is outside the
  candidate, while `pyproject.toml` declares additional Ruff-specific
  exclusions. Ruff-recognized `.ignore` files may also remove untracked local
  material from discovery, but a tracked Ruff input cannot cross either ignore
  boundary silently because the shared gate rejects it before formatting or
  linting.
- The explicit list deliberately re-declares recursive cache/VCS/environment
  exclusions needed by this repository while narrowing generated output
  basenames to root-relative paths. Maintenance of that list is visible review
  work rather than hidden default behavior.
- `--fix` no longer rewrites genuinely ignored, untracked local Python files.
- The ordinary workflow still performs Ruff inside its existing pinned Python
  compatibility environment. A separate fail-fast style job remains an optional
  later optimization, not part of this Decision.

## Non-goals

This does not change Ruff version, lint rule selection, mypy coverage, test
selection, branch protection, review policy, R2A trust boundaries, release or
publication behavior. It does not claim that every generated directory in every
future checkout is known today; it makes the repository's intentional exclusion
boundary explicit and mechanically testable.
