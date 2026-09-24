"""VF0-E4 diagnostic only. No production admission, receipt or gate activation."""
import base64
import copy
import hashlib
import io
import json
import os
import re
import ssl
import stat
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

REPO = 'ktogias/gnostoa'
REPO_ID = 1317045725
RUN = 36029088664
WORKFLOW_ID = 366248218
SOURCE = 'ddd6a38b5bad2d6a5bd0794300684e8198889308'
SOURCE_SHA256 = '49bf2b3827303bc4f9fcea16935789147c446d2d359b2e5b65e0c609984df4fb'
WORKFLOW = '.github/workflows/vf0-publisher-probe.yml'
BRANCH = 'agent-support/vf0-publisher-20260924-1644'
API = 'https://api.github.com/repos/' + REPO
INPUT_SHA256 = hashlib.sha256(b'vf0-e4-no-input/v1\n').hexdigest()
MARKER = 'VF0_PUBLISHER_V1 '
KEYS = {'schema', 'repository_id', 'run_id', 'run_attempt', 'source_commit',
        'job_role', 'artifact_id', 'artifact_name', 'archive_sha256',
        'observation_sha256', 'input_sha256'}
PREFIX = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?Z (.*)$')


class Rejected(Exception):
    """Expected diagnostic rejection with a stable, value-free reason."""


def require(condition, code):
    if not condition:
        raise Rejected(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(document):
    return json.dumps(document, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode('ascii')


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'DUPLICATE_KEY')
            result[key] = value
        return result
    def constant(_):
        raise Rejected('NONFINITE_JSON')
    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, UnicodeError, RecursionError):
        raise Rejected('INVALID_JSON') from None


def positive_id(value):
    return type(value) is int and 0 < value < 10**20


def validate_source(raw):
    require(sha(raw) == SOURCE_SHA256, 'UNADMITTED_SOURCE')


def validate_run(run, attempt):
    require(positive_id(attempt), 'INVALID_ATTEMPT')
    for field, value in [('id', RUN), ('workflow_id', WORKFLOW_ID), ('run_attempt', attempt)]:
        require(type(run.get(field)) is int and run[field] == value, 'RUN_IDENTITY')
    require(run.get('head_sha') == SOURCE and run.get('path') == WORKFLOW and
            run.get('head_branch') == BRANCH and run.get('event') == 'push', 'RUN_SOURCE')
    for field in ('repository', 'head_repository'):
        require(type(run.get(field, {}).get('id')) is int and
                run[field]['id'] == REPO_ID, 'RUN_REPOSITORY')
    require(run.get('status') == 'completed' and run.get('conclusion') == 'success',
            'RUN_INCOMPLETE')


def select_job(document, attempt):
    jobs = document.get('jobs', [])
    require(type(document.get('total_count')) is int and
            document['total_count'] == len(jobs) and 1 <= len(jobs) <= 2,
            'JOB_COVERAGE')
    require(all(j.get('name') in ('VF0 closed publisher', 'Exact source transport only')
                for j in jobs), 'UNEXPECTED_JOB')
    matches = [j for j in jobs if j.get('name') == 'VF0 closed publisher']
    require(len(matches) == 1, 'PUBLISHER_COUNT')
    job = matches[0]
    require(positive_id(job.get('id')) and type(job.get('run_id')) is int and
            job['run_id'] == RUN and type(job.get('run_attempt')) is int and
            job['run_attempt'] == attempt and job.get('head_sha') == SOURCE,
            'PUBLISHER_IDENTITY')
    require(job.get('status') == 'completed' and job.get('conclusion') == 'success',
            'PUBLISHER_FAILED')
    steps = job.get('steps', [])
    require([s.get('name') for s in steps] == ['Set up job', 'Create fixed diagnostic observation',
            'Upload fixed diagnostic', 'Emit closed publication record', 'Complete job'],
            'PUBLISHER_STEPS')
    require(all(s.get('status') == 'completed' and s.get('conclusion') == 'success'
                for s in steps), 'PUBLISHER_STEP_FAILED')
    return job


