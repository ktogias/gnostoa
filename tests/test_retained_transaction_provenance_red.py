"""RED provenance packet for the retained-transaction model at ca6f836.

Containment is closed; these are about what the retained records still permit once
a transaction is interrupted. Three properties:

  * an interrupted publication must not be displaced by a caller that took its
    decision before that publication existed -- every persistence boundary has to
    resolve what is in flight, not only the first read of the workspace;
  * the publication intent must bind the exact bytes it was written for, so a
    self-consistent substitution of the staged output under the same request
    cannot be finished forward in its place;
  * a retained state that claims readiness must carry the whole lock provenance
    chain, so removing a link is a refusal rather than one fewer thing to check.

All fixtures are synthetic and the qualification effect is patched and counted; no
Phase-D material, hidden oracle, runner or container effect participates.

At head ca6f836928926fda6bcf788bd982f98edc02a9db these are expected to be RED.
"""

from __future__ import annotations

import hashlib
import json
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


class ProvenanceFixture(ConsumptionFixture):
    def patched_effect(self, effects: list[str] | None = None) -> Any:
        def qualify(*args: object, **kwargs: object) -> Any:
            del args
            if effects is not None:
                effects.append("effect")
            task_id = kwargs.get("task_id", "T1")
            bound = kwargs.get("bound") or {}
            assert isinstance(task_id, str)
            assert isinstance(bound, dict)
            return _receipt(task_id, dict(bound))

        return mock.patch.object(compiler, "qualify_subjects", side_effect=qualify)

    def die_before_the_first_canonical_write(self) -> Any:
        """Interrupt a publication after its intent and before any canonical byte."""
        real_write = retained_commit._write_atomic

        def crash(path: Path, payload: bytes) -> None:
            if (
                path.parent == self.workspace
                and path.name == retained_commit.LEDGER_FILENAME
            ):
                raise RuntimeError("crash after the intent, before publishing")
            return real_write(path, payload)

        return mock.patch.object(retained_commit, "_write_atomic", side_effect=crash)

    def staged_member(self, transaction: str, name: str) -> Path:
        return retained_commit.staging_directory(self.workspace, transaction) / name


class InterruptedPublicationDisplacementTests(ProvenanceFixture):
    """A decision taken before a publication existed cannot settle its fate."""

    def prepare_spec(self, spec: Any, authority: Any = None) -> Any:
        return compiler.prepare(
            spec,
            self.workspace,
            offline=True,
            preflight_authority=authority,
            qualification_backend=qualification.LOCAL_PYTHON,
        )

    def test_an_interrupted_publication_is_not_displaced_at_another_finish(
        self,
    ) -> None:
        """Recovery belongs at every persistence boundary, not only the first read.

        A zero-effect invocation reads the workspace, is told it may proceed, and
        only afterwards does an effect-bearing transaction record its intent to
        publish and die. If the zero-effect caller then persists on the strength of
        its earlier decision, it overwrites the record of a publication that is the
        only route back to an effect which already ran and cannot run again.

        The zero-effect caller is given a different task deliberately, so that it
        has something of its own to publish. A caller that would reproduce what is
        already committed publishes nothing, and would not exercise this at all.
        """
        observed = self.prepare()
        candidate = observed.preflight_candidate_sha256
        assert candidate is not None
        authority = self.authority(candidate)
        effect_bearing_spec = self._spec()
        effects: list[str] = []
        interrupted: list[str] = []

        real_stage = retained_commit.stage

        def stage_then_let_the_effect_bearer_die(root: Path, **kwargs: Any) -> Any:
            # The zero-effect caller has already been told it may proceed. The
            # effect-bearing transaction runs its oracle, stages its output, records
            # its intent to publish, and dies before the first canonical byte moves.
            if not interrupted:
                interrupted.append("interrupted")
                with self.patched_effect(effects):
                    with self.die_before_the_first_canonical_write():
                        with self.assertRaises(RuntimeError):
                            self.prepare_spec(effect_bearing_spec, authority)
            return real_stage(root, **kwargs)

        self.payload["tasks"][0]["id"] = "T9"
        with mock.patch.object(
            retained_commit, "stage", side_effect=stage_then_let_the_effect_bearer_die
        ):
            zero_effect = self.prepare()

        self.assertEqual(interrupted, ["interrupted"])
        self.assertEqual(effects, ["effect"], "the oracle must have run exactly once")
        self.assertNotEqual(
            zero_effect.status,
            "READY_FOR_OWNER_REVIEW",
            "the zero-effect caller is not the one that qualified anything",
        )

        # The interrupted transaction's evidence must still be reachable: the
        # identical authorised request finishes it forward rather than finding a
        # consumed candidate whose only record has been swept away.
        with self.patched_effect(effects):
            recovered = self.prepare_spec(effect_bearing_spec, authority)

        self.assertEqual(
            effects, ["effect"], "recovery must not re-run the irreversible effect"
        )
        self.assertEqual(
            recovered.status,
            "READY_FOR_OWNER_REVIEW",
            "an interrupted publication must survive another caller's persistence "
            "boundary, or the effect it recorded is lost with it",
        )


