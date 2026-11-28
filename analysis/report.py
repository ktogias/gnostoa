#!/usr/bin/env python3
"""Pilot telemetry analysis, schema v1. Standard library only.

Runs on a checkout of the telemetry branch (this file is published there as analysis/report.py):

    python3 analysis/report.py [--root DIR] [--since YYYY-MM-DD] [--until YYYY-MM-DD] [--json]

It reads telemetry/v1/YYYY/MM/DD/<stream>.jsonl, keeps the latest version of every mutable entity (records that carry
an `entity` key: a Router job, a peer result, an Implementer receipt, an escalation, a hold), and prints:

1. tokens per useful result per role, model and effort;
2. denial and stop rates per role, with the denied programs and shapes and the typed stop reasons;
3. loop counts: turns with a loop flag, and inputs that took many turns;
4. delivery rates: Implementer outcomes, peer (PAO/SAS) publication and consumption, Router publication;
5. decision outcomes per decision kind;
6. configuration changes per kind and operation;
7. S700 quota weights: estimated quota points per million tokens per model and per token kind (quota_weights below);
8. S702 flow: work in progress against its start limit, the age of open work, throughput, cycle time, flow efficiency,
   Little's Law, the start admissions refused, the aged units and the pilot's closes (flow_report below).

Useful result (the registry USEFUL below, data):
- router: the input's Router job ended PUBLISHED with at least one publication;
- pao, sas: the input's peer result was PUBLISHED and its consumer status is CONSUMED;
- implementer: the receipt's execution outcome is COMPLETE, or the turn made material progress (receipts whose model
  turn never started, held by the wake gate, are decisions and are not counted as turns).
A role turn's tokens are its own usage delta (`tokens.total`). The useful result of an input is credited to the role,
model and effort of the input's last successful turn; tokens per useful result = all tokens of the group / its useful
results. The telemetry collector calls measure() and rollup() for the daily evaluation records and the manifest, so
the published numbers and this report use one definition.
"""
import argparse
import bisect
import collections
import datetime as dt
import json
import math
from pathlib import Path
import random
import re
import sys

SCHEMA_VERSION = 1
STREAMS = ('turns', 'tool_events', 'decisions', 'deliveries', 'config_changes', 'snapshots', 'evaluations', 'quota_readings',
           'flow', 'delivery')  # S704: the delivery register
ROLES = ('router', 'pao', 'sas', 'implementer')
DENIAL_CAUSES = frozenset({'TOOL_PERMISSION_DENIED', 'TOOL_CHANNEL_VIOLATION'})
STOP_CAUSES = frozenset({'TOOL_BUDGET', 'PROCESS_TIMEOUT', 'TIMEOUT', 'TASK_STATUS_LOOP'})
LOOP_TURNS_PER_INPUT = 5  # an input that took this many role turns or more is a cross-turn repetition
USEFUL = {
    'router': lambda job: job.get('status') == 'PUBLISHED' and (job.get('publications') or 0) > 0,
    'pao': lambda peer: peer.get('status') == 'PUBLISHED' and peer.get('consumer_status') == 'CONSUMED',
    'sas': lambda peer: peer.get('status') == 'PUBLISHED' and peer.get('consumer_status') == 'CONSUMED',
}


def load(root, since=None, until=None, streams=STREAMS):
    """{stream: [record]} of the partitions in [since, until] (UTC days, inclusive), latest version per entity."""
    data = {stream: [] for stream in streams}
    base = Path(root) / 'telemetry' / 'v1'
    for path in sorted(base.glob('[0-9][0-9][0-9][0-9]/[0-9][0-9]/[0-9][0-9]/*.jsonl')):
        day = '-'.join(path.parts[-4:-1])
        if path.stem not in data or (since and day < since) or (until and day > until):
            continue
        for line in path.read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if isinstance(record, dict) and record.get('schema_version') == SCHEMA_VERSION:
                data[path.stem].append(record)
    return latest(data)


def latest(data):
    """Each stream with only the newest version (by ts, then record_id) of every (kind, entity)."""
    out = {}
    for stream, records in data.items():
        keep, plain = {}, []
        for record in records:
            entity = record.get('entity')
            if not entity:
                plain.append(record)
                continue
            key = (record.get('kind'), entity)
            old = keep.get(key)
            if old is None or (record.get('ts') or '', record.get('record_id') or '') > (old.get('ts') or '', old.get('record_id') or ''):
                keep[key] = record
        out[stream] = sorted(plain + list(keep.values()), key=lambda r: (r.get('ts') or '', r.get('record_id') or ''))
    return out


def _subject(record, name):
    subject = record.get('subject')
    return subject.get(name) if isinstance(subject, dict) else None


def _total(record):
    tokens = record.get('tokens')
    value = tokens.get('total') if isinstance(tokens, dict) else None
    return value if type(value) is int else 0


def _group():
    return {'turns': 0, 'launched': 0, 'success': 0, 'failed': 0, 'tokens': 0, 'failed_tokens': 0, 'denials': 0,
            'stops': 0, 'useful': 0}


