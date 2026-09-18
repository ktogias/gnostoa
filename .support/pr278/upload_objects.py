"""Validate an admitted patch and upload immutable Git objects only."""
import base64
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import urllib.request

workspace = Path(os.environ['GITHUB_WORKSPACE'])
manifest = json.loads((workspace / 'helper/.support/pr278/manifest.json').read_text())
out = Path(os.environ['RUNNER_TEMP']) / 'pr278-object-receipt'
out.mkdir()
chunks = [workspace / f'helper/.support/pr278/repair.part{i}.b64' for i in range(1, 5)]
encoded = b''.join(p.read_bytes() for p in chunks)
assert len(encoded) == 14204
compressed = base64.b64decode(encoded, validate=True)
assert hashlib.sha1(b'blob ' + str(len(compressed)).encode() + b'\0' + compressed).hexdigest() == 'cfe4f78cbb02212b91797ec82f7c596370530477'
patch = gzip.decompress(compressed)
assert len(patch) == manifest['patch_bytes'] == 41880
assert hashlib.sha256(patch).hexdigest() == manifest['patch_sha256']
patch_path = out / 'candidate.patch'
patch_path.write_bytes(patch)

def git(*args):
    return subprocess.check_output(['git', '-C', str(workspace / 'source'), *args], timeout=30)

def api(path, data=None):
    request = urllib.request.Request('https://api.github.com/repos/ktogias/gnostoa/' + path,
        data=None if data is None else json.dumps(data).encode(),
        headers={'Authorization': 'Bearer ' + os.environ['GH_OBJECT_TOKEN'],
                 'Accept': 'application/vnd.github+json', 'Content-Type': 'application/json',
                 'X-GitHub-Api-Version': '2022-11-28'},
        method='GET' if data is None else 'POST')
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)

assert git('rev-parse', 'HEAD').decode().strip() == manifest['parent']
assert git('rev-parse', 'HEAD^{tree}').decode().strip() == manifest['base_tree']
assert not git('status', '--porcelain')
assert api('git/ref/heads/security/275-protected-payload-ci')['object']['sha'] == manifest['parent']
git('apply', '--cached', '--check', str(patch_path))
git('apply', '--cached', str(patch_path))
git('diff', '--cached', '--check')
assert set(git('diff', '--cached', '--name-only', '-z').decode().strip('\0').split('\0')) == set(manifest['files'])
assert git('write-tree').decode().strip() == manifest['tree']
entries = []
for path, expected in manifest['files'].items():
    actual = git('rev-parse', ':' + path).decode().strip()
    assert actual == expected
    mode = git('ls-files', '--stage', '--', path).decode().split()[0]
    assert mode == '100644'
    content = git('cat-file', 'blob', actual)
    assert len(content) < 1_000_000
    result = api('git/blobs', {'content': base64.b64encode(content).decode(), 'encoding': 'base64'})
    assert result['sha'] == expected
    entries.append({'path': path, 'mode': mode, 'type': 'blob', 'sha': expected})
result = api('git/trees', {'base_tree': manifest['base_tree'], 'tree': entries})
assert result['sha'] == manifest['tree']
receipt = {**manifest, 'effect': 'immutable blobs/tree only; no candidate code executed; no commit/ref/release mutation', 'workflow_run': os.environ['GITHUB_RUN_ID']}
(out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt, indent=2))
