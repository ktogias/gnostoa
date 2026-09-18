"""Transfer only hash-verified public source objects, without executing candidate code."""
import base64
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import urllib.request

support = Path(os.environ['SUPPORT_DIR'])
repo = Path(os.environ['CANDIDATE_DIR'])
out = Path(os.environ['RECEIPT_DIR'])
out.mkdir(parents=True, exist_ok=False)
manifest = json.loads((support / '.support/manifest.json').read_text())
assert manifest['base'] == 'e29b12950612e3696d3d087708cdd9a615d92b04'
assert manifest['tree'] == '64b1a371a315369ae51d94b365affca431a2db91'
wire = (support / '.support/repair.transport').read_bytes()
assert hashlib.sha1(b'blob '+str(len(wire)).encode()+b'\0'+wire).hexdigest() == 'abc18a54e09235fb5b58ad96493936ac4ce7ae06'
# Two known transcription errors in the tool-call transport, not in source.
# Apply the exact inverse, then require both original SHA-256s before use.
encoded = base64.b64encode(wire).decode('ascii')
for old, new in [('HDSG9j2Oj3', 'HDSG9j2yOj3'), ('lPtlYKFxZZ8', 'lPtlYKFxZ8')]:
    assert encoded.count(old) == 1
    encoded = encoded.replace(old, new)
compressed = base64.b64decode(encoded, validate=True)
assert hashlib.sha256(compressed).hexdigest() == manifest['gzip_sha256']
patch = gzip.decompress(compressed)
assert hashlib.sha256(patch).hexdigest() == manifest['patch_sha256']

def git(*args):
    return subprocess.check_output(['git', '-c', 'core.hooksPath=/dev/null', '-C', str(repo), *args], text=True).strip()

assert git('rev-parse', 'HEAD') == manifest['base']
assert git('rev-parse', 'HEAD^{tree}') == manifest['base_tree']
patch_path = out / 'repair.patch'
patch_path.write_bytes(patch)
(out / 'repair.patch.gz').write_bytes(compressed)
subprocess.run(['git', '-c', 'core.hooksPath=/dev/null', '-C', str(repo), 'apply', '--index', '--whitespace=error-all', str(patch_path)], check=True)
assert set(git('diff', '--cached', '--name-only').splitlines()) == set(manifest['files'])
assert git('write-tree') == manifest['tree']
verified = []
for name, expected in sorted(manifest['files'].items()):
    entry = git('ls-files', '--stage', '--', name)
    assert entry == f'100644 {expected} 0\t{name}', entry
    path = repo / name
    assert path.is_file() and not path.is_symlink()
    content = path.read_bytes()
    actual = hashlib.sha1(b'blob '+str(len(content)).encode()+b'\0'+content).hexdigest()
    assert actual == expected
    content.decode('utf-8')
    verified.append((name, expected, content))
# No candidate imports, tests, build scripts, commits or ref operations here.
for name, expected, content in verified:
    body = json.dumps({'content': base64.b64encode(content).decode('ascii'), 'encoding': 'base64'}).encode()
    request = urllib.request.Request('https://api.github.com/repos/ktogias/gnostoa/git/blobs', data=body, method='POST', headers={'Authorization': 'Bearer '+os.environ['GH_TOKEN'], 'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28', 'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.load(response)
    assert result['sha'] == expected
manifest['uploaded_blobs'] = len(verified)
manifest['candidate_executed'] = False
manifest['ref_changed'] = False
(out / 'receipt.json').write_text(json.dumps(manifest, indent=2)+'\n')
print(json.dumps(manifest, sort_keys=True))
