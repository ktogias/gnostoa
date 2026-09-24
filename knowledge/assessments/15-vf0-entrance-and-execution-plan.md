---
type: Source
title: VF0 entrance evidence and bounded execution plan
description: Actual exact-main missing-pre-evidence reproduction, initial behavior map and unexecuted proof obligations for the proposed VF0 assurance gate.
status: draft
generated:
  by: agent:chatgpt
  at: "2026-09-24T14:55:00Z"
sources:
  - id: owner-scope
    resource: https://github.com/ktogias/gnostoa/issues/15#issuecomment-5803831361
    title: VF0 scope and sequencing
  - id: entrance-checkpoint
    resource: https://github.com/ktogias/gnostoa/issues/15#issuecomment-5816376488
    title: Pre-execution exact-main entrance contract
  - id: entrance-result
    resource: https://github.com/ktogias/gnostoa/issues/15#issuecomment-5816520445
    title: Verified VF0-E1 result and artifact identities
  - id: actual-run
    resource: https://github.com/ktogias/gnostoa/actions/runs/36015395550
    title: Actual parent-owned preparation entrance execution
x-project-knowledge:
  id: kit.assessment.15-vf0-entrance-and-execution-plan
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /decisions/0092-bind-verification-first-evidence-to-parent-owned-preparation.md
    - kind: references
      target: /requirements/bounded-behavioral-traceability.md
---

# VF0 entrance evidence and bounded execution plan

**VF0 is not implemented or active.** This is the initial record for the existing
#15 child, not a new Work Item, public contract or reduced-risk replacement.
The proposed [Decision 0092](../decisions/0092-bind-verification-first-evidence-to-parent-owned-preparation.md)
is separate from the observed experiment below.

## Exact observation

Subject: integrated #315 main `63fb3e7bf7a929c755250e6112f5a43a2b3db5c7`,
tree `fa4cb2db0ea072897391efd77deda95ac7e1f9a4`.
The evidence harness was committed separately at
`a7edb7bf3a44411b9a4097998a5b7224bcf08282`, path
`.github/vf0-entrance-reproduce.py`; it never entered main.

In an isolated throwaway clone, the exact parent-owned wrapper prepared a
synthetic new Python module without any prior-evidence receipt or provenance.
Its existing verifier accepted the resulting D0090 receipt. The new assertion
requiring rejection failed with `VF0_MISSING_PRE_EVIDENCE_WAS_ACCEPTED`.

| Observation | Actual result |
| --- | --- |
| Desired missing-pre-evidence rejection | RED: 1 assertion failure, 0 errors, 0 skips |
| Parent-tracked production and four authority files | Unchanged |
| Prepared delta | Only `tools/vf0_missing_evidence_probe.py` |
| Existing style/focused/diff checks | All four returned zero |
| Existing D0090 receipt verification | PASS |
| Empty candidate and stale-parent controls | Both correctly rejected |
| Preparation, style, focused check or verifier mocks | None |

The test module is synthetic input to the existing gate, not VF0 implementation
or a reproduction of #314's original analyzer defect. This result establishes a
missing new invariant, not a failure of D0090's existing normalization contract.
The capture workflow's success means it correctly retained the failing assertion;
it does not mean the proposed gate passed.

## Retention and reproduction

Artifact **10814840263**, `vf0-exact-main-entrance-20260924`, from the linked run,
expires **2026-10-01 14:48:40 UTC**. Its downloaded ZIP, canonical result and
script identities were independently checked locally:

| Object | SHA-256 |
| --- | --- |
| Artifact archive | `6cbeef0eedf53e2af27668bcd0122dbd6f2b8ec96b68e088ce230edeac1f82de` |
| `evidence/result.json` | `e909e8b3af1e2aed95d4eef7a964d9cddd7a31f0df528264d55e3cd4b132806e` |
| Predeclared reproducer | `f6bdd6c74a5cb9e098197831d1fa8541ae6f82b258d6a6b096b0da594d935337` |

The run also exported only the named main history. Empty-repository bundle
verification, fresh-clone full fsck and exact detached HEAD/tree/clean checks
passed on the producer and after local download. A nonexistent default branch
in the bundle caused a clone warning; explicit exact-commit checkout succeeded.
The artifact is experiment evidence, not an admitted production attestation.

