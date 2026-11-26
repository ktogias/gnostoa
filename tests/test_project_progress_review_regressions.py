"""Review regressions: binding resolution stays owned; missing evidence holds egress."""

from __future__ import annotations

import copy
import json
import unittest
from datetime import UTC, datetime
from typing import Any

from tools import project_progress_native as n


class MigrationRearmTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = 1_800_000_000.0
        self.scope = {"kind": "work_item", "ref": "issue:496"}
        self.original = {"kind": "operation", "delivery_key": "completed-step"}
        self.store: n.Native = {}
        self.bound, _, _ = n.open_obligation(
            self.store, self.scope, [self.original], None, self.now
        )
        self.bound.update(status="DISCHARGED", discharge="QUIESCENT")
        self.bound["requests"] = [self.request("bound-request", self.now, "SENT")]
        self.bound["requests"][0]["input_sha256"] = self.fingerprint(self.bound)
        self.old, _, _ = n.open_obligation(
            self.store,
            {"kind": "work_item", "ref": None},
            [self.original],
            "unresolved-step",
            self.now,
        )

    @staticmethod
    def request(key: str, at: float, state: str) -> n.Native:
        return {
            "key": key,
            "at": datetime.fromtimestamp(at, UTC).isoformat(),
            "state": state,
        }

    @staticmethod
    def fingerprint(obligation: n.Native) -> str:
        return n.reconciliation_fingerprint(obligation)

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

    def test_replaying_migrated_origin_keeps_single_successor_after_restart(
        self,
    ) -> None:
        self.old["requests"] = [
            self.request("original-request", self.now + 1, "INTENT")
        ]
        bound = n.migrate(self.store, self.old, self.scope, self.now + 2)
        self.assertEqual(self.old["status"], "MIGRATED")
        expected_requests = copy.deepcopy(bound["requests"])
        self.store = json.loads(json.dumps(self.store))
        replayed, added, refresh = n.open_obligation(
            self.store,
            {"kind": "work_item", "ref": None},
            [self.original],
            "unresolved-step",
            self.now + 3,
        )
        self.assertFalse(added)
        self.assertIsNone(refresh)
        self.assertEqual(replayed["id"], bound["id"])
        self.assertEqual(self.store[self.old["id"]]["status"], "MIGRATED")
        self.assertEqual(replayed["requests"], expected_requests)
        self.assertEqual(
            [
                obligation["id"]
                for obligation in self.store.values()
                if obligation["status"] != "MIGRATED"
            ],
            [bound["id"]],
        )
        replayed_again, _, _ = n.open_obligation(
            self.store,
            {"kind": "work_item", "ref": None},
            [self.original],
            "unresolved-step",
            self.now + 4,
        )
        self.assertEqual(replayed_again["id"], bound["id"])
        self.assertEqual(self.store[self.old["id"]]["status"], "MIGRATED")

    def test_replaying_migrated_origin_without_successor_fails_closed(self) -> None:
        bound = n.migrate(self.store, self.old, self.scope, self.now + 1)
        del self.store[bound["id"]]
        replayed, added, refresh = n.open_obligation(
            self.store,
            {"kind": "work_item", "ref": None},
            [self.original],
            "unresolved-step",
            self.now + 2,
        )
        self.assertEqual(replayed["status"], "MIGRATED")
        self.assertFalse(added)
        self.assertEqual(refresh, "SOURCE_PENDING/REFRESH")
        self.assertNotIn("OPEN", [value["status"] for value in self.store.values()])

    def test_migrate_incomparable_scope_observations_preserves_refresh_requirement(
        self,
    ) -> None:
        """PRRT_kwDOToCF3c67yHvn: Incomparable epochs require refresh and must not drop requirement or tombstone."""
        held = {
            "kind": "scope",
            "generation": "g1",
            "observed": {"epoch": "reader-a", "seq": 1},
        }
        incoming = {
            "kind": "scope",
            "generation": "g2",
            "observed": {"epoch": "reader-b", "seq": 1},
        }
        store: n.Native = {}
        dest_scope = {"kind": "work_item", "ref": "issue:500"}
        _dest_ob, _, _ = n.open_obligation(store, dest_scope, [held], None, self.now)
        unbound_scope = {"kind": "work_item", "ref": None}
        unbound_ob, _, _ = n.open_obligation(
            store, unbound_scope, [incoming], "unresolved-step", self.now
        )
        bound = n.migrate(store, unbound_ob, dest_scope, self.now + 1)
        # On the admitted buggy revision:
        # unbound_ob is prematurely marked MIGRATED and no refresh requirement is preserved.
        # The expected behavior for the repair is that refresh requirement is preserved and
        # unbound_ob is not marked MIGRATED (or a typed pending refresh result is exposed).
        self.assertNotEqual(unbound_ob["status"], "MIGRATED")
        self.assertEqual(getattr(bound, "refresh", None), "SOURCE_PENDING/REFRESH")

    def test_migrate_incomparable_scope_without_destination_leaves_store_unchanged_across_json_roundtrip(
        self,
    ) -> None:
        """PRRT_kwDOToCF3c68I4_f: migration needing source refresh leaves store unchanged without inserting OPEN destination."""
        incoming = {
            "kind": "scope",
            "generation": "g2",
        }
        store: n.Native = {}
        unbound_scope = {"kind": "work_item", "ref": None}
        unbound_ob = {
            "id": "unbound-1",
            "status": "OPEN",
            "scope": unbound_scope,
            "sources": [incoming],
            "requests": [],
            "created_at": "2026-11-25T00:00:00Z",
        }
        store["unbound-1"] = unbound_ob
        dest_scope = {"kind": "work_item", "ref": "issue:500"}
        dest_oid = n.scope_identity(dest_scope)
        store_before = copy.deepcopy(store)
        unbound_before = copy.deepcopy(unbound_ob)

        result = n.migrate(store, unbound_ob, dest_scope, self.now + 1)

        self.assertEqual(getattr(result, "refresh", None), "SOURCE_PENDING/REFRESH")
        self.assertNotIn(dest_oid, store)
        self.assertEqual(store, store_before)
        self.assertEqual(unbound_ob, unbound_before)

        # JSON round trip preserves store without inserting OPEN destination
        reloaded_store = json.loads(json.dumps(store))
        self.assertNotIn(dest_oid, reloaded_store)
        self.assertEqual(len(reloaded_store), 1)
        self.assertIn(unbound_ob["id"], reloaded_store)
        self.assertEqual(reloaded_store[unbound_ob["id"]]["status"], "OPEN")

    def test_migrate_rejects_unresolved_destination_and_self_migration_leaving_store_and_unbound_unchanged(
        self,
    ) -> None:
        """PRRT_kwDOToCF3c68Tkbe: reject unresolved destination or self-migration without store/record mutation."""
        store: n.Native = {}
        unbound_record: n.Native = {
            "id": "unbound-42",
            "status": "OPEN",
            "scope": {"kind": "work_item", "ref": None},
            "sources": [{"kind": "operation", "delivery_key": "step-1"}],
            "requests": [self.request("req-1", self.now, "INTENT")],
            "created_at": "2026-11-25T00:00:00Z",
        }
        store["unbound-42"] = unbound_record

        # 1. Unresolved destination (ref is None / empty)
        unresolved_destinations: list[dict[str, Any]] = [
            {"kind": "work_item", "ref": None},
            {"kind": "work_item"},
            {"kind": "work_item", "ref": ""},
        ]
        for dest in unresolved_destinations:
            store_before = copy.deepcopy(store)
            unbound_before = copy.deepcopy(unbound_record)
            with self.assertRaisesRegex(ValueError, "destination.*unresolved"):
                n.migrate(store, unbound_record, dest, self.now + 1)
            self.assertEqual(store, store_before)
            self.assertEqual(unbound_record, unbound_before)

        # 2. Self-migration: destination identity equals source unbound id
        # Compute destination id for an admitted resolved scope
        dest_scope = {"kind": "work_item", "ref": "issue:500"}
        dest_oid = n.scope_identity(dest_scope)

        self_unbound: n.Native = {
            "id": dest_oid,
            "status": "OPEN",
            "scope": dest_scope,
            "sources": [{"kind": "operation", "delivery_key": "step-self"}],
            "requests": [self.request("req-self", self.now, "INTENT")],
            "created_at": "2026-11-25T00:00:00Z",
        }
        store_self: n.Native = {dest_oid: self_unbound}
        store_self_before = copy.deepcopy(store_self)
        self_unbound_before = copy.deepcopy(self_unbound)

        with self.assertRaisesRegex(ValueError, "self-migration"):
            n.migrate(store_self, self_unbound, dest_scope, self.now + 1)
        self.assertEqual(store_self, store_self_before)
        self.assertEqual(self_unbound, self_unbound_before)

    def test_migrate_handles_migrated_origin_replay_and_rejects_conflicting_destination(
        self,
    ) -> None:
        """PRRT_kwDOToCF3c68WHER: already-MIGRATED origin is accepted only if destination matches successor."""
        store: n.Native = {}
        dest_scope_1 = {"kind": "work_item", "ref": "issue:500"}
        dest_oid_1 = n.scope_identity(dest_scope_1)
        dest_scope_2 = {"kind": "work_item", "ref": "issue:501"}
        dest_oid_2 = n.scope_identity(dest_scope_2)

        unbound: n.Native = {
            "id": "unbound-42",
            "status": "OPEN",
            "scope": {"kind": "work_item", "ref": None},
            "sources": [{"kind": "operation", "delivery_key": "step-1"}],
            "requests": [self.request("req-1", self.now, "INTENT")],
            "created_at": "2026-11-25T00:00:00Z",
        }
        store["unbound-42"] = unbound

        # Migrate origin to dest_scope_1 initially
        bound_1 = n.migrate(store, unbound, dest_scope_1, self.now + 1)
        self.assertEqual(bound_1["id"], dest_oid_1)
        self.assertEqual(unbound["status"], "MIGRATED")
        self.assertEqual(unbound["superseded_by"], dest_oid_1)

        # JSON round-trip
        store_rt: n.Native = json.loads(json.dumps(store))
        unbound_rt: n.Native = store_rt["unbound-42"]

        # Case 1: Replay with matching destination returns successor idempotently without mutating store
        store_before_replay = copy.deepcopy(store_rt)
        unbound_before_replay = copy.deepcopy(unbound_rt)
        replayed = n.migrate(store_rt, unbound_rt, dest_scope_1, self.now + 2)
        self.assertEqual(replayed["id"], dest_oid_1)
        self.assertEqual(store_rt, store_before_replay)
        self.assertEqual(unbound_rt, unbound_before_replay)

        # Case 2: Conflicting destination is rejected with ValueError, leaving store & tombstone untouched
        store_before_conflict = copy.deepcopy(store_rt)
        unbound_before_conflict = copy.deepcopy(unbound_rt)
        with self.assertRaisesRegex(ValueError, "conflicting destination"):
            n.migrate(store_rt, unbound_rt, dest_scope_2, self.now + 3)
        self.assertEqual(store_rt, store_before_conflict)
        self.assertEqual(unbound_rt, unbound_before_conflict)
        self.assertNotIn(dest_oid_2, store_rt)

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
            {
                "authority_context": {
                    pointer: complete,
                    "_coverage": {"coverage": "COMPLETE"},
                }
            },
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
        before = copy.deepcopy(captured)
        changed = n.source_changes({pointer: captured}, {pointer: fresh}, [pointer])
        self.assertIsNotNone(changed)
        assert changed is not None
        self.assertEqual(changed[0], "SOURCE_PENDING")
        # The captured read keeps its own bytes: fresh data never fills the gap.
        self.assertEqual(captured, before)
        self.assertNotIn("observed_at", captured)


