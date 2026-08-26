---
type: Workflow
title: Adopt an existing project
description: Introduce governed knowledge incrementally without legitimizing stale or contradictory legacy documentation.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-07-29T00:00:00Z"
x-project-knowledge:
  id: guidance.workflow.adopt-existing-project
  owners:
    - team:gnostoa-maintainers
  scope:
    - generic-guidance
  relations:
    - kind: governed-by
      target: /guardrails/non-negotiable.md
    - kind: depends-on
      target: /practices/source-authority-and-lifecycle.md
    - kind: references
      target: /reference/repository-layout-and-distribution.md
    - kind: depends-on
      target: /workflows/bootstrap-new-project.md
    - kind: depends-on
      target: /workflows/propose-review-merge-change.md
    - kind: depends-on
      target: /workflows/configure-continuous-integration.md
---

# Adopt an existing project

## Outcome

One real development workflow has a verified current-state knowledge slice,
clear source authority, visible contradictions and measured navigation value.
The adoption does not attempt a big-bang rewrite of legacy documentation.

## First verified adoption slice

First resolve the intended commitment through the
[adoption guide](../../docs/core/adoption.md). A **minimal evaluation** follows
the linked quick start and stops before repository-owned policy, CI or provider
maintenance is introduced. A **durable adoption** continues through this
workflow. If the commitment is unclear, keep it unresolved and stop rather than
silently choosing the larger surface. If accountable ownership is unknown, keep
the affected knowledge draft or unresolved and ask; do not invent a person,
team, provenance or acceptance.

For durable adoption, complete this bounded slice before expanding the full
procedure:

