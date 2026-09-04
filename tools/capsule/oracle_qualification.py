"""Semantic prequalification of a hidden oracle, without executing it.

The compiler does not judge whether a subject behaves correctly. It requires the
spec to declare a role for every oracle case, and requires every control to cite
where its expected behaviour is already evidenced in the frozen base tree. A
control that asserts an expectation nobody can corroborate is blocked before
execution freeze -- the Phase-D D4 class.

Nothing here reads or emits oracle content into a public artifact: only case
names, digests and blocker codes leave this module.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from tools.capsule.spec import Semantics

_JS_CASE = re.compile(r"\b(?:it|test)\(\s*['\"](?P<title>[^'\"]+)['\"]")
_JS_STRING = re.compile(r"""(['"])(?P<value>(?:(?!\1).){1,200})\1""")


@dataclass(frozen=True, slots=True)
class OracleCase:
    name: str
    literals: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class OracleShape:
    language: str
    cases: tuple[OracleCase, ...]

    def case_names(self) -> tuple[str, ...]:
        return tuple(case.name for case in self.cases)

    def as_json(self) -> dict[str, object]:
        # Case names only. Asserted literals stay inside the private boundary.
        return {"language": self.language, "cases": list(self.case_names())}


def _python_shape(source: str) -> OracleShape:
    tree = ast.parse(source)
    cases: list[OracleCase] = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or not node.name.startswith("test"):
            continue
        literals: list[str] = []
        for inner in ast.walk(node):
            if isinstance(inner, ast.Constant) and isinstance(inner.value, str):
                literals.append(inner.value)
        cases.append(OracleCase(name=node.name, literals=tuple(literals)))
    return OracleShape(language="python", cases=tuple(cases))


def _javascript_shape(source: str) -> OracleShape:
    cases: list[OracleCase] = []
    matches = list(_JS_CASE.finditer(source))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(source)
        body = source[match.end() : end]
        literals = tuple(m.group("value") for m in _JS_STRING.finditer(body))
        cases.append(OracleCase(name=match.group("title"), literals=literals))
    return OracleShape(language="javascript", cases=tuple(cases))


def read_shape(path: Path) -> OracleShape:
    source = path.read_text()
    if path.suffix == ".py":
        return _python_shape(source)
    return _javascript_shape(source)


def qualify(
    shape: OracleShape,
    semantics: Semantics,
    *,
    base_tree: Path,
    task_id: str,
) -> list[dict[str, object]]:
    """Return structured blockers. An empty list means the oracle prequalifies."""
    blockers: list[dict[str, object]] = []
    declared_controls = {control.case: control for control in semantics.controls}
    declared = set(semantics.discriminator_cases) | set(declared_controls)

    for name in shape.case_names():
        if name not in declared:
            blockers.append(
                {
                    "task": task_id,
                    "code": "oracle-case-undeclared",
                    "detail": (
                        f"oracle case {name!r} has no declared role; declare it as a "
                        "discriminator case or as a control with corroboration"
                    ),
                }
            )

    present = set(shape.case_names())
    for name in semantics.discriminator_cases:
        if name not in present:
            blockers.append(
                {
                    "task": task_id,
                    "code": "declared-discriminator-absent-from-oracle",
                    "detail": f"declared discriminator case {name!r} is not present in the oracle",
                }
            )

    literals_by_case = {case.name: case.literals for case in shape.cases}
    for control in semantics.controls:
        if control.case not in present:
            blockers.append(
                {
                    "task": task_id,
                    "code": "declared-control-absent-from-oracle",
                    "detail": f"declared control case {control.case!r} is not present in the oracle",
                }
            )
            continue
        if control.corroboration is None:
            blockers.append(
                {
                    "task": task_id,
                    "code": "oracle-control-not-corroborated",
                    "detail": (
                        f"control {control.case!r} declares no corroboration; a control must "
                        "cite where its expected behaviour is already evidenced in the base tree"
                    ),
                }
            )
            continue

        citation = base_tree / control.corroboration.path
        if not citation.is_file():
            blockers.append(
                {
                    "task": task_id,
                    "code": "oracle-control-corroboration-path-missing",
                    "detail": (
                        f"control {control.case!r} cites {control.corroboration.path!r}, "
                        "which is not a file in the frozen base tree"
                    ),
                }
            )
            continue

        evidence = citation.read_text()
        substitutions = control.corroboration.value_substitutions
        corroborated = False
        for literal in literals_by_case.get(control.case, ()):
            candidate = literal
            for source_value, evidence_value in substitutions.items():
                candidate = candidate.replace(source_value, evidence_value)
            if candidate and candidate in evidence:
                corroborated = True
                break
        if not corroborated:
            blockers.append(
                {
                    "task": task_id,
                    "code": "oracle-control-not-corroborated",
                    "detail": (
                        f"control {control.case!r} asserts an expectation that does not appear in "
                        f"{control.corroboration.path!r} under the declared value substitutions; "
                        "the control may be over-strong for this subject"
                    ),
                }
            )
    return blockers
