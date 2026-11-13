"""Review regressions: binding resolution stays owned; missing evidence holds egress."""

from __future__ import annotations

import copy
import json
import unittest
from datetime import UTC, datetime

from tools import project_progress_native as n


class MigrationRearmTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = 1_800_000_000.0
        self.scope = {"kind": "work_item", "ref": "issue:496"}
        self.original = {"kind": "operation", "delivery_key": "completed-step"}
        self.store: n.Native = {}
        self.bound, _ = n.open_obligation(
            self.store, self.scope, [self.original], None, self.now
        )
        self.bound.update(status="DISCHARGED", discharge="QUIESCENT")
        self.bound["requests"] = [self.request("bound-request", self.now, "SENT")]
        self.bound["requests"][0]["input_sha256"] = self.fingerprint(self.bound)
        self.old, _ = n.open_obligation(
            self.store,
            {"kind": "work_item", "ref": None},
            [self.original],
            "unresolved-step",
            self.now,
        )

    def request(self, key: str, at: float, state: str) -> n.Native:
        return {
            "key": key,
            "at": datetime.fromtimestamp(at, UTC).isoformat(),
            "state": state,
        }

    @staticmethod
    def fingerprint(obligation: n.Native) -> str:
        return str(
            n.progress_row(
                obligation["scope"], obligation["sources"], obligation.get("chains")
            )["id"]
        )

    def decision(
        self,
        bound: n.Native,
        now: float,
        fate: str = "DISCHARGE",
        reason: str = "QUIESCENT",
    ) -> tuple[str, str]:
        return n.controller_decision(
            bound,
            fate=fate,
            reason=reason,
            touched=False,
            linked_open=False,
            source_router_open=False,
            now=now,
            obligations=self.store,
            current_input=self.fingerprint(bound),
            last_input=bound["requests"][-1].get("input_sha256"),
        )

    def test_new_sources_reopen_the_existing_discharged_destination(self) -> None:
        n.merge_sources(
            self.old, [{"kind": "operation", "delivery_key": "new-unresolved-step"}]
        )
        bound = n.migrate(self.store, self.old, self.scope, self.now + 1)
        self.assertEqual(
            bound["status"],
            "OPEN",
            "unresolved work was tombstoned into an accounted destination",
        )
        self.assertEqual(bound["reopened_by"], "BINDING_RESOLVED")
        self.assertEqual(self.old["status"], "MIGRATED")
        self.assertEqual(self.old["superseded_by"], bound["id"])
        self.assertEqual(self.decision(bound, self.now + 1), ("REQUEST", "QUIESCENT"))

    def test_duplicate_facts_keep_binding_resolution_dirty_across_cap_and_restart(
        self,
    ) -> None:
        self.bound["requests"] = [
            self.request(str(i), self.now - i, "SENT") for i in (3, 2, 1)
        ]
        self.bound["requests"][-1]["input_sha256"] = self.fingerprint(self.bound)
        bound = n.migrate(self.store, self.old, self.scope, self.now + 1)
        self.assertEqual(bound["status"], "OPEN")
        self.assertNotEqual(
            self.fingerprint(bound),
            bound["requests"][-1]["input_sha256"],
            "binding resolution was only an ephemeral touched flag",
        )
        self.assertEqual(self.decision(bound, self.now + 1), ("HELD", "IDENTITY_CAP"))
        self.store = json.loads(json.dumps(self.store))
        bound = self.store[bound["id"]]
        self.assertEqual(
            self.decision(bound, self.now + 86401), ("REQUEST", "QUIESCENT")
        )
        binding = [s for s in bound["sources"] if s.get("kind") == "scope_binding"]
        self.assertEqual(len(binding), 1)
        self.assertEqual(binding[0]["key"], "binding-resolved:" + self.old["id"])

    def test_replaying_a_bound_first_save_does_not_recarry_history_or_rearm_again(
        self,
    ) -> None:
        self.old["requests"] = [
            self.request("pending-unbound-request", self.now + 1, "INTENT")
        ]
        old_on_disk = copy.deepcopy(self.old)
        bound = n.migrate(self.store, self.old, self.scope, self.now + 2)
        self.assertEqual(bound["status"], "OPEN")
        persisted = copy.deepcopy(bound)
        # The bound was atomically saved; the old OPEN file survived a crash before its tombstone.
        self.store[self.old["id"]] = old_on_disk
        bound_again = n.migrate(self.store, old_on_disk, self.scope, self.now + 3)
        self.assertEqual(
            bound_again,
            persisted,
            "recovery duplicated already-retained history or input",
        )
        self.assertEqual(old_on_disk["status"], "MIGRATED")
        self.assertEqual(old_on_disk["superseded_by"], bound_again["id"])

    def test_carried_intent_reemits_same_key_then_holds_without_new_request(
        self,
    ) -> None:
        self.old["requests"] = [
            self.request("pending-unbound-request", self.now + 1, "INTENT")
        ]
        self.old["chains"] = {"pr:498": {"waits": ["existing-gate"]}}
        old_bound_request = copy.deepcopy(self.bound["requests"][0])
        bound = n.migrate(self.store, self.old, self.scope, self.now + 2)
        self.assertEqual(bound["status"], "OPEN")
        self.assertEqual(bound["requests"][0], old_bound_request)
        self.assertEqual(bound["requests"][-1]["key"], "pending-unbound-request")
        self.assertEqual(bound["requests"][-1]["carried_from"], self.old["id"])
        self.assertEqual(bound["chains"], self.old["chains"])
        self.assertEqual(self.decision(bound, self.now + 2)[0], "REEMIT")
        bound["requests"][-1].update(state="SENT", input_sha256=self.fingerprint(bound))
        self.assertEqual(
            self.decision(bound, self.now + 3, "HOLD", "PENDING_INGRESS")[0], "HOLD"
        )
        self.assertEqual(
            len(bound["requests"]),
            2,
            "migration or reconciliation minted another request",
        )
        self.assertEqual(
            n.request_budget(self.store, bound, self.now + 3, daily_cap=2), "DAILY_CAP"
        )
        self.assertIsNone(
            n.request_budget(self.store, bound, self.now + 3, daily_cap=3)
        )