def measure(data):
    """[{role, model, effort, turns, launched, success, failed, tokens, failed_tokens, denials, stops, useful,
    tokens_per_useful, success_rate, denial_rate, stop_rate}] sorted by role, model and effort."""
    groups = collections.defaultdict(_group)
    outcomes = {'router': {}, 'pao': {}, 'sas': {}}
    for job in data.get('decisions', []):
        if job.get('kind') == 'ROUTER_JOB' and _subject(job, 'input_key'):
            outcomes['router'][_subject(job, 'input_key')] = job
    for peer in data.get('deliveries', []):
        role = _subject(peer, 'role')
        if peer.get('kind') == 'PEER_RESULT' and role in outcomes and _subject(peer, 'input_key'):
            outcomes[role][_subject(peer, 'input_key')] = peer
    last_success = {}
    for turn in data.get('turns', []):
        role = _subject(turn, 'role') or 'unknown'
        key = (role, turn.get('model') or '-', turn.get('effort') or '-')
        group = groups[key]
        group['turns'] += 1
        group['launched'] += 1 if turn.get('launched') else 0
        tokens = _total(turn)
        group['tokens'] += tokens
        if turn.get('status') == 'SUCCESS':
            group['success'] += 1
            if _subject(turn, 'input_key'):
                last_success[(role, _subject(turn, 'input_key'))] = key
        else:
            group['failed'] += 1
            group['failed_tokens'] += tokens
        if turn.get('cause_code') in DENIAL_CAUSES or (turn.get('permission_denials') or 0) > 0:
            group['denials'] += 1
        if turn.get('cause_code') in STOP_CAUSES:
            group['stops'] += 1
    for (role, input_key), key in last_success.items():
        found = outcomes.get(role, {}).get(input_key)
        if found is not None and USEFUL[role](found):
            groups[key]['useful'] += 1
    for receipt in data.get('deliveries', []):
        # a receipt the wake gate held (no model turn started) is a decision, not a turn
        if receipt.get('kind') != 'IMPLEMENTER_TURN' or receipt.get('turn_started') is not True:
            continue
        group = groups[('implementer', receipt.get('model') or '-', receipt.get('effort') or '-')]
        group['turns'] += 1
        group['launched'] += 1
        tokens = _total(receipt)
        group['tokens'] += tokens
        if receipt.get('status') == 'COMPLETE':
            group['success'] += 1
        else:
            group['failed'] += 1
            group['failed_tokens'] += tokens
        if receipt.get('error_class') in DENIAL_CAUSES or (receipt.get('permission_denials') or 0) > 0:
            group['denials'] += 1
        if receipt.get('error_class') in STOP_CAUSES:
            group['stops'] += 1
        if receipt.get('outcome') == 'COMPLETE' or receipt.get('material_progress') is True:
            group['useful'] += 1
    rows = []
    for (role, model, effort), group in sorted(groups.items()):
        turns = group['turns'] or 1
        rows.append(dict(role=role, model=model, effort=effort, **group,
                         tokens_per_useful=round(group['tokens'] / group['useful']) if group['useful'] else None,
                         success_rate=round(group['success'] / turns, 3), denial_rate=round(group['denials'] / turns, 3),
                         stop_rate=round(group['stops'] / turns, 3)))
    return rows


def loops(data):
    """{flags: {role: {flag: turns}}, inputs: [(role, input_key, turns)] with LOOP_TURNS_PER_INPUT turns or more}."""
    flags = collections.defaultdict(collections.Counter)
    for event in data.get('tool_events', []):
        if event.get('kind') == 'TURN_TOOLS':
            for flag in event.get('loop_flags') or []:
                flags[_subject(event, 'role') or 'unknown'][flag] += 1
    per_input = collections.Counter((_subject(t, 'role') or 'unknown', _subject(t, 'input_key'))
                                    for t in data.get('turns', []) if _subject(t, 'input_key'))
    inputs = sorted(((role, key, n) for (role, key), n in per_input.items() if n >= LOOP_TURNS_PER_INPUT),
                    key=lambda row: (-row[2], row[0], row[1]))
    return {'flags': {role: dict(sorted(c.items())) for role, c in sorted(flags.items())}, 'inputs': inputs}


def denials_and_stops(data):
    denials = collections.Counter()
    stops = collections.Counter()
    for event in data.get('tool_events', []):
        role = _subject(event, 'role') or 'unknown'
        if event.get('kind') == 'DENIAL':
            denials[(role, event.get('program') or '-', event.get('shape') or '-')] += event.get('count') or 1
        elif event.get('kind') == 'TOOL_STOP':
            stops[(role, event.get('stop_class') or '-', event.get('stop_reason') or '-')] += 1
        elif event.get('kind') == 'CHANNEL_VIOLATION':
            denials[(role, 'channel', event.get('shape') or '-')] += 1
    return ([dict(role=r, program=p, shape=s, count=n) for (r, p, s), n in sorted(denials.items())],
            [dict(role=r, stop_class=c, stop_reason=s, count=n) for (r, c, s), n in sorted(stops.items())])


def deliveries(data):
    out = collections.defaultdict(collections.Counter)
    for record in data.get('deliveries', []):
        kind = record.get('kind')
        if kind == 'IMPLEMENTER_TURN':
            out['implementer_status'][record.get('status') or '-'] += 1
            out['implementer_outcome'][record.get('outcome') or '-'] += 1
        elif kind == 'PEER_RESULT':
            role = _subject(record, 'role') or 'unknown'
            out[role + '_status'][record.get('status') or '-'] += 1
            out[role + '_consumer'][record.get('consumer_status') or '-'] += 1
        elif kind:
            out[kind.lower()][record.get('state') or record.get('status') or '-'] += 1
    for job in data.get('decisions', []):
        if job.get('kind') == 'ROUTER_JOB':
            out['router_job_status'][job.get('status') or '-'] += 1
    return {name: dict(sorted(c.items())) for name, c in sorted(out.items())}


OUTCOME_FIELDS = ('decision', 'action', 'outcome', 'status', 'rule', 'reason')


def decisions(data):
    """{decision kind: {outcome: n}}: the outcome is the first of OUTCOME_FIELDS the record has."""
    out = collections.defaultdict(collections.Counter)
    for record in data.get('decisions', []):
        value = next((record[f] for f in OUTCOME_FIELDS if isinstance(record.get(f), str)), '-')
        out[record.get('kind') or '-'][value] += 1
    return {kind: dict(sorted(c.items())) for kind, c in sorted(out.items())}


def config_changes(data):
    out = collections.Counter((r.get('kind') or '-', r.get('op') or r.get('stage') or '-')
                              for r in data.get('config_changes', []))
    return [dict(kind=k, op=o, count=n) for (k, o), n in sorted(out.items())]


def rollup(data):
    """The compact daily numbers of the manifest and the daily summary: per role turns, success, tokens, useful,
    tokens per useful, denials, stops and loop-flagged turns; counts per stream kind."""
    roles = {}
    for row in measure(data):
        role = roles.setdefault(row['role'], _group())
        for name in _group():
            role[name] += row[name]
    flags = loops(data)['flags']
    for role, values in roles.items():
        values['tokens_per_useful'] = round(values['tokens'] / values['useful']) if values['useful'] else None
        values['loop_flags'] = sum(flags.get(role, {}).values())
    kinds = {stream: dict(sorted(collections.Counter(r.get('kind') or '-' for r in records).items()))
             for stream, records in sorted(data.items())}
    return {'roles': dict(sorted(roles.items())), 'kinds': kinds}


