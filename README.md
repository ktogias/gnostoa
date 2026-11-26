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
| CUSTODY | one input custody settlement |
| DEPTH_TIER | the adaptive effort tier chosen for an Implementer turn |
| ESCALATION | one Router escalation (typed class) |
| IMPLEMENTER_GATE | one Implementer wake-gate decision (launch or not, rotation, transport plan) |
| LANE_ROTATION | a lane or conversation rotation of an Implementer turn |
| LIMIT_PROBE | one transport limit probe |
| MODEL_SWITCH | a transport family switch for an Implementer turn |
| OWNER_ESCALATION | one Owner escalation ledger request (latest version) |
| REFUSAL | one refusal of a Router job (typed class) |
| ROUTER_DISPATCH | one Router assignment to a role (operation action, target, retry reason) |
| ROUTER_JOB | one Router job (latest version per job): status, attempts, refusals, escalation, publications |
| ROUTING | one S686 routing decision (task class, tier, first lane, expected costs) |
| SAFEGUARD | one S684 Router safeguard decision (aged pending, family breaker, stale authority) |
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
| blocker_kind | string |  | blocker kind |
| brake | string |  | typed brake reason |
| capacity_hold | string |  | typed capacity hold reason |
| cause_class | string |  | typed class of the source cause text |
| completion | strings |  | completion criteria the dispatch names |
| consumer | string |  | consumer of the signal |
| context_last_request | integer | tokens | context tokens of the lane last request at the gate |
| context_median | integer | tokens | median context tokens per call of the lane at the gate |
| costs | integers | tokens | expected cost per tier |
| coverage | string |  | continuation frontier coverage |
| criterion | string |  | merge criterion |
| decision | string |  | typed decision |
| detector | string |  | detector name |
| duration_s | number | s | wall-clock duration |
| effort | string |  | reasoning effort of the lane or turn (low, medium, high) |
| episode | string |  | digest of the episode id |
| error_class | string |  | typed class of an error (code, exception name or TEXT_<digest>) |
| escalation_class | string |  | typed escalation class |
| escalation_denied | string |  | why an escalation was denied |
| escalation_kind | string |  | escalation kind |
| evidence | strings |  | evidence sources the dispatch names |
| explore | boolean |  | the routing decision explored |
| fact_classes | counts | facts | facts per class |
| facts | integer |  | facts the gate saw |
| failure_causes | counts | attempts | failed attempts per cause |
| family | string |  | transport family (agy, claude, codex) |
| final_reason | string |  | typed final reason |
| first_lane | string |  | lane key the routing decision chose |
| from_family | string |  | family before the switch |
| frontier_exhausted | boolean |  | the continuation frontier was exhausted |
| group | string |  | quota group |
| guess | integer |  | first-guess tier |
| head | string |  | commit sha (public) |
| input_type | string |  | typed input type |
| items | integer |  | assignment items of the job |
| ladder | integer |  | tiers on the ladder |
| lane | string |  | lane key model@profile |
| last_failure_cause | string |  | cause of the last failed attempt |
| limit_kind | string |  | kind of provider limit (QUOTA, DAILY_CAP, OVERLOAD) |
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
| plan_family | string |  | transport family the gate planned |
| plan_switch | boolean |  | the gate planned a family switch |
| predicate | string |  | gate predicate |
| previous | string |  | previous status |
| profile | string |  | CLI credential profile alias of the lane (A, A2, B, C) |
| publication_statuses | counts | publications | publications per status |
| publications | integer |  | publications of the job |
| published | boolean |  | the output was published |
| reason | string |  | typed reason (class of the source reason) |
| reasons | integer |  | reasons recorded |
| recipient | string |  | recipient role |
| recipients | counts | publications | publications per recipient role |
| reference_comment | integer |  | comment id of the reference |
| reference_issue | integer |  | issue of the reference |
| refusal_class | string |  | typed refusal class |
| refusal_classes | counts | refusals | refusals per class |
| refusals | integer |  | refusals of the job |
| released_brake | string |  | typed reason of a released brake |
| reported_tokens | tokens | tokens | tokens as the role receipt reports them (agy: cumulative for the conversation) |
| represented_reason | string |  | why a dispatch was represented |
| required_approvers | integer |  | required approvers |
| reset_at | string |  | earliest reset time |
| retry_reason | string |  | typed retry reason of a dispatch |
| rotate_before_launch | boolean |  | the gate rotated the conversation before launch |
| rule | string |  | typed rule |
| safeguard | string |  | safeguard name |
| source_role | string |  | role that produced the input |
| stall_kind | string |  | stall detector kind |
| stalls | integer |  | stalls counted by the tier rule |
| status | string |  | status code of the source record |
| streak_max | integer |  | longest streak the tier rule saw |
| switch | boolean |  | the transport family switched for this turn |
| switch_reason | string |  | typed reason of the transport choice |
| target_issue | integer |  | issue number of the publication |
| task_class | string |  | task class of a routing decision |
| terminal_failure | boolean |  | the job ended as a terminal failure |
| terminal_reason | string |  | typed terminal reason |
| tier | integer |  | adaptive effort tier chosen (0 = base) |
| tier_reason | string |  | why the tier was chosen (BASE, ESCALATE_AFTER_STALL, ...) |
| transport | string |  | transport of the turn (agy, claude-print, codex-exec, *-resume) |
| version | string |  | version of the deciding rule |

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
| marker | string |  | typed marker of the input |
| material_progress | boolean |  | the turn changed the worktree or source state |
| model | string |  | model id the turn ran on (requested model) |
| model_attempts | integer |  | model attempts recorded |
| num_turns | integer |  | provider turns inside the call |
| outcome | string |  | typed outcome |
| permission_denials | integer |  | permission denials the provider reported |
| profile | string |  | CLI credential profile alias of the lane (A, A2, B, C) |
| prompt_bytes | integer | bytes | prompt size |
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
| ROLE_SCORECARD | S683 role effectiveness scorecard numbers per role (role_effectiveness.report, live window) |

| field | type | unit | meaning |
|---|---|---|---|
| effort | string |  | reasoning effort of the lane or turn (low, medium, high) |
| metrics | measures |  | numeric measures (see the kind) |
| model | string |  | model id the turn ran on (requested model) |
| window_days | integer | days | window of the scorecard |

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
- Schema changes: a new field is additive within v1; a change of meaning or type starts `v2` beside `v1`.

