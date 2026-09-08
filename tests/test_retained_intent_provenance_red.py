"""RED for intent provenance across repeated observations, at f4b3da5.

Publication itself is now one coherent observation, but resolving an interrupted
one is still several, and the checks between them are weaker than the records they
read:

  * a reservation alongside a durable intent is tolerated when it carries no seal
    at all, so removing the seal and rewriting valid JSON downgrades recovery
    provenance from the bytes back to the request identities;
  * a publisher that never reserved -- which is why the intent exists as its own
    record -- has nothing but the intent, and the staged output is re-read after
    the intent has been checked, so a complete self-consistent replacement can be
    published in its place and the intent rewritten to name it.

Both are the same family as the last finding: content identity has to hold across
repeated observations, not only within one of them.

The fixtures are synthetic and the qualification effect is patched and counted; no
Phase-D material, hidden oracle, runner or container effect participates.

At head f4b3da5443298b6c986e07557fd28786c2ec7af9 these are expected to be RED.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from tools.capsule import compiler, qualification, retained_commit

try:
    from test_preflight_authority_consumption import ConsumptionFixture
except ImportError:  # invoked as tests.<module> from the repository root
    from tests.test_preflight_authority_consumption import ConsumptionFixture


def _receipt(task_id: str, bound: dict[str, str]) -> qualification.QualificationReceipt:
    base = qualification.SubjectOutcome(
        subject="base",
        collected=True,
        passed=(),
        failed=("test_discriminates",),
        error_types={},
        classification=qualification.MATCH,
        detail="synthetic",
    )
    reference = qualification.SubjectOutcome(
        subject="reference",
        collected=True,
        passed=("test_discriminates",),
        failed=(),
        error_types={},
        classification=qualification.MATCH,
        detail="synthetic",
    )
    return qualification.QualificationReceipt(
        task=task_id,
        backend="local-python",
        base=base,
        reference=reference,
        bound=bound,
    )


class IntentProvenanceFixture(ConsumptionFixture):
    SUBSTITUTED = '{"substituted": true}\n'

    def patched_effect(self, effects: list[str]) -> Any:
        def qualify(*args: object, **kwargs: object) -> Any:
            del args
            effects.append("effect")
            task_id = kwargs.get("task_id", "T1")
            bound = kwargs.get("bound") or {}
            assert isinstance(task_id, str)
            assert isinstance(bound, dict)
            return _receipt(task_id, dict(bound))

        return mock.patch.object(compiler, "qualify_subjects", side_effect=qualify)

    def crash_before_the_first_canonical_write(self) -> Any:
        real_write = retained_commit._write_atomic

        def crash(path: Path, payload: bytes) -> None:
            if (
                path.parent == self.workspace
                and path.name == retained_commit.LEDGER_FILENAME
            ):
                raise RuntimeError("crash after the intent, before publishing")
            return real_write(path, payload)

        return mock.patch.object(retained_commit, "_write_atomic", side_effect=crash)

    def substitute(self, transaction: str) -> None:
        """Replace <txid> with a complete, self-consistent directory of its own."""
        original = retained_commit.staging_directory(self.workspace, transaction)
        replacement = original.with_name("substituted")
        shutil.copytree(original, replacement)
        (replacement / retained_commit.STATE_FILENAME).write_text(self.SUBSTITUTED)
        manifest_path = replacement / retained_commit.MANIFEST_FILENAME
        manifest = json.loads(manifest_path.read_text())
        manifest["state_file_sha256"] = hashlib.sha256(
            self.SUBSTITUTED.encode()
        ).hexdigest()
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        original.rename(original.with_name("displaced"))
        replacement.rename(original)

    def assert_preserved(self, transaction: str, before: str, result: Any) -> None:
        self.assertNotEqual(result.status, "READY_FOR_OWNER_REVIEW")
        self.assertIn(
            retained_commit.INCONSISTENT_STATE,
            [blocker["code"] for blocker in result.blockers],
        )
        self.assertIsNotNone(
            retained_commit.read_publication_intent(self.workspace),
            "the intent must survive as evidence of an unfinished commit",
        )
        self.assertTrue(
            (
                retained_commit.staging_directory(self.workspace, transaction)
                / retained_commit.MANIFEST_FILENAME
            ).is_file(),
            "the staged output must survive as evidence",
        )
        canonical = (self.workspace / "experiment-state.json").read_text()
        self.assertNotEqual(canonical, self.SUBSTITUTED)
        self.assertEqual(canonical, before)


class UnsealedReservationTests(IntentProvenanceFixture):
    """A reservation covering a publication must say which bytes, not only which request."""

    def test_a_reservation_without_a_seal_does_not_cover_a_publication(self) -> None:
        """Removing the seal must not downgrade provenance to request identities.

        By the time an intent is durable the reservation has been sealed, so an
        unsealed one is not a state this protocol produces. Tolerating it lets a
        rewritten reservation stand in for the commitment it dropped.
        """
        observed = self.prepare()
        candidate = observed.preflight_candidate_sha256
        assert candidate is not None
        authority = self.authority(candidate)
        effects: list[str] = []
        before = (self.workspace / "experiment-state.json").read_text()

        with self.patched_effect(effects):
            with self.crash_before_the_first_canonical_write():
                with self.assertRaises(RuntimeError):
                    self.prepare(authority=authority)

            intent = retained_commit.read_publication_intent(self.workspace)
            self.assertIsNotNone(intent)
            assert intent is not None
            path = self.workspace / retained_commit.RESERVATION_FILENAME
            reservation = json.loads(path.read_text())
            self.assertIsNotNone(reservation["staged_manifest_sha256"])
            reservation["staged_manifest_sha256"] = None
            path.write_text(json.dumps(reservation, indent=2, sort_keys=True) + "\n")

            refused = self.prepare(authority=authority)

        self.assertEqual(effects, ["effect"], "nothing may be re-run here")
        self.assert_preserved(intent.transaction_id, before, refused)


class NonReservingIntentTests(IntentProvenanceFixture):
    """The intent alone must be sufficient provenance, because sometimes it is all there is."""

    def test_staged_output_cannot_change_after_the_intent_was_checked(self) -> None:
        """An authority-less publisher never reserves, so nothing else vouches.

        The intent is compared against the staged manifest, and the staged output is
        then read again. A replacement installed between those two observations is
        published as the interrupted transaction's commit, and the intent is
        rewritten to name it.
        """
        effects: list[str] = []
        self.prepare()
        # A different task, so this publisher has output of its own to publish. One
        # that would reproduce what is already committed publishes nothing, and
        # records no intent at all.
        self.payload["tasks"][0]["id"] = "T9"
        with self.patched_effect(effects):
            with self.crash_before_the_first_canonical_write():
                with self.assertRaises(RuntimeError):
                    self.prepare()

        intent = retained_commit.read_publication_intent(self.workspace)
        self.assertIsNotNone(intent, "the publication must have been recorded")
        assert intent is not None
        self.assertIsNone(
            retained_commit.read_reservation(self.workspace),
            "an authority-less invocation must not have reserved",
        )
        before = (self.workspace / "experiment-state.json").read_text()

        real_digest = retained_commit._staged_manifest_digest
        substituted: list[str] = []

        def digest_then_substitute(root: Path, transaction_id: str) -> Any:
            observed = real_digest(root, transaction_id)
            # The intent has just been satisfied by this observation. The staged
            # output is about to be read again, and it is no longer the same.
            if not substituted:
                substituted.append(transaction_id)
                self.substitute(transaction_id)
            return observed

        with self.patched_effect(effects):
            with mock.patch.object(
                retained_commit,
                "_staged_manifest_digest",
                side_effect=digest_then_substitute,
            ):
                refused = self.prepare()

        self.assertEqual(substituted, [intent.transaction_id])
        self.assertEqual(effects, [], "no effect may run in either invocation")
        self.assert_preserved(intent.transaction_id, before, refused)


if __name__ == "__main__":
    unittest.main()
