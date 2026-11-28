# Pilot telemetry (schema v1)

Continuous, typed measurements of the Gnostoa pilot: limits, policies, the model and effort of every role, token use,
tool denials, failures, repetitions and loops, deliveries, evaluations and every routing, model, depth, gate, custody,
safeguard and escalation decision. This branch is data only and is never merged. One commit per publication; the
reports issue receives one daily summary that links the commit and its manifest.

## Layout

- `telemetry/v1/YYYY/MM/DD/<stream>.jsonl`: one JSON record per line, sorted by `ts` then `record_id`; the day is the UTC day of `ts`.
- `schema/v1/envelope.schema.json` and `schema/v1/<stream>.schema.json`: JSON Schema (draft 2020-12) of every stream.
- `manifests/YYYY-MM-DD.json`: sha256, bytes and record count of every file of the day, records dropped per reason, the
  disclosure gate result, the collector version and digest, and a rollup of the day.
- `analysis/report.py`: the analysis, standard library only: `python3 analysis/report.py --since 2026-11-20 [--json]`.

## Envelope (every record)

| field | meaning |
|---|---|
| schema_version | 1 |
| stream | the stream name |
| record_id | stable id (32 hex): sha256 of the source pointer and the normalized content, or of an explicit identity for observations, snapshots and derived rows; a rerun never duplicates a record |
| kind | record kind within the stream (below) |
| ts | UTC time of the fact, ISO 8601 with milliseconds |
| ts_basis | FILE_MTIME or DATE when ts is not the time the source states |
| entity | key of a mutable entity (a job, a receipt, a result, a hold): keep the latest version per (kind, entity) |
| derived | computed from other records (measure rows, scorecards); replaced when recomputed |
| subject | ids: role, input_key, job, receipt, pr, issue, comment, conversation, target, stage |
| source | root (pilot, stages, supervisor_ledger, derived), file (relative to that root), locator (line:N, file, op), sha256 of the source record |
| units | the unit of every field of the record that has one (tokens, s, h, bytes, USD, calls) |

Join keys: `subject.input_key` joins a role turn to its Router job, peer result or Implementer receipt;
`stream_receipt` joins a turn to its tool events; `subject.receipt` joins an Implementer receipt to its tool events and decisions.

## Stream `turns`

| kind | meaning |
|---|---|
| TURN | one role turn of the turn ledger (Router, PAO, SAS, unknown), launched or not |

| field | type | unit | meaning |
|---|---|---|---|
| admission_reason | string |  | typed admission refusal reason |
| admission_refused | boolean |  | the admission check refused the launch |
| attempt | integer |  | attempt number |
| cause_code | string |  | typed failure cause of a turn or attempt |
| context_tokens | tokens | tokens | tokens of the last context request |
| conversation_tokens | tokens | tokens | cumulative tokens of the conversation after the turn |
| cost_usd | number | USD | provider-reported cost |
| cycle_offset_s | number | s | seconds from the poll start to the turn start |
| delta_basis | string |  | how the ledger computed the usage delta |
| duration_s | number | s | wall-clock duration |
| effort | string |  | reasoning effort of the lane or turn (low, medium, high) |
| effort_basis | string |  | MODEL_SUFFIX when effort is the depth suffix of the model id (agy role lanes pass no effort flag) |
| extension_s | number | s | lane extension of the turn bound |
| lane | string |  | lane key model@profile |
| launch_cause | string |  | typed sub-cause of a PROCESS_LAUNCH (S691 launch_guard.LAUNCH_CAUSES) |
| launch_detail | string |  | closed detail of a launch failure: the engine stderr class or the errno name (never text) |
| launched | boolean |  | the provider process was launched |
| limit_kind | string |  | kind of provider limit (QUOTA, DAILY_CAP, OVERLOAD) |
| model | string |  | model id the turn ran on (requested model) |
| num_turns | integer |  | provider turns inside the call |
| permission_denials | integer |  | permission denials the provider reported |
| prefetch_bytes | integer | bytes | prefetch bytes shown |
| prefetch_failed | boolean |  | the prefetch failed |
| prefetch_reads | integer |  | prefetch reads |
| prefetch_s | number | s | prefetch duration |
| prefetch_type | string |  | prefetch block type |
| probe_refused | boolean |  | the quota probe refused the launch |
| profile | string |  | CLI credential profile alias of the lane (A, A2, B, C) |
| prompt_bytes | integer | bytes | prompt size (turns: the argv word as launched, S691) |
| prompt_cut_bytes | integer | bytes | bytes the argv-bound fit cut from the DATA lines of the prompt (S691) |
| provider_k | integer |  | provider slots available |
| provider_slot | integer |  | provider slot index |
| provider_wait_s | number | s | seconds waited for a provider slot |
| queue_age_s | number | s | age of the input when the turn started |
| queue_basis | string |  | what the queue age counts from |
| rotated_from | string |  | digest of the previous conversation id |
| rotation_reason | string |  | why the conversation was rotated before the turn |
| status | string |  | status code of the source record |
| stream_receipt | string |  | id of the stream receipt (join key turns <-> tool_events) |
| tokens | tokens | tokens | tokens of this turn (turn ledger usage delta; receipts: per-call usage) |
| tool_count | integer |  | tool calls in the turn |
| total_basis | string |  | INPUT_PLUS_OUTPUT when tokens.total was derived (no provider total) |
| transport | string |  | transport of the turn (agy, claude-print, codex-exec, *-resume) |
| trigger_class | string |  | the trigger key with numbers and digests replaced by N |

## Stream `tool_events`

| kind | meaning |
|---|---|
| CHANNEL_VIOLATION | a tool channel violation (typed shape) |
| DENIAL | a denied tool action with its typed program and shape |
| GOVERNOR | the S678 convergence governor trace of one Implementer turn |
| TOOL_STOP | a turn stopped by a typed stop (S678 governor, ledger refusal) or cut at a bound |
| TURN_TOOLS | tool-call aggregate of one stream receipt: tool types, states, programs, repetition and loop flags |