class MissingCapturedSourceTests(unittest.TestCase):
    def test_missing_capture_is_source_pending_even_with_fresh_provider_data(
        self,
    ) -> None:
        pointer = "https://github.com/ktogias/gnostoa/issues/496"
        read = {
            "kind": "work_item",
            "number": 496,
            "body_sha256": "body",
            "coverage": "CURRENT",
            "body_complete": True,
            "observed_at": 1.0,
        }
        for fresh in ({}, {pointer: read}):
            with self.subTest(fresh=bool(fresh)):
                result = n.source_changes({}, fresh, [pointer])
                self.assertIsNotNone(
                    result, "missing captured source was silently dropped"
                )
                assert result is not None
                self.assertEqual(result[0], "SOURCE_PENDING")
                self.assertIn(pointer, result[1])
        self.assertIsNone(n.source_changes({pointer: read}, {pointer: read}, [pointer]))
        self.assertIsNone(n.source_changes({}, {}, []))

    def test_one_missing_capture_never_disappears_among_other_valid_reads(self) -> None:
        pointer = "https://github.com/ktogias/gnostoa/issues/496"
        missing = "https://github.com/ktogias/gnostoa/issues/325"
        read = {
            "kind": "work_item",
            "number": 496,
            "body_sha256": "body",
            "coverage": "CURRENT",
            "body_complete": True,
            "observed_at": 1.0,
        }
        result = n.source_changes({pointer: read}, {pointer: read}, [pointer, missing])
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result[0], "SOURCE_PENDING")
        self.assertIn(missing, result[1])


