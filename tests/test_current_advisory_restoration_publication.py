from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_RELATIVE_PATH = (
    ".github/workflows/publish-current-advisory-restoration-runtime.yml"
)
WORKFLOW_PATH = ROOT / WORKFLOW_RELATIVE_PATH
R2A_WORKFLOW_PATH = ROOT / ".github/workflows/r2a-protected-current-advisory.yml"
DECISION_RELATIVE_PATH = (
    "knowledge/decisions/0084-publish-current-advisory-restoration-runtime-by-digest.md"
)
DECISION_PATH = ROOT / DECISION_RELATIVE_PATH
INDEX_PATH = ROOT / "knowledge/index.md"
GUARDRAILS_PATH = ROOT / "policy/guardrails.yaml"

SOURCE_COMMIT = "315487e7a67635ebf3ec3f70f666ef41646102e1"  # pragma: allowlist secret -- public source revision
SOURCE_TREE = "ea3fdebc6afa9bf5a4c2d0691199beca4dcece81"  # pragma: allowlist secret -- public source tree
PUBLIC_SURFACE = (
    "sha256:45bc59ce177ab53ddb5925279166b5ede91bbb6c43ef31fb056de56b6ddabca2"
)
BEFORE = "b80a4d8246e48d1e922c1732c37201e3e2b92c47"  # pragma: allowlist secret -- public predecessor
PR_NUMBER = "281"
HEAD_REF = "restoration/275-publish-current-advisory-runtime"
CHECKOUT = "actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd"
ATTEST = "actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6"


def _load(path: Path) -> dict[str, object]:
    value = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    if not isinstance(value, dict):
        raise AssertionError(f"{path} must be a mapping")
    return value


def _steps(job: dict[str, object]) -> list[dict[str, object]]:
    value = job.get("steps")
    if not isinstance(value, list) or not all(isinstance(x, dict) for x in value):
        raise AssertionError("job steps must be structured")
    return value


def _named(steps: list[dict[str, object]], name: str) -> dict[str, object]:
    found = [step for step in steps if step.get("name") == name]
    if len(found) != 1:
        raise AssertionError(f"expected one step named {name!r}, found {len(found)}")
    return found[0]


def _run(step: dict[str, object]) -> str:
    value = step.get("run")
    if not isinstance(value, str):
        raise AssertionError("expected executable run step")
    return value


