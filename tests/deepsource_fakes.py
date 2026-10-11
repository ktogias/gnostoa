"""DeepSource GraphQL fakes for the readback's tests (#309).

Typed and self-contained, so a test module can use them without importing
`test_analyzer_readback`, whose pre-existing findings are excluded from the
cleanup that introduced this module (#309, C).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

HEAD = "a" * 40
RUN_UID = "0c29b163-9e8e-43be-bd8b-a93254aa2748"
OBSERVED = "2026-09-23T13:30:00Z"


class GraphQLFake:
    """Answers the full read's run and check queries by (key, cursor)."""

    def __init__(self, responses: Mapping[tuple[str, str | None], Any]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def graphql(self, query: str, variables: Mapping[str, Any]) -> Mapping[str, Any]:
        values = dict(variables)
        self.calls.append((query, values))
        name = "run" if "AnalyzerRun" in query else str(values.get("id"))
        response: Mapping[str, Any] = self.responses[(name, values.get("cursor"))]
        return response


def check(identifier: str = "check-python", status: str = "FAILURE") -> dict[str, Any]:
    return {"id": identifier, "status": status, "analyzer": {"shortcode": "python"}}


def run_page(
    *,
    checks: list[dict[str, Any]] | None = None,
    total: int | None = 1,
    has_next: bool = False,
    cursor: str | None = None,
    uid: str = RUN_UID,
    head: str = HEAD,
    name: str = "gnostoa",
    status: str = "FAILURE",
) -> dict[str, Any]:
    nodes = [check()] if checks is None else checks
    return {
        "data": {
            "run": {
                "id": "run-node",
                "runUid": uid,
                "commitOid": head,
                "baseOid": "c" * 40,
                "status": status,
                "repository": {
                    "name": name,
                    "account": {"login": "ktogias", "vcsProvider": "GITHUB"},
                },
                "checks": {
                    "totalCount": total,
                    "edges": [{"node": node} for node in nodes],
                    "pageInfo": {"hasNextPage": has_next, "endCursor": cursor},
                },
            }
        }
    }


def check_page(
    issues: list[dict[str, Any]],
    *,
    total: int | None = None,
    has_next: bool = False,
    cursor: str | None = None,
    identifier: str = "check-python",
    status: str = "FAILURE",
) -> dict[str, Any]:
    return {
        "data": {
            "node": {
                "id": identifier,
                "status": status,
                "analyzer": {"shortcode": "python"},
                "issues": {
                    "totalCount": len(issues) if total is None else total,
                    "edges": [{"node": item} for item in issues],
                    "pageInfo": {"hasNextPage": has_next, "endCursor": cursor},
                },
            }
        }
    }


def issue(identifier: str, line: int) -> dict[str, Any]:
    return {
        "id": identifier,
        "path": "tools/example.py",
        "severity": "MAJOR",
        "category": "TYPECHECK",
        "title": f"Issue {identifier}",
        "explanation": "Details",
        "isSuppressed": False,
        "beginLine": line,
        "beginColumn": 1,
        "endLine": line,
        "endColumn": 4,
        "shortcode": "PY-TYPE",
        "issue": {"shortcode": "PY-TYPE", "title": "Type issue"},
    }
