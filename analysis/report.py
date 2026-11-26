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
6. configuration changes per kind and operation.

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
import collections
import json
from pathlib import Path
import sys

SCHEMA_VERSION = 1
STREAMS = ('turns', 'tool_events', 'decisions', 'deliveries', 'config_changes', 'snapshots', 'evaluations')
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


def report(data):
    return {'measure': measure(data), 'loops': loops(data), 'denials': denials_and_stops(data)[0],
            'stops': denials_and_stops(data)[1], 'deliveries': deliveries(data), 'decisions': decisions(data),
            'config_changes': config_changes(data), 'records': {s: len(r) for s, r in data.items()}}


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
    return '\n'.join(out) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description='Pilot telemetry analysis (schema v1)')
    parser.add_argument('--root', default=str(Path(__file__).resolve().parent.parent))
    parser.add_argument('--since')
    parser.add_argument('--until')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    result = report(load(args.root, args.since, args.until))
    if args.json:
        print(json.dumps(result, indent=1, sort_keys=True, default=list))
    else:
        sys.stdout.write(markdown(result, args.since, args.until))
    return 0


if __name__ == '__main__':
    sys.exit(main())
