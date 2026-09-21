from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from typing import Any


def _fixtures() -> Any:
    path = Path(__file__).with_name("test_review_reconcile_l1.py")
    spec = importlib.util.spec_from_file_location("l1_identity_collision_fixtures", path)
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

        origin_id = snapshot["reviews"][0]["observation_id"]
        legacy_thread_id = f"gnostoa-thread-evidence::{origin_id}"
        snapshot["reviews"][1]["observation_id"] = legacy_thread_id

        review_input = reducer.build_review_input(snapshot, fixtures._bundle())
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


if __name__ == "__main__":
    unittest.main()
