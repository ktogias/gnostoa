"""A8 fixed-source composition diagnostic; not a production admission adapter."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shutil
import ssl
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone

REPO = 'ktogias/gnostoa'
REPO_ID = 1317045725
SUBJECT = 'd695af8bbf67828cd87868ccf972ecd5c37e6405'
TREE = '47ad47143c8d6493c4a7cd8f0e32442efb3b9d3e'
MAIN = '63fb3e7bf7a929c755250e6112f5a43a2b3db5c7'
BRANCH = 'agent-support/vf0-admission-a6-20260924'
WORKFLOW = '.github/workflows/vf0-a8-composition.yml'
E5_REV = 'eb05bf43a9b8bdfc994287eeaf095597178e402f'
E5_SHA = '72df2689f653eb4e0f195eec1e9402403ae468d4621df743818d7dd6e258114c'
IMAGE = 'python:3.12-slim@sha256:2c941e860699f878900b0edc2403613c234d4b32eda3cc9fa7036991a2a63c4a'
ENV_ID = 22685212653
OWNER = 532328
PROBE_PATH = 'tests/vf0_a8_probe.py'
PROBE = b'''"""Fixed A8 characterization; no production admission."""
import copy
import sys
sys.path.insert(0, '/workspace')
from tools.vf0_contract import evaluate
from tests.test_vf0_contract import _fixture
value = _fixture()
result = evaluate(value)
if not (result['status'] == 'MATCH' and result['authentication'] == 'NOT_ESTABLISHED'
        and result['compliance'] is False and result['vf0_active'] is False):
    raise AssertionError('A8_NO_AUTHORITY')
missing = copy.deepcopy(value)
missing['candidate']['changed_paths'] = ['tools/target.py']
if evaluate(missing)['reasons'] != ['CANDIDATE_EVIDENCE_DELTA_MISSING']:
    raise AssertionError('A8_EVIDENCE_DELTA')
foreign = copy.deepcopy(value)
foreign['evidence']['execution']['instance'] = 'foreign-instance'
if evaluate(foreign)['reasons'] != ['EXECUTION_NAMESPACE']:
    raise AssertionError('A8_NAMESPACE')
print('VF0_A8_CHARACTERIZATION_OK')
'''
MARKER = 'VF0_A8_PUBLICATION '
SAFE_ENV = {'PATH': '/usr/local/bin:/usr/bin:/bin', 'HOME': '/tmp',
            'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null',
            'GIT_NO_REPLACE_OBJECTS': '1', 'PYTHONDONTWRITEBYTECODE': '1'}
GUARANTEES = ['request_binding', 'record_coverage', 'attempt_identity', 'latest_attempt',
              'source_revalidation', 'protection_revalidation', 'credential_separation']


class Rejected(Exception):
    """Static reason only; never provider content or secrets."""


def need(condition, reason):
    if not condition:
        raise Rejected(reason)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False).encode('ascii')


def digest(value):
    return 'sha256:' + sha(canonical(value))


def strict(raw):
    need(type(raw) is bytes and len(raw) <= 2_000_000, 'JSON_BOUND')
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'DUPLICATE_JSON_KEY')
            result[key] = value
        return result
    def constant(_):
        raise Rejected('NONFINITE_JSON')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


def identifier(value):
    need(type(value) is str and re.fullmatch(r'[1-9][0-9]{0,19}', value), 'ID')
    return int(value)


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    need(parsed.tzinfo is not None, 'TIMEZONE')
    return int(parsed.timestamp())


def command(argv, cwd=None, data=None, env=None, timeout=30):
    result = subprocess.run(argv, cwd=cwd, env=env or SAFE_ENV, input=data,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            timeout=timeout, check=False)
    need(result.returncode == 0 and len(result.stdout) <= 32_000_000, 'COMMAND_FAILED')
    return result.stdout


def git(root, *args, data=None, env=None):
    return command(['/usr/bin/git', '-c', 'core.hooksPath=/dev/null', '-C', str(root), *args],
                   data=data, env=env)


def source_pins(root):
    subject, dependency = root/'subject', root/'e5'
    need(git(subject, 'rev-parse', 'HEAD').decode().strip() == SUBJECT, 'SUBJECT_HEAD')
    need(git(subject, 'rev-parse', 'HEAD^{tree}').decode().strip() == TREE, 'SUBJECT_TREE')
    need(not git(subject, 'status', '--porcelain'), 'DIRTY_SUBJECT')
    need(git(dependency, 'rev-parse', 'HEAD').decode().strip() == E5_REV, 'E5_HEAD')
    e5 = dependency/'.github/vf0-isolation-probe.py'
    need(sha(e5.read_bytes()) == E5_SHA, 'E5_SOURCE')
    need(IMAGE in (subject/'Dockerfile').read_text(), 'RUNTIME_PIN')
    core = subject/'tools/vf0_contract.py'
    return {'subject': SUBJECT, 'subject_tree': TREE, 'main': MAIN,
            'core_sha256': sha(core.read_bytes()), 'e5_revision': E5_REV,
            'e5_sha256': E5_SHA, 'coordinator_sha256': sha(Path(__file__).read_bytes()),
            'workflow_sha256': sha((root/'coordinator'/WORKFLOW).read_bytes()),
            'runtime': IMAGE, 'probe_sha256': sha(PROBE)}


def evidence_tree(subject):
    # A planned evidence subject is not a prepared/published candidate.
    with tempfile.TemporaryDirectory(prefix='vf0-a8-index-') as tmp:
        env = dict(SAFE_ENV, GIT_INDEX_FILE=str(Path(tmp)/'index'))
        git(subject, 'read-tree', SUBJECT, env=env)
        oid = git(subject, 'hash-object', '-w', '--stdin', data=PROBE).decode().strip()
        git(subject, 'update-index', '--add', '--cacheinfo', '100644', oid, PROBE_PATH, env=env)
        tree = git(subject, 'write-tree', env=env).decode().strip()
        patch = git(subject, 'diff', '--binary', '--full-index', SUBJECT, tree, '--', PROBE_PATH)
        production = sha(git(subject, 'ls-tree', '-rz', SUBJECT))
        return tree, patch, production


def protection(environment, branches):
    need(type(environment.get('id')) is int and environment['id'] == ENV_ID and
         environment.get('name') == 'vf0-admission', 'ENVIRONMENT_ID')
    need(environment.get('can_admins_bypass') is False, 'BYPASS')
    need(environment.get('deployment_branch_policy') ==
         {'protected_branches': False, 'custom_branch_policies': True}, 'BRANCH_POLICY')
    rules = environment.get('protection_rules', [])
    need(len(rules) == 2 and {x.get('type') for x in rules} ==
         {'required_reviewers', 'branch_policy'}, 'PROTECTION_SET')
    reviewers = next(x for x in rules if x['type'] == 'required_reviewers')
    need(reviewers.get('prevent_self_review') is False, 'SELF_REVIEW_SETTING')
    actors = reviewers.get('reviewers', [])
    need(len(actors) == 1 and actors[0].get('type') == 'User' and
         actors[0].get('reviewer', {}).get('id') == OWNER, 'REVIEWER')
    listed = branches.get('branch_policies', [])
    need(type(branches.get('total_count')) is int and branches['total_count'] == 1 and
         len(listed) == 1 and listed[0].get('name') == BRANCH and
         listed[0].get('type') == 'branch', 'BRANCH_COVERAGE')
    return {'environment_id': ENV_ID, 'reviewer_id': OWNER, 'admin_bypass': False,
            'prevent_self_review': False, 'branch': BRANCH,
            'rule_ids': sorted(x['id'] for x in rules), 'branch_rule_id': listed[0]['id']}


def ref(run, opaque):
    return {'provider': 'github', 'instance': 'github.com', 'repository': str(REPO_ID),
            'opaque_id': f'a8:{run}:{opaque}'}


def build_manifest(run, pins, protected, tree, patch, production):
    rid = run['id']
    created = timestamp(run['created_at'])
    d = 'sha256:' + sha(PROBE)
    cases = [{'id': key, 'result': 'PASS', 'cause': 'NONE'} for key in
             ('no-authority', 'retained-delta', 'namespace')]
    policy = {'id': 'a8-diagnostic-fixture-not-effective-policy',
              'modes': {k: ['CHARACTERIZATION'] for k in
                        ('mechanical', 'normal', 'normative', 'critical', 'emergency')},
              'required_guarantees': sorted(GUARANTEES), 'max_age_seconds': 3600}
    request = {'identity': ref(rid, 'request'), 'work_item': ref(rid, 'work-item-15'),
               'decision': ref(rid, 'diagnostic-scope'), 'policy_sha256': digest(policy),
               'change_class': 'normal', 'mode': 'CHARACTERIZATION', 'criterion': 'EXECUTABLE',
               'candidate_paths': [PROBE_PATH], 'material': {
                   'parent_commit': SUBJECT, 'parent_tree': TREE, 'evidence_tree': tree,
                   'evidence_patch_sha256': 'sha256:'+sha(patch),
                   'production_sha256': 'sha256:'+production,
                   'command_sha256': digest(['/usr/local/bin/python3', '-I', '/workspace/'+PROBE_PATH,
                                            'characterize', '<controller-owned-private-path>']),
                   'oracle_sha256': digest(cases), 'evidence_files': {PROBE_PATH: d}},
               'outcome': {'exit_code': 0, 'cases': cases}, 'valid_from': created,
               'valid_until': created+86400, 'follow_up': None}
    return {'schema': 'vf0-a8-request/v1', 'effect': 'COMPOSE_DIAGNOSTIC_ONLY',
            'run_id': rid, 'attempt': 1, 'coordinator_revision': run['head_sha'],
            'pins': pins, 'protection': protected, 'request': request, 'fixture_policy': policy,
            'guarantee_labels_are_diagnostic_assumptions': True,
            'production_admission': False, 'vf0_active': False,
            'runtime_limits': {'seconds': 5, 'output_bytes': 65536, 'memory_bytes': 268435456,
                               'cpu': '0.5', 'pids': 32, 'network': 'none', 'rootfs': 'read-only'},
            'expires_at': datetime.fromtimestamp(created+86400, timezone.utc).isoformat()}


def approve_text(manifest):
    return f'VF0-A8 approve run={manifest["run_id"]} attempt=1 manifest-sha256={sha(canonical(manifest))}'


def approved(history, manifest, now):
    need(type(history) is list and len(history) == 1, 'APPROVAL_COVERAGE')
    record = history[0]
    need(record.get('state') == 'approved' and record.get('comment') == approve_text(manifest),
         'APPROVAL_BINDING')
    actor, targets = record.get('user', {}), record.get('environments', [])
    need(type(actor.get('id')) is int and actor['id'] == OWNER and actor.get('type') == 'User', 'APPROVER')
    need(len(targets) == 1 and type(targets[0].get('id')) is int and
         targets[0]['id'] == ENV_ID, 'APPROVAL_ENVIRONMENT')
    need(manifest['request']['valid_from'] <= now < manifest['request']['valid_until'], 'EXPIRED_REQUEST')
    return record


def run_identity(run, rid, revision):
    need(type(run.get('id')) is int and run['id'] == rid and
         type(run.get('run_attempt')) is int and run['run_attempt'] == 1, 'RUN_ATTEMPT')
    need(run.get('head_sha') == revision and run.get('head_branch') == BRANCH and
         run.get('path') == WORKFLOW and run.get('event') == 'push', 'RUN_SOURCE')
    for field in ('repository', 'head_repository'):
        need(run.get(field, {}).get('id') == REPO_ID, 'REPOSITORY')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Reader:
    def __init__(self, rid):
        self.rid = rid
        self.token = os.environ.pop('A8_READ_TOKEN')
        need(self.token and all('!' <= c <= '~' for c in self.token), 'TOKEN_FORMAT')
        self.deadline = time.monotonic()+300
        context = ssl.create_default_context()
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect(),
                      urllib.request.HTTPSHandler(context=context))

    def request(self, path):
        fixed = {'/pulls/319', '/git/ref/heads/main', '/environments/vf0-admission',
                 '/environments/vf0-admission/deployment-branch-policies?per_page=100',
                 f'/actions/runs/{self.rid}', f'/actions/runs/{self.rid}/approvals',
                 f'/actions/runs/{self.rid}/attempts/1/jobs?per_page=100'}
        need(path in fixed or re.fullmatch(r'/actions/(?:artifacts/[1-9][0-9]*(?:/zip)?|jobs/[1-9][0-9]*/logs)', path),
             'UNDECLARED_ENDPOINT')
        need(time.monotonic() < self.deadline, 'DEADLINE')
        return urllib.request.Request('https://api.github.com/repos/'+REPO+path, method='GET', headers={
            'Authorization': 'Bearer '+self.token, 'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'vf0-a8-fixed-diagnostic'})

    def get(self, path):
        with self.opener.open(self.request(path), timeout=20) as response:
            need(response.status == 200 and response.headers.get('Link') is None, 'METADATA_COVERAGE')
            return strict(response.read(2_000_001))

    def download(self, path):
        try:
            response = self.opener.open(self.request(path), timeout=20)
        except urllib.error.HTTPError as exc:
            need(exc.code == 302, 'DOWNLOAD_REDIRECT')
            url = exc.headers.get('Location', '')
            exc.close()
        else:
            response.close()
            raise Rejected('DOWNLOAD_REDIRECT')
        parts = urllib.parse.urlsplit(url)
        need(parts.scheme == 'https' and parts.hostname and not parts.username and not parts.password
             and not parts.fragment and parts.port in (None,443) and '\\' not in url
             and all(32 < ord(c) < 127 for c in url), 'ASSET_URL')
        need(parts.hostname.endswith(('.blob.core.windows.net', '.actions.githubusercontent.com')), 'ASSET_ORIGIN')
        # Fresh request, no API credential on the signed handoff.
        with self.opener.open(urllib.request.Request(url, method='GET'), timeout=20) as response:
            need(response.status == 200, 'DOWNLOAD_HTTP')
            raw = response.read(2_000_001)
        need(len(raw) <= 2_000_000, 'DOWNLOAD_BOUND')
        return raw


def observe(reader, revision):
    run = reader.get(f'/actions/runs/{reader.rid}')
    run_identity(run, reader.rid, revision)
    pr = reader.get('/pulls/319')
    need(pr['head']['sha'] == SUBJECT and pr['state'] == 'open' and pr['draft'] is True, 'PR_MOVED')
    main = reader.get('/git/ref/heads/main')
    need(main['object']['sha'] == MAIN, 'MAIN_MOVED')
    environment = reader.get('/environments/vf0-admission')
    branches = reader.get('/environments/vf0-admission/deployment-branch-policies?per_page=100')
    view = protection(environment, branches)
    history = reader.get(f'/actions/runs/{reader.rid}/approvals')
    return {'run': run, 'protection': view, 'environment': environment,
            'branches': branches, 'approvals': history}


def load_source(path, expected, name):
    need(sha(path.read_bytes()) == expected, 'PINNED_SOURCE')
    spec = importlib.util.spec_from_file_location(name, path)
    need(spec and spec.loader, 'SOURCE_LOADER')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path, value):
    path.write_bytes(canonical(value))


def capture(root, out, manifest, before, reader):
    approved(before['approvals'], manifest, int(time.time()))
    admitted_at = int(time.time())
    e5 = load_source(root/'e5/.github/vf0-isolation-probe.py', E5_SHA, 'a8_pinned_e5')
    try:
        _capture_with_e5(root, out, manifest, before, reader, e5, admitted_at)
    except e5.Rejected as exc:
        # The separately loaded pinned dependency has its own rejection class.
        # Only static known codes cross the log boundary; never copy raw output.
        known = {
            'SUBJECT_BINDING', 'SUBJECT_BYTES_OR_MODE', 'SYMLINK_REJECTED',
            'SPECIAL_FILE_REJECTED', 'UNDECLARED_PATH', 'TRUSTED_COMMAND_FAILED',
            'PARENT_HEAD', 'PARENT_TREE', 'PARENT_DIRTY', 'PARENT_FILE_TYPE',
            'PARENT_ARCHIVE_BOUND', 'ARCHIVE_PATH', 'ARCHIVE_MEMBER',
            'PARENT_MEMBER_BOUND', 'PARENT_MEMBER_UNAVAILABLE', 'PARENT_BLOB_MISMATCH',
            'PARENT_PATH_SET', 'CONTAINER_ID', 'MOUNT_CONTRACT', 'OCI_CONTRACT',
            'CONTAINER_STILL_RUNNING', 'ATTACHMENT_REAP_TIMEOUT',
            'CONTAINER_REMOVAL_TIMEOUT', 'CONTAINER_ABSENCE_CHECK_TIMEOUT',
            'CLEANUP_UNVERIFIED',
        }
        code = str(exc) if str(exc) in known else 'REJECTED'
        reason = 'E5_' + code
        write_json(out/'failure.json', {'schema': 'vf0-a8-capture-failure/v1',
            'reason': reason, 'manifest_sha256': sha(canonical(manifest)),
            'production_producer_admitted': False, 'vf0_active': False})
        raise Rejected(reason) from None


def _capture_with_e5(root, out, manifest, before, reader, e5, admitted_at):
    e5.PARENT, e5.TREE, e5.EVIDENCE_PATH, e5.EVIDENCE = SUBJECT, TREE, PROBE_PATH, PROBE
    e5.docker('pull', IMAGE, timeout=120)
    image = strict(e5.docker('image', 'inspect', IMAGE))[0]
    need(any(v.endswith('@'+IMAGE.split('@')[1]) for v in image.get('RepoDigests', [])), 'IMAGE_DIGEST')
    with tempfile.TemporaryDirectory(prefix='vf0-a8-') as tmp:
        work = Path(tmp)
        work.chmod(0o755)
        private = work/'private'
        private.mkdir(mode=0o700)
        canary = os.urandom(32)
        (private/'canary').write_bytes(canary)
        snapshot = work/'evidence-subject'
        baseline = e5.snapshot(root/'subject', snapshot)
        (snapshot/PROBE_PATH).write_bytes(PROBE)
        e5.validate_snapshot(snapshot, baseline, parent=SUBJECT, tree=TREE)
        started = int(time.time())
        outcome = e5.exercise(image['Id'], snapshot, private, 'characterize', out)
        completed = int(time.time())
        need(outcome['termination'] == 'completed' and outcome['container_exit_code'] == 0, 'CHARACTERIZATION_OUTCOME')
        need((out/'characterize.untrusted.stdout').read_bytes() == b'VF0_A8_CHARACTERIZATION_OK\n'
             and (out/'characterize.untrusted.stderr').read_bytes() == b'', 'FIXED_ORACLE')
        e5.validate_snapshot(snapshot, baseline, parent=SUBJECT, tree=TREE)
        need((private/'canary').read_bytes() == canary, 'CANARY_CHANGED')
        # This actual candidate materialization occurs only after observation.
        candidate = work/'synthetic-candidate'
        shutil.copytree(snapshot, candidate)
        e5.validate_snapshot(candidate, baseline, parent=SUBJECT, tree=TREE)
        candidate_at = int(time.time())
        tree, patch, production = evidence_tree(root/'subject')
        need(tree == manifest['request']['material']['evidence_tree'] and
             'sha256:'+production == manifest['request']['material']['production_sha256'], 'MATERIAL_DRIFT')
        (out/'synthetic-candidate.patch').write_bytes(patch)
        write_json(out/'parent-manifest.json', baseline)
    after = observe(reader, manifest['coordinator_revision'])
    approved(after['approvals'], manifest, int(time.time()))
    need(before['protection'] == after['protection'] and before['approvals'] == after['approvals'], 'ACQUISITION_DRIFT')
    write_json(out/'capture.json', {'manifest': manifest, 'before': before, 'after': after,
        'admission_observed_at': admitted_at, 'started_at': started, 'completed_at': completed,
        'candidate_at': candidate_at, 'outcome': outcome, 'candidate_tree': tree,
        'parent_and_evidence_unchanged': True, 'synthetic_candidate_published': False,
        'production_producer_admitted': False, 'vf0_active': False})


def publication(manifest):
    aid = identifier(os.environ['A8_ARTIFACT_ID'])
    archive = os.environ['A8_ARTIFACT_SHA256']
    need(re.fullmatch(r'[0-9a-f]{64}', archive), 'ARCHIVE_DIGEST')
    record = {'schema': 'vf0-a8-publication/v1', 'run': manifest['run_id'], 'attempt': 1,
              'source': manifest['coordinator_revision'], 'manifest_sha256': sha(canonical(manifest)),
              'artifact_id': aid, 'archive_sha256': archive}
    print(MARKER+canonical(record).decode('ascii'))


def read_capture(raw, metadata, record):
    need(sha(raw) == record['archive_sha256'] and metadata['digest'] == 'sha256:'+sha(raw), 'ARCHIVE_DIGEST')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = archive.infolist()
        allowed = {'capture.json', 'parent-manifest.json', 'synthetic-candidate.patch',
                   'characterize.container.json', 'characterize.untrusted.stdout', 'characterize.untrusted.stderr'}
        need({x.filename for x in entries} == allowed and len(entries) == len(allowed), 'ARCHIVE_MEMBERS')
        need(all(not x.is_dir() and not x.flag_bits & 1 and not stat.S_ISLNK(x.external_attr >> 16)
                 and 0 <= x.file_size <= 1_000_000 for x in entries), 'ARCHIVE_MEMBER_BOUND')
        need(sum(x.file_size for x in entries) <= 2_000_000, 'ARCHIVE_TOTAL_BOUND')
        return strict(archive.read('capture.json'))


def parse_publication(logs, manifest):
    records = []
    for line in logs.decode('utf-8').splitlines():
        match = re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,9})?Z (VF0_A8_PUBLICATION .*)', line)
        if match:
            records.append(match[1][len(MARKER):].encode('utf-8'))
    need(len(records) == 1 and len(records[0]) < 4096, 'PUBLICATION_COUNT')
    record = strict(records[0])
    need(set(record) == {'schema','run','attempt','source','manifest_sha256','artifact_id','archive_sha256'} and
         canonical(record) == records[0], 'PUBLICATION_SHAPE')
    need(record['schema'] == 'vf0-a8-publication/v1' and type(record['run']) is int and
         record['run'] == manifest['run_id'] and type(record['attempt']) is int and record['attempt'] == 1 and
         record['source'] == manifest['coordinator_revision'] and
         record['manifest_sha256'] == sha(canonical(manifest)), 'PUBLICATION_BINDING')
    need(type(record['artifact_id']) is int and record['artifact_id'] > 0 and
         re.fullmatch(r'[0-9a-f]{64}', record['archive_sha256']), 'PUBLICATION_ID')
    return record


def relation(manifest, captured, record, now):
    rid = manifest['run_id']
    evidence_refs = [digest(captured['before']['approvals']), digest(captured['after']['protection'])]
    # Assertions under the explicitly approved diagnostic fixture, not certifications.
    guarantees = {name: {'state': 'VERIFIED', 'records': evidence_refs} for name in GUARANTEES}
    request = manifest['request']
    admission = {'request_sha256': digest(request), 'record': ref(rid, 'native-review-content'),
                 'record_sha256': digest(captured['before']['approvals']), 'principal': ref(rid, str(OWNER)),
                 'disposition': 'APPROVED', 'observed_at': captured['admission_observed_at'],
                 'guarantees': copy.deepcopy(guarantees)}
    return {'schema': 'gnostoa-vf0-relation-input/v1', 'now': now,
        'policy': manifest['fixture_policy'], 'request': request, 'admission': admission,
        'evidence': {'request_sha256': digest(request), 'admission_sha256': digest(admission),
            'material': request['material'], 'mode': 'CHARACTERIZATION', 'chronology': 'PRE_CHANGE',
            'execution': ref(rid, 'isolated-command'), 'attempt': '1', 'latest_attempt': '1',
            'publisher': ref(rid, 'capture-job'), 'artifact': ref(rid, str(record['artifact_id'])),
            'source_sha256': 'sha256:'+manifest['pins']['coordinator_sha256'],
            'archive_sha256': 'sha256:'+record['archive_sha256'], 'status': 'COMPLETED', 'coverage': 'COMPLETE',
            'started_at': captured['started_at'], 'completed_at': captured['completed_at'],
            'expires_at': request['valid_until'], 'outcome': request['outcome'],
            'accountable_review': None, 'guarantees': copy.deepcopy(guarantees)},
        'candidate': {'parent_commit': SUBJECT, 'parent_tree': TREE, 'tree': captured['candidate_tree'],
            'observed_at': captured['candidate_at'], 'changed_paths': [PROBE_PATH],
            'evidence_files': request['material']['evidence_files']}}


def consume(root, out, manifest, before, reader):
    approved(before['approvals'], manifest, int(time.time()))
    jobs_path = f'/actions/runs/{reader.rid}/attempts/1/jobs?per_page=100'
    jobs = reader.get(jobs_path)
    need(jobs['total_count'] == len(jobs['jobs']) == 3, 'JOB_COVERAGE')
    expected = {'Freeze exact A8 request', 'Run approved isolated characterization', 'Reacquire and reconcile A8'}
    need({j['name'] for j in jobs['jobs']} == expected, 'JOB_NAMES')
    producers = [j for j in jobs['jobs'] if j['name'] != 'Reacquire and reconcile A8']
    for job in producers:
        need(job['run_id'] == reader.rid and job['run_attempt'] == 1 and
             job['head_sha'] == manifest['coordinator_revision'] and
             job['status'] == 'completed' and job['conclusion'] == 'success', 'PRODUCER_INCOMPLETE')
    publisher = next(j for j in producers if j['name'] == 'Run approved isolated characterization')
    logs_path = f'/actions/jobs/{publisher["id"]}/logs'
    logs = reader.download(logs_path)
    record = parse_publication(logs, manifest)
    path = f'/actions/artifacts/{record["artifact_id"]}'
    metadata = reader.get(path)
    need(metadata['id'] == record['artifact_id'] and metadata['name'] == f'vf0-a8-capture-{reader.rid}-1'
         and metadata['workflow_run']['id'] == reader.rid and metadata['workflow_run']['head_sha'] == manifest['coordinator_revision']
         and metadata['expired'] is False and timestamp(metadata['expires_at']) > int(time.time()), 'ARTIFACT_BINDING')
    need(metadata['workflow_run'].get('repository_id') == REPO_ID and
         metadata['workflow_run'].get('head_repository_id') == REPO_ID, 'ARTIFACT_REPOSITORY')
    raw = reader.download(path+'/zip')
    need(type(metadata.get('size_in_bytes')) is int and len(raw) == metadata['size_in_bytes'], 'ARCHIVE_SIZE')
    captured = read_capture(raw, metadata, record)
    need(captured['manifest'] == manifest and captured['parent_and_evidence_unchanged'] is True and
         captured['production_producer_admitted'] is False, 'CAPTURE_BINDING')
    after = observe(reader, manifest['coordinator_revision'])
    approved(after['approvals'], manifest, int(time.time()))
    need(before['protection'] == after['protection'] == captured['after']['protection'] and
         before['approvals'] == after['approvals'] == captured['after']['approvals'], 'FINAL_DRIFT')
    need(reader.get(path) == metadata and reader.download(logs_path) == logs, 'ARTIFACT_LOG_DRIFT')
    current_jobs = reader.get(jobs_path)
    for job in producers:
        need(next((j for j in current_jobs['jobs'] if j['id'] == job['id']), None) == job, 'JOB_DRIFT')
    core = load_source(root/'subject/tools/vf0_contract.py', manifest['pins']['core_sha256'], 'a8_core')
    value = relation(manifest, captured, record, int(time.time()))
    result = core.evaluate(value)
    need(result['status'] == 'MATCH' and result['authentication'] == 'NOT_ESTABLISHED' and
         result['compliance'] is False and result['vf0_active'] is False, 'RELATION_OR_AUTHORITY')
    negatives = []
    for key in ('parent_commit', 'parent_tree', 'evidence_files', 'changed_paths'):
        altered = copy.deepcopy(value)
        altered['candidate'][key] = {} if key == 'evidence_files' else [] if key == 'changed_paths' else 'other'
        observed = core.evaluate(altered)
        need(observed['status'] == 'REJECTED', 'NEGATIVE_FALSE_ACCEPT')
        negatives.append({'case': 'candidate_'+key, 'reasons': observed['reasons']})
    altered = copy.deepcopy(value)
    altered['evidence']['latest_attempt'] = '2'
    rejected = core.evaluate(altered)
    need(rejected['status'] == 'REJECTED', 'ATTEMPT_FALSE_ACCEPT')
    negatives.append({'case': 'newer_attempt', 'reasons': rejected['reasons']})
    production = copy.deepcopy(value)
    production['policy']['required_guarantees'].append('producer_integration')
    production['request']['policy_sha256'] = digest(production['policy'])
    production['admission']['request_sha256'] = digest(production['request'])
    production['evidence']['request_sha256'] = digest(production['request'])
    production['admission']['guarantees']['producer_integration'] = {'state':'UNSUPPORTED','records':[]}
    production['evidence']['admission_sha256'] = digest(production['admission'])
    refused = core.evaluate(production)
    need(refused['status'] == 'REJECTED', 'UNADMITTED_PRODUCER_ACCEPTED')
    negatives.append({'case': 'production_profile_unadmitted_producer', 'reasons': refused['reasons']})
    (out/'capture.zip').write_bytes(raw)
    (out/'publisher.log').write_bytes(logs)
    write_json(out/'provider-readback.json', {'before':before,'after':after,'jobs':jobs,'artifact':metadata,'publication':record})
    write_json(out/'relation-input.json', value)
    write_json(out/'result.json', {'schema':'vf0-a8-result/v1','status':'PASS','scope':'COMPOSE_DIAGNOSTIC_ONLY',
        'run':reader.rid,'subject':SUBJECT,'manifest_sha256':sha(canonical(manifest)),
        'relation':result,'negative_controls':negatives,'guarantee_labels_are_diagnostic_assumptions':True,
        'production_profile':refused,'production_producer_admitted':False,'vf0_active':False})
    print('VF0_A8_DIAGNOSTIC_COMPLETE_NO_PRODUCTION_ADMISSION')


def main():
    need(len(sys.argv) == 2 and sys.argv[1] in ('freeze','capture','publish','consume'), 'PHASE')
    phase = sys.argv[1]
    rid = identifier(os.environ['GITHUB_RUN_ID'])
    revision = os.environ['GITHUB_SHA']
    need(os.environ.get('GITHUB_REPOSITORY') == REPO and os.environ.get('GITHUB_RUN_ATTEMPT') == '1'
         and re.fullmatch(r'[0-9a-f]{40}', revision), 'CONTEXT')
    root = Path(os.environ['GITHUB_WORKSPACE'])
    need(git(root/'coordinator','rev-parse','HEAD').decode().strip() == revision, 'COORDINATOR_CHECKOUT')
    reader = Reader(rid)
    before = observe(reader, revision)
    pins = source_pins(root)
    tree, patch, production = evidence_tree(root/'subject')
    manifest = build_manifest(before['run'], pins, before['protection'], tree, patch, production)
    need(int(time.time()) < manifest['request']['valid_until'], 'EXPIRED_REQUEST')
    out = Path(os.environ['RUNNER_TEMP'])/('vf0-a8-'+phase)
    out.mkdir(mode=0o700, exist_ok=False)
    if phase == 'freeze':
        need(before['approvals'] == [], 'ALREADY_REVIEWED')
        write_json(out/'request.json', manifest)
        write_json(out/'preflight.json', before)
        (out/'probe.py').write_bytes(PROBE)
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='ascii') as stream:
            stream.write('manifest_sha256='+sha(canonical(manifest))+'\n')
        text = ('# A8: fixed-source composition diagnostic\n\nNo production deployment, merge or VF0 activation.\n\n'
                f'Run: https://github.com/{REPO}/actions/runs/{rid}\n\nSubject: `{SUBJECT}`\n\n'
                f'Expires: {manifest["expires_at"]}\n\nApproval comment:\n```text\n{approve_text(manifest)}\n```\n\n'
                'After approval: one isolated fixed three-check characterization; evidence-only synthetic candidate; '
                'independent archive/log read-back and the common relation. Diagnostic fixture assumptions are not production guarantees.\n')
        (out/'REQUEST.md').write_text(text)
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as stream:
            stream.write(text)
        print(approve_text(manifest))
    elif phase == 'capture':
        capture(root, out, manifest, before, reader)
    elif phase == 'publish':
        approved(before['approvals'], manifest, int(time.time()))
        publication(manifest)
    else:
        consume(root, out, manifest, before, reader)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('VF0_A8_REJECT '+(str(exc) if isinstance(exc, Rejected) else type(exc).__name__))
        raise SystemExit(1) from None
