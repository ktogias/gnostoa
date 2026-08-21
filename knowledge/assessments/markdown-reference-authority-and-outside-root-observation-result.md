---
type: Source
title: Markdown reference authority and outside-root observation result
description: Candidate-bound evidence for selecting and enforcing project-root authority over project-controlled local Markdown filesystem validation.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-21T19:18:08Z"
sources:
  - id: markdown-reference-authority-work-item
    resource: https://github.com/ktogias/gnostoa/issues/76
    title: Confine local Markdown references to the project root
x-project-knowledge:
  id: kit.assessment.markdown-reference-authority-and-outside-root-observation-result
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0034-confine-local-markdown-filesystem-references-to-the-explicit-project-root.md
    - kind: references
      target: /assessments/first-party-source-security-falsification-and-profile-read-result.md
---

# Markdown reference authority and outside-root observation result

**Candidate-time evidence.** Measured on `linux/amd64`. Re-observe before any
publication. **No claim is made that Gnostoa is secure.**

## Starting subject

| | |
|---|---|
| Protected main | `44055203721a85476b83bdfbcac241806d7cb111` |
| Public digest | `sha256:30df20ba9c9c7f3d7781f7cf15b35d7a83dbba69ac0e2074071ac8422e86f858` |
| Base / CPython / bundled Expat | `python:3.12-slim@sha256:2c941e860699f878900b0edc2403613c234d4b32eda3cc9fa7036991a2a63c4a` / 3.12.14 / 2.8.3 |
| Integrated-main provider run | `32495883659`: policy, fast, regression and smoke SUCCESS; extended SKIPPED |
| Profile F1 | remediated; 16 focused controls GREEN at entrance |

The entrance read found no newer released supported Python 3.12 image and no
new accountable CPython-attribution disposition. Decisions 0031-0033, X3 and
the three-way public-digest binding remained valid.

## Reference inventory and compatibility

The accepted read-only study enumerated **267 Markdown references**, including
**237 local references**, across the four supported self-check bundles:

| class | count | result |
|---|---:|---|
| K1 same-document fragment | 0 | fixture confirms no filesystem observation |
| K2 external URI | 30 | no local filesystem or network liveness check |
| K3 bundle-rooted `/...` | 0 | fixture confirms bundle-rooted semantics |
| K4 relative in-bundle | 203 | all valid |
| K5 cross-bundle/cross-surface in-project | 34 | all valid |
| K6 outside-project in current source | 0 | defect remained fixture-reachable |
| K7 directory target | 0 | fixture confirms `index.md` conversion |
| K8 symlink target | 0 | fixture confirms in-root and escaping behavior |
| K9 query/fragment suffix | 18 | all current cases external; local fixture semantics preserved |

The exceptional K5 set is bounded as follows:

- `guidance/guardrails/non-negotiable.md` references
  `policy/guardrails.yaml`;
- `guidance/workflows/bootstrap-new-project.md` references six files under
  `templates/`;
- `knowledge/assessments/gnostoa-self-dogfood-bootstrap-assessment.md`
  references `docs/core/adoption.md`;
- `knowledge/index.md` references `guidance/index.md`;
- `knowledge/runbooks/maintain-the-kit.md` carries three links into
  `guidance/`; and
- `knowledge/runbooks/review-publication-baseline.md` carries 22 links into
  `guidance/`.

O1 bundle-only authority would break all 34. O2 project-root authority breaks
none of the 237 measured local references. No documented supported use requires
local filesystem validation beyond `project_root`. O3 unrestricted host
filesystem authority therefore has no measured necessity, while O4 unvalidated
out-of-root local references has no coherent meaning under the current
broken-link contract.

## Pre-change falsification

Canary: `G3-MARKDOWN-TARGET-CANARY-76`. The Work Item replayed the material
baseline against exact starting main before implementation:

| control | pre-change result |
|---|---|
| M0 present in-bundle file | valid |
| M1 absent in-bundle file | broken-link issue |
| M2 present cross-surface in-project target | valid |
| M3 present outside-root regular file | **accepted** |
| M4 equivalent absent outside-root path | **broken-link issue** |
| M5 outside directory with `index.md` | **accepted** |
| M6 outside directory without `index.md` | **broken-link issue** |
| M7 bundle-rooted target | resolved below bundle, not host `/` |
| M8 external URI | no local observation or network request |
| M9 fragment | no local observation |
| M10 in-root symlink to in-root file | valid |
| M11 in-root symlink to outside target | outcome depended on outside state |
| M12 query/fragment suffixes | local file cleaning preserved |

This established E1 existence, E2 directory/type/`index.md`, and E3
canonical/symlink-target oracles. The earliest outside observation was
`Path.resolve()` through canonicalisation metadata, before `is_dir()` and
`exists()`. No target-content read was observed: E4 remained absent.

## Owner disposition and bounded implementation

The owner selected O2 project-root authority, S1 canonical in-root symlinks and
preservation of in-root directory-to-`index.md` behavior. Decision 0034 records
the normative rule.

The implementation is confined to Markdown validation. It cleans targets
without filesystem access, performs lexical containment, walks symlinks by
reading only in-root link objects, and permits `is_dir()` and `exists()` only
after the target is safely established in-root. An appended `index.md` receives
the same bounded symlink walk. Shared `resolve_target`, relation resolution and
context-pack graph semantics remain unchanged.

