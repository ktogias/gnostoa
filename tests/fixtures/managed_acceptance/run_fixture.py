"""Run one frozen case, persist its result, then consume the persisted state."""

import argparse
from copy import deepcopy
import importlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from adapters import ADAPTERS
from read_result import read_result
from services import FixtureServices


ROOT = Path(__file__).resolve().parent


def load_case(case_id: str) -> dict[str, Any]:
    inputs = json.loads((ROOT / "cases.json").read_text(encoding="utf-8"))
    case = deepcopy(inputs["common"])
    case.update(deepcopy(inputs["cases"][case_id]))
    case["id"] = case_id
    return case


def execute(case_id: str, adapter: str, implementation: str, output: Path) -> None:
    case = load_case(case_id)
    services = FixtureServices(case, adapter)
    control = importlib.import_module(implementation)
    control_case = deepcopy(case)
    del control_case["native_streams"]
    result = control.run(control_case, services)
    record = {
        "schema_version": 1,
        "case_id": case_id,
        "adapter": adapter,
        "implementation": implementation,
        "subject": case["subject"],
        "result": result,
        "observations": services.observations(),
    }
    output.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(read_result(output), sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True)
    parser.add_argument("--adapter", required=True, choices=ADAPTERS)
    parser.add_argument(
        "--implementation", required=True, choices=("baseline", "candidate")
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output is not None:
        execute(args.case, args.adapter, args.implementation, args.output)
    else:
        with TemporaryDirectory(prefix="gnostoa-f1-") as directory:
            execute(
                args.case,
                args.adapter,
                args.implementation,
                Path(directory) / "result.json",
            )


if __name__ == "__main__":
    main()