class SourceEvidenceBoundsTests(unittest.TestCase):
    def test_tracked_attribute_addition_or_removal_requires_new_judgment(self) -> None:
        from dataclasses import replace

        from tools import project_progress as p
        from tools.agent_review_model import Ref

        before = p.Read(
            "source",
            Ref("work_item", "496"),
            "opaque-body",
            1.0,
            True,
            True,
            (("kind", "work_item"),),
        )
        added = replace(
            before, attributes=(*before.attributes, ("author_id", "532328"))
        )
        for captured, fresh in ((before, added), (added, before)):
            with self.subTest(added=len(fresh.attributes) > len(captured.attributes)):
                changed = p.source_changes((captured,), (fresh,))
                self.assertIsNotNone(
                    changed, "tracked metadata change was silently ignored"
                )
                assert changed is not None
                self.assertEqual(changed[0], "REPAIR_PENDING")
        self.assertIsNone(
            p.source_changes(
                (added,),
                (replace(added, attributes=tuple(reversed(added.attributes))),),
            )
        )

    def test_malformed_current_reads_cannot_validate_real_assignments(self) -> None:
        pointer = "https://github.com/ktogias/gnostoa/issues/496"
        complete = {
            "kind": "work_item",
            "number": 496,
            "body_sha256": "opaque-digest",
            "coverage": "CURRENT",
            "body_complete": True,
            "observed_at": 1.0,
        }
        row = n.progress_row({"kind": "work_item", "ref": "issue:496"}, [])
        frontier = {"coverage": "COMPLETE", "rows": [row]}
        decoded = {"assignments": [{"operation": {"operation_target": "issue:496"}}]}
        for field, value in (
            ("body_sha256", None),
            ("body_sha256", ""),
            ("body_sha256", True),
            ("body_complete", None),
            ("body_complete", 1),
            ("observed_at", None),
            ("observed_at", True),
            ("observed_at", "1.0"),
            ("observed_at", float("nan")),
            ("observed_at", float("inf")),
        ):
            held = dict(complete)
            if value is None:
                held.pop(field)
            else:
                held[field] = value
            claim = {
                "id": row["id"],
                "disposition": "ASSIGNED",
                "assignment_index": 0,
                "evidence": [
                    {
                        "source": pointer,
                        "digest": held.get("body_sha256"),
                        "observed_at": held.get("observed_at"),
                    }
                ],
            }
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                n.validate_progress(
                    {"authority_context": {pointer: held}},
                    frontier,
                    row,
                    claim,
                    decoded,
                    [claim],
                )
        claim = {
            "id": row["id"],
            "disposition": "ASSIGNED",
            "assignment_index": 0,
            "evidence": [
                {"source": pointer, "digest": "opaque-digest", "observed_at": 1.0}
            ],
        }
        n.validate_progress(
            {"authority_context": {pointer: complete}},
            frontier,
            row,
            claim,
            decoded,
            [claim],
        )

    def test_boolean_citation_does_not_alias_the_numeric_native_read_time(self) -> None:
        pointer = "https://github.com/ktogias/gnostoa/issues/496"
        read = {
            "kind": "work_item",
            "number": 496,
            "coverage": "CURRENT",
            "body_sha256": "opaque",
            "body_complete": True,
            "observed_at": 1.0,
        }
        row = n.progress_row({"kind": "work_item", "ref": "issue:496"}, [])
        claim = {
            "id": row["id"],
            "disposition": "ASSIGNED",
            "assignment_index": 0,
            "evidence": [{"source": pointer, "digest": "opaque", "observed_at": True}],
        }
        with self.assertRaises(ValueError):
            n.validate_progress(
                {"authority_context": {pointer: read}},
                {"coverage": "COMPLETE", "rows": [row]},
                row,
                claim,
                {"assignments": [{"operation": {"operation_target": "issue:496"}}]},
                [claim],
            )

    def test_missing_read_metadata_allows_refresh_and_never_silently_becomes_complete(
        self,
    ) -> None:
        pointer = "https://github.com/ktogias/gnostoa/issues/496"
        row = n.progress_row({"kind": "work_item", "ref": "issue:496"}, [])
        claim = {
            "id": row["id"],
            "disposition": "REFRESH",
            "reason": "Reacquire complete source evidence.",
        }
        historical = {
            "kind": "work_item",
            "number": 496,
            "coverage": "CURRENT",
            "body_sha256": "opaque-digest",
            "observed_at": 1.0,
        }
        n.validate_progress(
            {"authority_context": {pointer: historical}},
            {"coverage": "COMPLETE", "rows": [row]},
            row,
            claim,
            {"assignments": []},
            [claim],
        )
        self.assertNotIn("body_complete", historical)

    def test_a_malformed_captured_read_is_not_repaired_in_place_by_fresh_data(
        self,
    ) -> None:
        pointer = "https://github.com/ktogias/gnostoa/issues/496"
        fresh = {
            "kind": "work_item",
            "number": 496,
            "coverage": "CURRENT",
            "body_sha256": "opaque-digest",
            "body_complete": True,
            "observed_at": 2.0,
        }
        captured = dict(fresh)
        captured.pop("observed_at")
        changed = n.source_changes({pointer: captured}, {pointer: fresh}, [pointer])
        self.assertIsNotNone(changed)
        assert changed is not None
        self.assertEqual(changed[0], "SOURCE_PENDING")


if __name__ == "__main__":
    unittest.main()
