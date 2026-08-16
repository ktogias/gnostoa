## Problem

Gnostoa's B1 self-dogfood bootstrap found and corrected material source-scope,
authority, lifecycle, drift and disclosure defects. It also produced an
unacceptable review surface: Issue #12 contains 342 comments and PR #2 contains
65, together totalling about 2.58 million characters. That history is useful
bootstrap evidence, but it is not a workflow that contributors should repeat.

## Desired outcome

Run one small, predeclared Gnostoa change as **B2**, using the existing toolkit
and ordinary provider-native review while preserving the useful B1 controls.
Compare B2 with B1 and determine whether the same assurance can be achieved
with materially less owner effort, fewer review rounds and lower evidence
amplification.

## Experiment contract

- Select one bounded post-publication Gnostoa change with an explicit owner,
  classification, exact base, expected behavior and pre-change evidence.
- Keep one compact current projection. Detailed deterministic evidence may be
  expandable, but it is not duplicated into a prose event for every check.
- Ask for one owner decision per genuine semantic choice. Faithful recording,
  exact read-back and deterministic reconstruction do not create duplicate
  approval gates.
- Use normal Pull Request review semantics for the patch. Historical ledgers
  remain evidence; they are not the interface presented to the reviewer.
- Target no more than one initial brief, one current review projection and one
  final result record. Exceeding that target is permitted only when a named
  safety or correctness reason is recorded.
- Stop and report rather than inventing completeness when authority, source,
  evidence or provider state is unknown.

## Measurements

Record at least:

- elapsed time and active owner review time;
- review rounds and semantic decisions;
- provider comments and evidence words per changed normative line;
- material defects caught before integration and escaped defects;
- invalidation precision, exact reconstruction and interruption recovery;
- false-ready and false-block outcomes; and
- new workflow/tooling surface required to complete the change.

## Acceptance criteria

- [ ] The B2 change and comparison method are fixed before implementation.
- [ ] The exact base, candidate, evidence and owner decision remain
      reconstructable without replaying raw conversations.
- [ ] No automated or agent-produced evidence is represented as human
      acceptance.
- [ ] A fresh reviewer can identify current status, remaining question and
      next action from one bounded projection.
- [ ] B2 reports both positive and negative results against the recorded B1
      baseline.
- [ ] Evidence amplification and owner interaction are materially lower than
      B1, or the experiment records a falsifying result and narrows the product
      claim.
- [ ] Any admitted automation is limited to repeated deterministic mechanics
      demonstrated by B1 or B2.

## Dependencies and boundaries

- Complete the first source-publication baseline in #1 before admitting the B2
  implementation change.
- #6, #9, #13 and #15 are research or contract inputs, not automatic B2
  implementation prerequisites.
- Issue #12 and PR #2 remain the immutable B1 evidence sources. Their comment
  volume is not a success metric and is not the expected contribution model.
- Recording this Work Item does not admit implementation, make another Work
  Item or Decision effective, merge a Pull Request or publish an artifact.

## Non-goals

- building a general workflow, forms or event-sourcing platform;
- automating the full historical ledger;
- claiming independent adoption from a self-hosted experiment; or
- hiding, deleting or rewriting B1's negative evidence.

The canonical B1 interpretation and measurement model are maintained in the
[self-dogfood bootstrap assessment](https://github.com/ktogias/gnostoa/blob/agent/release-hash-locked-artifacts/knowledge/assessments/gnostoa-self-dogfood-bootstrap-assessment.md).