# ----------------------------------------------------------------------------------------------------------------------
# S700: quota points per million tokens (by model, by token kind) from the quota readings and the turns between them
# ----------------------------------------------------------------------------------------------------------------------
# Model: between two consecutive readings of one window (profile, quota category, limit window) with the same reset,
# the points consumed (earlier remaining percent - later remaining percent) are the sum over the turns charged in the
# interval of weight(model) x tokens / 1e6, plus reading noise (the percent is printed in whole points and was measured
# to move back by a point between readings). A turn is charged to the first reading at or after its time plus the
# reporting lag. Its time: a turn whose record follows an admission:after reading of its profile within `snap_seconds`
# (the S700 ledger: the profile lock holds one turn between its admission's before and after readings) is placed just
# before that reading, so lag 0 means "its own after-reading shows it"; any other turn keeps its record time (the turn
# ledger row and the Implementer receipt are written after the admission's after-reading). lag_seconds 'auto' takes,
# per series, the lag of the grid `lags` with the least residual. Estimates: non-negative least squares over the
# intervals (coordinate descent on the normal equations),
# a 90% percentile interval from a bootstrap over intervals, and a robust ratio (points / tokens over the intervals in
# which one model has at least `dominant_share` of the tokens). A weight is ESTIMABLE when the model has tokens in at
# least `min_intervals` intervals and the half-width of its 90% interval is at most `target_relative` of the estimate;
# otherwise the record states how much more data of the same mix would reach that precision (the variance of a
# least-squares estimate falls with the amount of data: factor = (half-width / (target x estimate))^2).
QUOTA = {
    'lag_seconds': 'auto',
    'lags': (-30, -15, 0, 15, 30, 60, 120, 300, 600),
    'snap_seconds': 120,
    'reset_tolerance_seconds': 5,
    'min_intervals': 8,
    'target_relative': 0.25,
    'bootstrap': 200,
    'seed': 700,
    'dominant_share': 0.8,
    'history_days': 14,
}
TOKEN_KINDS = ('fresh_input', 'cache_read', 'output', 'thinking')
USAGE_STREAMS = {'turns': 'TURN', 'deliveries': 'IMPLEMENTER_TURN'}


def _epoch(value):
    if not isinstance(value, str):
        return None
    try:
        moment = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None
    return moment.timestamp() if moment.tzinfo is not None else None


def _words(value):
    return [w for w in re.split(r'[^a-z0-9]+', str(value).lower()) if w]


def limit_window(label):
    """The window of a limit from its printed kind: weekly, five_hour, daily, <n>_hour, else the kind slug."""
    text = '_'.join(_words(label))
    if not text:
        return None
    if 'week' in text:
        return 'weekly'
    if re.search(r'(^|_)(five|5)_?h(our|r)?s?(_|$)', text):
        return 'five_hour'
    if re.search(r'(^|_)(day|daily)(_|$)', text):
        return 'daily'
    found = re.search(r'(^|_)(\d+)_?h(our|r)?s?(_|$)', text)
    return found.group(2) + '_hour' if found else text[:32]


def category_group(category, groups):
    """The quota group (config.json model_quota_groups values) a printed quota category stands for: the group every word
    of whose name is a word of the category, the one with the most words; None when there is none or a tie."""
    if not category or not isinstance(groups, dict):
        return None
    words = set(_words(category))
    found = sorted(((len(_words(g)), g) for g in set(groups.values()) if isinstance(g, str) and _words(g)
                    and set(_words(g)) <= words), reverse=True)
    if not found or (len(found) > 1 and found[0][0] == found[1][0]):
        return None
    return found[0][1]


def quota_groups(data):
    """model -> quota group from the newest POLICY snapshot (config.json model_quota_groups)."""
    policies = [r for r in data.get('snapshots', []) if r.get('kind') == 'POLICY' and isinstance(r.get('config'), dict)]
    for record in sorted(policies, key=lambda r: (r.get('ts') or '', r.get('record_id') or ''), reverse=True):
        groups = record['config'].get('model_quota_groups')
        if isinstance(groups, dict) and groups:
            return {k: v for k, v in groups.items() if isinstance(v, str)}
    return {}


def token_basis(data):
    """Per usage stream: whether cache_read is part of input and thinking part of output, read from the data itself (a
    stream in which any record has cache_read > input counts cache reads apart from input; the same for thinking)."""
    out = {}
    for stream, kind in USAGE_STREAMS.items():
        cache, thinking = {'records': 0, 'apart': 0}, {'records': 0, 'apart': 0}
        for record in data.get(stream, []):
            tokens = record.get('tokens') if record.get('kind') == kind else None
            if not isinstance(tokens, dict):
                continue
            if tokens.get('cache_read') and 'input' in tokens:
                cache['records'] += 1
                cache['apart'] += tokens['cache_read'] > tokens['input']
            if tokens.get('thinking') and 'output' in tokens:
                thinking['records'] += 1
                thinking['apart'] += tokens['thinking'] > tokens['output']
        out[stream] = {'cache_read_in_input': cache['apart'] == 0, 'cache_records': cache['records'], 'cache_apart': cache['apart'],
                       'thinking_in_output': thinking['apart'] == 0, 'thinking_records': thinking['records'],
                       'thinking_apart': thinking['apart']}
    return out


def usage_events(data, groups, basis=None):
    """[{t, profile, model, group, total, kinds, stream, role}] of every role turn and Implementer turn that spent tokens;
    group = model_quota_groups[model], an unmapped model being a group of its own."""
    basis = basis or token_basis(data)
    out = []
    for stream, kind in USAGE_STREAMS.items():
        rule = basis.get(stream) or {}
        for record in data.get(stream, []):
            tokens = record.get('tokens')
            if record.get('kind') != kind or not isinstance(tokens, dict) or not record.get('model') or not record.get('profile'):
                continue
            if stream == 'deliveries' and record.get('turn_started') is not True:
                continue
            t = _epoch(record.get('ts'))
            total = tokens.get('total') or 0
            if t is None or total <= 0:
                continue
            cache = tokens.get('cache_read') or 0
            thinking = tokens.get('thinking') or 0
            fresh = max((tokens.get('input') or 0) - (cache if rule.get('cache_read_in_input', True) else 0), 0)
            output = max((tokens.get('output') or 0) - (thinking if rule.get('thinking_in_output', True) else 0), 0)
            out.append({'t': t, 'profile': record['profile'], 'model': record['model'],
                        'group': groups.get(record['model'], record['model']), 'total': total, 'stream': stream,
                        'role': _subject(record, 'role'),
                        'kinds': {'fresh_input': fresh, 'cache_read': cache, 'output': output, 'thinking': thinking}})
    return sorted(out, key=lambda e: e['t'])


