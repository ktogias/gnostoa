from __future__ import annotations

import importlib.util
import sys
import unittest
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from unittest import mock

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_RELATIVE_PATH = (
    ".github/workflows/verify-r2a-current-advisory-restoration-runtime.yml"
)
WORKFLOW_PATH = ROOT / WORKFLOW_RELATIVE_PATH
SMOKE_RELATIVE_PATH = "ci/review_current_advisory_restoration_smoke.py"
SMOKE_PATH = ROOT / SMOKE_RELATIVE_PATH
DECISION_RELATIVE_PATH = (
    "knowledge/decisions/"
    "0083-qualify-integrated-current-advisory-restoration-runtime.md"
)
DECISION_PATH = ROOT / DECISION_RELATIVE_PATH

SOURCE_COMMIT = "315487e7a67635ebf3ec3f70f666ef41646102e1"  # pragma: allowlist secret -- public integrated source
SOURCE_TREE = "ea3fdebc6afa9bf5a4c2d0691199beca4dcece81"  # pragma: allowlist secret -- public integrated tree
CHECKOUT_ACTION = "actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd"
SETUP_PYTHON_ACTION = "actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1"


def _load_workflow() -> dict[str, object]:
    workflow = yaml.load(
        WORKFLOW_PATH.read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )
    if not isinstance(workflow, dict):
        raise AssertionError("R2 qualification workflow must be a YAML mapping")
    return workflow


def _job_steps(job: dict[str, object]) -> list[dict[str, object]]:
    steps = job.get("steps")
    if not isinstance(steps, list) or not all(isinstance(step, dict) for step in steps):
        raise AssertionError("R2 qualification job must expose structured steps")
    return steps


def _named_step(
    steps: list[dict[str, object]], name: str
) -> tuple[int, dict[str, object]]:
    matches = [
        (index, step) for index, step in enumerate(steps) if step.get("name") == name
    ]
    if len(matches) != 1:
        raise AssertionError(f"expected one step named {name!r}, found {len(matches)}")
    return matches[0]


def _step_run(step: dict[str, object], name: str) -> str:
    run = step.get("run")
    if not isinstance(run, str):
        raise AssertionError(f"{name} must be an executable run step")
    return run


def _assert_all_in(case: unittest.TestCase, text: str, *required: str) -> None:
    """Each required fragment appears in a step's run text."""
    for fragment in required:
        case.assertIn(fragment, text)


# The local candidate the boundary test hands the verifier, and what it measured.
_CANDIDATE_IMAGE = "gnostoa-r2-restoration:boundary-test"
_CANDIDATE_IMAGE_ID = "sha256:" + "b" * 64
_CANDIDATE_SURFACE = "sha256:" + "5" * 64
_CANDIDATE_IDENTITY_FORMAT = (
    "{{.Os}}|{{.Architecture}}|{{.Config.User}}|"
    '{{index .Config.Labels "org.opencontainers.image.revision"}}'
)
_CANDIDATE_RUN = (
    "run",
    "--rm",
    "--pull=never",
    "--network",
    "none",
    "--read-only",
    "--cap-drop",
    "ALL",
    "--security-opt",
    "no-new-privileges",
)


