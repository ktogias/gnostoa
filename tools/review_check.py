from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, NoReturn

from jsonschema import Draft202012Validator

from .knowledge_common import KnowledgeFormatError, load_yaml, toolkit_root
from .review_evaluate import ReviewInputError, evaluate
from .review_model import ERROR_EXIT_CODE, SEMANTIC_EXIT_CODES, canonical_json, error_payload
from .review_policy import default_project_policy_path, resolve_project_policy


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise ValueError(message)


def _schema(name: str) -> dict[str, Any]:
    path = toolkit_root() / "schemas" / name
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise KnowledgeFormatError(f"Schema must be an object in {path}")
    return loaded


def _schema_errors(document: object, schema_name: str) -> list[str]:
    validator = Draft202012Validator(_schema(schema_name))
    errors = sorted(validator.iter_errors(document), key=lambda item: list(item.absolute_path))
    rendered: list[str] = []
    for error in errors:
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        rendered.append(f"{location}: {error.message}")
    return rendered


def evaluate_documents(input_document: object, policy_document: object) -> tuple[int, dict[str, Any]]:
    if not isinstance(input_document, dict):
        payload = error_payload("MALFORMED_INVOCATION", "review-check input must be an object")
        return ERROR_EXIT_CODE, payload
    if not isinstance(policy_document, dict):
        payload = error_payload("CONFIGURATION_ERROR", "review policy must be an object")
        return ERROR_EXIT_CODE, payload
    if input_document.get("schema_version") != "1.0":
        payload = error_payload("UNSUPPORTED_INPUT", "unsupported review-check input schema_version")
        return ERROR_EXIT_CODE, payload
    try:
        input_errors = _schema_errors(input_document, "review-check-input.schema.json")
        if input_errors:
            return ERROR_EXIT_CODE, error_payload(
                "MALFORMED_INVOCATION",
                "review-check input does not satisfy its public schema",
                details={"issues": input_errors},
            )
        policy_errors = _schema_errors(policy_document, "review-policy.schema.json")
        if policy_errors:
            return ERROR_EXIT_CODE, error_payload(
                "CONFIGURATION_ERROR",
                "review policy does not satisfy its public schema",
                details={"issues": policy_errors},
            )
        result = evaluate(input_document, policy_document)
    except ReviewInputError as exc:
        return ERROR_EXIT_CODE, error_payload(exc.code, str(exc), details=exc.details)
    except (KnowledgeFormatError, OSError, ValueError, TypeError) as exc:
        return ERROR_EXIT_CODE, error_payload("CONFIGURATION_ERROR", str(exc))
    outcome = result.get("outcome")
    exit_code = SEMANTIC_EXIT_CODES.get(outcome)
    if exit_code is None:
        return ERROR_EXIT_CODE, error_payload(
            "TOOL_ERROR",
            "evaluator returned an unsupported semantic outcome",
            details={"outcome": outcome},
        )
    return exit_code, result


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _parser() -> argparse.ArgumentParser:
    parser = _ArgumentParser(
        prog="knowledge review-check",
        description="Evaluate deterministic advisory semantic-review assurance over retained file evidence.",
    )
    parser.add_argument("--input", type=Path, required=True, help="review-check input JSON")
    parser.add_argument(
        "--policy",
        type=Path,
        help="effective policy YAML/JSON or project review-policy source",
    )
    parser.add_argument(
        "--change-class",
        choices=("mechanical", "normal", "normative", "critical", "emergency"),
        help="project specialization when the selected policy source contains change_classes",
    )
    return parser


def _load_policy(path: Path | None, change_class: str | None) -> dict[str, Any]:
    selected = default_project_policy_path() if path is None else path
    loaded = load_yaml(selected.resolve())
    if "change_classes" in loaded or "defaults" in loaded:
        if change_class is None:
            raise KnowledgeFormatError(
                "--change-class is required when evaluating a project review-policy source"
            )
        return resolve_project_policy(selected, change_class)
    if not isinstance(loaded, dict):
        raise KnowledgeFormatError(f"Review policy must be a mapping in {selected}")
    return loaded


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(sys.argv[1:] if argv is None else argv)
        input_document = _load_json(args.input.resolve())
        policy_document = _load_policy(args.policy, args.change_class)
        code, payload = evaluate_documents(input_document, policy_document)
    except (ValueError, OSError, json.JSONDecodeError, KnowledgeFormatError) as exc:
        code = ERROR_EXIT_CODE
        payload = error_payload("MALFORMED_INVOCATION", str(exc))
    sys.stdout.write(canonical_json(payload) + "\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