class PublicationIntentBindingTests(ProvenanceFixture):
    """The intent must name the bytes it was written for, not only a transaction."""

    def test_substituted_staged_output_is_not_finished_forward(self) -> None:
        """Same request, same identifier, different output.

        A staged tree rewritten self-consistently still satisfies every check that
        looks at which request it belongs to. Only a commitment to the exact bytes
        distinguishes the output the interrupted transaction produced from output
        somebody put in its place afterwards.
        """
        observed = self.prepare()
        candidate = observed.preflight_candidate_sha256
        assert candidate is not None
        before = (self.workspace / "experiment-state.json").read_text()

        with self.patched_effect():
            with self.die_before_the_first_canonical_write():
                with self.assertRaises(RuntimeError):
                    self.prepare(authority=self.authority(candidate))

        transaction = retained_commit.read_publication_intent(self.workspace)
        self.assertIsNotNone(transaction)
        assert transaction is not None
        identifier = (
            transaction if isinstance(transaction, str) else transaction.transaction_id
        )

        # Substitute the staged public state and re-seal the manifest around it, so
        # the staged tree stays complete and internally consistent and keeps naming
        # the same transaction, base, candidate and authority.
        state_path = self.staged_member(identifier, retained_commit.STATE_FILENAME)
        substituted = '{"substituted": true}\n'
        state_path.write_text(substituted)
        manifest_path = self.staged_member(
            identifier, retained_commit.MANIFEST_FILENAME
        )
        manifest = json.loads(manifest_path.read_text())
        manifest["state_file_sha256"] = hashlib.sha256(substituted.encode()).hexdigest()
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

        self.prepare()

        self.assertNotEqual(
            (self.workspace / "experiment-state.json").read_text(),
            substituted,
            "output substituted after the intent was recorded must never be "
            "published as that transaction's commit",
        )
        self.assertEqual(
            (self.workspace / "experiment-state.json").read_text(),
            before,
            "a workspace that cannot be recovered safely must be left as it was",
        )


class ReadyLockChainTests(ProvenanceFixture):
    """A state that claims readiness must carry every link, not the ones that remain."""

    def _complete(self) -> None:
        observed = self.prepare()
        candidate = observed.preflight_candidate_sha256
        assert candidate is not None
        with self.patched_effect():
            self.prepare(authority=self.authority(candidate))
        self.assertEqual(
            compiler.status(self.workspace)["status"], "READY_FOR_OWNER_REVIEW"
        )

    def _rebind(self, **overrides: Any) -> None:
        """Re-seal the commit record so the file digests agree after tampering."""
        path = self.workspace / retained_commit.COMMIT_RECORD_FILENAME
        record = json.loads(path.read_text())
        for field, filename in (
            ("stages_sha256", retained_commit.LEDGER_FILENAME),
            ("state_sha256", retained_commit.STATE_FILENAME),
            ("lock_file_sha256", retained_commit.LOCK_FILENAME),
        ):
            target = self.workspace / filename
            record[field] = (
                hashlib.sha256(target.read_bytes()).hexdigest()
                if target.is_file()
                else None
            )
        record.update(overrides)
        path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")

    def _assert_refused(self, why: str) -> None:
        with self.assertRaises(retained_commit.RetainedTransactionError) as raised:
            retained_commit.read_committed(self.workspace)
        self.assertEqual(raised.exception.code, retained_commit.INCONSISTENT_STATE, why)
        self.assertEqual(compiler.status(self.workspace)["status"], "BLOCKED", why)

    def test_a_ready_state_without_its_lock_is_refused(self) -> None:
        self._complete()
        (self.workspace / retained_commit.LOCK_FILENAME).unlink()
        self._rebind(lock_identity=None)
        self._assert_refused(
            "a state claiming readiness with no lock at all must not be accepted"
        )

    def test_a_ready_state_without_its_lock_binding_is_refused(self) -> None:
        self._complete()
        path = self.workspace / retained_commit.STATE_FILENAME
        state = json.loads(path.read_text())
        state["lock_sha256"] = None
        path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
        self._rebind()
        self._assert_refused(
            "a state claiming readiness must name the lock it was made ready by"
        )

    def test_a_ready_ledger_missing_a_lock_binding_is_refused(self) -> None:
        for stage in ("EXECUTION_FROZEN", "READY_FOR_OWNER_REVIEW"):
            with self.subTest(stage=stage):
                self.setUp()
                self._complete()
                path = self.workspace / retained_commit.LEDGER_FILENAME
                ledger = json.loads(path.read_text())
                ledger["records"][stage]["outputs"].pop("lock_sha256")
                path.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n")
                self._rebind()
                self._assert_refused(
                    f"a readiness whose {stage} receipt names no lock must not be "
                    "accepted"
                )


if __name__ == "__main__":
    unittest.main()
