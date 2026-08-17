"""Controls for the C4-v0 readiness-predicate experiment (Gnostoa self-hosted).

Every control replays a real commit that exists in this repository. Negative
controls are the historical false-ready states recorded in the canonical B2/P1
and B2/P2 assessments; positive controls are candidates the owner reviewed and
accepted. Nothing here is public surface: see
`knowledge/decisions/0017-scope-the-readiness-predicate-experiment-to-gnostoa-self-hosting.md`.
"""

from __future__ import annotations

import importlib
import subprocess
import unittest
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
P1 = "tasks/issue-24-b2-p1.yaml"
P2 = "tasks/issue-24-b2-p2.yaml"


@dataclass(frozen=True)
class Control:
    label: str
    commit: str
    envelope: str
    recorded_state: str
    expected: str


#: Historical false-ready states. `expected` is the *measured* verdict, pinned so
#: that later changes cannot silently alter the experiment's recorded result. The
#: hypothesis was that all eight are rejected; three are. The commits for the five
#: P1 states are matched from the canonical record's descriptions to the commit
#: that repaired each defect, because that record names no commits.
NEGATIVE_CONTROLS = (
    Control(
        "P1-1",
        "ef62a008c92e5ad0d9a2c1cd2efe32f2387372f7",
        P1,
        "review-ready while its own declared pre-merge gate was still unrun",
        "indeterminate",
    ),
    Control(
        "P1-2",
        "ee61349bc2a91c65d8138ee8c3f5bf9cc4ae7f18",
        P1,
        "offered for timed review with stale surface accounting",
        "indeterminate",
    ),
    Control(
        "P1-3",
        "3d19ec161244156488b113ed2f39114fddafc384",
        P1,
        "offered while the recursive-alias blocker was still present",
        "indeterminate",
    ),
    Control(
        "P1-4",
        "638bfab670652f75250ffdb6161c00012476dbad",
        P1,
        "offered while the wider error-boundary family was still present",
        "indeterminate",
    ),
    Control(
        "P1-5",
        "24356e0467bd38ac09983ab9830dce2dffa23064",
        P1,
        "offered while the source snapshot was neither single nor bounded",
        "indeterminate",
    ),
    Control(
        "P2-1",
        "96b2f8ca7a49742aa0915676be61c1823a5cf372",
        P2,
        "PR #27 opened while the durable envelope still stood at sequence 1",
        "blocked",
    ),
    Control(
        "P2-2",
        "37fa6e52438b7a00a01e463692dd32e4dc891b9e",
        P2,
        "owner review claimed while schema-invalid with two invented digests",
        "blocked",
    ),
    Control(
        "P2-3",
        "ada708ebc0f459be4eed13757cacf15c8da70137",
        P2,
        "owner review claimed while the required suite was red and two declared "
        "dependency identities were wrong",
        "blocked",
    ),
)

#: Candidates the owner actually reviewed and accepted. None is blocked, and none
#: reaches READY either: every one declares a provider-side identity that no local
#: evidence resolves.
POSITIVE_CONTROLS = (
    Control(
        "POS-1",
        "31266ff96f5beea31f4926e15f6e29611af34194",
        P1,
        "integrated P1 candidate, envelope active at checkpoint 8",
        "indeterminate",
    ),
    Control(
        "POS-2",
        "73909762661bdf81fc3c2c35ad553d13fa25acd1",
        P1,
        "P1 close-out on protected main, terminal at checkpoint 9",
        "indeterminate",
    ),
    Control(
        "POS-3",
        "0e336b49c16d2b8bbef7b9435b683d5df52755a7",
        P2,
        "P2 close-out candidate reviewed by the owner in 7 of 20 minutes",
        "indeterminate",
    ),
    Control(
        "POS-4",
        "ac95c558d70b119df4d635e6531334bf83bab1a9",
        P2,
        "integrated P2 close-out on protected main, terminal at checkpoint 6",
        "indeterminate",
    ),
)


def module():
    return importlib.import_module("experimental_readiness_v0")


