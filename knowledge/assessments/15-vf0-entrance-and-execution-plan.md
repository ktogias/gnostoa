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

## VF0-A7 chronology, A8 and bounded execution candidate

The **32-test** count above is intentionally preserved as the original A7
checkpoint. A later retained-evidence-delta regression increased the published
relation suite to **33 tests** before exact head
`d217453ece7694eeaed0f9acb2d17bd5903e70e0`. Do not rewrite the earlier number
as though those tests had already existed. The subsequent C2 review reproduced
a contradictory MATCH when `changed_paths` was non-empty but the candidate tree
was reset to the parent tree. On unchanged `d217`, the external pre-edit suite
therefore observed four C2 assertion failures across the allowed synthetic modes,
one missing-execution-entry assertion failure, one passing prior-fix control and
zero errors/skips.

[A8 run 36099667712](https://github.com/ktogias/gnostoa/actions/runs/36099667712)
completed its three bounded jobs successfully, including the actual
characterization and independent read-back of its native approval/result. That
retained experiment remains bound to its historical subject; it is **not** a
D0090 receipt for a later candidate and does not establish producer admission,
credential separation, compliance or VF0 activation. No A8 rerun is required
merely because the execution component changes.

The current grouped R1-R5 candidate adds one C2 relation regression, bringing the
relation suite to **34 tests**, and introduces a private bounded execution
component plus fixed live-OCI smoke. Its local conformance suite contains **39
execution/fixture tests**. Together, **73 focused tests** pass normally and with
Python optimization as a non-root user; scoped Ruff 0.16.0 formatting/lint and
strict mypy 2.3.0 also pass. The execution tests use real temporary Git subjects
and finite local processes while Docker-specific paths use explicit doubles. They
cover immutable per-call subjects, tests-only evidence bounds, complete byte/mode
comparison before and after execution, environment scrubbing, bounded separate
stdout/stderr, nonzero/timeout/overflow observations, descendant termination,
read-only OCI contract inspection and attachment-before-container cleanup.

Successor chronology after the subsequent execution hardening and restrictive-umask
regression, through exact head `f54cf89a0387856d441be3bfaa5a20783f03af36`:
the relation suite remains **34 tests** and the execution/fixture suite is **45
tests**, so the exact focused invocation executes **79 tests**. All 79 pass normally
and under Python optimization. The preceding **39 / 73** account is retained as
the earlier grouped-candidate checkpoint rather than rewritten.

The bounded uncertain-create settling repair adds one execution/fixture regression
for delayed Docker resource appearance after an initially negative inspect. The
relation suite remains **34 tests** and the execution/fixture suite becomes **46
tests**, so this candidate executes **80 focused tests**. All 80 pass normally and
under Python optimization before ordinary D0090 preparation.

The subsequent subject/snapshot boundedness repair adds three execution/fixture
regressions: finite Git subject entry count, finite Git tree-listing bytes, and
pre-read rejection of oversized post-execution files. The relation suite remains
**34 tests** and the execution/fixture suite becomes **49 tests**, so this
successor executes **83 focused tests**. All 83 pass normally and under Python
optimization before ordinary D0090 preparation.

The next in-scope execution-hardening candidate adds six execution/fixture test
methods for bounded post-execution entry traversal, subject Git-metadata path
rejection, evidence-directory destination refusal, detached-session descendant
containment, complete OCI mount validation, and uncertain Docker-remove
reconciliation. Existing evidence-path and OCI create-contract tests are also
strengthened to reject `.git` components and require exact mounted-subject
routing (`KNOWLEDGE_KIT_ROOT`, `KNOWLEDGE_KIT_REVISION`, and `PYTHONPATH`). The
relation suite remains **34 tests** and the execution/fixture suite becomes **55
tests**, so the focused corpus is **89 tests**. All 89 pass normally and under
Python optimization; the full non-root `fast` profile also passes before ordinary
D0090 preparation.

Subsequent containment and evidence-identity hardening adds three more
execution/fixture regressions. At exact head
`d2b1a1e6c1e6a7d6cda479dd7fc1a8752c653793`, direct source count is **34
relation tests + 58 execution/fixture tests = 92 focused tests**. The preceding
**55 / 89** account is retained as its historical checkpoint; **92** is the
current focused-test total before the isolated-subject import-routing repair.

This evidence still does **not** claim a live run of the new Docker specialization.
`tests/vf0_execution_oci_smoke.py` is intentionally outside unittest discovery and
must be executed after exact ordinary D0090 preparation/publication of this
component. Its successive-subject success check requires `completed`, exit code
`0` **and** exact expected stdout; matching bytes from a nonzero or timed-out run
do not count. The smoke also exercises forged authority-looking output without
replaying it as a workflow command or treating it as authority.

The grouped scope is limited to `tools/vf0_execution.py`,
`tests/test_vf0_execution.py`, `tests/vf0_execution_oci_smoke.py`, the C2 repair
in `tools/vf0_contract.py`/`tests/test_vf0_contract.py`, this assessment, Decision
0092 and the corresponding guardrail record. It changes no D0090 authority file,
effective policy threshold, public CLI/schema, dependency, credential, permanent
workflow or provider-specific common-core contract. Ordinary unchanged-parent
D0090 preparation remains mandatory before publication; the previously approved
bootstrap exception is unused. VF0 remains **critical and inactive** and still
precedes #318.
