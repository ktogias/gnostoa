"""Replay a declared acceptance mutant against the frozen fixture oracle."""

import argparse
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
OPERATORS = {
    "F1.M1": (ORIGINAL, MUTANT),
    "M4": (
        '    if services.worker_terminal != "completed":\n'
        '        return _result("PENDING", "PENDING", worker_check, '
        '"worker-not-completed")\n',
        "",
    ),
    "M7": (
        '    if check_plan in {"planned", "finalization"} and (\n'
        '        case["assigned_checker"] == "supervisor"\n'
        '        or case["allow_supervisor_substitution"]\n'
        "    ):\n",
        '    if check_plan in {"planned", "finalization"}:\n',
    ),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operator", choices=OPERATORS, default="F1.M1")
    args = parser.parse_args()
    original_text, replacement_text = OPERATORS[args.operator]
    source = (FIXTURE / "candidate.py").read_bytes()
    original = original_text.encode("utf-8")
    if source.count(original) != 1:
        raise RuntimeError("Mutation anchor must occur exactly once")
    changed = source.replace(original, replacement_text.encode("utf-8"))
    print(
        json.dumps(
            {
                "operator": args.operator,
                "original": original_text,
                "replacement": replacement_text,
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