Reproduce from the immutable script commit and exact subject above using the
retained workflow at `09957d875f7502b252fc047644c42b9c361d1550`. It builds the
repository development image, runs as a non-root UID without network or provider
credentials, and invokes real exact-parent preparation in a disposable clone.
After capture, both temporary support files were removed; support commit
`b65167703f4431f4bac96e6a2e7f0a4e1bda6a2f` has the original main tree.
History preserves the script even after artifact expiry. The scratch prepared
ref was released; no live candidate receipt is claimed from this experiment.

## Initial behavior map before production mutation

Task authority is the linked owner-selected VF0 scope. The mechanism paths below
are prospective; no new production implementation or independent reviewer result
exists at this checkpoint. The experiment is executor-authored evidence, not an
independent proof of test semantic sufficiency.

| ID | Required observable behavior | Proposed boundary / evidence | Execution and alignment | Executor / reviewer |
| --- | --- | --- | --- | --- |
| VF0-01 | Applicable semantic candidate without prior evidence is rejected | D0090 preparation; actual VF0-E1 entrance | RED; contradicts desired gate, supports gap diagnosis | Gap confirmed / PENDING |
| VF0-02 | RED uses unchanged parent production plus admitted evidence-only paths | Evidence producer; production-mutation and path-escape negatives | NOT RUN / UNKNOWN | PENDING / PENDING |
| VF0-03 | Matching hash or issuer label cannot authenticate a forged receipt | Trusted acquisition; unrelated run, wrong workflow, tampered archive and caller-hash negatives | NOT RUN / UNKNOWN | PENDING / PENDING |
| VF0-04 | Wrong parent/tree, policy, admission or retained test bytes rejects reuse | Parent-owned validator plus candidate relation | NOT RUN / UNKNOWN | PENDING / PENDING |
| VF0-05 | Modes obey effective class policy; late reconstruction cannot satisfy ordinary chronology | Mode matrix, forbidden downgrade and late-marker fixtures | NOT RUN / UNKNOWN | PENDING / PENDING |
| VF0-06 | Zero tests, skips, unrelated failures and timeouts cannot satisfy RED | Bound oracle and execution signals; non-vacuity negatives | NOT RUN / UNKNOWN | PENDING / PENDING |
| VF0-07 | Candidate cannot change the verifier or its trust inputs | Wrapper extraction and immutable authority membership | NOT RUN / UNKNOWN | PENDING / PENDING |
| VF0-08 | Independent CI reacquires provenance and checks the exact candidate | Real check-only provider consumer; end-to-end round trip | NOT RUN / UNKNOWN | PENDING / PENDING |
| VF0-09 | Valid evidence retains ordinary normalization and final verification | D0090 preparation/verification parity and valid mode fixtures | NOT RUN / UNKNOWN | PENDING / PENDING |
| VF0-10 | Bootstrap, artifact loss and rollback do not advertise false activation | Actual integrated-subject smoke and fail-closed availability tests | NOT RUN / UNKNOWN | PENDING / PENDING |

## Bounded execution plan

1. **Entrance complete:** retain actual VF0-E1, exact source and explicit limits.
2. **Decision/proof preparation:** reconcile the proposed acquisition boundary,
   trust configuration, admission inputs and version transition. Build a focused
   positive/negative provenance experiment before treating an acquired observation
   as trusted. The initial records-only candidate did not implement that
   experiment; the VF0-E2 result below records its subsequent bounded prototype.
3. **Evidence producer and verifier:** specify closed bounded inputs, preserve
   production equality and declared oracle identities, execute in demonstrated
   isolation, then retain observations outside candidate control. Keep the provider
   adapter separate from semantic policy logic. Establish focused RED first.
4. **D0090 authority evolution and CI:** wire the same authenticated relation into
   preparation and an independent check-only consumer. Preserve the v1 historical
   boundary and explicitly handle the introducing candidate's bootstrap.
5. **Critical acceptance and activation:** reconcile every map row with actual
   candidate/evidence, collect task-to-code and map-reconciliation reviews, obtain
   the exact integration effect, and verify a real integrated producer/consumer
   round trip. Only then consider VF0 closure and advancement to #318.

