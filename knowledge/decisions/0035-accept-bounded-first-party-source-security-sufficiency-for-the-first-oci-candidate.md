---
type: Decision
title: Accept bounded first-party source-security sufficiency for the first OCI candidate
description: Accept the bounded S1-S8 Gnostoa-self evidence boundary as satisfied for the exact measured first linux/amd64 OCI publication candidate, without creating a security certification or publication authority.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-21T22:41:09Z"
sources:
  - id: final-g3-disposition-work-item
    resource: https://github.com/ktogias/gnostoa/issues/78
    title: Record final bounded G3 first-party source-security disposition
  - id: integrated-candidate-provider-run
    resource: https://github.com/ktogias/gnostoa/actions/runs/32519748772
    title: Integrated provider verification for the exact accepted G3 candidate
x-project-knowledge:
  id: kit.decision.0035.accept-bounded-first-party-source-security-sufficiency-for-the-first-oci-candidate
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0022-define-the-security-boundary-for-the-first-gnostoa-oci-publication.md
    - kind: references
      target: /decisions/0031-accept-bounded-material-debian-security-uncertainty-for-the-first-oci-candidate.md
    - kind: references
      target: /decisions/0032-omit-composite-oci-licence-annotation-until-an-image-wide-expression-is-selected.md
    - kind: references
      target: /decisions/0033-confine-profile-inheritance-to-the-explicit-project-root.md
    - kind: references
      target: /decisions/0034-confine-local-markdown-filesystem-references-to-the-explicit-project-root.md
    - kind: references
      target: /assessments/first-party-source-security-falsification-and-profile-read-result.md
    - kind: references
      target: /assessments/markdown-reference-authority-and-outside-root-observation-result.md
---

# Accept bounded first-party source-security sufficiency for the first OCI candidate

Recorded by `codex/gpt-5` from the accountable maintainer's exact disposition.
The semantic choice is the maintainer's; this record is faithful transcription,
not another approval step.

Scope: **Gnostoa-self, first `linux/amd64` OCI publication candidate, exact
measured candidate only.**

## Context

The bounded G3 evidence model did not pass trivially. Its falsification first
identified a project-controlled profile-inheritance outside-authority content
read. Decision 0033 bounded that path to the explicit project root. Focused
replay then left Markdown validation with outside-authority existence,
directory/type and symlink/canonical-target observations. Decision 0034 bounded
that path to the same explicit project root without changing relation-target
semantics.

The integrated evidence records the two remediations, their focused replays,
the exact first-party source boundary and the exact runtime subject. This
Decision is the owner disposition over those records. It is not another
assessment or security implementation.

## Decision

### A. G3 scope

G3 addresses only **first-party Gnostoa source-security sufficiency for the
documented supported runtime**. It does not subsume CPython vulnerability
status, Debian vulnerability status, third-party Python package security,
image/legal/licence questions, the container engine or kernel, arbitrary
deployment configuration, OCI image reproducibility, registry identity or
permissions, provenance, signing, attestation, multi-architecture readiness or
production readiness. Those subjects retain their own authority and evidence.

### B. Supported runtime

Decision 0022's supported-runtime boundary is reused; no second threat model is
created. The G3 result applies to the documented default runtime, the non-root
`kit` user, documented Gnostoa entrypoint and usage, and the measured
`linux/amd64` platform.

### C. Durable S1-S8 evidence boundary

The previously provisional S1-S8 model is accepted as the durable bounded
**Gnostoa-self G3 evidence boundary for this first-publication use**:

**S1.** Documented supported first-party runtime entrypoints are completely
enumerated and deduplicated to unique underlying execution surfaces.

**S2.** Material externally influenced first-party boundaries reachable from
those surfaces are classified across parsing/deserialization, filesystem
read/path/symlink/write effects, subprocesses, environment/configuration,
network, archive handling, generated outputs, secrets and bounded
resource-failure behaviour.

