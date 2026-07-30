# Architecture and layer contract

This MkDocs page is a derived navigation projection. Canonical concepts are:

- [public inheritance contract](../../knowledge/contracts/public-inheritance-surface.md);
- [policy, guidance and self-knowledge separation](../../guidance/patterns/policy-guidance-self-separation.md);
- [repository layout and distribution](../../guidance/reference/repository-layout-and-distribution.md);
- [profile authoring](../../guidance/reference/profile-authoring.md);
- [derived retrieval decision](../../knowledge/decisions/0003-derived-retrieval-layers.md).
- [continuous-integration contract](../../guidance/reference/continuous-integration-contract.md).

The dependency direction is one-way:

```text
generic core <- project profile <- optional module specialization

canonical project/source artifacts -> replaceable views and retrieval indexes
```

The generic core never imports project vocabulary. Consuming projects never
inherit the toolkit's `knowledge/` self-bundle.