def _load_smoke() -> ModuleType:
    """The restoration smoke, loaded from its file as the workflow runs it. As
    importlib's own recipe does, the module is in `sys.modules` while it executes, so
    its dataclass can resolve its annotations."""
    spec = importlib.util.spec_from_file_location(
        "restoration_smoke_under_test", SMOKE_PATH
    )
    if spec is None or spec.loader is None:
        raise AssertionError("the restoration smoke must load as a module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        del sys.modules[spec.name]
    return module


def _candidate_reads(change: dict[str, str]) -> Callable[..., bytes]:
    """The local candidate's Docker reads, answered for exactly the verifier's argvs;
    any other read is refused. `change` replaces one measured value."""
    identity = change.get("identity", f"linux|amd64|kit|{SOURCE_COMMIT}")
    reads = {
        ("image", "inspect", "--format", "{{.Id}}", _CANDIDATE_IMAGE): change.get(
            "image_id", _CANDIDATE_IMAGE_ID
        ),
        (
            "image",
            "inspect",
            "--format",
            _CANDIDATE_IDENTITY_FORMAT,
            _CANDIDATE_IMAGE,
        ): identity,
        (
            *_CANDIDATE_RUN,
            "--entrypoint",
            "sh",
            _CANDIDATE_IMAGE,
            "-ec",
            "id -u; id -g",
        ): change.get("ids", "10001\n10001\n"),
        (
            *_CANDIDATE_RUN,
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,nodev,size=16m",
            "--entrypoint",
            "python",
            _CANDIDATE_IMAGE,
            "-m",
            "tools.cli",
            "surface-digest",
            "--root",
            "/opt/gnostoa",
        ): change.get("surface", _CANDIDATE_SURFACE),
    }

    def answer(arguments: list[str], **_: object) -> bytes:
        if tuple(arguments) not in reads:
            raise AssertionError(f"unexpected Docker read: {arguments!r}")
        return reads[tuple(arguments)].encode("utf-8")

    return answer


class CurrentAdvisoryRestorationRuntimeTests(unittest.TestCase):
    def test_r2_has_structural_verification_only_qualification_surface(self) -> None:
        self.assertTrue(DECISION_PATH.is_file(), "R2_RESTORATION_DECISION_UNAVAILABLE")
        self.assertTrue(
            WORKFLOW_PATH.is_file(),
            "R2_RUNTIME_QUALIFICATION_UNAVAILABLE: no verification-only "
            "restoration runtime workflow exists",
        )
        self.assertTrue(
            SMOKE_PATH.is_file(),
            "R2_RUNTIME_SMOKE_UNAVAILABLE: no layered candidate transport "
            "qualification exists",
        )

        workflow = _load_workflow()
        self.assertEqual(
            "Verify current-advisory restoration runtime",
            workflow["name"],
        )
        self.assertEqual({"contents": "read"}, workflow["permissions"])

        triggers = workflow.get("on")
        self.assertIsInstance(triggers, dict)
        assert isinstance(triggers, dict)
        pull_request = triggers.get("pull_request")
        self.assertIsInstance(pull_request, dict)
        assert isinstance(pull_request, dict)
        paths = pull_request.get("paths")
        self.assertIsInstance(paths, list)
        assert isinstance(paths, list)
        for required_path in (
            "tools/review_*.py",
            "tools/knowledge_common.py",
            "tools/cli.py",
            "schemas/review-*.json",
            "policy/review-policy.yaml",
            "Dockerfile",
            "ci/build-runtime",
        ):
            self.assertIn(required_path, paths)

        env = workflow.get("env")
        self.assertIsInstance(env, dict)
        assert isinstance(env, dict)
        self.assertEqual(SOURCE_COMMIT, env.get("SOURCE_COMMIT"))
        self.assertEqual(SOURCE_TREE, env.get("SOURCE_TREE"))

        jobs = workflow.get("jobs")
        self.assertIsInstance(jobs, dict)
        assert isinstance(jobs, dict)
        self.assertEqual({"qualify"}, set(jobs))
        qualify = jobs["qualify"]
        self.assertIsInstance(qualify, dict)
        assert isinstance(qualify, dict)
        self.assertNotIn("permissions", qualify)
        self.assertNotIn("if", qualify)
        self.assertNotIn("continue-on-error", qualify)
        steps = _job_steps(qualify)

        self.assertIn("workflow_dispatch", triggers)
        _, dispatch_guard = _named_step(
            steps, "Require protected main for manual qualification"
        )
        self.assertEqual(
            "github.event_name == 'workflow_dispatch'",
            dispatch_guard.get("if"),
        )
        dispatch_run = _step_run(dispatch_guard, "manual dispatch guard")
        self.assertIn(
            'test "${GITHUB_REF}" = "refs/heads/main"',
            dispatch_run,
        )
        self.assertIn(
            "manual R2 qualification must run from refs/heads/main",
            dispatch_run,
        )

        checkout_steps = [step for step in steps if step.get("uses") == CHECKOUT_ACTION]
        self.assertEqual(2, len(checkout_steps))
        candidate_with = checkout_steps[0].get("with")
        source_with = checkout_steps[1].get("with")
        self.assertIsInstance(candidate_with, dict)
        self.assertIsInstance(source_with, dict)
        assert isinstance(candidate_with, dict)
        assert isinstance(source_with, dict)
        self.assertEqual("false", candidate_with.get("persist-credentials"))
        self.assertEqual(
            "${{ github.event.pull_request.head.sha || github.sha }}",
            candidate_with.get("ref"),
        )
        self.assertEqual("0", candidate_with.get("fetch-depth"))
        self.assertEqual("false", source_with.get("persist-credentials"))
        self.assertEqual("${{ env.SOURCE_COMMIT }}", source_with.get("ref"))
        self.assertEqual("restoration-source", source_with.get("path"))

        setup_steps = [
            step for step in steps if step.get("uses") == SETUP_PYTHON_ACTION
        ]
        self.assertEqual(1, len(setup_steps))

        _, bind = _named_step(steps, "Bind exact integrated source")
        bind_run = _step_run(bind, "source binding")
        self.assertNotIn(
            "git -C restoration-source merge-base",
            bind_run,
        )
        _assert_all_in(
            self,
            bind_run,
            "git -C restoration-source rev-parse HEAD",
            "git -C restoration-source rev-parse 'HEAD^{tree}'",
            "git -C restoration-source status --porcelain",
            'protected_main="${{ github.event.pull_request.base.sha || github.sha }}"',
            'git merge-base --is-ancestor "${SOURCE_COMMIT}" "${protected_main}"',
            "restoration source is not an ancestor of protected main",
            "SOURCE_COMMIT is the immutable runtime subject",
        )

        _, build = _named_step(steps, "Build exact integrated runtime locally")
        build_run = _step_run(build, "local runtime build")
        _assert_all_in(
            self,
            build_run,
            "cd restoration-source",
            'GNOSTOA_CANDIDATE_REF="${SOURCE_COMMIT}"',
            "./ci/build-runtime",
            '--tag "${GNOSTOA_R2_CANDIDATE_IMAGE}"',
            "--platform linux/amd64",
            "--pull",
            "--no-cache",
            'docker run --rm "${GNOSTOA_R2_CANDIDATE_IMAGE}" self-check',
        )

        _, identity = _named_step(steps, "Measure candidate runtime identity")
        identity_run = _step_run(identity, "runtime identity")
        _assert_all_in(
            self,
            identity_run,
            "docker image inspect",
            "^sha256:[0-9a-f]{64}$",
            "org.opencontainers.image.revision",
            "surface-digest --root /opt/gnostoa",
            'echo "image_id=${image_id}"',
            'echo "public_surface_digest=${public_surface_digest}"',
            '>> "${GITHUB_OUTPUT}"',
        )

        _, contracts = _named_step(
            steps,
            "Run exact-source transport regression contracts via native orchestration fallback",
        )
        contracts_run = _step_run(contracts, "transport contracts")
        _assert_all_in(
            self,
            contracts_run,
            "restoration-source/tests/test_review_current_payload_transport.py",
            "restoration-source/tests/test_review_outer_containment.py",
            "restoration-source/tests/test_security_review_followup.py",
            "tests/test_current_advisory_restoration_runtime.py",
        )

        _, smoke_step = _named_step(steps, "Exercise layered candidate transport")
        smoke_run = _step_run(smoke_step, "layered transport smoke")
        self.assertIn(
            f"python {SMOKE_RELATIVE_PATH}",
            smoke_run,
        )
        smoke_env = smoke_step.get("env")
        self.assertIsInstance(smoke_env, dict)
        assert isinstance(smoke_env, dict)
        self.assertEqual(
            "${{ env.GNOSTOA_R2_CANDIDATE_IMAGE }}",
            smoke_env.get("GNOSTOA_R2A_CANDIDATE_IMAGE"),
        )
        self.assertEqual(
            "${{ env.SOURCE_COMMIT }}",
            smoke_env.get("GNOSTOA_R2_EXPECTED_SOURCE_REVISION"),
        )
        self.assertEqual(
            "${{ env.SOURCE_TREE }}",
            smoke_env.get("GNOSTOA_R2_EXPECTED_SOURCE_TREE"),
        )
        self.assertEqual(
            "${{ steps.identity.outputs.image_id }}",
            smoke_env.get("GNOSTOA_R2_EXPECTED_IMAGE_ID"),
        )
        self.assertEqual(
            "${{ steps.identity.outputs.public_surface_digest }}",
            smoke_env.get("GNOSTOA_R2_EXPECTED_PUBLIC_SURFACE_DIGEST"),
        )
        self.assertEqual(
            "${{ github.event.pull_request.base.sha || github.sha }}",
            smoke_env.get("GNOSTOA_R2_EXPECTED_PROTECTED_MAIN"),
        )
        self.assertNotIn(
            'test "${{ github.event.pull_request.base.sha }}" = "${SOURCE_COMMIT}"',
            bind_run,
        )

        _, receipt = _named_step(steps, "Record bounded qualification receipt")
        receipt_run = _step_run(receipt, "qualification receipt")
        self.assertIn("set -euo pipefail", receipt_run)
        self.assertIn('printf -- "- source revision: \\`%s\\`\\n"', receipt_run)
        self.assertIn('printf -- "- source tree: \\`%s\\`\\n"', receipt_run)
        # Double-quoted formats with escaped backticks: nothing in them expands, and ShellCheck (SC2016) sees no
        # single-quoted expression. The format still ends in printf's own newline escape, never a doubled one.
        self.assertIn(r"\`%s\`\n", receipt_run)
        self.assertNotIn(r"\`%s\`\\n", receipt_run)
        self.assertNotIn("printf -- '", receipt_run)
        self.assertNotIn('echo "- source revision: `', receipt_run)
        self.assertNotIn('echo "- source tree: `', receipt_run)
        self.assertIn("registry publication: **NOT PERFORMED**", receipt_run)
        self.assertIn(
            "protected authority/catalog promotion: **NOT PERFORMED**",
            receipt_run,
        )

        for required_step in (bind, build, identity, contracts, smoke_step, receipt):
            self.assertNotIn("if", required_step)
            self.assertNotIn("continue-on-error", required_step)

        _, cleanup = _named_step(steps, "Remove local candidate image")
        self.assertEqual("always()", cleanup.get("if"))
        cleanup_run = _step_run(cleanup, "candidate cleanup")
        self.assertIn("docker image inspect", cleanup_run)
        self.assertIn("docker image rm", cleanup_run)
        self.assertIn("R2 local candidate image cleanup failed", cleanup_run)
        self.assertNotIn("|| true", cleanup_run)

        all_run_text = "\n".join(
            _step_run(step, str(step.get("name", "unnamed")))
            for step in steps
            if "run" in step
        )
        for forbidden in (
            "docker login",
            "--push-by-digest",
            "docker push ",
            "gh attestation",
            "gh release",
        ):
            self.assertNotIn(forbidden, all_run_text)
        all_uses = [str(step.get("uses", "")) for step in steps if "uses" in step]
        self.assertFalse(any(use.startswith("actions/attest@") for use in all_uses))

        smoke = SMOKE_PATH.read_text(encoding="utf-8")
        self.assertIn("host_backed_shared_tmp_sentinel_absent", smoke)
        self.assertIn('"_HOST_PERSISTENCE_FREE_CONSUMER_IDENTITIES"', smoke)
        self.assertIn('"_verify_outer_image"', smoke)
        self.assertIn('"--interactive"', smoke)
        self.assertIn('"--mount"', smoke)
        self.assertNotIn('"--volume"', smoke)
        self.assertIn('"source_id": "retained-review-evidence"', smoke)
        self.assertIn('"candidate_claims": {"marker": _SENTINEL}', smoke)

    def test_decision_keeps_publication_and_promotion_outside_r2(self) -> None:
        decision = DECISION_PATH.read_text(encoding="utf-8")
        self.assertIn(SOURCE_COMMIT, decision)
        self.assertIn(SOURCE_TREE, decision)
        self.assertIn("does **not** authorize GHCR", decision)
        self.assertIn("human semantic review", decision)
        self.assertIn("R3 requires separate owner authorization", decision)

    def test_r2_surface_is_owned_by_security_and_semantic_guardrails(self) -> None:
        document = yaml.load(
            (ROOT / "policy" / "guardrails.yaml").read_text(encoding="utf-8"),
            Loader=yaml.BaseLoader,
        )
        self.assertIsInstance(document, dict)
        assert isinstance(document, dict)
        entries = document.get("guardrails")
        self.assertIsInstance(entries, list)
        assert isinstance(entries, list)
        by_id = {
            entry.get("id"): entry
            for entry in entries
            if isinstance(entry, dict) and isinstance(entry.get("id"), str)
        }

        semantic = by_id.get("semantic-review-assurance")
        self.assertIsInstance(semantic, dict)
        assert isinstance(semantic, dict)
        semantic_implementation = semantic.get("implementation")
        semantic_tests = semantic.get("tests")
        self.assertIsInstance(semantic_implementation, list)
        self.assertIsInstance(semantic_tests, list)
        assert isinstance(semantic_implementation, list)
        assert isinstance(semantic_tests, list)
        for required in (
            WORKFLOW_RELATIVE_PATH,
            SMOKE_RELATIVE_PATH,
            DECISION_RELATIVE_PATH,
        ):
            self.assertIn(required, semantic_implementation)
        self.assertIn(
            "tests/test_current_advisory_restoration_runtime.py",
            semantic_tests,
        )

        provider = by_id.get("immutable-provider-ci-adapters")
        self.assertIsInstance(provider, dict)
        assert isinstance(provider, dict)
        provider_implementation = provider.get("implementation")
        provider_tests = provider.get("tests")
        self.assertIsInstance(provider_implementation, list)
        self.assertIsInstance(provider_tests, list)
        assert isinstance(provider_implementation, list)
        assert isinstance(provider_tests, list)
        self.assertIn(WORKFLOW_RELATIVE_PATH, provider_implementation)
        self.assertIn(
            "tests/test_current_advisory_restoration_runtime.py",
            provider_tests,
        )

    @staticmethod
    def _verify_candidate(
        smoke: ModuleType, verify: Callable[..., None], change: dict[str, str]
    ) -> None:
        with mock.patch.object(
            smoke, "_checked_output", side_effect=_candidate_reads(change)
        ):
            verify(
                candidate_image=_CANDIDATE_IMAGE,
                expected_image_id=_CANDIDATE_IMAGE_ID,
                expected_revision=SOURCE_COMMIT,
                expected_surface_digest=_CANDIDATE_SURFACE,
                consumer={
                    "runtime_revision": change.get("consumer_revision", SOURCE_COMMIT)
                },
                config_dir=ROOT / "docker-config-unused",
            )

    def test_local_candidate_boundary_accepts_exactly_kit_and_its_number(
        self,
    ) -> None:
        """The local candidate may run as `kit` or as `10001:10001` and nothing else;
        every other identity, field count, platform, revision, image id, uid, gid or
        public surface is refused with its own reason (Decision 0125, item 6)."""
        smoke = _load_smoke()
        # The module's own binding: the restoration job runs this file with only the
        # restoration source on its path, so no other test module is importable.
        verify = vars(smoke)["_verify_local_candidate"]
        accepted = {
            "kit": {},
            "10001:10001": {"identity": f"linux|amd64|10001:10001|{SOURCE_COMMIT}"},
        }
        identity = "runtime identity changed"
        refused: dict[str, tuple[dict[str, str], str]] = {
            f"user {user!r}": (
                {"identity": f"linux|amd64|{user}|{SOURCE_COMMIT}"},
                identity,
            )
            for user in ("root", "0:0", "10001", "10002:10002", "kit:kit", "")
        }
        refused.update(
            {
                "three fields": ({"identity": "linux|amd64|kit"}, identity),
                "five fields": (
                    {"identity": f"linux|amd64|kit|{SOURCE_COMMIT}|extra"},
                    identity,
                ),
                "another OS": (
                    {"identity": f"windows|amd64|kit|{SOURCE_COMMIT}"},
                    identity,
                ),
                "another architecture": (
                    {"identity": f"linux|arm64|kit|{SOURCE_COMMIT}"},
                    identity,
                ),
                "another revision label": (
                    {"identity": "linux|amd64|kit|" + "0" * 40},
                    identity,
                ),
                "another consumer revision": (
                    {"consumer_revision": "0" * 40},
                    "identity changed revision",
                ),
                "another image id": (
                    {"image_id": "sha256:" + "c" * 64},
                    "image id changed",
                ),
                "another uid": ({"ids": "10002\n10001\n"}, "uid/gid changed"),
                "another gid": ({"ids": "10001\n10002\n"}, "uid/gid changed"),
                "another surface": (
                    {"surface": "sha256:" + "6" * 64},
                    "public surface changed",
                ),
            }
        )
        for label, change in accepted.items():
            with self.subTest(accepted=label):
                self._verify_candidate(smoke, verify, change)
        for label, (change, reason) in refused.items():
            with (
                self.subTest(refused=label),
                self.assertRaisesRegex(RuntimeError, reason),
            ):
                self._verify_candidate(smoke, verify, change)

    def test_residue_probe_without_a_daemon_image_reports_it_and_runs_nothing(
        self,
    ) -> None:
        """When the original plan builder raised, so that no daemon image was recorded,
        the residue probe reports that before any Docker run (Decision 0125, item 6)."""
        smoke = _load_smoke()
        run = vars(smoke)["_CandidateRun"](
            candidate_image=_CANDIDATE_IMAGE,
            synthetic_runtime_image="gnostoa-r2-synthetic:boundary-test",
        )
        with mock.patch.object(smoke, "_run_docker") as docker:
            issue = vars(smoke)["_tmp_residue_issue"](
                run, "gnostoa-r2-tmp-boundary-test", ROOT / "docker-config-unused"
            )
        self.assertEqual("R2 shared tmp residue inspection had no daemon image", issue)
        docker.assert_not_called()
        self.assertFalse(run.sentinel_absent)


if __name__ == "__main__":
    unittest.main()
