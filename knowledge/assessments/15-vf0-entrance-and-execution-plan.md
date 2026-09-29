---
type: Source
title: VF0 entrance evidence and bounded execution plan
description: Exact-main missing-pre-evidence reproduction, evolving component evidence and unexecuted proof obligations for the proposed VF0 assurance gate.
status: draft
generated:
  by: agent:chatgpt
  at: "2026-09-27T15:46:50Z"
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

**VF0's enforcement gate is not implemented or active.** Private relation and
execution components exist without production invocation. This is the initial
record for the existing
Issue #15 child, not a new Work Item, public contract or reduced-risk replacement.
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

## VF0-E5: actual evidence/controller isolation and bounded cleanup

The [pre-execution checkpoint](https://github.com/ktogias/gnostoa/pull/319#issuecomment-5818685504)
preceded the diagnostic controller and workflow. The
[executed reconciliation and pre-edit checkpoint](https://github.com/ktogias/gnostoa/pull/319#issuecomment-5819075808)
precedes this assessment-only append. All 26,710 preceding assessment bytes,
including the original behavior map and E3's rejected hypothesis, are preserved.
E5 tests a fixed adversarial evidence program in actual containers; it does not
implement human-admission acquisition or activate VF0.

### Failed executions and repair chronology

[Run 36033242673](https://github.com/ktogias/gnostoa/actions/runs/36033242673) and
[run 36034256533](https://github.com/ktogias/gnostoa/actions/runs/36034256533)
remain **FAILURE**. Both retained five completed-case captures and the overflow
container configuration, but neither retained an overflow capture or final
result. The provider logs reported `TimeoutExpired`, not a detailed traceback.

The first [repair checkpoint](https://github.com/ktogias/gnostoa/pull/319#issuecomment-5818858503)
preceded a narrow attachment-wait fix. The exact published cleanup block was
reproduced locally using a real finite full-pipe child: two tests, one assertion
failure, zero errors, then two passing tests after repair. The second real run
still failed, demonstrating that this local test did not cover the preceding
container-removal step or full cleanup ordering.

The next [repair checkpoint](https://github.com/ktogias/gnostoa/pull/319#issuecomment-5818979327)
recorded a fresh exact-finally-block RED: four tests, two assertion failures,
zero errors. A real blocked pipe client and an instrumented removal boundary
showed that removal preceded client closure, and removal failure skipped client
cleanup. This was an ordering test, not simulated Docker assurance. The repair
closes/reaps the attachment first, always attempts container removal afterwards,
and verifies absence independently. All four local tests then passed; the actual
OCI run below established the repaired full path. Output backpressure is the
supported diagnosis, but the original timeout's exact call site was not logged.
Neither earlier failure is retrospectively converted into success.

### Actual successful subject and outcomes

[Run 36035259818](https://github.com/ktogias/gnostoa/actions/runs/36035259818),
job `107753623007`, succeeded on workflow source
`578a8809681ac7e69b27c531973cfbaa6a591224`, executing controller
`eb05bf43a9b8bdfc994287eeaf095597178e402f` at
`.github/vf0-isolation-probe.py`. The development image was built from exact
parent `63fb3e7bf7a929c755250e6112f5a43a2b3db5c7`, tree
`fa4cb2db0ea072897391efd77deda95ac7e1f9a4`, and bound to local image identity
`sha256:746284ee8836ccf6c1a18fcbc27ef03b59b741c8ea494a984fa81331b5539c62`.
This is an executed image binding, not a reproducible-build claim.

The controller materialized **613 exact regular parent files** plus only the
fixed `tests/vf0_e5_probe.py`. Five preflight mutations rejected before container
creation: changed production bytes, undeclared file, symlink evidence, wrong
parent and wrong tree. Before initial publication, an arbitrary 4 MiB member
limit was found to reject an existing 7,843,840-byte parent archive; materialization
was corrected to exact Git-declared sizes within a 32 MiB aggregate bound.
This setup correction did not alter the runtime or acceptance oracle.

| Actual OCI case | Controller-observed outcome |
| --- | --- |
| Parent-function characterization | Exact workspace module imported; three fixed assertions; exit 0 |
| Fixed adversarial isolation probe | Twelve fixed checks returned true; exit 0; parent and controller canary unchanged |
| Fake publisher/workflow-command output | Captured as untrusted bytes only, not replayed to the workflow log |
| Claimed RED with exit 17 | Exit 17 recorded; no RED or production receipt issued |
| Timeout with spawned descendant | Five-second deadline; owned container removed and absence verified |
| Unbounded stdout attempt | Output-limit termination; 65,536 bytes retained, at least 73,728 observed; container absence verified |

All six cases recorded unchanged parent production/controller canary and verified
container removal. The container had a read-only root and source mount, no
network, no capabilities or privilege escalation, UID 10001, 256 MiB memory/swap,
half a CPU, 32 PIDs and bounded temporary storage. No host Git metadata, Docker
socket, credential environment or command-file/controller directory was mounted.
The fixed probe attempted writes, UID escalation, symlink/proc-root access and
network connection; its twelve returned booleans are not an authentication
mechanism for arbitrary child assertions.

The evidence bytes, five-second execution deadline, combined 65,536-byte capture
ceiling, removal bound and OCI restrictions were unchanged across repairs.
Container exit and termination are controller observations. This diagnostic
never issues production receipts at all: preserving fake success text as data
is not proof that an implemented production gate rejected a forged receipt.
No resource-exhaustion stress corpus, hostile kernel/runtime/provider-admin test,
complete sandbox certification or general test-oracle sufficiency is claimed.

### Retention, cleanup and next obligation

Successful artifact **10824390744**, `vf0-e5-isolation-36035259818`, expires
**2026-10-01 17:35:29 UTC**. Its 24 bounded members retain exact controller/evidence
source, image/runtime metadata, six container configurations/captures, parent
manifest and result. The whole archive digest was compared with independently
retrieved provider metadata before ZIP parsing. Local offline consistency replay
checked all three historical archives, retained failures, source identities,
limits, configurations and six outcomes; it did not execute artifact code,
repeat Docker isolation or establish current provider availability.

| Retained object | SHA-256 |
| --- | --- |
| First failed-run artifact 10823737447 | `2d1e4021b1f229f927d9ddf4ae263fc292e5aefec45938fdb269fe8fac1913fb` |
| Second failed-run artifact 10823579024 | `e171d7299e334abb0c71721b28eeddebdd1f16e7850fa628ebc08095b319c760` |
| Successful artifact 10824390744 | `4b8060da18a370350b077153c433e388c79b17d58a806d6b966ae4d28f0d163b` |
| Successful canonical result, terminal LF included | `eacb41f24e49f675ec9160455e2075285d887883bd9d34a6cafee9c9389a9a70` |
| Final diagnostic controller | `72df2689f653eb4e0f195eec1e9402403ae468d4621df743818d7dd6e258114c` |
| Unchanged fixed evidence program | `79c9df97e7f075d2e1f579ae6635b707750c2f9c2c1b58ef655fecf7683f5418` |

The failed artifacts expire respectively on 2026-10-01 at 17:18:33 and 17:27:16
UTC. Cleanup `6e1fa70a1842695698202aa1d739e4bb1b7ac57e` removed both E5 support
files and restored the pre-helper tree
`9b4d7c223eb82a9739c12e5e5221c6207f1288bd`; history and artifacts remain retained.
No helper entered this PR or main. Direct GitHub DNS and Docker were unavailable
locally, so the actual OCI execution used this bounded provider recovery route;
local source transport was independently digest-checked, bundle-verified and
fscked. This conditional route is not the default when direct tooling is available.

E5 gives partial experimental support to VF0-02/06/07/10 without closing any row.
Its fixed allowlist and synthetic canary do not represent independently
authenticated human admission. Next, establish that external admission/input
contract and its failing conformance cases, then compose qualified evidence
execution with reusable acquisition and separately admitted D0090 authority
evolution. E4 and E5 remain separate experiments, not an integrated authenticated
producer/consumer round trip. Do not rerun them merely to regenerate green
results. VF0 remains **critical and inactive**, with missing-evidence enforcement,
semantic non-vacuity, preparation parity and integrated-consumer obligations
open. The sequence stays **VF0 then #318**; no merge, Ready transition, production
trust or broader #15 completion is authorized by this record.


## VF0-A7: normalized relation core

The [owner-approved bootstrap method and additional connections](https://github.com/ktogias/gnostoa/pull/319#issuecomment-5823426881)
allow bounded continuation, not merge, producer trust or activation. The
[pre-edit C1-C7 checkpoint](https://github.com/ktogias/gnostoa/pull/319#issuecomment-5823516283)
bound the exact parent `4ef62a31424bf9d58e49bb4e591f1a827a89a506` before creating
`tools/vf0_contract.py`. The entry-point conformance test failed with one explicit
assertion before that module existed. This is **interface conformance RED**, not
a behavioral producer RED receipt or a replacement for the actual E1 gap.

The private relation module implements closed, bounded normalization and relation
checks without filesystem, network or process operations. Its result is always
`authentication=NOT_ESTABLISHED`, `compliance=false`, `vf0_active=false`, including
when the asserted relation matches. Supplied policy, classification, principal,
record hashes, guarantees and observation times remain untrusted data. The
admission time is when the observer acquired the disposition, **not an invented
native approval timestamp**. No object deserializer, self-consistent payload or
`VERIFIED` string authenticates its own provenance. A future protected composition
must independently acquire the effective policy, admission, source, exact attempt,
archive bytes, actual outcomes and guarantees before relying on a matching
relation. The module neither reads effective policy nor issues a D0090 receipt.

| Obligation | Implemented, locally executed support | Remaining limitation |
| --- | --- | --- |
| C1 closed bounded inputs | Duplicate/unknown/missing fields, non-finite values, excessive bytes/depth/nodes, cycles and strict integer negatives | No unbounded fuzz or resource-exhaustion certification |
| C2 exact relation | Request/policy/admission/material hashes, parent/tree, allowed changed paths and retained test bytes; a candidate declaring changes cannot retain the parent tree | Actual source/path classification and byte acquisition belong to protected composition |
| C3 modes and time | RED/characterization/structural/emergency controls, forbidden mode, late reconstruction, zero cases/skips/unrelated failures and freshness boundaries | Fixture policy and asserted observations are not effective policy or executed producer evidence |
| C4 provider isolation | Two different native fixture layouts normalize to matching outcomes; opaque attempt and namespace collision negatives | No live second-provider support |
| C5 capability evidence | Every required guarantee rejects missing/unknown/unsupported/contradictory state or absent retained identity | Record hashes and state labels do not authenticate guarantees |
| C6 navigation separation | Wrong-subject/unsafe link mappings reject independently; missing links leave the relation unchanged | URL filtering is not origin ownership, renderer escaping or provider authentication |
| C7 no self-authentication | Fully matching forged input still has no authentication, compliance, preparation or write authority | Parent-owned acquisition and preparer integration are not implemented by this module |

The focused suite contains **32 tests** with additional negative subcases. Local
Ruff 0.16.0 formatting/lint and strict mypy 2.3.0 cover both new files. The tools
were recovered from the unchanged parent development lock through
[read-only transport run36070735299](https://github.com/ktogias/gnostoa/actions/runs/36070735299),
then installed offline with hash enforcement in an external virtualenv. Archive
10838570896 SHA-256 `44e29ed4785aa1178a0af95c34372b632700adab28a7baa449f2e6f3c9e92625`
was verified before ZIP parsing; all 67 wheels match the parent lock. This does
not add a dependency. Cleanup `623ba257ad0bcc9819dee4aa41b72938fb78ac55` removes
the temporary transport workflow. No new source export was necessary.

This helper-only candidate must still cross ordinary exact-parent D0090
preparation before publication; it does not consume the one-time authority-change
exception. Exact receipt, final CI and individual reviewer dispositions are
retained in the PR candidate seal, not predicted here. The original ten VF0 gate
rows and E1-E5 observations above remain unchanged. A7 is not the integrated
producer/consumer, does not make supplied records authoritative and cannot close
VF0-01/03/07/08/09/10. Protected composition and the single introducing authority
transition remain subsequent work under the already approved method.

## VF0-A7/A8 history and current component boundary

This section is the replaceable current component view. The
[immutable pre-reconciliation chronology](https://github.com/ktogias/gnostoa/blob/a859d597d1d2fcd30f68106e5532bdae537ae6ac/knowledge/assessments/15-vf0-entrance-and-execution-plan.md#vf0-a7-chronology-a8-and-bounded-execution-candidate)
retains the original 32-test A7 checkpoint and the later 33–138-test results,
individual repair descriptions and their limits. Removing their rolling prose
from this view does not rewrite any earlier result. The original E1 RED, rejected
E3 timestamp hypothesis, failed E5 runs and initial failed A8 run remain retained.

A7's [C1–C7 checkpoint](https://github.com/ktogias/gnostoa/pull/319#issuecomment-5823516283)
preceded relation-core production edits at parent
`4ef62a31424bf9d58e49bb4e591f1a827a89a506`. Its interface-conformance assertion RED
is not a producer behavioral RED receipt and does not replace E1. The later
[R1–R5 checkpoint](https://github.com/ktogias/gnostoa/pull/319#issuecomment-5827810399)
and [exact-parent continuation](https://github.com/ktogias/gnostoa/pull/319#issuecomment-5830270213)
bound the private execution component before implementation.

The successful [A8 run 36099667712](https://github.com/ktogias/gnostoa/actions/runs/36099667712)
composed a request-bound native approval, isolated characterization, retained
publisher evidence and independent diagnostic relation evaluation on support
source `223bc20bef6b3d0f4efb2c710b1ec202aa49aceb`. Its
[retained result and limits](https://github.com/ktogias/gnostoa/pull/319#issuecomment-5827762406)
record one MATCH and six local negative substitutions. The first approved
[run 36079920491](https://github.com/ktogias/gnostoa/actions/runs/36079920491)
remains FAILURE; neither its approval nor its result is transferred to the repair.
A8's fixture policy and guarantee assertions are diagnostic assumptions, and its
MATCH still reports `authentication=NOT_ESTABLISHED`, `compliance=false`, and
`vf0_active=false`. It establishes no production trust or effective D0090 gate.

### Direction-correction checkpoint

The [whole-PR audit plan](https://github.com/ktogias/gnostoa/pull/319#issuecomment-5849874637)
reconciles the original scope with the owner's request for autonomous correction.
[Relation RED](https://github.com/ktogias/gnostoa/pull/319#issuecomment-5849891284)
and [execution RED](https://github.com/ktogias/gnostoa/pull/319#issuecomment-5849905214)
were recorded against unchanged parent `a859d597d1d2fcd30f68106e5532bdae537ae6ac`
before production edits. They expose four in-scope defects: final production
bytes required before RED; a nonempty evidence delta retaining the parent's tree;
a caller-mutable immutability claim; and an unconstrained OCI platform/config.

The correction removes the future-production precommitment and mutable capability
flags. It preserves parent/evidence/oracle/scope binding, distinguishes the later
candidate from its evidence subject, and requires the actual Docker execution to
use its inspected linux/amd64 image configuration.

The subsequent [cleanup RED](https://github.com/ktogias/gnostoa/pull/319#issuecomment-5849969494)
exposed a fifth defect during the full Sonar/source audit: a missing Docker socket
was misclassified as a missing container. Cleanup now requires the native inspect
absence diagnostic for the exact owned reference and always inspects after removal;
transport errors remain unknown and fail closed. Native Docker 26/29 diagnostic
observations and all four cleanup branches are covered by the correction.

The pure relation checker still
cannot authenticate declared hashes or classify semantic sufficiency. No general
runtime registry or new authority mechanism is introduced.

The [AUD08 follow-up](https://github.com/ktogias/gnostoa/pull/319#issuecomment-5850159967)
first reproduced mutation of validated backend configuration, then froze the
built-in image/executable values. Ordinary reassignment cannot substitute an
unvalidated executable or race identity derivation. This does not sandbox hostile
Python reflection inside the trusted controller itself. The
[base-reconciliation checkpoint](https://github.com/ktogias/gnostoa/pull/319#issuecomment-5850146165)
retains the protected-main mismatch RED and the already integrated #320 lineage;
no existing preparation or advisory authority is weakened. The
[Claude review disposition and AUD10 characterization](https://github.com/ktogias/gnostoa/pull/319#issuecomment-5850221438)
also remove a dead cleanup conditional without changing helper selection or
exception propagation.

The [AUD11 pre-change RED](https://github.com/ktogias/gnostoa/pull/319#issuecomment-5850415242)
then exposed a resource leak in the standalone read-only smoke probe on client
timeout or interruption. The probe now retains an owned name/nonce and reuses
the execution component's command and cleanup helpers in `finally`, before its
temporary mount is removed. Native-response controls cover removal/reinspection,
foreign ownership and unavailable cleanup while preserving the writable-target
read-only oracle. This changes a verification helper, not a production producer.

The [AUD12 grouped pre-change RED](https://github.com/ktogias/gnostoa/pull/319#issuecomment-5850610512)
then exposed six adjacent input-boundary defects in the execution component:
non-string Git identities and evidence modes leaked `TypeError`, non-iterable
evidence leaked `TypeError`, and duplicate evidence, NUL-containing command
arguments and over-large aggregate evidence were rejected only after subject
materialization. The snapshot now applies the existing stable refusal contract,
duplicate/path, NUL-command and aggregate-byte checks before materialization;
the lower-level overlay checks remain in place. Smoke tests also pin the
original timeout cause/interrupt and the normal `--rm` absence branch. This is
bounded input validation and test precision, not a new authority or producer.

The [AUD13 pre-change RED and admission checkpoint](https://github.com/ktogias/gnostoa/issues/15#issuecomment-5851047580)
reproduced three in-scope review findings against the exact prior subject: the
created OCI config accepted changed resolved entrypoint/arguments/workdir/tmpfs,
an OOM-killed wrapper exit 137 could be mistaken for its completion trailer, and
the successful `--rm` probe spent the full uncertainty-settle window polling an
already absent container. The execution component now verifies the effective
runtime fields before attachment, requires the engine's `OOMKilled` state to be
false, and uses a single exact absence read-back only after the smoke command
returned success. Failure, interruption and uncertain-create paths retain their
bounded reconciliation. These changes address the recorded R2–R4 findings; the
finite late-create edge remains unproved as stated in AUD14. They do not add a
producer or activate VF0.

At the AUD12 checkpoint, the corrected relation suite had 42 tests and the
execution suite ran 114 tests, including two explicit local-namespace skips.
All non-skipped tests passed in the development container; the execution suite
also passed under optimization. These are bounded checkpoint observations, not
a claim that every future head was verified.
Exact source identities for those observations are:

| Component source | SHA-256 |
| --- | --- |
| `tools/vf0_contract.py` | `6bebdc75e02ed47349d289fd9a32a4901aa8b5a4892a99c1ba7bcb50b84d5261` |
| `tools/vf0_execution.py` | `86b527dbb9bd69e327ad4b0ae1d6950c79d5f166f0a51fe0ce97260ed0a30cee` |
| `tests/test_vf0_contract.py` | `4dbf4fdc072e1fca1b181a679ca96db880426b7e44bf0364b19c95ba77fcaf35` |
| `tests/test_vf0_execution.py` | `326a732b5beb7fc74652f12c503845971398a284f0d3b6d1b87e0a11cd5bfcc5` |
| `tests/vf0_execution_oci_smoke.py` | `305a96ecae527bd638d098c592c2e8a041d4cc39fac46a0f8691377240caf1d6` |

These source hashes bind the AUD12 local observations only. Preparation receipts,
final normal/optimized results, live OCI observations, provider checks and
individual reviewer dispositions belong to the **exact-head review record on
[PR #319](https://github.com/ktogias/gnostoa/pull/319)**. That record must bind
the enclosing candidate/tree and this map before component convergence is
claimed. Source changes invalidate the affected checkpoint rows; a source file
cannot predict its own later publication or review result.

AUD13's grouped pre-change reproducer recorded `R2_MISMATCH=ACCEPTED_UNEXPECTEDLY`,
`R3_OOM_FORGED_TRAILER=ACCEPTED_UNEXPECTEDLY`, and 20 absence polls (2.0 seconds)
for the successful auto-remove probe. At that checkpoint the repaired execution
suite ran 117 tests in the development container: 115 passed and two
local-namespace tests were skipped. The exact-parent preparation receipt also
records `ci/verify fast`, style-fix, style-check and diff-check success. Live OCI
conformance and fresh exact-head independent review were pending at the AUD13
checkpoint; the later exact-b6 seal records the predecessor's component-only
live OCI result and broader verification, without activating VF0 or admitting a
producer. See [the exact-b6 PR seal](https://github.com/ktogias/gnostoa/pull/319#issuecomment-5851447787).
The normalized Python source hashes for this AUD13 implementation are:

| Component source | SHA-256 |
| --- | --- |
| `tools/vf0_execution.py` | `1287abedab8880c2e03ef62b793f1b04b8f24302fe2e266fa5e6bdc814baa80c` |
| `tests/test_vf0_execution.py` | `a1c500acb3706291731bd571758b6da896dee5eebf0dedec11a58b291389fc92` |
| `tests/vf0_execution_oci_smoke.py` | `6a675e4ab8034a325dbe794beb1ecf239581b3a19a2a8956f27794471772af98` |

Historical executed support remains available separately: the
[a859 candidate seal](https://github.com/ktogias/gnostoa/pull/319#issuecomment-5847676712)
records 40 relation plus 98 execution tests and D0090 preparation for tree
`99463d012ebcafbb7cbb5e2d87726221cd4379c4`; the
[earlier historical live OCI result](https://github.com/ktogias/gnostoa/pull/319#issuecomment-5847554790)
in this source audit belongs to `c6732f652252e274d1cdc25758850fd0fb523523` / tree
`d154f35bb4626f226b965807188aaeb6fbcc52f3`, run 36252630347. These are predecessor
observations. Reuse requires an explicit unchanged-relevant-subject comparison;
otherwise replay affected evidence on the reviewed successor.

### AUD14 bounded correction

Two further in-scope gaps were reproduced against exact prior source before the
corresponding edits. The [AUD14 pre-change record](https://github.com/ktogias/gnostoa/issues/15#issuecomment-5851937739)
captures the first RED set and its exact source identity; its count is 121 tests
run, four expected failures, two skips and 115 passes. The
[supplemental pre-change record](https://github.com/ktogias/gnostoa/issues/15#issuecomment-5852058263)
corrects that arithmetic and records two more exact-source observations: an
absent-looking returned container ID could leave the owned generated-name
container behind, and an overlong filesystem path was accepted. A separate
descriptor harness also exercised file and directory replacement immediately
before descriptor opening.

The current bounded correction preserves valid non-UTF-8 checkout-root paths
through operating-system filesystem decoding. Git tree entry names must decode
as UTF-8; invalid tracked path bytes reject as `SUBJECT_TREE_ENTRY` before
materialization. Snapshots use descriptor-relative, no-follow traversal,
compare the classified/opened/current inode metadata, hash regular files in
bounded chunks, and cap individual and aggregate path bytes, entry count and
depth. OCI cleanup now checks the generated name's ownership token when an ID is
invalid or unvalidated, and never removes by ID unless the ownership read-back
matches. These changes remain within D0092's existing R1/R4 behavior. Cleanup
reconciliation is intentionally finite: an engine object appearing after the
settlement window may remain, so this does not claim perpetual cleanup or add a
sweeper.

Final independent contract review then found that the existing oversized-file
regression patched `Path.read_bytes`, although `_snapshot` reads through
`os.read`. Against this current pre-edit pair (`tools/vf0_execution.py` SHA-256
`4bedebc2a725514ad705e0efd6138db3e45238061214a87f4b64778aa62c1267`,
`tests/test_vf0_execution.py` SHA-256
`a94b870899260fcb0eed318dfc82b869025f8aeea0566daff0f47dfd438a2278`), an
isolated control suppressed the metadata-size refusal: it read 33 bytes, yet the
old test still passed. On unchanged production the same control observed zero
reads. Script `/tmp/gnostoa-pr319-audit/aud14-pre-read-test-control.py` SHA-256
`2da3d999f2daff187dbba04899cbfeade53efa514a04931a1a194c4d6797f408`, result
`/tmp/gnostoa-pr319-audit/aud14-pre-read-test-control.json` SHA-256
`ac3fbcca1e71277909fa6abc7673c1e67f24800bae6c1bd0ea0f4b55b9f6e5c6`. The
verification-only correction will observe the actual `os.read` boundary and
fail if an oversized file is read before the stable refusal; production
behavior remains unchanged. Its pre-edit evidence mode is green characterization
of the correct current behavior plus a controlled mutant that the strengthened
oracle must reject.

The exact AUD14 local-source identities are:

| Component source | SHA-256 |
| --- | --- |
| `tools/vf0_execution.py` | `9321deae2db77e8fbd9fa557c2bab3b2e67a48985578ed4e7915ed36c909c813` |
| `tests/test_vf0_execution.py` | `f4368d4596c51a0396f4c05c05c2c6631c35256b3643c72272a9d43a10d26de0` |

The combined relation/execution modules ran 166 tests in the development
container: 164 passed and two local-namespace cases skipped. Full `fast`,
`extended` and `regression` each ran 1,476 tests, passed, and recorded four
skips. Policy, security-fast, smoke and the extended documentation build passed;
security-fast reported four reviewed findings and zero unresolved findings.
The exact pinned-image live-OCI result is retained at
`/tmp/gnostoa-pr319-aud14-live-oci.json`, SHA-256
`c384103b517d6fe10cb318aa9a05216c30721def13961afa480e8a0f141f5b26`. It is
`PASS` for `COMPONENT_CONFORMANCE_ONLY`, covers isolation, spoofing, nonzero,
timeout, overflow and exact subject/import binding, and reports
`vf0_active=false`, `producer_admitted=false` and
`production_receipt_issued=false`. The corrected pre-read oracle's controlled
mutant result is retained separately at
`/tmp/gnostoa-pr319-audit/aud14-pre-read-test-control-final.json`, SHA-256
`592ea1753a0e468eae401a5ba811e77415d96ed990eceafca57b509720251162`: current
production passes with zero reads; a mutant that skips the pre-read refusal
reads 33 bytes and fails the intended assertion.

### AUD15 bounded reviewer corrections

Owner direction remains the in-scope #15 component correction recorded in the
[AUD15 pre-edit checkpoint](https://github.com/ktogias/gnostoa/issues/15#issuecomment-5853057976).
The exact pre-edit subject was PR head
`e73bd016a8c1248fa742b6de3d3d064b699e5912`, tree
`aeb8a9180f8cdde0451f5d607e6f7452be138466`. Independent exact-head reviews
identified four bounded R1/R2 gaps: `.git` path rejection was case-sensitive;
Git object reads could honor a repository-local `core.sshCommand` during a
missing partial-clone object lookup; recursive snapshots used two open directory
descriptors per level and failed below the admitted 256-descriptor cap; and an
attached container could add environment keys outside the image-bound values and
controller overrides. These observations came from
[CodeRabbit](https://github.com/ktogias/gnostoa/pull/319#discussion_r4114076041),
[Codex](https://github.com/ktogias/gnostoa/pull/319#discussion_r4114076085),
[Greptile](https://github.com/ktogias/gnostoa/pull/319#discussion_r4114068755)
and [CodeAnt](https://github.com/ktogias/gnostoa/pull/319#discussion_r4114066510).
CodeAnt's separate finite late-create observation remains the recorded R4 limit
below; this correction does not claim perpetual cleanup.

The exact-parent RED evidence bound both production files to the hashes below.
The relation module ran 42 tests and rejected both mixed-case `.GIT` and `.Git`
cases unexpectedly accepted by the pre-edit normalizer. Three execution probes
also ran against unchanged source: the missing promised blob case invoked the
configured SSH marker, an extra `LD_PRELOAD` environment entry was accepted, and
a 200-level allowed tree raised `SUBJECT_SNAPSHOT` after descriptor exhaustion.
The two retained logs are `/tmp/gnostoa-pr319-e73-red-relation.log` (SHA-256
`ec94dbfad03efd44fa46541e7ccb6a55eab8cb93a339c0d23884d403baef5e63`) and
`/tmp/gnostoa-pr319-e73-red-execution.log` (SHA-256
`b0413c17c8deda00bde30484502384ec3d0778a76c6e97b0c25e895c9c1740ad`).

The bounded repair folds reserved `.git` matching, disables Git lazy fetch for
trusted object/tree reads, closes each directory scan before descending, and
requires the effective attached container environment to equal the digest-bound
image environment with only the five controller values. Malformed and duplicate
environment keys are refused. No public contract, trust policy, provider
authority, producer or activation state changes. The separate finite R4
late-create window remains unresolved and explicitly partial.

The exact pre-edit source identities are:

| Component source | SHA-256 |
| --- | --- |
| `tools/vf0_contract.py` | `6bebdc75e02ed47349d289fd9a32a4901aa8b5a4892a99c1ba7bcb50b84d5261` |
| `tests/test_vf0_contract.py` | `4dbf4fdc072e1fca1b181a679ca96db880426b7e44bf0364b19c95ba77fcaf35` |
| `tools/vf0_execution.py` | `9321deae2db77e8fbd9fa557c2bab3b2e67a48985578ed4e7915ed36c909c813` |
| `tests/test_vf0_execution.py` | `f4368d4596c51a0396f4c05c05c2c6631c35256b3643c72272a9d43a10d26de0` |

The parent-owned preparation wrapper from the exact PR head found one additional
mechanical Ruff issue in the test fixture; iterable unpacking corrected it
without changing test behavior. The verified code-only prepared tree is
`78d9ba74e33f35615c871cc7e38b09f7b32fa4d6`, with prepared diff digest
`sha256:d4662bfc3c13e5149767432cab00f8cb9093ee5e24805ab37cd237f10f2fe70a`,
receipt identity
`sha256:7375d1faf5a773f6087b360b63ca8f7a5ff0f88162bf2b5b9ec7ff060bbc54b4`,
and `ci/verify fast`, style-fix, style-check and diff-check all returning zero.
That receipt covers the four component source/test paths only; this assessment
revision supersedes it for publication. A new exact-candidate receipt and full
suite results must be bound in the final PR seal. No reviewer result at this
checkpoint grants convergence or review-ready disposition.

The AUD12 and AUD13 source tables above are historical and do not identify
AUD14 or AUD15. These local observations still require exact-candidate
preparation, provider checks and individual reviewer dispositions in the
exact-head PR seal; they do not close aggregate VF0 acceptance.

### AUD16 Git transport compatibility correction

The exact-head [Gitar finding](https://github.com/ktogias/gnostoa/pull/319#discussion_r4114414834)
identified a conditional R1 gap: trusted object reads use
`GIT_NO_LAZY_FETCH=1`, but a Git build that does not implement that variable can
still try a promisor fetch and execute the repository-local `core.sshCommand`
before the isolation boundary. Its proposed fixed `2.44` version threshold is
not reliable: upstream v2.44.0 omits the variable, v2.45.0 implements it, and
older maintained releases include distribution backports. See the versioned
[2.44 docs](https://git-scm.com/docs/git/2.44.0), [2.45 docs](https://git-scm.com/docs/git/2.45.0),
[v2.45.0 implementation](https://github.com/git/git/blob/v2.45.0/environment.c#L211-L212)
and [v2.39.4 backport](https://github.com/git/git/blob/v2.39.4/promisor-remote.c#L24).
This repair therefore does not impose or infer a minimum Git version.

The [AUD16 pre-edit checkpoint](https://github.com/ktogias/gnostoa/issues/15#issuecomment-5853755289)
bound the exact prior subject to PR head
`280e9af307a8bed76f53ccf5aaf81178b6d16124`, tree
`e8695fdd6785c836e77f69b7831af220878e8954`, parent
`e73bd016a8c1248fa742b6de3d3d064b699e5912`, and
`tools/vf0_execution.py` SHA-256
`bf42d83cc5183a62b6ee6e724a60c92828eab4627813ca6e44328fa111dd6734`.
The behavior-map objective remains R1: missing local subject objects must be
rejected without launching configured remote commands. The focused control ran
on Git 2.39.5 with the exact current module and test. The existing regression
passed with the current environment; when only `GIT_NO_LAZY_FETCH` was removed
from `_GIT_ENV`, it failed because the configured SSH marker ran. Adding an empty
`GIT_ALLOW_PROTOCOL` value made that same test pass with no marker. This
capability-absence simulation does not claim an unpatched older Git binary was
executed. Result JSON SHA-256 is
`b45370b5e08f012bcce3b8d1aa8e3853d383f790c8b3c59b1221a0348ee320f2`; the
reproducer SHA-256 is
`3591c4c2d6eede1d749dc9d6c3d2bbcd75bbd6336c2a75b85e0623ccf8517cc3`.

The implementation reuses Git's existing `GIT_ALLOW_PROTOCOL` allowlist, which
is documented in [Git 2.15.4](https://git-scm.com/docs/git/2.15.4) and remains
documented in [Git 2.43](https://git-scm.com/docs/git/2.43.0). Setting the value
to the empty list denies every transport and overrides repository protocol
configuration. The regression explicitly sets repository-local
`protocol.ssh.allow=always`, removes `GIT_NO_LAZY_FETCH` from the tested child
environment, and requires a stable `GIT_COMMAND_FAILED` refusal with no SSH
marker. This preserves local object reads and prevents a missing object from
crossing into a remote helper on builds where the no-lazy-fetch guard is absent.
No dependency, public contract, policy, authority, producer admission, activation
or broader platform requirement is added. The unrelated finite R4 late-create
limit remains partial and unchanged.

Codacy's four current annotations were independently checked as inert test
fixtures/result constructors. The 63 open SonarCloud code smells were separately
reviewed, including 50 targeted exception-test controls and runtime controls for
three type warnings; none substantiated another behavior/security repair. Their
dispositions are retained separately from the R1 correction, rather than used
to justify broad test refactoring.

### Current component behavior reconciliation

Task selectors are the linked pre-edit C1–C7 and R1–R5 records above and D0092's
provider-neutral execution/relation contract. This map covers the private
components. The AUD12–AUD14 source tables are historical; AUD15 component
evidence and the final prepared candidate must be bound separately in the
exact-head PR record, which also supplies final results and individual reviewer
dispositions. Pending review grants no review-ready disposition. Tests establish
the bounded mechanism, not authentication or semantic adequacy of a future
admitted oracle.

| ID | Required observable behavior | Canonical implementation and evidence | Execution / alignment | Executor / reviewer |
| --- | --- | --- | --- | --- |
| C1 | Closed, bounded normalized inputs reject ambiguous shapes and resource-bound violations | `tools/vf0_contract.py`: strict JSON and shape helpers; `tests/test_vf0_contract.py`: missing/unknown/duplicate/nonfinite/depth/size/cycle cases | Local fixture PASS / bounded SUPPORTS | Supported at checkpoint / pending exact-head review |
| C2 | Exact parent, evidence, policy and admission relation; evidence-only and final implementation subjects remain distinct without requiring future production-fix bytes before RED | `tools/vf0_contract.py`: material/request/evidence/candidate relation; exact binding, evidence-file byte/mode retention and chronology regressions | Local fixture PASS / bounded SUPPORTS | Supported at checkpoint / pending exact-head review |
| C3 | Effective-policy mode allowance, non-vacuous expected RED and truthful chronology remain separate from asserted data consistency | `_mode_relation`, `_time_relation`; mode matrix, emergency admission-to-evidence ordering, late reconstruction, zero/skip/unrelated failure controls | Local fixture PASS / bounded SUPPORTS | Supported at checkpoint / pending exact-head review |
| C4 | Provider-neutral identities and two distinct synthetic mappings produce equivalent common results without native ID ordering | Reference/namespace relation; two-mapping and collision/opaque-attempt tests | Local fixture PASS / bounded SUPPORTS | Supported at checkpoint / pending exact-head review |
| C5 | Missing, unknown, unsupported or contradictory required acquisition guarantees reject matching relation | Guarantee and coverage evaluation; missing/contradictory/incomplete/latest-attempt tests | Local fixture PASS / bounded SUPPORTS | Supported at checkpoint / pending exact-head review |
| C6 | Unsafe/wrong-subject action links reject as mappings; missing or changed navigation does not change otherwise matching authority relation | `resolve_links`; link-mapping separation tests | Local fixture PASS / bounded SUPPORTS | Supported at checkpoint / pending exact-head review |
| C7 | Even self-consistent forged normalized data cannot authenticate, approve, prepare, publish or activate | `evaluate` fixed claim boundary; forged-data and no-effectful-import tests | Local fixture PASS / bounded SUPPORTS | Supported at checkpoint / pending exact-head review |
| R1 | Exact immutable Git subject and admitted bounded tests-only delta materialize without supplied-input symlink, metadata, path or count escape; successive calls share no hidden subject; pre-execution writes assume an untampered trusted controller host | `tools/vf0_execution.py`: stable Git identity; descriptor-relative `O_NOFOLLOW` snapshot traversal and opened/current inode revalidation; case-folded `.git` rejection; `GIT_NO_LAZY_FETCH=1` plus empty `GIT_ALLOW_PROTOCOL` allowlist for trusted Git reads; scans close before descent; individual/aggregate path bytes, depth, entry, file and total-byte limits; no-read oversized-file refusal; real Git and adversarial snapshot swap/bound regressions; controller-host write limitation below | Local fixture PASS / bounded SUPPORTS on the prepared component tree; no hostile same-UID controller-host confinement claim | Exact-head independent review pending |
| R2 | Only the fixed digest-pinned image is accepted by the live OCI smoke; runtime, entrypoint, resource, mount and environment contract is checked before launch, and identity binds the actually used runtime | The smoke CLI has no image override; `run_smoke()` binds both Docker probes and its reported identity to `FIXED_IMAGE`. Immutable backend configuration and Docker inspection compare resolved `Path`/`Args`, configured entrypoint/command/workdir/tmpfs, image, mount and resources before attachment; effective environment must equal inspected image values plus the five fixed controller overrides, with malformed/duplicate keys refused; alternate-image negative | Local fixture PASS / bounded SUPPORTS on the prepared component tree | Exact-head independent review pending |
| R3 | Command and effective limits bind controller-observed exit, output and termination; child bytes cannot certify RED or authority | Snapshot command bounds including NUL rejection, capture and observation construction; infrastructure/timeout/overflow/spoof/completion controls; engine `OOMKilled=false` required before accepting the wrapper trailer | Local fixture PASS / bounded SUPPORTS | Supported at checkpoint / pending exact-head review |
| R4 | Owned attachment/process/container resources are terminated and reconciled on every admitted failure path | Capture cleanup and known-name/container ownership removal, also reused by the read-only smoke probe; successful `--rm` completion takes one exact absence read-back, while failed/uncertain creation retains bounded reconciliation; selector/descendant/create/remove and interruption controls plus live timeout | Local fixture PASS / partial SUPPORTS; an object appearing after the finite settlement window remains unproved | Supported for exercised cases / pending exact-head review |
| R5 | Before/after bytes and exact modes are checked; immutable-during-execution claims require enforced read-only subject; no provider or receipt effect is exposed | Snapshot/manifest plus controller backend claim; mutation/custom/local-backend negatives and live OCI conformance | Local fixture PASS / bounded SUPPORTS | Supported at checkpoint / pending exact-head review |

Live OCI and independent review results must be rebound in the exact-head PR
record; unit PASS alone does not close R2–R5 runtime obligations.

The local subprocess backend supplies bounded conformance execution only. It does
not enforce a read-only subject or isolate the caller's host files and cannot
establish immutable-subject or production security claims. Custom backend doubles
have no authenticated runtime identity. The built-in local backend retains its
backend-kind identity but reports `runtime_identity=null`: fixed executable paths
and wrapper source do not identify the actual host binaries, kernel or command
runtime. OCI unit doubles prove command and cleanup
contracts; only actual fixed-fixture OCI execution supports runtime conformance.
Neither result admits a production evidence producer.

### Remaining VF0 acceptance and integration boundary

The initial VF0-01–VF0-10 behavior map remains the aggregate acceptance contract.
Component evidence can support portions of VF0-02/04/05/06, but does not close their
production gate obligations. The current preparation entrance still lacks the
VF0-01 prior-evidence refusal. Authenticated production acquisition (VF0-03),
immutable authority membership (VF0-07), independent check-only consumption
(VF0-08), ordinary preparation parity (VF0-09), and integrated bootstrap/availability/
rollback proof (VF0-10) remain incomplete. No original row is exempted or silently
narrowed.

The [A8 staging note](https://github.com/ktogias/gnostoa/pull/319#issuecomment-5827762406)
identified a possible non-authoritative component integration, explicitly subject
to an owner decision on its exact scope and current reviews/CI. It did not approve
that integration or declare complete VF0 ready. Component reviewer convergence
must therefore be reported separately from D0092 aggregate acceptance and any
protected Ready/merge, production-producer admission or activation effect.

The later [owner disposition](https://github.com/ktogias/gnostoa/issues/15#issuecomment-5880532347)
selects bounded inactive component integration after in-scope correction,
exact-candidate reviews and protected checks. It resolves that staging choice
only; the original production obligations above remain incomplete. Decision
0092's [separate component boundary](../decisions/0092-bind-verification-first-evidence-to-parent-owned-preparation.md#separately-selected-inactive-component-integration)
keeps this source integration apart from full Work Item admission and activation.

The one-time authority-evolution method remains selected and unused by ordinary
helper-only candidates. No existing D0090 authority, effective threshold, public
CLI/schema, dependency, credential or permanent producer workflow is changed by
component convergence. VF0 remains critical and inactive; #318 stays dependent on
its actual acceptance.

### AUD17 exact-head review disposition

The [AUD17 pre-edit and RED checkpoints](https://github.com/ktogias/gnostoa/issues/15#issuecomment-5854631836)
and [focused RED supplement](https://github.com/ktogias/gnostoa/issues/15#issuecomment-5854654491)
bind the CodeAnt R2 fixed-image finding to candidate
`309901546343d0cd793800455557899ca65a6c41` / tree
`4f7194f107495b5e2e83abb50966f62edef58de5`. The pre-edit test-only run had one
failure and one error: the CLI accepted `--image`, and `run_smoke()` required a
caller-selected image. The correction removes that selector and fixes both
runtime probes and the result identity to the one `FIXED_IMAGE` in D0092. The
mocked alternate is never sent to Docker. Its final result and source hashes must
be rebound after parent-owned preparation.

Other exact-309901 review observations were reconciled against the current
contract before editing:

- CodeAnt's wording finding is corrected above. Valid non-UTF-8 checkout-root
  filesystem bytes are preserved, while invalid UTF-8 Git tree entry names are
  rejected with `SUBJECT_TREE_ENTRY` before materialization.
- Codex's proposed emergency ordering change is not adopted. D0092 binds
  `EMERGENCY_POST_EVENT` to effective approved emergency admission and its
  follow-up. `_time_relation` requires the admission observation to precede the
  evidence interval; the final candidate can be observed later. A container
  characterization with admission at 200, evidence at 600–700 and candidate at
  800 returned `MATCH`, consistent with that declared event boundary.
- CodeAnt's cleanup-error observation is not adopted as an R4 repair. When
  execution and cleanup both fail, the machine-visible refusal is
  `OCI_CLEANUP_UNVERIFIED` because resource absence is unproved; the original
  `OCI_EXECUTION_FAILED` remains in the exception context chain. The exact-head
  mock control observed both. The late-create-after-settlement-window report
  restates the existing partial R4 limitation from AUD14; no sweeper or
  timeless-cleanup behavior is claimed.
- CodeRabbit's report that the general Claude Actions mention route receives a
  write-capable App token is already captured as an unadmitted finding on the
  same-purpose reviewer-capability PR #297. It is outside this candidate's
  admitted effect boundary and does not authorize a #319 change.

These are dispositions of reviews at the predecessor head, not final convergence.
Each provider result must be checked against the exact prepared successor; a
stale finding may remain relevant when its source behavior is unchanged. None of
the agent reports supplies human semantic approval or changes Draft, integration,
producer-admission or VF0 activation state.

### AUD18 exact-head review disposition

The pre-edit checkpoints, RED evidence and reuse analysis for candidate
`93957cc32188408df515a0f77e2b250c0810107d` are retained in Issue #15 comments
[AUD18](https://github.com/ktogias/gnostoa/issues/15#issuecomment-5855210274),
its [RED supplement](https://github.com/ktogias/gnostoa/issues/15#issuecomment-5855220850),
the [reuse checkpoint](https://github.com/ktogias/gnostoa/issues/15#issuecomment-5855233264),
and [AUD19](https://github.com/ktogias/gnostoa/issues/15#issuecomment-5855486865)
with its [test-only RED](https://github.com/ktogias/gnostoa/issues/15#issuecomment-5855521577).
Those records bind CodeAnt's R3 custom-backend capture finding, Codex's final
evidence-record finding and CodeRabbit's tests-only evidence-path finding to the
existing #15 / D0092 scope. The owner had already admitted bounded corrections
to in-scope findings. No public interface, evidence authority, producer,
threshold, workflow or activation gate changed.

The relation validator now rejects every nonempty evidence path outside
`tests/` as `EVIDENCE_PATH_SCOPE` in `_material`, before those paths can be
subtracted from the production delta. This makes request, evidence and candidate
material share the tests-only boundary already present in the execution
component. `test_evidence_files_are_limited_to_tests_paths` reproduces the
formerly accepted `tools/target.py` evidence substitution. CodeAnt's custom
backend correction validates returned capture type, state, byte/count
consistency and the declared output bound once at `execute()`, while preserving
the existing backend protocol and stable refusal codes. The `#308` Decision
paragraph was rewrapped to prevent Markdown from rendering it as a heading; its
meaning and authority are unchanged.

Exact changed source identities and focused verification on those source/test
bytes are:

| File | SHA-256 | Development Container result |
| --- | --- | --- |
| `tools/vf0_contract.py` | `b20715b980ad684c474fa9258c499ea5f4c88d03bc191f9020670d99bdfb6cba` | 43 contract tests passed |
| `tests/test_vf0_contract.py` | `1a1fc8925e532be512b9495838ea96dd0c9d4519624364c0feda30da0a3d2dd8` | Includes the new `EVIDENCE_PATH_SCOPE` regression |
| `tools/vf0_execution.py` | `5cd2ebdb33376ba38ca8bff278b4dabb6717151390c4a1091d9a0cd5f9b1c2fa` | Execution module passed |
| `tests/test_vf0_execution.py` | `e3db8bd2d98c1baf9d33be190b251cd11aea065d7868fb20d28344fc4fd8a3c4` | 131 tests passed, 2 skipped |

`ci/style --check` passed in the Development Container. The exact prepared-tree,
receipt, commit and full-suite result are bound in the separate top-level exact
review-candidate record; that record avoids embedding its own tree identity here.

The exact-93957 reviewer reconciliation is:

| Reviewer | Result and disposition |
| --- | --- |
| Codex code review | P3 requested binding final source/test evidence; the table above records both hashes and focused results. The exact tree and complete candidate verification are in the external candidate record. |
| Codex Security | Reported no security findings; this is bounded by its report and publication threshold. |
| CodeAnt | Major R3 custom-backend capture finding verified and fixed as described above. |
| CodeRabbit | Both actionable findings verified and fixed: D0092 Markdown wrapping and tests-only evidence paths. |
| Greptile | Completed review of 12 files with zero comments; no stronger assurance is inferred. |
| Gitar | Exact-head read-only review reports seven closed findings and no open findings; no approval authority is inferred. |
| Codacy | Static check reports four new issues (two critical, two medium), but the GitHub result does not expose their individual details. The AI Reviewer request was acknowledged, with no separate result yet; these issues remain unclosed. |
| DeepSource | Analysis check was skipped because quota is exhausted; the read-only AI request has no substantive response. |
| Sourcery, Bito, Qodo and Cubic | Sourcery declined the oversized diff; Bito's fair-use limit, Qodo's ended trial and Cubic's exceeded monthly line allowance made fresh reviews unavailable. |
| Claude | No exact-head report is available. The repository's `@claude` Actions route can obtain a write-capable GitHub App token; its review-only prompt does not enforce read-only access. A separate owner authorization is required before triggering it. |

This is not reviewer convergence. Codacy's four issues still need provider
detail and disposition, unavailable reviews remain unknown, and human semantic
review is required. VF0 remains critical, inactive and incomplete; PR #319 stays
Draft.

### AUD20 exact-head review and repair disposition

The owner-directed, in-scope review repairs continue under Issue #15 and Decision
0092. The current review evidence and chronology are retained in the Issue #15
[AUD20 pre-edit checkpoint](https://github.com/ktogias/gnostoa/issues/15#issuecomment-5856211957),
[RED supplement](https://github.com/ktogias/gnostoa/issues/15#issuecomment-5856275984),
and [review/static-analysis disposition](https://github.com/ktogias/gnostoa/issues/15#issuecomment-5856363804).
Those exact-head results belong to candidate `0da4933722a836b7a858b4f8d9fe4dbf60e6cd14`;
they are not presented as fresh review of its successor.

Codex's two P2 resource-bound findings were reproduced before production edits.
The first RED observed a 2,097,153-byte buffer conversion before
`EVIDENCE_FILE_BOUND`; the second observed `.encode()` called before
`COMMAND_BYTES_BOUND`. The correction now measures `memoryview.nbytes` before
materialization, and compares a command argument's base-string character count
with the remaining byte budget before UTF-8 encoding. It uses base `str` methods
so a string-subclass override cannot defeat either measurement or encoding.
After the fix, the focused Development Container suite ran 133 tests, passed
with two existing skips, and `ci/style --check` passed with 495 files already
formatted.

| Source/evidence | SHA-256 | Result |
| --- | --- | --- |
| Pre-fix `tools/vf0_execution.py` | `5cd2ebdb33376ba38ca8bff278b4dabb6717151390c4a1091d9a0cd5f9b1c2fa` | Exact parent-candidate source before RED |
| RED-only `tests/test_vf0_execution.py` | `af2329365b054777561b40ffa682a5f8d56f02e285270b080afbfd72a5b2b4cc` | Two new regression assertions; both fail against pre-fix production source |
| Retained RED log | `dc328172d28792cd5a6a7bc21834b850ca94e655b3acb2e61bbb5ec116a2d7f3` | 133 tests; exactly two intended failures; two existing skips |
| Fixed `tools/vf0_execution.py` | `feb96babf754504766d8bb4ef7e2207538658e59e907a8b3a7b74bf50aa37b68` | Bound checks precede allocation/encoding |
| Fixed and cleaned `tests/test_vf0_execution.py` | `89712aed0a5a7c616290741f620318140658ce746cc526354544315fca7b1c36` | 133 passed; two existing skips |
| Retained focused GREEN log | `53fd3269e57047228f13135dfad01706f0b06e780fcd7d6cb96b85969cca2ca1` | Post-fix Development Container run |

The exact-head SonarCloud result passed its quality gate but reported 66 open
issues, all `CODE_SMELL` in the public issue query, with zero security hotspots
and 0.0% coverage on new code. Two `python:S5778` MAJOR findings
(`AaDgXW4ns4mYgcx9W4hF` and `AaDi5_yalacU-vKYSq_r`) pointed into the custom
backend exception tests. The declared pre-edit mode was a non-executable
structural criterion; setup that could itself raise now occurs before each
`assertRaises` context, leaving only the single `execute` invocation inside.
The focused GREEN and formatting results above followed this refactor. The
remaining complexity findings are recorded as maintainability concerns, not
classified as demonstrated bugs or vulnerabilities.

Codacy's exact-head `action_required` status reported four annotations. Two
`/tmp` warnings point to string values in an in-memory fake Docker inspect
configuration; two `CompletedProcess` failures construct synthetic command
results in a fake backend without executing subprocesses. These contexts appear
to be scanner false positives, but the Codacy-native issue disposition remains
unavailable, so the four alerts remain provider-open. The AI Reviewer status
acknowledged a first request but supplied no substantive report.

| Reviewer / analyzer on `0da4933` | Exact result and limit |
| --- | --- |
| Codex code review | Two P2 allocation-order findings reproduced and repaired as above. |
| Codex Security | Reported no security findings; report remains in the reviewer's private task. |
| CodeAnt | Reported emergency candidate-before-admission ordering. No change was made: D0092 defines `EMERGENCY_POST_EVENT` as post-event follow-up, requires admission before evidence execution, and permits the observed candidate to predate post-event admission. This concern alone does not establish unauthorized execution. |
| Greptile | Check reports 12 files reviewed and zero comments. The separately worded security-focused request did not produce a distinct certified security-check record. |
| Gitar | Medium risk; seven findings closed and no open findings. Provider reports rules and functional validation were not enabled. |
| CodeRabbit | Full-review command was rate-limited; next included review was stated to be available in 41 minutes. No report for this head. |
| Sourcery | Manual current-head request declined because the PR diff exceeds 150,000 characters. |
| DeepSource | Analysis skipped because the account quota is exhausted; no substantive AI review result. |
| Codacy | Static findings remain open as described; no substantive AI Reviewer report. |
| Bito, Qodo and Cubic | Unavailable under the observed fair-use limit, ended trial and exceeded monthly line allowance, respectively. |
| Claude | No review was posted: auto-review rejected the `@claude` trigger because the configured workflow can make source or PR changes. Explicit owner authorization is still required. |

These are outcomes on `0da4933`, not convergence on the next candidate. Fresh
exact-head results remain necessary after preparation. No report establishes
human semantic approval, changes PR #319 from Draft, admits a producer, activates
VF0 or authorizes integration.

The corrected exact-parent preparation ran from the recommended Development
Container as checkout owner UID/GID `1000:1000`, with `HOME=/tmp`, using the
trusted wrapper retrieved from parent
`0da4933722a836b7a858b4f8d9fe4dbf60e6cd14`. The `extended` profile, safe style
fix, final style check and diff check all returned zero. The verified prepared
tree is `a1b4ea56e792fbfad7e01294f8d03cc350339edb`, with parent tree
`acbec9d7d1834a8c68b29a7f5704ca22cb3f8060` and prepared-diff digest
`sha256:4146174e43b74b3c22ecce0db4ecaaeb5b36b09855b2bdb164b761cfd0d18029`.
The retained receipt identity is
`sha256:2fa784f54aadc4d8ceca99928d1ebb31fd2b43522a4e880f6c816413ac4f582d`;
the receipt file hash is
`6fc152cc513888e68eabe50c9ca771abe351e9a0323423bbb782323c1a1b5ddb`, rooted by
`refs/gnostoa/prepared/0da4933722a836b7a858b4f8d9fe4dbf60e6cd14/a1b4ea56e792fbfad7e01294f8d03cc350339edb/523560c7f0e6c63e9395f339c405a030`.

An initial attempt invoked the helper on the host and failed before issuing a
receipt because its host interpreter path was not present in the container. It
produced no receipt and did not mutate the source worktree. The documented
Development Container route above was then used successfully; the failed host
invocation is not treated as preparation evidence.

### AUD21 exact-head review and repair disposition

The next exact candidate was `633f7f947a7b188b1d1e0e5c14706a26e53975f6`.
Fresh reviewer attribution, subject bindings, recommendations, missing
environments, the Codacy/Sonar disposition and the pre-edit admission/reuse
checkpoint are retained in the [AUD21 review checkpoint](https://github.com/ktogias/gnostoa/issues/15#issuecomment-5857279606).
The [AUD21 RED supplement](https://github.com/ktogias/gnostoa/issues/15#issuecomment-5857322924)
retains the exact failing subject and log digest.

Codex reported a P2 in which `str` subclass overrides can hide an embedded NUL
or make a relative executable pass validation, leaving an uncaught `Popen`
error or PATH-based execution. CodeRabbit independently reported the same
subclass boundary and noted that the earlier character-count precheck was not
an exact UTF-8 byte bound. Both findings were confirmed before editing. The
original AUD20 change checked character count before `str.encode`; it still
allowed an over-budget multibyte allocation up to four times the byte limit.
This repair supersedes that implementation: command inputs are first bounded by
base `str` character count, copied to a plain built-in `str`, checked for NUL,
then scanned for exact UTF-8 length without constructing encoded bytes. The
scan rejects over-budget arguments before encoding/allocation and rejects
surrogates with the stable `COMMAND` reason. Snapshots retain only canonical
strings, so later path validation cannot invoke caller overrides. No public
interface, admission, threshold or activation behavior changed.

The three regression tests were added before production edits and failed on
exact parent `633f7f9`: a hidden-NUL subclass passed, a `startswith` subclass
made a relative executable pass, and a multibyte argument allocated 263,805
traced bytes before rejection against a 131,072-byte test ceiling. After the
implementation, the Development Container focused suite passed all 136 tests
with two existing skips; `ci/style --check` reported 495 files already
formatted and all checks passed.

| Source/evidence | SHA-256 | Result |
| --- | --- | --- |
| AUD21 pre-edit `tools/vf0_execution.py` | `feb96babf754504766d8bb4ef7e2207538658e59e907a8b3a7b74bf50aa37b68` | Exact parent source before implementation |
| AUD21 RED-only/final `tests/test_vf0_execution.py` | `a6c3f6dddf45b435def1f52a3d7f583e6c0e39af4647f9697c4454cf5b151850` | Three regression tests; RED then focused GREEN |
| AUD21 RED log | `b93a1097091d16ae631b903673063a888f14dd20e63942a62f065acecf0d566d` | Exactly the three intended failures; production unchanged |
| AUD21 fixed `tools/vf0_execution.py` | `fec59ee1f95d41e41036b7157530e45e78ffa4e141f1b563b368b3a6c569943a` | Canonical command strings and exact pre-allocation UTF-8 byte accounting |

On `633f7f9`, CodeAnt found no concrete defects but supplied no overall
recommendation; Gitar approved with medium risk and 7/7 findings closed, while
reporting that rules and functional validation were not enabled. Greptile's
code and security-focused ordinary reviews each completed with 12 files and zero
comments, without an overall recommendation or a separate dedicated security
check. CodeRabbit's full review produced the multibyte and subclass findings;
its included allowance is now spent. Codex code review produced the P2 above;
no Codex Security report is available. These are not convergence on this next
candidate. The PR remains Draft and required human semantic review remains
outstanding.

### AUD22 exact-head review and Docker control-output repair

The [AUD22 pre-edit checkpoint](https://github.com/ktogias/gnostoa/issues/15#issuecomment-5857879852)
binds owner admission, current provider identities, Decision 0092, the critical
classification, expected behavior and local reuse to exact parent
`e6541044be667e3c8e00411ab8e6a96e60e594ee` / tree
`d22c97bea53f6c83e85f994b2b019ead10a7274f`. The
[RED supplement](https://github.com/ktogias/gnostoa/issues/15#issuecomment-5857907405)
retains the single failing regression against that unchanged production parent.

Codex's exact-e654 P2 identified unbounded `subprocess.run(capture_output=True)`
for Docker control commands. `docker image inspect` and container inspections
return metadata that can be influenced by the pinned image; complete stdout and
stderr were buffered before JSON or resource-state validation. This violated
D0092's existing requirement that the controller own bounded output capture.
The correction reuses `_capture_process()` and its process-group termination and
reaping, with a 1 MiB aggregate stdout/stderr ceiling. Overflow raises
`DOCKER_CONTROL_OUTPUT_BOUND` before decoding or cleanup-state interpretation;
completed bounded commands retain exit status and their separate stdout/stderr.
The existing read-only smoke transport tests now characterize that same bounded
capture boundary. No public interface, producer admission, preparation authority,
activation gate or VF0 status changed.

The new regression failed before the production edit because the exact-parent
`_command()` returned without raising the expected overflow refusal. After the
fix, the focused Development Container run passed 137 tests with two existing
skips, and `ci/style --check` passed with 495 files already formatted. The exact
source identities after that focused GREEN are:

| Source/evidence | SHA-256 | Result |
| --- | --- | --- |
| Pre-edit `tools/vf0_execution.py` | `fec59ee1f95d41e41036b7157530e45e78ffa4e141f1b563b368b3a6c569943a` | Exact parent production source before RED |
| RED-only `tests/test_vf0_execution.py` | `c80bcc04e112033f7f5d7fdd9776ab749cf8337158471b17d6fd64ab18e7d8a7` | One new aggregate-overflow refusal regression |
| Retained RED log | `0be02e93039018e415739eddf8a84f26f2a55f8492b234e0c395dc9c4d88df58` | Expected `ExecutionRejected not raised`; production unchanged |
| Focused-GREEN `tools/vf0_execution.py` | `ce40ef1645e31a595ac04ec757ee40971c01e8912b7b44adf3ad13e179b19df0` | Existing streaming capture reused by Docker control commands |
| Focused-GREEN `tests/test_vf0_execution.py` | `f1b8e15d3d53e82536c3b3b93ea6838d2fed7d6d9fde0915a01ae1e9ec46bcf0` | 137 passed, two skipped; smoke transport uses the bounded capture seam |

The exact-e654 review reconciliation is:

| Reviewer or analyzer | Result and limit |
| --- | --- |
| Codex code review | P2 on unbounded Docker control output; reproduced before editing and fixed as described. |
| CodeAnt | Repeated its prior cleanup-error observation as a Major finding. The exact-e654 runtime characterization retained both execution and validation errors in the `__context__` chain while correctly refusing `OCI_CLEANUP_UNVERIFIED`; see the [thread and disposition](https://github.com/ktogias/gnostoa/pull/319#discussion_r4116104607). No source change was warranted. |
| CodeRabbit | The isolated full-review command completed and reported no new inline comments. No separate overall approval or test environment was supplied. |
| Greptile | Code review and security-focused ordinary review each completed with 12 files reviewed and zero comments. Neither result is a dedicated Security Check or an explicit approval. |
| Gitar | Approved, medium risk, seven closed findings and none open. Its report does not supply human approval. |
| Codacy | Exact-e654 static check passed and its summary reported zero new issues. Its AI Reviewer acknowledged a first request; no distinct substantive report was returned. |
| SonarCloud | Quality gate passed; it reported 64 new code smells, zero security hotspots and 0% coverage on new code. These analyzer results are not reviewer approval. |
| CodeQL and hosted suites | CodeQL, fast, extended, regression, smoke, policy, security-fast, Python 3.11/3.12 compatibility, protected-current advisory, and both branch-advisory checks passed on e654. Sourcery and DeepSource were skipped. |
| Codex Security | A separate `@codex security review` was posted once but produced no report or associated check. State remains unknown; it was not retriggered. |
| Claude | Automatic Claude review remained skipped on Draft. The prior automatic approval review rejected the general `@claude` Actions route because its configured token can modify source or PR state. Public source visibility does not reduce that token's authority; a human authorization is still required before using that route. |

The prepared successor, its full verification/runtime results and fresh
post-repair reviews must be read from the separate exact-candidate seal; this
AUD22 record does not predict those later provider effects. No result above
establishes human semantic approval, PR readiness, producer admission, VF0
activation or merge authority.

### AUD29–AUD31 exact-head safety corrections

The exact `cbe3108276da553a42a3b95ed6bbb72eeefa8580` parent exposed three
remaining bounded corrections. RED evidence was recorded before production
edits in the isolated exact-parent checkpoints; the Development Container was
unavailable in this execution context because access to `/var/run/docker.sock`
returned `permission denied`.

- **AUD29, completion-trailer forgery.** The Codex P2
  ([thread](https://github.com/ktogias/gnostoa/pull/319)) was reproduced: a
  child-authored static trailer plus an inspected exit code of 137 and
  `OOMKilled=false` returned `completed`. A second RED test showed that a child
  inherited the controller marker. The bounded repair uses a per-run random
  token, passes it through the Docker client's clean environment rather than
  argv, removes it before spawning evidence, sets the wrapper non-dumpable, and
  accepts only the matching final token trailer. The existing OOMKilled check
  remains. This is unit evidence for the wrapper process boundary, not live
  pinned-image OCI conformance; no live Docker daemon was available here.
- **AUD30, aggregate subject path work.** The Codex Security P2
  ([thread](https://github.com/ktogias/gnostoa/pull/319)) describes repeated
  filesystem normalization, but exact-parent code already normalized each
  unique directory once. The still-unbounded repeated path-component planning
  work was real: the new exact-parent RED fixture was accepted. The repair adds
  a 65,536 aggregate component-visit ceiling before materialization while
  retaining unique-directory normalization.
- **AUD31, emergency chronology.** The earlier AUD17/AUD21 disposition that a
  final candidate could be observed after its post-event evidence was too weak:
  the relation had no bound from that evidence to the exact candidate. On the
  exact parent, candidate observation at 800 with evidence at 600–700 returned
  `MATCH`; the positive control at candidate observation 500 is valid. The
  proposed relation now requires the exact candidate and approved emergency
  admission to precede evidence start. This is still post-change emergency
  follow-up, not a RED/pre-change claim, and the result remains unauthenticated,
  non-compliant and inactive. The prior candidate-after-evidence disposition is
  superseded for future exact candidates; historical results are not promoted.

The fixes also carry the AUD28 exact-head regressions: controller and backend
receive separate `ExecutionLimits` snapshots, snapshots reject case-insensitive
`.git` path components, and Docker control results use a bounded controller
owned result type. The existing `GIT_ALLOW_PROTOCOL=""` denial and prior AUD16
reproducer already cover the promisor-fetch finding; no additional change was
needed. The repeated cleanup-error report remains dispositioned by the retained
dual-failure characterization. The finite late-create window remains a known
R4 limitation: no perpetual cleanup or sweeper is claimed, so it cannot be
treated as a production activation proof. Exact prepared-tree identity,
post-change verification and reviewer dispositions are retained only in the
new exact-candidate seal after preparation; this assessment cannot predict
those provider results.

| Checkpoint | Exact-parent production/Decision source SHA-256 | RED-only test SHA-256 | RED log SHA-256 |
| --- | --- | --- | --- |
| AUD29 trailer forgery | `tools/vf0_execution.py`: `030387bfd588291eacfcc4a921734a36fcd21cb1464b2350b0c6e22d2459f67a` | `tests/test_vf0_execution.py`: `ba184c5418bab6a407a0bdc2302a4cf43f328f4e6c098de4f8922c809dfb4fed` | `5faa70f1c1614e1143357fc518dc29b4ce5e9aa055da782b9592fee8e7f8398c` |
| AUD29 token isolation | same exact-parent production source | `tests/test_vf0_execution.py`: `840f1ae2c5a073cf40bf6a707184241178981db5cb8b140c614a9057ea7c3029` | `9b16b89f436d166b1b819ec8f15f60e682283a090529710b895b00839295fa07` |
| AUD30 path-component bound | same exact-parent production source | `tests/test_vf0_execution.py`: `940b74bd16cfefa173b2f770750567491d1b9603d95c7b08c5bc1634edbb2de8` | `e578977ad2f1f28ffb54320e3aceb87634a710e8cb5a7adb8f5bd7e2774ea8b1` |
| AUD31 emergency ordering | `tools/vf0_contract.py`: `b20715b980ad684c474fa9258c499ea5f4c88d03bc191f9020670d99bdfb6cba`; D0092: `7ffeb7cc4130fd10892b86ddef60d212f9790fdaaff086981f904924a88fa2aa` | `tests/test_vf0_contract.py`: `1e6e2921c3b446301d76f54b9cee9aa109900eb22d4cc07700bed15b13e3b14e` | `85ad7c2555d9f6c3c993a7fab760f10e5bed64c5ad834e723093fddbb3fdb856` |

Each RED test-only file was run against production code at exact cbe parent; the
first test-selection typo in AUD30 was discarded and is not part of its
retained result. The final candidate source hashes and verification results
must be appended after the exact parent-owned preparation completes.

### AUD29–AUD31 prepared-tree verification follow-up

The earlier note that the Development Container was unavailable records the
initial attempt, when the host Docker socket denied access. The host fallback
also failed before issuing a receipt because its interpreter lacked Ruff. A
first container preparation included the separate, untracked Issue #15 provider
preview; that tree was rejected, its receipt was released through the exact
parent wrapper, and the preview was moved outside this candidate checkout.

After that correction, the exact parent wrapper prepared only the six intended
paths below from parent `cbe3108276da553a42a3b95ed6bbb72eeefa8580` / tree
`2406a56747601c899731e2d2f6872c8100610d0c`. The retained receipt identity is
`sha256:cdeb7801cc04101cededc70430fcaa0b9fc4e041fc729036be2229cd2393f68a`;
the receipt file SHA-256 is
`2229619d7c5d21c0f786f456ee0a54454bd716a1b09cd7aa5c52544731676457`, and its
prepared tree is `833391f8e2cf86e63df0d5e3f8c0647d19cd1599`. The exact-parent
verification command accepted the receipt and tree. Its fast profile, `ci/style
--fix`, final style check and diff check all passed. The prepared diff contains
only this assessment, Decision 0092, the two VF0 test files and the two VF0
implementation modules.

The Development Container was then rebuilt for local verification commit
`27834d73f1b8ce0ce4ff382b233d783d27a74045`, whose tree is exactly the prepared
tree above. `ci/verify extended` passed all 1,500 tests with four skips, Ruff
formatted 495 files, mypy passed, coverage was 78% against the 65% gate, both
dependency audits reported no known vulnerabilities, and the documentation
build passed. The fixed live-OCI smoke is not represented by this unit/extended
result; it remains a separate component-conformance check after publishing the
exact PR candidate. This does not close R4's finite late-create limitation or
activate VF0.

| Prepared-tree source | SHA-256 |
| --- | --- |
| `knowledge/decisions/0092-bind-verification-first-evidence-to-parent-owned-preparation.md` | `c4a9bbf6316d720a7aee95781e6b992c98030ceda2ca37c2c172250af37ff342` |
| `tests/test_vf0_contract.py` | `74a22f5747da0e45f88c6388372a8fef1e2a08011122b3b3331a54167d418a46` |
| `tests/test_vf0_execution.py` | `3c3b40168d721d52c577487bd0fc37c3d62303efa47c93386d7d4b1ab4b51f2c` |
| `tools/vf0_contract.py` | `8d8acb22f182836cf4f992c0df7a6e56342a8fc1ea1436bbf0af5441c5469d3a` |
| `tools/vf0_execution.py` | `0a93c4119a92509136d4f34e5f1c85c007adeee7668af53848954d510df24a46` |

### AUD39 capture ownership and bounded component disposition

The [owner disposition](https://github.com/ktogias/gnostoa/issues/15#issuecomment-5880532347)
and [pre-edit RED checkpoint](https://github.com/ktogias/gnostoa/pull/319#issuecomment-5880559943)
bind this correction to exact parent `8ff1bfb344450f30ddfde5427de7d3ab146138f9`.
Before production edits, an execute-level regression failed in all three
completion/timeout/output-limit subcases because later backend mutation changed
the returned stdout from one byte to nine. The controller now snapshots each
capture field once, validates those exact primitive values and constructs a
distinct result. The same regression passes; the focused Development Container
suite ran 196 relation/execution tests successfully with two environment skips.
This closes the reproduced R3 capture-alias behavior locally, pending prepared
exact-candidate verification and review. Final prepared-tree, receipt, full-suite
and live-OCI identities remain outside the prepared tree in the PR record.
No production gate, public command, admission adapter or original VF0 obligation
is activated or satisfied by this component correction.

### AUD40 leave the unmeasured local runtime unbound

The [current-head Codex finding](https://github.com/ktogias/gnostoa/pull/319#discussion_r4128222183)
identified that the local runtime digest encoded only fixed executable paths and
wrapper source. The [pre-edit checkpoint](https://github.com/ktogias/gnostoa/pull/319#issuecomment-5881048042)
and [corrected contemporaneous RED record](https://github.com/ktogias/gnostoa/pull/319#issuecomment-5881057941)
bind LOCAL-ID-1 to exact parent `1a11594fd427167e3df672b229ae7510f3b7b417`.
The Development Container execute-level regression failed because the returned
observation asserted a non-null runtime digest; an independent reviewer reproduced
the same value through real local execution against unchanged parent production.
The component now keeps `gnostoa-local-subprocess-v1` as the backend identity and
leaves its runtime identity unbound. It acquires no new host/runtime authority.
The regression and existing rebuilt-backend observation test require local null
runtime identity while preserving the pinned OCI identity distinction. Final
verification and reviewer dispositions belong in the external exact-candidate
record. This correction does not qualify the local backend for untrusted evidence
or alter the original VF0 activation obligations.

### AUD41 refuse polymorphic strings at direct backend command validation

The [current-head CodeAnt finding](https://github.com/ktogias/gnostoa/pull/319#discussion_r4128349146)
identified that direct backend callers could override a string's `startswith`
predicate and pass a bare executable to PATH lookup. The main `execute` entry
already canonicalizes string values and refuses the same input. The
[pre-edit checkpoint](https://github.com/ktogias/gnostoa/pull/319#issuecomment-5881308308)
and [contemporaneous RED](https://github.com/ktogias/gnostoa/pull/319#issuecomment-5881320068)
bind this correction to exact parent `0491ea88c8553d77258557f46f3d6ddfb01390b0`.
Both direct built-in backend regressions failed before the production edit,
reaching containment or image dispatch instead of command refusal; an independent
real-local reproduction separately demonstrated PATH execution. The shared
validator now requires exact strings before any caller-overridable predicate.
Direct local and OCI callers reject the subclass before dispatch, while the
existing canonicalizing entry and legitimate absolute or explicit relative
executables retain their behavior. The relative-executable control uses a fixed
capture double to check command routing, not to claim isolation. Final trusted
preparation, exact-candidate verification and reviews remain external records.
This private correctness repair changes no producer admission, production
enforcement, authority or original VF0 acceptance obligation.

### AUD42 retain the validated command snapshot at every built-in entry

Fresh independent execution and architecture review of exact
`ddae2fdf5adeca0f6626658db3be9a990be7cc23` found that AUD41's exact-string
predicate did not own the surrounding command sequence. A direct caller could
yield one explicit command during validation and a different bare executable
during launch. The existing `execute` entry's snapshot already prevented this;
the direct local/OCI and capture entries still re-read caller state. The
[pre-edit checkpoint](https://github.com/ktogias/gnostoa/pull/319#issuecomment-5881434120)
and [contemporaneous RED and green characterization](https://github.com/ktogias/gnostoa/pull/319#issuecomment-5881482047)
retain three failing command-snapshot regressions, including real capture exit
substitution, before production editing. Both reviewer recommendations were
superseded pending this correction rather than counted as convergence.

Shared validation now returns the existing bounded canonical tuple; each direct
built-in entry retains that same tuple for dispatch. String subclasses are
canonicalized safely before explicit-path validation, as at `execute`. Caller
commands retain their 256-argument/64-KiB envelope. The capture primitive uses a
separate finite 512-argument/128-KiB transport envelope for fixed wrappers and
Docker control flags. This allowance does not raise caller limits. Pre-edit
maximum-count/byte characterization and post-edit controls require valid maximum
caller commands to survive local and OCI wrapping; oversized transport is refused
before process dispatch. Unit doubles certify routing/validation only, not actual
OCI isolation. Final trusted preparation, full/live verification and current-head
reviews remain external records. No producer or original VF0 gate is activated.

### AUD43 bind every live smoke observation before declaring conformance

The [CodeAnt live-oracle finding](https://github.com/ktogias/gnostoa/pull/319#discussion_r4128455136)
was independently reproduced on exact `ddae2fdf5adeca0f6626658db3be9a990be7cc23`:
an adversarial observation with wrong subject/runtime/backend, unequal manifests,
false immutability and invalid byte counts still allowed overall smoke PASS.
The [pre-edit checkpoint](https://github.com/ktogias/gnostoa/pull/319#issuecomment-5881565891)
and [corrected contemporaneous RED](https://github.com/ktogias/gnostoa/pull/319#issuecomment-5881605144)
retain 65 failing runner-level forged-observation subcases and a green fully bound
control before smoke production editing. The first evidence record's fixture
errors were explicitly corrected before editing, not relabeled as oracle failures.

The fixed live runner now independently derives the requested subject, evidence,
command and limits identities and the known fixture's exact mode/content/directory
manifest. Every returned observation must match these, the fixed OCI backend/image,
true immutability and the bounded output/count/state relations before serialization.
The report retains evidence and before/after manifest identities. The image-routing
unit test also checks that both success and binding oracles are called; the separate
negative matrix keeps the real oracles active. These doubles qualify the runner's
refusal behavior, not actual OCI isolation. Exact-candidate live execution remains
required and its retained report remains component conformance only.

The [conditional controller-host race](https://github.com/ktogias/gnostoa/pull/319#discussion_r4128455141)
is **not fixed** by this oracle. A concurrently tampering same-UID host actor can
replace a pre-execution overlay path between inspection and pathname-based write.
The private temporary parent excludes other users; no untrusted evidence/backend
has started at that point, and admitted Git/evidence inputs cannot introduce the
symlink. R1's supplied-input confinement and descriptor-relative snapshot checks
must not be read as descriptor-relative write protection or isolation from a hostile
controller host. Producer/threat-model qualification in original #15 retains this
trusted-host limitation and must choose the actual controller isolation boundary
before activation. Neither this documentation nor inactive integration waives any
original VF0 acceptance criterion or admits host hardening/production execution.

### AUD44 — timeout observation count consistency

The common fixed-smoke oracle now requires exact observed/retained byte equality
for every non-output-limit state, including timeout, matching the executor's
existing capture contract. A genuine runner-level timeout observation retaining
one byte but claiming 999 was accepted on exact `871137587ed7c8b61fa2f66aa2910d171bc4ddd2`;
the added negative regression failed before oracle editing. The overflow
lower-bound rule and all existing binding checks remain unchanged. This is a
private verification correction within the inactive component slice, not a new
producer receipt, workflow enforcement, activation or whole-Issue-6 dependency.

The current CodeAnt emergency relation finding is also corrected within this
inactive scope. The closed private input requires `evidence.candidate_sha256`: it
is null for pre-change modes and the existing canonical JSON digest of the entire
validated candidate block for `EMERGENCY_POST_EVENT`. Array order is retained as
exact representation. This binds its tree, production digest, parent, retained
evidence bytes/modes, paths and observation time without asking ordinary RED to
name future implementation bytes. The existing candidate-before-evidence
chronology remains required. Positive emergency and unchanged-evidence
tree/digest/time substitution controls distinguish a true binding from blanket
schema rejection; missing/null emergency and nonnull pre-change bindings refuse.
Caller-supplied candidate and digest remain unauthenticated assertions. No
producer, public schema, preparer, workflow or independent consumer is activated.

The path-subclass regression now requires the exact `EVIDENCE_PATH` refusal
before materialization, overlay or backend dispatch. An unrelated early Git
refusal no longer passes it; malicious paths need not reach overlay. This is
test-strengthening over already correct input refusal, not host-race hardening.

Native Claude's current review additionally retains nonblocking qualifications in
the owning PR and original #15. In particular the untampered trusted controller
host premise lasts throughout materialization, execution and final snapshot and
across earlier local evidence runs, not merely until overlay. The local backend
does not isolate host filesystem/IPC; untrusted local execution cannot establish
that trusted-host premise. Built-in OCI read-only mounts and equal snapshots do
not exclude hostile-host transient changes. Live token-secrecy and forged-trailer
controls, input-shape/error projection, executable-format parity and display
escaping remain explicit producer/runtime qualifications before activation.

### AUD46 — incomplete attachment framing and truthful child-byte bounds

Native Claude's exact `fcf5556c9dfbeb1b415e2047bcb2cd3a988b0646` review found a
current R3 accuracy defect, independently reproduced before production editing:
a real transport process writes child bytes and a full completion trailer,
closes its pipes, then misses the leader-exit deadline. The old Docker backend
retained transport bytes in timeout and could falsely report child overflow.
The real capture is combined with Docker configuration/cleanup doubles; it is
not evidence of the frequency of a live OCI timing race. Exact-parent failing
regressions precede the correction in the owning PR's AUD46 chronology record.

The same strict unique, complete, matching-token final trailer parser now runs
for every attachment state. It strips exact authenticated transport bytes and
their count, but only a completed attachment adopts the parsed exit. Timeout
and overflow retain their original state and null exit, subject to actual child
overflow after normalization. Completed engine-state/spoof controls remain.
Malformed, foreign or duplicate framing and trailing partial public-header
prefixes conservatively refuse `OCI_ATTACH_STATE`; guessed token fragments are
never authenticated or silently removed. This can refuse legitimate child
stderr ending in a reserved header prefix, an explicit fail-closed framing
collision rather than a claimed exact partial-token decoder.

When no framing was retained, retained bytes are child bytes under the trusted
wrapper-final-stderr premise; unretained counts subtract at most the finite
maximum possible transport overhead and remain at least the retained child
count. Overflow requires a proven child-byte lower bound above the caller
budget. Transport-only overflow without that proof refuses instead of inventing
a child count or completion. No producer authentication, authority enforcement,
host isolation, cleanup-liveness fix or VF0 activation is introduced. Slow owned
inspect, late-create and whole-call trusted-host limits remain separate original
#15 obligations before activation; whole #6 is not a technical predecessor to
this inactive private normalization repair.

### AUD45 exact cleanup diagnostic reference and retained liveness limit

The missing-object recognizer now normalizes only the native error prefix and
compares the container reference suffix exactly. An uppercase diagnostic
reference for a lowercase owned identity failed the added regression on exact
`8cf777401236986d34cd59cef5b8a7ab28a3c415` before parser editing. Known native
prefix variants remain accepted; other targets, appended/multiline diagnostics
and transport failures remain unknown. This is narrow identity-parser hardening:
current controller-generated names/IDs are lowercase and trusted Docker echoes
the queried reference, so no admitted evidence path to actual false cleanup was
demonstrated. It does not authenticate a hostile controller host or Docker daemon.

Native Claude's exact8cf review also identified a distinct partial-R4 liveness
limit, independently reproduced with a clock-controlled transport double. An
owned-container inspection that consumes the finite settlement deadline can
result in `OCI_CLEANUP_UNVERIFIED` before the first removal attempt; the uncertain
create fallback may repeat that path. No successful result or verified absence
is returned, but the resource-bounded container can remain running. This is
**not fixed** and is not the already retained late-create case. Original #15's
mandatory producer/runtime qualification must resolve or select the actual
cleanup/availability boundary before activation. It does not block the selected
inactive source integration and supplies no assertion of cleanup under daemon
unavailability. The review's representation-order, trusted requested OCI pin,
identity-display and caller-type limitations remain individual PR dispositions.