1. Select one pilot and bind the exact documentation and toolkit source subjects.
   Use the [bootstrap root and target map](bootstrap-new-project.md#roots-targets-and-identities)
   rather than reconstructing file placement from names.
2. Check source access, workspace state and required project tools, then identify
   the **actual supported execution route** that will run: native, source-built
   or immutable OCI. Record the observed route identity; a declaration alone is
   not execution evidence.
3. Author only the project-owned profile, lock, policy and smallest draft concept
   spine needed by the pilot. Preserve unknown facts as unknown.
4. Run source/runtime-lock, policy, profile and bundle structural validation
   through that route.
5. Run bounded-context generation for the pilot and retain the generated output
   and its identity. Follow its concept paths back to canonical project records
   for full evidence.
6. Run the project suites that the environment supports. Classify an unavailable
   required tool or suite separately as `BLOCKED`; do not report it as a pass or
   make it erase a distinct structural result.
7. Record the dimensions independently rather than collapsing them into one
   adoption status:
   - Structural validation: `PASS`, `FAIL` or `NOT RUN`.
   - Bounded context generation: `PASS`, `FAIL` or `NOT RUN`.
   - Project suites: `PASS`, `FAIL`, `BLOCKED` or `NOT RUN`.
   - Semantic owner review: `ACCEPT`, `CORRECT`, `REJECT` or `UNRESOLVED`.
   - Durable adoption: `YES`, `NO` or `DEFERRED`.

Only an accountable owner can accept the semantic content and durable
commitment. This slice is a concentrated entry to the existing procedure, not a
universal path and not a substitute for the linked bootstrap, verification or
provider details.

## Preserve existing project authority

Before writing any mapped target, inspect whether it already exists and
identify its project authority. A reusable template is source material for
adaptation, not authorization to replace an existing authoritative file.

If `AGENTS.md` exists and the authority to edit it is clear, preserve its
existing project-specific instructions, add only the missing Gnostoa routing
section, and retain unrelated content and ordering where practical. Record the
before/after diff or identities as adoption evidence. Never silently resolve
contradictory instructions. If a Gnostoa route conflicts with existing project
instructions, or authority to alter them is unclear, stop, preserve the
existing file, record the conflict and request accountable-owner resolution.

Apply the same inventory and no-blind-overwrite boundary to existing mapped
policy, CI and verification targets. This boundary does not imply that prose or
a reusable template can mechanically merge their semantics. The existing
unknown-owner and commitment stop, source/runtime-lock check and final staged
gitlink equality remain required in their owning steps; do not replace them
with file-preservation evidence. This documentation is a falsifiable control,
not a guarantee of agent compliance, and one later fresh rerun must measure its
predicted benefit.

## Mechanical completion evidence

After the bounded candidate is authored and staged, use a toolkit source or
runtime that actually contains `adoption-check` to bind its mechanical state
before accountable-owner review. The immutable v0.1.2 source and OCI artifact
predate this command and do not acquire it through later documentation.

From the project root, the normal native invocation is:

```bash
knowledge adoption-check \
  --execution-route native \
  --seed project.system.pilot \
  --output-dir ../gnostoa-adoption-evidence
```

Choose a new output path outside the project. The command derives the lock,
toolkit source, profile, policy, verification manifest, bundle and required
`fast` and `regression` commands from their conventional locations. Use the
documented path overrides only for a real non-standard layout, and use
`--documentation-root` when the exact guidance subject consulted differs from
the pinned toolkit source. Every override is retained as an input declaration;
it cannot prove execution or coherence.

The project-owned verification adapter remains authoritative for entering its
runtime. During each adoption-check suite attempt it receives
`GNOSTOA_ADOPTION_OBSERVATION_PATH` and
`GNOSTOA_ADOPTION_INVOCATION_BINDING`. To provide complete evidence, that same
invocation writes one closed
`gnostoa-project-runtime-observation/v1` JSON object through a temporary file in
the supplied directory and atomically installs the initially absent sidecar
without replacement. The object is at most 64 KiB, rejects duplicate or unknown
members, contains 1--16 unique identity items, and has this closed shape:

```json
{
  "schema": "gnostoa-project-runtime-observation/v1",
  "suite": "fast",
  "invocation_binding": "<GNOSTOA_ADOPTION_INVOCATION_BINDING>",
  "route_kind": "native",
  "runtime_identity": [
    {
      "kind": "native-executable",
      "role": "suite-runtime",
      "subject": "/absolute/path/to/executable",
      "value": {"sha256": "sha256:<64 hex>", "version": "<observed>"},
      "measurement": {"method": "executable-sha256-and-version-v1"}
    }
  ],
  "origin": {"kind": "project-adapter", "entry": "./ci/verify"}
}
```

The placeholder object is incomplete. The exact version-1 identity profiles
are:

| Route | `kind` / `role` | Exact `value` members | Exact measurement method |
|---|---|---|---|
| native | `native-executable` / `suite-runtime` | `sha256`, `version` | `executable-sha256-and-version-v1` |
| native | `dependency-lock` / `suite-lock` | `sha256` | `file-sha256-v1` |
| container | `oci-platform-manifest` / `suite-runtime` | `manifest_digest`, `manifest_media_type`, `configuration_digest`, `platform` (`os`, `architecture`) | `entered-container-platform-manifest-config-v1` |

A complete native observation includes the actual suite executables/toolchains
and every applicable dependency/toolchain lock. Executable subjects are
normalized absolute paths; lock subjects are normalized project-relative POSIX
paths. A complete container observation has exactly one printable entered
instance subject, one platform-specific OCI or Docker v2 manifest media type,
and the instance-to-configuration and manifest-to-configuration binding. Hashes
use `sha256:` plus 64 lowercase hexadecimal characters. Other strings are
bounded to 512 characters (versions to 256); suite keys use 1--64 ASCII letters,
digits, `.`, `_` or `-`.

Tags, expected values, engine image IDs and unbound repository digests are
declarations, not observations. Service and composite routes are unsupported
by version 1. Missing, malformed, stale, unsupported or incomplete sidecars
leave the project-runtime observation `BLOCKED`; a complete observation that
conflicts with an applicable mandatory declaration is `FAIL`. Outside
adoption-check the handshake variables are absent and the adapter's ordinary
behavior is unchanged.

The evidence directory retains component numeric exits and output, the
project-reported sidecars and hashes, two-generation context evidence, the
staged patch and before/after Git state. Gnostoa holds authoritative artifact
bytes in an append-only in-memory ledger while project suites run; the only
suite-visible tool-owned area is that attempt's fresh incoming sidecar
directory. It binds the validated output parent once before suites, creates
exchanges and final staging by basename relative to that held directory, and
checks that the visible parent still has the held identity after each suite and
at the materialization and publication boundaries. After all attempts, it
creates a clean no-replace bundle from the ledger, reconciles every regular
file, and publishes with a descriptor-relative no-replace rename. A missing,
symlinked or replaced visible parent is an integrity failure; if detected after
publication, the tool removes only its just-created bundle and emits neither
commitment nor readiness.

After a successful bundle publication, trusted stdout emits exactly one
`EVIDENCE BUNDLE COMMITMENT: gnostoa-adoption-evidence-bundle/v1 sha256:<64
hex>` record. The digest covers compact, key-sorted UTF-8 JSON plus one LF: an
array sorted by normalized relative path with exactly `path`, `bytes` and
`sha256` for every materialized file, including `adoption-check.json` and
`SHA256SUMS`. Retain this external record separately. Recomputing it detects
later changed bundle bytes, but it is not provenance or protection from an
unrestricted persistent process running as the same filesystem owner. That
residual same-user process can still race after the final identity checkpoint
or alter ordinary post-publication custody without operating-system isolation
or another external trust anchor.

Exit `0` means only `READY FOR
ACCOUNTABLE-OWNER REVIEW`; exit `1` is a mechanical failure, exit `2` an unsafe
or invalid invocation/internal error, and exit `3` a blocked prerequisite. A
project-reported runtime observation is not independent attestation, semantic
truth, owner acceptance or durable-adoption authority.

## Preconditions

- A bounded pilot area and its accountable owners are selected.
- The source repositories and available historical material are accessible.
- The team agrees to distinguish current state, target state and proposals.
- A baseline task set exists for measuring searches, tokens, correctness and
  review time.

## Procedure

1. Choose embedded placement for one repository or a dedicated knowledge
   repository for a multi-repository program.
2. Pin the toolkit revision, deterministic public-surface digest and matching
   runtime identity, then create a minimal project profile and validate the lock
   through the [new-project workflow](bootstrap-new-project.md).
3. Inherit the generic change-control and CI policies. Inventory current branch,
   review, hooks, pipelines, test suites, secrets and emergency practices, and
   record gaps without silently treating them as compliant.
4. Select one protected integration branch and one pilot Change Request. Do not
   attempt to migrate all open long-lived branches in the first change.
5. Establish high-impact characterization tests around the pilot behavior before
   refactoring or normalizing it. Do not pursue blanket coverage.
6. Create the verification manifest around the pilot. Map existing fast and
   regression commands first, declare conditional capabilities honestly, then
   exercise one failing candidate pipeline before making its checks required.
7. Inventory sources without summarizing them. Record owner, location,
   revision, last modification and authority class.
8. Establish source precedence for standards, accepted decisions, executable
   contracts, implementation, reviewed documentation, meeting records and
   generated summaries.
9. Model the current state first. Keep target architecture and proposals in
   separate concepts.
10. Create only the concepts needed by the pilot: repositories, boundaries,
   contracts, decisions, open questions and contradictions.
11. Link to source artifacts rather than copying their contents.
12. Keep generated or inferred concepts as `draft`; promote them only after
   source-owner review.
13. Validate source/runtime lockstep, the inherited change and CI policies,
    verification manifest and new bundle strictly. Raw legacy
    Markdown remains outside the bundle unless converted to conforming `Source`
    concepts.
14. Run the baseline tasks with and without the knowledge slice and compare
    correctness, exploration operations, input tokens and human review time.
15. Stage the bounded candidate and run the
    [mechanical completion check](#mechanical-completion-evidence). Preserve its
    evidence bundle for accountable-owner review; do not translate exit `0`
    into semantic acceptance or durable adoption.
16. Expand one bounded area at a time only when the previous slice remains
    maintainable.

## Verification

- Every stable claim has a human verifier.
- Contradictory sources remain visible and are not silently reconciled.
- Current and target architecture are distinguishable.
- The pilot answers its selected questions by following concepts to evidence.
- Measured savings exceed generation and maintenance cost.
- The pilot change reaches the protected branch only through a passing Change
  Request and any review required by the project's specialization.
- Required checks belong to the latest pilot merge candidate; hook success
  alone cannot satisfy integration.

## Recovery

If authority cannot be established, retain the material as a draft Source or
open question. If maintenance cost grows faster than value, freeze expansion,
reduce the taxonomy and retain only the verified navigation spine.
