"""RED for coherence of a staged transaction across one publication, at 7d3ce2e.

Each operation is now anchored on a descriptor, but a publication performs several
of them and reopens the transaction directory by name in between: the manifest
digest, the parsed staged object and the member bytes are not necessarily
observations of the same directory. A complete, self-consistent replacement
carrying the same transaction, base, candidate and authority can therefore be
substituted between two of those observations.

The reservation was sealed to the manifest of the output that was actually staged,
which is exactly the commitment that should settle this. It is not consulted where
a publication intent exists, so the substitution survives the check that was added
to prevent it.

The fixture is synthetic and the qualification effect is patched and counted; no
Phase-D material, hidden oracle, runner or container effect participates.

At head 7d3ce2e69ff164f72f26f8406d122c84f74e0144 this is expected to be RED.
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


class StagedSubstitutionDuringPublicationTests(ConsumptionFixture):
    """One publication must be one observation of one directory."""

    SUBSTITUTED = '{"substituted": true}\n'

    def _substitute(self, transaction: str) -> None:
        """Replace <txid> with a complete, self-consistent directory of its own.

        Same transaction, base, candidate and authority; different output, and a
        manifest that seals that different output correctly.
        """
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

    def test_a_directory_swapped_mid_publication_is_never_finished_forward(
        self,
    ) -> None:
        observed = self.prepare()
        candidate = observed.preflight_candidate_sha256
        assert candidate is not None
        authority = self.authority(candidate)
        before = (self.workspace / "experiment-state.json").read_text()
        effects: list[str] = []
        substituted: list[str] = []

        def qualify(*args: object, **kwargs: object) -> Any:
            del args
            effects.append("effect")
            task_id = kwargs.get("task_id", "T1")
            bound = kwargs.get("bound") or {}
            assert isinstance(task_id, str)
            assert isinstance(bound, dict)
            return _receipt(task_id, dict(bound))

        real_digest = retained_commit._staged_manifest_digest
        real_write = retained_commit._write_atomic

        def substitute_then_digest(root: Path, transaction_id: str) -> Any:
            # The publication has read its members from the directory it opened and
            # closed it. Between that and the observation the intent is bound to,
            # the name now resolves to a different directory entirely.
            if not substituted:
                substituted.append(transaction_id)
                self._substitute(transaction_id)
            return real_digest(root, transaction_id)

        def crash_before_the_record(path: Path, payload: bytes) -> None:
            if (
                path.parent == self.workspace
                and path.name == retained_commit.COMMIT_RECORD_FILENAME
            ):
                raise RuntimeError("crash after the intent, before the record")
            return real_write(path, payload)

        with mock.patch.object(compiler, "qualify_subjects", side_effect=qualify):
            with (
                mock.patch.object(
                    retained_commit,
                    "_staged_manifest_digest",
                    side_effect=substitute_then_digest,
                ),
                mock.patch.object(
                    retained_commit,
                    "_write_atomic",
                    side_effect=crash_before_the_record,
                ),
            ):
                with self.assertRaises(RuntimeError):
                    self.prepare(authority=authority)

            reservation = retained_commit.read_reservation(self.workspace)
            self.assertIsNotNone(reservation)
            assert reservation is not None
            self.assertIsNotNone(
                reservation.staged_manifest_sha256,
                "the reservation must be sealed to the output that was staged",
            )
            intent = retained_commit.read_publication_intent(self.workspace)
            self.assertIsNotNone(intent, "the publication must have been recorded")
            assert intent is not None

            # The invariant, whether or not the substitution found a window: a
            # publication may only be bound to the output its own reservation was
            # sealed to. Binding it to anything else means the bytes being published
            # and the bytes vouched for are two different observations.
            self.assertEqual(
                intent.manifest_sha256,
                reservation.staged_manifest_sha256,
                "the publication intent names output the reservation never sealed",
            )

            self.prepare(authority=authority)

        self.assertEqual(effects, ["effect"], "nothing may be re-run here")
        self.assertNotEqual(
            (self.workspace / "experiment-state.json").read_text(),
            self.SUBSTITUTED,
            "output substituted between two observations of one publication must "
            "never become this transaction's commit",
        )
        self.assertNotEqual(
            before,
            self.SUBSTITUTED,
            "the substituted bytes must differ from what was already committed, or "
            "this proves nothing",
        )


if __name__ == "__main__":
    unittest.main()