def parse_record(logs, source, attempt):
    # A raw log or a caller-selected hash never supplies source admission.
    validate_source(source)
    require(0 < len(logs) <= 2 * 1024 * 1024, 'LOG_BOUND')
    try:
        lines = logs.decode('utf-8').splitlines()
    except UnicodeError:
        raise Rejected('LOG_ENCODING') from None
    records = []
    for line in lines:
        match = PREFIX.fullmatch(line)
        if match and match[1].startswith('VF0_PUBLISHER'):
            records.append(match[1])
    require(len(records) == 1, 'RECORD_COUNT')
    line = records[0]
    require(line.startswith(MARKER) and len(line) <= 4096, 'RECORD_FRAMING')
    body = line[len(MARKER):].encode('utf-8')
    record = strict_json(body)
    require(type(record) is dict and set(record) == KEYS, 'RECORD_KEYS')
    require(canonical(record) == body, 'NONCANONICAL_RECORD')
    require(record['schema'] == 'vf0-publisher-experiment/v1', 'RECORD_SCHEMA')
    for key in ('repository_id', 'run_id', 'run_attempt', 'artifact_id'):
        require(positive_id(record[key]), 'RECORD_ID_TYPE')
    require(record['repository_id'] == REPO_ID and record['run_id'] == RUN and
            record['run_attempt'] == attempt, 'RECORD_SUBJECT')
    require(record['source_commit'] == SOURCE and record['job_role'] == 'publisher',
            'RECORD_SOURCE_ROLE')
    for key in ('archive_sha256', 'observation_sha256', 'input_sha256'):
        require(type(record[key]) is str and re.fullmatch(r'[0-9a-f]{64}', record[key]),
                'RECORD_DIGEST')
    require(record['input_sha256'] == INPUT_SHA256, 'RECORD_INPUT')
    require(record['artifact_name'] == f'vf0-e4-{RUN}-{attempt}', 'RECORD_NAME')
    return record


def validate_artifact(item, record, now):
    require(type(item.get('id')) is int and item['id'] == record['artifact_id'] and
            item.get('name') == record['artifact_name'], 'ARTIFACT_IDENTITY')
    require(item.get('expired') is False, 'ARTIFACT_EXPIRED')
    try:
        expiry = datetime.fromisoformat(item['expires_at'].replace('Z', '+00:00'))
        require(expiry.tzinfo is not None and expiry > now, 'ARTIFACT_EXPIRED')
    except (KeyError, TypeError, ValueError, AttributeError):
        raise Rejected('ARTIFACT_EXPIRY') from None
    relation = item.get('workflow_run', {})
    for key, value in [('id', RUN), ('repository_id', REPO_ID), ('head_repository_id', REPO_ID)]:
        require(type(relation.get(key)) is int and relation[key] == value, 'ARTIFACT_RUN')
    require(relation.get('head_sha') == SOURCE and relation.get('head_branch') == BRANCH,
            'ARTIFACT_SOURCE')
    require(item.get('digest') == 'sha256:' + record['archive_sha256'], 'ARTIFACT_DIGEST')
    require(type(item.get('size_in_bytes')) is int and 0 < item['size_in_bytes'] <= 65536,
            'ARTIFACT_SIZE')


def read_observation(raw, item, record):
    require(0 < len(raw) <= 65536 and len(raw) == item['size_in_bytes'], 'ARCHIVE_SIZE')
    require(sha(raw) == record['archive_sha256'] and
            item['digest'] == 'sha256:' + sha(raw), 'ARCHIVE_DIGEST')
    # No archive parser may be reached until the complete-byte comparison above.
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            entries = archive.infolist()
            require(len(entries) == 1 and entries[0].filename == 'observation.json',
                    'ARCHIVE_MEMBERS')
            entry = entries[0]
            require(not entry.is_dir() and not stat.S_ISLNK(entry.external_attr >> 16) and
                    not entry.flag_bits & 1 and entry.compress_type in (0, 8) and
                    0 < entry.file_size <= 4096, 'ARCHIVE_MEMBER_TYPE_BOUND')
            with archive.open(entry) as stream:
                payload = stream.read(4097)
            require(len(payload) <= 4096, 'OBSERVATION_BOUND')
    except (zipfile.BadZipFile, RuntimeError, OSError, NotImplementedError):
        raise Rejected('ARCHIVE_INVALID') from None
    require(sha(payload) == record['observation_sha256'], 'OBSERVATION_DIGEST')
    observed = strict_json(payload)
    expected = dict(schema='vf0-observation-experiment/v1', repository_id=REPO_ID,
                    run_id=RUN, run_attempt=record['run_attempt'], source_commit=SOURCE,
                    input_sha256=INPUT_SHA256, production_producer_admitted=False)
    require(canonical(expected) + b'\n' == payload and observed == expected,
            'OBSERVATION_BINDING')
    return observed


