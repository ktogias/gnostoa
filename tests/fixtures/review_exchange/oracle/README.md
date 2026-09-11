# Independent controlled review-transport oracle

The accepted first-evaluation card supplies the requirements. `freeze.json` binds its preserved proposed text, the root-reported owner acceptance event, main/reference identities and every literal input/expected artifact. This oracle was authored without reading or implementing the controller. All cases are **NOT RUN** until the executor records actual evidence. A file timestamp/hash is a binding record, not independent proof of execution or authority.

## Inputs and observable comparison

`cases.json` defines eight bounded scenarios. `expected.json` defines literal expected projections and native byte identities. `roster-two.json` is the independent A+B denominator; `roster-single.json` supplies the single-actor control. These files are test specifications, not an invented production schema. Root may map names/commands to the implementation's public test CLI, but must preserve each assertion's meaning; do not derive expected missing jobs or findings by consulting the controller's registry.

The intended CLI operations are init, dispatch, collect, view, disposition and revise. Each scenario is isolated. The controlled cases may replay synthetic jobs repeatedly; that does not allocate extra live assignments. The actual live envelope remains at most two reviewer assignments, one intentional handoff and one round for the whole admitted trial.

- `eligible_count` comes from the independent frozen roster, never the dispatch/result registry.
- `current_ids` means a retained review matches the active candidate **and** assignment. It is not semantic acceptance.
- `pending_ids` lists eligible jobs with no usable normalized current review because they never dispatched, have an ambiguous outstanding dispatch, or normalization failed. `stale_ids` separately lists retained historical reviews that are not current. Missing/stale categories must not disappear from the view.
- `unknown_dispatch_ids` distinguishes the missing-receipt case from a known not-yet-dispatched job. Unknown does not authorize a retry.
- `original_reviews` remains present for stale/dissenting records; recommendations, material flags, finding identifiers and text cannot be rewritten into executor conclusions.
- `executor_disposition_count` is the number of separately retained dispositions. X07 expects one explicit deferred disposition, with the material finding still visible as unresolved. A deferred finding is not silently cured.
- `independent_review_claim: false` means the controlled output must not claim independent review. In X02 the reviewing actor equals the coordinator. Other synthetic actor names do not prove independent derivation.
- `real_provider_portability: UNESTABLISHED` is mandatory interpretation for controlled runs, even when processes or native encodings differ. `human_approval: false` rejects invented human acceptance.

List membership is order-insensitive unless ordering is part of an original review. Compare required scalar values and finding/recommendation text exactly. Compare native stdout/stderr by their actual bytes against the frozen expected SHA-256 and lengths; comparing two controller-reported hashes to each other is insufficient. The B response deliberately uses CRLF/spacing different from A. Parsed JSON equality is not native-byte fidelity.

Implementation-specific timestamps, PIDs and receipt identifiers need not equal literal constants. Their relations and actual effects require evidence outside the controller's summary. Do not manufacture a passing boolean when the observation is unavailable.

## Required process and effect evidence

For X03, launch P1 and P2 as separate processes, terminate P1, and start P2 with only the durable workspace locator and normal command arguments. Preserve the independent process-launch record and the input files P2 acquires. No reconstructed task, reviewer result or prior in-memory object may be handed directly to P2. A normal new CLI invocation alone is not evidence of a different real agent/tool; the synthetic process test establishes only persistence/acquisition behavior.

For X05, observe that the intent reaches durable storage before worker launch. An independent worker launch marker confirms one actual launch, then the receipt is absent. Subsequent collect/view calls must leave launch count at one. A missing receipt cannot prove whether remote work happened and cannot justify implicit retry. This tests coordinator retry behavior; it does not account for SDK-internal requests.

For X08, force normalization failure after native capture and inspect both native files. Their survival with exact frozen bytes is required. A successful-path hash check alone would not discriminate normalize-first-and-drop-on-error behavior.

## Intentionally defective comparison

**M0 / registry-only completion baseline:** construct the review view by enumerating only jobs present in the dispatch or completed-result registry, and call collection complete when every enumerated job has a result. It can look correct for X01 while silently dropping B in X04.

On X04, this baseline should report an incomplete denominator or omit pending B; the frozen oracle requires `eligible_count = 2`, `current_ids = [A]`, `pending_ids = [B]`, and `never_dispatched_ids = [B]`. Its apparent completion is therefore a real false-complete observation relative to the independent roster. Retain the baseline output and actual assertion mismatch; an unrelated exception or skipped test is not this RED. Repair must face the same unchanged oracle.

This is one sufficient discriminatory baseline. Optional later mutants are not a new required mutation campaign. Do not widen scope merely to obtain a positive result.

## Live observations that these fixtures cannot supply

Bind actual installed tool versions, permitted authentication/account/data routes, known quota/spend behavior, command/assignment identity and source acquisition before live dispatch. Preserve the actual native stdout/stderr/service response before normalization and compare the final human packet to that retained response. Synthetic expected findings must not be substituted for what a live reviewer actually said, and a live model need not rediscover every historical finding to pass transport fidelity.

For real coordinator replacement, retain evidence that the second qualified tool acquired the external durable record and outstanding results without owner restatement. If the second tool is unavailable, real portability remains unestablished. Record actual owner transfers and reconstruction through an external observer/explicit measurement; missing telemetry is UNKNOWN, not zero. Current artifacts do not prove original service authenticity, hostile isolation, crash/power-loss durability, cross-device recovery, general quality equivalence or L10 enforcement.

## Byte-preserving packaging

`inputs.zip` retains the original frozen inputs as unchanged root-level regular
files. The test verifies the pinned archive digest, exact member set and each
original freeze binding before execution. To inspect or reuse plain inputs,
unpack into a temporary directory; `GNOSTOA_EXCHANGE_ORACLE_ROOT` accepts that
directory. The eight original cases/expectations have not been rewritten.

Public hashes in these immutable inputs trigger entropy heuristics. Packaging
avoids mutating the original bytes to add scanner annotations. The experiment
assessment retains the actual extracted-member scan and per-finding triage;
ordinary tracked-tree CI scanning of the ZIP does **not** inspect these members.
Wrapper/index lines use explicit annotations for inspected public digests under
the existing scanner mechanism. No path/global exclusion or scanner policy
change is introduced.