**S3.** Existing deterministic controls are reused where they actually check
the property.

**S4.** Material boundaries receive focused falsification/control where
executable evidence is meaningful.

**S5.** No demonstrated supported-runtime first-party defect remains that
produces, through the measured boundary:

- arbitrary first-party code execution;
- unsafe deserialization;
- unauthorized command execution;
- shell or argument injection;
- unintended network effect;
- project-controlled outside-authority file read;
- material outside-authority filesystem observation;
- traversal write;
- symlink escape with unauthorized effect;
- unauthorized overwrite;
- secret disclosure;
- privilege expansion; or
- a small hostile input bypassing the documented failure contract through
  uncontrolled failure.

**S6.** No material first-party security property remains unclassified merely
because a bounded required observation could not be acquired and bound.

**S7.** Residual uncertainty remains explicit and is never translated into
`safe`, `secure`, `unaffected` or `vulnerability-free`.

**S8.** The result is candidate/subject-bound and is invalidated by material
change to first-party security-relevant source, a supported execution surface,
or a dependency/runtime change that materially alters a measured boundary.

### D. Exact candidate binding

The accepted result binds exactly to:

| Subject | Bound value |
|---|---|
| Protected source revision | `f3b9954dd72edb5f98167cb7f607ed24eb280a05` |
| Git tree | `cac29498d48792a3352eaf5f9cdbdb080f5f8577` |
| Public digest | `sha256:bdda49f6953efa3816b0d88ea26ee6738911152bf38800848444072701c55cd6` |
| Platform | `linux/amd64` |
| Base | `python:3.12-slim@sha256:2c941e860699f878900b0edc2403613c234d4b32eda3cc9fa7036991a2a63c4a` |
| CPython | `3.12.14` |
| Bundled Expat | `2.8.3` |

The public-surface digest is candidate evidence, not a complete source-identity
mechanism.

### E. Supported execution surface

The established enumeration records **12 installed console scripts mapping to
11 unique supported underlying execution targets**. Aliases are not inflated
into independent security surfaces.

### F. SB2 source membership

The exact first-party security-relevant SB2 membership is 12 files:

- `tools/build_context_pack.py`
- `tools/build_docs.py`
- `tools/check_change_policy.py`
- `tools/check_ci_policy.py`
- `tools/check_guardrails.py`
- `tools/check_runtime_lock.py`
- `tools/cli.py`
- `tools/knowledge_common.py`
- `tools/repository_scope.py`
- `tools/self_check.py`
- `tools/task_envelope.py`
- `tools/validate_bundle.py`

The per-file candidate digests remain authoritative re-binding evidence in the
integrated Markdown assessment. They are not an aggregate public identity.

### G. Evidence chronology

The model first falsified the candidate rather than assuming sufficiency:

1. Profile inheritance demonstrated an outside-authority content read.
2. Decision 0033 and its implementation remediated that F1.
3. Markdown validation still exhibited E1 existence, E2 directory/type and E3
   symlink/canonical-target observations outside authority.
4. Decision 0034 and its implementation remediated those observations.
5. The Markdown pre-remediation study measured 267 total references, including
   237 local references and 34 K5 cross-bundle/cross-surface references.
6. The integrated remediated candidate measures 269 total and 239 local
   references, preserves every original 237 local reference, and preserves the
   K5 set exactly 34/34.
7. Integrated replay on `f3b9954dd72edb5f98167cb7f607ed24eb280a05`
   records profile F1 GREEN; E1, E2 and E3 removed; E4 content read absent; all
   34 measured K5 links preserved; relation-target semantics unchanged; and no
   known material S1-S8 defect or observation/binding gap remaining.

This is falsification and candidate re-binding evidence, not a claim that a
scanner found nothing.

### H. Final G3 disposition

**G3 STATUS: SATISFIED FOR THE EXACT MEASURED CANDIDATE.**

