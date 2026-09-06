"""RED transaction packet for the #200 retained-transaction model.

These state invariants, not a mechanism. Each one is expressed in terms of what a
workspace must contain after an interleaving, so that whichever protocol is chosen
-- generation CAS, effect-aware reservation, or something else -- has to satisfy the
same observable contract.

Every case is deterministic: concurrency is simulated by driving a second
invocation from inside a patched seam of the first, never by threads or timing.
All fixtures are synthetic and the qualification effect is patched and counted; no
Phase-D material and no hidden oracle participates.

At head 4d4d2a6b these are expected to be RED. They are the evidence a repair must
turn green, and they are deliberately written before any repair exists.
"""

from __future__ import annotations

import json
import unittest
from unittest import mock

from tools.capsule import compiler, qualification, retained_commit
from tools.capsule import lock as lock_module
from tools.capsule.identity import digest_of

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


class EffectBearingTransactionTests(ConsumptionFixture):
    """An invocation that crossed the irreversible boundary must be able to finish."""

    def test_zero_effect_commit_cannot_fence_out_a_completed_qualification(
        self,
    ) -> None:
        """The central invariant: an effect that happened must be recordable.

        A prepare that has consumed the claim and run the oracle holds strictly more
        standing than one that has done nothing irreversible. Resolving that by
        arrival order loses the result of a non-repeatable effect, which is the
        failure class this work exists to prevent.
        """
        observed = self.prepare()
        candidate = observed.preflight_candidate_sha256
        assert candidate is not None
        authority = self.authority(candidate)
        effects: list[str] = []

        def qualify_then_let_a_zero_effect_prepare_commit(*args, **kwargs):  # type: ignore[no-untyped-def]
            del args
            effects.append("qualify_subjects")
            # A zero-effect invocation commits while the winner is mid-effect.
            self.prepare()
            return _receipt(
                kwargs.get("task_id", "T1"), dict(kwargs.get("bound") or {})
            )

        with mock.patch.object(
            compiler,
            "qualify_subjects",
            side_effect=qualify_then_let_a_zero_effect_prepare_commit,
        ):
            winner = self.prepare(authority=authority)

        self.assertEqual(effects, ["qualify_subjects"])
        current = compiler.status(self.workspace)
        self.assertEqual(
            winner.status,
            "READY_FOR_OWNER_REVIEW",
            "an invocation whose irreversible effect succeeded must not be fenced out",
        )
        self.assertEqual(current["status"], "READY_FOR_OWNER_REVIEW")
        self.assertIsNotNone(
            current["lock_sha256"],
            "the successful transaction must be able to record its lock",
        )

    def test_a_transaction_that_cannot_commit_leaves_no_orphan_lock(self) -> None:
        """Lock publication belongs to the same recoverable transaction as the state.

        An immutable lock written outside the committing transaction can survive a
        commit that never happened, and a later recovery then meets a lock conflict
        for a transaction the public state never recorded.
        """
        observed = self.prepare()
        candidate = observed.preflight_candidate_sha256
        assert candidate is not None
        authority = self.authority(candidate)

        def qualify_then_commit_elsewhere(*args, **kwargs):  # type: ignore[no-untyped-def]
            del args
            self.prepare()
            return _receipt(
                kwargs.get("task_id", "T1"), dict(kwargs.get("bound") or {})
            )

        with mock.patch.object(
            compiler, "qualify_subjects", side_effect=qualify_then_commit_elsewhere
        ):
            self.prepare(authority=authority)

        current = compiler.status(self.workspace)
        lock_present = (self.workspace / "experiment.lock").is_file()
        if current["lock_sha256"] is None:
            self.assertFalse(
                lock_present,
                "an uncommitted transaction must not leave an immutable lock behind",
            )


class RetainedLockBindingTests(ConsumptionFixture):
    """Canonical validity is not provenance."""

    def _complete(self) -> str:
        observed = self.prepare()
        candidate = observed.preflight_candidate_sha256
        assert candidate is not None
        with mock.patch.object(
            compiler,
            "qualify_subjects",
            side_effect=lambda *a, **k: _receipt(
                k.get("task_id", "T1"), dict(k.get("bound") or {})
            ),
        ):
            self.prepare(authority=self.authority(candidate))
        return candidate

    def test_substituted_lock_with_recomputed_digest_cannot_prove_currentness(
        self,
    ) -> None:
        """A self-consistent lock is not necessarily *this* completion's lock.

        Fields excluded from the currentness comparison can be rewritten and the
        digest recomputed. Canonical loading still succeeds, so the retained lock
        must additionally be bound to the identity the successful transaction
        recorded.
        """
        self._complete()
        retained_identity = compiler.status(self.workspace)["lock_sha256"]
        path = self.workspace / "experiment.lock"
        payload = {
            key: value
            for key, value in json.loads(path.read_text()).items()
            if key != "lock_sha256"
        }
        payload["tasks"] = [{"id": "SUBSTITUTED", "capsule_identity": "0" * 64}]
        payload["lock_sha256"] = digest_of(payload)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True))

        # The substitution is canonically valid but is a different lock.
        lock_module.load(path)
        self.assertNotEqual(payload["lock_sha256"], retained_identity)

        self.prepare()
        self.assertEqual(
            compiler.status(self.workspace)["status"],
            "BLOCKED",
            "a lock that is not the retained completion's lock must not prove READY",
        )


