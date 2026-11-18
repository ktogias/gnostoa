"""Characterization of three capsule functions before their extraction (Decision 0126).

Each test reaches its function through the public API and pins behaviour that the
pre-change mutant table left unpinned (#389 6567727855):
- `discover_preparation`'s file-presence branch, and its refusal of an empty version-file
  key;
- the retained claim's refusals of malformed task records and of disagreeing backends;
- `qualify`'s blocker for each way a declared control can fail.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from collections.abc import Mapping
from pathlib import Path

from tools.capsule.authority import PreflightAuthority
from tools.capsule.effect_claim import (
    INVALID_CLAIM,
    EffectClaimError,
    claim_fresh_candidate,
    load_consumed_candidate,
)
from tools.capsule.identity import digest_of
from tools.capsule.oracle_qualification import OracleCase, OracleShape, qualify
from tools.capsule.preparation import discover_preparation
from tools.capsule.spec import Control, Corroboration, Semantics

_SCM = "[tool.setuptools_scm]\n{keys}\n"


class PreparationDiscoveryTests(unittest.TestCase):
    """Which declared version files the frozen tree is missing."""

    def _tree(self, keys: str) -> Path:
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        (root / "pyproject.toml").write_text(_SCM.format(keys=keys))
        return root

    def test_without_frozen_paths_file_presence_decides(self) -> None:
        tree = self._tree('write_to = "src/pkg/_version.py"')
        missing = discover_preparation(tree)
        self.assertTrue(missing.required)
        self.assertEqual(("src/pkg/_version.py",), missing.generated_paths)

        (tree / "src" / "pkg").mkdir(parents=True)
        (tree / "src" / "pkg" / "_version.py").write_text("version = '0'\n")
        present = discover_preparation(tree)
        self.assertFalse(present.required)
        self.assertEqual("setuptools-scm-version-file", present.kind)
        self.assertEqual((), present.generated_paths)

    def test_an_empty_version_file_key_is_not_a_target(self) -> None:
        tree = self._tree('write_to = ""\nversion_file = "src/pkg/_version.py"')
        requirement = discover_preparation(tree, frozen_paths=frozenset())
        self.assertTrue(requirement.required)
        self.assertEqual(("src/pkg/_version.py",), requirement.generated_paths)


_CANDIDATE = "c" * 64
_EXPERIMENT = "experiment-1"
_SCOPE = "base-reference"
_AUTHORITY = PreflightAuthority(
    id="authority-1",
    experiment_id=_EXPERIMENT,
    scope=(_SCOPE,),
    preflight_candidate_sha256=_CANDIDATE,
)


class RetainedClaimBindingTests(unittest.TestCase):
    """The retained claim binds the authority that completed qualification."""

    def _workspace(
        self,
        tasks: Mapping[str, object],
        stage_authority: PreflightAuthority = _AUTHORITY,
    ) -> Path:
        workspace = Path(self.enterContext(tempfile.TemporaryDirectory()))
        candidate_tasks = [
            {"id": task, "qualification_mode": "fresh"} for task in tasks
        ]
        claim_fresh_candidate(
            workspace,
            experiment_id=_EXPERIMENT,
            scope=_SCOPE,
            candidate_sha256=_CANDIDATE,
            authority=_AUTHORITY,
            candidate_tasks=candidate_tasks,
        )
        capsules = {
            task: record["capsule_identity"]
            for task, record in tasks.items()
            if isinstance(record, dict)
        }
        stage_inputs = {
            "authority": stage_authority.as_json(),
            "preflight_candidate_sha256": _CANDIDATE,
            "authorised_candidate_sha256": _CANDIDATE,
            "backend": "oci",
            "capsules": capsules,
        }
        stage = {"status": "COMPLETE", "inputs_sha256": digest_of(stage_inputs)}
        (workspace / "stages.json").write_text(
            json.dumps({"records": {"BASE_REFERENCE_QUALIFIED": stage}})
        )
        state = {"preflight_candidate_sha256": _CANDIDATE, "tasks": dict(tasks)}
        (workspace / "experiment-state.json").write_text(json.dumps(state))
        return workspace

    @staticmethod
    def _load(workspace: Path, tasks: Mapping[str, object]) -> dict[str, object]:
        return load_consumed_candidate(
            workspace,
            experiment_id=_EXPERIMENT,
            scope=_SCOPE,
            candidate_sha256=_CANDIDATE,
            candidate_tasks=[
                {"id": task, "qualification_mode": "fresh"} for task in tasks
            ],
        )

    def test_a_complete_retained_state_binds_the_claim(self) -> None:
        tasks = {
            "task-1": {
                "capsule_identity": "capsule-1",
                "qualification": {"backend": "oci"},
            }
        }
        payload = self._load(self._workspace(tasks), tasks)
        self.assertEqual(_AUTHORITY.as_json(), payload["authority"])

    def test_each_malformed_task_record_is_refused_by_its_own_message(self) -> None:
        cases: dict[str, tuple[object, str]] = {
            "an empty capsule identity": (
                {"capsule_identity": "", "qualification": {"backend": "oci"}},
                "has no capsule identity",
            ),
            "no qualification receipt": (
                {"capsule_identity": "capsule-1"},
                "has no qualification receipt",
            ),
            "an empty backend": (
                {"capsule_identity": "capsule-1", "qualification": {"backend": ""}},
                "has no qualification backend",
            ),
        }
        for label, (record, message) in cases.items():
            tasks = {"task-1": record}
            with self.subTest(label):
                workspace = self._workspace(tasks)
                with self.assertRaisesRegex(EffectClaimError, message) as refused:
                    self._load(workspace, tasks)
                self.assertEqual(INVALID_CLAIM, refused.exception.code)

    def test_disagreeing_backends_are_refused(self) -> None:
        tasks = {
            "task-1": {
                "capsule_identity": "capsule-1",
                "qualification": {"backend": "oci"},
            },
            "task-2": {
                "capsule_identity": "capsule-2",
                "qualification": {"backend": "process"},
            },
        }
        workspace = self._workspace(tasks)
        with self.assertRaisesRegex(
            EffectClaimError, "disagree on qualification backend"
        ) as refused:
            self._load(workspace, tasks)
        self.assertEqual(INVALID_CLAIM, refused.exception.code)

    def test_a_stage_another_authority_completed_is_refused(self) -> None:
        tasks = {
            "task-1": {
                "capsule_identity": "capsule-1",
                "qualification": {"backend": "oci"},
            }
        }
        other = PreflightAuthority(
            id="authority-2",
            experiment_id=_EXPERIMENT,
            scope=(_SCOPE,),
            preflight_candidate_sha256=_CANDIDATE,
        )
        workspace = self._workspace(tasks, stage_authority=other)
        with self.assertRaisesRegex(
            EffectClaimError, "does not bind the completed qualification stage"
        ) as refused:
            self._load(workspace, tasks)
        self.assertEqual(INVALID_CLAIM, refused.exception.code)


def _shape(*cases: tuple[str, tuple[object, ...]]) -> OracleShape:
    return OracleShape(
        language="python",
        cases=tuple(
            OracleCase(name=name, literals=literals) for name, literals in cases
        ),
    )


def _semantics(*controls: Control) -> Semantics:
    return Semantics(
        requirement="the requirement",
        discriminator_cases=("test_discriminator",),
        behavior_paths=(),
        controls=controls,
    )


class OracleControlQualificationTests(unittest.TestCase):
    """The blocker each way a declared control can fail, and none when it holds."""

    def setUp(self) -> None:
        self.base = Path(self.enterContext(tempfile.TemporaryDirectory()))
        (self.base / "evidence.py").write_text(
            "def evidenced():\n    return 'expected value'\n"
        )

    def _codes(
        self,
        control: Control,
        literals: tuple[object, ...] = ("expected value",),
        prior: str | None = None,
        with_control_case: bool = True,
    ) -> list[object]:
        cases = [("test_discriminator", ())] + [
            ("test_control", literals)
        ] * with_control_case
        shape = _shape(*cases)
        blockers = qualify(
            shape,
            _semantics(control),
            base_tree=self.base,
            task_id="task-1",
            prior_qualification_sha256=prior,
        )
        return [blocker["code"] for blocker in blockers]

    def test_a_corroborated_control_has_no_blocker(self) -> None:
        cited = Corroboration(path="evidence.py", symbol="evidenced")
        self.assertEqual([], self._codes(Control("test_control", cited)))

    def test_each_failing_control_names_its_own_blocker(self) -> None:
        cases: dict[str, tuple[Control, str]] = {
            "a control case the oracle lacks": (
                Control(
                    "test_absent", Corroboration(path="evidence.py", symbol="evidenced")
                ),
                "declared-control-absent-from-oracle",
            ),
            "no corroboration": (
                Control("test_control", None),
                "oracle-control-not-corroborated",
            ),
            "a cited file that does not exist": (
                Control(
                    "test_control", Corroboration(path="missing.py", symbol="evidenced")
                ),
                "oracle-control-corroboration-path-missing",
            ),
            "a file cited without a symbol": (
                Control("test_control", Corroboration(path="evidence.py")),
                "oracle-control-corroboration-symbol-required",
            ),
            "a symbol the file does not define": (
                Control(
                    "test_control", Corroboration(path="evidence.py", symbol="absent")
                ),
                "oracle-control-corroboration-symbol-missing",
            ),
        }
        for label, (control, code) in cases.items():
            with self.subTest(label):
                in_oracle = control.case == "test_control"
                self.assertEqual(
                    [code], self._codes(control, with_control_case=in_oracle)
                )

    def test_a_prior_qualification_must_be_the_one_the_task_binds(self) -> None:
        control = Control(
            "test_control", Corroboration(prior_qualification_sha256="a" * 64)
        )
        self.assertEqual([], self._codes(control, prior="a" * 64))
        self.assertEqual(
            ["prior-qualification-not-current"], self._codes(control, prior="b" * 64)
        )
        self.assertEqual(["prior-qualification-not-current"], self._codes(control))

    def test_one_corroborating_literal_is_enough(self) -> None:
        cited = Corroboration(path="evidence.py", symbol="evidenced")
        literals: tuple[object, ...] = ("expected value", "another value")
        self.assertEqual([], self._codes(Control("test_control", cited), literals))


if __name__ == "__main__":
    unittest.main()