| field | type | unit | meaning |
|---|---|---|---|
| active_at_end | integer | calls | tool calls still ACTIVE when the turn ended |
| attempt | integer |  | attempt number |
| by_state | counts | calls | tool calls per final state |
| by_tool | counts | calls | tool calls per tool type |
| cause_code | string |  | typed failure cause of a turn or attempt |
| context_tokens | tokens | tokens | tokens of the last context request |
| count | integer |  | number of denied actions |
| distinct_commands | integer |  | distinct command digests |
| duration_s | number | s | wall-clock duration |
| effort | string |  | reasoning effort of the lane or turn (low, medium, high) |
| error_class | string |  | typed class of an error (code, exception name or TEXT_<digest>) |
| errors | integer | calls | tool calls that ended in ERROR |
| exit_code | integer |  | process exit code |
| family | string |  | transport family (agy, claude, codex) |
| governor | measures |  | S678 convergence governor trace: bounds, new answers, live polls, re-entries, extensions |
| identical_repeat_runs | integer |  | command runs that repeated an earlier identical command |
| lane | string |  | lane key model@profile |
| loop_flags | strings |  | loop rules (LOOP_RULES) the turn met |
| max_consecutive_identical | integer |  | longest run of consecutive identical commands |
| max_identical_repeats | integer |  | runs of the most repeated identical command |
| model | string |  | model id the turn ran on (requested model) |
| output_bytes | integer | bytes | tool output bytes |
| permission_denials | integer |  | permission denials the provider reported |
| profile | string |  | CLI credential profile alias of the lane (A, A2, B, C) |
| program | string |  | denied program name |
| programs | counts | calls | command segments per program name (first word only, never arguments) |
| read_range_repeats | integer |  | file reads that repeated an earlier identical range |
| scope | string |  | scope of a denial or snapshot |
| shape | string |  | denied command shape or channel violation shape |
| status | string |  | status code of the source record |
| status_polls | integer |  | background-task status polls |
| steps | integer |  | model steps of the turn |
| stop_class | string |  | TYPED_STOP (governor or ledger), BOUND (tool or time bound), LOOP |
| stop_reason | string |  | typed stop (governor, ledger refusal, bound) |
| stop_steps | integer |  | steps the stop cites |
| stream_receipt | string |  | id of the stream receipt (join key turns <-> tool_events) |
| stream_status | string |  | status the stream receipt recorded |
| terminal_reason | string |  | typed terminal reason |
| tokens | tokens | tokens | tokens of this turn (turn ledger usage delta; receipts: per-call usage) |
| tool_count | integer |  | tool calls in the turn |
| tool_limit | integer |  | tool-call bound of the turn |
| transport | string |  | transport of the turn (agy, claude-print, codex-exec, *-resume) |
| truncated_outputs | integer | calls | tool outputs truncated |

## Stream `decisions`

| kind | meaning |
|---|---|
| BLOCKER | one role blocker record (daily cap, quota, provider) |
| BREAKER | one quota-group breaker state |
| CAP_HELD | one S713 role daily cap (turns or tokens) that holds a PENDING input (role, cap, count, held inputs, oldest input age, reset), once per role, day and cap |
| CHAIN_END | one S692 chain end of an ACTIVE obligation with no live next step (class, newest step, idle time) |
| CONTINUATION | one S692 custody continuation request to the Router (kind, class, attempt, delivery status) |
| CONTINUATION_DEFERRED | one S705 custody continuation held by the day or item request bound (once per episode, reason and day) |
| CUSTODY | one input custody settlement |
| DEPTH_TIER | the adaptive effort tier chosen for an Implementer turn |
| DISPOSITION_CANDIDATE | one S694 disposition candidate (pull request, Work Item, typed triggers) |
| DISPOSITION_CLOSE | one S701 controller typed close of a decided subject (decision, remedy, closed or refused, attempt, Work Item link) |
| DISPOSITION_DECISION | one S694 Owner decision read or refused (decision, by, matches the recommendation) |
| DISPOSITION_DEFERRED | one S694 review deferred by the daily bound or the token budget |
| DISPOSITION_EVIDENCE | one S694 evidence bundle collected without a model (files, lines, citing comments, large) |
| DISPOSITION_EXECUTION | one S694 decided disposition sent to the Router as the item remedy |
| DISPOSITION_FAILED | one S694 failed review turn or decision request (cause, S698 per-attempt causes or refusal) |
| DISPOSITION_POLICY | one S694 merge policy snapshot refresh of the disposition review |
| DISPOSITION_QUEUED | one S694 review turn queued (stage, attempt, routing floor, S698 allowed reads, previous causes) |
| DISPOSITION_RECORD | one S694 typed record kept (recommendation, confidence, tokens) or architecture check |
| DISPOSITION_REQUEST | one S694 decision request through the Owner escalation ledger (status) |
| DISPOSITION_RETRY | one S698 decision request retried without a new turn once its refusal no longer applies |
| DISPOSITION_WITHDRAWN | one S694 subject withdrawn (closed, no longer a candidate) |
| ESCALATION | one Router escalation (typed class) |
| FINDING_THREADS_REFUSED | one S709 review-finding assignment refused at the seal: ids not unresolved in the held exact thread read, or review comment ids |
| FREEZE_ADOPTED | one S705 push freeze the Router adopted from a SAS route (pull request, frozen head, batch action) |
| FREEZE_EXCEPTION | one S705 push admitted under a freeze as the route's one batched commit |
| FREEZE_REFUSED | one S705 push the writer refused under a freeze (pull request, operation action) |
| FREEZE_RELEASED | one S705 push freeze ended (batch published, Router or operator release, subject closed, expired) |
| FREEZE_VIOLATION | one S705 head of a frozen pull request that neither the freeze nor its exception holds |
| GOAL_ESCALATION | one S692 Owner escalation of an obligation whose continuations were spent |
| GRANT_SKIPPED | one S705 ready Work Item passed over for the slot because it had no runnable next step (basis, the item granted instead) |
| IDENTITY_REKEYED | one S709 Router assignment whose identity a never-posted dispatch held, sealed under the next free attempt token (held error, attempt before and after) |
| IDENTITY_REKEY_EXHAUSTED | one S709 held identity with no free attempt token within rekey_steps (the seal then refuses it, naming the held dispatch) |
| IMPLEMENTER_GATE | one Implementer wake-gate decision (launch or not, rotation, transport plan) |
| INGRESS_HELD | one S713 due PENDING input unserved for 10 minutes while its role took no turn (DAILY_TURN_CAP, DAILY_TOKEN_BUDGET, PROVIDER_LIMIT_BREAKER, PROFILE_HOLD, WORKER_STOPPED, UNSERVED), or (S725, status SELECTED_NOT_LAUNCHED) at once, a due input its role worker selected and did not launch because the role's typed hold (the reason) keeps it |
| INGRESS_RELEASED | one S713 held input that left PENDING (its final status and the seconds it was held) |
| LANE_ROTATION | a lane or conversation rotation of an Implementer turn |
| LIMIT_PROBE | one transport limit probe |
| MODEL_SWITCH | a transport family switch for an Implementer turn |
| OBLIGATION | one S692 goal custody obligation transition (previous state, state, reason, rule) |
| OWNER_ESCALATION | one Owner escalation ledger request (latest version) |
| PROFILE_FAILOVER | one S690 profile failover or failback decision (primary, from and to profile, reading) |
| PR_CARD_READ | one S718 controller card read of an open pull request the portfolio ledger had no current read of (pull request, head, GETs, lines, reviewable lines, files) |
| PR_CARD_READ_FAILED | one S718 controller card read that failed (pull request, head, GETs, attempt; FINAL when the attempts are spent) |
| PR_INVENTORY_REFRESH | one S705 poll-cycle read of the open pull requests while the observer scope was stale (complete, count, scope age) |
| PUBLICATION_ADMITTED | one S701 open admitted after its provider checks (mode, branch, start head, existing pull request, remedy, decision basis) |
| PUBLICATION_CANDIDATE | one S720 accepted candidate kept for its operation (status CANDIDATE_RETAINED, typed reason), restored into a re-dispatch of the same operation (CANDIDATE_RESTORED) or discarded once published (CANDIDATE_DISCARDED) |
| PUBLICATION_CLOSE | one S693 original pull request closed as superseded by its carrier, its branch kept |
| PUBLICATION_EFFECT | one S701 remedy operation routed to its effect (RECORD: one Work Item comment, no branch or pull request) |
| PUBLICATION_OPEN | one S693 draft pull request opened (or reconciled) and read back (pr, branch, head, draft) |
| PUBLICATION_PUSH | one S693 push of a pilot namespace branch by the draft pull request writer (created or fast-forward) |
| PUBLICATION_REFUSAL | one S693 refused or unavailable open or close (typed reason; S701: prelaunch when known before the turn) |
| REFUSAL | one refusal of a Router job (typed class) |
| REFUSAL_CLEARED | one S705 refusal whose predicate passes now: the item is asked again once (code, basis, refused at) |
| REFUSAL_PAIR | one S709 identical refusal pair (class and clause) of one Router job's consecutive attempts on its subjects |
| REFUSAL_PAIR_CLEARED | one S709 sealed decision with dispatches on a subject that ends that subject's recorded pairs |
| REFUSAL_PAIR_STOP | one S709 Router job stopped at its refusal because it repeats a recorded identical pair on one of its subjects (REFUSAL_PAIR_REPEATED) |
| REFUSAL_SEQUENCED | one S705 operation refused behind the item's own open pull request (or another applying refusal), kept SEQUENCED while the item's remedy proceeds (code, behind) |
| RESULT_HELD | one S705 native peer result not routable for 10 minutes (PR_INVENTORY_STALE, PR_NOT_OPEN, PR_HEAD_NOT_CURRENT) |
| RESUME_UNBOUND | one S709 Implementer resume no checkpoint could bind, dropped at the seal so the retry runs from its exact subject |
| ROUTER_DISPATCH | one Router assignment to a role (operation action, target, retry reason) |
| ROUTER_JOB | one Router job (latest version per job): status, attempts, refusals, escalation, publications |
| ROUTING | one S686 routing decision (task class, tier, first lane, expected costs) |
| SAFEGUARD | one S684 Router safeguard decision (aged pending, family breaker, stale authority) |
| SCHEDULE_GRANT | one S692 Implementer slot grant (item, reason, wait, streak, contenders) |
| SCHEDULE_GRANT_END | the end of one S692 slot grant (USED, WITHDRAWN, LAPSED) |
| SCHEDULE_REFUSAL | one S692 seal refusal of a Router decision (invalid CUSTODY line, custody request not decided) |
| SIGNAL | one S685 assurance signal |
| STALL | one stall and brake detector decision |
| STALL_ALERT | one stall alert |
| SUBJECT_HOLD | one subject hold (latest version) |
| WAKE_GATE | one Router wake-gate decision |

