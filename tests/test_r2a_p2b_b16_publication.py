from __future__ import annotations

import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_RELATIVE_PATH = ".github/workflows/publish-r2a-p2b-b16-oci.yml"
WORKFLOW_PATH = ROOT / WORKFLOW_RELATIVE_PATH
R2A_WORKFLOW_RELATIVE_PATH = ".github/workflows/r2a-protected-current-advisory.yml"
R2A_WORKFLOW_PATH = ROOT / R2A_WORKFLOW_RELATIVE_PATH
FOCUSED_TEST_RELATIVE_PATH = "tests/test_r2a_p2b_b16_publication.py"
RECONCILIATION_TEST_RELATIVE_PATH = (
    "tests/test_r2a_p2b_b16_reconciliation_fail_closed.py"
)
DECISION_RELATIVE_PATH = (
    "knowledge/decisions/0075-materialize-integrated-r2a-p2b-b16-consumer-by-digest.md"
)
DECISION_PATH = ROOT / DECISION_RELATIVE_PATH
GUARDRAILS_PATH = ROOT / "policy" / "guardrails.yaml"
SOURCE_COMMIT = "f29499286bac9859364d45da0f6c59396518b749"  # pragma: allowlist secret -- public source revision
SOURCE_TREE = "ff38abe5718ebc550054ea6af18a73d0aef8e514"  # pragma: allowlist secret -- public source tree
AUTHORIZED_BEFORE_COMMIT = SOURCE_COMMIT
AUTHORIZED_PR_NUMBER = "257"
AUTHORIZED_PR_HEAD_REF = "r2a-b16-materialization"
CHECKOUT_ACTION = "actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd"
SETUP_PYTHON_ACTION = "actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1"
ATTEST_ACTION = "actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6"
B15_SMOKE = "ci/review_b15_runtime_smoke.py"
B16_SMOKE = "ci/review_b16_entrypoint_smoke.py"
B16_ENTRYPOINT = "tools/review_live_entrypoint.py"
B16_RUNTIME_LOCK = "b16-source/requirements/runtime.lock"
RESTRICTED_NATIVE_RATIONALE = (
    "Restricted native orchestration: the runner owns the Docker service; "
    "the candidate receives no daemon or socket authority."
)
_HEREDOC_RE = re.compile(r"(?<!<)(<<-?)(?!<)\s*[\"']?([A-Za-z_][A-Za-z0-9_]*)[\"']?")


def _load_workflow() -> dict[str, object]:
    workflow = yaml.load(
        WORKFLOW_PATH.read_text(encoding="utf-8"), Loader=yaml.BaseLoader
    )
    if not isinstance(workflow, dict):
        raise AssertionError("B1.6 publication workflow must be a YAML mapping")
    return workflow


def _guardrail_section(guardrails: str, guardrail_id: str) -> str:
    marker = f"  - id: {guardrail_id}"
    return guardrails.split(marker, 1)[1].split("\n  - id:", 1)[0]


def _named_bash_run_step(steps: list[object], name: str) -> str:
    matches = [
        step for step in steps if isinstance(step, dict) and step.get("name") == name
    ]
    if len(matches) != 1:
        raise AssertionError(f"expected exactly one workflow step named {name!r}")
    step = matches[0]
    run = step.get("run")
    if step.get("shell") != "bash" or not isinstance(run, str):
        raise AssertionError(f"workflow step {name!r} must be a bash run step")
    return run


