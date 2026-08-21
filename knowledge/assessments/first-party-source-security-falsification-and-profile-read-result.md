---
type: Source
title: First-party source-security falsification and profile-read result
description: Candidate-bound result of the bounded G3 first-party source-security falsification, the demonstrated profile-inheritance outside-authority read, and its remediation to an explicit project-root boundary.
status: draft
generated:
  by: agent:claude-opus-5
  at: "2026-08-20T23:30:00Z"
sources:
  - id: profile-read-boundary-work-item
    resource: https://github.com/ktogias/gnostoa/issues/74
    title: Confine profile inheritance to the project root
x-project-knowledge:
  id: kit.assessment.first-party-source-security-falsification-and-profile-read-result
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0033-confine-profile-inheritance-to-the-explicit-project-root.md
    - kind: references
      target: /decisions/0022-define-the-security-boundary-for-the-first-gnostoa-oci-publication.md
---

# First-party source-security falsification and profile-read result

**Candidate-time evidence.** Measured on `linux/amd64` only. Re-observe before any
publication. **No claim is made that Gnostoa is secure.**

## Subject

| | |
|---|---|
| Falsified candidate | `f524fc2b35cb14973a12c180d6ae7cd85eee93a4` |
| Falsified public digest | `sha256:b67f64b8965d782bab477dab0639990800e61dbee13b09a79cf764823d7249f1` |
| Base / CPython / bundled Expat | `python:3.12-slim@sha256:2c941e860699f878900b0edc2403613c234d4b32eda3cc9fa7036991a2a63c4a` / 3.12.14 / 2.8.3 |
| Supported execution surfaces | **11 unique callables** (12 console scripts = 1 dispatcher + 11 targets) |
| SB2 | **12 first-party security-relevant files** |

The 11 supported targets were re-enumerated as `validate`, `context-pack`,
`docs-build`, `check-guardrails`, `check-change-policy`, `check-ci-policy`,
`check-runtime`, `surface-digest`, `task-validate`, `task-project` and
`self-check`.

## What was surveyed

Across SB2: **0** `eval`/`exec`/`compile`, **0** `pickle`/`marshal`/`shelve`,
**0** `shell=True`/`os.system`/`os.popen`, **0** `tarfile`/`zipfile`/`extract`,
**0** `socket`/HTTP clients. `urllib` use is `urlparse`/`urlsplit` only. Two
subprocess call sites, both list-form: `git` (literal argv plus an
operator-chosen root) and `sys.executable -m mkdocs` (temp-dir config).

`KnowledgeLoader` is a verified `yaml.SafeLoader` subclass; four
object-construction payloads (`!!python/object/apply`, `!!python/name`,
`!!python/module`) were **rejected** with bounded errors. Option-injection and
command-injection probes against `git` found nothing. **No supported network
effect**, **no supported archive extraction**, **no credential handling** (all 31
credential-shaped matches are YAML lexer token classes, a `max_tokens` budget and
one CI capability name), and **no first-party privilege effect**.

These reduce attack surface. They do not by themselves establish sufficiency.

## F1 — the demonstrated defect

Profile `extends` is project-controlled input, and `_load_profile` resolved
parents with no containment. Measured pre-change, canary `G3-PROFILE-CANARY-8f31c2`:

| control | pre-change |
|---|---|
| **P0** no parent | loaded |
| **P1** documented project → pinned toolkit inheritance | loaded |
| **P2** relative escape `../../outside.yaml` | **loaded**, canary merged |
| **P3** absolute reference | **loaded**, canary merged |
| **P4** symlink parent → outside | **loaded**, canary merged |
| **P5** outside non-YAML | rejected, but **canary appeared in the error message** |
| **P6** `/etc/hostname` | opened and read, rejected only afterwards |
| **P7** inheritance cycle | rejected fail-closed |

Reproduced in the published runtime as non-root `kit`: a canary from outside the
mounted project was read and merged. Reachable from **three** supported
entrypoints — `validate`, `context-pack`, `check-runtime`. Disclosure to
context-pack output is bounded to `id`, `version`, `okf_version`; the read itself
is not bounded.

## Remediation

Decision 0033 binds inheritance to one explicit `project_root`: references must
be relative, the canonical target — after symlink resolution — must stay inside
the root, and containment is checked **before** the parent is opened.

Post-change, same controls: **P2, P3, P4, P5, P6 all refused, canary absent from
every result and every diagnostic.** Preserved: no-parent load, documented
`.knowledge → ../.knowledge-kit/core/profile.yaml`, module → project, multi-hop
in-root, in-root symlink, and cycle detection. All three supported entrypoints
refuse with no canary in output.

