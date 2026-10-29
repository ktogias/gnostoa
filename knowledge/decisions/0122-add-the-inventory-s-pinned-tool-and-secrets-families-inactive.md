---
type: Decision
title: Add the inventory's pinned tool and secrets families, inactive until a separate activation
description: "The diagnostic inventory gains ShellCheck, Hadolint, actionlint, GitLab-script, secrets and unsafe-calls families under a v2 protected profile that pins each official release executable per machine. Each new family is off on the protected profile, so every effective obligation is unchanged until a separate activation decision."
status: draft
generated:
  by: anthropic/claude-opus-5-5
  at: "2026-10-29T22:19:00Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/389
    title: Keep merges possible while a vendor analyzer is unavailable
  - id: owner-coverage
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6502660123
    title: "The owner's direction: replace Shell and Docker analysis, DIFF and FULL, in every applicable class"
  - id: owner-python-secrets
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6505016187
    title: "The owner's direction: complete the Python/Secrets replacement case, no blanket loss"
  - id: owner-admission
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6508582845
    title: "The owner's admission of H-PYSEC-2 for implementation and qualification, initially unactivated"
  - id: scope
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6508335114
    title: "The Router's H-PYSEC-2 scope"
  - id: route
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6508695016
    title: "The Router's disposition: the inactive reading, the protected baseline, the transport"
  - id: lineage
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6508616758
    title: The pre-mutation architecture lineage
  - id: red
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6508786854
    title: The RED, alone, before the implementation
  - id: qualification
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6503632912
    title: "The measured ShellCheck, Hadolint and actionlint qualification on main"
  - id: queue
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6503958085
    title: "The concurrency.queue compatibility projection and its controls"
  - id: python-secrets
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6507941344
    title: "The Python/Secrets closure points: unsafe-calls, the plugin and its identity binding"
  - id: profile
    resource: ./0117-select-the-diagnostic-inventory-s-families-through-a-protected-profile.md
    title: The protected profile this decision extends
  - id: normal
    resource: ./0119-admit-normal-changes-through-the-project-s-own-inventory-and-keep-deepsource-for-every-other-class.md
    title: The inventory route whose production obligations this decision leaves unchanged
x-project-knowledge:
  id: kit.decision.0122.add-the-inventory-s-pinned-tool-and-secrets-families-inactive
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /decisions/0117-select-the-diagnostic-inventory-s-families-through-a-protected-profile.md
    - kind: references
      target: /decisions/0119-admit-normal-changes-through-the-project-s-own-inventory-and-keep-deepsource-for-every-other-class.md
---

# Add the inventory's pinned tool and secrets families, inactive until a separate activation

## Context

The owner selected replacing DeepSource's useful Shell, Docker, Python and Secrets assurance in every applicable class
(sources `owner-coverage`, `owner-python-secrets`). The qualification measured the official ShellCheck 0.11.0,
Hadolint 2.15.1 and actionlint 1.7.12 on main and the hostile inputs each one must ignore (source `qualification`), a
bounded projection for the `concurrency.queue` key actionlint 1.7.12 does not know (source `queue`), and the narrow
unsafe-calls Ruff family and a protected secrets plugin for the forms detect-secrets' default plugins miss (source
`python-secrets`). The owner admitted their implementation and qualification, initially unactivated (source
`owner-admission`).

## Decision

1. **The profile.** `policy/diagnostic-profile.yaml` moves to `gnostoa-diagnostic-profile/v2`, which adds:
   - a `tools` map pinning each official release executable by its SHA-256 per machine (`x86_64`, `aarch64`);
   - a per-family `active` flag, absent meaning active;
   - the families `shell-lint`, `dockerfile-lint`, `workflow-lint`, `gitlab-script`, `secrets` and `unsafe-calls`,
     each `active: false`.

   A v1 profile has no tool families, pins or activation. Under v2 each pinned family's tools must be pinned.
