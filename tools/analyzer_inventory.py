"""The diagnostic inventory as two analyzer readbacks (#389 A0-MP1; Decision 0118).

The inventory (`tools/quality_evidence.py`) is the project's own analyzer: protected
main's code and hash-locked tools over a Pull Request head, read as data. Like each
provider's adapter, this translates its native record into the existing readback
contract, so nothing downstream branches on it.

It partitions the findings and never filters them. A finding in a path the
comparison changed is the DIFF readback's, whatever its line (fix-on-touch); every
other finding is the FULL readback's, one that mypy reported through a followed
import among them. Each obtained finding is therefore listed exactly once and keeps
reaching M17 (the PAO's R1 and R4 on #389 6387305292). Neither readback claims more
than the inventory's own composite coverage.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .analyzer_readback import AnalyzerReadbackError, build_readback, coverage
from .quality_evidence import DIAGNOSTIC_SCHEMA
from .review_model import canonical_digest

PROVIDER = "gnostoa-inventory"
ADAPTER = "gnostoa-diagnostic-inventory/v3"
_SCOPES = (("DIFF", "DIFF_LOCAL"), ("FULL", "FULL_RUN"))
_NO_COMPARISON = "no comparison with a base, so the changed paths are unknown"


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise AnalyzerReadbackError(f"the inventory's {label} must be an object")
    return value


def _changed_paths(scope: Mapping[str, Any]) -> frozenset[str] | None:
    """The paths the inventory's comparison changed, or None when it made none."""
    diff = scope.get("diff")
    if diff is None:
        return None
    paths = _mapping(diff, "comparison").get("changed_paths")
    if not isinstance(paths, list) or not all(isinstance(p, str) for p in paths):
        raise AnalyzerReadbackError("the inventory's changed paths must be text")
    return frozenset(paths)


def _gap(inventory: Mapping[str, Any], requested_head: str) -> str | None:
    """Why no readback of this inventory is COMPLETE, or None: another commit than
    the requested head, or a composite that is not COMPLETE, whose own reason it is."""
    revision = _mapping(inventory.get("source"), "source").get("revision")
    if revision != requested_head:
        return "the inventory analyzed another commit than the requested head"
    composite = _mapping(inventory.get("coverage"), "coverage")
    if composite.get("status") == "COMPLETE":
        return None
    reason = composite.get("reason")
    if isinstance(reason, str) and reason:
        return reason
    return f"the inventory's coverage is {composite.get('status')!r}"


def readbacks(
    record: object,
    *,
    repository: str,
    pull_number: int,
    requested_head: str,
    observed_at: str,
) -> list[dict[str, Any]]:
    """The DIFF and the FULL readback of one inventory record, in that order."""
    inventory = _mapping(record, "record")
    if inventory.get("schema") != DIAGNOSTIC_SCHEMA:
        raise AnalyzerReadbackError(
            f"the inventory schema must be {DIAGNOSTIC_SCHEMA!r}"
        )
    findings = inventory.get("findings")
    if not isinstance(findings, list):
        raise AnalyzerReadbackError("the inventory's findings must be an array")
    for finding in findings:
        _mapping(finding, "finding")
    source = _mapping(inventory.get("source"), "source")
    changed = _changed_paths(_mapping(inventory.get("scope"), "scope"))
    touched = [f for f in findings if changed is not None and f.get("path") in changed]
    rest = [f for f in findings if changed is None or f.get("path") not in changed]
    gap = _gap(inventory, requested_head)
    revision = source.get("revision")
    profile = _mapping(inventory.get("configuration"), "configuration").get("profile")
    common: dict[str, Any] = {
        "repository": repository,
        "pull_number": pull_number,
        "requested_head": requested_head,
        "observed_head": revision if isinstance(revision, str) else None,
        "analysis_id": canonical_digest(inventory),
        "observed_at": observed_at,
        # The run seen is the requested head's, or another subject's, as the provider
        # adapters say of a head they did not observe; coverage says the rest.
        "run_state": "COMPLETE" if revision == requested_head else "UNKNOWN",
        "native": {
            "profile": _mapping(profile, "profile").get("digest"),
            "source_binding": source.get("source_binding"),
            "tree": source.get("tree"),
        },
    }
    diff_gap = gap or (_NO_COMPARISON if changed is None else None)
    return [
        _readback("DIFF", "DIFF_LOCAL", diff_gap, touched, common),
        _readback("FULL", "FULL_RUN", gap, rest, common),
    ]


def _readback(
    scope: str,
    kind: str,
    gap: str | None,
    findings: Sequence[Mapping[str, Any]],
    common: Mapping[str, Any],
) -> dict[str, Any]:
    return build_readback(
        provider=PROVIDER,
        adapter=ADAPTER,
        scope=scope,
        completeness=kind if gap is None else "AMBIGUOUS",
        native_mode=kind,
        coverage_record=coverage(
            "COMPLETE" if gap is None else "INCOMPLETE",
            pages=1,
            count=len(findings),
            reason=gap,
        ),
        findings=findings,
        **common,
    )


def unavailable(
    *,
    repository: str,
    pull_number: int,
    requested_head: str,
    observed_at: str,
    reason: str,
) -> list[dict[str, Any]]:
    """The two readbacks of an inventory that was not written: no finding is known,
    so none is listed and neither readback is complete."""
    return [
        build_readback(
            provider=PROVIDER,
            adapter=ADAPTER,
            repository=repository,
            pull_number=pull_number,
            requested_head=requested_head,
            observed_head=None,
            analysis_id=None,
            scope=scope,
            completeness="READBACK_UNAVAILABLE",
            native_mode=kind,
            observed_at=observed_at,
            run_state="UNKNOWN",
            coverage_record=coverage("ERROR", pages=0, count=0, reason=reason),
            findings=[],
        )
        for scope, kind in _SCOPES
    ]
