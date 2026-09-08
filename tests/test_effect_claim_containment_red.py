"""RED for the effect claim's filename, at 4ac101c7.

The claim is the single-use fence #197 rests on. Both public entry points build its
filename by interpolating the candidate identifier:

    name = f"{candidate_sha256}.json"

and open it with ``dir_fd``, which does not confine a name: ``..`` and ``/`` still
traverse from it, and ``O_NOFOLLOW`` guards only the final component. An identifier
that is not an identifier therefore places the fence somewhere else, and a fence
somewhere else is not a fence.

This is the class already closed in ``retained_commit``, where a transaction id and a
candidate read back from a record are both validated before they address anything.
``effect_claim`` is the module that actually turns a candidate into a path and
validates neither.

Nothing here writes outside the test's own temporary tree: the escape targets are
directories beside the workspace, inside that tree, and every case asserts they stay
untouched.

At head 4ac101c7ab875039425528451cdb8c3d568e6916 the refusals are expected to be RED
and the positive case green.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from tools.capsule import authority as authority_module
from tools.capsule import effect_claim
from tools.capsule.identity import digest_of

try:
    from test_preflight_authority_consumption import ConsumptionFixture
except ImportError:  # invoked as tests.<module> from the repository root
    from tests.test_preflight_authority_consumption import ConsumptionFixture

_TASKS = ({"id": "T1", "capsule_identity": "c" * 64, "qualification_mode": "fresh"},)


class ClaimNameContainmentTests(ConsumptionFixture):
    """A candidate identifier is an identifier, never a path."""

    def setUp(self) -> None:
        super().setUp()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.outside = self.root / "outside-the-workspace"
        self.outside.mkdir(parents=True, exist_ok=True)

    def _authority(self, candidate: str) -> authority_module.PreflightAuthority:
        return authority_module.PreflightAuthority(
            id="auth-197",
            experiment_id="E1",
            scope=(authority_module.BASE_REFERENCE_QUALIFICATION,),
            preflight_candidate_sha256=candidate,
        )

    def _claim_directory(self) -> Path:
        return self.workspace / effect_claim.CLAIM_DIRECTORY

    def _assert_nothing_escaped(self) -> None:
        self.assertEqual(
            sorted(entry.name for entry in self.outside.iterdir()),
            [],
            "no claim may be created outside the retained workspace",
        )
        directory = self._claim_directory()
        if directory.is_dir():
            self.assertEqual(
                sorted(entry.name for entry in directory.iterdir()),
                [],
                "a refused identifier must leave no claim behind",
            )

    def _refused(self, candidate: str) -> None:
        with self.assertRaises(effect_claim.EffectClaimError) as raised:
            effect_claim.claim_fresh_candidate(
                self.workspace,
                experiment_id="E1",
                scope=authority_module.BASE_REFERENCE_QUALIFICATION,
                candidate_sha256=candidate,
                authority=self._authority(candidate),
                candidate_tasks=_TASKS,
            )
        self.assertEqual(raised.exception.code, effect_claim.INVALID_CLAIM)
        self.assertIn(
            "not a preflight candidate identifier",
            raised.exception.detail,
            "the refusal must be about the identifier, not a downstream symptom",
        )
        self._assert_nothing_escaped()

    def test_a_traversing_identifier_is_refused(self) -> None:
        self._refused("../../outside-the-workspace/escaped")

    def test_an_absolute_identifier_is_refused(self) -> None:
        # Absolute paths ignore dir_fd entirely, so this one would not even be
        # relative to the claim directory.
        self._refused(str(self.outside / "absolute"))

    def test_a_nested_identifier_is_refused(self) -> None:
        self._refused("a" * 32 + "/" + "b" * 31)

    def test_identifiers_that_are_not_digests_are_refused(self) -> None:
        for candidate in (
            "",
            "a" * 63,
            "a" * 65,
            "A" * 64,
            "g" * 64,
            " " + "a" * 63,
            "." * 64,
        ):
            with self.subTest(candidate=candidate):
                self._refused(candidate)

    def test_reading_a_consumed_candidate_refuses_the_same_identifiers(self) -> None:
        for candidate in ("../../outside-the-workspace/escaped", "A" * 64, "a" * 63):
            with self.subTest(candidate=candidate):
                with self.assertRaises(effect_claim.EffectClaimError) as raised:
                    effect_claim.load_consumed_candidate(
                        self.workspace,
                        experiment_id="E1",
                        scope=authority_module.BASE_REFERENCE_QUALIFICATION,
                        candidate_sha256=candidate,
                        candidate_tasks=_TASKS,
                    )
                self.assertEqual(raised.exception.code, effect_claim.INVALID_CLAIM)
                # The code alone proves nothing here: an absent claim is refused with
                # the same code, so an unvalidated name would look identical. The
                # refusal has to be about the identifier.
                self.assertIn(
                    "not a preflight candidate identifier",
                    raised.exception.detail,
                )
                self._assert_nothing_escaped()

    def test_a_real_digest_still_claims_and_reads_back(self) -> None:
        """Positive regression: the contract is unchanged for a genuine identifier."""
        candidate = digest_of({"candidate": "synthetic"})
        self.assertRegex(candidate, r"^[0-9a-f]{64}$")

        effect_claim.claim_fresh_candidate(
            self.workspace,
            experiment_id="E1",
            scope=authority_module.BASE_REFERENCE_QUALIFICATION,
            candidate_sha256=candidate,
            authority=self._authority(candidate),
            candidate_tasks=_TASKS,
        )
        self.assertEqual(
            sorted(entry.name for entry in self._claim_directory().iterdir()),
            [f"{candidate}.json"],
        )
        self.assertEqual(sorted(entry.name for entry in self.outside.iterdir()), [])

        # A genuine identifier must pass the name check and be refused, if at all,
        # for a substantive reason. Reading a consumed candidate additionally
        # cross-checks the retained stage ledger, which this synthetic workspace does
        # not have; the end-to-end read-back is covered by the retained-consumption
        # regressions. What matters here is that it is not turned away as a name.
        with self.assertRaises(effect_claim.EffectClaimError) as reading:
            effect_claim.load_consumed_candidate(
                self.workspace,
                experiment_id="E1",
                scope=authority_module.BASE_REFERENCE_QUALIFICATION,
                candidate_sha256=candidate,
                candidate_tasks=_TASKS,
            )
        self.assertIn("stage ledger", reading.exception.detail)

        with self.assertRaises(effect_claim.EffectClaimError) as raised:
            effect_claim.claim_fresh_candidate(
                self.workspace,
                experiment_id="E1",
                scope=authority_module.BASE_REFERENCE_QUALIFICATION,
                candidate_sha256=candidate,
                authority=self._authority(candidate),
                candidate_tasks=_TASKS,
            )
        self.assertEqual(raised.exception.code, effect_claim.ALREADY_CONSUMED)


if __name__ == "__main__":
    unittest.main()
