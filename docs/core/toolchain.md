# Tool selection

This MkDocs page is a derived navigation projection. Use the canonical
[tool-selection reference](../../guidance/reference/tool-selection.md) and
[established supporting patterns](../../guidance/practices/established-patterns.md).

The baseline is Git, OKF, validation and native executable contracts.
Generation, static rendering, context caches, temporal graphs and enterprise
catalogs remain optional and replaceable. Concrete implementation frameworks
and contract-testing products belong in project or module specializations.

Consumer execution is container-first; see
[runtime and distribution modes](../../guidance/reference/runtime-and-distribution.md).
Central CI uses the provider-neutral
[continuous-integration contract](../../guidance/reference/continuous-integration-contract.md);
GitHub Actions and GitLab CI remain replaceable adapters.