Focused tests instrument `lstat`, `readlink`, `stat`, `Path.resolve`,
`Path.is_dir`/`exists` through their underlying operations, and target
`read_text`. Fixture creation occurs before observation begins. For every
outside lexical or symlink escape, every validation-time filesystem path is
required to remain inside `project_root`; target-content reads are forbidden.

## Candidate replay and re-binding

The final source bytes were replayed before provider publication. The two new
same-bundle navigation links bring the candidate inventory to 269 total / 239
local links. Every original one of the 237 local references remains valid, and
the K5 cross-surface set remains exactly **34/34**.

| control | candidate result |
|---|---|
| M0 present in-bundle | valid |
| M1 absent in-bundle | existing broken-link error |
| M2 cross-surface in-project | valid |
| M3 outside present file | bounded project-root authority error |
| M4 outside absent path | same authority error as M3 |
| M5 outside directory with `index.md` | same authority error as M3 |
| M6 outside directory without `index.md` | same authority error as M3 |
| M7 bundle-rooted | valid beneath bundle; host-root state irrelevant |
| M8 external URI | no local filesystem observation or network request |
| M9 fragment | no local filesystem observation |
| M10 in-root symlink to in-root file | valid |
| M11 in-root symlink to outside target | authority error after only in-root link observation |
| M12 local query/fragment suffixes | existing cleaning preserved |

Instrumentation recorded **no outside-root `resolve`, `stat`, `lstat`,
`readlink`, directory or existence observation** for any refused target. The
present/absent, file/directory, directory-index/no-index variants are
indistinguishable through validation output. No target-content read occurred.

The 16 profile-boundary controls remain GREEN, including three supported CLI
routes and canary non-consumption. The four supported bundles validate, the 34
K5 links remain valid, and context-pack relation traversal remains GREEN.
`tools/knowledge_common.py` is byte-identical to the starting source, so shared
`resolve_target` and `relation_target_document` semantics are unchanged.

SB2 was re-derived by traversing first-party relative imports from the supported
CLI dispatcher and its 11 targets. Membership remains **12 files**; only
`tools/validate_bundle.py` changed, to add the Markdown-only authority ordering:

| SB2 path | candidate SHA-256 |
|---|---|
| `tools/build_context_pack.py` | `54339d70f04824605a8e7bee0fb8bce02906523109e1c012a20eb312b9cac1cb` |
| `tools/build_docs.py` | `e22de87395da6ff5e32428ed9b8cfc123a3512136aeb12f939868fa68f049676` |
| `tools/check_change_policy.py` | `6659c3680ad5ec0ca325f9a4b41fda7ef71b8c8f31ea584624c0c53f5587e156` |
| `tools/check_ci_policy.py` | `9c0ba59484a81e6f9aa00296557e7b66ec698c1e6d44d9df8047563f4882484c` |
| `tools/check_guardrails.py` | `dd4839c528451421fa5757468fd4bbc7c9ea475325d22b9e630d884d0fce7ab9` |
| `tools/check_runtime_lock.py` | `15cc878aea0a1eda46af40e443f2d87f6123d8def1eb7d22cb1b05649b308c8a` |
| `tools/cli.py` | `ac9bb147308f26a0d0a4ad0267c934f5021c44527396eb98c7e6149b4c1d3898` |
| `tools/knowledge_common.py` | `2d5a77af4d0a6b2bd1dcf3786e7ebacc1c06bc6cc0e07c2e69f0736e98515593` |
| `tools/repository_scope.py` | `a61fc494a84cad5cad6923f072dc05fd2edb41162cf45c7446eb05303d73e5c4` |
| `tools/self_check.py` | `c0f7c63107c941b5bbfc89d4399c5a197f9c0939c06e5b8012c3aeeaa9b54824` |
| `tools/task_envelope.py` | `da5644815c1ed19d79f320c3c2758a4877f105d440d0a0206650ec8f92f06204` |
| `tools/validate_bundle.py` | `7d728446c8a34e7515c626b1c3b8af6cfafee38318616a44a86303af3beb5ca1` |

Pre-provider local evidence: 6 focused Markdown authority tests, 16 profile
boundary tests, 7 bundle/context-pack tests and the complete 165-test unit suite
PASS. Container `policy`, `fast`, `regression`, `smoke` and the exact local
`extended` suite PASS. Extended evidence includes clean Ruff and mypy results,
165 coverage tests at 73%, exact-lock dependency audits with no known findings
at the measured time, bounded licence/SBOM/secret evidence and a successful docs
build.

Focused post-change classification: **A — Markdown residual remediated; no
known first-party S1-S8 defect or observation/binding gap remains.** This makes
the integrated candidate eligible for a separate final bounded G3 owner
disposition; it is not that disposition.

## G3 effect and non-claims

The focused replay found profile F1 GREEN, E1-E3 removed, E4 absent, all 34
baseline K5 links valid, relation semantics unchanged and no new bounded
first-party S1-S8 gap. The provisional model remains an evaluation boundary
until the separate owner disposition.

Not claimed: that Gnostoa is secure; that unknown vulnerabilities are absent;
that execution is an arbitrary-filesystem-proof capability; host or container
engine security; CPython residual clearance; legal clearance; source-identity,
deployable-artifact or OCI-publication readiness.
