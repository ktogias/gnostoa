---
type: Source
title: First-publication provider audit snapshot
description: Evidence-bounded review of the exact source candidate and GitHub surface that would be exposed by Gnostoa's first repository publication.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-15T00:00:00Z"
sources:
  - id: gnostoa-repository
    resource: https://github.com/ktogias/gnostoa
    title: Gnostoa repository
  - id: publication-baseline-work-item
    resource: https://github.com/ktogias/gnostoa/issues/1
    title: Prepare the Gnostoa publication baseline
  - id: accepted-publication-baseline
    resource: https://github.com/ktogias/gnostoa/pull/2
    title: Prepare the Gnostoa publication baseline
  - id: retained-durable-context-research
    resource: https://github.com/ktogias/gnostoa/pull/4
    title: Add durable task context and explicit handoffs
  - id: cumulative-publication-candidate
    resource: https://github.com/ktogias/gnostoa/pull/23
    title: Bind Python installs to reviewed wheel hashes
  - id: cumulative-candidate-verification
    resource: https://github.com/ktogias/gnostoa/actions/runs/31873612181
    title: Exact-head cumulative verification run
x-project-knowledge:
  id: kit.assessment.first-publication-provider-audit
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /project/gnostoa.md
    - kind: references
      target: /assessments/gnostoa-self-dogfood-bootstrap-assessment.md
    - kind: governed-by
      target: /decisions/0013-defer-provider-enforcement-while-private.md
    - kind: governed-by
      target: /decisions/0014-strengthen-gnostoa-self-governance.md
    - kind: verified-by
      target: /runbooks/prepare-first-publication.md
---

# First-publication provider audit snapshot

## Result

The cumulative source candidate is technically credible and no current
high-confidence credential or developer-local-path exposure was found in the
inspected provider surface. Repository visibility nevertheless remains
**NO-GO** at this snapshot because provider currentness, disclosure acceptance,
name-risk disposition and the visibility/protection transition are not yet
complete.

This is a dated, correlated project audit. It is evidence for a later owner
decision, not an independent security, legal or semantic approval.

## Exact basis

The provider and repository were inspected on 2026-08-15 before the
publication-cleanup candidate was committed.

| Item | Exact observed state |
|---|---|
| Default branch | `main` at `3adbbbfcc313fe23e29e68e31803f239c8cc3fa8` |
| Cumulative candidate | PR #23 at `049446b4bfe27103da2d6a9f43531e621cfcbd80` |
| Cumulative comparison | 21 commits, 106 changed files, 9,094 additions and 839 deletions; candidate is 21 ahead and 0 behind `main` |
| Accepted inner baseline | PR #2 head `2b0945c2c2882fb4cf35a5e7e08ad3134addacf6`, contained in the PR #23 ancestry |
| Separate research branch | PR #4 head `dfad73f17760b2e548e0066dee7904dab94ccb1e`, conflicting and outside the cumulative candidate |
| Repository visibility | Private |

Any new cleanup commit, provider-body edit, branch update, visibility change or
artifact expiry changes this basis and requires affected reconciliation. The
snapshot must not be reused as a final GO record for different bytes or a
different provider surface.

## Technical evidence

- `git diff --check`, policy, fast, regression and smoke checks passed on the
  exact cumulative candidate; 95 of 95 tests passed.
- Ruff formatting/lint and strict mypy reported zero diagnostics.
- GitHub Actions run 31873612181 passed all five declared jobs against the
  exact head and uploaded 13 content-addressed reports.
- The uploaded report records 67.59723964868256% branch-aware `tools/`
  coverage against a 65% floor, 7 of 7 runtime and 67 of 67 development wheel
  identities admitted, zero known reported vulnerabilities and zero tracked-
  tree secret candidates.
- Wheel and source-distribution candidates installed cleanly against the
  explicit source-binding contract and produced identical declared results.

These results support a bounded source candidate. They do not establish
independent semantic review, package provenance, production readiness or
security certification.

## Provider inventory

| Surface | Observed state |
|---|---|
| Remote branches and history | 11 remote branches and 25 unique commits reachable from them |
| Pull Requests | PR #2 plus PRs #16–#23 form one nine-PR stack; all are open drafts. PR #23 is mergeable and clean. PR #4 is a separate conflicting draft. |
| Work Items | 13 open Issues: #1, #3 and #5–#15; none currently has a `Now`, `Next` or `Research` provider label |
| Actions | 49 runs; four unexpired evidence artifacts; no Actions caches |
| Releases and delivery | No tags, releases, deployments or Pages site |
| Settings | No branch protection or rulesets, deploy keys, hooks, Actions secrets, Actions variables or environments were observed |
| Public metadata | Repository description is generic; homepage and topics are empty |

The current plan does not permit private-repository branch protection. This is
the bounded provider exception recorded by Decision 0013, not evidence that
the branches are protected.

## Exposure inspection

The audit inspected all current remote-branch history; the current tree; 23
Issue or Pull Request bodies; 425 top-level comments; all available Actions
logs; and the four retained Actions artifacts. It used path, credential,
private-key, token, binary and large-file pattern scans plus targeted manual
inspection.

