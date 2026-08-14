---
type: Reference
title: Policy versioning and toolkit upgrades
description: Treat profiles, change-control and continuous-integration policies and verification manifests as public validation contracts with reviewed upgrades.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-07-29T00:00:00Z"
sources:
  - id: semver
    resource: https://semver.org/
    title: Semantic Versioning 2.0.0
x-project-knowledge:
  id: guidance.reference.versioning-and-upgrades
  owners:
    - team:gnostoa-maintainers
  scope:
    - generic-guidance
  relations:
    - kind: guides
      target: /workflows/create-specialization.md
    - kind: applies-to
      target: /guardrails/non-negotiable.md
---

# Policy versioning and toolkit upgrades

## Purpose

Make validation reproducible and prevent an upstream policy change from
silently breaking or relaxing a project.

## Content

Versions of profiles, change-control policies, continuous-integration policies
and verification manifests use semantic meaning. The same rule applies to every
profile or policy specialization:

- PATCH: backward-compatible correction that changes neither accepted inputs
  nor required consumer behavior.
- MINOR: backward-compatible optional vocabulary or capability.
- MAJOR: any removal, rename, stricter requirement or incompatible behavior
  change that can invalidate a previously accepted input or require a consumer
  migration.

`okf_version` is independent from the profile version.

Upgrade workflow:

1. Fetch the target released tag.
2. Resolve the matching published OCI image digest and source revision.
3. Change source, image and lock pins and every affected public
   validation-contract version in a dedicated branch.
4. Run the runtime-lock check.
5. Validate every project, module and aggregate profile.
6. Validate every bundle, change-control and continuous-integration
   specialization, and verification manifest.
7. Review migration diffs and changed enforcement.
8. Merge the new pins and migration together.
9. Retain the previous pins and validation-contract revisions for rollback until
   the upgrade is proven.

## Usage

Never point CI at a mutable default branch or image tag. Version the project
profile, change-control policy, continuous-integration policy, verification
manifest and each profile or policy specialization separately. A leaf profile
upgrade must not force unrelated siblings to inherit its vocabulary.