def _has_direct_top_level_shell_sequence(
    script: str, sequence: tuple[str, ...]
) -> bool:
    lines = script.splitlines()
    width = len(sequence)
    starts = [
        index
        for index in range(len(lines) - width + 1)
        if tuple(lines[index : index + width]) == sequence
    ]
    if len(starts) != 1:
        return False

    stack: list[str] = []
    heredoc: tuple[str, bool] | None = None
    for raw_line in lines[: starts[0]]:
        stripped = raw_line.strip()
        if heredoc is not None:
            delimiter, strip_tabs = heredoc
            candidate = raw_line.lstrip("\t") if strip_tabs else raw_line
            if candidate == delimiter:
                heredoc = None
            continue
        if not stripped or stripped.startswith("#"):
            continue

        if stripped.startswith(")") and stack and stack[-1] == "cmdsub":
            stack.pop()
            continue

        closers = {
            "fi": "fi",
            "done": "done",
            "esac": "esac",
            ")": ")",
            "}": "}",
        }
        if stripped in closers:
            expected = closers[stripped]
            if not stack or stack[-1] != expected:
                return False
            stack.pop()
            continue

        if stripped.startswith("if "):
            stack.append("fi")
        elif stripped.startswith(("for ", "while ", "until ", "select ")):
            stack.append("done")
        elif stripped.startswith("case "):
            stack.append("esac")
        elif stripped == "(":
            stack.append(")")
        elif stripped.endswith("{"):
            stack.append("}")

        last_command_sub = stripped.rfind("$(")
        if last_command_sub >= 0 and ")" not in stripped[last_command_sub + 2 :]:
            stack.append("cmdsub")

        heredoc_match = _HEREDOC_RE.search(stripped)
        if heredoc_match is not None:
            operator, delimiter = heredoc_match.groups()
            heredoc = (delimiter, operator == "<<-")

    return heredoc is None and not stack