No independent stage may claim the overall gate is active. Artifact availability,
test/oracle adequacy, actual admission and isolation are material proof obligations,
not satisfied by a document, function name, receipt schema or green unit test.

## VF0-E2: bounded acquisition experiment

The [continuation checkpoint](https://github.com/ktogias/gnostoa/pull/319#issuecomment-5817094277)
bound this experiment and the three review repairs before record edits. Its
[read-only run 36020858876](https://github.com/ktogias/gnostoa/actions/runs/36020858876)
completed successfully using the one-shot workflow at
`9095c79d7f7fb1735fe6b3b148ac5908affb5a7b`, path
`.github/workflows/vf0-acquisition-probe.yml`. No candidate checkout or supplied
artifact code was executed, no Environment/analyzer secret was used, and the
job had only repository content, Actions and pull-request read permissions.

The live positive case reacquired the existing entrance run, its first-attempt
capture job and step outcomes, both pinned producer source files, artifact
metadata and download from GitHub. It validated TLS certificates/hostnames,
followed the bounded signed-asset handoff without forwarding the API credential,
compared the downloaded archive with the provider-reported SHA-256 before even
opening ZIP metadata, and read only the declared bounded observation member.
Run/attempt and artifact metadata were reread after acquisition. This was actual
provider access, not a mock network response or acceptance of an offline digest.

The 20 negative controls are deterministic local mutations of acquired data or
request inputs, not 20 hostile-provider executions. They rejected wrong run ID,
source commit, workflow path, attempt, repository and conclusion; wrong artifact
ID, expired flag, missing/malformed digest and wrong run association; altered
archive bytes; three unsafe URL forms, wrong API origin and asset host; support
producer non-admission with and without a self-asserted trust flag; and duplicate
JSON keys. The altered-byte test replaced the ZIP constructor with a failure
sentinel: digest rejection happened without calling that constructor.

The positive result recognizes the historical helper **only under this
experiment's fixed pins**. Both production-admission controls rejected it;
`production_producer_admitted` and `vf0_gate_implemented` remain false. The
branch-prefix rejection is an experiment safeguard, not a sufficient production
trust policy. No trusted observation type, reusable provider adapter, production
producer, D0090 receipt extension or independent CI consumer was installed.

### Retained evidence and limits

Artifact **10816258803**, `vf0-acquisition-experiment-20260924`, expires
**2026-10-01 15:31:55 UTC**. Downloaded bytes were checked locally against the
provider digest before reading its exact two members, `probe.py` and `result.json`.

| Object | SHA-256 |
| --- | --- |
| Experiment artifact archive | `f91cbb2b8a4c52ba92335301d84ba5fe34d1e39675152d925b83769b6390df9a` |
| Experimental probe | `8fe21fe8aa6328b67ebc97874d1fea9a8f1a793b3a0670578f10cd97ed04389e` |
| Canonical result including terminal LF | `64c9ae7735ab7a7c4cb1b2425b6428082c806c8df7bf5d49e751f74ee3d9285d` |

The earlier entrance artifact identity, content and RED disposition are unchanged.
This second experiment demonstrates bounded acquisition feasibility, not the
semantic sufficiency or chronology of that original test and not VF0 activation.
Only the reported cases executed: no malicious TLS server, ZIP-bomb corpus,
complete archive-parser fuzzing or hostile OS/provider experiment is claimed.

One material provider limit remains: artifact metadata binds a workflow run but
has no direct run-attempt field. The prototype admits only the known first
attempt and rereads it; it does not claim a general solution for rerun attribution.
The production design must authenticate attempt-specific observation identity,
handle stale/replaced evidence and bind the same identity in the independent
consumer. Likewise, fixed pins in a diagnostic script are not a substitute for
an admitted integrated producer and parent-owned trust configuration.

### Post-E2 behavior-map delta

Preserve the initial map above as the pre-production checkpoint. VF0-03 now has
**partial experimental support** for acquisition, digest rejection and rejecting
self-asserted support trust; production authentication remains **NOT RUN**.
VF0-04 and VF0-10 have partial experimental support for identity and availability
rejections only. All remaining production proof obligations, including VF0-08's
integrated producer/consumer round trip and VF0-01's actual enforcement, remain
open. The next bounded step is to reconcile the admitted producer/attempt and
trust-configuration contract, then establish focused conformance evidence for
its reusable acquisition adapter before changing D0090 authority. The sequence
VF0 then #318 and aggregate critical classification are unchanged.

## VF0-E3: attempt attribution and a rejected timestamp hypothesis

The [original checkpoint](https://github.com/ktogias/gnostoa/pull/319#issuecomment-5817575821)
preceded the temporary producer. [Run 36024200145](https://github.com/ktogias/gnostoa/actions/runs/36024200145)
completed two actual attempts on the same source
`75c55209f452fe57a1ed8cd0e79d9561642a1793`. Its only diagnostic job had no checkout,
caller inputs or candidate execution. Workflow `.github/workflows/vf0-attempt-probe.yml`
has provider blob `b418910265fdf30170fd1515518d41a25e8ae83f`; it remains an
experimental, non-admitted producer. No new live run was needed on resume.

All following times are UTC on 2026-09-24. Exact-attempt job metadata and
run-associated artifact metadata were acquired separately.

| Attempt / job | Upload-step start / end | Artifact / creation |
| --- | --- | --- |
| 1 / 107716443309 | 15:59:49 / 15:59:49 | 10819500924 / 15:59:49 |
| 2 / 107716928097 | 16:00:58 / 16:00:59 | 10819271025 / 16:00:59 |

**Negative result:** the predeclared strict upload-step-window relation rejected
both genuine cases because artifact creation equalled an interval boundary.
The interval was not widened after observation, and a job-window check was not
substituted as a successful production attribution rule. This falsifies that
bounded positive oracle, not all possible attempt-binding mechanisms.

### Separate diagnostic consistency observation

The [diagnostic-extension checkpoint](https://github.com/ktogias/gnostoa/pull/319#issuecomment-5817792898)
preceded its local evaluator. Authenticated retrieval of each exact job's full
log exposed the pinned uploader's artifact ID and ZIP digest. These matched
independently retrieved artifact metadata and the downloaded archive bytes.
Only the bounded single `observation.json` member was read after digest
comparison; neither archive content nor observation code was extracted/executed.

The [retained reconciliation](https://github.com/ktogias/gnostoa/pull/319#issuecomment-5817950344)
records **two matching diagnostic cases and 21 expected local-control
rejections**, separately from the two preserved timestamp-oracle rejections.
Inputs were reduced, manually transcribed fields from connector metadata/log
reads, not an implemented live adapter or raw-log parser. The controls covered
crossed attempts in both directions; missing/conflicting or mismatched publisher
identity; wrong source/repository/run/job/name; Boolean attempt; failed job;
incomplete coverage; missing/malformed digest; expired flag/elapsed expiry;
altered bytes before a sentinel ZIP constructor; caller-reasserted old evidence;
and attempted production use. They are not malicious-provider executions or a
complete parser/security corpus.

| Retained object | SHA-256 |
| --- | --- |
| Attempt 1 archive | `a0987a133c76b45a781e2a860a21eb25ac093f27d47ad012eacbed570dcf2b92` |
| Attempt 2 archive | `5f205e7bd7e156cbc010b68a721dbce758b96301e01829b0366a603344fa2249` |
| Attempt 1 observation | `c6ed71976ff3f2f24c17c29cc73f3a4ff7d1903776aed6dc5dcc75d0814fdf06` |
| Attempt 2 observation | `ad33c7fc73e873f944127435fe4845c6db03cda5ed5dfa9e1cb1a5e70711c988` |
| Local replay source | `5fe5afc5232d306ce82ee2c5a248d182c18e9a61dc5588972a3edc8036c25251` |
| Local result including terminal LF | `e97753ced9fa94da1d3826a17696e8527e408a929f6c5e7c8bd99f74d1a583d8` |

Artifacts expire respectively on **2026-10-01 15:59:49 UTC** and
**2026-10-01 16:00:58 UTC**. The replay source/result are retained in the local
handoff, not claimed as provider-produced test artifacts. Its fixed historical
comparison cut, `2026-09-24T16:15:00Z`, does not assert continuing availability.
The immutable workflow source survives helper cleanup and artifact expiry;
reproducing a later live run produces new identities, not the historical result.

### Disposition and next proof obligation

Keep the timestamp hypothesis rejected and the log consistency observation
strictly diagnostic. Candidate-controlled logs can forge uploader-looking text;
this experiment's closed support job does not admit arbitrary job logs or itself
as a production trust root. The proposed parent-owned trust and external-admission
inputs are now explicit in Decision 0092, but their production acquisition and
consumer contracts remain unimplemented.

Next, freeze a closed publisher-record protocol and its isolated emission,
external-admission inputs and bounded acquisition contract; establish focused
failing conformance evidence before implementing the reusable adapter. D0090
authority evolution and the real integrated producer/consumer round trip remain
separate subsequent obligations. All ten original gate-behavior rows still need
executed support; E3 does not close VF0-03, VF0-04, VF0-08 or VF0-10. VF0 remains
critical and inactive, with #318 still after its acceptance.

## VF0-E4: live closed-record acquisition across two attempts

The [pre-execution checkpoint](https://github.com/ktogias/gnostoa/pull/319#issuecomment-5818227485)
fixed the diagnostic protocol and negative-control categories before publication.
The [executed reconciliation and record-edit checkpoint](https://github.com/ktogias/gnostoa/pull/319#issuecomment-5818383699)
precedes this assessment-only append. All earlier assessment bytes, including
E3's rejected timestamp hypothesis and the original ten-row map, are preserved.
This result advances experimental acquisition, not production VF0 enforcement.

### Actual executions and bounded protocol

[Producer run 36029088664](https://github.com/ktogias/gnostoa/actions/runs/36029088664)
completed two actual attempts on source
`ddd6a38b5bad2d6a5bd0794300684e8198889308`, path
`.github/workflows/vf0-publisher-probe.yml`. Its `publisher` job had no candidate
checkout, caller input or test execution. A separate transport-only job exported
the exact starting PR source without executing repository code. The publisher
created one fixed diagnostic observation and uploaded it with the already-used
pinned upload-artifact action, without overwrite.

After upload, a separate controller step emitted exactly one
`VF0_PUBLISHER_V1 ` record. The bounded canonical ASCII JSON has a closed key
set: schema, numeric repository/run/attempt, exact source commit, publisher role,
artifact ID/name, archive SHA-256, observation SHA-256 and fixed diagnostic-input
SHA-256. Numeric publisher-job identity is independently supplied by the
provider's exact-attempt jobs endpoint and associated log endpoint; the role
string inside the record is not that identity. The runner timestamp prefixes
frame log lines only; no timestamp interval supplies attempt attribution.

[Consumer run 36029757177](https://github.com/ktogias/gnostoa/actions/runs/36029757177)
completed successfully on workflow source
`335da3f966083ef6b637721ae6f12edf64a08366`, executing the exact helper at
`50bd8ed60dfb83a6105adb67bd76c56d5c735d64`, path
`.github/vf0-publisher-consumer.py`. It had only contents/Actions read permissions
and used the job token, not an Environment/analyzer secret. Unlike E3, this
consumer acquired and parsed actual raw provider logs itself: no manual
transcription or mock network response supplied its positive observations.

The live path reacquired the pinned producer workflow bytes and Git blob
identity, current run, exact-attempt run/job metadata, raw publisher-job logs,
artifact metadata and downloaded bytes. It required certificate/hostname-validated
HTTPS and a bounded signed-download handoff without the API credential for both
logs and archives. Full archive SHA-256 comparison preceded ZIP parsing. Only
one bounded regular `observation.json` member was read, never extracted or
executed. Run/job/artifact/log state was reacquired and reconciled after download.

| Attempt | Provider publisher job | Artifact | Acquisition disposition |
| --- | --- | --- | --- |
| 1 | `107732969976` | `10820892833` | Historical diagnostic only; not current compliance |
| 2 | `107733318066` | `10820783107` | Matching current diagnostic attempt |

Both records matched their independently retrieved artifact metadata and bytes.
The first attempt was not admitted as current evidence after the rerun. Supplying
either actual record for the other attempt rejected with `RECORD_SUBJECT`.
These are two matching diagnostic observations, not two production admissions.

### Executed controls and retained identities

The consumer executed **35 expected fixture/mutation rejections**: 33 bounded
controls over the acquired data plus both actual cross-attempt substitutions.
They cover missing/duplicate/conflicting/malformed/noncanonical records,
duplicate keys, unknown key/schema, Boolean numeric identity, wrong
repository/run/attempt/source/role/input/name/digest, changed or arbitrary source,
oversized logs, stale/moved attempts, incomplete run/job coverage, failed
publisher, mismatched/expired/changed artifact metadata, wrong observation digest
and altered archive bytes. A failing ZIP-constructor sentinel confirmed the
altered-byte rejection occurred before archive parsing.

These are not 35 hostile-provider executions. Attempt movement and failed or
unavailable state were represented by deterministic input mutations; no real
concurrent rerun race, hostile TLS server, malicious OS, complete ZIP corpus or
parser fuzz campaign was executed. An initially separate synthetic positive and
33 controls passed locally before the helper was published. Those synthetic
results are not counted again as additional live cases.

Artifact **10821163285**, `vf0-e4-live-acquisition-36029757177`, expires
**2026-10-01 16:47:16 UTC**. It retains the two raw logs, downloaded diagnostic
archives, corresponding metadata, exact publisher/consumer source and result.
Its nine members were inspected locally only after the complete archive digest
matched independently retrieved provider metadata. The retained source bytes
matched local preparation; raw-log/observation replay matched both observations
and all 33 common controls. The result separately retains both cross-attempt
rejections executed by the consumer.

| Object | SHA-256 |
| --- | --- |
| E4 evidence archive | `c8c1960316e486faf62da75a586878d0a18ed5c6a56a2004f405a51b5a40eed8` |
| Canonical `result.json`, including terminal LF | `e7a8707efa8be672454d392d6f995547eeeee7f716b2d5d7929a06948b9c16ee` |
| Publisher workflow | `49bf2b3827303bc4f9fcea16935789147c446d2d359b2e5b65e0c609984df4fb` |
| Consumer helper | `d7b7ef99c4f6904815943fd0293fcd150c931684baa162923e8f16d349375139` |
| Attempt-1 diagnostic archive | `eced24251627032b6207c6fee259c51c2b9771d40f7de2c6e274a9eb6d8c6146` |
| Attempt-2 diagnostic archive | `aafe31bd0f785c3a40d1a6ce08cfb521352bd91fc1cc3cc73837f9b996d22a48` |

All three support files were removed by
`9079575695e43fdbc86dd08737d4adf7f54719ed`, restoring the pre-helper tree
`143375e2ca50f41cd4ca4104880a776b907cae5d`. History and artifacts remain retained;
no helper entered this PR or main. Local retention does not extend provider
availability or authenticate a later offline compliance claim.

### What this does and does not establish

The experiment supports a specific composite attempt-attribution route: exact
provider job origin plus a closed, fixed-source publisher record, independently
reconciled with artifact metadata and bytes. Neither a marker, raw log, source
hash, artifact name nor payload assertion is sufficient alone. The parser is a
diagnostic helper, not an API that can turn arbitrary caller bytes into an
authenticated observation. The pinned support producer is still not integrated
or admitted for production.

In particular, the diagnostic publisher never ran hostile candidate/test code.
Absence of that code is not proof of sandbox isolation, protected controller
outputs or safe handling of a real evidence-only test delta. Separately
authenticated human admission, effective class/mode policy, semantic non-vacuity,
ordinary chronology and parent-production equality were not implemented or
proved by this diagnostic input. No new signing service or dependency was added.
The provider-neutral semantic relation and proposed Decision 0092 remain distinct
from this GitHub-specific experiment.

VF0-03 gains bounded executed support for actual closed-record acquisition;
VF0-04 gains evidence for artifact/observation and attempt mismatch rejection.
Neither row is complete. VF0-02/06/07 still require real isolated evidence-producer
and authority tests; VF0-01 enforcement, VF0-08's integrated independent consumer
and VF0-09 preparation parity remain open. No original row is waived or closed.

The next bounded production-preparation work is to establish the externally
admitted input contract and demonstrate isolation between evidence execution and
controller/publisher authority, then establish focused failing conformance on the
exact parent before implementing the reusable acquisition boundary and separately
admitted D0090 authority evolution. The E4 helpers are reusable experimental
reference material, not a second permanent pipeline. VF0 remains **critical and
inactive**; the sequence remains **VF0 then #318**, with no merge authorization,
Q0 activation or broader #15 completion supplied by this result.