def quota_series(data, groups):
    """({(profile, category, group, window): [(t, remaining, reset)]}, {profile: [(t, reader)]}): one observation per
    time; a ledger row that states the previous value adds the observation of that value at its last reading. The
    second map lists every admission reading (before, after) per profile, for snap()."""
    series = collections.defaultdict(dict)
    admissions = collections.defaultdict(dict)
    for record in data.get('quota_readings', []):
        t = _epoch(record.get('ts'))
        if t is None or not record.get('profile'):
            continue
        seen = _epoch(record.get('previous_seen_ts'))
        for moment, reader in ((t, record.get('reader')), (seen, record.get('previous_seen_reader'))):
            if moment is not None and isinstance(reader, str) and reader.startswith('admission:'):
                admissions[record['profile']][round(moment, 3)] = (moment, reader)
        if record.get('kind') != 'QUOTA_READING' or not record.get('limit_category') or not record.get('limit_window'):
            continue
        value = record.get('remaining_percent')
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            continue
        group = record.get('group') or category_group(record['limit_category'], groups)
        key = (record['profile'], record['limit_category'], group, record['limit_window'])
        reset = _epoch(record.get('limit_reset_at'))
        series[key].setdefault(round(t, 3), (t, float(value), reset))
        before = record.get('previous_remaining_percent')
        if isinstance(before, (int, float)) and not isinstance(before, bool) and seen is not None and seen < t:
            previous_reset = _epoch(record.get('previous_reset_at')) if record.get('previous_reset_at') else reset
            series[key].setdefault(round(seen, 3), (seen, float(before), previous_reset))
    return ({key: sorted(points.values()) for key, points in series.items()},
            {profile: sorted(points.values()) for profile, points in admissions.items()})


def snap(events, admissions, seconds):
    """Place each turn whose record follows an admission:after reading of its profile (the newest admission reading
    before it, within `seconds`) just before that reading; one turn per reading. Returns the number placed."""
    placed = 0
    for profile, readings in admissions.items():
        times = [t for t, _reader in readings]
        used = set()
        for event in (e for e in events if e['profile'] == profile):
            index = bisect.bisect_right(times, event['t']) - 1
            if index < 0 or index in used:
                continue
            moment, reader = readings[index]
            if reader.startswith('admission:after') and event['t'] - moment <= seconds:
                event['t'] = moment - 0.001
                event['snapped'] = True
                used.add(index)
                placed += 1
    return placed


def _intervals(points, tolerance):
    """[(t0, t1, points consumed)] between consecutive observations with the same reset; the count of excluded pairs."""
    out, excluded = [], 0
    for (t0, v0, r0), (t1, v1, r1) in zip(points, points[1:]):
        if t1 <= t0:
            continue
        if (r0 is None) != (r1 is None) or (r0 is not None and abs(r0 - r1) > tolerance):
            excluded += 1
            continue
        out.append((t0, t1, v0 - v1))
    return out, excluded


def _assign(intervals, events, lag, column):
    """Per interval {column: tokens in millions} of the events whose end plus `lag` falls in it; unassigned tokens."""
    ends = [i[1] for i in intervals]
    rows = [collections.defaultdict(float) for _ in intervals]
    unassigned = 0
    for event in events:
        moment = event['t'] + lag
        index = bisect.bisect_left(ends, moment)
        if index < len(intervals) and intervals[index][0] < moment <= intervals[index][1]:
            for name, value in column(event).items():
                if value:
                    rows[index][name] += value / 1e6
        else:
            unassigned += event['total']
    return rows, unassigned


def nnls(rows, y, names, counts=None, sweeps=3000):
    """Non-negative least squares: argmin ||X w - y||^2, w >= 0, by coordinate descent on the normal equations. rows are
    sparse {name: x}; counts weight each row (the bootstrap). Returns ({name: w}, residual sum of squares)."""
    index = {name: i for i, name in enumerate(names)}
    k = len(names)
    h = [[0.0] * k for _ in range(k)]
    b = [0.0] * k
    for n, (row, value) in enumerate(zip(rows, y)):
        c = counts[n] if counts is not None else 1
        if not c:
            continue
        items = [(index[name], x) for name, x in row.items() if name in index]
        for i, x in items:
            b[i] += c * x * value
            for j, z in items:
                h[i][j] += c * x * z
    w = [0.0] * k
    for _ in range(sweeps):
        change = 0.0
        for j in range(k):
            if h[j][j] <= 0:
                continue
            gradient = sum(h[j][m] * w[m] for m in range(k)) - b[j]
            new = max(0.0, w[j] - gradient / h[j][j])
            change = max(change, abs(new - w[j]))
            w[j] = new
        if change <= 1e-12 * (1 + max(w, default=0.0)):
            break
    rss = sum((counts[n] if counts is not None else 1) * (value - sum(w[index[name]] * x for name, x in row.items() if name in index)) ** 2
              for n, (row, value) in enumerate(zip(rows, y)))
    # a column without data in these rows (a bootstrap sample that left out all its intervals) has no estimate
    return {name: (w[i] if h[i][i] > 0 else None) for name, i in index.items()}, rss


def _percentile(values, q):
    values = sorted(values)
    if not values:
        return None
    position = (len(values) - 1) * q
    low, high = math.floor(position), math.ceil(position)
    return values[low] + (values[high] - values[low]) * (position - low)


