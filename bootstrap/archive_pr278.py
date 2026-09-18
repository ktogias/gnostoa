"""One-shot evidence archiver; never imports or executes PR/candidate code."""
from __future__ import annotations
import ast, base64, hashlib, io, json, os, pathlib, platform, urllib.error, urllib.parse, urllib.request, zipfile, zlib
from datetime import datetime, timezone

REPO = 'ktogias/gnostoa'
BRANCH = 'evidence/pr278-deep-review-ad1efac7-20260918'
SOURCE = 'ad1efac7b5d62f2252131483066579728012690c'
BASE = '7c14f9111cb560ea26dd68440812f64b37069706'
MERGE = 'fb3b19d1b1a01c58d11bc8c88da4e71e5595a1ec'
RUN = 35373573729
ARTIFACT = 10559267997
REPORT = 5735783198
PREFIX = 'evidence/pr278/ad1efac7/'
API = 'https://api.github.com/repos/' + REPO
MAX = 32 * 1024 * 1024
TOKEN = os.environ.get('GH_TOKEN', '')
NOW = datetime.now(timezone.utc).isoformat()
files: dict[str, bytes] = {}


def digest(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def encode(obj: object) -> bytes:
    return (json.dumps(obj, ensure_ascii=False, indent=2) + '\n').encode()


def request(path: str, data: object | None = None, method: str | None = None) -> bytes:
    if not path.startswith('/'):
        raise ValueError('relative repository API path required')
    headers = {'Authorization': 'Bearer ' + TOKEN, 'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'gnostoa-pr278-evidence-archiver'}
    body = None if data is None else json.dumps(data).encode()
    req = urllib.request.Request(API + path, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=60) as response:
        raw = response.read(MAX + 1)
    if len(raw) > MAX:
        raise RuntimeError('API response exceeds archival bound')
    return raw


def api(path: str, data: object | None = None, method: str | None = None) -> object:
    return json.loads(request(path, data, method))


def retain(path: str, destination: str) -> object:
    raw = request(path)
    files[destination] = raw
    return json.loads(raw)


def pages(path: str, label: str) -> list[dict]:
    result = []
    for page in range(1, 41):
        sep = '&' if '?' in path else '?'
        batch = retain(f'{path}{sep}per_page=100&page={page}', f'provider-readback/{label}-{page:03d}.json')
        if not isinstance(batch, list):
            raise RuntimeError('expected paginated array')
        result.extend(batch)
        if len(batch) < 100:
            return result
    raise RuntimeError('public record pagination exceeds bound; not complete')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def download_artifact() -> bytes:
    req = urllib.request.Request(API + f'/actions/artifacts/{ARTIFACT}/zip', headers={'Authorization': 'Bearer ' + TOKEN, 'User-Agent': 'gnostoa-pr278-evidence-archiver'})
    try:
        with urllib.request.build_opener(NoRedirect).open(req, timeout=60) as response:
            raw = response.read(MAX + 1)
    except urllib.error.HTTPError as exc:
        if exc.code not in (301, 302, 303, 307, 308):
            raise RuntimeError(f'artifact download failed HTTP {exc.code}') from None
        location = exc.headers.get('Location', '')
        if urllib.parse.urlparse(location).scheme != 'https':
            raise RuntimeError('artifact redirect must be HTTPS')
        with urllib.request.urlopen(urllib.request.Request(location, headers={'User-Agent': 'gnostoa-pr278-evidence-archiver'}), timeout=60) as response:
            raw = response.read(MAX + 1)
    if len(raw) > MAX:
        raise RuntimeError('artifact exceeds archival bound')
    return raw


def read_blob(sha: str) -> bytes:
    obj = api('/git/blobs/' + sha)
    raw = base64.b64decode(obj['content'])
    actual = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
    if actual != sha:
        raise RuntimeError('Git blob identity mismatch')
    return raw


def verify_originals(records: dict) -> dict:
    results = {}
    for name, expected in records['member_manifest'].items():
        raw = files['original/' + name]
        if len(raw) != expected['size_bytes'] or digest(raw) != expected['sha256']:
            raise RuntimeError('original member mismatch: ' + name)
        results[name] = expected
    audit = json.loads(files['original/artifact-audit.json'])
    summary = json.loads(files['original/provider-reports/quality-summary.json'])
    if summary['source']['revision'] != MERGE:
        raise RuntimeError('provider merge subject mismatch')
    if len(audit['manifest_checks']) != 13:
        raise RuntimeError('wrong internal manifest cardinality')
    for name, expected in audit['manifest_checks'].items():
        raw = files['original/provider-reports/' + name]
        if len(raw) != expected['size_bytes'] or digest(raw) != expected['sha256']:
            raise RuntimeError('provider internal report mismatch: ' + name)
    return results


VERIFIER = '''"""Offline integrity verifier. Does not execute candidate code or tests."""
import hashlib, json
from pathlib import Path
root = Path(__file__).resolve().parent
manifest = json.loads((root / 'manifest.json').read_text())
for name, entry in manifest['files'].items():
    p = Path(name)
    if p.is_absolute() or '..' in p.parts:
        raise SystemExit('unsafe manifest path')
    raw = (root / p).read_bytes()
    if len(raw) != entry['size_bytes'] or hashlib.sha256(raw).hexdigest() != entry['sha256']:
        raise SystemExit('MISMATCH: ' + name)
print('PASS:', len(manifest['files']), 'archived file hashes and sizes')
print('Integrity is not test execution, signature, review approval or merge authorization.')
'''


def main() -> None:
    if os.environ.get('GITHUB_REPOSITORY') != REPO or os.environ.get('GITHUB_REF') != 'refs/heads/' + BRANCH or os.environ.get('GITHUB_EVENT_NAME') != 'push':
        raise RuntimeError('archival execution is restricted to the exact evidence branch push')
    if not TOKEN:
        raise RuntimeError('missing token')
    initial = os.environ['GITHUB_SHA']
    ref_path = '/git/ref/heads/' + BRANCH
    if api(ref_path)['object']['sha'] != initial:
        raise RuntimeError('evidence branch moved before acquisition')
    # Repair a single verified transport omission; all decoded original bytes
    # remain guarded by independently retained whole-payload and member hashes.
    encoded = read_blob('9d216e4802904d2b1c0a8c9f1024413c965c7a97').decode()
    encoded = encoded.replace('J5fRi8vvLn/jaoA2', 'J5fRi8vvLn/44fK/UEMS5qKGcPcwMbhf5dnzq4unry6v/jaoA2')
    if digest(encoded.encode()) != 'b27344f640a71bf2730c106674ff769edeed40c1ddb7fa9da61c92b392f0903b':
        raise RuntimeError('local-record transfer integrity check failed')
    decompressor = zlib.decompressobj()
    decoded = decompressor.decompress(base64.b64decode(encoded.strip(), validate=True), 1048576)
    if not decompressor.eof or decompressor.unused_data or decompressor.unconsumed_tail:
        raise RuntimeError('invalid or oversized local record envelope')
    records = json.loads(decoded)
    for name, text in records['files'].items():
        if name not in ('README.md', 'characterization.py', 'characterization-results.json', 'artifact-audit.json'):
            raise RuntimeError('unexpected local record')
        files['original/' + name] = text.encode()
    metadata = retain(f'/actions/artifacts/{ARTIFACT}', 'provider-readback/original-artifact-metadata.json')
    if metadata.get('workflow_run', {}).get('id') != RUN or metadata.get('expired'):
        raise RuntimeError('provider artifact provenance or availability mismatch')
    archive = download_artifact()
    if digest(archive) != 'aad2f0ae8f4304365f450d5cbda00dd345417e8699f06a591075a217238128ae':
        raise RuntimeError('provider archive hash mismatch')
    files['provider-original.zip'] = archive
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        expected = {n.removeprefix('provider-reports/') for n in records['member_manifest'] if n.startswith('provider-reports/')}
        if set(z.namelist()) != expected or len(z.namelist()) != len(expected):
            raise RuntimeError('provider archive member set mismatch')
        if sum(i.file_size for i in z.infolist()) > 4 * 1024 * 1024:
            raise RuntimeError('provider archive expansion bound exceeded')
        for name in sorted(expected):
            files['original/provider-reports/' + name] = z.read(name)
    member_checks = verify_originals(records)
    original_zip = io.BytesIO()
    with zipfile.ZipFile(original_zip, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for item in records['zip_layout']:
            info = zipfile.ZipInfo(item['filename'], tuple(item['date_time']))
            for key, value in item.items():
                if key not in ('filename', 'date_time'):
                    setattr(info, key, value)
            z.writestr(info, files['original/' + item['filename']], compresslevel=6)
    original_bytes = original_zip.getvalue()
    if digest(original_bytes) != records['original_zip_sha256'] or len(original_bytes) != records['original_zip_size']:
        raise RuntimeError('byte-for-byte original review ZIP reconstruction failed')
    files['pr278-review-evidence-original.zip'] = original_bytes
    files['original-member-manifest.json'] = encode(records['member_manifest'])
    report = retain(f'/issues/comments/{REPORT}', 'provider-readback/full-report-comment.json')
    if report['issue_url'] != API + '/issues/278' or not report['body'].startswith('<!-- gnostoa:deep-review:ad1efac7:'):
        raise RuntimeError('report identity mismatch')
    files['REPORT.el.md'] = report['body'].encode()
    files['archiver-source.py'] = pathlib.Path(__file__).read_bytes()
    source_commit = retain('/git/commits/' + SOURCE, 'sources/reviewed-commit.json')
    source_tree = retain('/git/trees/' + source_commit['tree']['sha'] + '?recursive=1', 'sources/reviewed-tree.json')
    if source_tree.get('truncated') or source_commit['tree']['sha'] != '0438f8c5a0b07158122a60e31e5bfd50fcb7b166':
        raise RuntimeError('source tree identity/completeness mismatch')
    entries = {i['path']: i for i in source_tree['tree']}
    source_paths = ['tools/security_scan.py', 'tools/review_current.py', 'tools/quality_evidence.py', 'tools/repository_scope.py', 'tools/review_outer.py', 'tests/test_security_review_followup.py', 'tests/test_quality_evidence.py', 'tests/test_review_current_payload_transport.py', 'LICENSE', 'requirements/runtime.lock', 'requirements/development.lock']
    source_index = []
    for path in source_paths:
        entry = entries[path]
        raw = read_blob(entry['sha'])
        files['sources/' + path] = raw
        source_index.append({'path': path, 'blob_sha': entry['sha'], 'sha256': digest(raw), 'size_bytes': len(raw), 'url': f'https://github.com/{REPO}/blob/{SOURCE}/{path}'})
    files['source-index.json'] = encode(source_index)
    extracts = {n.name: n for n in ast.parse(files['original/characterization.py']).body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    groups = {'tools/security_scan.py': ['_os_error_symbol', '_safe_os_error', '_close_snapshot_descriptor', '_check_snapshot_deadline', '_write_all', '_immutable_candidate_snapshot'], 'tools/review_current.py': ['_kill_and_reap'], 'tools/quality_evidence.py': ['main']}
    ast_checks = []
    for path, names in groups.items():
        actual = {n.name: n for n in ast.parse(files['sources/' + path]).body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        for name in names:
            same = ast.dump(extracts[name], include_attributes=False) == ast.dump(actual[name], include_attributes=False)
            ast_checks.append({'source': path, 'function': name, 'ast_equal': same, 'method': 'static AST comparison, no execution'})
    files['source-extract-validation.json'] = encode(ast_checks)
    current = retain('/pulls/278', 'provider-readback/pr-at-archival.json')
    retain('/compare/' + SOURCE + '...' + current['head']['sha'], 'provider-readback/compare-reviewed-to-archival-head.json')
    retain(f'/actions/runs/{RUN}', 'provider-readback/original-run.json')
    retain(f'/actions/runs/{RUN}/jobs?per_page=100', 'provider-readback/original-run-jobs.json')
    issue_comments = pages('/issues/278/comments', 'issue-comments')
    reviews = pages('/pulls/278/reviews', 'reviews')
    inline = pages('/pulls/278/comments', 'inline-comments')
    for comment in (5728228063, 5730114348, 5734815516, 5734830816, 5734834185):
        retain(f'/issues/comments/{comment}', f'provider-readback/handoff-comment-{comment}.json')
    retain('/issues/275', 'provider-readback/issue-275.json')
    index = []
    for kind, items in [('issue_comment', issue_comments), ('review', reviews), ('inline_comment', inline)]:
        for item in items:
            index.append({'kind': kind, 'id': item['id'], 'user': item.get('user', {}).get('login'), 'url': item.get('html_url'), 'commit_id': item.get('commit_id'), 'original_commit_id': item.get('original_commit_id'), 'created_at': item.get('created_at', item.get('submitted_at')), 'updated_at': item.get('updated_at'), 'state': item.get('state'), 'path': item.get('path'), 'body_preview': item.get('body', '')[:500]})
    files['review-source-index.json'] = encode(index)
    validation = {'archived_at_utc': NOW, 'reviewed_head': SOURCE, 'base': BASE, 'provider_event_merge_subject': MERGE, 'archival_readback_head': current['head']['sha'], 'archival_bootstrap_commit': initial, 'archival_workflow_run': os.environ.get('GITHUB_RUN_ID'), 'archival_python': platform.python_version(), 'provider_archive_sha256': digest(archive), 'original_review_archive_sha256': digest(original_bytes), 'original_members_verified': len(member_checks), 'provider_internal_manifest_entries_verified': 13, 'provider_report_count_including_summary': 14, 'source_extracts_ast_equal': all(i['ast_equal'] for i in ast_checks), 'source_extracts_compared': len(ast_checks), 'original_tests_rerun': False, 'candidate_code_executed': False, 'full_checkout_tests_run': False, 'docker_run': False, 'scope': 'archival integrity and static binding verification only', 'limitations': ['Original execution transcript was not supplied.', 'Original raw reviewer snapshot is not in the initial ZIP; separately retained public records were collected at archival time.', 'Omitted Qodo portal findings have no complete individual inventory here.', 'No actual hostile filesystem or kernel-stall experiment.', 'No transfer of old-head review conclusions to the current head.', 'Evidence hashes and branch are not signatures or provider-enforced immutable storage.']}
    files['archival-validation.json'] = encode(validation)
    dispositions = [('D01','cooperative deadline','ACCEPT_STAGED_LIMITATION'),('D02','CodeAnt abort ordering deadlock claim','NOT_ESTABLISHED_AS_BLOCKER'),('D03','unexpected scanner exception boundary','NONBLOCKING_HARDENING'),('D04','blind tracked_paths forwarding','NOT_ADOPTED'),('D05','cleanup RecursionError/root finalization','ADDRESSED_WITH_LIMITS'),('D06','prior assertion stub formatting typing failures','NO_LONGER_REPORTED_IN_RETAINED_PROVIDER_EVIDENCE'),('D07','known raw repository scope error','ADDRESSED'),('D08','subprocess audit warnings','PER_OPERATION_ADJUDICATION'),('D09','docstring coverage','DOCUMENTATION_NONBLOCKING'),('D10','current_advisory unavailability','CONTAINED_RESTORATION_PENDING'),('D11','stale PR description','RECORD_RECONCILIATION_REQUIRED'),('D12','15 omitted Qodo findings','INDIVIDUAL_STATUS_UNKNOWN'),('D13','pip missing audit row','EXPLICIT_COVERAGE_GAP'),('D14','license manual review and SBOM scope','SEPARATE_OBLIGATION_NOT_DISCHARGED')]
    files['dispositions.json'] = encode({'reviewed_head': SOURCE, 'authority': 'agent-authored advisory; not owner acceptance or merge authorization', 'details': 'REPORT.el.md', 'items': [{'id': i, 'topic': topic, 'disposition': status} for i,topic,status in dispositions]})
    files['verify_archive.py'] = VERIFIER.encode()
    files['README.md'] = ('''# PR #278 full historical review and evidence archive

Read REPORT.el.md for the complete report, all dispositions and primary-source references. dispositions.json is a navigation index, not a replacement for the rationale.

This evidence-only branch is not a product change, is not a merge candidate, and must not be merged into main. Use the final commit-pinned URL, not the mutable branch name, as the archival locator.

## Boundaries

Reviewed source: `''' + SOURCE + '''`.
Provider event/merge subject: `''' + MERGE + '''`.
Later PR state is separately captured under provider-readback/; it is NOT the original review-time snapshot and does not rebind the report to newer code.

## Contents of complete-review-archive.zip

- REPORT.el.md: full Greek report as published in PR comment 5735783198.
- pr278-review-evidence-original.zip: byte-for-byte original 149497-byte review package.
- provider-original.zip: exact original provider archive, artifact 10559267997 / run 35373573729.
- original/: all 18 original review-package members (14 provider reports including quality-summary.json, original README, characterization script, results and artifact audit).
- sources/: exact-source files, commit and complete Git tree metadata; source-index.json contains Git blob identities and SHA-256 hashes. Source extracts remain repository-owned code; the source LICENSE is retained.
- provider-readback/: paginated public comments/reviews and source/workflow/handoff records, collected at archival time. review-source-index.json records attribution, times and commit IDs without manufacturing absent portal findings or thread-resolution state.
- source-extract-validation.json: static AST binding checks, not tests or code execution.
- archival-validation.json: new archival checks and explicit gaps; original test results are unchanged.
- manifest.json, SHA256SUMS and verify_archive.py: per-file integrity metadata and offline verification.
- archiver-source.py: one-shot acquisition/verification script; contains no candidate execution or product repair.

## Verify without running tests

Download the complete ZIP and its outer ARCHIVE.sha256 from the same pinned commit. Verify the outer SHA-256 before extraction, then extract into a new directory and run:

```sh
python3 verify_archive.py
sha256sum -c SHA256SUMS
```

The manifest excludes itself and SHA256SUMS to avoid circular hashing; SHA256SUMS includes manifest.json. The complete ZIP is not a member of itself. Integrity is not signature, original provenance authentication, review approval or merge authorization.

## Reproduce the original isolated characterization separately

Read original/characterization.py first. On Linux/Python 3.11+, copy it into a fresh directory, then execute the copy. It starts/kills test children and overwrites the neighboring characterization-results.json. Retain the new interpreter version, stdout/stderr and result separately; do not overwrite archived evidence. The retained original run used Python 3.13.5. This script uses source extracts and stubs; it is not ci/verify, a full checkout test, Docker execution or a real hostile-filesystem experiment.

The original complete terminal transcript and original-time raw reviewer snapshot were not supplied. Qodo's omitted individual portal findings are not reconstructed. Any source-binding discrepancy in archival-validation.json must be investigated before evidence reuse.

## Restoration obligation

The only operational checklist is https://github.com/ktogias/gnostoa/issues/275#issuecomment-5734815516 (R1–R7), linked from #14 and #15. Containment is not restoration. No box is completed by archiving this report.

## Effects

The archiver reads fixed public source/review artifacts and writes this evidence branch only. It executes no candidate code or tests and retires the temporary bootstrap workflow by replacing the branch tree with evidence-only files. It changes neither main nor the #278 source branch, protected authority, required checks, package/release publication, reviewer-thread status, nor merge state.
''').encode()
    manifest = {'schema_version': 1, 'reviewed_head': SOURCE, 'provider_event_merge_subject': MERGE, 'excludes': ['manifest.json', 'SHA256SUMS'], 'files': {name: {'size_bytes': len(raw), 'sha256': digest(raw)} for name, raw in sorted(files.items())}}
    files['manifest.json'] = encode(manifest)
    files['SHA256SUMS'] = ''.join(f'{digest(raw)}  {name}\n' for name, raw in sorted(files.items())).encode()
    bundle = io.BytesIO()
    with zipfile.ZipFile(bundle, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name, raw in sorted(files.items()):
            z.writestr(name, raw)
    bundle_bytes = bundle.getvalue()
    selected = ['README.md','REPORT.el.md','dispositions.json','archival-validation.json','manifest.json','verify_archive.py','source-index.json','source-extract-validation.json','original-member-manifest.json','original/artifact-audit.json','original/characterization-results.json','original/characterization.py','original/README.md']
    tree_entries = [{'path': PREFIX + name, 'mode': '100644', 'type': 'blob', 'content': files[name].decode()} for name in selected]
    tree_entries.append({'path': 'README.md', 'mode': '100644', 'type': 'blob', 'content': '# PR #278 evidence archive\n\nEvidence only; never merge this branch into main.\n\n[Full report and archive](evidence/pr278/ad1efac7/README.md)\n'})
    for name, raw in [('complete-review-archive.zip', bundle_bytes), ('pr278-review-evidence-original.zip', original_bytes), ('provider-original.zip', archive)]:
        blob = api('/git/blobs', {'content': base64.b64encode(raw).decode(), 'encoding': 'base64'}, 'POST')
        tree_entries.append({'path': PREFIX + name, 'mode': '100644', 'type': 'blob', 'sha': blob['sha']})
    outer_hash = digest(bundle_bytes)
    tree_entries.append({'path': PREFIX + 'ARCHIVE.sha256', 'mode': '100644', 'type': 'blob', 'content': outer_hash + '  complete-review-archive.zip\n'})
    tree = api('/git/trees', {'tree': tree_entries}, 'POST')
    if api(ref_path)['object']['sha'] != initial:
        raise RuntimeError('evidence branch moved before publication')
    commit = api('/git/commits', {'message': 'docs(evidence): preserve complete PR 278 ad1efac7 review and verified artifacts\n\nEvidence only; no product or review-candidate mutation. Retire one-shot archival workflow.', 'tree': tree['sha'], 'parents': [initial]}, 'POST')
    api('/git/refs/heads/' + BRANCH, {'sha': commit['sha'], 'force': False}, 'PATCH')
    if api(ref_path)['object']['sha'] != commit['sha']:
        raise RuntimeError('evidence ref read-back mismatch')
    receipt = {'commit': commit['sha'], 'tree': tree['sha'], 'archive_sha256': outer_hash, 'archive_size_bytes': len(bundle_bytes), 'archive_members': len(files), 'original_review_zip_sha256': digest(original_bytes), 'provider_original_zip_sha256': digest(archive), 'source_extracts_ast_equal': validation['source_extracts_ast_equal'], 'candidate_code_executed': False, 'original_tests_rerun': False}
    print(json.dumps(receipt, indent=2))
    with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as out:
        out.write('# Archival receipt\n\n```json\n' + json.dumps(receipt, indent=2) + '\n```\n')


if __name__ == '__main__':
    main()
