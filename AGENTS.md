# Gnostoa agent router

Start with `README.md`. Load only the route required by the task.

- Core profile, schemas, validators, templates or CI: read
  `knowledge/contracts/public-inheritance-surface.md` and
  `knowledge/runbooks/maintain-the-kit.md`.
- Reusable workflow or practice: route through `guidance/index.md`.
- CI policy, provider adapters or hooks: read
  `guidance/workflows/configure-continuous-integration.md`.
- Toolkit architecture or rationale: route through `knowledge/index.md`.
- Anonymous examples: use only generic vocabulary and never treat examples as
  approved project facts.

Before changing normative behavior, read
`guidance/guardrails/non-negotiable.md` and update
`policy/guardrails.yaml` when coverage changes. Generated content starts as
draft. Stable concepts require a `human:` verifier. Preserve provenance and
keep executable artifacts canonical in their native formats.

Classify every change through
`guidance/workflows/propose-review-merge-change.md` and
`policy/change-control.yaml`. Agents may author changes and evidence, but never
self-approve where independent approval is required, bypass controls or replace
required human semantic review.
For this repository, every normal, normative or critical change requires a
linked Work Item and Decision before implementation; an emergency supplies them
in its mandatory follow-up.
Normative and critical changes also require a validated active Execution Plan;
normal changes require one when work crosses an actor/session boundary or is
otherwise costly to reconstruct. At start or resume, inspect Git state and run
`knowledge task start|resume --plan <path>` through
`guidance/workflows/resume-and-handoff-change.md`. Keep raw prompts, reasoning
and exhaustive activity logs noncanonical.
Before implementation, follow
`guidance/workflows/develop-verification-first.md`; record expected behavior and
establish the applicable failing or characterization evidence before editing.
Mechanical changes and emergency follow-up use the timing declared by
`policy/change-control.yaml`.
Before handing unfinished work to another person or agent, update its plan,
commit a coherent checkpoint, require a clean worktree and reconcile the
managed Change Request block with the actual candidate revision.

Before completion run:

```bash
python -m unittest discover -s tests -v
python -m tools.validate_bundle --profile guidance/profile.yaml --bundle guidance
python -m tools.validate_bundle --profile knowledge/profile.yaml --bundle knowledge
python -m tools.check_guardrails
python -m tools.check_change_policy
python -m tools.check_ci_policy --policy policy/continuous-integration.yaml --verification policy/verification.yaml
```

For runtime, distribution or CI changes, also build the `runtime` container
target and run `knowledge self-check` inside it.
