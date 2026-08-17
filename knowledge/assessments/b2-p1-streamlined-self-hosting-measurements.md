---
type: Source
title: B2/P1 streamlined self-hosting measurements
description: Mechanically derived measurements for the first B2 slice, compared with the recorded B1 self-dogfood baseline, including the recorded owner review time and disposition.
status: draft
generated:
  by: agent:claude-opus-5
  at: "2026-08-16T21:37:05Z"
sources:
  - id: streamlined-self-hosting-experiment
    resource: https://github.com/ktogias/gnostoa/issues/24
    title: Run one bounded B2 streamlined self-hosting experiment
  - id: b2-p1-change-request
    resource: https://github.com/ktogias/gnostoa/pull/25
    title: B2 — add a validated task envelope and current projection
x-project-knowledge:
  id: kit.assessment.b2-p1-streamlined-self-hosting-measurements
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md
    - kind: derived-from
      target: /assessments/gnostoa-self-dogfood-bootstrap-assessment.md
    - kind: references
      target: /failure-modes/reverse-centaur-review-overload.md
---

# B2/P1 streamlined self-hosting measurements

## Measurement boundary

This record covers **B2/P1** only: the first increment of the Decision 0016
sequence, delivered as PR #25 and durably tracked by the `GNOSTOA/B2/P1` task
envelope at checkpoint 9. It does not cover B2 as a whole, and it is not an
acceptance record.

The task envelope does **not** contain the candidate identity. A committed
envelope cannot carry its own commit identity without a self-reference, so the
candidate is supplied at projection time and is currently bound by the Change
Request head and the derived current projection. This record is subject to the
same constraint and therefore names no revision of its own.

Two different surfaces are measured here, and they are not interchangeable:

- the **implementation delta** is every change under review except this record
  and its fixture. It is what a reviewer reads for correctness, and it is
  stable against edits to this record; and
- the **complete human-review surface** additionally includes this record and
  its fixture. Because writing that total into this record would change it,
  the complete figure is reported only by the provider and the Change Request
  body, against the exact head.

Every figure below is mechanically derived from the repository and the provider
API, except active owner review time, which cannot be derived. That value is
now reported by the maintainer rather than estimated, and is recorded below.

## Recorded B1 baseline

From the exact provider extraction on 2026-08-15 recorded in the
[self-dogfood bootstrap assessment](gnostoa-self-dogfood-bootstrap-assessment.md):

| Metric | B1 |
|---|---:|
| Provider comments on the two main threads | 407 |
| Comment-body characters on those threads | 2,580,461 |
| Comment corpus words (all threads) | ~289,449 |
| Repository text words | ~40,131 |
| Evidence amplification (comment words ÷ repository text words) | ~7.2 : 1 |
| Formal Change Request reviews and inline review comments | 0 |
| Elapsed span | ~17 days (2026-07-30 → 2026-08-15) |

## B2/P1 measurements at checkpoint 9