Focused replay leaves classification **A — blocked only by Markdown
owner-semantic / residual disposition**. This is not a final G3 disposition and
does not promote the experimental sufficiency model.

## Other findings, unchanged by this slice

**F3/F4 — Markdown outside-root existence oracle.** `resolve_target` applies no
containment and `validate_bundle` branches on `resolved.exists()`, so a
project-controlled link distinguishes an existing outside path from an absent
one; `../../../../../../etc/passwd` resolves to `/etc/passwd` and is accepted
silently. This is an **existence oracle, not a content read** — no bytes are read
or emitted. **Deliberately not fixed here**, because Gnostoa legitimately uses
cross-surface relative links and the authoritative Markdown reference boundary
needs its own owner disposition.

**F3 —** the maximum profile read authority was previously undefined; Decision
0033 now defines it. The Markdown reference authority remains undefined.

**F2 — none observed** in the bounded study or focused replay.

**F4 —** recursive YAML aliases produce self-referential structures without
error; `deep_merge` did not hang on one.

**F5 — outside the supported surface:** `quality_evidence.py`,
`release_smoke.py`, `requirements_lock.py` — shipped and importable but not
reachable from any supported callable. The only `urlopen` lives in the last of
these.

**Contract ambiguity, not a security finding:** `docs-build` is an installed
alias while MkDocs is absent from the published runtime and unpinned in
`runtime.lock`. It **fails closed** with exit 1. Not addressed here.

## Sufficiency model

The provisional S1–S8 boundary is **WORKABLE**: it proved falsifiable by
actually failing S5 on this candidate rather than being assumed satisfied. The
pre-remediation candidate **did not satisfy** it. The model remains
**experimental** and is not promoted to a durable "source is secure" Decision;
that requires a post-remediation replay and a separate owner disposition.

## SB2 post-fix baseline

Membership was re-derived from the dispatcher, the 11 supported targets and the
shared first-party code reachable from them. It is **unchanged at 12 files**:

| SB2 path | candidate SHA-256 |
|---|---|
| `tools/cli.py` | `ac9bb147308f26a0d0a4ad0267c934f5021c44527396eb98c7e6149b4c1d3898` |
| `tools/validate_bundle.py` | `b32f63bdb3937a5ad2836b80d648410989833786295d8cd0fe21a18facd40ded` |
| `tools/build_context_pack.py` | `54339d70f04824605a8e7bee0fb8bce02906523109e1c012a20eb312b9cac1cb` |
| `tools/build_docs.py` | `e22de87395da6ff5e32428ed9b8cfc123a3512136aeb12f939868fa68f049676` |
| `tools/check_change_policy.py` | `6659c3680ad5ec0ca325f9a4b41fda7ef71b8c8f31ea584624c0c53f5587e156` |
| `tools/check_ci_policy.py` | `9c0ba59484a81e6f9aa00296557e7b66ec698c1e6d44d9df8047563f4882484c` |
| `tools/check_guardrails.py` | `dd4839c528451421fa5757468fd4bbc7c9ea475325d22b9e630d884d0fce7ab9` |
| `tools/check_runtime_lock.py` | `15cc878aea0a1eda46af40e443f2d87f6123d8def1eb7d22cb1b05649b308c8a` |
| `tools/task_envelope.py` | `da5644815c1ed19d79f320c3c2758a4877f105d440d0a0206650ec8f92f06204` |
| `tools/self_check.py` | `c0f7c63107c941b5bbfc89d4399c5a197f9c0939c06e5b8012c3aeeaa9b54824` |
| `tools/knowledge_common.py` | `2d5a77af4d0a6b2bd1dcf3786e7ebacc1c06bc6cc0e07c2e69f0736e98515593` |
| `tools/repository_scope.py` | `a61fc494a84cad5cad6923f072dc05fd2edb41162cf45c7446eb05303d73e5c4` |

Five SB2 files changed: `knowledge_common.py` implements containment;
`validate_bundle.py`, `build_context_pack.py` and `check_runtime_lock.py`
propagate one bound root; and `self_check.py` now supplies the repository root it
already resolves. The other seven are byte-identical to the falsified source.
These hashes are re-binding evidence only, not a new public identity mechanism.

## Non-claims

Not claimed: that Gnostoa is secure; that all first-party security defects are
cleared; that G3 is complete; that the Markdown existence oracle is fixed; that
arbitrary filesystem access is impossible through every code path; legal
clearance; CPython residual clearance; OCI publication readiness; or
source-identity readiness.
