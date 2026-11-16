"""Native/provider seams preserve S52 evidence and journal identities, without I/O."""

from __future__ import annotations

import copy
import json
import unittest
from datetime import UTC, datetime
from typing import cast
from unittest import mock

from tools import project_progress as core
from tools import project_progress_native as n


class NativeProgressTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = 1_800_000_000.0
        self.scope: n.Native = {"kind": "work_item", "ref": "issue:496"}
        self.row = n.progress_row(
            self.scope, [{"kind": "operation", "delivery_key": "old-step"}]
        )
        self.frontier: n.Native = {"coverage": "COMPLETE", "rows": [self.row]}
        self.reads: dict[str, n.Native] = {
            f"https://github.com/ktogias/gnostoa/issues/{number}": {
                "kind": "work_item",
                "number": number,
                "body_sha256": str(number),
                "coverage": "CURRENT",
                "body_complete": True,
                "observed_at": self.now,
            }
            for number in (496, 325)
        }
        self.job: n.Native = {
            "authority_context": {
                **self.reads,
                "_coverage": {"coverage": "COMPLETE"},
            },
            "continuation_contract": {"frontier_sha256": "lineage"},
        }
        self.decoded: n.Native = {
            "assignments": [{"operation": {"operation_target": "issue:325"}}]
        }
        self.claim: n.Native = {
            "id": self.row["id"],
            "disposition": "ASSIGNED",
            "assignment_index": 0,
            "evidence": [
                {"source": url, "digest": read["body_sha256"], "observed_at": self.now}
                for url, read in self.reads.items()
            ],
        }

    def validate(self, claim: n.Native | None = None) -> None:
        value = self.claim if claim is None else claim
        n.validate_progress(
            self.job, self.frontier, self.row, value, self.decoded, [value]
        )

    def test_native_journal_time_keeps_the_original_whole_second_encoding(self) -> None:
        row = n.new_obligation("id", self.scope, self.now + 0.75)
        self.assertEqual(
            row["created_at"],
            datetime.fromtimestamp(self.now, UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )

    def test_late_older_scope_delivery_after_restart_does_not_rearm(self) -> None:
        store: n.Native = {}
        newer = {
            "kind": "scope",
            "generation": "g2",
            "observed": {"epoch": "reader-a", "seq": 2},
        }
        obligation, added, refresh = n.open_obligation(
            store, self.scope, [newer], None, self.now
        )
        self.assertTrue(added)
        self.assertIsNone(refresh)
        obligation["status"] = "DISCHARGED"
        store = json.loads(json.dumps(store))
        older = {
            "kind": "scope",
            "generation": "g1",
            "observed": {"epoch": "reader-a", "seq": 1},
        }
        obligation, added, refresh = n.open_obligation(
            store, self.scope, [older], None, self.now + 1
        )
        self.assertFalse(added)
        self.assertIsNone(refresh)
        self.assertEqual(obligation["status"], "DISCHARGED")
        self.assertEqual(obligation["sources"], [newer])

    def test_scope_observation_order_is_not_part_of_source_fingerprint(self) -> None:
        # No generation: only the fingerprint can tell that the later one is held.
        first = {"kind": "scope", "observed": {"epoch": "reader-a", "seq": 1}}
        later = {"kind": "scope", "observed": {"epoch": "reader-a", "seq": 3}}
        obligation = n.new_obligation("id", self.scope, self.now)
        self.assertEqual(n.merge_sources(obligation, [first]), (True, False))
        self.assertEqual(n.merge_sources(obligation, [later]), (False, False))
        self.assertEqual(obligation["sources"], [first])

    def test_newer_observation_accepts_digest_reversion(self) -> None:
        store: n.Native = {}
        for generation, sequence in (("g1", 1), ("g2", 2), ("g1", 3)):
            source = {
                "kind": "scope",
                "generation": generation,
                "observed": {"epoch": "reader-a", "seq": sequence},
            }
            obligation, added, refresh = n.open_obligation(
                store, self.scope, [source], None, self.now + sequence
            )
            self.assertTrue(added)
            self.assertIsNone(refresh)
        self.assertEqual(obligation["sources"], [source])

    def test_duplicate_observation_cannot_rewind_retained_raw_order_after_reload(
        self,
    ) -> None:
        store: n.Native = {}
        held = {
            "kind": "scope",
            "generation": "g1",
            "observed": {"epoch": "reader-a", "seq": 3},
        }
        obligation, added, refresh = n.open_obligation(
            store, self.scope, [held], None, self.now
        )
        self.assertTrue(added)
        self.assertIsNone(refresh)

        duplicate = {
            **held,
            "observed": {"epoch": "reader-a", "seq": 1},
        }
        obligation, added, refresh = n.open_obligation(
            store, self.scope, [duplicate], None, self.now + 1
        )
        self.assertFalse(added)
        self.assertIsNone(refresh)
        self.assertEqual(obligation["sources"], [held])

        store = json.loads(json.dumps(store))
        newer_generation = {
            "kind": "scope",
            "generation": "g2",
            "observed": {"epoch": "reader-a", "seq": 2},
        }
        obligation, added, refresh = n.open_obligation(
            store, self.scope, [newer_generation], None, self.now + 2
        )
        self.assertFalse(added)
        self.assertIsNone(refresh)
        self.assertEqual(obligation["sources"], [held])

    def test_missing_or_different_epoch_keeps_scope_and_requests_refresh(self) -> None:
        held = {
            "kind": "scope",
            "generation": "g2",
            "observed": {"epoch": "reader-a", "seq": 2},
        }
        for incoming in (
            {"kind": "scope", "generation": "g1"},
            {
                "kind": "scope",
                "generation": "g1",
                "observed": {"epoch": "reader-b", "seq": 3},
            },
        ):
            with self.subTest(incoming=incoming):
                store: n.Native = {}
                obligation, _, _ = n.open_obligation(
                    store, self.scope, [held], None, self.now
                )
                obligation["status"] = "DISCHARGED"
                obligation, added, refresh = n.open_obligation(
                    store, self.scope, [incoming], None, self.now + 1
                )
                self.assertFalse(added)
                self.assertEqual(refresh, "SOURCE_PENDING/REFRESH")
                self.assertEqual(obligation["sources"], [held])
                self.assertEqual(obligation["status"], "DISCHARGED")

    def test_scope_and_distinct_target_bind_to_real_captured_reads(self) -> None:
        self.validate()
        for remove in (0, 1):
            claim = copy.deepcopy(self.claim)
            claim["evidence"].pop(remove)
            with (
                self.subTest(remove=remove),
                self.assertRaisesRegex(ValueError, "bind its scope"),
            ):
                self.validate(claim)

    def test_claim_identity_must_match_the_row_being_validated(self) -> None:
        for claim_id in ("another-row", None):
            claim = copy.deepcopy(self.claim)
            if claim_id is None:
                claim.pop("id")
            else:
                claim["id"] = claim_id
            with (
                self.subTest(claim_id=claim_id),
                self.assertRaises(ValueError),
            ):
                self.validate(claim)

    def test_missing_authority_context_coverage_fails_closed(self) -> None:
        self.job["authority_context"].pop("_coverage")
        with self.assertRaisesRegex(ValueError, "bind its scope"):
            self.validate()

    def test_same_scope_frontier_token_does_not_replace_the_source(self) -> None:
        self.decoded["assignments"][0]["operation"]["operation_target"] = "issue:496"
        self.claim["evidence"] = [
            {
                "source": "frontier:" + self.row["id"],
                "digest": "lineage",
                "observed_at": None,
            }
        ]
        with self.assertRaisesRegex(ValueError, "bind its scope"):
            self.validate()

    def test_source_fingerprint_changes_hold_egress_but_observation_time_does_not(
        self,
    ) -> None:
        pointers = tuple(self.reads)
        fresh = copy.deepcopy(self.reads)
        for row in fresh.values():
            row["observed_at"] = cast(float, row["observed_at"]) + 20
        self.assertIsNone(n.source_changes(self.reads, fresh, pointers))
        original = self.reads[pointers[0]]
        original["source_binding_sha256"] = "original-provider-object"
        fresh[pointers[0]]["source_binding_sha256"] = "changed-provider-object"
        changed = n.source_changes(self.reads, fresh, pointers)
        assert changed is not None
        self.assertEqual(changed[0], "REPAIR_PENDING")
        fresh.pop(pointers[0])
        missing = n.source_changes(self.reads, fresh, pointers)
        assert missing is not None
        self.assertEqual(missing[0], "SOURCE_PENDING")

    def test_non_mapping_source_entries_remain_source_pending(self) -> None:
        pointer = next(iter(self.reads))
        held = {pointer: copy.deepcopy(self.reads[pointer])}
        fresh = copy.deepcopy(held)
        invalid_entries: tuple[object, ...] = (None, 17, "invalid", [])
        for invalid_entry in invalid_entries:
            with self.subTest(side="held", entry=invalid_entry):
                result = n.source_changes({pointer: invalid_entry}, fresh, (pointer,))
                self.assertIsNotNone(result)
                assert result is not None
                self.assertEqual(result[0], "SOURCE_PENDING")
            with self.subTest(side="fresh", entry=invalid_entry):
                result = n.source_changes(held, {pointer: invalid_entry}, (pointer,))
                self.assertIsNotNone(result)
                assert result is not None
                self.assertEqual(result[0], "SOURCE_PENDING")

    def test_pointer_missing_from_held_is_source_pending_not_a_key_error(self) -> None:
        pointer = next(iter(self.reads))
        fresh = {pointer: copy.deepcopy(self.reads[pointer])}
        for held in ({}, {"unrelated": copy.deepcopy(self.reads[pointer])}):
            with self.subTest(held=sorted(held)):
                result = n.source_changes(held, fresh, (pointer,))
                assert result is not None
                self.assertEqual(result[0], "SOURCE_PENDING")
                self.assertIn(pointer, result[1])

    def test_migration_keeps_tombstone_request_identity_and_budget_attribution(
        self,
    ) -> None:
        store: n.Native = {}
        unbound, _, _ = n.open_obligation(
            store, {"kind": "work_item", "ref": None}, [], "old", self.now
        )
        unbound["requests"] = [
            {
                "key": "stable-request",
                "at": datetime.fromtimestamp(self.now, UTC).isoformat(),
                "state": "INTENT",
                "input_sha256": "original-input",
            }
        ]
        bound = n.migrate(store, unbound, self.scope, self.now + 10)
        self.assertEqual(unbound["status"], "MIGRATED")
        self.assertEqual(unbound["superseded_by"], bound["id"])
        self.assertEqual(bound["requests"][0]["key"], "stable-request")
        self.assertEqual(bound["requests"][0]["input_sha256"], "original-input")
        self.assertEqual(bound["requests"][0]["carried_from"], unbound["id"])
        self.assertEqual(
            n.request_budget(store, bound, self.now + 10, daily_cap=1), "DAILY_CAP"
        )
        self.assertIsNone(n.request_budget(store, bound, self.now + 10, daily_cap=2))

    def test_migration_of_new_sources_reopens_a_discharged_bound_obligation(
        self,
    ) -> None:
        store: n.Native = {}
        source = {"category": "comment", "fingerprint": "new-evidence"}
        old, _, _ = n.open_obligation(
            store, {"kind": "work_item", "ref": None}, [source], "old", self.now
        )
        bound, _, _ = n.open_obligation(store, self.scope, [], None, self.now)
        bound["status"] = "DISCHARGED"
        old["status"] = "DISCHARGED"
        migrated = n.migrate(store, old, self.scope, self.now + 1)
        self.assertEqual(migrated["status"], "OPEN")
        self.assertEqual(migrated["reopened_by"], "NEW_SOURCE")

    def test_migration_rejects_an_ordering_that_invents_a_request(self) -> None:
        store: n.Native = {}
        old, _, _ = n.open_obligation(
            store, {"kind": "work_item", "ref": None}, [], "old", self.now
        )
        old["requests"] = [
            {
                "key": "k",
                "at": datetime.fromtimestamp(self.now, UTC).isoformat(),
                "state": "INTENT",
            }
        ]
        invented = core.RequestStamp("never-given", self.now)
        with (
            mock.patch.object(core, "migrate_requests", return_value=(invented,)),
            self.assertRaises(ValueError),
        ):
            n.migrate(store, old, self.scope, self.now + 1)

    def test_migration_retains_each_overlapping_request_record(self) -> None:
        store: n.Native = {}
        old, _, _ = n.open_obligation(
            store, {"kind": "work_item", "ref": None}, [], "old", self.now
        )
        bound, _, _ = n.open_obligation(store, self.scope, [], None, self.now)
        at = datetime.fromtimestamp(self.now, UTC).isoformat()
        old["requests"] = [{"key": "same-key", "at": at, "state": "INTENT"}]
        bound["requests"] = [{"key": "same-key", "at": at, "state": "SENT"}]
        migrated = n.migrate(store, old, self.scope, self.now + 1)
        self.assertEqual([r["state"] for r in migrated["requests"]], ["INTENT", "SENT"])
        self.assertEqual(migrated["requests"][0]["carried_from"], old["id"])

    def test_source_invalidation_survives_stored_restart_even_when_not_newly_touched(
        self,
    ) -> None:
        obligation = n.new_obligation("opaque-id", self.scope, self.now)
        obligation["requests"] = [
            {
                "key": "original-request",
                "state": "SENT",
                "at": datetime.fromtimestamp(self.now, UTC).isoformat(),
            }
        ]
        action, _ = n.controller_decision(
            obligation,
            fate="DISCHARGE",
            reason="ASSIGNED",
            touched=False,
            linked_open=False,
            source_router_open=False,
            now=self.now + 1,
            obligations={"opaque-id": obligation},
            current_input="new-source",
            last_input="old-source",
        )
        self.assertEqual(action, "REQUEST")

    def test_exact_owner_review_resume_needs_new_native_time_and_subject(self) -> None:
        head = "a" * 40
        row: n.Native = {
            "id": "gate",
            "kind": "HUMAN_MERGE",
            "source_kind": "canonical_criterion",
            "subject": {"pr_number": 600, "head_sha": head},
            "source_sha256": "captured",
            "canonical": {"criterion": "M16"},
        }
        claim: n.Native = {
            "id": "gate",
            "disposition": "WAITING",
            "owner": "human:ktogias",
            "resume_event": "native_exact_head_review",
            "evidence_sha256": "captured",
        }
        gate = n.gate_binding({}, row, claim)
        self.assertIsNotNone(gate)
        assert gate is not None
        gate["at"] = self.now
        record: n.Native = {
            "kind": "review",
            "number": 600,
            "material_id": "one-material",
            "observed_at": self.now + 1,
            "payload": {
                "item": {
                    "commit_id": head,
                    "submitted_at": datetime.fromtimestamp(
                        self.now + 1, UTC
                    ).isoformat(),
                }
            },
        }
        fact: n.Native = {"head": head, "provider_id": 90}
        self.assertEqual(
            n.gate_resume(gate, record, fact, self.now + 2, owner_review=True),
            "OWNER_REVIEW",
        )
        self.assertIsNone(
            n.gate_resume(
                gate,
                record,
                fact,
                self.now + 2,
                owner_review=True,
                seen=["one-material"],
            )
        )
        missing_gate_time = copy.deepcopy(gate)
        missing_gate_time.pop("at")
        self.assertIsNone(
            n.gate_resume(
                missing_gate_time, record, fact, self.now + 2, owner_review=True
            )
        )
        for invalid_at in (None, "not-a-timestamp", True):
            invalid_gate_time = copy.deepcopy(gate)
            invalid_gate_time["at"] = invalid_at
            with self.subTest(invalid_at=invalid_at):
                self.assertIsNone(
                    n.gate_resume(
                        invalid_gate_time,
                        record,
                        fact,
                        self.now + 2,
                        owner_review=True,
                    )
                )
        for mismatch in ("number", "head"):
            wrong_record = copy.deepcopy(record)
            wrong_fact = copy.deepcopy(fact)
            if mismatch == "number":
                wrong_record["number"] = 601
            else:
                wrong_record["payload"]["item"]["commit_id"] = "b" * 40
                wrong_fact["head"] = "b" * 40
            with self.subTest(mismatch=mismatch):
                self.assertIsNone(
                    n.gate_resume(
                        gate, wrong_record, wrong_fact, self.now + 2, owner_review=True
                    )
                )
        record["payload"]["item"]["submitted_at"] = datetime.fromtimestamp(
            self.now - 1, UTC
        ).isoformat()
        self.assertIsNone(
            n.gate_resume(gate, record, fact, self.now + 2, owner_review=True)
        )

    def test_waiting_claims_bind_to_supported_gate_sources(self) -> None:
        scope: n.Native = {"kind": "work_item", "ref": "issue:499"}
        row = n.progress_row(scope, [])
        subject = {"pr_number": 500, "head_sha": "a" * 40}
        dependency = {"pr_number": 600, "head_sha": "b" * 40}
        cases: tuple[tuple[str, n.Native, n.Native, n.Native], ...] = (
            (
                "human_review",
                {
                    "id": "human-gate",
                    "kind": "HUMAN_MERGE",
                    "source_kind": "canonical_criterion",
                    "subject": subject,
                    "source_sha256": "human-evidence",
                    "canonical": {"criterion": "M16"},
                },
                {
                    "id": "human-gate",
                    "disposition": "WAITING",
                    "owner": "human:ktogias",
                    "reason": "Await the exact-head review.",
                    "resume_event": "native_exact_head_review",
                    "evidence_sha256": "human-evidence",
                },
                {},
            ),
            (
                "dependency",
                {
                    "id": "dependency-gate",
                    "kind": "TECHNICAL",
                    "subject": subject,
                    "source_sha256": "dependency-evidence",
                },
                {
                    "id": "dependency-gate",
                    "disposition": "WAITING",
                    "owner": "human:ktogias",
                    "reason": "Await the captured dependency check.",
                    "resume_event": "native_exact_head_review",
                    "evidence_sha256": "dependency-evidence",
                    "dependency_pr_number": 600,
                    "dependency_head_sha": "b" * 40,
                },
                {
                    "continuation_frontier": {
                        "dependency_waits": [
                            {
                                "subject": subject,
                                "dependency": dependency,
                                "evidence_sha256": "dependency-evidence",
                                "check_run_id": 123,
                                "protected_revision": "protected",
                            }
                        ]
                    }
                },
            ),
            (
                "check_run",
                {
                    "id": "check-gate",
                    "kind": "TECHNICAL",
                    "source_kind": "canonical_criterion",
                    "subject": subject,
                    "source_sha256": "check-evidence",
                    "canonical": {"check_run_id": 456},
                },
                {
                    "id": "check-gate",
                    "disposition": "WAITING",
                    "owner": "provider:canonical-gate",
                    "reason": "Await the exact-head check update.",
                    "resume_event": "provider_source_changed",
                    "evidence_sha256": "check-evidence",
                    "check_run_id": 456,
                },
                {
                    "continuation_frontier": {
                        "rows": [
                            {
                                "id": "check-gate",
                                "kind": "TECHNICAL",
                                "source_kind": "canonical_criterion",
                                "subject": subject,
                                "source_sha256": "check-evidence",
                                "canonical": {"check_run_id": 456},
                            }
                        ]
                    }
                },
            ),
        )
        for name, gate_row, claim, extra_job in cases:
            with self.subTest(name=name):
                job: n.Native = {
                    "authority_context": {
                        "_coverage": {"coverage": "COMPLETE"},
                    },
                    "continuation_contract": {"frontier_sha256": "lineage"},
                    **extra_job,
                }
                frontier = {"coverage": "COMPLETE", "rows": [row, gate_row]}
                n.validate_progress(
                    job, frontier, row, claim, {"assignments": []}, [claim]
                )
                binding = n.gate_binding(job, gate_row, claim)
                self.assertIsNotNone(binding)
                assert binding is not None
                self.assertEqual(binding["row"], gate_row["id"])
                self.assertEqual(binding["resume_event"], claim["resume_event"])
                self.assertEqual(binding["head_sha"], subject["head_sha"])
                if name == "dependency":
                    self.assertEqual(binding["resume_subject"], dependency)
                    self.assertEqual(binding["canonical"]["check_run_id"], 123)
                elif name == "check_run":
                    self.assertEqual(binding["canonical"]["check_run_id"], 456)
                invalid_claims = []
                if "evidence_sha256" in claim:
                    invalid_claims.append(
                        {**claim, "evidence_sha256": "different-evidence"}
                    )
                if name == "dependency":
                    invalid_claims.append({**claim, "dependency_head_sha": "c" * 40})
                elif name == "check_run":
                    invalid_claims.append({**claim, "check_run_id": 789})
                else:
                    invalid_claims.append(
                        {**claim, "resume_event": "unsupported_event"}
                    )
                for invalid in invalid_claims:
                    with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                        n.validate_progress(
                            job,
                            frontier,
                            row,
                            invalid,
                            {"assignments": []},
                            [invalid],
                        )

    def test_progress_claim_keeps_its_identity_and_resolves_distinct_gate_row(
        self,
    ) -> None:
        progress_claim: n.Native = {
            "id": self.row["id"],
            "disposition": "WAITING",
            "owner": "human:ktogias",
            "reason": "Await the exact-head review.",
            "resume_event": "gate:gate-G",
        }
        head = "a" * 40
        gate_row: n.Native = {
            "id": "gate-G",
            "kind": "HUMAN_MERGE",
            "source_kind": "canonical_criterion",
            "subject": {"pr_number": 500, "head_sha": head},
            "source_sha256": "gate-evidence",
            "canonical": {"criterion": "M16"},
        }
        gate_claim: n.Native = {
            "id": "gate-G",
            "disposition": "WAITING",
            "owner": "human:ktogias",
            "reason": "Await the exact-head review.",
            "resume_event": "native_exact_head_review",
            "evidence_sha256": "gate-evidence",
        }
        frontier = {"coverage": "COMPLETE", "rows": [self.row, gate_row]}
        claims = [progress_claim, gate_claim]

        n.validate_progress(
            self.job, frontier, self.row, progress_claim, {"assignments": []}, claims
        )
        binding = n.gate_binding(self.job, gate_row, gate_claim)
        self.assertIsNotNone(binding)
        assert binding is not None
        self.assertEqual(binding["row"], "gate-G")
        self.assertEqual(binding["resume_event"], "native_exact_head_review")
        self.assertEqual(binding["head_sha"], head)

        gate = {**binding, "at": self.now}
        record = {
            "kind": "review",
            "number": 500,
            "material_id": "review:exact-head",
            "observed_at": self.now + 1,
            "payload": {
                "item": {
                    "commit_id": head,
                    "submitted_at": datetime.fromtimestamp(
                        self.now + 0.5, UTC
                    ).isoformat(),
                }
            },
        }
        fact = {"head": head, "provider_id": 123}
        self.assertEqual(
            n.gate_resume(gate, record, fact, self.now + 2, owner_review=True),
            "OWNER_REVIEW",
        )

        invalid_cases = (
            ({**progress_claim, "id": "wrong-progress"}, claims, frontier),
            ({**progress_claim, "resume_event": "gate:missing"}, claims, frontier),
            (progress_claim, claims, {"coverage": "COMPLETE", "rows": [self.row]}),
            (
                progress_claim,
                claims,
                {"coverage": "COMPLETE", "rows": [self.row, gate_row, gate_row]},
            ),
            (progress_claim, [progress_claim], frontier),
            (progress_claim, [*claims, gate_claim], frontier),
            (
                progress_claim,
                [
                    progress_claim,
                    {**gate_claim, "evidence_sha256": "different-evidence"},
                ],
                frontier,
            ),
            (
                progress_claim,
                [
                    progress_claim,
                    {**gate_claim, "resume_event": "unsupported_event"},
                ],
                frontier,
            ),
        )
        for invalid_claim, invalid_claims, invalid_frontier in invalid_cases:
            with (
                self.subTest(invalid_claim=invalid_claim),
                self.assertRaises(ValueError),
            ):
                n.validate_progress(
                    self.job,
                    invalid_frontier,
                    self.row,
                    invalid_claim,
                    {"assignments": []},
                    invalid_claims,
                )

    def test_waiting_claims_with_missing_or_mismatched_binding_fail_closed(
        self,
    ) -> None:
        scope: n.Native = {"kind": "work_item", "ref": "issue:499"}
        row = n.progress_row(scope, [])
        gate_row: n.Native = {
            "id": "human-gate",
            "kind": "HUMAN_MERGE",
            "source_kind": "canonical_criterion",
            "subject": {"pr_number": 500, "head_sha": "a" * 40},
            "source_sha256": "captured-evidence",
            "canonical": {"criterion": "M16"},
        }
        claim: n.Native = {
            "id": "human-gate",
            "disposition": "WAITING",
            "owner": "human:ktogias",
            "reason": "Await the exact-head review.",
            "resume_event": "native_exact_head_review",
            "evidence_sha256": "captured-evidence",
        }
        job: n.Native = {
            "authority_context": {"_coverage": {"coverage": "COMPLETE"}},
            "continuation_contract": {"frontier_sha256": "lineage"},
        }
        frontier = {"coverage": "COMPLETE", "rows": [row, gate_row]}
        for invalid in (
            {key: value for key, value in claim.items() if key != "evidence_sha256"},
            {**claim, "evidence_sha256": "different-evidence"},
            {**claim, "resume_event": "unsupported_event"},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                n.validate_progress(
                    job, frontier, row, invalid, {"assignments": []}, [invalid]
                )

    def _claims_by_mode(self) -> dict[str, n.Native]:
        return {
            "ASSIGNED": self.claim,
            "REFRESH": {
                "id": self.row["id"],
                "disposition": "REFRESH",
                "reason": "need a fresher read",
            },
            "WAITING": {
                "id": self.row["id"],
                "disposition": "WAITING",
                "owner": "human:ktogias",
                "reason": "wait",
                "resume_event": "gate:other",
            },
        }

    def test_malformed_or_missing_frontier_is_a_namespaced_refusal(self) -> None:
        good = self.row
        frontiers: list[object] = [
            None,
            [],
            {"coverage": "COMPLETE"},
            {"coverage": "COMPLETE", "rows": None},
            {"coverage": "COMPLETE", "rows": {"a": good}},
            {"coverage": "COMPLETE", "rows": [good, "row"]},
            {"coverage": "COMPLETE", "rows": [good, {"kind": "TECHNICAL"}]},
            {"coverage": "COMPLETE", "rows": [good, {"id": "x"}]},
            {"coverage": "COMPLETE", "rows": [good, {"id": "", "kind": "TECHNICAL"}]},
        ]
        for mode, claim in self._claims_by_mode().items():
            for frontier in frontiers:
                with (
                    self.subTest(mode=mode, frontier=frontier),
                    self.assertRaisesRegex(
                        ValueError, "^PROJECT_PROGRESS the captured frontier"
                    ),
                ):
                    n.validate_progress(
                        self.job,
                        cast("n.Native", frontier),
                        self.row,
                        claim,
                        self.decoded,
                        [claim],
                    )

    def test_missing_or_unsupported_target_is_refused_for_every_claim(self) -> None:
        for operation in ({}, {"operation_target": "repo:x"}, {"operation_target": 5}):
            decoded: n.Native = {"assignments": [{"operation": operation}]}
            for mode, claim in self._claims_by_mode().items():
                with (
                    self.subTest(mode=mode, operation=operation),
                    self.assertRaisesRegex(ValueError, "^PROJECT_PROGRESS .*target"),
                ):
                    n.validate_progress(
                        self.job, self.frontier, self.row, claim, decoded, [claim]
                    )

    def test_supported_targets_still_pass_on_non_assigned_claims(self) -> None:
        refresh = self._claims_by_mode()["REFRESH"]
        job = copy.deepcopy(self.job)
        job["authority_context"]["_coverage"] = {"coverage": "INCOMPLETE"}
        for target in ("issue:325", "pr:500"):
            decoded: n.Native = {
                "assignments": [{"operation": {"operation_target": target}}]
            }
            n.validate_progress(
                job, self.frontier, self.row, refresh, decoded, [refresh]
            )


if __name__ == "__main__":
    unittest.main()