class MalformedPeerObligationIsolationTests(unittest.TestCase):
    def test_malformed_peer_does_not_crash_settled_or_retry_decisions(self) -> None:
        scope = {"kind": "work_item", "ref": "issue:77"}
        at = 1_000.0
        record = n.new_obligation("example", scope, at)
        record["requests"] = [
            {"key": "delivered", "at": "1970-01-01T00:16:40Z", "state": "SENT"}
        ]
        store = {
            "example": record,
            "another-scope": {
                "status": "OPEN",
                "requests": [{"key": "missing-time"}],
            },
        }

        # Settled branch must discharge even with the invalid peer
        settled_action, settled_reason = n.controller_decision(
            record,
            fate="DISCHARGE",
            reason="ASSIGNED",
            touched=False,
            linked_open=False,
            source_router_open=False,
            now=at + 1,
            obligations=store,
            current_input="same",
            last_input="same",
        )
        self.assertEqual((settled_action, settled_reason), ("DISCHARGE", "ASSIGNED"))

        # A new request with unverifiable budget must stay held with a stable diagnostic
        retry_action, retry_reason = n.controller_decision(
            record,
            fate="RETRY",
            reason="LOST",
            touched=False,
            linked_open=False,
            source_router_open=False,
            now=at + 1,
            obligations=store,
            current_input="same",
            last_input="same",
        )
        self.assertEqual((retry_action, retry_reason), ("HELD", "UNVERIFIABLE_BUDGET"))

        # But a malformed subject obligation itself still raises a named refusal
        with self.assertRaisesRegex(ValueError, "PROJECT_PROGRESS a request"):
            n.controller_decision(
                store["another-scope"],
                fate="RETRY",
                reason="LOST",
                touched=False,
                linked_open=False,
                source_router_open=False,
                now=at + 1,
                obligations=store,
                current_input="same",
                last_input="same",
            )


