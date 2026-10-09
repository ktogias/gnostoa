---
type: Decision
title: Read pull-request descriptions with a CommonMark parser
description: The merge-evidence adapter reads a pull request's Change control fields from its description. A hand-written reader of raw Markdown kept reading lines that GitHub renders as code or hides, so the description is read with markdown-it-py, a maintained CommonMark parser. It joins the runtime lock with its one dependency, mdurl, and the development lock's reviewed hashes.
status: draft
generated:
  by: anthropic/claude-opus-5-5
  at: "2026-10-09T13:50:00Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/407
    title: Require a provider-neutral merge-admission verdict on the exact head (MA0 Phase 1b)
  - id: owner-choice
    resource: https://github.com/ktogias/gnostoa/issues/407#issuecomment-6082207809
    title: The owner's choice to adopt markdown-it-py, and why
  - id: proposal
    resource: https://github.com/ktogias/gnostoa/issues/407#issuecomment-6082229646
    title: The dependency proposal and its prior art, admitted by the owner
  - id: consumer
    resource: https://github.com/ktogias/gnostoa/pull/413
    title: The GitHub merge-evidence adapter (slice 1b.3a), whose review rounds found the defect class
  - id: lock-precedent
    resource: ./0095-refresh-vulnerable-development-dependency-pins.md
    title: How a lock pin is admitted, its wheel hash checked against the downloaded file
  - id: runtime-precedent
    resource: ./0109-run-the-test-suite-in-parallel-processes-through-one-owner.md
    title: A development-lock pin joining the runtime lock as authority evolution
  - id: parser
    resource: https://pypi.org/project/markdown-it-py/4.2.0/
    title: markdown-it-py 4.2.0, MIT
x-project-knowledge:
  id: kit.decision.0113.read-pull-request-descriptions-with-a-commonmark-parser
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /decisions/0112-admit-merges-through-a-required-provider-neutral-merge-admission-verdict.md
    - kind: references
      target: /decisions/0109-run-the-test-suite-in-parallel-processes-through-one-owner.md
    - kind: references
      target: /decisions/0095-refresh-vulnerable-development-dependency-pins.md
---

# Read pull-request descriptions with a CommonMark parser

## Context

Slice 1b.3a of MA0 Phase 1b ([Decision 0112](0112-admit-merges-through-a-required-provider-neutral-merge-admission-verdict.md),
#413) reads a pull request's change class, Work Items and Decisions from the
description's `## Change control` fields. A field that GitHub renders as code, or
hides, is not evidence. Reading it as evidence would let a description satisfy M14
with links that nobody sees.

The first reader matched raw Markdown with regular expressions. Each of four
review rounds found a construct that GitHub renders as code or hides, but that
the reader still read as a field:

- fences indented by one to three spaces, or longer than three characters;
- indented code blocks;
- unclosed HTML comments;
- raw HTML blocks such as `<pre>`;
- a fence straddling a comment;
- a comment delimiter inside a code span.

Each patch fixed an instance, and the next round found another. The capability
was the defect.

## Decision

1. **The description is read with a CommonMark parser.** Code blocks, HTML blocks
   and comments are distinct token types there, never list items, so a field is
   only a list item the parser finds.
2. **The parser is `markdown-it-py` 4.2.0,** a maintained, pure-Python,
   CommonMark-compliant parser (MIT). Its one dependency is `mdurl` 0.1.2 (MIT).
3. **Both join the runtime lock** with the development lock's reviewed hashes. Each
   wheel's SHA-256 was checked against the file downloaded from PyPI, as
   [Decision 0095](0095-refresh-vulnerable-development-dependency-pins.md)
   requires. `markdown-it-py>=4.2,<5` joins `pyproject.toml`'s dependencies.
4. **A test pins the property the reader relies on.** Every case from #413's
   rounds, run through the locked parser, is a code, HTML-block or comment token,
   and never a list item.

## Evidence

- **Hashes:** `markdown_it_py-4.2.0-py3-none-any.whl` hashes to `9f7ebbcd…` and
  `mdurl-0.1.2-py3-none-any.whl` to `84008a41…`. Both match the development lock,
  both are non-yanked wheels, and both carry MIT license metadata.
- **The property:** `tests/test_markdown_parser_dependency.py` runs each of #413's
  cases, and the cases pass on the locked parser.

## Consequences

- The runtime image holds two more pure-Python distributions.
- #413 rebuilds its Change control reader on the parser's tokens, and merges after
  this change.
- Closing references are still read in the raw text, code included, as Decision
  0112 records. Over-reporting there can only deny.

## Alternatives not chosen

- **`cmarkgfm`** (bindings to GitHub's cmark-gfm, MIT): the closest to GitHub's
  renderer, but a C extension with per-platform wheels in the merge-admission trust
  path. The block structure the reader needs is CommonMark's, which GFM extends.
- **`mistune`** (BSD-3-Clause): not fully CommonMark.
- **`commonmark`** (commonmark.py, BSD-3-Clause): deprecated in favour of
  `markdown-it-py`.
- **Python-Markdown** (BSD-3-Clause): not CommonMark.
- **A stricter hand-written grammar:** bounded and fail-closed, but still an
  approximation of Markdown. The owner chose the parser.

## Delivery

This is authority evolution: `pyproject.toml` and the locks are
preparation-authority surfaces under Decision 0090. As with Decision 0109, the
candidate is verified directly in the development container and in the runtime
image built from its own lock. The owner admitted the change on 2026-10-09.
