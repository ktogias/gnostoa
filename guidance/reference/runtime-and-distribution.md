---
type: Reference
title: Runtime and distribution modes
description: Provide a container-first consumer interface with an explicitly supported native fallback.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-07-29T00:00:00Z"
sources:
  - id: oci
    resource: https://opencontainers.org/
    title: Open Container Initiative
  - id: dev-containers
    resource: https://containers.dev/
    title: Development Containers
  - id: docker-bind-mounts
    resource: https://docs.docker.com/engine/storage/bind-mounts/
    title: Docker bind mounts
  - id: gitlab-image-digests
    resource: https://docs.gitlab.com/ci/docker/using_docker_images/
    title: GitLab CI container images
x-project-knowledge:
  id: guidance.reference.runtime-and-distribution
  owners:
    - team:gnostoa-maintainers
  scope:
    - generic-guidance
  relations:
    - kind: guides
      target: /workflows/bootstrap-new-project.md
    - kind: applies-to
      target: /reference/versioning-and-upgrades.md
    - kind: governed-by
      target: /guardrails/non-negotiable.md
---

# Runtime and distribution modes

## Purpose

Make the toolkit implementation language irrelevant to consuming projects while
retaining a transparent development and recovery path for maintainers.

## Content

The supported modes are:

| Use | Primary mode | Supported fallback |
|---|---|---|
| Project validation | OCI-compatible runtime image pinned by digest | Isolated native CLI |
| CI validation | Pinned runtime image | Isolated native CLI job |
| Toolkit maintenance | Development Container | Native development environment |
| Air-gapped use | Imported or internally mirrored OCI image | Vendored source and native CLI |

Container-first is not container-only. The runtime image encapsulates the
implementation language and dependencies; it does not change the canonical
Markdown, YAML, profiles or executable project artifacts.

The runtime image:

- runs as a non-root user;
- declares its toolkit source revision;
- pins its base image by digest;
- reads the project through an explicit bind mount;
- writes only through an explicitly writable output mount;
- exposes one `knowledge` command with subcommands.

A project lock records the toolkit source revision, deterministic public-surface
digest, profile path, runtime image digest and runtime revision. Validation
recomputes the mounted source digest and rejects a mismatch with either the lock
or the public surface embedded in the executing image. The locked source digest
also protects the native fallback, where no independent image surface exists.
Development images and mutable local tags are permitted only for toolkit
development, never as CI policy dependencies.

## Usage

Use an OCI-compatible engine such as Docker or Podman. Mount project content
read-only for validation. Pin CI images as
`registry.example/image@sha256:<digest>` rather than by mutable tag.

Use the Development Container definition when maintaining the toolkit. Use the
native environment when containers are unavailable, for low-level debugging or
as an explicit recovery path. Both modes run the same test and validation
commands.
