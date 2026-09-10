"""Replay the completion-without-evidence mutant against the frozen oracle."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

FIXTURE = Path(__file__).resolve().parent
ORIGINAL = 'return _result("PENDING", "PENDING", worker_check, "verification-missing")'
MUTANT = (
    'return _result("ACCEPTED", "ACCEPTED", worker_check, '
    '"mutant-completion-without-evidence")'
)


def main() -> int:
    source = (FIXTURE / "candidate.py").read_bytes()
    original = ORIGINAL.encode("utf-8")
    if source.count(original) != 1:
        raise RuntimeError("Mutation anchor must occur exactly once")
    changed = source.replace(original, MUTANT.encode("utf-8"))
    print(
        json.dumps(
            {
                "operator": "F1.M1",
                "original": ORIGINAL,
                "replacement": MUTANT,
                "source_sha256": hashlib.sha256(source).hexdigest(),
                "mutant_sha256": hashlib.sha256(changed).hexdigest(),
            },
            sort_keys=True,
        ),
        flush=True,
    )
    with TemporaryDirectory(prefix="gnostoa-f1-mutant-") as directory:
        tests = Path(directory) / "tests"
        destination = tests / "fixtures" / "managed_acceptance"
        shutil.copytree(FIXTURE, destination)
        (destination / "candidate.py").write_bytes(changed)
        shutil.copyfile(
            FIXTURE.parents[1] / "test_managed_acceptance_fixture.py",
            tests / "test_managed_acceptance_fixture.py",
        )
        environment = dict(os.environ, GNOSTOA_FIXTURE_IMPLEMENTATION="candidate")
        return subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", str(tests), "-v"],
            env=environment,
            check=False,
        ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
