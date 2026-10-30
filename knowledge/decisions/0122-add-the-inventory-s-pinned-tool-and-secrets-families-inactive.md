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
4. **Applicability** comes from the frozen tree's one listing:
   - for ShellCheck, a `.sh`, `.bash`, `.dash` or `.ksh` file, or a sh/bash/dash/ksh shebang;
   - `Dockerfile*`;
   - GitHub workflows and `ci/github*.yml`;
   - the GitLab CI files;
   - every tracked file for secrets.

   A DIFF-only family reaches by that listing, never by the Python paths alone.
5. **Attributable gaps.** These make a family's row PARTIAL or INCOMPLETE and are named, never a clean result:
   - a ShellCheck directive, a Hadolint pragma or a sourced file;
   - a workflow step whose effective shell is not bash or sh;
   - an unsupported GitLab construct (include, `!reference`, `inherit`, cycles, merge keys, unmappable items);
   - another shell's script;
   - a missing, linked or altered tool, a wrong version, or a run with no status;
   - a report that is not the pinned tool's: a duplicate key, a non-finite number, or a field its version does not
     write;
   - a report its exit status contradicts;
   - a workflow whose structure is not the documented mapping, or a step whose shell is empty or not text, and a
     `concurrency.queue` form the projection refuses;
   - a GitLab item whose tag cannot read its text;
   - for secrets, a file holding NUL bytes, which the protected plugins never read.
   - for secrets, a protected baseline with no results mapping, or a plugin that fails while its pinned bytes
     load: the scan is refused and named.

   Each input a family cannot vouch for is named in its row by its own path (and line, for a marked line). Each
   unanalyzed target's reason is named once, with how many targets it covers and the first. Every finding a run
   reports stays listed: past `max_findings` no inventory is written at all, and the refusal names the real count.
   A tool runs from a copy of its verified bytes in the run, so a replacement after the check never runs.
6. **The queue projection** changes, in an analysis copy only, a validated block-style `concurrency.queue: single|max`
   line into a comment, keeping every other byte and the line count. Every other form is left for actionlint to
   report.
7. **Secrets** run the project's scanner over the head's files as data, against the protected reviewed baseline
   restricted to the scanned files, then the protected plugin `tools/security_scan_plugin.py`. The scanner pins the
   plugin by digest (`PLUGIN_PINS`), reads its bytes through no link, and imports only a private read-only copy. The
   candidate `security-fast` scan and `.secrets.baseline` are unchanged.
   - **Identity:** the scan refuses any detect-secrets version, plugin or filter set but the protected baseline's.
     Its run record names that version, and its report binds the scanner, the baseline's digest and each plugin
     pin.
   - **Deadline:** a spent inventory deadline starts no scan. Every target is then unanalyzed with that reason
     named, so the row is INCOMPLETE, never clean. The scan itself is bounded by the scanner's timeout.
   - **Reasons:** a scanner refusal keeps its own classification, which never copies an exception's text or a
     filename; any other failure is named by its type alone.
   - **The plugin is stricter than the scanner.** No inline allowlist pragma hides its hits; no suppression
     comment hides a finding from the inventory's Ruff either. The reviewed baseline holds no audit for its hits.
     An entry of its type would read as stale to the scanner, unless the plugin were one of the baseline's
     `plugins_used`. That would change `security-fast`. So the plugin has no false-positive path yet: choosing one
     is part of activation.
8. **Unsafe-calls** select S301, S307, S324, S602, S605 and S608 on the existing Ruff producer. Its one finding on
   main, a Git blob id hashed with SHA-1, is repaired with `usedforsecurity=False`, which keeps the same digest.
9. **Qualification with the real executables** is `tests/test_quality_evidence_tool_qualification.py`. It runs only
   when `GNOSTOA_QUALIFICATION_TOOL_ROOT` names a directory whose executables are the protected pins. Otherwise it
   skips, and the skip says why.
   - **What it runs:** the protected profile with its new families switched on, passed explicitly, so every record
     names its origin as an argument, never the producer tree's.
   - **What it covers:** real positives in changed and unchanged files and benign controls; each named gap; an
     altered, linked or missing executable, and a pin that is the correct digest of the wrong tool; and the
     findings' path through the readbacks to M17.
   - **What it is not:** an obligation. It is a qualification instrument, so no guardrail lists it.

## Consequences

- **Nothing effective changes at merge.** This change is a partial delivery of the admitted H-PYSEC-2 work, not
  its whole outcome. Two things remain, kept apart.
  - **The admitted remainder** (implementation, under the same admission):
    - the pinned tool acquisition into `TOOL_ROOT` for the protected inventory job and the development image;
    - the development dependencies the producers need there, detect-secrets among them, since the runtime image
      carries none and a secrets family without it is unanalyzed;
    - the repairs of the findings the new families report on main (Hadolint and actionlint, source
      `qualification`).
  - **The later decision** to enable production coverage: turning any family `active`, the coverage choices the
    owner still holds (source `owner-admission`), and the plugin's false-positive path (decision item 7).

  This change leaves acquisition out because, while every new family is off, a mandatory release download would
  add a failure to every pull request's inventory and no coverage. Source `route` keeps the effective production
  obligations unchanged now. A dependency added to the effective inventory still needs its validation and its
  activation boundary.
- **The frozen tree is listed once.** That one listing serves the Python families and the new families'
  applicability, so an inactive profile enumerates exactly as before.
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

- **The RED** (source `red`) failed on main for its stated reasons and passes on this change.
- **The real-tool qualification found three defects the fake tools could not show:**
  - a second family's version check could not write the report the first had written, so a family that reused
    ShellCheck never ran it;
  - a family's unanalyzed targets were counted and never named;
  - another shell's script was named by its interpreter, not its path.

  Each fix followed a RED in the default suite. That suite now fakes a run that refuses an existing report, as the
  real one does.
- **The project's suite found a regression,** a second listing of the frozen tree, which ran even when every new
  family was inactive.
- **The protected inventory** over this change's head against main reports COMPLETE coverage, with no DIFF or FULL
  finding.
