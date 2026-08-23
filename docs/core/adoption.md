# Adoption guide

This page is a navigation projection, not a second source of operating rules.

## Choose the commitment

For a bounded technical look, use the [minimal evaluation and orientation
route](../quick-start.md). It validates a public example and generates derived
context without requiring repository, CI or provider adoption. The existing
[project profile example](https://github.com/ktogias/gnostoa/blob/main/examples/profiles/example-project/profile.yaml)
and [Project concept example](https://github.com/ktogias/gnostoa/blob/main/examples/generic/project.md) show the two
starting shapes directly.

Full adoption is a durable project-maintenance choice. Use the canonical route
for the task:

- [bootstrap a new project](../../guidance/workflows/bootstrap-new-project.md);
- [adopt an existing project](../../guidance/workflows/adopt-existing-project.md);
- [create a project or module specialization](../../guidance/workflows/create-specialization.md);
- [perform a routine knowledge change](../../guidance/workflows/daily-change-loop.md).
- [configure continuous integration](../../guidance/workflows/configure-continuous-integration.md).

All routes converge on the same minimum controls:

1. pin an immutable toolkit version and matching OCI image digest;
2. extend the core with the smallest justified project profile;
3. keep the project's canonical bundle in project ownership;
4. declare verification capabilities and validate it through authoritative
   merge-candidate CI;
5. keep generated knowledge draft until human verification;
6. measure retrieval outcomes before adding graph or memory infrastructure.

The consuming project's agent router should be adapted from
[`templates/AGENTS.project.md`](../../templates/AGENTS.project.md). It routes
agents to the one relevant generic workflow and explicitly excludes toolkit
self-knowledge.

## Unknown accountable owner

Keep an unknown owner explicit and the affected knowledge draft or unresolved.
Do not invent a person. If a syntactic role placeholder is needed to keep a
draft structurally valid, label the ownership gap explicitly: the placeholder
is routing metadata, not verified accountability. Do not promote the concept or
Decision to stable until an accountable owner accepts it.
