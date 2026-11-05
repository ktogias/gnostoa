---
type: Decision
title: Match inherited analyzer debt against a protected ledger that ships empty
description: "The M17 transition of #389's closure: a finding that matches an entry of the protected target's analyzer debt ledger exactly, by its item, rule, path, message, severity, run-bound configuration identity, analyzer identity and the content of its enclosing function or class, is listed as inherited and does not count. Any other finding counts as before. The ledger ships empty, so no finding is inherited until the owner approves an entry, and only a finding whose readback states a run-bound configuration, today the project inventory's, can match one. The owner's Option B dropped the DeepSource carried-forward rule this first proposed; DeepSource's adapter and full-report reader stay, as an optional source."
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
  - id: option-b
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6658166252
    title: "The owner's Option B: keep the empty ledger and its strict matching, drop only the DeepSource carried-forward rule"
  - id: exit
    resource: ./0130-retire-deepsource-as-merge-evidence-and-give-every-class-the-project-inventory.md
    title: The DeepSource exit, which retired DeepSource as merge evidence
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
    - kind: references
      target: /decisions/0130-retire-deepsource-as-merge-evidence-and-give-every-class-the-project-inventory.md
---

# Match inherited analyzer debt against a protected ledger that ships empty

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
     `addendum`), for the findings of every readback the bundle carries: Codacy's,
     SonarCloud's and the project inventory's. DeepSource, retired as merge evidence,
     gives none (source `exit`).
   - The step reads each Python finding's file (`.py` or `.pyi`) at the exact head through
     GitHub's contents API. The file is read as data: nothing in the head runs or selects a
     tool. It is read and parsed once for all its findings.
   - The read is bounded: 64 requests, 1 MiB each, and 8 MiB in all. Content whose encoded
     length is not the one its declared size implies is refused before it is decoded, so no
     more than one base64 block past the declared size is ever decoded; the decoded bytes
     must then be exactly the declared size.
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
     - the finding's `severity` at its proof, as text, or an explicit `null` for a
       provider that states none (owner [6620829215](https://github.com/ktogias/gnostoa/issues/389#issuecomment-6620829215) §1);
     - its `configuration`: the run-bound configuration identity the finding was proved
       under (§2);
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
   count. "Exactly" means the same item, rule, path, message, enclosing scope content,
   severity, configuration identity, tool id and tool name.
   - **The configuration identity** comes from the finding's own readback. Merge evidence
     derives it from three parts, and only when the readback states all of them:
     - the readback's adapter;
     - the protected profile digest its run was bound to (`native.profile`, with
       `source_binding` `BOUND`);
     - the effective identity of the finding's own producer, named by its `tool.id`
       (owner [6621293483](https://github.com/ktogias/gnostoa/issues/389#issuecomment-6621293483) §1).
     A finding whose readback states none of these, or no proved identity for its
     producer, never matches.
   - **A producer's effective identity** is the inventory adapter's
     `native.producers` entry: a digest over each of its invocations' version, settings
     and environment, from the inventory's own provenance.
     - Which producers are launched with an observed environment, mypy and Ruff today,
       is the inventory's own declaration, the one its source binding reads, never a
       record's shape. Any other producer is proved only in process, such as
       complexity; another process producer, such as shellcheck, is unproved.
     - A launched producer's settings are its argv before the `--` its builder puts
       before the file list, so the files it read do not change it. An in-process
       producer's settings are its own configuration, such as complexity's.
     - The environment is the observation's interpreter and its after digest.
     - A producer is left out when any invocation lacks a version; when, launched, it
       lacks its argv, that separator, its interpreter or its digest, or was not
       observed with its environment equal before and after it; or when, in process,
       its record carries an argv or an observation.
     So a new tool version, setting or environment unmatches each of its findings.
   - An entry absorbs one finding.
   - These findings never match:
     - one in a provider's security category (`security`, `vulnerability` or
       `security_hotspot`, in any case), whatever its entry says (source `pao`);
     - one without a rule, a path or a scope.
   - Nothing is matched unless M17's read is complete. Under a 1.1 declaration that is the
     completeness verdict; under 1.0 it is the findings' own coverage. Otherwise every
     finding counts, and no entry is called resolved.
   - An entry is listed under `resolved_debt` when it matches no finding and no
     unmatched finding is left at its item, rule and path. An entry whose finding changed
     in place is not listed: that finding still counts. Either listing has no effect.
4. **The regression rule.** A finding's identity includes the content of its enclosing
   function or class. So a change anywhere in that scope unmatches every finding in it, on
   changed and unchanged lines alike.
   - **The measure.** The message carries the measure, such as a complexity. So a worse
     measure does not match. A better one does not match either, until the entry is updated.
     This is stricter than the packet's "a measure no worse" (source `packet`).
   - **The severity.** Compared exactly, so a raised, lowered, new or dropped severity
     unmatches. A raised severity with the same message and scope is the case the owner
     named.
   - **The analyzer.** A change in the analyzer's identity matches nothing (PAO's P2,
     source `pao`). Neither does a change in its run-bound configuration, nor a finding
     whose readback states no configuration at all: an unknown configuration is not a
     comparable one.
   - **The read.** A stale, partial or unbound read matches nothing.
5. **The ledger is not activated.** The ledger ships empty, so no finding is inherited
   until the owner approves an entry. An entry is added only by a pull request on
   protected `main` that the owner approves. Each entry carries its proof:
   - a BOUND, COMPLETE authenticated readback listed it;
   - its scope was byte-identical on that protected commit;
   - its analyzer identity.

## Limits

- **Only configuration-bound findings can be inherited.** Today that is only the project
  inventory, whose readbacks state their protected profile's digest, bound to their run,
  and each proved producer's effective identity. DeepSource, Codacy and SonarCloud
  findings never match.
  - **DeepSource:** its API exposes no run's own configuration or analyzer version; its
    capability discovery is `CURRENT_NOT_RUN_BOUND`. Since Decision 0130 it gives the
    bundle no readback at all; its adapter stays, as an optional source.
  - **Codacy and SonarCloud:** their readbacks name no configuration.
  - Each can become matchable only when its adapter states a run-bound configuration
    identity, which is a change of its own.
- **A finding of a provider that states no severity** matches only an entry recorded with
  `null`, so a severity that appears unmatches it.
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
  - the evidence.
- **The end-to-end test.** It runs through `evidence_for` and `merge_admission.evaluate`,
  on the active providers' evidence: Codacy's, SonarCloud's and the inventory's. With the
  ledger's entry for a finding, M17 does not fail on it. With another scope, severity,
  profile or producer, a finding whose readback states no configuration, or no ledger,
  M17 fails.
- **The head read** is exercised on the inventory's readback: the bundle binds a
  document as the inventory job writes it, and gives its Python findings their scopes
  within the bounds.
- **The owner's checks before merge** (source `option-b`). Under the ledger this
  repository ships, which is empty, and in every class, end to end:
  - missing or incomplete required evidence still denies M2–M8 and M17: no readback,
    another head's, Codacy's read missing or unavailable, SonarCloud's inventory
    unavailable, either inventory read missing or partial;
  - every obtained finding still denies M17: a new one, a worsened one, one whose
    identity an entry could match, a security one, and Codacy's and SonarCloud's;
  - the shipped ledger changes no criterion's verdict or reasons against no ledger.
  The declaration's required items, their classes and their claims are main's: this
  change does not touch `policy/assurance-evidence.yaml` or its checks.

## Consequences

- **With the empty ledger, the matching changes no verdict:** no finding is inherited.
  The verdict also lists `inherited_findings` and `resolved_debt`, both empty, and the
  evidence carries `analyzer_debt`.
- **Each pull request's inherited findings** become an owner's decision, entry by entry, in
  a ledger pull request. A finding that a change makes worse, or adds, still denies.

## Amendments

*2026-11-05, the owner's Option B (source `option-b`).* This text narrows the version
#480 published at `ace8d7cd` (15077 bytes, SHA-256
`368460bf8cbcc31f11acc4304c553febf66fb2075b46186d32b70e5cd216f3d5`). The owner kept the
protected debt ledger, empty at delivery, with strict matching of the enclosing scope,
severity and configuration bound to the actual run, and dropped only the
DeepSource-specific carried-forward rule #480 introduced, its wiring and its tests.

- **Removed:** that version's item 5, the carried-forward comment, and each statement
  that the rule takes effect when this lands: the second half of its title, the last
  sentence of its description, its Context's paragraph on #477's carried-forward comment,
  item 6's, now item 5's, and its Verification's and Consequences' bullets on the rule.
- **Kept:** DeepSource's adapter and full-report reader, as on `main`. DeepSource stays
  available as an optional source, and a carried-forward comment keeps its DIFF read
  `PARTIAL`, as before.
- **Since that version,** Decision 0130 (source `exit`) retired DeepSource as merge
  evidence, so the bundle carries no DeepSource readback. The tests that took their
  findings from DeepSource take them from the active providers, and the owner's checks
  before merge are added to the Verification.

*2026-11-05, Codex on #480.* M17's guard refuses a security finding by its `category`, and the
project inventory, the only provider whose findings can be inherited, gave none. Its producer
now gives its own security classification as `category: security`, as Codacy's and SonarCloud's
adapters give theirs: Ruff's flake8-bandit rules (`S` and digits, such as `literal-secrets`'
`S106` and `unsafe-calls`' `S307`) and every finding of the `secrets` producer. An exact entry
that calls such a finding, say, `correctness` still absorbs nothing.
