"""Native/provider seams preserve S52 evidence and journal identities, without I/O."""

from __future__ import annotations

import copy
import unittest
from datetime import UTC, datetime

from tools import project_progress_native as n


class NativeProgressTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = 1_800_000_000.0
        self.scope = {"kind": "work_item", "ref": "issue:496"}
        self.row = n.progress_row(
            self.scope, [{"kind": "operation", "delivery_key": "old-step"}]
        )
        self.frontier = {"coverage": "COMPLETE", "rows": [self.row]}
        self.reads = {
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
        self.job = {
            "authority_context": self.reads,
            "continuation_contract": {"frontier_sha256": "lineage"},
        }
        self.decoded = {
            "assignments": [{"operation": {"operation_target": "issue:325"}}]
        }
        self.claim = {
            "id": self.row["id"],
            "disposition": "ASSIGNED",
            "assignment_index": 0,
            "evidence": [
                {"source": url, "digest": read["body_sha256"], "observed_at": self.now}
                for url, read in self.reads.items()
            ],
        }

    def validate(self, claim: dict | None = None) -> None:
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
            row["observed_at"] += 20
        self.assertIsNone(n.source_changes(self.reads, fresh, pointers))
        original = self.reads[pointers[0]]
        original["source_binding_sha256"] = "original-provider-object"
        fresh[pointers[0]]["source_binding_sha256"] = "changed-provider-object"
        self.assertEqual(
            n.source_changes(self.reads, fresh, pointers)[0], "REPAIR_PENDING"
        )
        fresh.pop(pointers[0])
        self.assertEqual(
            n.source_changes(self.reads, fresh, pointers)[0], "SOURCE_PENDING"
        )

    def test_migration_keeps_tombstone_request_identity_and_budget_attribution(
        self,
    ) -> None:
        store = {}
        unbound, _ = n.open_obligation(
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

    def test_migration_retains_each_overlapping_request_record(self) -> None:
        store = {}
        old, _ = n.open_obligation(
            store, {"kind": "work_item", "ref": None}, [], "old", self.now
        )
        bound, _ = n.open_obligation(store, self.scope, [], None, self.now)
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
        row = {
            "id": "gate",
            "kind": "HUMAN_MERGE",
            "source_kind": "canonical_criterion",
            "subject": {"pr_number": 600, "head_sha": head},
            "source_sha256": "captured",
            "canonical": {"criterion": "M16"},
        }
        claim = {
            "id": "gate",
            "disposition": "WAITING",
            "owner": "human:ktogias",
            "resume_event": "native_exact_head_review",
            "evidence_sha256": "captured",
        }
        gate = n.gate_binding({}, row, claim)
        self.assertIsNotNone(gate)
        gate["at"] = self.now
        record = {
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
        fact = {"head": head, "provider_id": 90}
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
        record["payload"]["item"]["submitted_at"] = datetime.fromtimestamp(
            self.now - 1, UTC
        ).isoformat()
        self.assertIsNone(
            n.gate_resume(gate, record, fact, self.now + 2, owner_review=True)
        )


if __name__ == "__main__":
    unittest.main()
