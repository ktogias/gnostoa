from __future__ import annotations

import copy
import hashlib
import unittest
from pathlib import Path

from tools import adoption_assurance

ROOT = Path(__file__).resolve().parents[1]


def _digest(label: str) -> str:
    return f"sha256:{hashlib.sha256(label.encode()).hexdigest()}"


def _evidence(label: str) -> dict[str, object]:
    return {
        "path": f"evidence/{label}.json",
        "sha256": _digest(label),
        "bytes": len(label),
        "origin": "gnostoa-test",
    }


class AdoptionAssuranceContractTests(unittest.TestCase):
    def _subject(self, *, after_patch: str | None = None) -> dict[str, object]:
        patch_digest = _digest("patch")
        before = {
            "head": "a" * 40,
            "tree": "b" * 40,
            "status_sha256": _digest("status"),
            "staged_index_sha256": _digest("index"),
            "staged_index_bytes": 123,
            "candidate_patch_sha256": patch_digest,
            "candidate_patch_bytes": 456,
        }
        after = dict(before)
        after["candidate_patch_sha256"] = after_patch or patch_digest
        return adoption_assurance.build_candidate_subject(
            repository_object_format="sha1",
            base_commit="a" * 40,
            staged_index_sha256=_digest("index"),
            staged_index_bytes=123,
            candidate_patch_sha256=patch_digest,
            candidate_patch_bytes=456,
            gitlinks=[{"path": "vendor/toolkit", "commit": "c" * 40}],
            before=before,
            after=after,
        )

    def _observation(
        self,
        subject_id: str,
        observation_type: str,
        *,
        observation_id: str | None = None,
        outcome: str = "PASS",
    ) -> dict[str, object]:
        return adoption_assurance.make_observation(
            observation_id=observation_id or f"observation.{observation_type}",
            observation_type=observation_type,
            subject_id=subject_id,
            outcome=outcome,
            producer="test-producer",
            evidence=[_evidence(observation_type)],
        )

    def _conditions(
        self,
        subject_id: str,
        *,
        override: dict[str, tuple[str, str, str]] | None = None,
    ) -> list[dict[str, object]]:
        observation_types = {
            "CandidateStable": "candidate-stability",
            "ExecutionSubjectsCoherent": "execution-subject-coherence",
            "StructuralValid": "structural-validation",
            "ContextDeterministic": "context-determinism",
            "ProjectSuitesPassed": "project-suite-process",
            "RuntimeObservationAvailable": "project-runtime-report",
            "EvidenceIntegrityPreserved": "evidence-publication",
            "SemanticReviewRequired": "semantic-review-requirement",
        }
        changes = override or {}
        conditions: list[dict[str, object]] = []
        for condition_type, observation_type in observation_types.items():
            outcome, status, reason = changes.get(
                condition_type, ("PASS", "TRUE", "Satisfied")
            )
            if (
                condition_type == "SemanticReviewRequired"
                and condition_type not in changes
            ):
                reason = "Required"
            observation = self._observation(
                subject_id,
                observation_type,
                observation_id=f"observation.{condition_type}",
                outcome=outcome,
            )
            conditions.append(
                adoption_assurance.make_condition(
                    condition_type=condition_type,
                    subject_id=subject_id,
                    status=status,
                    reason=reason,
                    observations=[observation],
                )
            )
        return conditions

    def test_policy_bytes_and_digest_are_canonical_and_stable(self) -> None:
        document = adoption_assurance.policy_document()
        self.assertEqual("gnostoa-review-ready/v1", document["id"])
        self.assertEqual(
            adoption_assurance.canonical_json_bytes(document),
            adoption_assurance.policy_bytes(),
        )
        self.assertEqual(
            _digest_from_bytes(adoption_assurance.policy_bytes()),
            adoption_assurance.policy_digest(),
        )
        self.assertEqual(
            adoption_assurance.policy_digest(), adoption_assurance.POLICY_SHA256
        )

    def test_candidate_subject_is_canonical_and_change_sensitive(self) -> None:
        subject = self._subject()
        repeated = self._subject()
        changed = self._subject(after_patch=_digest("changed-patch"))
        self.assertEqual(subject, repeated)
        self.assertNotEqual(subject["id"], changed["id"])
        self.assertEqual("git-staged-candidate/v1", subject["type"])

    def test_assurance_is_assigned_from_observation_type(self) -> None:
        subject_id = str(self._subject()["id"])
        direct = self._observation(subject_id, "candidate-stability")
        process = self._observation(subject_id, "project-suite-process")
        report = self._observation(subject_id, "project-runtime-report")
        self.assertEqual("gnostoa-direct-measurement", direct["assurance"])
        self.assertEqual("gnostoa-observed-project-process", process["assurance"])
        self.assertEqual("invocation-bound-project-report", report["assurance"])

    def test_unknown_observation_type_cannot_forge_assurance(self) -> None:
        subject_id = str(self._subject()["id"])
        with self.assertRaises(adoption_assurance.AssuranceContractError):
            adoption_assurance.make_observation(
                observation_id="observation.forged",
                observation_type="producer-selected-high-assurance",
                subject_id=subject_id,
                outcome="PASS",
                producer="untrusted-producer",
                evidence=[_evidence("forged")],
            )

    def test_condition_rejects_mutated_assurance_and_malformed_evidence(self) -> None:
        subject_id = str(self._subject()["id"])
        observation = self._observation(subject_id, "candidate-stability")

        forged = copy.deepcopy(observation)
        forged["assurance"] = "verified-external-attestation"
        with self.assertRaises(adoption_assurance.AssuranceContractError):
            adoption_assurance.make_condition(
                condition_type="CandidateStable",
                subject_id=subject_id,
                status="TRUE",
                reason="Satisfied",
                observations=[forged],
            )

        stale = copy.deepcopy(observation)
        stale["evidence"][0]["sha256"] = "sha256:00"
        with self.assertRaises(adoption_assurance.AssuranceContractError):
            adoption_assurance.make_condition(
                condition_type="CandidateStable",
                subject_id=subject_id,
                status="TRUE",
                reason="Satisfied",
                observations=[stale],
            )

    def test_incomplete_external_attestation_is_rejected(self) -> None:
        subject_id = str(self._subject()["id"])
        with self.assertRaises(adoption_assurance.AssuranceContractError):
            adoption_assurance.make_observation(
                observation_id="observation.external",
                observation_type="external-attestation",
                subject_id=subject_id,
                outcome="PASS",
                producer="external-provider",
                evidence=[_evidence("external")],
                external_verification={"subject_digest": subject_id},
            )

        with self.assertRaises(adoption_assurance.AssuranceContractError):
            adoption_assurance.make_observation(
                observation_id="observation.external",
                observation_type="external-attestation",
                subject_id=subject_id,
                outcome="PASS",
                producer="external-provider",
                evidence=[_evidence("external")],
                external_verification={
                    "verifier": "external-verifier",
                    "verification_method": "signature-and-subject-binding-v1",
                    "attestation_digest": _digest("attestation"),
                    "subject_digest": _digest("other-subject"),
                },
            )

        with self.assertRaisesRegex(
            adoption_assurance.AssuranceContractError,
            "separately selected verifier",
        ):
            adoption_assurance.make_observation(
                observation_id="observation.external",
                observation_type="external-attestation",
                subject_id=subject_id,
                outcome="PASS",
                producer="external-provider",
                evidence=[_evidence("external")],
                external_verification={
                    "verifier": "external-verifier",
                    "verification_method": "signature-and-subject-binding-v1",
                    "attestation_digest": _digest("attestation"),
                    "subject_digest": subject_id,
                },
            )

    def test_all_required_true_is_ready_and_semantic_review_is_not_cleared(
        self,
    ) -> None:
        subject_id = str(self._subject()["id"])
        conditions = self._conditions(subject_id)
        readiness = adoption_assurance.evaluate_readiness(subject_id, conditions)
        self.assertEqual(("READY", 0), (readiness["result"], readiness["exit_code"]))
        semantic = next(
            item for item in conditions if item["type"] == "SemanticReviewRequired"
        )
        self.assertEqual(("TRUE", "Required"), (semantic["status"], semantic["reason"]))
        self.assertNotIn("SemanticReviewRequired", readiness["required_conditions"])

    def test_false_required_condition_fails_without_erasing_other_results(self) -> None:
        subject_id = str(self._subject()["id"])
        conditions = self._conditions(
            subject_id,
            override={"ProjectSuitesPassed": ("FAIL", "FALSE", "ObservedFailure")},
        )
        readiness = adoption_assurance.evaluate_readiness(subject_id, conditions)
        self.assertEqual(("FAILED", 1), (readiness["result"], readiness["exit_code"]))
        statuses = {
            item["type"]: item["status"] for item in readiness["condition_statuses"]
        }
        self.assertEqual("TRUE", statuses["StructuralValid"])
        self.assertEqual("FALSE", statuses["ProjectSuitesPassed"])

    def test_unknown_required_condition_is_blocked(self) -> None:
        subject_id = str(self._subject()["id"])
        conditions = self._conditions(
            subject_id,
            override={
                "RuntimeObservationAvailable": (
                    "BLOCKED",
                    "UNKNOWN",
                    "PrerequisiteBlocked",
                )
            },
        )
        readiness = adoption_assurance.evaluate_readiness(subject_id, conditions)
        self.assertEqual(("BLOCKED", 3), (readiness["result"], readiness["exit_code"]))

    def test_false_required_condition_precedes_unrelated_unknown(self) -> None:
        subject_id = str(self._subject()["id"])
        conditions = self._conditions(
            subject_id,
            override={
                "ProjectSuitesPassed": ("FAIL", "FALSE", "ObservedFailure"),
                "RuntimeObservationAvailable": (
                    "BLOCKED",
                    "UNKNOWN",
                    "PrerequisiteBlocked",
                ),
            },
        )
        readiness = adoption_assurance.evaluate_readiness(subject_id, conditions)
        self.assertEqual(("FAILED", 1), (readiness["result"], readiness["exit_code"]))

    def test_integrity_or_internal_unknown_has_error_precedence(self) -> None:
        subject_id = str(self._subject()["id"])
        conditions = self._conditions(
            subject_id,
            override={
                "ProjectSuitesPassed": ("FAIL", "FALSE", "ObservedFailure"),
                "EvidenceIntegrityPreserved": (
                    "ERROR",
                    "UNKNOWN",
                    "UnsafeBoundary",
                ),
            },
        )
        readiness = adoption_assurance.evaluate_readiness(subject_id, conditions)
        self.assertEqual(("ERROR", 2), (readiness["result"], readiness["exit_code"]))

    def test_missing_required_condition_is_an_error(self) -> None:
        subject_id = str(self._subject()["id"])
        conditions = [
            item
            for item in self._conditions(subject_id)
            if item["type"] != "ContextDeterministic"
        ]
        readiness = adoption_assurance.evaluate_readiness(subject_id, conditions)
        self.assertEqual(("ERROR", 2), (readiness["result"], readiness["exit_code"]))
        self.assertEqual("InvalidPolicyInput", readiness["reason"])

    def test_stale_condition_subject_is_an_error(self) -> None:
        subject_id = str(self._subject()["id"])
        conditions = self._conditions(subject_id)
        stale = copy.deepcopy(conditions)
        stale[0]["subject"] = _digest("stale-subject")
        readiness = adoption_assurance.evaluate_readiness(subject_id, stale)
        self.assertEqual(("ERROR", 2), (readiness["result"], readiness["exit_code"]))

    def test_provider_projection_accepts_only_ready_exact_subject(self) -> None:
        subject_id = str(self._subject()["id"])
        ready = adoption_assurance.evaluate_readiness(
            subject_id, self._conditions(subject_id)
        )
        self.assertEqual(
            "SUCCESS",
            adoption_assurance.provider_projection(ready, subject_id)["result"],
        )
        blocked = dict(ready, result="BLOCKED", exit_code=3)
        self.assertEqual(
            "FAILURE",
            adoption_assurance.provider_projection(blocked, subject_id)["result"],
        )
        self.assertEqual(
            "FAILURE",
            adoption_assurance.provider_projection(ready, _digest("other"))["result"],
        )
        self.assertEqual(
            "FAILURE",
            adoption_assurance.provider_projection(None, subject_id)["result"],
        )
        stale_policy = copy.deepcopy(ready)
        stale_policy["policy"]["sha256"] = _digest("changed-policy")
        projection = adoption_assurance.provider_projection(stale_policy, subject_id)
        self.assertEqual(
            ("FAILURE", "StalePolicy"),
            (projection["result"], projection["reason"]),
        )
        incomplete = copy.deepcopy(ready)
        incomplete["condition_statuses"] = []
        projection = adoption_assurance.provider_projection(incomplete, subject_id)
        self.assertEqual(
            ("FAILURE", "ReadinessNotSatisfied"),
            (projection["result"], projection["reason"]),
        )

    def test_result_schema_is_closed_and_rejects_v1_dimensions(self) -> None:
        schema = adoption_assurance.load_result_schema(
            ROOT / "schemas" / "adoption-check.schema.json"
        )
        self.assertEqual(
            "https://ktogias.github.io/gnostoa/schemas/v1/adoption-check.schema.json",
            schema["$id"],
        )
        self.assertFalse(schema["additionalProperties"])
        self.assertNotIn("dimensions", schema["properties"])


def _digest_from_bytes(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


if __name__ == "__main__":
    unittest.main()