2. **Activation stays separate.** An inactive family is never planned, run or rowed, so the protected inventory's
   families, findings and every assurance obligation are unchanged by this decision.
3. **The producers** (tools/quality_evidence.py) run a pinned tool only from the protected `TOOL_ROOT`, and only after
   its bytes match the pin and its version output names the pinned version. They run with a clean environment and the
   protected configuration:
   - ShellCheck: `--norc`, no `-x`, explicit files;
   - Hadolint: an explicit protected `-c`, `--disable-ignore-pragma`, an empty working directory;
   - actionlint: a protected `-config-file`, the pinned ShellCheck, no pyflakes.
4. **Applicability** comes from the frozen tree: a `.sh` file or a sh/bash/dash/ksh shebang, `Dockerfile*`, GitHub
   workflows and `ci/github*.yml`, the GitLab CI files, and every tracked file for secrets.
5. **Attributable gaps.** These make a family's row PARTIAL or INCOMPLETE and are named, never a clean result:
   - a ShellCheck directive, a Hadolint pragma or a sourced file;
   - a workflow step whose effective shell is not bash or sh;
   - an unsupported GitLab construct (include, `!reference`, `inherit`, cycles, merge keys, unmappable items);
   - another shell's script;
   - a missing, linked or altered tool, or a wrong version;
   - a report its exit status contradicts.

   Every finding a run reports stays listed.
6. **The queue projection** changes, in an analysis copy only, a validated block-style `concurrency.queue: single|max`
   line into a comment, keeping every other byte and the line count. Every other form is left for actionlint to
   report.
7. **Secrets** run the project's scanner over the head's files as data, against the protected reviewed baseline
   restricted to the scanned files, then the protected plugin `tools/security_scan_plugin.py`. The scanner pins the
   plugin by digest (`PLUGIN_PINS`), reads its bytes through no link, and imports only a private read-only copy. The
   candidate `security-fast` scan and `.secrets.baseline` are unchanged.
8. **Unsafe-calls** select S301, S307, S324, S602, S605 and S608 on the existing Ruff producer. Its one finding on
   main, a Git blob id hashed with SHA-1, is repaired with `usedforsecurity=False`, which keeps the same digest.

## Consequences

- **Nothing effective changes at merge.** Activation is a separate decision: the protected inventory job's pinned
  tool acquisition into `TOOL_ROOT`, the development image's, the findings the new families would report on main
  (Hadolint and actionlint, source `qualification`), and the coverage choices the owner still holds (source
  `owner-admission`).
- **The inventory document stays v3.** New values ride existing fields, and the adapter reads only the schema string.
- **Touched files are acquired whole.** The files this change touches were brought clean under the inventory's own
  families: fixture annotations, originals through the mock factory instead of private attribute access, and a public
  alias for `exact_tree`'s directory flags.

## Prior-art and reuse disposition

- **ShellCheck and Hadolint are GPL-3.0, and actionlint is MIT.** Each is used as a separate, unmodified executable,
  downloaded from its upstream release by digest, and is not linked or shipped in any published image. The
  Apache-2.0 licensing of Gnostoa is unaffected; this is the recorded reading, not a separate legal qualification.
- **Reused:** the existing profile owner and its validation, `_family_targets`, `_withheld`, `_family_row`, the
  finding normalization, the lossless changed/rest partition, the existing Ruff producer, and the project's secret
  scanner unchanged.

## Alternatives considered

- **Activate at merge.** Rejected: the owner admitted implementation and qualification only, and on main the new
  families would report findings that need their own repairs.
- **Put the plugin in `security-fast`.** Rejected for this step: that would activate new required coverage, and change
  the candidate scan's baseline, at merge.

## Evidence

The RED (source `red`) failed on main for its stated reasons and passes on this change. The protected inventory over
this change's head against main reports COMPLETE coverage, with no DIFF or FULL finding.