No current high-confidence credential, private key or developer-local path was
found in those inspected surfaces. The retained artifacts also passed the
bounded Trivy secret scan. No blob larger than 1 MiB was found in current
remote history.

Residual disclosure remains explicit:

- the reachable commits expose the maintainer identity and author email when
  the repository becomes public;
- 13 existing provider comments contain Greek collaboration text, although no
  current Issue or Pull Request body does;
- the current head commit is unsigned and is not associated by the provider
  with a verified author or committer login;
- heuristic scans cannot prove absence of every secret or personal datum; and
- a stale local-only branch contains remediated pre-publication history with a
  developer-local path. It is not a remote/provider exposure and must not be
  pushed accidentally.

The owner must accept the intended identity and multilingual-history exposure
or authorize a separate remediation. This audit grants neither choice.

## Pull Request preservation and integration

`Superseded` must not mean discarded. The precise cumulative route is:

1. Treat PR #2 and PRs #16–#22 as **absorbed provenance** only after an exact
   comparison proves their selected commits and bytes are contained in PR #23.
2. Retarget one final cumulative candidate to `main` and preserve links to
   every absorbed PR, its discussion and its exact head. Do not delete their
   branches before successful integration and read-back.
3. Retain PR #4 as **Research input** for Issue #3. Its current work and review
   findings remain useful, but its conflicts and eight unresolved findings
   keep it outside the first-publication baseline.
4. Keep or close PR #4 only with an explicit parked-state summary, exact head,
   restart conditions and retained branch. Closing is lifecycle hygiene, not
   deletion or rejection.

This reduces the final merge to one cumulative source effect without erasing
the incremental review history.

## Change-control trace for the cumulative stack

All cumulative work belongs to Work Item #1. The final cumulative Change
Request must make the previously uneven provider trace explicit:

| Slice | Principal linked Decisions and rationale |
|---|---|
| PR #2 | Decisions 0005–0008 and 0012–0014: runtime boundary, verification, CI, public identifiers and bootstrap governance |
| PR #16 | Decisions 0009, 0013 and 0014: working name, private-provider exception and Gnostoa self-policy |
| PR #17 | Decisions 0013 and 0014: truthful public projection and bounded self-governance |
| PRs #18–#19 | Decisions 0005, 0007 and 0008: execution/source separation and release verification |
| PRs #20–#23 | Decisions 0007, 0008, 0010 and 0014: verification evidence, centralized CI, licensing evidence and self-policy |

This table links existing records; it does not make a draft Decision effective
or retroactively attribute new owner approval to an earlier PR.

## Publication findings and route

| Finding | Current disposition |
|---|---|
| Canonical project record and provider summaries describe the old PR #2/V4 state | Repair in the publication-cleanup candidate, then reconcile Issue #1 and the final cumulative PR body |
| Roadmap does not classify open work by delivery horizon | Repair with an explicit `Now`, `Next` and `Research` projection; provider labels remain a later provider write |
| Security and support routes are absent | Add truthful pre-release `SECURITY.md` and `SUPPORT.md` and link them from the front door |
| Repository description is generic and homepage/topics are empty | Set a bounded product description and relevant topics; leave the homepage empty until a real public site exists |
| PR #23 claims 67.72% coverage while its exact uploaded report records 67.59723964868256% | Correct the provider summary to 67.60% or the exact value |
| Earlier disclosure V4 covers only 3 branches, 15 commits, 25 runs and no artifacts | Replace it with an owner-reviewed disclosure bound to the current counts and final exact candidate |
| PR #4 has no clean first-publication disposition | Park it explicitly as retained Research work or complete its independent rework; do not merge it accidentally |
| Repository name has only preliminary exact-string screening | Complete Decision 0009's independent OBI, EUIPO/TMview and WIPO review with an explicit go, conditional-go or rename result |
| Protection is unavailable while private | Keep `main` unchanged; after an authorized visibility change, enable and verify protection and private vulnerability reporting before the cumulative merge |

Package metadata enrichment, authoritative release-smoke CI, OS/base-image
inventory, license-compatibility review and signed publisher provenance remain
artifact-release gates. They do not silently block a clearly bounded source
publication, and source visibility does not mark them complete.

## Exit criteria

A pre-visibility audit may report **GO to the visibility transition** only
when:

1. the cleanup is committed and the exact cumulative candidate passes the
   complete declared verification;
2. source, project record, Issue #1 and the final cumulative PR tell the same
   current story;
3. every exposed branch and open PR has a clear retained, absorbed, active or
   parked status; and
4. the owner has dispositioned the exact disclosure and Decision 0009's
   required independent name-review result is recorded.

That result does not itself authorize visibility. After a separate visibility
authorization, keep `main` unchanged while the provider transition is read
back. Integration remains blocked until:

5. branch protection, required current-head checks and private vulnerability
   reporting are configured and verified; and
6. anonymous-reader links and disclosure scans pass against the actual public
   surface.

This snapshot changes no visibility, branch, Pull Request, Issue, protection,
source integration or artifact publication state.
