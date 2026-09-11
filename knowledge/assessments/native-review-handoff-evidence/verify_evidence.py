"""Verify this retained archive's bytes; no extraction, native call or truth claim."""

import gzip
import hashlib
import json
import tarfile
from pathlib import Path

root = Path(__file__).resolve().parent
index = json.loads((root / "index.json").read_bytes())
archive = root / index["archive"]
data = archive.read_bytes()
assert len(data) == index["bytes"]
assert hashlib.sha256(data).hexdigest() == index["sha256"]
manifest = (root / index["member_index"]["file"]).read_bytes()
assert hashlib.sha256(manifest).hexdigest() == index["member_index"]["sha256"]
raw = gzip.decompress(manifest)
assert hashlib.sha256(raw).hexdigest() == index["member_index"]["uncompressed_sha256"]
expected = json.loads(raw)
assert len(expected) == index["member_index"]["entries"]
with tarfile.open(archive) as packed:
    members = packed.getmembers()
    assert len(members) == len(expected)
    assert {member.name for member in members} == set(expected)
    for member in members:
        assert member.isfile()
        value = packed.extractfile(member).read()
        assert len(value) == expected[member.name]["bytes"]
        assert hashlib.sha256(value).hexdigest() == expected[member.name]["sha256"]
print(f"Verified archive and {len(expected)} retained members; no provider calls")