class OwnerAuthorityGateBindingTests(unittest.TestCase):
    """PRRT_kwDOToCF3c64wmlz / S572: owner authority is supplied by trusted caller, not hardcoded."""

    def test_gate_binding_and_validate_progress_accept_and_enforce_owner_authority(
        self,
    ) -> None:
        subject = {"pr_number": 500, "head_sha": "a" * 40}
        scope = {"kind": "work_item", "ref": "issue:499"}
        row = n.progress_row(scope, [])
        gate_row = {
            "id": "human-gate",
            "kind": "HUMAN_MERGE",
            "source_kind": "canonical_criterion",
            "subject": subject,
            "source_sha256": "human-evidence",
            "canonical": {"criterion": "M16"},
        }
        claim_configured = {
            "id": "human-gate",
            "disposition": "WAITING",
            "owner": "human:configured-owner",
            "reason": "Await the exact-head review.",
            "resume_event": "native_exact_head_review",
            "evidence_sha256": "human-evidence",
        }
        progress_claim = {
            "id": row["id"],
            "disposition": "WAITING",
            "owner": "human:configured-owner",
            "reason": "Await review.",
            "resume_event": "gate:human-gate",
        }
        job = {
            "authority_context": {"_coverage": {"coverage": "COMPLETE"}},
            "continuation_contract": {"frontier_sha256": "lineage"},
        }
        frontier = {"coverage": "COMPLETE", "rows": [row, gate_row]}

        # With matching configured owner_authority, gate binds and progress validates
        binding = n.gate_binding(
            job, gate_row, claim_configured, owner_authority="human:configured-owner"
        )
        self.assertIsNotNone(binding)
        assert binding is not None
        self.assertEqual(binding["owner"], "human:configured-owner")

        n.validate_progress(
            job,
            frontier,
            row,
            progress_claim,
            {"assignments": []},
            [progress_claim, claim_configured],
            owner_authority="human:configured-owner",
        )

        # Missing authority or absent keyword fails closed
        self.assertIsNone(n.gate_binding(job, gate_row, claim_configured))
        with self.assertRaises(ValueError):
            n.validate_progress(
                job,
                frontier,
                row,
                progress_claim,
                {"assignments": []},
                [progress_claim, claim_configured],
            )

        # Mismatched authority fails closed
        self.assertIsNone(
            n.gate_binding(
                job, gate_row, claim_configured, owner_authority="human:different-owner"
            )
        )
        with self.assertRaises(ValueError):
            n.validate_progress(
                job,
                frontier,
                row,
                progress_claim,
                {"assignments": []},
                [progress_claim, claim_configured],
                owner_authority="human:different-owner",
            )

    def test_validate_progress_m16_gate_requires_nonempty_captured_digest(
        self,
    ) -> None:
        """PRRT_kwDOToCF3c679brO: M16 gate requires nonempty captured digest matching linked claim."""
        subject = {"pr_number": 500, "head_sha": "a" * 40}
        scope = {"kind": "work_item", "ref": "issue:499"}
        row = n.progress_row(scope, [])
        gate_row_missing_digest = {
            "id": "human-gate",
            "kind": "HUMAN_MERGE",
            "source_kind": "canonical_criterion",
            "subject": subject,
            "canonical": {"criterion": "M16"},
        }
        claim_missing_digest = {
            "id": "human-gate",
            "disposition": "WAITING",
            "owner": "human:configured-owner",
            "reason": "Await the exact-head review.",
            "resume_event": "native_exact_head_review",
        }
        progress_claim = {
            "id": row["id"],
            "disposition": "WAITING",
            "owner": "human:configured-owner",
            "reason": "Await review.",
            "resume_event": "gate:human-gate",
        }
        job = {
            "authority_context": {"_coverage": {"coverage": "COMPLETE"}},
            "continuation_contract": {"frontier_sha256": "lineage"},
        }
        frontier = {"coverage": "COMPLETE", "rows": [row, gate_row_missing_digest]}

        # When both source_sha256 and evidence_sha256 are missing/None, gate must not bind and progress validation fails
        self.assertIsNone(
            n.gate_binding(
                job,
                gate_row_missing_digest,
                claim_missing_digest,
                owner_authority="human:configured-owner",
            )
        )
        with self.assertRaises(ValueError):
            n.validate_progress(
                job,
                frontier,
                row,
                progress_claim,
                {"assignments": []},
                [progress_claim, claim_missing_digest],
                owner_authority="human:configured-owner",
            )

    def test_advancing_observation_order_alone_preserves_reconciliation_fingerprint_and_discharge(
        self,
    ) -> None:
        """PRRT_kwDOToCF3c68CFgz: Advancing observation sequence leaves existing discharge accounted."""
        scope: n.Native = {"kind": "work_item", "ref": "issue:499"}
        source_initial: n.Native = {
            "kind": "scope",
            "observed": {"epoch": "reader-a", "seq": 1},
        }
        store: n.Native = {}
        now = 1_800_000_000.0
        obligation, added, refresh = n.open_obligation(
            store, scope, [source_initial], None, now
        )
        self.assertTrue(added)
        self.assertIsNone(refresh)

        # Record a sent request bound to the initial reconciliation fingerprint
        initial_fingerprint = n.reconciliation_fingerprint(obligation)
        obligation["requests"] = [
            {
                "key": "req-1",
                "at": datetime.fromtimestamp(now, UTC).isoformat(),
                "state": "SENT",
                "input_sha256": initial_fingerprint,
            }
        ]

        # Valid discharge accounts for the obligation
        action, reason = n.controller_decision(
            obligation,
            fate="DISCHARGE",
            reason="QUIESCENT",
            touched=False,
            linked_open=False,
            source_router_open=False,
            now=now,
            obligations=store,
            current_input=initial_fingerprint,
            last_input=obligation["requests"][-1].get("input_sha256"),
        )
        self.assertEqual((action, reason), ("DISCHARGE", "QUIESCENT"))

        # Advance ONLY the observation sequence (same-generation replay, no new evidence)
        source_advanced: n.Native = {
            "kind": "scope",
            "observed": {"epoch": "reader-a", "seq": 2},
        }
        added_adv, refresh_adv = n.merge_sources(obligation, [source_advanced])
        self.assertFalse(added_adv)
        self.assertFalse(refresh_adv)
        self.assertEqual(
            obligation["sources"][0]["observed"], {"epoch": "reader-a", "seq": 2}
        )

        # Progress row preserves raw observations, changing its ID
        old_row = n.progress_row(scope, [source_initial])
        row_advanced = n.progress_row(scope, obligation["sources"])
        self.assertNotEqual(old_row["id"], row_advanced["id"])
        self.assertNotEqual(old_row["source_sha256"], row_advanced["source_sha256"])

        # But the reconciliation input fingerprint excludes observation order and remains unchanged
        reconciled_fingerprint = n.reconciliation_fingerprint(obligation)
        self.assertEqual(reconciled_fingerprint, initial_fingerprint)

        # controller_decision still accounts for the obligation with DISCHARGE rather than spurious REQUEST
        settled_action, settled_reason = n.controller_decision(
            obligation,
            fate="DISCHARGE",
            reason="QUIESCENT",
            touched=False,
            linked_open=False,
            source_router_open=False,
            now=now + 1,
            obligations=store,
            current_input=reconciled_fingerprint,
            last_input=obligation["requests"][-1].get("input_sha256"),
        )
        self.assertEqual((settled_action, settled_reason), ("DISCHARGE", "QUIESCENT"))

    def test_prrt_kwdotocf3c68ezgl_malformed_read_does_not_validate_quiescent(
        self,
    ) -> None:
        """PRRT_kwDOToCF3c68EZgL: context completeness checks normalized coverage of reads."""
        now = 1_800_000_000.0
        scope_source = "https://github.com/ktogias/gnostoa/issues/496"
        row = n.progress_row({"kind": "work_item", "ref": "issue:496"}, [])
        claim: n.Native = {
            "id": row["id"],
            "disposition": "QUIESCENT",
            "evidence": [
                {"source": scope_source, "digest": "scope-digest", "observed_at": now}
            ],
        }
        valid_scope_read: n.Native = {
            "kind": "work_item",
            "number": 496,
            "body_sha256": "scope-digest",
            "coverage": "CURRENT",
            "body_complete": True,
            "observed_at": now,
        }
        # Baseline with valid scope read alone satisfies quiescence
        valid_context: n.Native = {
            scope_source: valid_scope_read,
            "_coverage": {"coverage": "COMPLETE"},
        }
        n.validate_progress(
            {"authority_context": valid_context},
            {"coverage": "COMPLETE", "rows": [row]},
            row,
            claim,
            {"assignments": []},
            [claim],
        )

        # An additional malformed mapping-shaped read (e.g. {}) is normalized as incomplete
        # and must prevent QUIESCENT from validating
        malformed_context: n.Native = {
            scope_source: valid_scope_read,
            "https://github.com/ktogias/gnostoa/pull/999": {},
            "_coverage": {"coverage": "COMPLETE"},
        }
        with self.assertRaisesRegex(ValueError, "^PROJECT_PROGRESS quiescence"):
            n.validate_progress(
                {"authority_context": malformed_context},
                {"coverage": "COMPLETE", "rows": [row]},
                row,
                claim,
                {"assignments": []},
                [claim],
            )

    def test_held_frontier_member_deep_validation_fails_closed(self) -> None:
        """PRRT_kwDOToCF3c68G5zK: invalid nested subjects, run IDs, or obligation IDs refuse whole table."""
        subject = {"pr_number": 500, "head_sha": "a" * 40}
        dependency = {"pr_number": 600, "head_sha": "b" * 40}
        gate: n.Native = {
            "id": "gate",
            "kind": "TECHNICAL",
            "source_kind": "canonical_criterion",
            "subject": subject,
            "source_sha256": "check-sha",
            "canonical": {"check_run_id": 456},
        }
        native: n.Native = {
            "id": "native-row",
            "kind": "UNFINISHED",
            "source_kind": "native_outcome",
            "subject": subject,
            "source_key": "delivery:1",
            "source_sha256": "native-sha",
        }
        valid_dep_wait: n.Native = {
            "subject": subject,
            "dependency": dependency,
            "evidence_sha256": "dep-sha",
            "check_run_id": 123,
        }
        valid_prov_wait: n.Native = {
            "subject": subject,
            "source_key": "delivery:1",
            "source_sha256": "native-sha",
            "obligation_ids": ["gate"],
            "observed_check_run_id": 456,
        }
        prov_claim: n.Native = {
            "id": "native-row",
            "disposition": "WAITING",
            "owner": "provider:canonical-gate",
            "reason": "Wait",
            "resume_event": "provider_source_changed",
            "evidence_sha256": "check-sha",
            "check_run_id": 456,
        }
        dep_gate: n.Native = {
            "id": "gate",
            "kind": "TECHNICAL",
            "subject": subject,
            "source_sha256": "dep-sha",
        }
        dep_claim: n.Native = {
            "id": "gate",
            "disposition": "WAITING",
            "owner": "human:ktogias",
            "reason": "Wait",
            "resume_event": "native_exact_head_review",
            "evidence_sha256": "dep-sha",
            "dependency_pr_number": 600,
            "dependency_head_sha": "b" * 40,
        }

        # Valid baseline succeeds
        job_prov: n.Native = {
            "continuation_frontier": {
                "rows": [gate],
                "provider_waits": [valid_prov_wait],
            }
        }
        self.assertIsNotNone(n.gate_binding(job_prov, native, prov_claim))

        job_dep: n.Native = {
            "continuation_frontier": {"dependency_waits": [valid_dep_wait]}
        }
        self.assertIsNotNone(
            n.gate_binding(
                job_dep, dep_gate, dep_claim, owner_authority="human:ktogias"
            )
        )

        # Malformed sibling in provider_waits refuses whole table
        for bad_wait in (
            {**valid_prov_wait, "subject": {}},
            {**valid_prov_wait, "subject": {"pr_number": -1, "head_sha": "a" * 40}},
            {**valid_prov_wait, "observed_check_run_id": 0},
            {**valid_prov_wait, "observed_check_run_id": -10},
            {**valid_prov_wait, "obligation_ids": []},
            {**valid_prov_wait, "obligation_ids": ["gate", ""]},
            {**valid_prov_wait, "obligation_ids": [123]},
        ):
            damaged_job: n.Native = {
                "continuation_frontier": {
                    "rows": [gate],
                    "provider_waits": [valid_prov_wait, bad_wait],
                }
            }
            with self.subTest(bad_prov_wait=bad_wait):
                self.assertIsNone(n.gate_binding(damaged_job, native, prov_claim))

        # Malformed sibling in dependency_waits refuses whole table
        for bad_wait in (
            {**valid_dep_wait, "subject": {}},
            {**valid_dep_wait, "dependency": {}},
            {**valid_dep_wait, "dependency": {"pr_number": 0, "head_sha": "b" * 40}},
        ):
            damaged_job = {
                "continuation_frontier": {
                    "dependency_waits": [valid_dep_wait, bad_wait]
                }
            }
            with self.subTest(bad_dep_wait=bad_wait):
                self.assertIsNone(
                    n.gate_binding(
                        damaged_job,
                        dep_gate,
                        dep_claim,
                        owner_authority="human:ktogias",
                    )
                )

    def test_project_progress_waiting_claim_requires_matching_captured_frontier_row(
        self,
    ) -> None:
        """PRRT_kwDOToCF3c68J0HA: require the supplied PROJECT_PROGRESS row to match a captured frontier row."""
        scope: n.Native = {"kind": "work_item", "ref": "issue:499"}
        progress_row = n.progress_row(scope, [])
        head = "a" * 40
        gate_row: n.Native = {
            "id": "gate-G",
            "kind": "HUMAN_MERGE",
            "source_kind": "canonical_criterion",
            "subject": {"pr_number": 500, "head_sha": head},
            "source_sha256": "gate-evidence",
            "canonical": {"criterion": "M16"},
        }
        progress_claim: n.Native = {
            "id": progress_row["id"],
            "disposition": "WAITING",
            "owner": "human:ktogias",
            "reason": "Await the exact-head review.",
            "resume_event": "gate:gate-G",
        }
        gate_claim: n.Native = {
            "id": "gate-G",
            "disposition": "WAITING",
            "owner": "human:ktogias",
            "reason": "Await the exact-head review.",
            "resume_event": "native_exact_head_review",
            "evidence_sha256": "gate-evidence",
        }
        claims = [progress_claim, gate_claim]
        frontier_with_both = {"coverage": "COMPLETE", "rows": [progress_row, gate_row]}
        frontier_gate_only = {"coverage": "COMPLETE", "rows": [gate_row]}
        altered_progress_row = {**progress_row, "kind": "TECHNICAL"}
        frontier_with_altered = {
            "coverage": "COMPLETE",
            "rows": [altered_progress_row, gate_row],
        }
        job: n.Native = {
            "authority_context": {"_coverage": {"coverage": "COMPLETE"}},
            "continuation_contract": {"frontier_sha256": "lineage"},
            "continuation_frontier": {"rows": [gate_row]},
        }

        # Baseline: with both rows present in frontier, validation passes
        n.validate_progress(
            job,
            frontier_with_both,
            progress_row,
            progress_claim,
            {"assignments": []},
            claims,
            owner_authority="human:ktogias",
        )

        # Absent progress row fails closed even though gate is present
        with self.assertRaisesRegex(
            ValueError, "^PROJECT_PROGRESS the captured frontier does not hold this row"
        ):
            n.validate_progress(
                job,
                frontier_gate_only,
                progress_row,
                progress_claim,
                {"assignments": []},
                claims,
                owner_authority="human:ktogias",
            )

        # Altered progress row in frontier also fails closed
        with self.assertRaisesRegex(
            ValueError, "^PROJECT_PROGRESS the captured frontier does not hold this row"
        ):
            n.validate_progress(
                job,
                frontier_with_altered,
                progress_row,
                progress_claim,
                {"assignments": []},
                claims,
                owner_authority="human:ktogias",
            )

    def test_held_rows_validation_accepts_progress_row_and_technical_gate_at_intake_and_pre_egress(
        self,
    ) -> None:
        """PRRT_kwDOToCF3c68Os_Q: held rows validation accepts both PROJECT_PROGRESS and technical gate."""
        scope: n.Native = {"kind": "work_item", "ref": "issue:499"}
        progress_row = n.progress_row(scope, [])
        head = "a" * 40
        gate_row: n.Native = {
            "id": "check-gate",
            "kind": "TECHNICAL",
            "source_kind": "canonical_criterion",
            "subject": {"pr_number": 500, "head_sha": head},
            "source_sha256": "check-evidence",
            "canonical": {"check_run_id": 456},
        }
        progress_claim: n.Native = {
            "id": progress_row["id"],
            "disposition": "WAITING",
            "owner": "provider:canonical-gate",
            "reason": "Await the exact-head check update.",
            "resume_event": "gate:check-gate",
        }
        check_claim: n.Native = {
            "id": "check-gate",
            "disposition": "WAITING",
            "owner": "provider:canonical-gate",
            "reason": "Await the exact-head check update.",
            "resume_event": "provider_source_changed",
            "evidence_sha256": "check-evidence",
            "check_run_id": 456,
        }
        claims = [progress_claim, check_claim]
        frontier_with_both = {"coverage": "COMPLETE", "rows": [progress_row, gate_row]}
        job: n.Native = {
            "authority_context": {"_coverage": {"coverage": "COMPLETE"}},
            "continuation_contract": {"frontier_sha256": "lineage"},
            "continuation_frontier": {"rows": [progress_row, gate_row]},
        }

        # Intake: binding technical gate succeeds when continuation frontier holds both rows
        binding = n.gate_binding(job, gate_row, check_claim)
        self.assertIsNotNone(binding)
        assert binding is not None
        self.assertEqual(binding["pr_number"], 500)
        self.assertEqual(binding["head_sha"], head)
        self.assertEqual(binding["canonical"]["check_run_id"], 456)

        # Pre-egress: validation succeeds when continuation frontier holds both rows
        n.validate_progress(
            job,
            frontier_with_both,
            progress_row,
            progress_claim,
            {"assignments": []},
            claims,
        )

        refusal = "^PROJECT_PROGRESS wait needs a supported exact gate binding"

        # Damaged authority: progress row missing scope damages table and fails closed
        bad_progress_scope_missing = {
            k: v for k, v in progress_row.items() if k != "scope"
        }
        job_scope_missing: n.Native = {
            **job,
            "continuation_frontier": {"rows": [bad_progress_scope_missing, gate_row]},
        }
        self.assertIsNone(n.gate_binding(job_scope_missing, gate_row, check_claim))
        with self.assertRaisesRegex(ValueError, refusal):
            n.validate_progress(
                job_scope_missing,
                frontier_with_both,
                progress_row,
                progress_claim,
                {"assignments": []},
                claims,
            )

        # Damaged authority: progress row with invalid scope damages table and fails closed
        bad_progress_scope_invalid = {
            **progress_row,
            "scope": {"kind": "work_item", "ref": "invalid"},
        }
        job_scope_invalid: n.Native = {
            **job,
            "continuation_frontier": {"rows": [bad_progress_scope_invalid, gate_row]},
        }
        self.assertIsNone(n.gate_binding(job_scope_invalid, gate_row, check_claim))
        with self.assertRaisesRegex(ValueError, refusal):
            n.validate_progress(
                job_scope_invalid,
                frontier_with_both,
                progress_row,
                progress_claim,
                {"assignments": []},
                claims,
            )

        # Damaged authority: gate row missing subject damages table and fails closed
        bad_gate_missing_subject = {k: v for k, v in gate_row.items() if k != "subject"}
        job_gate_missing_subject: n.Native = {
            **job,
            "continuation_frontier": {"rows": [progress_row, bad_gate_missing_subject]},
        }
        self.assertIsNone(
            n.gate_binding(job_gate_missing_subject, gate_row, check_claim)
        )
        with self.assertRaisesRegex(ValueError, refusal):
            n.validate_progress(
                job_gate_missing_subject,
                frontier_with_both,
                progress_row,
                progress_claim,
                {"assignments": []},
                claims,
            )

    def test_batch1_github_and_progress_defects_red_baseline(self) -> None:
        from tools import project_progress as p
        from tools import project_progress_github as g

        self.assertEqual(g.closed_targets(None), ())
        self.assertTrue(
            g.valid_subject(
                {
                    "pr_number": 500,
                    "head_sha": "A1B2C3D4" * 5,
                }
            )
        )
        self.assertEqual(
            g.closed_reads(
                {
                    "pr_old": {
                        "kind": "pr",
                        "pr_number": 500,
                        "state": "closed",
                    },
                    "pr_new": {
                        "kind": "pr",
                        "pr_number": 500,
                        "state": "open",
                        "merged": False,
                    },
                }
            ),
            (),
        )
        self.assertEqual(
            p.request_budget(
                [p.RequestStamp(key="k1", at=float("nan"), carried=False)],
                [],
                now=1_800_000_000.0,
            ),
            "TIME_MONOTONICITY_HOLD",
        )
        held = [
            p.Source(
                category="scope",
                key="k1",
                fingerprint="fp-old",
                observed=("e1", 1),
                replaces_category=True,
            )
        ]
        incoming = p.Source(
            category="scope",
            key="k1",
            fingerprint="fp-new",
            observed=("e1", 2),
            replaces_category=True,
        )
        merged, _, _ = p.merge_sources(held, [incoming])
        self.assertEqual(merged[0].fingerprint, "fp-new")


if __name__ == "__main__":
    unittest.main()
