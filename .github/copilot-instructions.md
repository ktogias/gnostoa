# Gnostoa repository instructions

Treat `AGENTS.md` as the repository router and source of mandatory local rules.
For any change task, use the repository `change-lifecycle` skill.

- Inspect Git state before trusting prior conversation context.
- Follow the effective change class and required Work Item, Decision and
  verification chronology.
- For a required or existing Execution Plan, run the applicable
  `knowledge task start|resume|checkpoint|handoff` command.
- Continue from the plan's `next_action` and reconcile scope with its Work Item.
- Preserve unexplained user or agent changes; never silently replace them.
- Keep prompts, private reasoning and raw activity transcripts out of canonical
  project knowledge.
- Regenerate managed Pull Request context from the plan and actual candidate
  revision; do not append ad hoc status prose.
- Agent evaluation is evidence and never substitutes for required human
  semantic verification or approval.
