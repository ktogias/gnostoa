---
type: Decision
title: Match inherited analyzer debt against a protected ledger, inactive until the owner approves an entry
description: "The M17 transition of #389's closure: a finding that matches an entry of the protected target's analyzer debt ledger exactly, by its item, rule, path, message, analyzer identity and the content of its enclosing function or class, is listed as inherited and does not count. Any other finding counts as before. The ledger ships empty, so no finding is inherited until the owner approves an entry. A carried-forward DeepSource comment no longer degrades the DIFF read when the same run's complete full read shows its finding gone."
status: draft
generated:
  by: anthropic/claude-opus-5-5
  at: "2026-11-03T21:40:00Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/389
    title: Keep merges possible while a vendor analyzer is unavailable
  - id: owner-decision
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6612057593
    title: "The owner's decision, section 3: prepare the M17 transition packet, with no activation"
  - id: owner-follow-up
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6614620697
    title: "The owner's follow-up: the concrete packet, its scrutiny and its implementation are authorized"
  - id: packet
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6614843940
    title: "The Implementer's M17 transition packet, with the gates measured per pull request"
  - id: pao
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6614901388
    title: "PAO's scrutiny of the packet: provider configuration drift (P2) and security findings"
  - id: amendment
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6614964854
    title: "The packet's amendment: where the scope comes from, and the implementation's lineage"
  - id: addendum
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6615072518
    title: "The addendum: the field name, the head read over REST, and the full-run remedy"
  - id: verdict
    resource: ./0112-admit-merges-through-a-required-provider-neutral-merge-admission-verdict.md
    title: The merge-admission verdict whose M17 this amends
  - id: readback
    resource: ./0107-run-the-analyzer-readback-for-every-pull-request-head.md
    title: The authenticated analyzer readback, which now reads each finding's enclosing scope
x-project-knowledge:
  id: kit.decision.0129.match-inherited-analyzer-debt-against-a-protected-ledger
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /decisions/0112-admit-merges-through-a-required-provider-neutral-merge-admission-verdict.md
    - kind: references
      target: /decisions/0107-run-the-analyzer-readback-for-every-pull-request-head.md
---

# Match inherited analyzer debt against a protected ledger, inactive until the owner approves an entry

## Context

M17 denies on every finding the analyzer readback acquires, with no waiver (source
`verdict`). DeepSource's full run lists the debt of every file a change touches, and some
of the modules those files import. So a change that touches an old file inherits that file's
findings. The packet measured this against protected `main`, by content, on three open pull
requests (source `packet`):

- #479: all 3 findings inherited;
- #477: all 16 inherited;
- #478: 82 of 128 inherited.

"Inherited by content" means that the finding's region, and the smallest function or class
enclosing it, are byte-identical on `main` at the same path.

The owner asked for a transition of M17 with no activation (source `owner-decision`):

- the smallest change, with a before-and-after table;
- a protected baseline and its ledger;
- a regression rule that is not changed-line-only;
- tests, and a separate proof for every gate.

The owner then authorized the implementation and its review (source `owner-follow-up`).

#477's M2–M8 is a separate obligation, with a separate cause. GitHub carries one DeepSource
inline comment from an earlier head to the current one. The adapter excludes such a
comment, and so it marks the DIFF read `PARTIAL`.

## Decision

1. **A finding's enclosing scope.** `enclosing` is a finding's smallest enclosing function or
   class. It has three fields:
   - `kind`, `function` or `class`;
   - its `name`;
   - `sha256`, the SHA-256 of its exact lines, decorators included. The lines are
     Python's own, split only at a line feed, a carriage return or both, and hashed with
     their endings, so a Unicode line separator inside a literal stays in its line.

   The readback's normalizer keeps it as a closed record, so a readback that carries it
   rebuilds exactly. Where the scope comes from:
   - The bundle step of the authenticated readback computes it (`collect_bundle`, source
     `addendum`).
   - The step reads each Python finding's file (`.py` or `.pyi`) at the exact head through
     GitHub's contents API. The file is read as data: nothing in the head runs or selects a
     tool. It is read and parsed once for all its findings.
   - The read is bounded: 64 requests, 1 MiB each, and 8 MiB in all. Content longer than
     its declared size is refused before it is decoded, so the bounds hold for the work done.
   - In these cases a finding gets no scope, and it is never matched:
     - the read fails;
     - the file is not a file, is over a bound, is not valid base64, has other than its
       declared size, or is not UTF-8;
     - the file does not parse;
     - the finding is at module level, or in another language.
