"""Every lock field must be classified for retained-currentness purposes.

A currentness check that compares a hand-picked subset goes stale silently: a new
authority-independent lock field is simply not compared, and nothing fails. This
pins the partition against the lock the builder actually produces, so adding a
field forces a deliberate decision about which role it plays.
"""

from __future__ import annotations

import unittest

from tools.capsule import lock as lock_module
from tools.capsule import retained_preflight

_PARTITION = {
    "compared_for_currentness": retained_preflight.LOCK_FIELDS_COMPARED_FOR_CURRENTNESS,
    "derived_from_compared": retained_preflight.LOCK_FIELDS_DERIVED_FROM_COMPARED,
    "authority_dependent": retained_preflight.LOCK_FIELDS_AUTHORITY_DEPENDENT,
    "qualification_dependent": retained_preflight.LOCK_FIELDS_QUALIFICATION_DEPENDENT,
    "integrity_metadata": retained_preflight.LOCK_FIELDS_INTEGRITY_METADATA,
}


def _built_lock_fields() -> set[str]:
    built = lock_module.build(
        experiment_id="E1",
        question="q",
        claim_boundary="b",
        launch={"executor": {}},
        tasks=[{"id": "T1"}],
        capabilities=[],
        stage_receipts={"DISCOVERED": "a" * 64},
        authority={"id": "auth"},
        run_plan={"runs": []},
        artifact_store="/tmp/artifacts",
    )
    # What actually lands on disk: the payload plus the digest write() appends.
    return set(built.payload) | {"lock_sha256"}


class RetainedLockFieldAccountingTests(unittest.TestCase):
    def test_every_lock_field_is_classified_exactly_once(self) -> None:
        produced = _built_lock_fields()
        classified: set[str] = set()
        for name, group in _PARTITION.items():
            overlap = classified & group
            self.assertEqual(
                overlap, set(), f"{name} re-classifies already-classified {overlap}"
            )
            classified |= group

        unclassified = produced - classified
        self.assertEqual(
            unclassified,
            set(),
            "new lock fields must be classified for retained currentness, not "
            f"silently ignored: {sorted(unclassified)}",
        )
        stale = classified - produced
        self.assertEqual(
            stale,
            set(),
            f"the partition names fields the lock no longer carries: {sorted(stale)}",
        )

    def test_compared_set_is_not_empty_and_excludes_the_authority(self) -> None:
        compared = retained_preflight.LOCK_FIELDS_COMPARED_FOR_CURRENTNESS
        self.assertTrue(compared)
        self.assertNotIn("authority", compared)
        self.assertNotIn("lock_sha256", compared)


if __name__ == "__main__":
    unittest.main()
