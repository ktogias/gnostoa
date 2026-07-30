---
type: Requirement
title: Centralized CI verifies every integration candidate
description: Required automated evidence must run on the latest candidate revision through provider-neutral, non-weakening CI policy.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-07-29T00:00:00Z"
x-project-knowledge:
  id: kit.requirement.centralized-ci-verifies-integration-candidates
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0008-authoritative-tiered-continuous-integration.md
    - kind: verified-by
      target: /runbooks/maintain-the-kit.md
---

# Centralized CI verifies every integration candidate

The public toolkit must:

- define provider-neutral branch-revision, Change Request, merge-candidate,
  integration, scheduled and release events;
- make centralized required checks authoritative and local hooks advisory;
- require policy and fast evidence on pushed revisions;
- require regression evidence on Change Requests and merge candidates;
- require the latest reviewable revision to pass before integration;
- require projects to declare applicable verification capabilities and suites;
- reject CI-policy specializations that weaken inherited gates or remove
  required suites;
- make release verification conditional on a declared deployable artifact;
- promote the same verified artifact without environment-specific rebuilds;
- provide pinned, least-privilege provider adapters and shared local commands;
- keep concrete build systems, test frameworks and deployment targets in
  project or module specializations.

The self-check must validate the generic CI policy, the toolkit specialization
and its verification manifest.
