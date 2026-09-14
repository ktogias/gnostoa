from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, NoReturn

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError

from .knowledge_common import KnowledgeFormatError, toolkit_root
from .review_evaluate import ReviewInputError, evaluate
from .review_model import (
    ERROR_EXIT_CODE,
    SEMANTIC_EXIT_CODES,
    canonical_json,
    error_payload,
    parse_rfc3339,
)
from .review_policy import (
    default_project_policy_path,
    load_review_policy_source,
    resolve_loaded_project_policy,
)

# File-mode review evidence gets more room than a task envelope while remaining
# operationally bounded. The limit is four times the existing 512 KiB task
# envelope source cap; semantic eligibility still comes from the public schemas.
MAX_REVIEW_INPUT_BYTES = 2_097_152
MAX_REVIEW_DOCUMENT_DEPTH = 64
FORMAT_CHECKER = FormatChecker()


@FORMAT_CHECKER.checks("date-time")
def _is_strict_rfc3339(value: object) -> bool:
    if not isinstance(value, str):
        return True
    try:
        parse_rfc3339(value)
    except ValueError:
        return False
    return True


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise ValueError(message)


def _schema(name: str) -> dict[str, Any]:
    path = toolkit_root() / "schemas" / name
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except RecursionError as exc:
        raise KnowledgeFormatError(
            f"Installed review-assurance schema nesting exhausted the JSON parser: {path}"
        ) from exc
    if not isinstance(loaded, dict):
        raise KnowledgeFormatError(f"Schema must be an object in {path}")
    try:
        Draft202012Validator.check_schema(loaded)
    except RecursionError as exc:
        raise KnowledgeFormatError(
            f"Installed review-assurance schema nesting exhausted the schema checker: {path}"
        ) from exc
    return loaded


def _schema_errors(document: object, schema_name: str) -> list[str]:
    validator = Draft202012Validator(
        _schema(schema_name),
        format_checker=FORMAT_CHECKER,
    )
    errors = sorted(
        validator.iter_errors(document), key=lambda item: list(item.absolute_path)
    )
    rendered: list[str] = []
    for error in errors:
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        rendered.append(f"{location}: {error.message}")
    return rendered


def _assert_document_depth(document: object, label: str) -> None:
    pending: list[tuple[object, int]] = [(document, 1)]
    processed_depth: dict[int, int] = {}
    while pending:
        value, depth = pending.pop()
        if depth > MAX_REVIEW_DOCUMENT_DEPTH:
            raise ValueError(
                f"{label} nests deeper than the "
                f"{MAX_REVIEW_DOCUMENT_DEPTH}-level operational bound"
            )
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError(f"{label} contains a non-finite number")
        if not isinstance(value, (dict, list)):
            continue

        identity = id(value)
        previous_depth = processed_depth.get(identity)
        if previous_depth is not None and depth <= previous_depth:
            continue
        processed_depth[identity] = depth

        children = value.values() if isinstance(value, dict) else value
        pending.extend((child, depth + 1) for child in children)


def _object_without_duplicate_fields(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"review-check input repeats JSON object field {key!r}")
        result[key] = value
    return result


def _reject_non_finite_constant(value: str) -> NoReturn:
    raise ValueError(f"review-check input contains non-finite JSON number {value!r}")


def _parse_finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(
            f"review-check input contains non-finite JSON number {value!r}"
        )
    return parsed


