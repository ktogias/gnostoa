"""Actual result consumer for this local fixture, not a production authority."""

import argparse
import json
from pathlib import Path
from typing import Any


def read_result(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ValueError("Unsupported fixture result record")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    print(json.dumps(read_result(args.path), sort_keys=True))


if __name__ == "__main__":
    main()