class R2AP2bB16PublicationTests(unittest.TestCase):
    def test_exact_integrated_b16_has_one_shot_digest_only_publisher(self) -> None:
        self.assertTrue(
            WORKFLOW_PATH.is_file(),
            "P2B_B16_PUBLISHER_UNAVAILABLE: exact integrated B1.6 has no "
            "protected-main one-shot OCI materializer",
        )
        workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
        workflow = _load_workflow()

        self.assertEqual(
            "Publish R2A P2b-B1.6 prior-effective OCI consumer", workflow["name"]
        )
        self.assertEqual(
            {
                "push": {
                    "branches": ["main"],
                    "paths": [WORKFLOW_RELATIVE_PATH],
                }
            },
            workflow["on"],
        )
        self.assertEqual({}, workflow["permissions"])
        workflow_env = workflow["env"]
        self.assertIsInstance(workflow_env, dict)
        assert isinstance(workflow_env, dict)
        self.assertEqual(AUTHORIZED_PR_NUMBER, workflow_env["AUTHORIZED_PR_NUMBER"])
        self.assertEqual(AUTHORIZED_PR_HEAD_REF, workflow_env["AUTHORIZED_PR_HEAD_REF"])

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
        self.assertEqual("authorize", publish["needs"])
        self.assertEqual({"pull-requests": "read"}, authorize["permissions"])
        self.assertEqual(
            {"EVENT_BEFORE": "${{ github.event.before }}"},
            authorize["env"],
        )
        authorize_steps = authorize["steps"]
        self.assertIsInstance(authorize_steps, list)
        assert isinstance(authorize_steps, list)
        required_authorization_checks = (
            'test "${GITHUB_REPOSITORY}" = "ktogias/gnostoa"',
            'test "${GITHUB_EVENT_NAME}" = "push"',
            'test "${GITHUB_REF}" = "refs/heads/main"',
            'test "${GITHUB_REF_TYPE}" = "branch"',
            'test "${GITHUB_REF_NAME}" = "main"',
            'test "${GITHUB_ACTOR}" = "ktogias"',
            'test "${GITHUB_TRIGGERING_ACTOR}" = "ktogias"',
            'test "${GITHUB_RUN_ATTEMPT}" = "1"',
            'test "${EVENT_BEFORE}" = "${AUTHORIZED_BEFORE_COMMIT}"',
            (
                'test "${GITHUB_WORKFLOW_REF}" = '
                '"${GITHUB_REPOSITORY}/.github/workflows/'
                'publish-r2a-p2b-b16-oci.yml@refs/heads/main"'
            ),
        )
        boundary_run = _named_bash_run_step(
            authorize_steps, "Refuse any context outside the admitted one-shot boundary"
        )
        self.assertEqual(
            ["set -euo pipefail", *required_authorization_checks],
            boundary_run.splitlines(),
            "authorization guards must be direct executable commands in the authorize job",
        )
        provider_binding_run = _named_bash_run_step(
            authorize_steps, "Bind the pushed commit to merged PR 257"
        )
        for required_provider_binding in (
            "timeout --kill-after=5s",
            "pulls/${AUTHORIZED_PR_NUMBER}",
            "merge_commit_sha",
            "AUTHORIZED_PR_HEAD_REF",
            "GITHUB_SHA",
        ):
            self.assertIn(required_provider_binding, provider_binding_run)
        self.assertEqual(
            {
                "contents": "read",
                "packages": "write",
                "id-token": "write",
                "attestations": "write",
            },
            publish["permissions"],
        )

        steps = publish["steps"]
        self.assertIsInstance(steps, list)
        assert isinstance(steps, list)
        checkout_steps = [
            step
            for step in steps
            if isinstance(step, dict) and step.get("uses") == CHECKOUT_ACTION
        ]
        self.assertEqual(2, len(checkout_steps))
        publisher_checkout, source_checkout = checkout_steps
        self.assertEqual(
            {"persist-credentials": "false", "fetch-depth": "1"},
            publisher_checkout["with"],
        )
        self.assertEqual(
            {
                "persist-credentials": "false",
                "fetch-depth": "1",
                "ref": "${{ env.SOURCE_COMMIT }}",
                "path": "b16-source",
            },
            source_checkout["with"],
        )

        attest_steps = [
            step
            for step in steps
            if isinstance(step, dict) and step.get("uses") == ATTEST_ACTION
        ]
        self.assertEqual(1, len(attest_steps))
        self.assertEqual(
            {
                "subject-name": "${{ env.IMAGE_NAME }}",
                "subject-digest": "${{ steps.publish.outputs.registry_digest }}",
                "push-to-registry": "true",
            },
            attest_steps[0]["with"],
        )

        self.assertIn(f"SOURCE_COMMIT: {SOURCE_COMMIT}", workflow_text)
        self.assertIn(f"SOURCE_TREE: {SOURCE_TREE}", workflow_text)
        self.assertIn(
            f"AUTHORIZED_BEFORE_COMMIT: {AUTHORIZED_BEFORE_COMMIT}", workflow_text
        )
        self.assertIn("IMAGE_NAME: ghcr.io/ktogias/gnostoa", workflow_text)
        self.assertIn(
            'test "$(git rev-parse HEAD)" = "${SOURCE_COMMIT}"', workflow_text
        )
        self.assertIn(
            'test "$(git rev-parse \'HEAD^{tree}\')" = "${SOURCE_TREE}"',
            workflow_text,
        )
        self.assertIn("surface-digest --root /opt/gnostoa", workflow_text)
        self.assertIn("--push-by-digest", workflow_text)
        self.assertIn("--metadata-file", workflow_text)
        self.assertIn('metadata["containerimage.digest"]', workflow_text)
        self.assertIn('digest_ref="${IMAGE_NAME}@${registry_digest}"', workflow_text)
        self.assertIn('digest_ref="${IMAGE_NAME}@${REGISTRY_DIGEST}"', workflow_text)
        self.assertIn('test "${actual}" = "${PUBLIC_DIGEST}"', workflow_text)
        self.assertIn("gh attestation verify", workflow_text)
        self.assertIn("anonymous_config=", workflow_text)

        for forbidden in (
            "workflow_dispatch",
            "docker push",
            "refs/tags/",
            "gh release",
            "git tag",
            ":latest",
            "RELEASE_VERSION",
            "IMAGE_TAG:",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, workflow_text)

    def test_b16_host_smoke_uses_exact_source_runtime_dependencies(self) -> None:
        workflow = _load_workflow()
        jobs = workflow["jobs"]
        self.assertIsInstance(jobs, dict)
        assert isinstance(jobs, dict)
        publish = jobs["publish"]
        self.assertIsInstance(publish, dict)
        assert isinstance(publish, dict)
        steps = publish["steps"]
        self.assertIsInstance(steps, list)
        assert isinstance(steps, list)

        source_checkout_index = next(
            index
            for index, step in enumerate(steps)
            if isinstance(step, dict)
            and step.get("uses") == CHECKOUT_ACTION
            and isinstance(step.get("with"), dict)
            and step["with"].get("path") == "b16-source"
        )
        setup_indices = [
            index
            for index, step in enumerate(steps)
            if isinstance(step, dict) and step.get("uses") == SETUP_PYTHON_ACTION
        ]
        self.assertEqual(1, len(setup_indices))
        setup_index = setup_indices[0]
        setup_step = steps[setup_index]
        assert isinstance(setup_step, dict)
        self.assertEqual(
            {
                "python-version": "3.12",
                "cache": "pip",
                "cache-dependency-path": B16_RUNTIME_LOCK,
            },
            setup_step["with"],
        )

        install_indices = [
            index
            for index, step in enumerate(steps)
            if isinstance(step, dict)
            and step.get("name") == "Install exact B1.6 source runtime dependencies"
        ]
        self.assertEqual(1, len(install_indices))
        install_index = install_indices[0]
        install_step = steps[install_index]
        assert isinstance(install_step, dict)
        install_run = install_step.get("run")
        self.assertIsInstance(install_run, str)
        assert isinstance(install_run, str)
        for required in (
            "python -m pip install",
            "--only-binary=:all:",
            "--require-hashes",
            f"-r {B16_RUNTIME_LOCK}",
        ):
            self.assertIn(required, install_run)

        local_verify_index = next(
            index
            for index, step in enumerate(steps)
            if isinstance(step, dict)
            and step.get("name")
            == "Build and verify exact B1.6 consumer locally before any registry effect"
        )
        self.assertLess(source_checkout_index, setup_index)
        self.assertLess(setup_index, install_index)
        self.assertLess(install_index, local_verify_index)

    def test_b16_native_smoke_path_is_explicitly_restricted_and_rationalized(
        self,
    ) -> None:
        workflow = _load_workflow()
        jobs = workflow["jobs"]
        self.assertIsInstance(jobs, dict)
        assert isinstance(jobs, dict)
        publish = jobs["publish"]
        self.assertIsInstance(publish, dict)
        assert isinstance(publish, dict)
        steps = publish["steps"]
        self.assertIsInstance(steps, list)
        assert isinstance(steps, list)

        local_run = _named_bash_run_step(
            steps,
            "Build and verify exact B1.6 consumer locally before any registry effect",
        )
        authenticated_run = _named_bash_run_step(
            steps,
            "Publish exact B1.6 consumer without a remote tag and read back digest",
        )
        anonymous_run = _named_bash_run_step(
            steps, "Verify attestation and anonymous digest acquisition"
        )
        reconciliation_run = _named_bash_run_step(
            steps, "Reconcile and clean post-publication state"
        )
        smoke_cuts = (
            (
                "local",
                local_run,
                'GNOSTOA_R2A_CANDIDATE_IMAGE="${local_image}" '
                f"python b16-source/{B15_SMOKE}",
                'PYTHONPATH=b16-source GNOSTOA_R2A_CANDIDATE_IMAGE="${local_image}" '
                f"python b16-source/{B16_SMOKE}",
            ),
            (
                "authenticated",
                authenticated_run,
                'GNOSTOA_R2A_CANDIDATE_IMAGE="${digest_ref}" '
                f"python b16-source/{B15_SMOKE}",
                'PYTHONPATH=b16-source GNOSTOA_R2A_CANDIDATE_IMAGE="${digest_ref}" '
                f"python b16-source/{B16_SMOKE}",
            ),
            (
                "anonymous",
                anonymous_run,
                'GNOSTOA_R2A_CANDIDATE_IMAGE="${digest_ref}" '
                f"python b16-source/{B15_SMOKE}",
                'PYTHONPATH=b16-source GNOSTOA_R2A_CANDIDATE_IMAGE="${digest_ref}" '
                f"python b16-source/{B16_SMOKE}",
            ),
            (
                "reconciliation",
                reconciliation_run,
                'GNOSTOA_R2A_CANDIDATE_IMAGE="${digest_ref}" '
                f"python b16-source/{B15_SMOKE}",
                'PYTHONPATH=b16-source GNOSTOA_R2A_CANDIDATE_IMAGE="${digest_ref}" '
                f"python b16-source/{B16_SMOKE}",
            ),
        )
        rationale_line = f"# {RESTRICTED_NATIVE_RATIONALE}"
        for cut_name, smoke_run, b15_command, b16_command in smoke_cuts:
            with self.subTest(cut=cut_name):
                self.assertEqual("set -euo pipefail", smoke_run.splitlines()[0])
                self.assertTrue(
                    _has_direct_top_level_shell_sequence(
                        smoke_run, (rationale_line, b15_command, b16_command)
                    ),
                    f"{cut_name} B1.5/B1.6 smoke must execute directly at shell top level",
                )

    def test_shell_structure_helper_rejects_inert_smoke_sequences(self) -> None:
        rationale_line = f"# {RESTRICTED_NATIVE_RATIONALE}"
        b15_command = (
            'GNOSTOA_R2A_CANDIDATE_IMAGE="${digest_ref}" '
            f"python b16-source/{B15_SMOKE}"
        )
        b16_command = (
            'PYTHONPATH=b16-source GNOSTOA_R2A_CANDIDATE_IMAGE="${digest_ref}" '
            f"python b16-source/{B16_SMOKE}"
        )
        sequence = (rationale_line, b15_command, b16_command)
        heredoc_inert = "\n".join(
            (
                "set -euo pipefail",
                "cat <<EOF",
                "  EOF",
                *sequence,
                "EOF",
            )
        )
        multiline_if_inert = "\n".join(
            (
                "set -euo pipefail",
                "if false",
                "then",
                *sequence,
                "fi",
            )
        )
        multiline_loop_inert = "\n".join(
            (
                "set -euo pipefail",
                "while false",
                "do",
                *sequence,
                "done",
            )
        )
        self.assertFalse(_has_direct_top_level_shell_sequence(heredoc_inert, sequence))
        self.assertFalse(
            _has_direct_top_level_shell_sequence(multiline_if_inert, sequence)
        )
        self.assertFalse(
            _has_direct_top_level_shell_sequence(multiline_loop_inert, sequence)
        )

    def test_b16_materialization_reproves_b15_and_b16_runtime_at_all_three_cuts(
        self,
    ) -> None:
        self.assertTrue(
            WORKFLOW_PATH.is_file(),
            "P2B_B16_PUBLISHER_UNAVAILABLE",
        )
        workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
        for required_source in (B15_SMOKE, B16_SMOKE, B16_ENTRYPOINT):
            self.assertIn(
                f'grep -Fx "{required_source}" /opt/gnostoa/.gnostoa-source-files',
                workflow_text,
            )

        local_b15 = (
            'GNOSTOA_R2A_CANDIDATE_IMAGE="${local_image}" '
            f"python b16-source/{B15_SMOKE}"
        )
        local_b16 = (
            'PYTHONPATH=b16-source GNOSTOA_R2A_CANDIDATE_IMAGE="${local_image}" '
            f"python b16-source/{B16_SMOKE}"
        )
        digest_b16 = (
            'PYTHONPATH=b16-source GNOSTOA_R2A_CANDIDATE_IMAGE="${digest_ref}" '
            f"python b16-source/{B16_SMOKE}"
        )
        self.assertIn(local_b15, workflow_text)
        self.assertIn(local_b16, workflow_text)
        self.assertEqual(
            3,
            workflow_text.count(digest_b16),
            "authenticated, anonymous, and reconciliation B1.6 smoke cuts must import from the exact source checkout",
        )
        self.assertGreaterEqual(
            workflow_text.count(f"python b16-source/{B15_SMOKE}"),
            4,
            "B1.5 Docker-client/no-daemon capability must be re-proved at all four cuts",
        )
        self.assertEqual(
            4,
            workflow_text.count(f"python b16-source/{B16_SMOKE}"),
            "B1.6 input-only module/daemonless capability must be re-proved at exactly all four cuts",
        )
        login_index = workflow_text.index("docker login ghcr.io")
        self.assertLess(workflow_text.index(local_b15), login_index)
        self.assertLess(workflow_text.index(local_b16), login_index)
        self.assertNotIn("/var/run/docker.sock", workflow_text)

    def test_digest_readback_is_uniform_and_anonymous_reacquisition_is_not_cached(
        self,
    ) -> None:
        workflow = _load_workflow()
        jobs = workflow["jobs"]
        self.assertIsInstance(jobs, dict)
        assert isinstance(jobs, dict)
        publish = jobs["publish"]
        self.assertIsInstance(publish, dict)
        assert isinstance(publish, dict)
        steps = publish["steps"]
        self.assertIsInstance(steps, list)
        assert isinstance(steps, list)

        digest_uid_check = (
            'test "$(docker run --rm --entrypoint id "${digest_ref}" -u)" = "10001"'
        )
        digest_gid_check = (
            'test "$(docker run --rm --entrypoint id "${digest_ref}" -g)" = "10001"'
        )
        authenticated_block = _named_bash_run_step(
            steps,
            "Publish exact B1.6 consumer without a remote tag and read back digest",
        )
        anonymous_block = _named_bash_run_step(
            steps, "Verify attestation and anonymous digest acquisition"
        )
        for cut_name, digest_cut in (
            ("authenticated", authenticated_block),
            ("anonymous", anonymous_block),
        ):
            with self.subTest(cut=cut_name):
                self.assertIn(
                    digest_uid_check,
                    digest_cut,
                    f"{cut_name} digest cut must prove uid 10001",
                )
                self.assertIn(
                    digest_gid_check,
                    digest_cut,
                    f"{cut_name} digest cut must prove gid 10001",
                )
                self.assertIn("bounded_registry_capture()", digest_cut)
                self.assertIn("timeout --kill-after=5s", digest_cut)
                self.assertIn("head -c 4097", digest_cut)
                self.assertIn("docker buildx imagetools inspect", digest_cut)
                self.assertIn('docker pull --quiet "${digest_ref}"', digest_cut)

        permissive_rm = 'docker image rm "${digest_ref}" >/dev/null 2>&1 || true'
        strict_rm = 'docker image rm "${digest_ref}" >/dev/null'
        absence_probe = 'if docker image inspect "${digest_ref}" >/dev/null 2>&1; then'
        anonymous_pull = 'docker pull --quiet "${digest_ref}"'
        failure_exit = "exit 1"
        for required_command in (
            strict_rm,
            absence_probe,
            anonymous_pull,
            permissive_rm,
            failure_exit,
        ):
            self.assertIn(
                required_command,
                anonymous_block,
                f"anonymous teardown ordering requires command {required_command!r}",
            )

        strict_rm_index = anonymous_block.index(strict_rm)
        absence_probe_index = anonymous_block.index(absence_probe)
        anonymous_pull_index = anonymous_block.index(anonymous_pull)
        permissive_cleanup_index = anonymous_block.index(permissive_rm)

        self.assertEqual(1, anonymous_block.count(permissive_rm))
        self.assertLess(strict_rm_index, absence_probe_index)
        self.assertLess(absence_probe_index, anonymous_pull_index)
        self.assertLess(anonymous_pull_index, permissive_cleanup_index)
        self.assertLess(
            permissive_cleanup_index,
            anonymous_block.index(failure_exit, permissive_cleanup_index),
        )
        self.assertLess(
            anonymous_pull_index,
            anonymous_block.index(digest_uid_check),
        )
        self.assertLess(
            anonymous_pull_index,
            anonymous_block.index(digest_gid_check),
        )

    def test_post_write_reconciliation_and_local_cleanup_are_fail_closed(self) -> None:
        workflow = _load_workflow()
        jobs = workflow["jobs"]
        self.assertIsInstance(jobs, dict)
        assert isinstance(jobs, dict)
        publish = jobs["publish"]
        self.assertIsInstance(publish, dict)
        assert isinstance(publish, dict)
        steps = publish["steps"]
        self.assertIsInstance(steps, list)
        assert isinstance(steps, list)

        local_run = _named_bash_run_step(
            steps,
            "Build and verify exact B1.6 consumer locally before any registry effect",
        )
        local_image = 'local_image="gnostoa-r2a-p2b-b16-verify:${SOURCE_COMMIT}"'
        local_cleanup = "trap cleanup_local_image EXIT"
        for required in (
            "cleanup_local_image()",
            "local prior_status=$?",
            "local cleanup_status=0",
            "trap - EXIT",
            'if ! docker image rm "${local_image}" >/dev/null 2>&1; then',
            'if docker image inspect "${local_image}" >/dev/null 2>&1; then',
            'echo "local verification image remained cached" >&2',
            'echo "local verification image cleanup failed" >&2',
            'if [ "${cleanup_status}" -ne 0 ]; then',
            'exit "${prior_status}"',
            'exit "${cleanup_status}"',
            local_cleanup,
        ):
            self.assertIn(required, local_run)
        self.assertNotIn(
            "trap 'docker image rm \"${local_image}\" >/dev/null 2>&1 || true' EXIT",
            local_run,
        )
        self.assertLess(local_run.index(local_image), local_run.index(local_cleanup))
        self.assertEqual("cleanup_local_image", local_run.rstrip().splitlines()[-1])

        reconciliation_name = "Reconcile and clean post-publication state"
        reconciliation_matches = [
            (index, step)
            for index, step in enumerate(steps)
            if isinstance(step, dict) and step.get("name") == reconciliation_name
        ]
        self.assertEqual(1, len(reconciliation_matches))
        reconciliation_index, reconciliation_step = reconciliation_matches[0]
        assert isinstance(reconciliation_step, dict)
        anonymous_index = next(
            index
            for index, step in enumerate(steps)
            if isinstance(step, dict)
            and step.get("name")
            == "Verify attestation and anonymous digest acquisition"
        )
        self.assertLess(anonymous_index, reconciliation_index)
        self.assertEqual(
            "${{ always() && steps.publish.outcome != 'skipped' }}",
            reconciliation_step["if"],
        )
        self.assertEqual("bash", reconciliation_step["shell"])
        self.assertEqual(
            {
                "GH_TOKEN": "${{ github.token }}",
                "REGISTRY_DIGEST": "${{ steps.publish.outputs.registry_digest }}",
                "METADATA_FILE": "${{ runner.temp }}/r2a-p2b-b16-build-metadata.json",
                "BUILD_DATE": "${{ steps.source.outputs.build_date }}",
                "PUBLIC_DIGEST": "${{ steps.local.outputs.public_digest }}",
            },
            reconciliation_step["env"],
        )
        reconciliation_run = _named_bash_run_step(steps, reconciliation_name)
        for required in (
            "set -euo pipefail",
            'registry_digest="${REGISTRY_DIGEST}"',
            'if [ -z "${registry_digest}" ]; then',
            'python - "${METADATA_FILE}"',
            'metadata["containerimage.digest"]',
            'digest_ref="${IMAGE_NAME}@${registry_digest}"',
            "bounded_registry_capture()",
            "timeout --kill-after=5s",
            "head -c 4097",
            "cleanup_post_write()",
            "trap cleanup_post_write EXIT",
            "local prior_status=$?",
            "local cleanup_status=0",
            "trap - EXIT",
            "bounded_registry_capture 30 docker buildx imagetools inspect",
            "bounded_registry_capture 30 gh attestation verify",
            'env DOCKER_CONFIG="${reconcile_config}"',
            'docker pull --quiet "${digest_ref}"',
            'test "$(git -C b16-source rev-parse HEAD)" = "${SOURCE_COMMIT}"',
            'test "${actual}" = "${PUBLIC_DIGEST}"',
        ):
            self.assertIn(required, reconciliation_run)
        self.assertNotIn(
            "docker logout ghcr.io >/dev/null 2>&1 || true", reconciliation_run
        )
        self.assertNotIn(
            'docker image rm "${digest_ref}" >/dev/null 2>&1 || true',
            reconciliation_run,
        )
        for forbidden in ("docker push", "--push-by-digest"):
            self.assertNotIn(forbidden, reconciliation_run)

    def test_b16_decision_triggers_dedicated_r2a_verification(self) -> None:
        workflow = yaml.load(
            R2A_WORKFLOW_PATH.read_text(encoding="utf-8"), Loader=yaml.BaseLoader
        )
        self.assertIsInstance(workflow, dict)
        assert isinstance(workflow, dict)
        on = workflow["on"]
        self.assertIsInstance(on, dict)
        assert isinstance(on, dict)
        pull_request = on["pull_request"]
        self.assertIsInstance(pull_request, dict)
        assert isinstance(pull_request, dict)
        paths = pull_request["paths"]
        self.assertIsInstance(paths, list)
        assert isinstance(paths, list)
        for protected_path in (
            "knowledge/decisions/0072-materialize-integrated-r2a-p2b-b15-consumer-by-digest.md",
            "knowledge/decisions/0073-promote-r2a-b15-outer-consumer-authority.md",
            WORKFLOW_RELATIVE_PATH,
            DECISION_RELATIVE_PATH,
            FOCUSED_TEST_RELATIVE_PATH,
            RECONCILIATION_TEST_RELATIVE_PATH,
        ):
            self.assertIn(protected_path, paths)

    def test_b16_decision_is_semantic_review_assurance_owned(self) -> None:
        guardrails = GUARDRAILS_PATH.read_text(encoding="utf-8")
        semantic_section = _guardrail_section(guardrails, "semantic-review-assurance")
        self.assertIn(
            "knowledge/decisions/0072-materialize-integrated-r2a-p2b-b15-consumer-by-digest.md",
            semantic_section,
        )
        self.assertIn(DECISION_RELATIVE_PATH, semantic_section)

    def test_b16_materialization_is_governed_and_declared(self) -> None:
        self.assertTrue(
            DECISION_PATH.is_file(),
            "P2B_B16_MATERIALIZATION_DECISION_UNAVAILABLE",
        )
        decision = DECISION_PATH.read_text(encoding="utf-8")
        for required in (
            "Decision 0072",
            "Decision 0073",
            "Decision 0074",
            "5671332574",
            SOURCE_COMMIT,
            SOURCE_TREE,
            "digest-only",
            "no blind rerun",
            "prior-effective",
            "P2b-B2",
            "not a release",
            "host Docker socket",
            "review_live_entrypoint",
            "candidate-injected",
        ):
            self.assertIn(required, decision)

        guardrails = GUARDRAILS_PATH.read_text(encoding="utf-8")
        immutable_section = _guardrail_section(
            guardrails, "immutable-provider-ci-adapters"
        )
        self.assertIn(WORKFLOW_RELATIVE_PATH, immutable_section)
        self.assertIn(
            "tests/test_r2a_p2b_b16_publication.py::"
            "R2AP2bB16PublicationTests."
            "test_b16_materialization_is_governed_and_declared",
            immutable_section,
        )


if __name__ == "__main__":
    unittest.main()