def unchanged(before, after):
    require(before == after, 'ACQUISITION_DRIFT')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Client:
    """Read-only bounded provider transport; no credentials on signed handoffs."""
    def __init__(self):
        self.token = os.environ.pop('READ_TOKEN')
        require(self.token and all('!' <= c <= '~' for c in self.token), 'CREDENTIAL_FORMAT')
        self.deadline = time.monotonic() + 240
        context = ssl.create_default_context()
        require(context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED, 'TLS_REQUIRED')
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                      NoRedirect(), urllib.request.HTTPSHandler(context=context))

    def request(self, url, asset=False):
        try:
            parts = urllib.parse.urlsplit(url)
            valid = parts.scheme == 'https' and parts.hostname and parts.port in (None, 443)
            valid = valid and parts.username is None and parts.password is None and not parts.fragment
            valid = valid and all(33 <= ord(c) <= 126 for c in url)
        except ValueError:
            valid = False
        require(valid, 'UNSAFE_URL')
        headers = {'User-Agent': 'gnostoa-vf0-e4-experiment'}
        if asset:
            require(parts.hostname.endswith(('.blob.core.windows.net', '.actions.githubusercontent.com')),
                    'ASSET_HOST')
        else:
            require(parts.netloc == 'api.github.com' and url.startswith(API + '/'), 'API_ORIGIN')
            headers.update(Authorization='Bearer ' + self.token,
                           Accept='application/vnd.github+json', **{'X-GitHub-Api-Version': '2022-11-28'})
        req = urllib.request.Request(url, headers=headers, method='GET')
        require(not asset or req.get_header('Authorization') is None, 'CREDENTIAL_LEAK')
        return req

    def body(self, response, limit):
        data = bytearray()
        while True:
            require(time.monotonic() < self.deadline, 'DEADLINE')
            block = response.read(min(65536, limit + 1 - len(data)))
            if not block:
                return bytes(data)
            data.extend(block)
            require(len(data) <= limit, 'HTTP_BODY_BOUND')

    def json(self, path):
        with self.opener.open(self.request(API + path), timeout=20) as response:
            require(response.status == 200, 'METADATA_HTTP')
            return strict_json(self.body(response, 2 * 1024 * 1024))

    def download(self, path, limit):
        try:
            response = self.opener.open(self.request(API + path), timeout=20)
        except urllib.error.HTTPError as exc:
            require(exc.code == 302, 'EXPECTED_302')
            location = exc.headers.get('Location', '')
            exc.close()
        else:
            response.close()
            raise Rejected('EXPECTED_302')
        with self.opener.open(self.request(location, True), timeout=20) as response:
            require(response.status == 200, 'ASSET_HTTP')
            return self.body(response, limit)


def acquire(client, attempt, source, historical=False):
    latest_path = f'/actions/runs/{RUN}'
    latest = client.json(latest_path)
    if not historical:
        validate_run(latest, attempt)
    run_path = f'/actions/runs/{RUN}/attempts/{attempt}'
    run = client.json(run_path)
    validate_run(run, attempt)
    job_path = run_path + '/jobs?per_page=100'
    jobs = client.json(job_path)
    job = select_job(jobs, attempt)
    logs = client.download(f'/actions/jobs/{job["id"]}/logs', 2 * 1024 * 1024)
    record = parse_record(logs, source, attempt)
    artifact_path = f'/actions/artifacts/{record["artifact_id"]}'
    artifact = client.json(artifact_path)
    validate_artifact(artifact, record, datetime.now(timezone.utc))
    raw = client.download(artifact_path + '/zip', 65536)
    observed = read_observation(raw, artifact, record)
    # Compare independently reacquired identities; no fallback or automatic retry.
    latest_after = client.json(latest_path)
    if not historical:
        validate_run(latest_after, attempt)
    unchanged((latest['id'], latest['run_attempt'], latest['head_sha'], latest['status'], latest['conclusion']),
              (latest_after['id'], latest_after['run_attempt'], latest_after['head_sha'], latest_after['status'], latest_after['conclusion']))
    unchanged(job, select_job(client.json(job_path), attempt))
    artifact_after = client.json(artifact_path)
    validate_artifact(artifact_after, record, datetime.now(timezone.utc))
    unchanged(artifact, artifact_after)
    unchanged(logs, client.download(f'/actions/jobs/{job["id"]}/logs', 2 * 1024 * 1024))
    return dict(run=run, jobs=jobs, job=job, logs=logs, record=record, artifact=artifact,
                archive=raw, observation=observed)


