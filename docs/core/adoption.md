# Adoption guide

This page is a navigation projection, not a second source of operating rules.
Use the canonical route for the task:

- [bootstrap a new project](../../guidance/workflows/bootstrap-new-project.md);
- [adopt an existing project](../../guidance/workflows/adopt-existing-project.md);
- [create a project or module specialization](../../guidance/workflows/create-specialization.md);
- [perform a routine knowledge change](../../guidance/workflows/daily-change-loop.md).
- [resume or hand off a bounded change](../../guidance/workflows/resume-and-handoff-change.md);
- [configure continuous integration](../../guidance/workflows/configure-continuous-integration.md).

All routes converge on the same minimum controls:

1. pin an immutable toolkit version and matching OCI image digest;
2. extend the core with the smallest justified project profile;
3. keep the project's canonical bundle in project ownership;
4. declare verification capabilities and validate it through authoritative
   merge-candidate CI;
5. keep generated knowledge draft until human verification;
6. measure retrieval outcomes before adding graph or memory infrastructure.
7. create bounded live task state only when policy or continuity requires it.

The consuming project's agent router should be adapted from
[`templates/AGENTS.project.md`](../../templates/AGENTS.project.md). It routes
agents to the one relevant generic workflow and explicitly excludes toolkit
self-knowledge.
