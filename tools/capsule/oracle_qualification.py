"""Semantic prequalification of a hidden oracle, without executing it.

The compiler does not judge whether a subject behaves correctly. It requires the
spec to declare a role for every oracle case, and requires every control to cite
where its expected behaviour is already evidenced in the frozen base tree. A
control that asserts an expectation nobody can corroborate is blocked before
execution freeze -- the Phase-D D4 class.

Citations are symbol-scoped, not file-scoped: the spec names the exact function in
the cited file whose behaviour is the evidence, and only strings inside that symbol
can corroborate. An unrelated occurrence of the same value elsewhere in the file
cannot stand in for the relevant behaviour.

Nothing here reads or emits oracle content into a public artifact: only case
names, digests and blocker codes leave this module.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from tools.capsule.spec import Semantics

_JS_CASE = re.compile(r"\b(?:it|test)\(\s*['\"](?P<title>[^'\"]+)['\"]")
_JS_EXPECT = re.compile(
    r"\b(?:toBe|toEqual|toStrictEqual)\(\s*(?P<argument>[^)]{0,400})\)"
)
_JS_STRING = re.compile(r"""(['"])(?P<value>(?:(?!\1).){1,200})\1""")


@dataclass(frozen=True, slots=True)
class OracleCase:
    name: str
    literals: tuple[object, ...]


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
        # Only the asserted expected value counts as the case's expectation. Any
        # other string in the body is incidental setup and must never be able to
        # corroborate a control by accident.
        literals: list[object] = []
        for inner in ast.walk(node):
            if not isinstance(inner, ast.Assert):
                continue
            test = inner.test
            if not isinstance(test, ast.Compare):
                continue
            for operand in (test.left, *test.comparators):
                if isinstance(operand, ast.Constant):
                    literals.append(operand.value)
        cases.append(OracleCase(name=node.name, literals=tuple(literals)))
    return OracleShape(language="python", cases=tuple(cases))


def _javascript_shape(source: str) -> OracleShape:
    cases: list[OracleCase] = []
    matches = list(_JS_CASE.finditer(source))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(source)
        body = source[match.end() : end]
        # Same restriction as Python: only asserted expectations, not incidental strings.
        literals = tuple(
            m.group("value")
            for assertion in _JS_EXPECT.finditer(body)
            for m in _JS_STRING.finditer(assertion.group("argument"))
        )
        cases.append(OracleCase(name=match.group("title"), literals=literals))
    return OracleShape(language="javascript", cases=tuple(cases))


def _symbol_literals(source: str, symbol: str) -> tuple[object, ...] | None:
    """Constants inside the named function, or None when it is absent."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == symbol
        ):
            return tuple(
                inner.value
                for inner in ast.walk(node)
                if isinstance(inner, ast.Constant)
            )
    return None


def _corroborates(
    expected: object, evidence: Sequence[object], substitutions: Mapping[str, str]
) -> bool:
    """A string expectation is compared after declared substitutions; other scalars exactly.

    Booleans and None are never corroborating: they are too common to bind a control
    to a specific behaviour.
    """
    if isinstance(expected, str):
        candidate = expected
        for source_value, evidence_value in substitutions.items():
            candidate = candidate.replace(source_value, evidence_value)
        return bool(candidate) and candidate in [
            item for item in evidence if isinstance(item, str)
        ]
    if expected is None or isinstance(expected, bool):
        return False
    return any(
        type(item) is type(expected) and item == expected
        for item in evidence
        if not isinstance(item, (str, bool))
    )


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
    prior_qualification_sha256: str | None = None,
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

        declared_prior = control.corroboration.prior_qualification_sha256
        if declared_prior is not None:
            if (
                prior_qualification_sha256
                and declared_prior == prior_qualification_sha256
            ):
                continue
            blockers.append(
                {
                    "task": task_id,
                    "code": "prior-qualification-not-current",
                    "detail": (
                        f"control {control.case!r} cites a prior qualification that the task does "
                        "not bind; requalify or cite base-tree evidence"
                    ),
                }
            )
            continue
        assert control.corroboration.path is not None
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

        symbol = control.corroboration.symbol
        if not symbol:
            blockers.append(
                {
                    "task": task_id,
                    "code": "oracle-control-corroboration-symbol-required",
                    "detail": (
                        f"control {control.case!r} cites a file but no symbol; name the exact "
                        "function whose behaviour is the evidence"
                    ),
                }
            )
            continue

        evidence_literals = _symbol_literals(citation.read_text(), symbol)
        if evidence_literals is None:
            blockers.append(
                {
                    "task": task_id,
                    "code": "oracle-control-corroboration-symbol-missing",
                    "detail": (
                        f"control {control.case!r} cites symbol {symbol!r} in "
                        f"{control.corroboration.path!r}, which does not define it"
                    ),
                }
            )
            continue

        substitutions = control.corroboration.value_substitutions
        corroborated = any(
            _corroborates(literal, evidence_literals, substitutions)
            for literal in literals_by_case.get(control.case, ())
        )
        if not corroborated:
            blockers.append(
                {
                    "task": task_id,
                    "code": "oracle-control-not-corroborated",
                    "detail": (
                        f"control {control.case!r} asserts an expectation that does not appear in "
                        f"{control.corroboration.path}::{control.corroboration.symbol} under the "
                        "declared value substitutions; the control may be over-strong for this subject"
                    ),
                }
            )
    return blockers