For the exact measured supported first-party runtime subject, the bounded S1-S8
evidence envelope is satisfied and no known first-party G3 defect or material
observation/binding gap remains.

This does not mean Gnostoa is secure, vulnerability-free, certified, audited
safe or free of unknown vulnerabilities.

### I. Bounded residuals

- Unknown first-party vulnerabilities may exist.
- Bounded parser and resource behaviours observed by G3 are evidence, not proof
  of universal denial-of-service resistance.
- Shipped/importable maintainer-only modules outside supported
  first-publication entrypoints were not promoted into the supported-runtime
  subject merely because they can be imported.
- The installed `docs-build` alias and absent MkDocs published-runtime
  dependency remain a separate contract/packaging ambiguity, not a security
  defect silently cleared here.
- Third-party, runtime and legal residuals remain separately governed.
- OCI reproducibility, registry, provenance, signing, attestation and
  publication readiness remain separate unresolved gates and are not part of
  G3.

### J. Invalidation and re-binding

Invalidation is distinct from a SHA change. A later commit SHA alone does not
require every G3 measurement to be repeated.

A later candidate may re-bind without deep G3 replay only after explicit
subject read-back proves all of the following unchanged:

- SB2 membership;
- SB2 bytes and per-file digests;
- supported runtime execution surfaces;
- security-relevant runtime dependency behaviour; and
- measured authority and failure semantics.

Knowledge-only Decision records, navigation-only self-knowledge changes and
non-executable licence or NOTICE attribution changes may qualify, but unchanged
subject must still be verified explicitly.

Affected G3 evidence is invalidated by a material change to SB2 membership or
bytes, supported entrypoints, parser/path/subprocess/network/write/secret/
privilege behaviour, or interpreter/runtime dependency behaviour affecting a
measured boundary. Invalidation requires the **smallest affected replay**, not
an automatic complete re-audit.

### K. CPython and base refresh consequence

A later Python or base refresh is not automatically a first-party source
defect. It does change the interpreter/runtime dependency context and therefore
requires an affected G3 re-binding assessment. If the refreshed runtime
materially changes a measured first-party boundary, the affected controls must
be rerun before this G3 result can transfer. The result for
`f3b9954dd72edb5f98167cb7f607ed24eb280a05` does not transfer silently to a new
base.

### L. G3 is Gnostoa-self only

This Decision is Gnostoa-self first-publication governance. It is not a generic
security standard for adopters, a promised security level for every project
using Gnostoa, a reusable certification scheme or evidence of cross-project
transfer. Generic/adopter promotion would require separate transfer evidence
and a separate owner Decision.

### M. Other gates remain separate

Decision 0032 retains the **CPython incorporated-software attribution qualified
legal-review residual**. Decision 0022/J retains mandatory publication-time
security freshness, including current merged/unreleased CPython 3.12 fixes.

The following publication-preparation gates remain distinct: OCI image-digest
and reproducibility evidence; registry identity and permissions; provenance;
signing; attestation; multi-architecture scope if selected; and the public
publication claim and surface. They are not G3 defects, are not silently cleared
by G3, do not automatically invalidate G3, and are not automatically reasons to
block future immutable source-identity selection unless their evidence requires
source changes.

G3 no longer blocks the exact candidate, but source identity remains paused for
the still-unresolved source-defining gates.

### N. No publication authority

This Decision does not authorize source identity, a tag, a release, OCI or
package publication, registry mutation or production deployment.
`deployable_artifact` remains `false`.

## Consequences

- Final bounded G3 owner disposition is accepted for the exact measured
  candidate; the exact candidate subject satisfies it.
- Generic/adopter security guarantee: **none**.
- Security certification: **none**.
- G3 is no longer a source-identity blocker, while the distinct source-defining
  CPython/legal/freshness gates remain unresolved.
- No executable source, security mechanism, provider policy, public generic
  adopter contract, source identity or publication authority changes here.
