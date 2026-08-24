---
type: Decision
title: Prepare a bounded v0.1.2 B3-readiness candidate
description: Admit one normative source candidate that rejects ambiguous YAML, verifies the declared Python floor, pins the adopted OKF subject and reconciles current public projections without authorizing publication.
status: draft
generated:
  by: human:ktogias
  at: "2026-08-24T11:48:37Z"
sources:
  - id: b3-readiness-work-item
    resource: https://github.com/ktogias/gnostoa/issues/109
    title: Harden the public surface before the first B3 adoption run
  - id: okf-v0-2-immutable-spec
    resource: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/9a15b13ba996bb713b19e053ea744abee01c2714/okf/SPEC.md
    title: Open Knowledge Format specification v0.2 at an immutable revision
  - id: yaml-v1-2-2-spec
    resource: https://yaml.org/spec/1.2.2/
    title: YAML specification v1.2.2
x-project-knowledge:
  id: kit.decision.0043.prepare-a-bounded-v0-1-2-b3-readiness-candidate
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md
    - kind: references
      target: /contracts/public-inheritance-surface.md
    - kind: references
      target: /decisions/0042-accept-the-weather-note-cold-start-onboarding-result.md
    - kind: references
      target: /assessments/b3-independent-adoption-experiment-design.md
    - kind: references
      target: /assessments/first-publication-reputation-and-direction-assessment.md
---

# Prepare a bounded v0.1.2 B3-readiness candidate

Recorded by `codex/gpt-5` from the accountable maintainer's selection and
implementation authorization. The scope, exclusions and stop before merge,
tag or release are the maintainer's semantic choice; this record is faithful
transcription.

## Context

The published `v0.1.1` source and `linux/amd64` OCI identities remain the
current immutable consumer route. Subsequent cold-start evidence supported the
technical onboarding route and pre-registered the first real B3 methodology,
but B3 has not begun and no candidate project, owner or task has been selected.

Four bounded source defects remain material before that experiment:

- the shared YAML loader silently applies last-key-wins semantics to duplicate
  mapping keys in both standalone YAML and Markdown frontmatter;
- metadata declares Python 3.11 or newer while the authoritative current
  container route exercises Python 3.12;
- the three sources that ground Gnostoa's OKF choice point at mutable upstream
  `main`; and
- public navigation still contains projections from before the OCI publication
  and before the B3 pre-registration.

YAML 1.2.2 defines mapping keys as unique, and OKF v0.2 requires parseable YAML
frontmatter. Rejecting a duplicate is therefore selected as correction of
ambiguous invalid input, not as a supported-input migration. The actual parser
behavior still changes, so the source candidate is classified `normative` and
receives pre-implementation failing evidence.

## Decision

**A. Candidate.** Prepare one bounded **`v0.1.2` source/runtime candidate** from
protected-main subject `2046cbcd9927043c61d9b256d1aa84780e2b2c45` under
[Work Item #109](https://github.com/ktogias/gnostoa/issues/109).

**B. Duplicate mappings.** Make the canonical safe YAML loader reject duplicate
keys at every mapping depth. The same behavior applies to standalone YAML and
Markdown frontmatter because both are public inputs to the same loader. The
diagnostic identifies the duplicate and its source location without exposing
unrelated file content. Unique-key inputs, aliases already permitted by the
bounded loader, timestamp-as-string behavior and profile semantics remain
unchanged. Repeated explicit YAML merge keys are duplicates too and fail by the
same rule. One merge key, one merge whose value is a sequence and an explicit
key overriding a value inherited through one merge remain supported.

**C. Compatibility.** Treat duplicate mappings as invalid ambiguous YAML rather
than as a supported public input. No valid-input behavior is selected to change,
so public profile, change-control, CI-policy, schema and OKF version identifiers
remain unchanged. Increment the Gnostoa guardrail-coverage manifest for the new
automated coverage and record the stricter observed failure semantics in
compatibility guidance. If evidence shows a valid-input or broader compatibility
change, stop and reclassify before continuing.

**D. Python support.** Retain `requires-python = ">=3.11"` and the public
`Python 3.11 or newer` claim only by adding a bounded CPython 3.11 and 3.12
source-test matrix to centralized CI. The existing Python 3.12 container remains
the authoritative runtime, smoke and release path. The matrix makes no claim
for an untested interpreter, operating system or architecture. At the PR,
merge-group and protected-main boundaries, `regression` must run through an
`always()` route and explicitly fail unless `policy`, `fast` and the aggregate
Python-compatibility matrix all succeeded. One controlled intermediate Python
3.11 failure must demonstrate provider `regression` failure before the fault is
removed and the final exact head is rerun green.

**E. Immutable OKF subject.** Bind Gnostoa's adopted OKF v0.2 rationale and
reusable source references to upstream commit
`9a15b13ba996bb713b19e053ea744abee01c2714`. Add one small fixture that verifies
the implemented consumer boundary required by OKF v0.2: YAML frontmatter is
parsed, `type` is retained, unknown extension keys are preserved, and a bare
`verified` mapping remains consumable. This is a conformance sentinel, not a
vendored specification, schema registry or general OKF compatibility suite.

**F. Current projections.** Correct the front-door index, status and roadmap so
they describe the published `v0.1.1` source/OCI route and the actual B3 state:
methodology pre-registered, experiment not begun, candidate selection still the
next B3 owner subject. Provider labels may be reconciled only after authoritative
read-back and may not predict a future effect.

**G. Version metadata.** Align the Python distribution version and default
local OCI version label to `0.1.2` for the candidate. Do not rewrite the
immutable `v0.1.1` publication workflow, digest, tag, evidence or historical
documentation. Until a later provider effect is authorized and completed,
public consumer instructions continue to name `v0.1.1` and its immutable
digest.

**G.2. Executable candidate binding.** Because `tools/knowledge_common.py` is an
SB2 executable, bind the final exact PR head and tree to its changed paths,
public-surface digest, new per-file SHA-256, source/runtime/vendored digest
equality and runtime self-check through a Docker-capable provider route. Reuse
prior X3 source-binding evidence only after proving its mechanism unchanged;
otherwise replay `ci/x3_conformance`. Reopen and replay only the affected G3
parser boundary rather than claiming the earlier SB2 bytes are unchanged.

**H. Explicit exclusions.** Select no B3 project, outreach, execution or result;
no generator, DSL, alias, mutable image tag, `latest`, workflow engine or new
generic reusable evidence mechanism beyond the exact-candidate binding in G.2;
no package, OCI image or site publication; and no broader context-budget,
package-namespace, coverage or knowledge-lifecycle work.

**I. Effect boundary.** This Decision admits preparation and verification of a
branch and Pull Request. It authorizes **no merge, tag, GitHub Release, registry
mutation or Work Item closure**. Each such effect requires exact-candidate
evidence and separate accountable-owner authorization.

## Consequences

- Ambiguous mappings fail before they can silently replace canonical metadata.
- The declared Python floor gains direct source-test evidence without changing
  the released Python 3.12 runtime boundary.
- OKF adoption becomes reconstructable from an immutable upstream subject and a
  bounded local sentinel rather than from a moving branch.
- Front-door navigation stops contradicting the published artifact and B3
  pre-registration state.
- `v0.1.2` remains only a candidate until a separately governed release effect;
  `v0.1.1` remains the current released source and OCI identity.
