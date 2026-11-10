---
type: Decision
title: Read an Owner-declared frozen evidence archive whole for M13, and show its markers for the approval
description: "Decision 0112's M13 amendment, option (c) of #396's plan: a changed file that the protected target's frozen-archive declaration names by its path, Git blob and SHA-256 is read whole instead of by its hunks. L1 attaches the verified bytes of each hunkless added or modified file, within bounds, and reads no declaration. The producer reads a declared gzip tar within bounds, validates all of it first, and lists every marker occurrence in its members, with its member and line, as frozen evidence. A frozen record never denies; the verdict shows it for the native approval apart from the justified suppressions. Any mismatch, exceeded bound or unreadable member leaves the suppressions PARTIAL, and an undeclared binary stays PARTIAL. The declaration ships with the one archive the Owner chose for #396."
status: draft
generated:
  by: anthropic/claude-opus-5-5
  at: "2026-11-10T08:45:00Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/389
    title: Fail closed when required assurance evidence is missing, stale or incomplete
  - id: plan
    resource: https://github.com/ktogias/gnostoa/pull/396#issuecomment-6753827825
    title: "#396's M13 plan: its predicate A2 and the three options for the archive"
  - id: owner-choice
    resource: https://github.com/ktogias/gnostoa/pull/396#issuecomment-6754982324
    title: "The Owner's choice of option (c), relayed from the session; a relay, not an approval"
  - id: dispatch
    resource: https://github.com/ktogias/gnostoa/issues/325#issuecomment-6761114746
    title: "The Router's dispatch of the read-only admission packet"
  - id: packet
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6761333802
    title: "The admission packet: the archive read from its blob, the design, the bounds, the lineage at 1a79ef0d and the REDs"
  - id: pao
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6761351016
    title: "PAO's assessment: the packet approved, Q1-A, the frozen flag, the shipped entry and the factored reader"
  - id: route
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6761800629
    title: "The Router's dispatch of the implementation from the RED commit"
  - id: verdict
    resource: ./0112-admit-merges-through-a-required-provider-neutral-merge-admission-verdict.md
    title: The merge-admission verdict, whose M13 this amends
  - id: ledger
    resource: ./0129-match-inherited-analyzer-debt-against-a-protected-ledger.md
    title: The analyzer debt ledger, the precedent of a protected declaration that M17 reads
  - id: acquisition
    resource: ./0122-add-the-inventory-s-pinned-tool-and-secrets-families-inactive.md
    title: The pinned tool acquisition, whose bounded archive-member read this factors
x-project-knowledge:
  id: kit.decision.0134.read-an-owner-declared-frozen-evidence-archive-whole-for-m13
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /decisions/0112-admit-merges-through-a-required-provider-neutral-merge-admission-verdict.md
    - kind: references
      target: /decisions/0129-match-inherited-analyzer-debt-against-a-protected-ledger.md
    - kind: references
      target: /decisions/0122-add-the-inventory-s-pinned-tool-and-secrets-families-inactive.md
---

# Read an Owner-declared frozen evidence archive whole for M13, and show its markers for the approval

## Context

M13 reads only the lines a patch adds (source `verdict`). A changed file without hunks
leaves the suppressions `PARTIAL`, unless it is a removal or its head blob is Git's empty
blob. GitHub lists a binary file with no patch and no additions, so any added or modified
binary leaves M13 fail-closed.

#396 adds such a file, `spike-scripts.tar.gz`, the frozen evidence of its shell-parser
evaluation. The packet read it from its exact blob (source `packet`):

- blob `585d4608efc744818e06d773840ace0806b693a0`, SHA-256
  `f682e3bcc1fc12fc843f1bcaaa64905867d5f4782d9f038130d822f7800c3ea3`;
- 8,775 bytes of gzip, 40,960 bytes of tar, 13 regular members with flat, unique names;
- 10 marker occurrences, none with a reason: 6 `noqa` and 4 `# type: ignore`.

It was #396's only remaining M13 cause. The plan offered three options (source `plan`).
The Owner chose (c), a Decision 0112 amendment in its own protected change (source
`owner-choice`). The PAO approved the packet and answered its four questions (source
`pao`):

- **Q1-A:** L1 acquires the bytes and reads no declaration.
- **Q2:** a `frozen: true` flag on the suppression records.
- **Q3:** the declaration ships with #396's entry.
- **Q4:** one bounded archive-member reader, factored for both of its users.

## Decision