def repository_is_replayable() -> bool:
    """True when every control commit is present.

    A guard that cannot tell "history absent" from "git refused to run" turns an
    environment failure into a silent skip, which is how a suite reports success
    without exercising its subject. Only a clean `cat-file` miss counts as
    absent history; anything else is left to fail loudly during evaluation.
    """
    commits = [control.commit for control in (*NEGATIVE_CONTROLS, *POSITIVE_CONTROLS)]
    for commit in commits:
        probe = subprocess.run(
            [
                "git",
                "-c",
                f"safe.directory={ROOT.resolve()}",
                "-C",
                str(ROOT),
                "cat-file",
                "-e",
                f"{commit}^{{commit}}",
            ],
            capture_output=True,
            check=False,
        )
        if probe.returncode != 0:
            if probe.stderr.strip():
                return True
            return False
    return True


@unittest.skipUnless(
    repository_is_replayable(),
    "control commits are not present in this clone",
)
class ReadinessPredicateControlTests(unittest.TestCase):
    def verdict(self, control: Control) -> str:
        result = module().evaluate(ROOT, control.commit, control.envelope)
        return result.verdict.value

    def test_replayed_controls_produce_the_measured_verdicts(self) -> None:
        for control in (*NEGATIVE_CONTROLS, *POSITIVE_CONTROLS):
            with self.subTest(control=control.label):
                self.assertEqual(
                    control.expected,
                    self.verdict(control),
                    f"{control.label}: {control.recorded_state}",
                )

    def test_no_recorded_false_ready_state_is_called_ready(self) -> None:
        for control in NEGATIVE_CONTROLS:
            with self.subTest(control=control.label):
                self.assertNotEqual("ready", self.verdict(control))

    def test_no_owner_accepted_state_is_blocked(self) -> None:
        for control in POSITIVE_CONTROLS:
            with self.subTest(control=control.label):
                self.assertNotEqual("blocked", self.verdict(control))

    def test_measured_coverage_is_three_of_eight_with_no_false_blocks(self) -> None:
        rejected = [c for c in NEGATIVE_CONTROLS if self.verdict(c) == "blocked"]
        undecided = [c for c in NEGATIVE_CONTROLS if self.verdict(c) == "indeterminate"]
        falsely_blocked = [c for c in POSITIVE_CONTROLS if self.verdict(c) == "blocked"]
        reaching_ready = [c for c in POSITIVE_CONTROLS if self.verdict(c) == "ready"]
        self.assertEqual(3, len(rejected))
        self.assertEqual(5, len(undecided))
        self.assertEqual(0, len(falsely_blocked))
        self.assertEqual(0, len(reaching_ready))

    def test_every_positive_control_is_undecidable_on_a_provider_identity(self) -> None:
        readiness = module()
        for control in POSITIVE_CONTROLS:
            with self.subTest(control=control.label):
                result = readiness.evaluate(ROOT, control.commit, control.envelope)
                self.assertEqual(
                    readiness.Decision.UNDECIDABLE,
                    result.decision(readiness.DEPENDENCIES_RECOMPUTE),
                )


class FailClosedCombinationTests(unittest.TestCase):
    def check(self, decision: str):
        readiness = module()
        return readiness.Check("probe", readiness.Decision(decision), "probe")

    def test_ready_requires_every_precondition_to_be_decided_satisfied(self) -> None:
        readiness = module()
        self.assertEqual(
            readiness.Verdict.READY,
            readiness._combine((self.check("satisfied"), self.check("satisfied"))),
        )

    def test_an_undecidable_precondition_never_yields_ready(self) -> None:
        readiness = module()
        self.assertEqual(
            readiness.Verdict.INDETERMINATE,
            readiness._combine((self.check("satisfied"), self.check("undecidable"))),
        )

    def test_a_violation_outranks_an_undecidable_precondition(self) -> None:
        readiness = module()
        self.assertEqual(
            readiness.Verdict.BLOCKED,
            readiness._combine((self.check("undecidable"), self.check("violated"))),
        )


if __name__ == "__main__":
    unittest.main()