| Metric | B2/P1 | B1 comparison |
|---|---:|---|
| Provider comments on the change | **0** | 407 |
| Review-time Change Request body words (PR #25, accepted state) | **1,163** | — |
| Review-time projection words (checkpoint 8) | **660** | — |
| **Review-time foreground evidence words** | **1,823** | ~289,449 comment words |
| Changed normative words added | 7,217 | — |
| **Review-time evidence amplification** (foreground ÷ changed normative words) | **~0.25 : 1** | ~7.2 : 1 on a different denominator |
| Terminal projection words (checkpoint 9, post-integration observation) | 550 | — |
| Implementation delta | 22 files, +3,073 / −149 | — |
| — normative surfaces | 16 files, +1,833 / −98 | — |
| — tests | 2 files, +1,197 / −17 | — |
| — documentation and packaging | 4 files, +43 / −34 | — |
| Commits on the candidate branch | 8 | — |
| Completed owner review rounds | **5** untimed pre-review rounds, one an independent read-only audit, plus one timed disposition | 0 formal reviews |
| Semantic decisions requested / answered | 2 / 2 | not separately recorded |
| Effect authorizations requested / granted | 4 / 4 | not separately recorded |
| Material defects caught before integration | **8** defect families | multiple |
| Evidence defects corrected in owner review | **3** | not separately recorded |
| Known escaped defects | **0 known through the checkpoint-9 post-integration reconciliation** | — |
| False-ready outcomes | **5** | not separately recorded |
| False-block outcomes | 0 | not separately recorded |
| Elapsed to checkpoint 9 | see note below | ~17 days (provider-visible) |
| Integrated | yes, squashed to `31266ff` | yes |

### Which foreground evidence was measured, and when

Every foreground figure above is a **review-time** measurement: the evidence
actually in front of the maintainer at the moment the human disposition was
made. That is **Pull Request #25 in its accepted checkpoint-8 review state**,
not this follow-up Change Request, and not PR #25's body as it reads today —
that body was afterwards amended to carry the acceptance record, which was not
present when the review happened.

Method: whitespace-delimited tokens (`wc -w`) over the Markdown source of the
Change Request body and over the generated projection.

While the review was still pending, these figures were deliberately held
outside this record, because a record that is part of the change it measures
changes its own totals when it states them. That constraint ended when PR #25
was accepted and integrated: its review-time body is now frozen history, so the
figures are recorded here directly.

The terminal projection at checkpoint 9 measures 550 words. That is a separate
**post-integration observation** showing how much smaller the resume surface
becomes once a task closes and its handoff empties. It is not the evidence the
maintainer reviewed, and it does not replace the 660-word review-time figure.
Using it as the experimental measurement would retroactively shrink the
evidence the human actually read.

### Elapsed time is three different measurements

Provider-visible elapsed time, active work time and final review time are not
interchangeable, and the earlier single "~3 hours" figure conflated them
against a B1 baseline that used provider-visible wall-clock time:

| Measurement | B2/P1 | B1 |
|---|---:|---:|
| Provider-visible elapsed, first candidate commit to current head | see the Change Request | ~17 days |
| Active work time | not instrumented | not instrumented |
| Final timed disposition | ~27–32 min active, of which <12 min orientation | not applicable |

Only the first row is comparable with B1. The final timed disposition is now
instrumented and reported. Overall active work time across the slice remains
uninstrumented, and this record does not reconstruct it.

The amplification denominators are **not** the same measurement. B1 divided its
comment corpus by total repository text; B2/P1 divides review-time foreground
evidence by the words PR #25 added to normative surfaces at its accepted
checkpoint-8 state. The directly comparable figure is the provider comment
count: 407 against 0.

## Recorded human entry

- `active_owner_review_minutes`: **recorded**. The maintainer performed the
  timed semantic review of candidate `c5fff8c5…` and reported:

  | Activity | Minutes |
  |---|---:|
  | Orientation from the current projection | **< 12** |
  | Implementation diff scan | ~15–20 |
  | **Total active** | **~27–32** |

  The declared 20-minute budget covers final semantic orientation and
  disposition. That part was met with margin. The total exceeded it because
  this round also required an implementation review of 3,073 changed lines,
  which the budget never claimed to cover. One field proved insufficient: the
  measurement needs the two rows above, not a single number.

The 20 minutes budget final human semantic orientation and disposition over one
exact candidate. They are not a claim that a reviewer inspects every generated
test and evidence artifact line by line. The test is whether, inside that time,
the owner can state the semantic choice, intended effect, principal consequence
and strongest remaining uncertainty, and can still pause, reject or require a
split. If any of those is out of reach, the budget is exceeded regardless of
the clock.

### The measured object was the wrong one

The maintainer identified a confound during the timed review, and it is the
most important result of this slice.

**This round reviewed the Change Request that builds the envelope, not a change
reviewed through the envelope.** The projection is designed to make orientation
cheap, and it did: under 12 minutes for a fresh, accurate picture of where the
task stood. The 3,073-line implementation delta is the construction of the
tool. Those are different objects, and only the first is what B2 claims to
improve.

Therefore B2's headline claim — the same assurance for materially less owner
effort — **is not yet tested**. What is established:

- foreground evidence and provider comment volume are materially smaller than
  B1, by a wide margin; and
- orientation from a bounded projection fits comfortably inside a 20-minute
  budget.

What is not established is the comparison the experiment set out to make.
Owner interaction cannot be compared with B1 at all, because B1's owner time
was never instrumented. Only the next change, reviewed *through* the envelope
with owner time instrumented from minute zero, can close Issue #24's sixth
acceptance criterion.

### The resume surface saturated before the slice closed

`state.completed` reached its 20-item maximum while work was still being
recorded. The final three defect families and the integration itself could not
be written into the durable envelope, and had to live in this record and the
Change Request body instead. A durable resume surface that cannot record the
work it describes is a design limit, not a nuisance, and it is direct input to
the P2 schema.

### Disposition

The accountable maintainer accepted candidate
`c5fff8c5f5e22e14008e0d064f22f2671fdb7948` for integration. It was squashed to
`31266ff`, and the integrated tree is byte-identical to the accepted candidate.
The provider approval record is absent because GitHub refuses self-approval and
branch protection requires none; the disposition is recorded in the Change
Request body and in this record. Issue #24 remains open on its sixth
criterion.

## Defects, recovery and negative results

**Material defect 1 — working-directory dependence.** The declared
runtime-target gate was run against an earlier candidate and failed.
Task-envelope reference resolution defaulted to the process working directory,
so the required test
`test_duplicate_keys_and_nonportable_references_are_rejected` passed only when
the caller happened to run from a Gnostoa checkout. `knowledge self-check` is
both the `regression` suite and the documented consumer command, so the
packaged runtime image failed it out of the box. Caught by the declared gate.

**Material defect 2 — checkout-normalization fragility.** The first fixture for
the provider digest stored the issue body as raw Markdown bytes. A checkout
that rewrites line endings would have changed those bytes and broken the
required test, on a rule whose entire point is that no normalization applies.
Caught in owner review; the fixture is now JSON, so every line break inside the
body is an escape sequence and the parsed body is invariant under file
line-ending normalization. The test asserts that invariance directly.

**Material defect 3 — unbounded recursive alias traversal.** The duplicate-key
visitor walked the composed YAML node graph without cycle detection. A document
whose alias forms a cycle raised an uncaught `RecursionError` with a full
traceback and exit code 1, instead of the documented bounded validation error:

```yaml
recursive: &recursive
  - *recursive
```

This contradicted both the envelope's JSON-shaped schema and digest model and
the claimed fail-closed, no-traceback command contract. Caught in owner review
of the exact candidate.

The traversal was changed to track the active path to reject cycles and to
remember completed nodes so a shared subgraph is inspected once. A measured
side effect: on a 22-level acyclic alias document the previous traversal
exceeded a three-million-node-visit budget, while the corrected traversal
completes immediately. That is a consequence of visiting each node once, not a
claim of general YAML hardening.

**Temporal status.** At that checkpoint acyclic aliases were still supported
YAML, and this section described the state as it then stood. Family 6 later
withdrew that allowance by owner disposition, after alias amplification was
measured: anchors and aliases are now refused while scanning, before
construction. The correction above remains historically accurate for its
checkpoint; it is not the current contract.

**Material defect family 4 — the CLI error boundary was narrower than the
input it accepted.** An independent read-only robustness audit of the exact
candidate confirmed five manifestations of one root cause: `validate_main` and
`project_main` caught only `KnowledgeFormatError`, `OSError` and
`json.JSONDecodeError`, while the code beneath them could raise four other
exception types. Each produced a full traceback and exit code 1 instead of the
documented bounded path.

| # | Input | Escaping exception | Raised in |
|---|---|---|---|
| A1 | invalid UTF-8 envelope bytes | `UnicodeDecodeError` | source decoding |
| A2 | ~500 nested levels in a 1 KB file | `RecursionError` | PyYAML's composer, before any project code |
| A3 | `resource: "https://["` | `ValueError` | `urlsplit()` |
| A4 | a `!!binary` value with checkpoint validation | `TypeError` | `json.dumps()` in the digest |
| A5 | valid JSON that is not a valid schema | `SchemaError` | JSON Schema construction |

These are counted as **one defect family**, not five defects. A2 is the reason
the earlier recursive-alias fix was insufficient on its own: the recursion
happens inside the parser, so no detector running after composition can reach
it.

The correction establishes a pre-parse input contract — an explicit byte-size
bound and an explicit nesting-depth bound measured with YAML's iterative
scanner before composition — and converts each demonstrated boundary exception
into a bounded diagnostic. A1, A2, A4 and A5 now exit 2 on stderr. A3 is
deliberately different: a malformed URL inside an otherwise parsable envelope
is a validation issue, so it exits 1 through the validation path. No
`except Exception` was added.

**Deferred finding — loader-semantic and merge-key gap (Family C).** The same
audit confirmed, and this slice does not fix, that duplicate-key detection and
object construction do not share fully equivalent key semantics: detection
compares composed key nodes under `SafeLoader`, while construction uses
`KnowledgeLoader`, which drops the timestamp resolver, and keys on constructed
Python values. Keys whose source text differs but whose constructed values
collide are therefore not flagged, and YAML merge keys (`<<`) are not
prohibited, so merged properties are invisible to the check. The fixed task
envelope schema, with `additionalProperties: false` throughout and no
date-, bool- or numeric-shaped key names, prevents every demonstrated case from
silently overriding a valid schema-relevant property. This is recorded as a
bounded follow-up, and the wording in the code and the public workflow no
longer claims that all semantically ambiguous YAML is rejected.

**Temporal status.** This finding has since been split by Family 6. The
**merge-key portion is closed**: merge keys are now rejected while composing,
before construction, so merged properties can no longer be invisible to the
check. The **constructed-key semantic collision portion remains deferred**:
detection still compares composed key nodes while construction keys on
constructed Python values, and two source keys whose values collide are still
not flagged. Only the second half is outstanding follow-up work.

**Material defect family 5 — the checked bytes were not the constructed
bytes.** A focused review found that `load_task_envelope` re-read the path with
`load_yaml(path)` after preflight, so size, depth and duplicate-key checks
applied to one snapshot while the object was constructed from whatever the file
contained at construction time. A demonstration that rewrote the file between
preflight and construction produced an envelope carrying the *replacement*
content while reporting that the *original* had been checked. The same read
also pulled the entire file into memory before comparing it with the byte
bound: rejecting a 600 KB envelope first read all 600 KB.

Manifestations of the one root cause — a source read that was neither single
nor bounded — also covered the caller-supplied `--schema`, which had no size
bound at all and no conversion for recursion raised inside `json.loads` or
`Draft202012Validator.check_schema`. A schema of 300 nested `items` produced a
traceback.

Loading now captures one bounded immutable snapshot: the file is opened once in
binary mode, at most the limit plus one byte is read, and decode, scan, compose,
construct, validate and digest all run on that captured text. The path is never
read again, so a source that changes afterwards cannot alter what was checked.
The same helper bounds a supplied schema, and both recursion sites are
converted.

**Contract correction, not a product defect — the source bound rationale.** The
previous 128 KiB bound was justified by an ASCII serialization of a
schema-maximal envelope measuring about 74 KB. That reasoning was wrong: the
schema bounds code points, not bytes, so a schema-valid envelope written in
multibyte characters exceeded the bound while remaining entirely legal. A valid
envelope of 179,664 bytes was refused. The bound is now 512 KiB and is
documented as an operational limit on the YAML **source representation**, with
no claim that every schema-valid spelling fits. This is recorded as an evidence
and contract correction rather than a third product defect.

**Material defect families 6, 7 and 8 — the remaining input boundaries.** A
focused review confirmed three further families, each recorded as one family
rather than one defect per probe.

*Family 6 — YAML anchors, aliases and merge keys.* These have no JSON meaning
in a canonical JSON-shaped document, and a very small alias graph amplifies
enormously: twenty doubling levels occupy 434 source bytes and expand to
22,020,183 characters of JSON, about 50,700 times the source, during the
compatibility check, schema validation and digest. Ordinary aliases were
accepted, merge-by-alias and inline merge keys passed structurally, and
recursive aliases were caught only by a separate cycle check. The previous
requirement to preserve valid acyclic aliases is therefore **withdrawn by owner
disposition**: anchors and aliases are now refused while scanning and merge keys
while composing, before construction and before serialisation. Explicit
JSON-shaped mappings and sequences are unaffected.

*Family 7 — scalar literals the parsers refuse.* An unquoted integer above the
interpreter's integer-string conversion limit raised an uncaught `ValueError`
from `yaml.load`, and the same literal in a supplied JSON schema raised one from
`json.loads`. Both are converted narrowly at their own call sites; no global
`ValueError` catch was added around application logic.

*Family 8 — custom schema references reached outward.* A supplied schema with
`$ref` values of `file:`, `http:` or `https:` form, an unresolvable local
fragment, a self-recursive `{"$ref": "#"}` or a `$dynamicRef` all produced
tracebacks, and nothing prevented retrieval. Custom schemas are now bounded
local inputs: only same-document fragment references are supported, other forms
are refused before resolution, `$dynamicRef` is explicitly unsupported in this
portable mode, and validation runs against an offline registry whose retrieval
function refuses every request. The built-in schema and ordinary `$defs`
references are unaffected. A test asserts that no retrieval function is called.

Also corrected: an `https` reference with no authority, such as `https://` or
`https:///path`, was accepted. It is now an ordinary exit-1 envelope validation
issue. No network resolution or availability checking was added.

**A note on the false-ready counter.** It is unchanged at 5. The previous
candidate was published with an explicit statement that it was *not* ready for
timed review and that a verification pass would decide. Under this project's
recorded definition a false-ready outcome is a readiness signal that was wrong
when issued; no such signal was issued, so finding further defects in a
candidate already labelled unready does not increment the counter.

**Evidence defects corrected in owner review (3).** The review packet reported
a review surface measured before the measurement artifacts existed, which did
not match the provider's count for the exact head; and this record stated that
the task envelope carries the candidate identity, which it does not and cannot.
Both were evidence errors rather than product defects, and both would have
misinformed a timed review.

**False-ready outcomes (5).** An earlier candidate was presented as review-ready
while its own declared pre-merge gate was still unrun. A second packet was
presented for timed review with stale surface accounting. A third was presented
while the recursive-alias blocker was still present. A fourth was presented
while the wider error-boundary family was still present. A fifth was presented
while the source snapshot was neither single nor bounded. None reached
integration, but all five ready signals were wrong when issued.

The pattern matters more than the count: every required suite was green each
time. Green checks were a necessary and repeatedly insufficient condition for
readiness, and each defect was found by a human or by a gate that the automated
suites did not run.

**Route asymmetry, recorded as a durable failure mode.** The development
container binds the source at `/workspace`, so it always supplies a repository
root by accident; the runtime target does not. Development-container green is
therefore not sufficient evidence for a change touching the CLI or `tools/`.

**Interruption recovery: successful.** A fresh actor with no prior conversation
context reconstructed the authoritative state from the Decision 0016 resume
card, the roadmap projection, the live Issue and Change Request bodies and the
task envelope, then verified base, dependency, candidate and checkpoint
identities before acting. No historical ledger was replayed. This is the first
direct evidence that the resume contract works for an actor that was not
present for the original work.

**Reproducibility gap found and closed.** The recorded provider dependency used
the ambiguous identity kind `provider-body-sha256` with no written
canonicalization rule; reproducing the digest required guessing among five
candidate rules. The kind is now `github-issue-body-utf8-sha256-v1` with an
exactly specified byte sequence and offline evidence.

## New maintenance and tooling surface

P1 as a whole adds: one JSON Schema, one public template, one tool module, two
CLI commands, one test module, one guidance workflow, one durable state file
and one test fixture. Checkpoints 5 to 8 corrected the validator traversal,
established the bounded single-snapshot input contract and closed the remaining
input boundaries; the other post-review checkpoints added no product code — only
tests, a fixture, documentation and this record.

This is the surface that must keep earning its place. Decision 0016's stop rule
applies: if an increment does not improve a named outcome, simplify, remove or
redesign it.

## Status against Issue #24 acceptance

Satisfied so far: the change and comparison method were fixed before
implementation; the exact base, candidate, evidence and dependencies remain
reconstructable without replaying conversations; no agent-produced evidence is
represented as human acceptance; a fresh reviewer can identify status, question
and next action from one bounded projection; both positive and negative results
are reported here.

Not yet satisfied: the sixth criterion, that evidence amplification **and**
owner interaction fall materially below B1. Three things stand between P1 and
that criterion:

- P1 measured what it could: semantic orientation from the projection and the
  final timed disposition. Both are recorded above.
- B1's owner time was never instrumented, so a direct owner-effort comparison
  is unavailable and cannot be reconstructed.
- More importantly, P1 **built** the envelope rather than reviewing an ordinary
  change **through** it, so the object measured was not the object the claim is
  about.

P2 is therefore the first valid test of B2's headline claim.