class RetainedGenerationIntegrityTests(ConsumptionFixture):
    """Missing, valid and invalid retained version state are three states."""

    def test_malformed_generation_marker_is_not_the_initial_generation(self) -> None:
        self.prepare()
        marker = self.workspace / retained_commit.GENERATION_FILENAME
        if not marker.exists():  # a different mechanism may record this elsewhere
            self.skipTest("no generation marker in this implementation")
        marker.write_text("{ not valid json")
        self.assertNotEqual(
            retained_commit.read_generation(self.workspace),
            0,
            "an unreadable marker must be distinguishable from a fresh workspace",
        )

    def test_state_newer_than_the_marker_is_not_overwritable(self) -> None:
        """A crash between persisting state and advancing the marker must fail closed.

        Otherwise a stale invocation holding the pre-crash value legitimately passes
        the check and overwrites state that is newer than the marker admits.
        """
        self.prepare()
        stale = retained_commit.read_generation(self.workspace)
        marker = self.workspace / retained_commit.GENERATION_FILENAME
        if not marker.exists():
            self.skipTest("no generation marker in this implementation")

        wrote: list[str] = []
        # State advances; the marker does not, as if the process died between them.
        with mock.patch.object(
            retained_commit, "_write_generation", side_effect=RuntimeError("crash")
        ):
            with self.assertRaises(RuntimeError):
                retained_commit.commit_if_current(
                    self.workspace,
                    expected=stale,
                    persist=lambda: wrote.append("newer state"),
                )
        self.assertEqual(wrote, ["newer state"])

        self.assertFalse(
            retained_commit.commit_if_current(
                self.workspace, expected=stale, persist=lambda: wrote.append("stale")
            ),
            "a writer holding the pre-crash generation must not overwrite newer state",
        )
        self.assertEqual(wrote, ["newer state"])


class CoherentSnapshotTests(ConsumptionFixture):
    """The retained snapshot and its version token must be acquired together."""

    def test_snapshot_paired_with_a_newer_token_cannot_commit(self) -> None:
        """Reading the ledger and the token separately permits a torn pair.

        An invocation can hold a snapshot from before a completion and a token from
        after it. Any equality check on that token then passes, and the stale
        snapshot is written over state it never saw. The workspace is rewound to the
        pre-completion snapshot so the caller genuinely loads the older ledger.
        """
        import shutil

        observed = self.prepare()
        candidate = observed.preflight_candidate_sha256
        assert candidate is not None
        old_snapshot = self.root / "snapshot-before-completion"
        shutil.copytree(self.workspace, old_snapshot)

        with mock.patch.object(
            compiler,
            "qualify_subjects",
            side_effect=lambda *a, **k: _receipt(
                k.get("task_id", "T1"), dict(k.get("bound") or {})
            ),
        ):
            self.prepare(authority=self.authority(candidate))
        winner = compiler.status(self.workspace)
        self.assertEqual(winner["status"], "READY_FOR_OWNER_REVIEW")
        completed_snapshot = self.root / "snapshot-after-completion"
        shutil.copytree(self.workspace, completed_snapshot)

        # Rewind: the caller will load the pre-completion ledger.
        shutil.rmtree(self.workspace)
        shutil.copytree(old_snapshot, self.workspace)

        torn: list[str] = []
        real_read = retained_commit.read_generation

        def read_after_the_winner_landed(root):  # type: ignore[no-untyped-def]
            # The caller has loaded the old ledger; the winner's state and token
            # become visible before the caller reads its token.
            if not torn:
                torn.append("torn")
                shutil.rmtree(self.workspace)
                shutil.copytree(completed_snapshot, self.workspace)
            return real_read(root)

        with mock.patch.object(
            compiler.retained_commit,
            "read_generation",
            side_effect=read_after_the_winner_landed,
        ):
            self.prepare()

        self.assertEqual(torn, ["torn"])
        current = compiler.status(self.workspace)
        self.assertEqual(
            current["status"],
            "READY_FOR_OWNER_REVIEW",
            "a torn snapshot/token pair must not authorise overwriting newer state",
        )
        self.assertEqual(current["lock_sha256"], winner["lock_sha256"])


