---
type: Workflow
title: Resume a bounded task from one current projection
description: Validate durable task state, fail closed on stale identities and hand one compact current view to the next actor.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-16T00:00:00Z"
x-project-knowledge:
  id: guidance.workflow.resume-bounded-task
  owners:
    - team:gnostoa-maintainers
  scope:
    - generic-guidance
  relations:
    - kind: depends-on
      target: /workflows/propose-review-merge-change.md
    - kind: governed-by
      target: /guardrails/non-negotiable.md
---

# Resume a bounded task from one current projection

## Outcome

A person or agent can identify one task's current state, exact source
identities, remaining action and handoff without replaying a raw conversation.
The YAML envelope is canonical task state; the Markdown projection is derived
and replaceable.

## Preconditions

- The task has one stable ID, accountable owner and change class.
- Scope and explicit non-goals are bounded.
- Base and dependency identities come from their authoritative sources.
- A Work Item and Decision are linked when the effective change policy requires
  them.

## Procedure

1. From a source checkout copy `templates/task-envelope.yaml`; an adopting
   project copies the same file from its pinned `.knowledge-kit/templates/`
   surface. Fill only current facts and links. Link Decisions and evidence; do
   not copy their bodies into the envelope. The named owner is accountable but
   is not thereby the recorder or approver.
2. Validate the envelope:

   ```bash
   knowledge task-validate \
     --envelope path/to/task.yaml \
     --repository-root .
   ```

   Repository-relative references resolve against `--repository-root`, which
   defaults to the current working directory. Here `.` is the adopting
   project's repository root, so run the command from that root. A caller
   running anywhere else — a packaged image, a hook, a scheduler — must pass
   the exact root instead, or the same envelope will validate differently
   depending on where it was invoked.

3. Refresh the base and every declared dependency from their authoritative
   sources. Render a current view only with those observed identities and the
   exact immutable candidate revision:

   ```bash
   knowledge task-project \
     --envelope path/to/task.yaml \
     --repository-root . \
     --candidate git:EXACT_CANDIDATE \
     --observed-base git:EXACT_BASE \
     --observed-dependency dependency-id=EXACT_VALUE
   ```

   The command checks declared base and dependency values against the supplied
   observations. The candidate is a typed immutable caller observation; the
   portable core does not refresh provider HEAD or mediate an external effect.

4. Give the next actor the projection, the focused diff and only the linked
   source needed for an unresolved question. One genuine semantic choice gets
   one human decision; deterministic validation, projection and read-back do
   not create another approval.
5. To resume unchanged state, compare its SHA-256 with
   `--expected-checkpoint`. To advance state, increment the sequence, put the
   prior digest in `checkpoint.previous`, and verify that link with
   `--expected-previous-checkpoint`. Both values are caller observations; a
   later provider adapter may refresh them but cannot change their meaning.
6. Pause as `blocked` when the owner cannot explain the bounded change,
   consequence or uncertainty inside the declared review budget. Clarification
   is safer than ceremonial approval.
7. Keep the derived projection on standard output or in a disposable review
   artifact. Never use `--output` to replace the canonical envelope.

## Identity kinds

Every declared identity names a `kind`. A `kind` is a versioned contract over
an exact byte sequence, not a hint. Define those bytes where the kind is
introduced, and version the name so that a later change to the rule becomes a
new kind instead of a silent reinterpretation of already recorded digests. The
portable core compares declared and observed values literally: it never trims,
re-encodes or normalizes them, and it never fetches them.

Gnostoa's own task state uses one provider-specific kind as the worked example.
`github-issue-body-utf8-sha256-v1` is the SHA-256 of the exact Unicode string
returned in the GitHub REST API `body` field, encoded directly as UTF-8, with
no trimming, no insertion or removal of a trailing newline, no line-ending
normalization, no Unicode normalization and no Markdown rendering:

```bash
gh api repos/OWNER/REPO/issues/NUMBER | python3 -c \
  'import hashlib,json,sys; print("sha256:" + hashlib.sha256(
   json.load(sys.stdin)["body"].encode("utf-8")).hexdigest())'
```

Read the authoritative record, not a rendered page. A shell pipeline that adds
or strips a trailing newline yields a different digest, which is exactly what
the versioned name exists to keep unambiguous.

## Input bounds

An envelope is bounded input, not an arbitrary document. Both commands enforce
a maximum byte size and a maximum structural nesting depth before the YAML
parser runs, so an over-large or over-deep file is a concise diagnostic rather
than an exhausted interpreter stack. Recursive anchor cycles are rejected the
same way; ordinary acyclic anchors and aliases remain supported.

Duplicate scalar keys are rejected by comparing composed key nodes. Keys whose
source text differs but whose constructed values collide are not yet covered,
so this is not a claim that every semantically ambiguous YAML document is
refused.

## Verification

- Identical semantic YAML and observations reproduce byte-identical output.
- A stale base, missing or changed dependency, duplicate identity or old
  checkpoint fails before a current projection is produced.
- The projection contains one next action and an explicit handoff, but no
  transcript or duplicated evidence body.
- Its declared character and owner-time budgets are visible; an oversized
  projection fails rather than truncating content.
- The candidate is supplied at projection time because a committed envelope
  cannot contain its own commit identity without a self-reference.

## Recovery

On drift, refresh the authoritative identities and regenerate the projection.
On a checkpoint conflict, reconcile the competing state before writing; do not
overwrite it. If the task exceeds its attention or scope budget, split the
change or record a blocker. This contract is not an event store, workflow
engine, provider adapter or authority service.