2. **The ledger.** It is `policy/analyzer-debt-ledger.yaml`. Merge evidence reads it from the
   protected target, as it reads the trust roots and suppression markers. A candidate's own
   copy is never read.
   - It is a closed, versioned declaration.
   - Each entry has:
     - an `id`;
     - the finding's `item`, `rule`, `path` and `message`, as the readback lists them;
     - `enclosing_sha256`;
     - an `aspect`;
     - when the finding names one, the analyzer's `tool`;
     - its `provenance`: the protected commit it was proved on, the readback run that
       listed it, and the owner's admission.
   - An entry whose aspect is `security` is refused.
   - Merge evidence checks every entry with the verdict's own contract,
     `parse_analyzer_debt`. So the two never disagree on an entry.
   - Without the file, the evidence's `analyzer_debt` is `UNAVAILABLE`, and M17 is what it
     was.
   - A change to the ledger is under `/policy/`, a trust root (M15). The owner approves it.
3. **M17.** A finding that matches an entry exactly is inherited. It stays listed among the
   analyzer findings, and among `inherited_findings` with its entry's id, and it does not
   count. "Exactly" means the same item, rule, path, message, enclosing scope content, tool
   id and tool name.
   - An entry absorbs one finding.
   - These findings never match:
     - one in a provider's security category (`security`, `vulnerability` or
       `security_hotspot`, in any case), whatever its entry says (source `pao`);
     - one without a rule, a path or a scope.
   - Nothing is matched unless M17's read is complete. Under a 1.1 declaration that is the
     completeness verdict; under 1.0 it is the findings' own coverage. Otherwise every
     finding counts, and no entry is called resolved.
   - An entry that matches no finding is listed under `resolved_debt`, with no effect.
4. **The regression rule.** A finding's identity includes the content of its enclosing
   function or class. So a change anywhere in that scope unmatches every finding in it, on
   changed and unchanged lines alike.
   - **The measure.** The message carries the measure, such as a complexity. So a worse
     measure does not match. A better one does not match either, until the entry is updated.
     This is stricter than the packet's "a measure no worse" (source `packet`).
   - **The analyzer.** A change in the analyzer's identity matches nothing (PAO's P2,
     source `pao`).
   - **The read.** A stale, partial or unbound read matches nothing.
5. **The carried-forward comment.** Such a comment is still excluded from DeepSource's DIFF
   read.
   - **When the read is complete:** the same run's full read of the exact head is
     `COMPLETE`. It lists no finding at the comment's path and line, whatever its message,
     and none in that file with the comment's stated title, at any line. So neither a
     reworded title nor a drifted line hides a finding. Then the read records the comment
     in its native record, as absent from the full run.
   - **When it stays `PARTIAL`:**
     - the comment has no path, line or stated title;
     - the full read is of another run, head or provider, or is not complete.
   - **A finding the full run still lists** reaches M17 through that run.
   - Unlike the packet's first form, it does not also require the comment's review thread to
     be resolved: the readback does not read thread state, and reading it would be a new
     acquisition (source `addendum`).
6. **Not activated.** The ledger ships empty. An entry is added only by a pull request on
   protected `main` that the owner approves. Each entry carries its proof:
   - a BOUND, COMPLETE authenticated readback listed it;
   - its scope was byte-identical on that protected commit;
   - its analyzer identity.

## Limits

- **Configuration drift is not fully visible.** For DeepSource, the analyzer's configuration
  and version are provider-side. The readback shows only the finding's tool, so drift that
  keeps the tool's identity is not seen. This is a declared limit, not a proof.
- **SonarCloud's findings name no tool,** so their entries carry none.
- **A reworded message unmatches.** A provider that rewords a message unmatches its entries,
  and the finding counts until the entry is updated.
- **A failed head read counts.** When the head read fails, for example by a rate limit, the
  finding has no scope and counts.

## Verification

- **RED first.** Each step's tests were run on the parent first, and failed for the defect.
  Then they passed with the step's change, together with every analyzer-readback,
  merge-evidence and merge-admission test module. The steps:
  - the scope;
  - the head read;
  - the matching;
  - the analyzer identity and the security category;
  - the evidence;
  - the carried-forward remedy.
- **The end-to-end test.** It runs through `evidence_for` and `merge_admission.evaluate`.
  With the ledger's entry for a finding, M17 does not fail on it. With another scope, or no
  ledger, M17 fails.

## Consequences

- **With the empty ledger, every verdict keeps its outcome.** The verdict also lists
  `inherited_findings` and `resolved_debt`, both empty, and the evidence carries
  `analyzer_debt`.
- **The carried-forward rule takes effect when this lands,** because the readback runs
  `main`'s adapter.
- **Each pull request's inherited findings** become an owner's decision, entry by entry, in
  a ledger pull request. A finding that a change makes worse, or adds, still denies.