class ConcurrentReconciliationTests(ConsumptionFixture):
    """Liveness, not only safety: a legitimate waiter must converge, not fail.

    The other six invariants can all be satisfied by a protocol that simply refuses
    everyone except the transaction owner. That would be safe and operationally
    wrong, so this states the semantics a reservation must not collapse into: an
    exclusive right to perform the effect-bearing transaction, rather than an
    exclusive right to touch the workspace at all.

    Unlike the safety cases this one needs genuine concurrency, because the waiter's
    required behaviour is to still be waiting while the owner is mid-transaction. It
    asserts outcomes only -- never how long anything took, nor that any particular
    primitive was used -- so waiting, optimistic retry or any other correct design
    satisfies it.
    """

    def test_identical_authorised_waiter_reconciles_to_the_single_winner(self) -> None:
        import threading

        observed = self.prepare()
        candidate = observed.preflight_candidate_sha256
        assert candidate is not None
        authority = self.authority(candidate)

        owner_in_effect = threading.Event()
        waiter_started = threading.Event()
        effects: list[str] = []
        results: dict[str, object] = {}

        def qualify(*args, **kwargs):  # type: ignore[no-untyped-def]
            del args
            effects.append("qualify_subjects")
            owner_in_effect.set()
            # Hold the transaction open until the waiter has genuinely arrived.
            waiter_started.wait(timeout=30)
            return _receipt(
                kwargs.get("task_id", "T1"), dict(kwargs.get("bound") or {})
            )

        # Built once, before either thread starts: the fixture writes the spec to a
        # shared path, so letting both threads build it would race in the harness
        # rather than in the code under test.
        shared_spec = self._spec()

        def run_owner() -> None:
            with mock.patch.object(compiler, "qualify_subjects", side_effect=qualify):
                results["owner"] = compiler.prepare(
                    shared_spec,
                    self.workspace,
                    offline=True,
                    preflight_authority=authority,
                )

        def run_waiter() -> None:
            try:
                results["waiter"] = compiler.prepare(
                    shared_spec,
                    self.workspace,
                    offline=True,
                    preflight_authority=authority,
                )
            except Exception as exc:  # recorded rather than raised across threads
                results["waiter_error"] = exc

        owner = threading.Thread(target=run_owner)
        owner.start()
        self.assertTrue(
            owner_in_effect.wait(timeout=30), "the owner never entered its effect"
        )
        waiter = threading.Thread(target=run_waiter)
        waiter.start()
        waiter_started.set()
        owner.join(timeout=60)
        waiter.join(timeout=60)
        self.assertFalse(owner.is_alive())
        self.assertFalse(waiter.is_alive())

        self.assertEqual(effects, ["qualify_subjects"], "exactly one effect may run")
        self.assertNotIn("waiter_error", results)
        owner_result = results["owner"]
        waiter_result = results["waiter"]

        self.assertEqual(owner_result.status, "READY_FOR_OWNER_REVIEW")
        self.assertEqual(
            waiter_result.status,
            "READY_FOR_OWNER_REVIEW",
            "an identical authorised waiter must reconcile onto the winning "
            "transaction, not receive a terminal concurrency refusal",
        )
        self.assertNotIn(
            retained_commit.CONCURRENT_STATE_CHANGED,
            [blocker["code"] for blocker in waiter_result.blockers],
        )
        current = compiler.status(self.workspace)
        self.assertEqual(current["status"], "READY_FOR_OWNER_REVIEW")
        self.assertIsNotNone(current["lock_sha256"])


class ConcurrentAuthorityLessCallerTests(ConsumptionFixture):
    """A caller with no authority may stay blocked, but must not fence the owner."""

    def test_authority_less_caller_stays_blocked_without_disturbing_the_winner(
        self,
    ) -> None:
        observed = self.prepare()
        candidate = observed.preflight_candidate_sha256
        assert candidate is not None
        effects: list[str] = []

        def qualify_then_let_an_authority_less_caller_run(*args, **kwargs):  # type: ignore[no-untyped-def]
            del args
            effects.append("qualify_subjects")
            results["authority_less"] = self.prepare()
            return _receipt(
                kwargs.get("task_id", "T1"), dict(kwargs.get("bound") or {})
            )

        results: dict[str, object] = {}
        with mock.patch.object(
            compiler,
            "qualify_subjects",
            side_effect=qualify_then_let_an_authority_less_caller_run,
        ):
            owner = self.prepare(authority=self.authority(candidate))

        self.assertEqual(effects, ["qualify_subjects"])
        # The authority-less caller is entitled to remain blocked ...
        self.assertEqual(results["authority_less"].status, "BLOCKED")
        # ... but not to cost the owner its committed transaction.
        self.assertEqual(owner.status, "READY_FOR_OWNER_REVIEW")
        current = compiler.status(self.workspace)
        self.assertEqual(current["status"], "READY_FOR_OWNER_REVIEW")
        self.assertIsNotNone(current["lock_sha256"])


if __name__ == "__main__":
    unittest.main()