def mutations(snapshot, source):
    results = []
    record, logs = snapshot['record'], snapshot['logs']
    attempt = record['run_attempt']
    def reject(name, fn, reason):
        try:
            fn()
        except Rejected as exc:
            require(str(exc) == reason, 'WRONG_REJECTION_' + name)
            results.append(dict(case=name, reason=reason))
        else:
            raise Rejected('FALSE_ACCEPT_' + name)
    def log_for(doc):
        return b'2026-09-24T00:00:00.0000000Z ' + MARKER.encode() + canonical(doc) + b'\n'
    def changed(doc, key, value):
        output = copy.deepcopy(doc)
        output[key] = value
        return output
    def parse(raw):
        return parse_record(raw, source, attempt)
    reject('missing_record', lambda: parse(b'not a record\n'), 'RECORD_COUNT')
    reject('duplicate_record', lambda: parse(log_for(record)*2), 'RECORD_COUNT')
    reject('conflicting_record', lambda: parse(log_for(record)+log_for(changed(record,'artifact_id',1))), 'RECORD_COUNT')
    reject('malformed_json', lambda: parse(log_for(record).replace(b'{', b'{oops', 1)), 'INVALID_JSON')
    reject('duplicate_key', lambda: parse(log_for(record).replace(b'{', b'{"schema":"x",', 1)), 'DUPLICATE_KEY')
    reject('noncanonical', lambda: parse(log_for(record).replace(b'{', b'{ ', 1)), 'NONCANONICAL_RECORD')
    reject('unknown_key', lambda: parse(log_for(changed(record,'trusted',True))), 'RECORD_KEYS')
    reject('wrong_schema', lambda: parse(log_for(changed(record,'schema','other/v1'))), 'RECORD_SCHEMA')
    reject('boolean_id', lambda: parse(log_for(changed(record,'run_attempt',True))), 'RECORD_ID_TYPE')
    for key in ('repository_id','run_id','run_attempt'):
        reject('wrong_'+key, lambda k=key: parse(log_for(changed(record,k,1))), 'RECORD_SUBJECT')
    for key, value in [('source_commit','0'*40),('job_role','untrusted_test')]:
        reject('wrong_'+key, lambda k=key,v=value: parse(log_for(changed(record,k,v))), 'RECORD_SOURCE_ROLE')
    reject('bad_digest', lambda: parse(log_for(changed(record,'archive_sha256','bad'))), 'RECORD_DIGEST')
    reject('wrong_input', lambda: parse(log_for(changed(record,'input_sha256','0'*64))), 'RECORD_INPUT')
    reject('wrong_record_name', lambda: parse(log_for(changed(record,'artifact_name','other'))), 'RECORD_NAME')
    reject('unadmitted_source', lambda: parse_record(logs,source+b'\n',attempt), 'UNADMITTED_SOURCE')
    reject('untrusted_log_origin', lambda: parse_record(log_for(record),b'candidate prints matching record',attempt), 'UNADMITTED_SOURCE')
    reject('oversized_logs', lambda: parse(b'x'*(2*1024*1024+1)), 'LOG_BOUND')
    reject('stale_attempt', lambda: validate_run(snapshot['run'],attempt-1), 'RUN_IDENTITY')
    reject('attempt_moved', lambda: validate_run(changed(snapshot['run'],'run_attempt',attempt+1),attempt), 'RUN_IDENTITY')
    reject('incomplete_run', lambda: validate_run(changed(snapshot['run'],'status','in_progress'),attempt), 'RUN_INCOMPLETE')
    reject('incomplete_jobs', lambda: select_job(changed(snapshot['jobs'],'total_count',10),attempt), 'JOB_COVERAGE')
    broken = copy.deepcopy(snapshot['jobs'])
    for job in broken['jobs']:
        if job['name'] == 'VF0 closed publisher':
            job['conclusion'] = 'failure'
    reject('failed_publisher', lambda: select_job(broken,attempt), 'PUBLISHER_FAILED')
    now = datetime.now(timezone.utc)
    for key,value,reason in [('id',1,'ARTIFACT_IDENTITY'),('name','other','ARTIFACT_IDENTITY'),
                             ('digest','sha256:'+'0'*64,'ARTIFACT_DIGEST'),('expired',True,'ARTIFACT_EXPIRED'),
                             ('expires_at','2000-01-01T00:00:00Z','ARTIFACT_EXPIRED')]:
        reject('artifact_'+key,lambda k=key,v=value: validate_artifact(changed(snapshot['artifact'],k,v),record,now),reason)
    reject('artifact_drift', lambda: unchanged(snapshot['artifact'],changed(snapshot['artifact'],'id',1)), 'ACQUISITION_DRIFT')
    reject('wrong_observation_digest', lambda: read_observation(snapshot['archive'],snapshot['artifact'],
                    changed(record,'observation_sha256','0'*64)), 'OBSERVATION_DIGEST')
    raw = snapshot['archive']
    with patch.object(zipfile,'ZipFile',side_effect=AssertionError('ZIP_BEFORE_DIGEST')):
        reject('tampered_before_zip',lambda: read_observation(raw[:-1]+bytes([raw[-1]^1]),snapshot['artifact'],record), 'ARCHIVE_DIGEST')
    return results