def _fit(rows, y, names, params, reference=None):
    """Point estimate, bootstrap 90% intervals and, with a reference column, the weights relative to it."""
    fit, rss = nnls(rows, y, names)
    rng = random.Random(params['seed'])
    samples, relative = collections.defaultdict(list), collections.defaultdict(list)
    n = len(rows)
    for _ in range(params['bootstrap'] if n >= 2 else 0):
        counts = [0] * n
        for _ in range(n):
            counts[rng.randrange(n)] += 1
        boot, _rss = nnls(rows, y, names, counts)
        for name in names:
            if boot[name] is None:
                continue
            samples[name].append(boot[name])
            if reference and (boot.get(reference) or 0) > 0:
                relative[name].append(boot[name] / boot[reference])
    out = {}
    for name in names:
        present = sum(1 for row in rows if row.get(name))
        low, high = _percentile(samples[name], 0.05), _percentile(samples[name], 0.95)
        entry = {'estimate': fit[name] or 0.0, 'ci90': [low, high], 'intervals': present, 'samples': len(samples[name])}
        if reference and (fit.get(reference) or 0) > 0:
            entry['relative'] = fit[name] / fit[reference]
            entry['relative_ci90'] = [_percentile(relative[name], 0.05), _percentile(relative[name], 0.95)]
        out[name] = entry
    dof = max(len(rows) - sum(1 for name in names if (fit[name] or 0) > 0), 1)
    return out, rss, math.sqrt(rss / dof)


def _verdict(entry, params):
    """ESTIMABLE or INSUFFICIENT, and the factor of more data (same mix) that would reach the target precision."""
    estimate, (low, high) = entry['estimate'], entry['ci90']
    half = (high - low) / 2 if low is not None and high is not None else None
    if entry['intervals'] == 0:
        return {'status': 'NO_DATA', 'needs_factor': None}
    if estimate <= 0 or half is None:
        return {'status': 'INSUFFICIENT', 'needs_factor': None, 'upper90': high}
    factor = max((half / (params['target_relative'] * estimate)) ** 2, params['min_intervals'] / entry['intervals'], 1.0)
    ok = entry['intervals'] >= params['min_intervals'] and half <= params['target_relative'] * estimate
    return {'status': 'ESTIMABLE' if ok else 'INSUFFICIENT', 'needs_factor': None if ok else round(factor, 1),
            'relative_half_width': round(half / estimate, 3)}


def _ratio(intervals, rows, names, share, params):
    """Robust ratio per column: points / millions of the column's tokens over the intervals it dominates."""
    out = {}
    for name in names:
        chosen = [(row[name], iv[2]) for iv, row in zip(intervals, rows)
                  if row.get(name) and row[name] >= share * sum(row.values())]
        if not chosen:
            out[name] = {'estimate': None, 'intervals': 0}
            continue
        tokens = sum(x for x, _ in chosen)
        rng = random.Random(params['seed'])
        boot = []
        for _ in range(params['bootstrap'] if len(chosen) >= 2 else 0):
            pick = [chosen[rng.randrange(len(chosen))] for _ in chosen]
            mass = sum(x for x, _ in pick)
            if mass > 0:
                boot.append(sum(v for _, v in pick) / mass)
        out[name] = {'estimate': sum(v for _, v in chosen) / tokens, 'intervals': len(chosen), 'tokens_m': round(tokens, 3),
                     'ci90': [_percentile(boot, 0.05), _percentile(boot, 0.95)]}
    return out


def _round(value, digits=3):
    if isinstance(value, float):
        return round(value, digits)
    if isinstance(value, list):
        return [_round(v, digits) for v in value]
    if isinstance(value, dict):
        return {k: _round(v, digits) for k, v in value.items()}
    return value


def quota_weights(data, groups=None, params=None):
    """S700: per (profile, quota category, group, window) the estimated quota points per million tokens per model and
    per token kind, with confidence, the lag sensitivity and the data still needed. See QUOTA for the method."""
    params = dict(QUOTA, **(params or {}))
    groups = groups if groups is not None else quota_groups(data)
    basis = token_basis(data)
    events = usage_events(data, groups, basis)
    series, admissions = quota_series(data, groups)
    out = {'parameters': {k: list(v) if isinstance(v, tuple) else v for k, v in params.items()}, 'token_basis': basis,
           'snapped_events': snap(events, admissions, params['snap_seconds']), 'events': len(events), 'series': []}
    for (profile, category, group, window), points in sorted(series.items(), key=lambda kv: tuple(str(x) for x in kv[0])):
        intervals, excluded = _intervals(points, params['reset_tolerance_seconds'])
        mine = [e for e in events if e['profile'] == profile and group is not None and e['group'] == group]
        entry = {'profile': profile, 'category': category, 'group': group, 'window': window, 'readings': len(points),
                 'intervals': len(intervals), 'excluded_intervals': excluded,
                 'span_h': round((points[-1][0] - points[0][0]) / 3600, 2) if points else 0,
                 'points': round(sum(i[2] for i in intervals), 3),
                 'first': _iso(points[0][0]) if points else None, 'last': _iso(points[-1][0]) if points else None}
        if group is None:
            entry['status'] = 'CATEGORY_UNMAPPED'
            out['series'].append(entry)
            continue
        y = [i[2] for i in intervals]
        lag_rss = {}
        for lag in params['lags']:
            rows, _ = _assign(intervals, mine, lag, lambda e: {e['model']: e['total']})
            lag_rss[str(lag)] = nnls(rows, y, sorted({n for r in rows for n in r}))[1]
        best = int(min(lag_rss, key=lambda k: (lag_rss[k], abs(int(k)))))
        lag = best if params['lag_seconds'] == 'auto' else float(params['lag_seconds'])
        entry.update(lag_rss=lag_rss, best_lag_seconds=best, lag_seconds=lag)
        by_model, unassigned = _assign(intervals, mine, lag, lambda e: {e['model']: e['total']})
        names = sorted({name for row in by_model for name in row})
        entry['tokens_m'] = round(sum(sum(row.values()) for row in by_model), 3)
        entry['unassigned_tokens_m'] = round(unassigned / 1e6, 3)
        if not names or len(intervals) < 2:
            entry['status'] = 'NO_TOKENS' if not names else 'TOO_FEW_INTERVALS'
            out['series'].append(entry)
            continue
        totals = {name: sum(row.get(name, 0) for row in by_model) for name in names}
        reference = max(names, key=lambda name: (totals[name], name))
        fitted, rss, sigma = _fit(by_model, y, names, params, reference)
        ratios = _ratio(intervals, by_model, names, params['dominant_share'], params)
        models = []
        for name in names:
            row = dict(model=name, tokens_m=round(totals[name], 3), **fitted[name], ratio=ratios[name])
            row.update(_verdict(fitted[name], params))
            row['needs_tokens_m'] = round(row['needs_factor'] * totals[name], 1) if row.get('needs_factor') else None
            models.append(row)
        pooled_tokens = sum(totals.values())
        entry.update(status='FITTED', reference_model=reference, residual_sigma=sigma, rss=rss,
                     pooled_points_per_mtok=entry['points'] / pooled_tokens if pooled_tokens else None, models=models)
        by_kind, _ = _assign(intervals, mine, lag, lambda e: e['kinds'])
        kinds = [k for k in TOKEN_KINDS if any(row.get(k) for row in by_kind)]
        if kinds:
            kind_fit, _rss, _sigma = _fit(by_kind, y, kinds, params)
            entry['kinds'] = [dict(kind=k, tokens_m=round(sum(row.get(k, 0) for row in by_kind), 3), **kind_fit[k],
                                   **_verdict(kind_fit[k], params)) for k in kinds]
        cells = [(m, k) for m in names for k in kinds]
        needed = 3 * len(cells)
        entry['model_kind'] = {'status': 'NOT_FITTED', 'columns': len(cells), 'intervals_needed': needed} if len(intervals) < needed else None
        if entry['model_kind'] is None:
            rows, _ = _assign(intervals, mine, lag, lambda e: {e['model'] + '/' + k: v for k, v in e['kinds'].items()})
            cell_names = sorted({n for r in rows for n in r})
            cell_fit, _rss, _sigma = _fit(rows, y, cell_names, params)
            entry['model_kind'] = {'status': 'FITTED', 'cells': [dict(cell=c, **cell_fit[c], **_verdict(cell_fit[c], params))
                                                                 for c in cell_names]}
        out['series'].append(_round(entry, 4))
    return out


