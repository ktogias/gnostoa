"""Offline integrity verifier. Does not execute candidate code or tests."""
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