1. **The declaration.** It is `policy/merge-frozen-archives.yaml`, in the convention of the
   other merge declarations: `schema_version` `"1.0"`, an `id`, a `version` and one field,
   `archives`.
   - `archives` is a non-empty list of closed entries, with no path twice. Each entry has:
     - `path`, a plain relative path: no leading `/`, no empty, `.` or `..` segment;
     - `blob`, the file's Git blob id, 40 lowercase hex digits;
     - `sha256`, the SHA-256 of its bytes, 64 lowercase hex digits;
     - `format`, `tar+gzip`, the only value;
     - `decision`, the four-digit id, as text, of the Decision that chose it.
   - Anything else is an input error.
   - Merge evidence reads it from the project root, the protected target, as it reads the
     markers, the trust roots and the debt ledger. A candidate's own copy is never read.
   - Without the file, no archive is declared, and M13 is what it was.
   - It is under `/policy/`, a trust root, so M15 lists every change to it for the native
     approval.
   - `decision` is provenance. The authority for an entry is the Owner's native approval
     of the exact head of the change that adds it (M16).
2. **L1's acquisition.** The GitHub collector attaches a file's content when the file:
   - is `added` or `modified`;
   - has no patch and 0 `additions`;
   - lists a blob that is neither null nor Git's empty blob.

   It reads that blob through the shared client, `git/blobs/{blob}`, and attaches the
   bytes as `content`, in base64 on one line. It attaches nothing unless:
   - the answer is an object whose `sha` is the listed blob and whose `encoding` is
     `base64`;
   - the content decodes as strict base64 once its whitespace is removed;
   - `size` is an integer equal to the decoded length, and at most 1 MiB;
   - the blob id recomputed from the decoded bytes is the listed one.

   A refused read attaches nothing too, and the file list's coverage stays as it was. At
   most 8 blobs are read per comparison, in its order, and at most 4 MiB attached in all;
   a later file gets no content. L1 reads no declaration: an attached file that no entry
   names is `PARTIAL`, as today.
3. **The producer's read.** A hunkless file is read as a frozen archive only when one entry
   names its path, and:
   - its listed blob, the blob id recomputed from its `content` and that content's SHA-256
     are the entry's;
   - it is `added` or `modified`, with 0 `additions` and no patch, and its patch was not cut.

   A file with a patch, additions, a cut patch, or another status is read as before,
   whatever is declared.

   The archive is validated whole before any record is built:
   - **gzip:** one member, at most 8 MiB decompressed. The stream ends, with nothing after
     it.
   - **tar:** at most 256 members. Each is a regular, non-sparse file with a plain relative
     name, and no name repeats.
   - **text:** each member is strict UTF-8. Its lines are split at line feeds, as a
     patch's are.

   Every line of every member then goes through the declared markers' own rule. Each
   occurrence is a record, `{path, line, marker, justified, reason, member, frozen: true}`,
   in member order and then line order. Frozen records are charged as the command writes
   them, against the comparison's one budget of 1,000 records and 1 MiB. Past either, the
   list keeps its prefix and is `PARTIAL`. A read archive counts as covered.

   Any mismatch, exceeded bound or unreadable member leaves the file uncovered: the
   suppressions are `PARTIAL`, and that archive gives no record.
4. **The bounded member read is one helper.** The gzip and tar bounds are the ones the
   pinned tool acquisition already enforces (source `acquisition`). They are factored into
   one reader that both use. It also refuses data after the compressed stream, for both.
   The acquisition's tests keep their outcomes.
5. **The verdict.** A suppression record may carry `member` and `frozen`. `frozen`, when
   present, is the boolean `true`. A record with `member` has `frozen`, and a frozen record
   has a non-blank text `member` and a `line`. Anything else is malformed evidence.
   - A frozen record never denies M13, justified or not.
   - The verdict lists the frozen records for the approval as `frozen_suppressions`, empty
     when there are none, apart from the justified non-frozen ones.
   - A non-frozen record without a reason denies, as before. Evidence without the new keys
     means what it meant.
6. **The first entry.** The declaration ships with #396's archive, as the packet read it
   (source `pao`, Q3).

## Verification

- **RED first.** The tests were committed on protected `main`'s `1a79ef0d`, run alone, and
  failed for the missing behaviour. The undeclared binary's case was the kept
  characterization. They pin:
  - the declaration's shape and its read from the project root;
  - L1's attachment, its checks and its bounds;
  - the producer's identity checks, its status and hunk checks, each archive bound, and
    the shared budgets;
  - the verdict's frozen records;
  - the shipped entry.
- **GREEN.** They pass with this change, and the acquisition tests keep their outcomes.
- **End to end.** A declared archive goes through `evidence_for` and
  `merge_admission.evaluate`. M13 does not fail, and the verdict lists its markers as
  frozen.

## Consequences

- **#396:** after this lands, its next evaluation reads the archive, lists its 10
  occurrences as frozen, and M13 is no longer `PARTIAL` because of it. M16 stays the
  Owner's.
- **Each further archive** is an Owner decision, entry by entry, in a protected change that
  M15 lists.
- **L1 reads up to 8 more blobs** for a comparison with hunkless files, whether or not any
  is declared.

## Limits

- Only gzip tars of regular, UTF-8 members can be read. Any other binary stays `PARTIAL`.
- A frozen record's reason is kept as written and never judged adequate, as any other
  reason.
- A declared archive changed by even one byte no longer matches its entry, and is
  `PARTIAL` until its entry is updated.