| field | type | unit | meaning |
|---|---|---|---|
| action | string |  | typed action |
| age_h | number | h | age of the input |
| aged_action | string |  | aged-pending action |
| aged_rule | string |  | aged-pending rule |
| attempt | integer |  | attempt number |
| attempt_failures | integer |  | failed attempts recorded |
| attempt_lanes | strings |  | lane of each model attempt, in order |
| attempts | integer |  | attempts recorded |
| batch_action | string |  | S705 operation_action prefix of the route's one batched commit (the push freeze's typed exception) |
| behind_ref | string |  | S705 what a refused operation waits behind (pr:N, DECISION, WIP_LIMIT, a held subject) |
| blocker_kind | string |  | blocker kind |
| brake | string |  | typed brake reason |
| branch | string |  | S693 branch of the pilot namespace (agent/<work-item>-<slug>) |
| capacity_hold | string |  | typed capacity hold reason |
| cause_class | string |  | typed class of the source cause text |
| chain_step | string |  | S692 typed newest step of an ended chain (JOURNAL_FAILED_RECORDED, ...) |
| check_states | counts | checks | S693 check runs per state on the original head of a pure carry (opened without the local validation gate) |
| clear_basis | string |  | S705 the refusal predicate's basis: why it no longer applies (RULE_CHANGED, INPUTS_CHANGED, OPERATOR_NAMED, RETRY_DUE, PULL_CLOSED, WIP_ADMITTED, HOLD_RELEASED), or for REFUSAL_SEQUENCED why it still does (PULL_OPEN, ...) |
| completion | strings |  | completion criteria the dispatch names |
| confidence | string |  | S694 confidence of a disposition record or architecture check (HIGH, MEDIUM, LOW) |
| consumer | string |  | consumer of the signal |
| contenders | integer |  | S692 ready Work Items when the grant was decided |
| context_last_request | integer | tokens | context tokens of the lane last request at the gate |
| context_median | integer | tokens | median context tokens per call of the lane at the gate |
| costs | integers | tokens | expected cost per tier |
| coverage | string |  | continuation frontier coverage |
| criterion | string |  | merge criterion |
| decision | string |  | typed decision |
| decision_basis | string |  | S701 how the decision reference verified: OWNER (the Owner's comment) or SUPERVISOR_RELAY (an operator-named relay record) |
| decision_reason | string |  | S701 why a decision reference did not verify (decision_authority.REASONS) |
| decision_source | string |  | S701 the operator data that names the decision reference (CONFIG, OPERATOR, COMMAND, POLICY) |
| detector | string |  | detector name |
| draft | boolean |  | S693 the opened pull request read back as a draft |
| duration_s | number | s | wall-clock duration |
| effect | string |  | S701 effect of a remedy operation (OPEN, CLOSE, RECORD) |
| effort | string |  | reasoning effort of the lane or turn (low, medium, high) |
| end_class | string |  | S692 class of a chain end (INFRASTRUCTURE, MODEL_CAPACITY, DECISION) |
| episode | string |  | digest of the episode id |
| error_class | string |  | typed class of an error (code, exception name or TEXT_<digest>) |
| escalation_class | string |  | typed escalation class |
| escalation_denied | string |  | why an escalation was denied |
| escalation_kind | string |  | escalation kind |
| evidence | strings |  | evidence sources the dispatch names |
| existing_pr | integer |  | S701 the pull request an admitted open reconciles (the carrier already open) |
| explore | boolean |  | the routing decision explored |
| fact_classes | counts | facts | facts per class |
| facts | integer |  | facts the gate saw |
| failure_causes | counts | attempts | failed attempts per cause |
| family | string |  | transport family (agy, claude, codex) |
| final_reason | string |  | typed final reason |
| first_lane | string |  | lane key the routing decision chose |
| freeze_release | string |  | S705 how a push freeze ended (BATCH_PUBLISHED, ROUTER_RELEASE, SUBJECT_CLOSED, EXPIRED) |
| from_family | string |  | family before the switch |
| frontier_exhausted | boolean |  | the continuation frontier was exhausted |
| frozen_head | string |  | S705 head a push freeze holds (a FREEZE_VIOLATION observed another one) |
| granted_item | string |  | S705 the Work Item granted instead of a skipped non-runnable contender (none: no runnable contender) |
| group | string |  | quota group |
| guess | integer |  | first-guess tier |
| head | string |  | commit sha (public) |
| held_s | number | s | S692 time a slot grant was held before it ended |
| idle_s | number | s | S692 time an ACTIVE obligation had no live next step when its chain end was found |
| input_type | string |  | typed input type |
| items | integer |  | assignment items of the job |
| ladder | integer |  | tiers on the ladder |
| lane | string |  | lane key model@profile |
| last_failure_cause | string |  | cause of the last failed attempt |
| launch_cause | string |  | typed sub-cause of a PROCESS_LAUNCH (S691 launch_guard.LAUNCH_CAUSES) |
| limit_kind | string |  | kind of provider limit (QUOTA, DAILY_CAP, OVERLOAD) |
| link | string |  | S701 the Work Item link of a typed close (PRESENT, POSTED, UNCONFIRMED, FAILED) |
| marker | string |  | typed marker of the input |
| measures | measures |  | typed numeric or code facts of the source row |
| model | string |  | model id the turn ran on (requested model) |
| model_attempts | integer |  | model attempts recorded |
| models | integer |  | models held |
| ok | boolean |  | the probe succeeded |
| omitted_facts | integer |  | facts omitted |
| open_prs | integer |  | open pull requests seen |
| opens | integer |  | breaker opens |
| operation_action | string |  | operation action of a dispatch |
| operation_attempt | integer |  | operation attempt of a dispatch |
| operation_target | string |  | operation target of a dispatch |
| outcome | string |  | typed outcome |
| over_item | string |  | S692 Work Item whose consecutive operations triggered a FAIRNESS_RUN grant |
| passed | integer |  | S692 operations of other Work Items while the granted item waited |
| plan_family | string |  | transport family the gate planned |
| plan_switch | boolean |  | the gate planned a family switch |
| predicate | string |  | gate predicate |
| prelaunch | boolean |  | S701 the refusal was known before the turn: no model ran |
| previous | string |  | previous status |
| priority | number |  | S692 aged priority of the granted item (weight x (1 + wait / aging)) |
| profile | string |  | CLI credential profile alias of the lane (A, A2, B, C) |
| publication_mode | string |  | S693 open mode (WORK_ITEM: an admitted Work Item from main; CARRIER: an Owner-decided carrier) |
| publication_statuses | counts | publications | publications per status |
| publications | integer |  | publications of the job |
| published | boolean |  | the output was published |
| reason | string |  | typed reason (class of the source reason) |
| reasons | integer |  | reasons recorded |
| recipient | string |  | recipient role |
| recipients | counts | publications | publications per recipient role |
| recommendation | string |  | S694 recommendation of a disposition record (CARRY_OVER, RE_IMPLEMENT, CLOSE_SUPERSEDED) |
| reference_comment | integer |  | comment id of the reference |
| reference_issue | integer |  | issue of the reference |
| refusal_class | string |  | typed refusal class |
| refusal_classes | counts | refusals | refusals per class |
| refusal_code | string |  | S705 typed code of the refusal whose predicate cleared (refusal_causes.PREDICATES) |
| refusals | integer |  | refusals of the job |
| released_brake | string |  | typed reason of a released brake |
| remedy | string |  | S701 registered remedy of the item (CARRIER, RE_IMPLEMENT, CLOSE_SUPERSEDED) |
| reported_tokens | tokens | tokens | tokens as the role receipt reports them (agy: cumulative for the conversation) |
| represented_reason | string |  | why a dispatch was represented |
| request_kind | string |  | S692 kind of a custody continuation (CHAIN_ENDED_UNDECIDED, SLOT_GRANTED) |
| required_approvers | integer |  | required approvers |
| reset_at | string |  | earliest reset time |
| retry_reason | string |  | typed retry reason of a dispatch |
| review_stage | string |  | S694 disposition stage of the transition (SAS_RECORD, PAO_ARCH_CHECK, REQUEST) |
| rotate_before_launch | boolean |  | the gate rotated the conversation before launch |
| routing_floor | integer |  | S694/S698 lane tier a disposition review turn starts from (0 = the base lane) |
| rule | string |  | typed rule |
| runnable_basis | string |  | S705 why a ready Work Item could not use the slot (ASK_BUDGET_SPENT, ASK_UNANSWERED, DECISION_STALE, HELD, NO_NEXT_STEP) |
| running_item | string |  | S692 Work Item whose turn ran when the grant was decided |
| safeguard | string |  | safeguard name |
| same_body | boolean |  | S698 a retried decision request renders the same body as the refused one |
| source_pr | integer |  | S693 original pull request a carrier carries |
| source_role | string |  | role that produced the input |
| stall_kind | string |  | stall detector kind |
| stalls | integer |  | stalls counted by the tier rule |
| status | string |  | status code of the source record |
| streak | integer |  | S692 longest run of one other Work Item while the granted item waited |
| streak_max | integer |  | longest streak the tier rule saw |
| switch | boolean |  | the transport family switched for this turn |
| switch_reason | string |  | typed reason of the transport choice |
| target_issue | integer |  | issue number of the publication |
| task_class | string |  | task class of a routing decision |
| terminal_failure | boolean |  | the job ended as a terminal failure |
| terminal_reason | string |  | typed terminal reason |
| tier | integer |  | adaptive effort tier chosen (0 = base) |
| tier_reason | string |  | why the tier was chosen (BASE, ESCALATE_AFTER_STALL, ...) |
| to_state | string |  | S692 obligation state after a transition (ACTIVE, WAITING, PARKED, DONE) |
| tool_reads | integer |  | S698 provider reads the disposition turn prompt allows (0 = answer with no tool call) |
| transport | string |  | transport of the turn (agy, claude-print, codex-exec, *-resume) |
| unlaunched_retries | integer |  | failed turns that did no model work and spent no model attempt (S691) |
| version | string |  | version of the deciding rule |
| wait_s | number | s | S692 time a Work Item has waited ready for the Implementer slot |

## Stream `deliveries`

| kind | meaning |
|---|---|
| IMPLEMENTER_TURN | one Implementer receipt (latest version): outcome, progress, model, effort, tier, tokens |
| MAIN_HEAD | a new head of the default branch observed (a merge landed) |
| PEER_RESULT | one PAO or SAS result (latest version): publication, consumption, model, attempts |
| PR_LEFT_OPEN | a pull request left the open set (closed or merged) |
| PR_STATE | an open pull request head observed (first observation of each head) |

| field | type | unit | meaning |
|---|---|---|---|
| attempt_failures | integer |  | failed attempts recorded |
| brake | string |  | typed brake reason |
| capacity_hold | string |  | typed capacity hold reason |
| consumer_status | string |  | whether the coordinator consumed the output |
| context_total | integer | tokens | context tokens of the turn as the receipt reports them |
| cost_usd | number | USD | provider-reported cost |
| delivery_state | string |  | consumer delivery state |
| duration_s | number | s | wall-clock duration |
| effort | string |  | reasoning effort of the lane or turn (low, medium, high) |
| error_class | string |  | typed class of an error (code, exception name or TEXT_<digest>) |
| failure_causes | counts | attempts | failed attempts per cause |
| family | string |  | transport family (agy, claude, codex) |
| from_family | string |  | family before the switch |
| gate_decision | string |  | wake-gate decision of the receipt |
| head | string |  | commit sha (public) |
| input_type | string |  | typed input type |
| ladder | integer |  | tiers on the ladder |
| lane | string |  | lane key model@profile |
| lane_rotation | string |  | lane rotation reason of the turn |
| last_failure_cause | string |  | cause of the last failed attempt |
| launch_cause | string |  | typed sub-cause of a PROCESS_LAUNCH (S691 launch_guard.LAUNCH_CAUSES) |
| marker | string |  | typed marker of the input |
| material_progress | boolean |  | the turn changed the worktree or source state |
| model | string |  | model id the turn ran on (requested model) |
| model_attempts | integer |  | model attempts recorded |
| num_turns | integer |  | provider turns inside the call |
| outcome | string |  | typed outcome |
| permission_denials | integer |  | permission denials the provider reported |
| profile | string |  | CLI credential profile alias of the lane (A, A2, B, C) |
| prompt_bytes | integer | bytes | prompt size (turns: the argv word as launched, S691) |
| proposal_refusal | boolean |  | a proposal was refused |
| publication_phase | string |  | publication phase |
| published | boolean |  | the output was published |
| refusal_class | string |  | typed refusal class |
| released_brake | string |  | typed reason of a released brake |
| reported_tokens | tokens | tokens | tokens as the role receipt reports them (agy: cumulative for the conversation) |
| result_status | string |  | status the role returned |
| return_status | string |  | return delivery status |
| source_role | string |  | role that produced the input |
| stalls | integer |  | stalls counted by the tier rule |
| state | string |  | pull request state |
| status | string |  | status code of the source record |
| switch | boolean |  | the transport family switched for this turn |
| switch_reason | string |  | typed reason of the transport choice |
| target_issue | integer |  | issue number of the publication |
| tier | integer |  | adaptive effort tier chosen (0 = base) |
| tier_reason | string |  | why the tier was chosen (BASE, ESCALATE_AFTER_STALL, ...) |
| tokens | tokens | tokens | tokens of this turn (turn ledger usage delta; receipts: per-call usage) |
| tool_count | integer |  | tool calls in the turn |
| tool_items | integer |  | tool items the receipt counted |
| total_basis | string |  | INPUT_PLUS_OUTPUT when tokens.total was derived (no provider total) |
| transport | string |  | transport of the turn (agy, claude-print, codex-exec, *-resume) |
| turn_completed | boolean |  | the model turn completed |
| turn_started | boolean |  | the model turn started |
| unlaunched_retries | integer |  | failed turns that did no model work and spent no model attempt (S691) |

## Stream `config_changes`

| kind | meaning |
|---|---|
| INSTALL | one supervisor stage install with its patch sha256 and file digests |
| LANECTL_OP | one runtime overlay operation (lane, cap, timeout, limit, order) with operator class and rollback |
| LEDGER_ROW | one dated row of the supervisor lessons ledger, a stage row or an incident row (stages, public record link, text digest) |

| field | type | unit | meaning |
|---|---|---|---|
| args | object |  | typed operation arguments |
| file_hashes | object |  | sha256 per installed file (pilot-relative path) |
| files | integer |  | files installed |
| inverse_args | object |  | typed arguments of the recorded rollback |
| inverse_op | string |  | operation of the recorded rollback |
| model_calls | integer |  | model calls made by the install |
| op | string |  | lanectl operation |
| op_id | string |  | lanectl operation id |
| operator_class | string |  | supervisor, operator, owner or other |
| operator_digest | string |  | digest of the operator note |
| patch_sha256 | string |  | sha256 of the installed patch |
| preflight | string |  | preflight result (NOT_RUN, OK, FAILED) |
| record_comment | integer |  | comment id of the public record |
| record_issue | integer |  | issue of the public record |
| reverts | string |  | operation id this operation reverts |
| row | integer |  | row number of the supervisor ledger |
| smoke | string |  | smoke result (NOT_RUN, OK, FAILED) |
| stage | string |  | supervisor stage id (S<n>) |
| stages | strings |  | supervisor stage ids of a ledger row |
| status | string |  | status code of the source record |
| text_sha256 | string |  | sha256 of the row text (the text itself is not copied) |

## Stream `snapshots`

| kind | meaning |
|---|---|
| LIMITS | every registered runtime limit: value, default, band, module, source operation |
| POLICY | supervision, safeguard and routing policy settings, quota groups |
| QUOTA | provider quota reading of one profile with the floor and reserve |
| ROLE_CONFIG | effective configuration of one role: lanes, models, effort, caps, timeouts, tool budget, role limits, routing |
| RUNTIME | runtime settings |

| field | type | unit | meaning |
|---|---|---|---|
| basis | string |  | LIVE or RECONSTRUCTED_CURRENT_BASE (overlay operations over the current base config) |
| config | object |  | typed effective configuration |
| content_sha256 | string |  | sha256 of the canonical snapshot content |
| op_id | string |  | lanectl operation id |
| scope | string |  | scope of a denial or snapshot |
| trigger | string |  | CHANGED, DAILY or RECONSTRUCTED_AT_OP |

## Stream `evaluations`

| kind | meaning |
|---|---|
| MEASURE_ROW | daily measure table row per role, model and effort (telemetry_report.measure) |
| QUOTA_WEIGHT | S700 estimated quota points per million tokens of one model (no model: all models pooled, with the token-kind fit) on one profile, quota group and limit window (telemetry_report.quota_weights): estimate, 90% interval, weight relative to the most used model, status, data still needed |
| ROLE_SCORECARD | S683 role effectiveness scorecard numbers per role (role_effectiveness.report, live window) |

| field | type | unit | meaning |
|---|---|---|---|
| effort | string |  | reasoning effort of the lane or turn (low, medium, high) |
| group | string |  | quota group |
| limit_category | string |  | S700 quota category as the usage command prints it, as a slug |
| limit_window | string |  | S700 window of the limit read from its kind (weekly, five_hour, daily, <n>_hour) |
| metrics | measures |  | numeric measures (see the kind) |
| model | string |  | model id the turn ran on (requested model) |
| profile | string |  | CLI credential profile alias of the lane (A, A2, B, C) |
| window_days | integer | days | window of the scorecard (QUOTA_WEIGHT: of the readings and turns the estimate used; FLOW_DAILY: of the flow metrics) |

## Stream `quota_readings`

| kind | meaning |
|---|---|
| QUOTA_READING | S700 one limit of one provider quota reading: profile, category, window, remaining percent, reset, reader |
| QUOTA_READING_FAILED | S700 one failed quota reading (typed error class) |

| field | type | unit | meaning |
|---|---|---|---|
| bracket | string |  | S700 id shared by the readings of one admission (before and after its turn) |
| caller | string |  | S700 module that asked for the reading (pilot_core, implementer_transport, profile_failover, ...) |
| error_class | string |  | typed class of an error (code, exception name or TEXT_<digest>) |
| group | string |  | quota group |
| limit_category | string |  | S700 quota category as the usage command prints it, as a slug |
| limit_label | string |  | S700 limit kind as the usage command prints it, as a slug |
| limit_reset_at | string |  | S700 reset time of the limit window (UTC) |
| limit_window | string |  | S700 window of the limit read from its kind (weekly, five_hour, daily, <n>_hour) |
| previous_remaining_percent | number | percent | S700 the value before this change |
| previous_reset_at | string |  | S700 the reset before this change, when it differs |
| previous_seen_bracket | string |  | S700 bracket of that reading |
| previous_seen_reader | string |  | S700 reader of that reading |
| previous_seen_ts | string |  | S700 time of the last reading that still showed the previous value |
| profile | string |  | CLI credential profile alias of the lane (A, A2, B, C) |
| query_s | number | s | S700 duration of the usage command of the reading |
| reader | string |  | S700 reading of an admission (admission:before, admission:after: around one turn under the profile lock) or of a held preparation (retry_hold) |
| reading_id | string |  | S700 id of one reading (its limit rows share it) |
| reading_source | string |  | S700 record the reading came from: LEDGER (receipts/quota), BUDGET_STATE (state/agy-budget-<profile>.json), SNAPSHOT_BACKFILL (a QUOTA snapshot of that file), FAILOVER_EVENT (a profile failover decision) |
| remaining_percent | number | percent | S700 remaining share of the limit window as printed (whole points) |
| unchanged_readings | integer |  | S700 readings of the same value the ledger left out since its previous row of this limit |

## Stream `flow`

| kind | meaning |
|---|---|
| FLOW_DAILY | S702 the daily flow metrics: WIP, age, throughput, cycle time, flow efficiency, Little's Law, and the tuned expectation |
| WIP_CLOSE | S702 one typed close of an agent pull request (deadline missed or hold expired): closed, link |
| WIP_DECISION | S702 one decision the pilot took and recorded (CONVERGE_ROUTE: the deadline of an aged agent pull request) |
| WIP_SNAPSHOT | S702 the WIP view when its counts change (at least hourly): open pull requests, limit, started Work Items, aged and expired units, stages, trends |
| WIP_START | S702 one start admission at an enforcement point (op class, admitted, reason, WIP and limit) |
| WIP_TRANSITION | S702 a unit entered or left a condition (AGED, HOLD_EXPIRED, DEADLINE_MISSED) or left the WIP |
| WIP_UNIT | S702 one work unit when its typed state changes: stage, age, idle time, last real progress, trend, verdict, blocker, conditions, action |

| field | type | unit | meaning |
|---|---|---|---|
| action | string |  | typed action |
| active_s | number | s | S702 Implementer turn time on the unit in the history window (flow efficiency: active) |
| admitted | boolean |  | S702 the operation was admitted |
| aged_units | integer |  | S702 units idle longer than their age expectation |
| already_closed | boolean |  | S702 the pull request was closed before the close ran |
| author_class | string |  | S702 author of the pull request: OWNER, AGENT, OTHER, UNKNOWN |
| authority | string |  | S702 who decides a close: OWNER (disposition) or PILOT (agent-authored with a Work Item) |
| blocker | string |  | S702 first typed blocker: HOLD:<predicate>, DISPOSITION:<status>, REMEDY:<remedy>, CUSTODY:<state>:<reason>, GATE:<criteria>, NONE |
| class_reason | string |  | S702 why the operation has its class (NEW_WORK_ITEM_PULL_REQUEST, UNSTARTED_WORK_ITEM, ...) |
| closed | boolean |  | S702 the typed close read back closed |
| closeness | number |  | S702 closeness to merge 0..1 (the scheduler aging term) |
| condition | string |  | S702 the condition a transition entered or left (or LEFT_WIP) |
| conditions | strings |  | S702 AGED, HOLD_EXPIRED, DEADLINE_MISSED |
| custody_state | string |  | S702 goal custody state:reason of the unit's Work Item |
| deadline_ts | string |  | S702 the convergence deadline the pilot set (CONVERGE_ROUTE) |
| decision | string |  | typed decision |
| disposition_status | string |  | S702 status of the unit's S694 disposition review |
| enforcement_point | string |  | S702 OPEN_PR (publication_opener), DISPATCH, SCHEDULE (work_scheduler) |
| entered | boolean |  | S702 the condition was entered (false: left) |
| expectation_s | number | s | S702 the age expectation of the unit class without real progress |
| failing_criteria | strings |  | S702 merge-admission criteria failing at the latest verdict |
| hold_expired_units | integer |  | S702 units held longer than the hold expiry |
| hold_predicate | string |  | S702 the S685 hold predicate or OWNER_HOLD |
| implementer_tokens | integer | tokens | S702 Implementer tokens on the unit in the history window |
| implementer_turns | integer |  | S702 launched Implementer turns on the unit in the history window |
| last_progress_ts | string |  | S702 time of the last real progress |
| link_status | string |  | S702 the Work Item link of the close (PRESENT, POSTED, UNCONFIRMED, FAILED) |
| metrics | measures |  | numeric measures (see the kind) |
| op_class | string |  | S702 START, FINISH or REPLACE |
| operation_action | string |  | operation action of a dispatch |
| over_limit | integer |  | S702 open pull requests above the limit |
| progress_kind | string |  | S702 the last real progress: CRITERION_GREEN, VERDICT_ALLOW, THREADS_DOWN, DECIDED, MERGED, OPENED, NONE_OBSERVED |
| reason | string |  | typed reason (class of the source reason) |
| stage_counts | counts |  | S702 units per stage (STARTED, CONVERGING, MERGEABLE, MERGED, CLOSED) |
| started_ts | string |  | S702 start of the unit (the pull request created_at; a Work Item: its first launched turn) |
| trend | string |  | S702 CONVERGING, DIVERGING, FLAT or UNKNOWN over the trend window |
| trend_basis | string |  | S702 CRITERIA, THREADS or S697A_DIVERGENCE |
| trend_counts | counts |  | S702 pull request units per trend (CONVERGING, DIVERGING, FLAT, UNKNOWN) |
| tune_metrics | measures |  | S702 the expectations the data supports (p85 cycle time of merged pull requests) |
| unit_age_s | number | s | S702 work item age: now minus the start |
| unit_class | string |  | S702 OWNER_PR, AGENT_PR, OTHER_PR or WORK_ITEM (the age expectation class) |
| unit_idle_s | number | s | S702 time since the last real progress (or the start) |
| unit_kind | string |  | S702 PR or WORK_ITEM |
| unit_remedy | string |  | S702 the registered remedy of the unit's Work Item |
| unit_stage | string |  | S702 STARTED, CONVERGING (a DENY verdict), MERGEABLE (ALLOW at the head), MERGED, CLOSED |
| unresolved_threads | integer |  | S702 unresolved review threads at the latest exact read |
| verdict | string |  | S702 latest merge-admission verdict status (ALLOW, DENY) |
| verdict_current | boolean |  | S702 the verdict is at the open head |
| window_days | integer | days | window of the scorecard (QUOTA_WEIGHT: of the readings and turns the estimate used; FLOW_DAILY: of the flow metrics) |
| wip | integer |  | S702 open pull requests (the WIP the start limit counts) |
| wip_basis | string |  | S702 where the open set came from: OBSERVER_SCOPE (complete) or PORTFOLIO (last reads) |
| wip_limit | integer |  | S702 the limit for starting new work (supervision.wip.limit_open_prs) |
| work_items_started | integer |  | S702 Work Items started (an open pull request or a launched Implementer turn) |

## Stream `delivery`

| kind | meaning |
|---|---|
| DELIVERY_CLOSE | S704 one pull request closed without merge when its CloseRecord status changes: class, validity, basis, source, follow-up, successor latency |
| DELIVERY_COMMENT | S704 one version of the maintained delivery-state comment on the Owner thread |
| DELIVERY_FINDING | S704 one integrity finding entered or left (kind, subject, route) |
| DELIVERY_ITEM | S704 one Work Item when its typed delivery state changes: class, rule, resume conditions, review date, open, integrated and attempt pull requests, custody |
| DELIVERY_REGISTER | S704 the delivery register on every digest change (and hourly): status, Work Items per class, findings per kind, CloseRecords per class, source coverage, metrics |
| DELIVERY_ROUTE | S704 one routing effect of a finding (route, status) |
| OWNER_QUEUE | S708 the set of pending Owner decisions on every digest change (and hourly): count, ages, kinds, sources, critical path, dashboard issue |
| OWNER_QUEUE_EFFECT | S708 one provider effect of the owner queue and its readback (dashboard, label, reaction, mention, pin, answer recorded) |
| OWNER_QUEUE_ITEM | S708 one pending Owner decision entered or left the set (kind, source, subjects, age, answer comment) |

| field | type | unit | meaning |
|---|---|---|---|
| attempt_pulls | integers |  | S704 pull requests of the Work Item closed without merge (never integrated) |
| author_role | string |  | S704 author of the closed pull request: OWNER, APP, AGENT, OTHER |
| class_counts | counts |  | S704 Work Items per class |
| close_basis | string |  | S704 FACT, DERIVED or JUDGMENT |
| close_by | string |  | S704 who recorded the class: OWNER, PILOT, AGENT, OTHER |
| close_class | string |  | S704 the CloseRecord class: SUPERSEDED_FULL, SUPERSEDED_PARTIAL, REDIRECTED, SEQUENCED, CARRIED, PROBE (none: missing or invalid) |
| close_counts | counts |  | S704 pull requests closed without merge per CloseRecord class (MISSING: none valid) |
| close_invalid | string |  | S704 why the CloseRecord is missing or invalid |
| close_source | string |  | S704 S693_CARRIER, S701_DECIDED, S702_WIP, DISPOSITION_RECORD, OWNER_LINE, CLOSE_COMMENT, TITLE_DECLARATION |
| close_valid | boolean |  | S704 the CloseRecord satisfies its class evidence rule |
| closed_ts | string |  | S704 when the pull request closed |
| closer_role | string |  | S704 who closed it: OWNER, APP, AGENT, OTHER |
| comment_chars | integer |  | S704 its size in characters |
| comment_id | integer |  | S704 the maintained delivery-state comment on the Owner thread |
| comment_sha | string |  | S704 sha256 prefix of the comment body |
| comment_status | string |  | S704 POSTED, PATCHED, UNCONFIRMED, FAILED or REFUSED_HOST_DETAIL |
| comment_version | integer |  | S704 its version (posts and edits that read back) |
| custody_word | string |  | S704 the goal custody state:reason of the Work Item |
| delivery_class | string |  | S704 the Work Item problem class: SOLVED, IN_PROGRESS, DEFERRED, UNSOLVED_UNSCHEDULED, UNSOLVED, CLOSED_UNVERIFIED, NOT_PLANNED |
| delivery_metrics | measures |  | S704 unmerged closes, valid CloseRecords and their percent (target 100), orphaned follow-ups (target 0), close-to-successor latency p50/max, closes in the window |
| delivery_rule | string |  | S704 the classification rule (R1..R8, delivery_register.classify) |
| delivery_tag | string |  | S704 F (recorded fact), D (deterministic derivation) or J (human judgment) |
| digest_changed | boolean |  | S704 the digest changed (false: the hourly heartbeat) |
| finding_counts | counts |  | S704 findings per kind |
| finding_entered | boolean |  | S704 the finding was entered (false: it left) |
| finding_id | string |  | S704 the finding id (stable per kind, subject and key) |
| finding_kind | string |  | S704 FALSE_SOLVED, UNEVIDENCED_CLOSE, STALE_RECORD, ATTEMPT_UNRECORDED, MISSING_CLOSE_RECORD, INVALID_CLOSE_RECORD, FALSE_SUPERSEDED, ORPHANED_FOLLOW_UP, SEQUENCED_BLOCKED, FORGOTTEN, RESUME_DUE, REVIEW_DUE, ATTEMPT_UNOWNED, FOLLOW_UP, TRIAGE |
| follow_up | strings |  | S704 the follow-up status per successor: SCHEDULED, PENDING, OPENED, MERGED, ORPHANED |
| forgotten_tier | string |  | S704 ATTEMPT_DROPPED, CUSTODY_DONE_OPEN, INTEGRATED_OPEN or NEVER_ADMITTED |
| in_window | boolean |  | S704 closed inside the attempt window (attempt_window_days) |
| integrated_items | integer |  | S704 Work Items with at least one merged pull request |
| integrated_pulls | integers |  | S704 merged pull requests bound to the Work Item |
| integrated_total | integer |  | S704 merged pull requests bound to Work Items |
| mention_status | string |  | S704 what the record line says of the pull request: PENDING or LANDED |
| open_pulls | integers |  | S704 open pull requests bound to the Work Item |
| owner_queue_action | string |  | S708 DASHBOARD_CREATE, DASHBOARD_FOUND, DASHBOARD_EDIT, DASHBOARD_REOPEN, CONFIG_WRITE, PIN, LABEL_CREATE, LABEL_ADD, LABEL_REMOVE, ANSWER_RECORDED, REACTION, MENTION |
| owner_queue_age_s | number | s | S708 the item age when it entered or left |
| owner_queue_ages_s | integers |  | S708 the age in seconds of every pending Owner decision, oldest first |
| owner_queue_changed | boolean |  | S708 the set digest changed (false: the hourly heartbeat) |
| owner_queue_chars | integer |  | S708 the dashboard body size in characters |
| owner_queue_comment | integer |  | S708 the answer comment (an item that left) or the comment written (an effect) |
| owner_queue_critical | integer |  | S708 pending Owner decisions on the critical path (Owner-ordered work items, S702 WIP units) |
| owner_queue_digest | string |  | S708 the set digest (sha256 prefix) |
| owner_queue_effects | boolean |  | S708 provider effects enabled (false: the set is computed and recorded only) |
| owner_queue_entered | boolean |  | S708 the item entered the set (false: it left, answered or resolved) |
| owner_queue_item | string |  | S708 sha256 prefix of the pending item id (stable per decision) |
| owner_queue_items | integer |  | S708 items named by one mention |
| owner_queue_kind | string |  | S708 the kind of the pending item |
| owner_queue_kinds | counts |  | S708 pending Owner decisions per kind (DISPOSITION, TRIAGE, DELIVERY:<finding>, STARVATION, ...) |
| owner_queue_n | integer |  | S708 pending Owner decisions in the set (every one listed, no cap) |
| owner_queue_oldest_s | number | s | S708 age of the oldest pending Owner decision |
| owner_queue_on_path | boolean |  | S708 the item is on the critical path |
| owner_queue_sha | string |  | S708 sha256 prefix of the dashboard body |
| owner_queue_source | string |  | S708 its producer source: disposition, triage, register, escalation, custody |
| owner_queue_sources | counts |  | S708 producer sources per read status (OK, or the error class of an unreadable one) |
| owner_queue_status | string |  | S708 the effect outcome after its readback (CREATED, EDITED, CONFIRMED, UNCONFIRMED, REFUSED, PINNED, PIN_UNAVAILABLE, ...) |
| owner_queue_subjects | integers |  | S708 the issue and pull request numbers the item names (the labelled subjects) |
| owner_queue_tier | integer |  | S708 the mention tier in days (3, then 7) |
| record_line | integer |  | S704 the line of that record |
| record_ref | string |  | S704 the knowledge record a STALE_RECORD names (decision:NNNN, runbook:<name>, orientation:<ext>, roadmap) |
| register_digest | string |  | S704 the register digest (sha256 prefix, volatile fields excluded) |
| register_status | string |  | S704 CURRENT, STALE or INCOMPLETE (a mandatory source missing or stale) |
| resume_condition | string |  | S704 the first typed resume condition of a deferred Work Item |
| resume_conditions | strings |  | S704 every typed resume condition (AFTER_MERGE, AFTER_DATE, OWNER_ADMISSION, WIP_SLOT, HOLD_RELEASE, OWNER_DECISION, CAPABILITY, EXCLUDED) |
| resume_satisfied | boolean |  | S704 every resume condition is satisfied |
| review_ts | string |  | S704 the deferral review date (explicit or the fallback) |
| roadmap_labels | strings |  | S704 roadmap and lifecycle labels of the Work Item |
| route | string |  | S704 CUSTODY_ADMISSION, ROUTER_REQUEST, ATTEMPT_LINE, DISPOSITION_REVIEW, OWNER_ESCALATION, OWNER_TRIAGE |
| route_status | string |  | S704 the outcome of the routing effect (ADMITTED, DELIVERED, POSTED, PRESENT, QUEUED, RECORDED, BOUND, ...) |
| source_states | counts |  | S704 sources per coverage state (COMPLETE, PARTIAL, STALE, MISSING) |
| successor_latency_s | number | s | S704 time from the close to the first successor pull request |
| successor_pulls | integers |  | S704 the successor pull requests opened for the closed one |
| typed_close | string |  | S704 the pilot's typed close that closed it (S693_CARRIER, S701_DECIDED, S702_WIP) |
| unbound_merged | integer |  | S704 merged pull requests with no Work Item binding |
| work_item_state | string |  | S704 the provider state of the Work Item (open, closed) |

## Loop rules (tool_events.loop_flags)

| flag | field | threshold |
|---|---|---|
| CONSECUTIVE_IDENTICAL_COMMAND | max_consecutive_identical | >= 3 |
| REPEATED_IDENTICAL_COMMAND | max_identical_repeats | >= 4 |
| REPEATED_READ_RANGE | read_range_repeats | >= 3 |
| STATUS_POLLING | status_polls | >= 20 |

Cross-turn repetition: the report lists inputs with 5 or more role turns.

## Privacy

- Allowlist: only typed fields are copied (codes, ids, numbers, model, lane and profile aliases, commit shas, public issue,
  pull request and comment ids). Comment bodies, prompts, responses, command lines, tool outputs, error prose and paths are
  never copied; a digest (`*_digest`, `text_sha256`, `conversation`) or a typed class (`error_class`, `reason`, `cause_class`:
  the code, the exception name or `TEXT_<digest>`) takes their place. Commands appear only as program-name counts and
  repetition counts of their digests.
- Every string of a record is checked for credential shapes and host paths, and every serialized record against the
  categories of the repository disclosure scanner. A record that fails is dropped and counted per reason in the manifest
  (`dropped`, `dropped_ids`).
- Before publication the disclosure gate runs on every file of the commit; the manifest records its result.

## Definitions used by the analysis

- Useful result: router = the input Router job ended PUBLISHED with a publication; pao and sas = the peer result was
  PUBLISHED and CONSUMED by the coordinator; implementer = execution outcome COMPLETE or material progress.
- Tokens per useful result = all tokens of the role, model and effort / useful results credited to them (the last
  successful turn of an input carries its result).
- Snapshots: ROLE_CONFIG, LIMITS, RUNTIME and POLICY are written when their content changes and once per UTC day
  (`trigger` CHANGED or DAILY); `RECONSTRUCTED_AT_OP` rows rebuild the lane and limit history from the runtime overlay
  operations over the current base configuration (`basis` RECONSTRUCTED_CURRENT_BASE).
- Quota readings (S700): one `quota_readings` record per limit of every provider quota reading the pilot took
  (admission before and after each turn, held-preparation rechecks, failover polls; `reader`, `caller`, `bracket`);
  the pilot ledger leaves out a repeat of an unchanged value within 300 s and the next row states the previous value and
  its last reading (`previous_*`). Readings recorded before S700 come from the QUOTA snapshots (SNAPSHOT_BACKFILL).
- Quota weights (S700, evaluations QUOTA_WEIGHT): quota points per million tokens per model and token kind, by
  non-negative least squares over the intervals between consecutive readings of one window (same reset), each turn
  charged to the first reading at or after its time plus the reporting lag; a 90% bootstrap interval; ESTIMABLE only
  with >= 8 intervals and a half-width <= 25% of the estimate, else the factor of more data still needed.
- Work in progress (S702, stream `flow`): one record per change of the WIP view and of each unit (an open pull
  request or a started Work Item), every start admission at an enforcement point, every condition entered or left,
  the pilot's convergence routes and closes, and one FLOW_DAILY row per UTC day with the Kanban flow measures (WIP,
  throughput, work item age, cycle time), flow efficiency and Little's Law, plus the expectation the data supports.
- Schema changes: a new field is additive within v1; a change of meaning or type starts `v2` beside `v1`.