def evaluate_documents(
    input_document: object, policy_document: object
) -> tuple[int, dict[str, Any]]:
    if not isinstance(input_document, dict):
        payload = error_payload(
            "MALFORMED_INVOCATION", "review-check input must be an object"
        )
        return ERROR_EXIT_CODE, payload
    if not isinstance(policy_document, dict):
        payload = error_payload(
            "CONFIGURATION_ERROR", "review policy must be an object"
        )
        return ERROR_EXIT_CODE, payload
    if input_document.get("schema_version") != "1.0":
        payload = error_payload(
            "UNSUPPORTED_INPUT", "unsupported review-check input schema_version"
        )
        return ERROR_EXIT_CODE, payload

    try:
        _assert_document_depth(input_document, "review-check input")
    except (ValueError, RecursionError) as exc:
        return ERROR_EXIT_CODE, error_payload("MALFORMED_INVOCATION", str(exc))
    try:
        _assert_document_depth(policy_document, "review policy")
    except (ValueError, RecursionError) as exc:
        return ERROR_EXIT_CODE, error_payload("CONFIGURATION_ERROR", str(exc))

    try:
        try:
            input_errors = _schema_errors(
                input_document, "review-check-input.schema.json"
            )
        except RecursionError as exc:
            return ERROR_EXIT_CODE, error_payload(
                "MALFORMED_INVOCATION",
                "review-check input nesting exhausted schema validation",
                details={"exception": type(exc).__name__},
            )
        if input_errors:
            return ERROR_EXIT_CODE, error_payload(
                "MALFORMED_INVOCATION",
                "review-check input does not satisfy its public schema",
                details={"issues": input_errors},
            )
        try:
            policy_errors = _schema_errors(policy_document, "review-policy.schema.json")
        except RecursionError as exc:
            return ERROR_EXIT_CODE, error_payload(
                "CONFIGURATION_ERROR",
                "review policy nesting exhausted schema validation",
                details={"exception": type(exc).__name__},
            )
        if policy_errors:
            return ERROR_EXIT_CODE, error_payload(
                "CONFIGURATION_ERROR",
                "review policy does not satisfy its public schema",
                details={"issues": policy_errors},
            )
        try:
            result = evaluate(input_document, policy_document)
        except RecursionError as exc:
            return ERROR_EXIT_CODE, error_payload(
                "MALFORMED_INVOCATION",
                "review-check input nesting exhausted semantic evaluation",
                details={"exception": type(exc).__name__},
            )
        try:
            result_errors = _schema_errors(result, "review-gate-result.schema.json")
        except RecursionError as exc:
            return ERROR_EXIT_CODE, error_payload(
                "TOOL_ERROR",
                "evaluator result nesting exhausted schema validation",
                details={"exception": type(exc).__name__},
            )
        if result_errors:
            return ERROR_EXIT_CODE, error_payload(
                "TOOL_ERROR",
                "evaluator result does not satisfy the public result schema",
                details={"issues": result_errors},
            )
    except ReviewInputError as exc:
        return ERROR_EXIT_CODE, error_payload(exc.code, str(exc), details=exc.details)
    except SchemaError as exc:
        return ERROR_EXIT_CODE, error_payload(
            "CONFIGURATION_ERROR",
            "installed review-assurance schema is invalid",
            details={"schema_error": str(exc)},
        )
    except (KnowledgeFormatError, OSError, ValueError, TypeError) as exc:
        return ERROR_EXIT_CODE, error_payload("CONFIGURATION_ERROR", str(exc))
    outcome = result.get("outcome")
    if not isinstance(outcome, str):
        return ERROR_EXIT_CODE, error_payload(
            "TOOL_ERROR",
            "evaluator returned a semantic result without a string outcome",
            details={"outcome": outcome},
        )
    exit_code = SEMANTIC_EXIT_CODES.get(outcome)
    if exit_code is None:
        return ERROR_EXIT_CODE, error_payload(
            "TOOL_ERROR",
            "evaluator returned an unsupported semantic outcome",
            details={"outcome": outcome},
        )
    return exit_code, result


def _load_json(path: Path) -> object:
    with path.open("rb") as handle:
        raw = handle.read(MAX_REVIEW_INPUT_BYTES + 1)
    if len(raw) > MAX_REVIEW_INPUT_BYTES:
        raise ValueError(
            "review-check input is larger than the "
            f"{MAX_REVIEW_INPUT_BYTES}-byte operational bound"
        )
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"review-check input is not valid UTF-8: {exc}") from exc
    try:
        value = json.loads(
            text,
            object_pairs_hook=_object_without_duplicate_fields,
            parse_constant=_reject_non_finite_constant,
            parse_float=_parse_finite_float,
        )
    except RecursionError as exc:
        raise ValueError(
            "review-check input nesting exhausted the JSON parser"
        ) from exc
    _assert_document_depth(value, "review-check input")
    return value


