"""Replay M0: enumerate recorded jobs instead of the independent roster."""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
ORIGINAL = 'ids = read(workspace / "roster.json")["eligible_job_ids"]'
MUTANT = 'ids = sorted(path.name for path in (workspace / "jobs").glob("*"))'


def main() -> int:
    with TemporaryDirectory(prefix="review-exchange-mutant-") as directory:
        fixture = Path(directory) / "fixture"
        shutil.copytree(HERE, fixture)
        source = (fixture / "candidate.py").read_text()
        if source.count(ORIGINAL) != 1:
            raise ValueError("Mutation target changed: requalify the operator")
        (fixture / "candidate.py").write_text(source.replace(ORIGINAL, MUTANT))
        environment = os.environ.copy()
        environment["GNOSTOA_EXCHANGE_FIXTURE_ROOT"] = str(fixture)
        environment["GNOSTOA_EXCHANGE_IMPLEMENTATION"] = "candidate"
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests",
                "-p",
                "test_review_exchange_fixture.py",
                "-v",
            ],
            cwd=HERE.parents[2],
            env=environment,
            check=False,
        ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
