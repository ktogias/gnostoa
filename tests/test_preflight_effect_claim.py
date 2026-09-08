"""GREEN boundary tests for the retained fresh-preflight effect claim (#197).

All material is synthetic. The integration cases patch the qualification effect path;
the claim-unit cases operate only on temporary retained workspaces.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from tools.capsule import compiler, effect_claim
from tools.capsule.authority import (
    BASE_REFERENCE_QUALIFICATION,
    PreflightAuthority,
)
from tools.experiment.evidence import canonical_json_bytes

try:
    from test_preflight_authority_consumption import ConsumptionFixture
except ImportError:  # invoked as tests.<module> from the repository root
    from tests.test_preflight_authority_consumption import ConsumptionFixture


class FreshClaimIntegrationTests(ConsumptionFixture):
    def test_second_authority_for_same_candidate_cannot_reopen_effect_path(
        self,
    ) -> None:
        observed = self.prepare()
        candidate = observed.preflight_candidate_sha256
        self.assertIsNotNone(candidate)
        assert candidate is not None
        first_authority = self.authority(candidate)
        second_authority = PreflightAuthority(
            id="auth-197-second",
            experiment_id="E1",
            scope=(BASE_REFERENCE_QUALIFICATION,),
            preflight_candidate_sha256=candidate,
        )

        effects: list[str] = []

        def reached(*args, **kwargs):  # type: ignore[no-untyped-def]
            del args, kwargs
            effects.append("qualify_subjects")
            return [
                {
                    "task": "T1",
                    "code": "synthetic-stop-after-effect-entry",
                    "detail": "focused #197 GREEN",
                }
            ]

        with mock.patch.object(compiler, "qualify_subjects", side_effect=reached):
            self.prepare(authority=first_authority)
            replay = self.prepare(authority=second_authority)

        self.assertEqual(effects, ["qualify_subjects"])
        self.assertIn(
            effect_claim.ALREADY_CONSUMED,
            [blocker["code"] for blocker in replay.blockers],
        )

    def test_authority_less_prepare_creates_no_effect_claim(self) -> None:
        first = self.prepare()
        second = self.prepare()
        self.assertEqual(
            first.preflight_candidate_sha256, second.preflight_candidate_sha256
        )
        self.assertFalse((self.workspace / effect_claim.CLAIM_DIRECTORY).exists())

    def test_all_reuse_candidate_creates_no_effect_claim(self) -> None:
        fresh = self.prepare()
        receipt = self.prior_receipt(fresh)
        reuse = self.prepare(receipt=receipt)
        candidate = reuse.preflight_candidate_sha256
        self.assertIsNotNone(candidate)
        assert candidate is not None

        with mock.patch.object(
            compiler,
            "qualify_subjects",
            side_effect=AssertionError(
                "all-reuse candidate reached fresh qualification"
            ),
        ):
            authorised = self.prepare(
                authority=self.authority(candidate), receipt=receipt
            )

        self.assertTrue(authorised.task("T1").qualification_reused)
        self.assertFalse((self.workspace / effect_claim.CLAIM_DIRECTORY).exists())


class EffectClaimDurabilityTests(unittest.TestCase):
    candidate = "c" * 64
    tasks = (
        {
            "id": "T1",
            "capsule_identity": "d" * 64,
            "qualification_mode": "fresh",
        },
    )

    def setUp(self) -> None:
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        self.authority = PreflightAuthority(
            id="auth-restart",
            experiment_id="E1",
            scope=(BASE_REFERENCE_QUALIFICATION,),
            preflight_candidate_sha256=self.candidate,
        )

    def claim(self, workspace: Path | None = None) -> dict[str, object]:
        return effect_claim.claim_fresh_candidate(
            workspace or self.workspace,
            experiment_id="E1",
            scope=BASE_REFERENCE_QUALIFICATION,
            candidate_sha256=self.candidate,
            authority=self.authority,
            candidate_tasks=self.tasks,
        )

    def test_consumption_survives_a_new_python_process(self) -> None:
        self.claim()
        repository = Path(__file__).resolve().parents[1]
        program = f"""
from pathlib import Path
from tools.capsule import effect_claim
from tools.capsule.authority import BASE_REFERENCE_QUALIFICATION, PreflightAuthority
candidate = {self.candidate!r}
authority = PreflightAuthority(
    id='auth-restart-second-process',
    experiment_id='E1',
    scope=(BASE_REFERENCE_QUALIFICATION,),
    preflight_candidate_sha256=candidate,
)
tasks = ({dict(self.tasks[0])!r},)
try:
    effect_claim.claim_fresh_candidate(
        Path({str(self.workspace)!r}),
        experiment_id='E1',
        scope=BASE_REFERENCE_QUALIFICATION,
        candidate_sha256=candidate,
        authority=authority,
        candidate_tasks=tasks,
    )
except effect_claim.EffectClaimError as exc:
    print(exc.code)
    raise SystemExit(0 if exc.code == effect_claim.ALREADY_CONSUMED else 2)
raise SystemExit(3)
"""
        completed = subprocess.run(
            [sys.executable, "-c", program],
            cwd=repository,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.strip(), effect_claim.ALREADY_CONSUMED)

    def test_malformed_existing_claim_fails_closed(self) -> None:
        directory = self.workspace / effect_claim.CLAIM_DIRECTORY
        directory.mkdir()
        (directory / f"{self.candidate}.json").write_text("{}\n")
        with self.assertRaises(effect_claim.EffectClaimError) as caught:
            self.claim()
        self.assertEqual(caught.exception.code, effect_claim.INVALID_CLAIM)

    def test_non_regular_existing_claim_is_never_followed(self) -> None:
        directory = self.workspace / effect_claim.CLAIM_DIRECTORY
        directory.mkdir()
        outside = self.root / "outside.json"
        outside.write_text("do-not-read-or-replace\n")
        (directory / f"{self.candidate}.json").symlink_to(outside)
        with self.assertRaises(effect_claim.EffectClaimError) as caught:
            self.claim()
        self.assertEqual(caught.exception.code, effect_claim.INVALID_CLAIM)
        self.assertEqual(outside.read_text(), "do-not-read-or-replace\n")

    def test_tampered_canonical_claim_fails_closed(self) -> None:
        self.claim()
        path = self.workspace / effect_claim.CLAIM_DIRECTORY / f"{self.candidate}.json"
        payload = json.loads(path.read_text())
        payload["authority_sha256"] = "0" * 64
        path.write_bytes(canonical_json_bytes(payload))
        with self.assertRaises(effect_claim.EffectClaimError) as caught:
            self.claim()
        self.assertEqual(caught.exception.code, effect_claim.INVALID_CLAIM)

    def test_ambiguous_write_is_not_repaired_into_retry_permission(self) -> None:
        original = effect_claim.os.fsync
        calls = 0

        def fail_first(descriptor: int) -> None:
            nonlocal calls
            calls += 1
            if calls == 2:
                # root-directory fsync is first when the claim directory is created;
                # the claim file fsync is second. Leave the created file in place.
                raise OSError("synthetic durability uncertainty")
            original(descriptor)

        with mock.patch.object(effect_claim.os, "fsync", side_effect=fail_first):
            with self.assertRaises(effect_claim.EffectClaimError) as caught:
                self.claim()
        self.assertEqual(caught.exception.code, effect_claim.WRITE_FAILED)

        with self.assertRaises(effect_claim.EffectClaimError) as replay:
            self.claim()
        self.assertEqual(replay.exception.code, effect_claim.ALREADY_CONSUMED)


if __name__ == "__main__":
    unittest.main()