class CurrentAdvisoryRestorationPublicationTests(unittest.TestCase):
    def test_r3_exact_one_shot_digest_only_publisher(self) -> None:
        self.assertTrue(
            WORKFLOW_PATH.is_file(),
            "R3_OCI_PUBLISHER_UNAVAILABLE: no exact one-shot restoration publisher exists",
        )
        workflow = _load(WORKFLOW_PATH)
        self.assertEqual(
            "Publish qualified current-advisory restoration runtime by digest",
            workflow["name"],
        )
        self.assertEqual(
            {"push": {"branches": ["main"], "paths": [WORKFLOW_RELATIVE_PATH]}},
            workflow["on"],
        )
        self.assertEqual({}, workflow["permissions"])

        env = workflow["env"]
        self.assertIsInstance(env, dict)
        assert isinstance(env, dict)
        self.assertEqual(SOURCE_COMMIT, env["SOURCE_COMMIT"])
        self.assertEqual(SOURCE_TREE, env["SOURCE_TREE"])
        self.assertEqual(PUBLIC_SURFACE, env["EXPECTED_PUBLIC_SURFACE_DIGEST"])
        self.assertEqual(BEFORE, env["AUTHORIZED_BEFORE_COMMIT"])
        self.assertEqual(PR_NUMBER, env["AUTHORIZED_PR_NUMBER"])
        self.assertEqual(HEAD_REF, env["AUTHORIZED_PR_HEAD_REF"])

        jobs = workflow["jobs"]
        self.assertIsInstance(jobs, dict)
        assert isinstance(jobs, dict)
        self.assertEqual({"authorize", "publish"}, set(jobs))
        authorize = jobs["authorize"]
        publish = jobs["publish"]
        self.assertIsInstance(authorize, dict)
        self.assertIsInstance(publish, dict)
        assert isinstance(authorize, dict)
        assert isinstance(publish, dict)
        self.assertEqual({"pull-requests": "read"}, authorize["permissions"])
        self.assertEqual("authorize", publish["needs"])
        self.assertEqual(
            {
                "contents": "read",
                "packages": "write",
                "id-token": "write",
                "attestations": "write",
            },
            publish["permissions"],
        )
        self.assertNotIn("if", authorize)
        self.assertNotIn("continue-on-error", authorize)
        self.assertNotIn("if", publish)
        self.assertNotIn("continue-on-error", publish)

        asteps = _steps(authorize)
        psteps = _steps(publish)

        guard = _run(
            _named(
                asteps, "Refuse any context outside the admitted one-shot R3 boundary"
            )
        )
        for token in (
            'test "${GITHUB_REPOSITORY}" = "ktogias/gnostoa"',
            'test "${GITHUB_EVENT_NAME}" = "push"',
            'test "${GITHUB_REF}" = "refs/heads/main"',
            'test "${GITHUB_ACTOR}" = "ktogias"',
            'test "${GITHUB_TRIGGERING_ACTOR}" = "ktogias"',
            'test "${GITHUB_RUN_ATTEMPT}" = "1"',
            'test "${EVENT_BEFORE}" = "${AUTHORIZED_BEFORE_COMMIT}"',
            WORKFLOW_RELATIVE_PATH,
        ):
            self.assertIn(token, guard)

        binding = _run(_named(asteps, "Bind the pushed commit to merged PR 281"))
        for token in (
            "pulls/${AUTHORIZED_PR_NUMBER}",
            "merge_commit_sha",
            'pr.get("base", {}).get("ref") == "main"',
            'pr.get("head", {}).get("ref") == expected_head_ref',
        ):
            self.assertIn(token, binding)

        effect_guard = _run(
            _named(psteps, "Refuse rerun at the effect-capable R3 publication job")
        )
        self.assertIn('test "${GITHUB_RUN_ATTEMPT}" = "1"', effect_guard)
        self.assertIn(
            'test "${EVENT_BEFORE}" = "${AUTHORIZED_BEFORE_COMMIT}"', effect_guard
        )

        checkouts = [step for step in psteps if step.get("uses") == CHECKOUT]
        self.assertEqual(2, len(checkouts))
        source_with = checkouts[1]["with"]
        self.assertIsInstance(source_with, dict)
        assert isinstance(source_with, dict)
        self.assertEqual("${{ env.SOURCE_COMMIT }}", source_with["ref"])
        self.assertEqual("restoration-source", source_with["path"])

        local = _run(
            _named(
                psteps,
                "Build and verify exact qualified runtime before any registry effect",
            )
        )
        for token in (
            "./ci/build-runtime",
            "surface-digest --root /opt/gnostoa",
            'test "${public_digest}" = "${EXPECTED_PUBLIC_SURFACE_DIGEST}"',
            "tools/review_current.py",
            "tools/review_outer.py",
            "tools/review_live.py",
            "tools/review_live_entrypoint.py",
            "review_current_advisory_restoration_smoke.py",
        ):
            self.assertIn(token, local)

        publication = _run(
            _named(
                psteps,
                "Publish exact qualified runtime without a remote tag and read back digest",
            )
        )
        self.assertIn('--push-by-digest "${IMAGE_NAME}"', publication)
        self.assertIn("containerimage.digest", publication)
        self.assertIn("docker buildx imagetools inspect", publication)
        self.assertNotIn("docker push ", publication)

        attest = [step for step in psteps if step.get("uses") == ATTEST]
        self.assertEqual(1, len(attest))

        reacquire = _run(
            _named(
                psteps,
                "Verify attestation, anonymously reacquire, and replay restoration smoke",
            )
        )
        for token in (
            "gh attestation verify",
            "docker logout ghcr.io",
            'DOCKER_CONFIG="${anonymous_config}"',
            "review_current_advisory_restoration_smoke.py",
            'GNOSTOA_R2A_CANDIDATE_IMAGE="${digest_ref}"',
            'GNOSTOA_R2_EXPECTED_PROTECTED_MAIN="${GITHUB_SHA}"',
            "authority promotion: **NOT PERFORMED**",
        ):
            self.assertIn(token, reacquire)

        reconcile = _run(_named(psteps, "Reconcile and clean post-publication state"))
        self.assertIn(
            "post-write outcome is ambiguous and no exact digest is available; do not rerun blindly",
            reconcile,
        )
        self.assertIn("gh attestation verify", reconcile)
        self.assertIn('DOCKER_CONFIG="${reconcile_config}"', reconcile)

        all_run = "\n".join(_run(step) for step in asteps + psteps if "run" in step)
        for forbidden in (
            "docker push ",
            "gh release create",
            "git tag ",
            "tasks/issue-11-r2a-current-advisory-consumer.json",
            "_HOST_PERSISTENCE_FREE_CONSUMER_IDENTITIES",
        ):
            self.assertNotIn(forbidden, all_run)

    def test_r3_decision_preserves_effect_boundaries(self) -> None:
        decision = DECISION_PATH.read_text(encoding="utf-8")
        for token in (
            SOURCE_COMMIT,
            SOURCE_TREE,
            PUBLIC_SURFACE,
            "Stop before merge/publication for a separate owner authorization",
            "R4 is separate again",
            "no rerun authority",
            "anonymous",
            "attest",
        ):
            self.assertIn(token, decision)

    def test_r3_is_governed_and_routed(self) -> None:
        self.assertIn(
            DECISION_RELATIVE_PATH.removeprefix("knowledge/"),
            INDEX_PATH.read_text(encoding="utf-8"),
        )
        guardrails = _load(GUARDRAILS_PATH)
        entries = guardrails.get("guardrails")
        self.assertIsInstance(entries, list)
        assert isinstance(entries, list)
        by_id = {
            entry.get("id"): entry
            for entry in entries
            if isinstance(entry, dict) and isinstance(entry.get("id"), str)
        }
        for guardrail_id in (
            "semantic-review-assurance",
            "immutable-provider-ci-adapters",
        ):
            entry = by_id[guardrail_id]
            self.assertIn(WORKFLOW_RELATIVE_PATH, entry["implementation"])
            self.assertIn(
                "tests/test_current_advisory_restoration_publication.py",
                entry["tests"],
            )
        self.assertIn(
            DECISION_RELATIVE_PATH,
            by_id["semantic-review-assurance"]["implementation"],
        )

        r2a = R2A_WORKFLOW_PATH.read_text(encoding="utf-8")
        self.assertIn(WORKFLOW_RELATIVE_PATH, r2a)
        self.assertIn(DECISION_RELATIVE_PATH, r2a)
        self.assertGreaterEqual(
            r2a.count("tests/test_current_advisory_restoration_publication.py"),
            3,
        )


if __name__ == "__main__":
    unittest.main()