def main():
    output = Path(sys.argv[1])
    output.mkdir(parents=True, exist_ok=False)
    client = Client()
    doc = client.json('/contents/'+WORKFLOW+'?ref='+SOURCE)
    require(doc.get('encoding') == 'base64' and doc.get('path') == WORKFLOW, 'SOURCE_METADATA')
    source = base64.b64decode(''.join(doc['content'].split()), validate=True)
    blob = hashlib.sha1(b'blob '+str(len(source)).encode()+b'\0'+source).hexdigest()
    require(blob == doc.get('sha'), 'SOURCE_GIT_BLOB')
    validate_source(source)
    current = acquire(client, 2, source)
    historical = acquire(client, 1, source, historical=True)
    controls = mutations(current, source)
    # These genuine cross-attempt substitutions must fail independently of archive payload assertions.
    for old, attempt in [(historical,2),(current,1)]:
        try:
            parse_record(old['logs'], source, attempt)
        except Rejected as exc:
            require(str(exc) == 'RECORD_SUBJECT','WRONG_CROSS_ATTEMPT_REASON')
            controls.append(dict(case=f'actual_attempt_{old["record"]["run_attempt"]}_as_{attempt}',reason=str(exc)))
        else:
            raise Rejected('CROSS_ATTEMPT_ACCEPTED')
    validate_run(client.json(f'/actions/runs/{RUN}'),2)
    result = dict(schema='vf0-e4-result/v1', status='PASS', scope='EXPERIMENT_ONLY',
                  current_attempt=2, historical_attempt=1, historical_is_current_compliance=False,
                  source_sha256=sha(source), producer_source=SOURCE,
                  producer_run=RUN, production_producer_admitted=False,
                  admission_acquisition_implemented=False, vf0_gate_implemented=False,
                  controls=controls, controls_count=len(controls), observations=[])
    (output/'publisher.yml').write_bytes(source)
    for snapshot in (historical,current):
        attempt = snapshot['record']['run_attempt']
        prefix = output/f'attempt-{attempt}'
        prefix.with_suffix('.log').write_bytes(snapshot['logs'])
        prefix.with_suffix('.zip').write_bytes(snapshot['archive'])
        metadata = {k:v for k,v in snapshot.items() if k not in ('logs','archive')}
        prefix.with_suffix('.json').write_bytes(canonical(metadata)+b'\n')
        result['observations'].append(dict(attempt=attempt,job_id=snapshot['job']['id'],
                     artifact_id=snapshot['artifact']['id'],archive_sha256=sha(snapshot['archive']),
                     logs_sha256=sha(snapshot['logs']),record=snapshot['record']))
    (output/'consumer.py').write_bytes(Path(__file__).read_bytes())
    (output/'result.json').write_bytes(canonical(result)+b'\n')
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Never print transport exceptions, signed URLs or credential values.
        print('VF0_E4_REJECT '+(str(exc) if isinstance(exc,Rejected) else type(exc).__name__))
        sys.exit(1)