def _iso(seconds):
    return dt.datetime.fromtimestamp(seconds, dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def weight_rows(result):
    """The flat routing-facing table: one row per fitted (profile, group, window, model)."""
    rows = []
    for series in result.get('series', []):
        for model in series.get('models') or []:
            rows.append({'profile': series['profile'], 'group': series['group'], 'window': series['window'],
                         'model': model['model'], 'points_per_mtok': model['estimate'], 'ci90': model['ci90'],
                         'relative': model.get('relative'), 'relative_ci90': model.get('relative_ci90'),
                         'reference_model': series['reference_model'], 'intervals': model['intervals'],
                         'tokens_m': model['tokens_m'], 'status': model['status'], 'needs_factor': model.get('needs_factor'),
                         'needs_tokens_m': model.get('needs_tokens_m'), 'ratio': model['ratio'].get('estimate'),
                         'lag_seconds': series['lag_seconds'], 'best_lag_seconds': series['best_lag_seconds']})
    return rows


def flow_report(data):
    """S702: the flow of work (stream `flow`, wip_policy's ledger): the latest daily metrics, the latest WIP view, the
    latest state of every unit, the start admissions per class and outcome, the conditions entered, the pilot's
    convergence routes and closes. The metrics follow the Kanban Guide's four flow measures (WIP, throughput, work item
    age, cycle time) plus flow efficiency and Little's Law (L = lambda W; its ratio and the stability check)."""
    rows = [r for r in data.get('flow') or [] if isinstance(r, dict)]
    by_kind = collections.defaultdict(list)
    for row in rows:
        by_kind[row.get('kind')].append(row)
    units = {}
    for row in by_kind['WIP_UNIT']:
        target = _subject(row, 'target')
        if target and (target not in units or (row.get('ts') or '') >= (units[target].get('ts') or '')):
            units[target] = row
    left = {_subject(r, 'target') for r in by_kind['WIP_TRANSITION'] if r.get('condition') == 'LEFT_WIP'}
    starts = collections.Counter('%s %s %s' % (r.get('op_class'), 'ADMITTED' if r.get('admitted') else 'REFUSED',
                                                r.get('reason')) for r in by_kind['WIP_START'])
    entered = collections.Counter(r.get('condition') for r in by_kind['WIP_TRANSITION'] if r.get('entered'))
    daily = by_kind['FLOW_DAILY'][-1] if by_kind['FLOW_DAILY'] else None
    snapshot = by_kind['WIP_SNAPSHOT'][-1] if by_kind['WIP_SNAPSHOT'] else None
    return {'daily': {'ts': daily.get('ts'), 'limit': daily.get('wip_limit'), 'metrics': daily.get('metrics') or {},
                      'tune': daily.get('tune_metrics') or {}} if daily else None,
            'snapshot': {k: snapshot.get(k) for k in ('ts', 'wip', 'wip_limit', 'over_limit', 'work_items_started',
                                                       'aged_units', 'hold_expired_units', 'stage_counts', 'trend_counts')}
            if snapshot else None,
            'units': [units[t] for t in sorted(units) if t not in left or (units[t].get('ts') or '') > max(
                (r.get('ts') or '' for r in by_kind['WIP_TRANSITION'] if _subject(r, 'target') == t
                 and r.get('condition') == 'LEFT_WIP'), default='')],
            'starts': dict(sorted(starts.items())), 'entered': dict(sorted(entered.items())),
            'routes': [{'target': _subject(r, 'target'), 'deadline': r.get('deadline_ts')} for r in by_kind['WIP_DECISION']],
            'closes': [{'target': _subject(r, 'target'), 'closed': r.get('closed'), 'reason': r.get('reason'),
                        'conditions': r.get('conditions')} for r in by_kind['WIP_CLOSE']]}


def _days(seconds):
    return '-' if not isinstance(seconds, (int, float)) else '%.1f d' % (seconds / 86400)


def delivery_lines(data):
    """S704: the daily summary's delivery paragraph from the day's latest DELIVERY_REGISTER ([] without one): Work Items
    per class, findings per kind, the CloseRecord measures (valid percent, target 100; orphaned follow-ups, target 0;
    close-to-successor latency)."""
    rows = sorted((r for r in (data or {}).get('delivery') or [] if isinstance(r, dict) and r.get('kind') ==
                   'DELIVERY_REGISTER'), key=lambda r: str(r.get('ts')))
    if not rows:
        return []
    last = rows[-1]
    m = last.get('delivery_metrics') or {}
    counts = ', '.join('%s %s' % (k.lower().replace('_', ' '), v) for k, v in sorted((last.get('class_counts') or {}).items()))
    found = ', '.join('%s %s' % kv for kv in sorted((last.get('finding_counts') or {}).items())) or 'none'
    closes = ', '.join('%s %s' % kv for kv in sorted((last.get('close_counts') or {}).items())) or 'none'
    return ['Delivery state (S704, register %s, %s): Work Items %s; findings %s.' % (
                last.get('register_digest'), last.get('register_status'), counts, found),
            'Closed without merge: %s (%s with a valid CloseRecord, %s%%, target 100; by class %s); orphaned follow-ups %s '
            '(target 0); close to successor p50 %s, max %s.' % (
                m.get('unmerged_closes'), m.get('valid_close_records'), m.get('valid_close_record_pct'), closes,
                m.get('orphaned_follow_ups'), _days(m.get('close_to_successor_p50_s')),
                _days(m.get('close_to_successor_max_s')))]


def owner_queue_lines(data):
    """S708: the daily summary's one line on the pending Owner decisions, from the day's latest OWNER_QUEUE record, only
    when N > 0 ([] otherwise): "Awaiting the Owner: N, oldest Xd" and the dashboard issue."""
    rows = sorted((r for r in (data or {}).get('delivery') or [] if isinstance(r, dict) and r.get('kind') ==
                   'OWNER_QUEUE'), key=lambda r: str(r.get('ts')))
    if not rows or not isinstance(rows[-1].get('owner_queue_n'), int) or rows[-1]['owner_queue_n'] <= 0:
        return []
    last = rows[-1]
    oldest = last.get('owner_queue_oldest_s')
    days = int(oldest // 86400) if isinstance(oldest, (int, float)) else None
    issue = (last.get('subject') or {}).get('issue')
    return ['Awaiting the Owner: %d, oldest %s%s.' % (last['owner_queue_n'], '<1d' if days == 0 else '%sd' % days
                                                       if days is not None else '-', (' (#%d)' % issue) if issue else '')]


def flow_lines(flow):
    """S702: the daily summary's flow paragraph and the report's section 8 (markdown lines, [] without flow data)."""
    if not flow or not (flow.get('daily') or flow.get('snapshot') or flow.get('units')):
        return []
    snap, daily = flow.get('snapshot') or {}, flow.get('daily') or {}
    m = daily.get('metrics') or {}
    lines = []
    if snap:
        lines.append('WIP (S702): %s open pull requests, limit %s for starting new work%s; %s Work Items started; %s aged, '
                     '%s holds expired.' % (snap.get('wip'), snap.get('wip_limit'),
                                            ' (%s over)' % snap['over_limit'] if snap.get('over_limit') else '',
                                            snap.get('work_items_started'), snap.get('aged_units') or 0,
                                            snap.get('hold_expired_units') or 0))
    if m:
        lines.append('Flow over %s days: throughput %s merged/day (%s merged, %s closed; %s days since the last merge); '
                     'cycle time p50 %s d, p85 %s d; open work age p50 %s d, p85 %s d, max %s d; flow efficiency %s '
                     '(waiting %s); Little\'s Law: average WIP %s vs throughput x cycle time %s (ratio %s, %s, %s: '
                     '%s arrivals, %s departures).' % (
                         m.get('window_days'), _fmt(m.get('throughput_merged_per_day')), m.get('merged'), m.get('closed'),
                         _fmt(m.get('days_since_merge'), 1), _fmt(m.get('cycle_days_p50')), _fmt(m.get('cycle_days_p85')),
                         _fmt(m.get('age_days_p50'), 1), _fmt(m.get('age_days_p85'), 1), _fmt(m.get('age_days_max'), 1),
                         _fmt(m.get('flow_efficiency'), 3), _fmt(m.get('waiting_share'), 3), _fmt(m.get('wip_avg')),
                         _fmt(m.get('littles_predicted_wip')), _fmt(m.get('littles_ratio')), m.get('littles_status'),
                         m.get('stability'), m.get('arrivals'), m.get('departures')))
    tune = daily.get('tune') or {}
    if tune.get('cycle_seconds_p85'):
        lines.append('Expectation from data: p85 cycle time of the %s pull requests merged in %s days is %s (the age '
                     'expectation the data supports: %s).' % (tune.get('merged'), tune.get('window_days'),
                                                             _days(tune.get('cycle_seconds_p85')),
                                                             _days(tune.get('age_expectation_seconds'))))
    if flow.get('starts'):
        lines.append('Start admissions: ' + ', '.join('%s %d' % kv for kv in flow['starts'].items()) + '.')
    aged = [u for u in flow.get('units') or [] if u.get('conditions')]
    if aged:
        lines.append('Aged or expired units: ' + '; '.join(
            '%s %s idle %s, %s (%s)' % (_subject(u, 'target'), u.get('unit_class'), _days(u.get('unit_idle_s')),
                                        '+'.join(u.get('conditions') or []), u.get('action'))
            for u in sorted(aged, key=lambda u: -(u.get('unit_idle_s') or 0))[:8]) + '.')
    if flow.get('closes') or flow.get('routes'):
        lines.append('Pilot decisions: %d convergence routes, %d closes (%d closed).' % (
            len(flow.get('routes') or []), len(flow.get('closes') or []),
            sum(1 for c in flow.get('closes') or [] if c.get('closed'))))
    return lines


def report(data, quota_params=None):
    return {'measure': measure(data), 'loops': loops(data), 'denials': denials_and_stops(data)[0],
            'stops': denials_and_stops(data)[1], 'deliveries': deliveries(data), 'decisions': decisions(data),
            'config_changes': config_changes(data), 'records': {s: len(r) for s, r in data.items()},
            'quota': quota_weights(data, params=quota_params), 'flow': flow_report(data)}


def _table(rows, columns):
    lines = ['| ' + ' | '.join(columns) + ' |', '|' + '---|' * len(columns)]
    for row in rows:
        lines.append('| ' + ' | '.join('-' if row.get(c) is None else str(row.get(c)) for c in columns) + ' |')
    return lines


def markdown(result, since=None, until=None):
    out = ['# Pilot telemetry report' + (' ' + (since or '...') + ' to ' + (until or '...') if since or until else ''), '',
           'Records: ' + ', '.join('%s %d' % kv for kv in sorted(result['records'].items())), '',
           '## 1. Tokens per useful result (role, model, effort)', '']
    out += _table(result['measure'], ['role', 'model', 'effort', 'turns', 'success', 'failed', 'tokens', 'failed_tokens',
                                      'useful', 'tokens_per_useful', 'success_rate'])
    out += ['', '## 2. Denials and stops', '']
    out += _table(result['measure'], ['role', 'model', 'effort', 'turns', 'denials', 'denial_rate', 'stops', 'stop_rate'])
    out += [''] + _table(result['denials'], ['role', 'program', 'shape', 'count'])
    out += [''] + _table(result['stops'], ['role', 'stop_class', 'stop_reason', 'count'])
    out += ['', '## 3. Loops', '']
    flags = [dict(role=role, flag=flag, turns=n) for role, c in result['loops']['flags'].items() for flag, n in c.items()]
    out += _table(flags, ['role', 'flag', 'turns'])
    out += ['', 'Inputs with %d or more role turns:' % LOOP_TURNS_PER_INPUT, '']
    out += _table([dict(role=r, input_key=k, turns=n) for r, k, n in result['loops']['inputs'][:30]], ['role', 'input_key', 'turns'])
    out += ['', '## 4. Deliveries', '']
    out += _table([dict(measure=m, value=v, count=n) for m, c in result['deliveries'].items() for v, n in c.items()],
                  ['measure', 'value', 'count'])
    out += ['', '## 5. Decision outcomes', '']
    out += _table([dict(kind=k, outcome=o, count=n) for k, c in result['decisions'].items() for o, n in c.items()],
                  ['kind', 'outcome', 'count'])
    out += ['', '## 6. Configuration changes', '']
    out += _table(result['config_changes'], ['kind', 'op', 'count'])
    out += quota_markdown(result.get('quota') or {})
    lines = flow_lines(result.get('flow'))
    if lines:
        out += ['', '## 8. Flow of work (S702)', ''] + lines
        units = (result.get('flow') or {}).get('units') or []
        if units:
            out += [''] + _table([{'unit': _subject(u, 'target'), 'class': u.get('unit_class'), 'stage': u.get('unit_stage'),
                                   'age': _days(u.get('unit_age_s')), 'idle': _days(u.get('unit_idle_s')),
                                   'progress': u.get('progress_kind'), 'trend': u.get('trend'), 'blocker': u.get('blocker'),
                                   'action': u.get('action')} for u in units],
                                 ['unit', 'class', 'stage', 'age', 'idle', 'progress', 'trend', 'blocker', 'action'])
    return '\n'.join(out) + '\n'


def _fmt(value, digits=2):
    return '-' if value is None else ('%.*f' % (digits, value) if isinstance(value, float) else str(value))


def quota_markdown(quota):
    params = quota.get('parameters') or {}
    out = ['', '## 7. Quota points per million tokens (S700)', '',
           'Lag %s (s); %s of %s turns placed at their own after-reading; a weight is ESTIMABLE with >= %s intervals and a'
           ' 90%% half-width <= %d%% of the estimate.'
           % (params.get('lag_seconds'), quota.get('snapped_events'), quota.get('events'), params.get('min_intervals'),
              round(100 * (params.get('target_relative') or 0))), '']
    for series in quota.get('series') or []:
        out.append('### %s / %s / %s (group %s): %s readings, %s intervals (%s excluded), %s points over %s h, status %s'
                   % (series['profile'], series['category'], series['window'], series.get('group') or '-', series['readings'],
                      series['intervals'], series['excluded_intervals'], _fmt(series['points'], 1), series['span_h'],
                      series.get('status')))
        if series.get('status') != 'FITTED':
            out.append('')
            continue
        out += ['', 'Pooled %s points per M tokens; residual sigma %s points; lag used %s s, best %s s (RSS per lag %s).'
                % (_fmt(series.get('pooled_points_per_mtok')), _fmt(series.get('residual_sigma')), series.get('lag_seconds'),
                   series.get('best_lag_seconds'),
                   ', '.join('%s: %s' % (k, _fmt(v, 1)) for k, v in (series.get('lag_rss') or {}).items())), '']
        rows = [dict(m, ci90='%s..%s' % (_fmt(m['ci90'][0]), _fmt(m['ci90'][1])), ratio=_fmt(m['ratio'].get('estimate')),
                     relative=_fmt(m.get('relative')), estimate=_fmt(m['estimate'])) for m in series['models']]
        out += _table(rows, ['model', 'tokens_m', 'intervals', 'estimate', 'ci90', 'ratio', 'relative', 'status',
                             'needs_factor', 'needs_tokens_m'])
        kinds = [dict(k, ci90='%s..%s' % (_fmt(k['ci90'][0]), _fmt(k['ci90'][1])), estimate=_fmt(k['estimate']))
                 for k in series.get('kinds') or []]
        if kinds:
            out += [''] + _table(kinds, ['kind', 'tokens_m', 'intervals', 'estimate', 'ci90', 'status', 'needs_factor'])
        cells = series.get('model_kind') or {}
        if cells.get('status') == 'NOT_FITTED':
            out += ['', 'Model x token kind: not fitted (%s columns need >= %s intervals).' % (cells['columns'], cells['intervals_needed'])]
        out.append('')
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description='Pilot telemetry analysis (schema v1)')
    parser.add_argument('--root', default=str(Path(__file__).resolve().parent.parent))
    parser.add_argument('--since')
    parser.add_argument('--until')
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--lag-seconds', default=QUOTA['lag_seconds'], help="S700 quota reporting lag: seconds or 'auto'")
    args = parser.parse_args(argv)
    lag = args.lag_seconds if args.lag_seconds == 'auto' else float(args.lag_seconds)
    result = report(load(args.root, args.since, args.until), quota_params={'lag_seconds': lag})
    if args.json:
        print(json.dumps(result, indent=1, sort_keys=True, default=list))
    else:
        sys.stdout.write(markdown(result, args.since, args.until))
    return 0


if __name__ == '__main__':
    sys.exit(main())
