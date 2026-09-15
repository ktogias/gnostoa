from __future__ import annotations

import sys
from pathlib import Path

from . import review_live
from .review_check import _ArgumentParser, _load_json
from .review_model import ERROR_EXIT_CODE, canonical_json, error_payload


def _parser() -> _ArgumentParser:
    parser = _ArgumentParser(
        prog="python -m tools.review_live_entrypoint",
        description=(
            "Evaluate Gnostoa-self current advisory through the integrated protected "
            "live route using only an untrusted input document."
        ),
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="untrusted current-advisory input JSON",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Transport one bounded input into the integrated protected live evaluator."""

    try:
        args = _parser().parse_args(sys.argv[1:] if argv is None else argv)
        try:
            input_path = args.input.resolve()
        except RuntimeError as exc:
            raise ValueError(f"live input path cannot be resolved: {exc}") from exc
        input_document = _load_json(input_path)
    except (OSError, RecursionError, ValueError) as exc:
        code = ERROR_EXIT_CODE
        payload = error_payload("MALFORMED_INVOCATION", str(exc))
    else:
        code, payload = review_live.evaluate_gnostoa_current_advisory(input_document)

    sys.stdout.write(canonical_json(payload) + "\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
