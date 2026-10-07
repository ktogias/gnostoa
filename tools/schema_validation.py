"""The one JSON Schema validation the toolkit's commands share: registry id `schema-validation`.

A machine-read declaration is checked against an installed schema under `schemas/`, in
Draft 2020-12. Nine commands each did this with their own helper -- eight module
functions such as `_schema`/`_schema_errors`, and one inline (#365). This module owns
the responsibility; extend it, do not write another, and those copies converge on it
under #365's P4.

It is its own module, not part of `knowledge_common`, so that a script importing the
common module never needs `jsonschema` installed.
"""

from __future__ import annotations

import json
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError

from tools.knowledge_common import KnowledgeFormatError, toolkit_root

_FORMAT_CHECKER = FormatChecker()


def load_schema(name: str) -> dict[str, Any]:
    """Return the installed toolkit schema ``name``, checked as a Draft 2020-12 schema."""
    if not name or "/" in name or "\\" in name or name.startswith("."):
        raise KnowledgeFormatError(f"{name!r} does not name an installed schema")
    path = toolkit_root() / "schemas" / name
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError) as exc:
        raise KnowledgeFormatError(f"Cannot load schema {path}: {exc}") from exc
    if not isinstance(loaded, dict):
        raise KnowledgeFormatError(f"Schema must be an object in {path}")
    try:
        Draft202012Validator.check_schema(loaded)
    except (SchemaError, RecursionError) as exc:
        raise KnowledgeFormatError(f"{path} is not a valid schema: {exc}") from exc
    return loaded


def schema_errors(document: object, name: str) -> list[str]:
    """Return each way ``document`` violates schema ``name``, as `location: message`.

    Ordered by location, so a report is stable; `<root>` names the document itself.
    """
    validator = Draft202012Validator(load_schema(name), format_checker=_FORMAT_CHECKER)
    errors = sorted(
        validator.iter_errors(document),
        key=lambda error: [str(part) for part in error.absolute_path],
    )
    return [
        f"{'.'.join(str(part) for part in error.absolute_path) or '<root>'}: "
        f"{error.message}"
        for error in errors
    ]
