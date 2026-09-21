from __future__ import annotations

import base64
import importlib.util
import json
import unittest
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


def _fixtures() -> Any:
    path = Path(__file__).with_name("test_review_reconcile_l1.py")
    spec = importlib.util.spec_from_file_location(
        "l1_identity_collision_fixtures",
        path,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("L1_FIXTURES_UNAVAILABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class UsefulL1IdentityCollisionTests(unittest.TestCase):
    def test_provider_review_id_may_equal_legacy_thread_evidence_id(self) -> None:
        fixtures = _fixtures()
        reducer = fixtures.reducer_fixture()
        snapshot = fixtures.snapshot_fixture()

        self.assertGreaterEqual(len(snapshot["reviews"]), 2)
        origin_id = snapshot["reviews"][0]["observation_id"]
        legacy_thread_id = f"gnostoa-thread-evidence::{origin_id}"
        snapshot["reviews"][1]["observation_id"] = legacy_thread_id

        review_input = reducer.build_review_input(snapshot, fixtures.bundle_fixture())
        observations = review_input["evidence_set"]["observations"]
        observation_ids = {item["observation_id"] for item in observations}

        self.assertIn(origin_id, observation_ids)
        self.assertIn(legacy_thread_id, observation_ids)

        thread_only = [
            item
            for item in observations
            if item["native"].get("thread_evidence_only") is True
        ]
        self.assertEqual(1, len(thread_only))
        self.assertNotEqual(legacy_thread_id, thread_only[0]["observation_id"])
        self.assertEqual(
            origin_id,
            thread_only[0]["native"]["origin_review_observation_id"],
        )

    def test_non_colliding_thread_evidence_id_keeps_legacy_identity(self) -> None:
        fixtures = _fixtures()
        reducer = fixtures.reducer_fixture()
        snapshot = fixtures.snapshot_fixture()

        origin_id = snapshot["reviews"][0]["observation_id"]
        review_input = reducer.build_review_input(snapshot, fixtures.bundle_fixture())
        thread_only = [
            item
            for item in review_input["evidence_set"]["observations"]
            if item["native"].get("thread_evidence_only") is True
        ]

        self.assertEqual(1, len(thread_only))
        self.assertEqual(
            f"gnostoa-thread-evidence::{origin_id}",
            thread_only[0]["observation_id"],
        )

    def test_fallback_probes_past_a_second_provider_collision(self) -> None:
        fixtures = _fixtures()
        reducer = fixtures.reducer_fixture()
        snapshot = fixtures.snapshot_fixture()

        origin_id = snapshot["reviews"][0]["observation_id"]
        legacy_thread_id = f"gnostoa-thread-evidence::{origin_id}"
        encoded_origin = (
            base64.urlsafe_b64encode(origin_id.encode("utf-8"))
            .decode("ascii")
            .rstrip("=")
        )
        first_fallback = f"gnostoa-thread-evidence:v2:{encoded_origin}"

        snapshot["reviews"][1]["observation_id"] = legacy_thread_id
        snapshot["reviews"].append(
            {
                "observation_id": first_fallback,
                "reviewer_id": "collision-fixture",
                "recommendation_state": "COMMENTED",
                "observed_at": "2026-09-19T16:39:00Z",
                "head_commit": "d" * 40,
                "source_url": snapshot["subject"]["source_url"] + "#collision-fixture",
            }
        )
        snapshot["coverage"]["reviews"]["count"] = 3

        review_input = reducer.build_review_input(snapshot, fixtures.bundle_fixture())
        observations = review_input["evidence_set"]["observations"]
        thread_only = [
            item
            for item in observations
            if item["native"].get("thread_evidence_only") is True
        ]

        self.assertEqual(1, len(thread_only))
        self.assertEqual(first_fallback + ":1", thread_only[0]["observation_id"])
        self.assertIn(
            first_fallback,
            {item["observation_id"] for item in observations},
        )

    def test_collision_fallback_is_independent_of_provider_review_order(self) -> None:
        fixtures = _fixtures()
        reducer = fixtures.reducer_fixture()

        def thread_id(reverse: bool) -> str:
            snapshot = fixtures.snapshot_fixture()
            origin_id = snapshot["reviews"][0]["observation_id"]
            snapshot["reviews"][1]["observation_id"] = (
                f"gnostoa-thread-evidence::{origin_id}"
            )
            if reverse:
                snapshot["reviews"].reverse()
            review_input = reducer.build_review_input(snapshot, fixtures.bundle_fixture())
            thread_only = [
                item
                for item in review_input["evidence_set"]["observations"]
                if item["native"].get("thread_evidence_only") is True
            ]
            self.assertEqual(1, len(thread_only))
            return thread_only[0]["observation_id"]

        self.assertEqual(thread_id(False), thread_id(True))

    def test_collision_fallback_remains_valid_r2a_input(self) -> None:
        fixtures = _fixtures()
        reducer = fixtures.reducer_fixture()
        snapshot = fixtures.snapshot_fixture()

        self.assertGreaterEqual(len(snapshot["reviews"]), 2)
        origin_id = snapshot["reviews"][0]["observation_id"]
        snapshot["reviews"][1]["observation_id"] = (
            f"gnostoa-thread-evidence::{origin_id}"
        )
        review_input = reducer.build_review_input(snapshot, fixtures.bundle_fixture())

        schema_path = (
            Path(__file__).resolve().parents[1]
            / "schemas"
            / "review-check-input.schema.json"
        )
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(
            schema,
            format_checker=FormatChecker(),
        ).validate(review_input)


if __name__ == "__main__":
    unittest.main()
