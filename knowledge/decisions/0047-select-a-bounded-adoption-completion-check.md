---
type: Decision
title: Select a bounded adoption-completion check
description: Select one non-authoring composite check for mechanically complete, artifact-bound adoption evidence while preserving semantic acceptance as an accountable-owner decision.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-26T11:14:07+03:00"
sources:
  - id: adoption-completion-gate-work-item
    resource: https://github.com/ktogias/gnostoa/issues/130
    title: Determine the smallest executable adoption completion gate
  - id: adoption-completion-gate-analysis
    resource: ../assessments/nextcloud-mail-adoption-completion-gate-analysis.md
    title: Nextcloud Mail adoption-completion gate analysis
  - id: post-remediation-mail-result
    resource: ../assessments/nextcloud-mail-post-remediation-fresh-rerun-result.md
    title: Nextcloud Mail post-remediation fresh rerun result
x-project-knowledge:
  id: kit.decision.0047.select-a-bounded-adoption-completion-check
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md
    - kind: references
      target: /decisions/0045-select-documentation-only-remediation-for-nextcloud-mail-adoption.md
    - kind: references
      target: /decisions/0046-select-fail-closed-existing-file-adaptation.md
    - kind: references
      target: /lifecycles/evidence-gated-capability-evolution.md
    - kind: references
      target: /assessments/nextcloud-mail-adoption-completion-gate-analysis.md
    - kind: derived-from
      target: /assessments/nextcloud-mail-post-remediation-fresh-rerun-result.md
---

# Select a bounded adoption-completion check

## Context

Four rejected Nextcloud Mail adoption attempts are recorded across three Work
Item cycles. Three mechanically substantive attempts — the baseline, #122 and
#125 — repeatedly left mechanically decidable completion evidence absent or
unbound. The separate #117 frozen fresh-agent rerun stopped before adoption
mechanics and exposed a route-activation failure. The final mechanically
substantive attempt consulted the exact A1 and narrow A2 guidance and improved
route orientation, existing-file preservation and Git representation. It still
omitted source/runtime-lock validation, retained no context artifact or hash,
failed to classify unavailable project suites, retained only partial evidence
binding and overstated completion.

The existing `check-runtime`, policy, bundle, context and Git mechanisms can
decide or directly acquire most of those facts. The observed gap is their
unreliable composition and binding at the post-authoring boundary. Real
ownership, provenance, project truth, owner acceptance and durable commitment
remain human-semantic oracle limits.

The accountable-owner prompt authorizes a draft mechanism selection only when
the evidence justifies it. The linked analysis establishes that threshold. This
Decision records the bounded selection for review; it is not implementation
admission or self-approval.

## Decision

**A. Select one composite completion check.** Select a future public command,
`knowledge adoption-check`, as the smallest mechanism justified by the repeated
evidence. It is invoked after the candidate adoption files are authored and
staged and before accountable-owner review. It is not an initializer, preflight
or adoption engine.

**B. Reuse existing mechanics.** The command must compose the existing
source/runtime-lock, change-policy, CI-policy, profile/bundle and bounded-context
mechanisms; derive project suite commands from the existing validated
verification manifest; and acquire exact Git candidate and submodule facts
directly. Its normal invocation derives conventional adoption paths and locked
identities from the project root, toolkit lock and verification manifest;
non-standard paths are explicit recorded overrides. It adds no project input
schema, owner default, vocabulary or alternative validation semantics.

**C. Bind evidence and fail closed.** The check must retain a deterministic
context artifact and hash, component outputs and numeric exits, exact
documentation/source/runtime identities, staged candidate diff, file hashes,
Git/submodule representation and one versioned JSON result plus SHA256SUMS. It
must never overwrite an existing evidence bundle or modify canonical project,
toolkit or index bytes. Required failures, blocked prerequisites and unrun
dependencies remain distinct; no required check may silently skip.

**D. Preserve the semantic oracle.** Exit `0` means only `READY FOR
ACCOUNTABLE-OWNER REVIEW`. The result always reports semantic owner review as
`REQUIRED` and durable adoption as `NOT DETERMINED`. The command has no flag
that can assert an owner, provenance, acceptance, truth or durable commitment.

**E. Keep subject identities distinct.** Documentation, toolkit source,
executing native/source-built/OCI runtime and declared OCI identity are
separate subjects. Locked, expected or caller-supplied identities are
declarations, never execution observations; they cannot independently produce
an identity or coherence pass. The check directly measures documentation,
toolkit-source and executing-runtime revision/public-surface identities wherever
mechanically possible. For OCI it reports the internally measured runtime
revision and public surface separately from the external declared digest, and
reports that digest `NOT OBSERVED` unless independently digest-bound evidence
is mechanically validated and bound to the execution. A differing
documentation and toolkit public surface or an unobserved required OCI digest
blocks the check; no caller override may manufacture compatibility. Native or
source-built execution remains valid when its actual subject is fully measured
and bound.

**F. Select exact failure semantics.** Reserve exit `0` for complete mechanical
evidence, `1` for an executed check or postcondition failure, `2` for an unsafe
or invalid invocation/internal error and `3` for a material unavailable
prerequisite or incoherent subject. Required project suite launch failures and
exit `126`/`127` are `BLOCKED`; other non-zero suite exits are `FAIL`.

**G. Require a separately admitted implementation and falsification.** A later
owner effect must classify and admit the exact public-CLI diff, establish the
focused RED cases named in the analysis, implement only the bounded command and
verify its public-surface/runtime impact. One later pre-registered fresh Mail
run must expect the absent PHP/Composer environment to yield exit `3` and a
retained `BLOCKED` result rather than adoption completion.

**H. Leave broader alternatives unselected.** Select neither no change nor
another documentation-only restatement because the eligible rerun repeated the
mechanical omissions. Do not select a separate preflight: it would not observe
final context, suite, Git or evidence state. Do not select an initializer or
generator: correct file preservation and gitlink representation were already
demonstrated without one, and generated structure would increase semantic and
overwrite risk.

## Consequences

- The command and `gnostoa-adoption-check/v1` output would be additive public
  compatibility surfaces. They require a new source/runtime release before
  general consumers can use them; immutable v0.1.2 remains unchanged.
- A source-built exact integrated candidate can falsify the mechanism before a
  release. Publication, version selection and OCI mutation remain separate
  owner effects.
- Project suites retain their existing commands and possible project-owned
  side effects. The wrapper snapshots Git before and after but is not a general
  sandbox or workflow engine.
- The evidence bundle supports bounded inspection; it is not canonical project
  knowledge, a generic receipt platform, provenance attestation or semantic
  acceptance.
- No implementation, Mail mutation, release, rerun, B3 or Decision-0036 result
  is authorized by this draft Decision.