def _parser() -> argparse.ArgumentParser:
    parser = _ArgumentParser(
        prog="knowledge review-check",
        description="Evaluate deterministic advisory semantic-review assurance over retained file evidence.",
    )
    parser.add_argument(
        "--input", type=Path, required=True, help="review-check input JSON"
    )
    parser.add_argument(
        "--policy",
        type=Path,
        help="historical/file-replay effective policy YAML/JSON or project review-policy source",
    )
    parser.add_argument(
        "--change-class",
        choices=("mechanical", "normal", "normative", "critical", "emergency"),
        help="project specialization when the selected policy source contains change_classes",
    )
    return parser


def _load_policy(path: Path | None, change_class: str | None) -> dict[str, Any]:
    selected = default_project_policy_path() if path is None else path
    loaded = load_review_policy_source(selected)
    if "change_classes" in loaded or "defaults" in loaded:
        if change_class is None:
            raise KnowledgeFormatError(
                "--change-class is required when evaluating a project review-policy source"
            )
        return resolve_loaded_project_policy(loaded, change_class)
    if not isinstance(loaded, dict):
        raise KnowledgeFormatError(f"Review policy must be a mapping in {selected}")
    return loaded


def _current_advisory_bootstrap_issue(
    input_document: object,
    policy_path: Path | None,
) -> str | None:
    if not isinstance(input_document, dict):
        return None
    context = input_document.get("evaluation_context")
    if not isinstance(context, dict) or context.get("mode") != "current_advisory":
        return None
    if policy_path is not None:
        return (
            "current_advisory forbids caller-selected --policy; the protected route "
            "uses only the prior-effective Gnostoa-self policy"
        )
    return None


def _is_protected_current_advisory(input_document: object) -> bool:
    if not isinstance(input_document, dict):
        return False
    context = input_document.get("evaluation_context")
    return (
        isinstance(context, dict)
        and context.get("mode") == "current_advisory"
        and context.get("judge_relation") == "prior_integrated"
    )


def _malformed(message: str) -> tuple[int, dict[str, Any]]:
    return ERROR_EXIT_CODE, error_payload("MALFORMED_INVOCATION", message)


def _configuration(message: str) -> tuple[int, dict[str, Any]]:
    return ERROR_EXIT_CODE, error_payload("CONFIGURATION_ERROR", message)


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(sys.argv[1:] if argv is None else argv)
        input_document = _load_json(args.input.resolve())
    except (ValueError, OSError, json.JSONDecodeError, RecursionError) as exc:
        code, payload = _malformed(str(exc))
    else:
        bootstrap_issue = _current_advisory_bootstrap_issue(
            input_document,
            args.policy,
        )
        if bootstrap_issue is not None:
            code, payload = _configuration(bootstrap_issue)
        elif _is_protected_current_advisory(input_document):
            if args.change_class is not None:
                code, payload = _configuration(
                    "current_advisory prior-integrated forbids caller-selected "
                    "--change-class; protected authority supplies the effective policy"
                )
            else:
                code, payload = _configuration(
                    "current_advisory prior-integrated authority acquisition is not "
                    "available in the candidate-side P2b-B1 CLI; the dormant outer "
                    "consumer must become prior-effective before activation"
                )
        else:
            try:
                policy_document = _load_policy(args.policy, args.change_class)
            except (
                KnowledgeFormatError,
                OSError,
                ValueError,
                TypeError,
                RecursionError,
            ) as exc:
                code, payload = _configuration(str(exc))
            else:
                code, payload = evaluate_documents(input_document, policy_document)
    sys.stdout.write(canonical_json(payload) + "\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
