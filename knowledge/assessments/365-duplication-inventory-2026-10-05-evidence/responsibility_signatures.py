"""Detector C of the 2026-10-05 duplication inventory (#365).

Run: python responsibility_signatures.py <root>, where <root> is an extracted
`git archive 4618e1b`. It prints the table recorded, gzip-compressed, in
responsibility-signatures.txt.gz: for each responsibility, how many modules and lines
match its pattern, and the five modules with the most lines. A line counts once per
pattern, whatever shape the responsibility takes around it.
"""

import collections
import pathlib
import re
import sys

SIGNATURES = {
    "subprocess launches": r"subprocess\.(run|Popen|check_output|check_call)\(",
    "atomic replace": r"os\.replace\(",
    "temp-file writes": r"tempfile\.(mkstemp|NamedTemporaryFile)\(",
    "sha256": r"hashlib\.sha256\(",
    "current time": r"datetime\.now\(|time\.time\(\)",
    "JSON from a file": r"json\.loads?\(\s*[\w.]*(read_text|open)\(",
    "strict JSON hooks": r"object_pairs_hook|parse_constant",
    "HTTP": r"urllib\.request|urlopen\(|http\.client",
    "YAML loading": r"yaml\.(safe_)?load\(",
    "schema validation": r"Draft202012Validator",
    "path confinement": r"is_relative_to\(",
    "bounded read": r"\.read\(\s*\w*(LIMIT|MAX|limit|max)\w*\s*\+\s*1\s*\)",
    "retry/sleep loops": r"time\.sleep\(",
    "process-group kill": r"os\.killpg\(|killpg",
    "argparse CLIs": r"argparse\.ArgumentParser\(",
}


def main() -> None:
    root = pathlib.Path(sys.argv[1])
    files = sorted(
        p for d in ("tools", "ci", "tasks", ".github") for p in (root / d).rglob("*.py")
    )
    rows: list[tuple[str, int, int, list[tuple[str, int]]]] = []
    for name, pattern in SIGNATURES.items():
        rx = re.compile(pattern)
        hits: collections.Counter[str] = collections.Counter()
        for f in files:
            text = f.read_text(encoding="utf-8").splitlines()
            n = sum(1 for line in text if rx.search(line))
            if n:
                hits[f.relative_to(root).as_posix()] = n
        rows.append((name, len(hits), sum(hits.values()), hits.most_common(5)))
    for name, modules, lines, top in sorted(rows, key=lambda r: -r[1]):
        print(
            f"{name:22s} {modules:3d} modules {lines:4d} lines  top: "
            + ", ".join(f"{m.split('/')[-1]}:{n}" for m, n in top)
        )


if __name__ == "__main__":
    main()
