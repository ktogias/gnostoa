from __future__ import annotations

import hashlib
import importlib
import json
import os
import re
import subprocess
import tarfile
import tempfile
import tomllib
import unittest
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from io import BytesIO, StringIO
from pathlib import Path
from unittest.mock import patch

from tools import knowledge_common
from tools.build_context_pack import build_pack
from tools.build_docs import prepare_projection
from tools.check_change_policy import check_change_policy, load_change_policy
from tools.check_guardrails import check_guardrails
from tools.check_runtime_lock import check_runtime_lock, public_surface_digest
from tools.cli import main as cli_main
from tools.knowledge_common import (
    Document,
    KnowledgeFormatError,
    load_profile,
    load_yaml,
    markdown_links,
    resolve_target,
)
from tools.release_smoke import (
    ArtifactResult,
    ReleaseSmokeError,
    distribution_metadata_issues,
    release_evidence_manifest,
    release_smoke,
    verify_release_source,
    wheel_canonical_payloads,
    write_release_evidence_manifest,
)
from tools.repository_scope import find_text_matches
from tools.requirements_lock import locked_requirements
from tools.validate_bundle import Issue, _validate_links, validate_bundle

ROOT = Path(__file__).resolve().parent.parent


def _add_tar_bytes(archive: tarfile.TarFile, name: str, content: bytes) -> None:
    member = tarfile.TarInfo(name)
    member.size = len(content)
    archive.addfile(member, BytesIO(content))


def _release_archive_fixtures(
    directory: Path,
    *,
    version: str = "0.1.2",
    include_notice: bool = True,
) -> tuple[Path, Path]:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]
    metadata = (
        "Metadata-Version: 2.4\n"
        f"Name: {project['name']}\n"
        f"Version: {version}\n"
        f"License-Expression: {project['license']}\n"
        f"Requires-Python: {project['requires-python']}\n"
        + "".join(
            f"Requires-Dist: {requirement}\n" for requirement in project["dependencies"]
        )
        + "".join(
            f'Requires-Dist: {requirement}; extra == "{extra}"\n'
            for extra, requirements in project.get("optional-dependencies", {}).items()
            for requirement in requirements
        )
        + "\n"
    ).encode()
    entry_points = (
        "[console_scripts]\n"
        + "".join(f"{name} = {target}\n" for name, target in project["scripts"].items())
    ).encode()
    license_bytes = (ROOT / "LICENSE").read_bytes()
    notice_bytes = (ROOT / "NOTICE").read_bytes()

    wheel = directory / f"gnostoa-{version}-py3-none-any.whl"
    dist_info = f"gnostoa-{version}.dist-info"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("tools/__init__.py", "")
        archive.writestr(f"{dist_info}/METADATA", metadata)
        archive.writestr(f"{dist_info}/entry_points.txt", entry_points)
        archive.writestr(f"{dist_info}/licenses/LICENSE", license_bytes)
        if include_notice:
            archive.writestr(f"{dist_info}/licenses/NOTICE", notice_bytes)

    source_distribution = directory / f"gnostoa-{version}.tar.gz"
    source_root = f"gnostoa-{version}"
    with tarfile.open(source_distribution, "w:gz") as archive:
        _add_tar_bytes(archive, f"{source_root}/PKG-INFO", metadata)
        _add_tar_bytes(archive, f"{source_root}/LICENSE", license_bytes)
        if include_notice:
            _add_tar_bytes(archive, f"{source_root}/NOTICE", notice_bytes)
        for name in ("README.md", "pyproject.toml", "tools/cli.py"):
            _add_tar_bytes(archive, f"{source_root}/{name}", (ROOT / name).read_bytes())
    return wheel, source_distribution


class BrandIdentityTests(unittest.TestCase):
    def test_publishable_project_identity_is_gnostoa(self) -> None:
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual("gnostoa", project["project"]["name"])
        self.assertTrue(
            (ROOT / "README.md").read_text(encoding="utf-8").startswith("# Gnostoa\n")
        )
        self.assertIn(
            "site_name: Gnostoa",
            (ROOT / "mkdocs.yml").read_text(encoding="utf-8"),
        )
        self.assertIn(
            'org.opencontainers.image.title="Gnostoa"',
            (ROOT / "Dockerfile").read_text(encoding="utf-8"),
        )
        self.assertTrue((ROOT / "knowledge" / "project" / "gnostoa.md").is_file())
        self.assertFalse(
            (ROOT / "knowledge" / "project" / "knowledge-architecture-kit.md").exists()
        )

    def test_self_policy_and_distribution_identity_track_gnostoa(self) -> None:
        self.assertEqual(
            "gnostoa-self",
            load_yaml(ROOT / "knowledge" / "profile.yaml")["id"],
        )
        expected_policy_ids = {
            "change-control.yaml": "gnostoa-change-control",
            "continuous-integration.yaml": "gnostoa-continuous-integration",
            "verification.yaml": "gnostoa-verification",
        }
        for filename, expected_id in expected_policy_ids.items():
            policy = load_yaml(ROOT / "policy" / filename)
            self.assertEqual(expected_id, policy["id"])
            self.assertEqual("team:gnostoa-maintainers", policy["owner"])

        self.assertIn(
            "registry.example.org/gnostoa@sha256:",
            (ROOT / "templates" / "knowledge-kit.lock.yaml").read_text(
                encoding="utf-8"
            ),
        )
        self.assertNotIn(
            "team:knowledge-architecture-kit-maintainers",
            (ROOT / "policy" / "guardrails.yaml").read_text(encoding="utf-8"),
        )


class PublicationBaselineTests(unittest.TestCase):
    def test_repository_contains_no_specialization_vocabulary(self) -> None:
        forbidden_patterns = {
            "project name": re.compile("Open" + "OP", re.IGNORECASE),
            "standards organization": re.compile(
                r"\b" + "ET" + "SI" + r"\b",
                re.IGNORECASE,
            ),
            "module name": re.compile(
                r"\b" + "TF" + r"[-_ ]" + "SDK" + r"\b",
                re.IGNORECASE,
            ),
            "component acronym": re.compile(
                r"\b" + "S" + "RM" + r"\b",
                re.IGNORECASE,
            ),
        }
        self.assertEqual([], find_text_matches(ROOT, forbidden_patterns))

    def test_schema_ids_use_the_versioned_gnostoa_namespace(self) -> None:
        schema_paths = sorted((ROOT / "schemas").glob("*.schema.json"))
        self.assertTrue(schema_paths)

        ids: list[str] = []
        for path in schema_paths:
            schema = json.loads(path.read_text(encoding="utf-8"))
            expected = f"https://ktogias.github.io/gnostoa/schemas/v1/{path.name}"
            self.assertEqual(expected, schema.get("$id"), path.name)
            ids.append(schema["$id"])

        self.assertEqual(len(ids), len(set(ids)))

    def test_github_provider_surface_is_active_and_owned(self) -> None:
        workflow_path = ROOT / ".github" / "workflows" / "verification.yml"
        codeowners_path = ROOT / ".github" / "CODEOWNERS"
        self.assertTrue(workflow_path.is_file())
        self.assertTrue(codeowners_path.is_file())

        workflow = workflow_path.read_text(encoding="utf-8")
        for event in (
            "pull_request:",
            "merge_group:",
            "push:",
            "schedule:",
            "workflow_dispatch:",
        ):
            self.assertIn(event, workflow)
        for suite in ("policy", "fast", "regression", "smoke", "extended"):
            self.assertIn(f"./ci/verify {suite}", workflow)
        self.assertIn("permissions:", workflow)
        self.assertIn("contents: read", workflow)
        self.assertIn(
            "github.event.pull_request.number || github.ref",
            workflow,
        )
        self.assertIn("always() &&", workflow)
        self.assertIn(
            "(github.event_name != 'push' || github.ref == 'refs/heads/main')",
            workflow,
        )
        self.assertRegex(workflow, r"actions/checkout@[a-f0-9]{40}")
        self.assertRegex(workflow, r"actions/setup-python@[a-f0-9]{40}")
        self.assertIn('python-version: ["3.11", "3.12"]', workflow)
        self.assertIn("needs: [policy, fast, python-compatibility]", workflow)
        self.assertIn("./ci/verify fast", workflow)
        self.assertIn("docker build", workflow)

        codeowners = codeowners_path.read_text(encoding="utf-8")
        for owned_path in (
            "* @ktogias",
            "/.github/ @ktogias",
            "/core/ @ktogias",
            "/schemas/ @ktogias",
            "/policy/ @ktogias",
            "/knowledge/ @ktogias",
            "/guidance/ @ktogias",
        ):
            self.assertIn(owned_path, codeowners)

    def test_pr_candidate_binding_is_generic_and_complete(self) -> None:
        workflow_path = ROOT / ".github" / "workflows" / "verification.yml"
        workflow = workflow_path.read_text(encoding="utf-8")
        binding = workflow.split(
            "      - name: Bind the exact PR executable candidate\n", maxsplit=1
        )[1].split("\n  extended:\n", maxsplit=1)[0]

        sb2_paths = (
            "tools/build_context_pack.py",
            "tools/build_docs.py",
            "tools/check_change_policy.py",
            "tools/check_ci_policy.py",
            "tools/check_guardrails.py",
            "tools/check_runtime_lock.py",
            "tools/cli.py",
            "tools/knowledge_common.py",
            "tools/repository_scope.py",
            "tools/self_check.py",
            "tools/task_envelope.py",
            "tools/validate_bundle.py",
        )
        for path in sb2_paths:
            with self.subTest(path=path):
                self.assertEqual(1, binding.count(path))

        for required in (
            'test "${candidate_commit}" = '
            '"${{ github.event.pull_request.head.sha || github.sha }}"',
            "candidate_tree=$(git rev-parse 'HEAD^{tree}')",
            "printf 'candidate.tree=%s\\n' \"${candidate_tree}\"",
            'git archive "${candidate_commit}"',
            "surface-digest --root /workspace",
            "surface-digest --root /opt/gnostoa",
            "surface-digest --root /vendored",
            'test "${source_digest}" = "${runtime_digest}"',
            'test "${source_digest}" = "${vendored_digest}"',
            'test "$(wc -l < "${sb2_paths_file}")" -eq 12',
            'cmp "${source_sb2_manifest}" "${runtime_sb2_manifest}"',
            'cmp "${source_sb2_manifest}" "${vendored_sb2_manifest}"',
            'docker run --rm "${GNOSTOA_CI_IMAGE}" self-check',
            "sb2.source.begin",
            "sb2.runtime.begin",
            "sb2.vendored.begin",
            'git diff --name-only "${BASE_SHA}" HEAD',
        ):
            with self.subTest(required=required):
                self.assertIn(required, binding)

        for incident_specific in (
            "ARG KIT_VERSION=0.1.1",
            "ARG KIT_VERSION=0.1.2",
            "expected_version_delta",
            "ci/build-runtime tools/repository_scope.py",
            "sb2.tools_knowledge_common",
            "continue-on-error",
            "|| true",
        ):
            with self.subTest(incident_specific=incident_specific):
                self.assertNotIn(incident_specific, binding)

        self.assertNotIn("Dockerfile", binding)
        self.assertGreater(
            binding.index('git diff --name-only "${BASE_SHA}" HEAD'),
            binding.index('docker run --rm "${GNOSTOA_CI_IMAGE}" self-check'),
        )

    def test_ghcr_publication_workflow_is_exact_and_write_once(self) -> None:
        workflow_path = ROOT / ".github" / "workflows" / "publish-oci.yml"
        self.assertTrue(workflow_path.is_file())
        workflow = workflow_path.read_text(encoding="utf-8")
        parsed = load_yaml(workflow_path)

        self.assertEqual({}, parsed["permissions"])
        self.assertEqual(["publish"], list(parsed["jobs"]))
        self.assertEqual(
            {
                "contents": "read",
                "packages": "write",
                "id-token": "write",
                "attestations": "write",
            },
            parsed["jobs"]["publish"]["permissions"],
        )
        self.assertEqual(
            {"group": "gnostoa-ghcr-0.1.1", "cancel-in-progress": False},
            parsed["concurrency"],
        )

        required = (
            "workflow_dispatch:",
            "group: gnostoa-ghcr-0.1.1",
            "cancel-in-progress: false",
            "contents: read",
            "packages: write",
            "id-token: write",
            "attestations: write",
            "refs/tags/v0.1.1",
            "84cc4959d9fb0b315084cc49a5381c13166b6554",  # pragma: allowlist secret -- public source revision
            "938a789f807b898797d2e634b7bfbaaedfe29a63",  # pragma: allowlist secret -- public source tree
            "ac7faf520bad82edd13ed41c6f9a9c8e686e019e",  # pragma: allowlist secret -- public tag object
            "ghcr.io/ktogias/gnostoa:0.1.1",
            "GNOSTOA_CANDIDATE_REF=v0.1.1",
            "GNOSTOA_KIT_VERSION=0.1.1",
            "BUILD_DATE=2026-08-22T13:20:42Z",
            "--platform linux/amd64",
            "--provenance=false",
            "--sbom=false",
            "manifest unknown|not found",
            'docker push "${IMAGE_REF}"',
            "--format '{{.Manifest.Digest}}'",
            "33792909555029c1b2879d78f112ba0e3227d73abac0b89652781554fee1af74",  # pragma: allowlist secret -- public-surface digest
            "68978e9fc1875f275c0dfb9bd71ed19d025b01f66409bb31d785d86165ee691c",  # pragma: allowlist secret -- public notice digest
            "actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd",
            "actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6",
            "subject-name: ghcr.io/ktogias/gnostoa",
            "push-to-registry: true",
            "create-storage-record: false",
            "gh attestation verify",
        )
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, workflow)

        self.assertNotIn("inputs:", workflow)
        self.assertNotIn("docker/login-action", workflow)
        self.assertNotIn("docker/setup-buildx-action", workflow)
        self.assertNotIn("docker/build-push-action", workflow)
        self.assertNotRegex(workflow, r"ghcr\.io/ktogias/gnostoa:latest\b")
        self.assertEqual(3, workflow.count("assert_tag_absent"))
        self.assertEqual(1, workflow.count('docker push "${IMAGE_REF}"'))

    def test_release_verification_is_bound_to_published_digest(self) -> None:
        verification = load_yaml(ROOT / "policy" / "verification.yaml")
        self.assertTrue(verification["capabilities"]["deployable_artifact"])
        self.assertEqual(
            ["./ci/verify", "release"],
            verification["suites"]["release"]["command"],
        )

        script = (ROOT / "ci" / "verify").read_text(encoding="utf-8")
        immutable_ref = (
            "ghcr.io/ktogias/gnostoa@sha256:"
            "73e5bd55fb4fed4accc836294a97b144d8b7060d68b19c3631ab7c05b5cd1455"  # pragma: allowlist secret -- public registry identity
        )
        self.assertIn(immutable_ref, script)
        self.assertNotIn("ghcr.io/ktogias/gnostoa:0.1.1", script)
        self.assertNotIn("SKIP: deployable_artifact capability is false", script)
        for marker in (
            "DOCKER_CONFIG",
            "docker pull",
            "linux/amd64",
            "3.12.14",
            "(2, 8, 3)",
            "33792909555029c1b2879d78f112ba0e3227d73abac0b89652781554fee1af74",  # pragma: allowlist secret -- public-surface digest
            "68978e9fc1875f275c0dfb9bd71ed19d025b01f66409bb31d785d86165ee691c",  # pragma: allowlist secret -- public notice digest
            "gnostoa-sb2.sha256",
            "self-check --skip-tests",
            "org.opencontainers.image.licenses",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, script)

    def test_current_indexes_cover_every_canonical_concept(self) -> None:
        for surface in ("guidance", "knowledge"):
            with self.subTest(surface=surface):
                index = ROOT / surface / "index.md"
                linked = {
                    resolved
                    for target in markdown_links(index.read_text(encoding="utf-8"))
                    if (resolved := resolve_target(ROOT, index, target)) is not None
                }
                expected = {
                    path.resolve()
                    for path in (ROOT / surface).rglob("*.md")
                    if path.name != "index.md"
                }
                self.assertEqual(set(), expected - linked)


class LicensePolicyTests(unittest.TestCase):
    def test_distribution_declares_one_apache_2_license_contract(self) -> None:
        license_bytes = (ROOT / "LICENSE").read_bytes()
        expected_license_digest = "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30"  # pragma: allowlist secret -- public LICENSE digest
        self.assertEqual(
            expected_license_digest,
            hashlib.sha256(license_bytes).hexdigest(),
        )
        license_text = license_bytes.decode("utf-8")
        self.assertIn("http://www.apache.org/licenses/", license_text)

        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual("Apache-2.0", project["project"]["license"])
        self.assertEqual(["LICENSE", "NOTICE"], project["project"]["license-files"])

    def test_composite_image_publishes_no_image_wide_license_expression(self) -> None:
        """The first-party licence is not an image-wide licence expression.

        `org.opencontainers.image.licenses` describes the licence(s) under which
        the *contained* software is distributed, as an SPDX expression. The
        image contains CPython, MIT-licensed distributions and Debian packages
        under many licence families, so Gnostoa's own Apache-2.0 does not
        describe it. The annotation is optional, and omitting it is truthful
        where a partial value would not be.

        This asserts the current selection, not a permanent rule: a later
        Decision may select a real image-wide expression, and this test is then
        the thing to change.
        """

        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertNotIn("org.opencontainers.image.licenses", dockerfile)
        # The first-party declaration stays exactly where it belongs.
        self.assertIn('org.opencontainers.image.title="Gnostoa"', dockerfile)
        self.assertIn(
            'org.opencontainers.image.authors="Konstantinos Togias"', dockerfile
        )

    def test_cpython_third_party_notices_are_version_bound_and_tracked(self) -> None:
        notice_path = ROOT / "THIRD_PARTY_NOTICES"
        notice_bytes = notice_path.read_bytes()
        self.assertEqual(
            "68978e9fc1875f275c0dfb9bd71ed19d025b01f66409bb31d785d86165ee691c",  # pragma: allowlist secret -- public notice digest
            hashlib.sha256(notice_bytes).hexdigest(),
        )

        manifest = ROOT / ".gnostoa-source-files"
        if manifest.is_file():
            self.assertIn(
                b"THIRD_PARTY_NOTICES",
                manifest.read_bytes().split(b"\0"),
            )
        else:
            tracked = subprocess.run(
                [
                    "git",
                    "-c",
                    f"safe.directory={ROOT}",
                    "-C",
                    str(ROOT),
                    "ls-files",
                    "--error-unmatch",
                    "THIRD_PARTY_NOTICES",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual("THIRD_PARTY_NOTICES", tracked.stdout.strip())

        def exact_section(start: bytes, end: bytes) -> bytes:
            return notice_bytes.split(start, maxsplit=1)[1].split(end, maxsplit=1)[0]

        cpython_licence = exact_section(
            b"----- BEGIN EXACT CPYTHON V3.12.14 DOC/LICENSE.RST -----\n",
            b"----- END EXACT CPYTHON V3.12.14 DOC/LICENSE.RST -----\n",
        )
        hacl_root_licence = exact_section(
            b"----- BEGIN EXACT HACL BOUND-REVISION ROOT LICENSE -----\n",
            b"----- END EXACT HACL BOUND-REVISION ROOT LICENSE -----\n",
        )
        self.assertEqual(
            "341832873fd316a37927e79385093fbbfd40a467428480835fe435a80cadf4e5",  # pragma: allowlist secret -- public CPython licence digest
            hashlib.sha256(cpython_licence).hexdigest(),
        )
        self.assertEqual(
            "c5accbbd8546e94c34aed24afe689a617627d18eed5a6c48277e48db57c23851",  # pragma: allowlist secret -- public HACL licence digest
            hashlib.sha256(hacl_root_licence).hexdigest(),
        )

        notice = notice_bytes.decode("utf-8")
        self.assertIn("CPython tag: v3.12.14", notice)
        self.assertIn(
            "bb3d0dc8d9d15a5cd51094d5b69e70aa09005ff0",  # pragma: allowlist secret -- public HACL revision
            notice,
        )
        self.assertIn("/opt/gnostoa/THIRD_PARTY_NOTICES", notice)
        self.assertIn("must be refreshed and\nre-verified", notice)

        # The existing source-authority route installs every tracked candidate
        # path beneath /opt/gnostoa. Exact runtime presence is read back from
        # the built image in the delivery verification for this candidate.
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("COPY --from=candidate --chown=kit:kit source/ .", dockerfile)

    def test_license_scope_is_explicit_for_adopting_projects(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        licensing = (ROOT / "LICENSING.md").read_text(encoding="utf-8")
        normalized_licensing = " ".join(licensing.split())
        self.assertIn("[Licensing](LICENSING.md)", readme)
        self.assertIn(
            "does not, by itself, change the license",
            normalized_licensing,
        )
        self.assertIn(
            "does not grant permission to use the Gnostoa name",
            normalized_licensing,
        )
        self.assertTrue(
            (
                ROOT
                / "knowledge"
                / "decisions"
                / "0010-license-gnostoa-under-apache-2.0.md"
            ).is_file()
        )

    def test_initial_owner_and_contributor_retention_are_consistent(self) -> None:
        self.assertEqual(
            "Gnostoa\nCopyright 2026 Konstantinos Togias\n",
            (ROOT / "NOTICE").read_text(encoding="utf-8"),
        )

        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(
            [{"name": "Konstantinos Togias"}],
            project["project"]["authors"],
        )
        self.assertIn(
            'org.opencontainers.image.authors="Konstantinos Togias"',
            (ROOT / "Dockerfile").read_text(encoding="utf-8"),
        )

        licensing = " ".join(
            (ROOT / "LICENSING.md").read_text(encoding="utf-8").split()
        )
        contributing = " ".join(
            (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8").split()
        )
        self.assertIn("Copyright 2026 Konstantinos Togias", licensing)
        self.assertIn(
            "Contributors retain copyright in their contributions",
            contributing,
        )
        self.assertTrue(
            (
                ROOT
                / "knowledge"
                / "decisions"
                / "0011-record-initial-copyright-ownership.md"
            ).is_file()
        )


class ProfileTests(unittest.TestCase):
    def test_example_module_profile_inherits_all_layers(self) -> None:
        profile = load_profile(
            ROOT
            / "examples"
            / "profiles"
            / "example-project"
            / "example-module"
            / "profile.yaml",
            project_root=ROOT,
        )
        self.assertIn("System", profile["concept_types"])
        self.assertIn("Module", profile["concept_types"])
        self.assertIn("Extension Point", profile["concept_types"])
        self.assertIn("tested-by", profile["relation_kinds"])
        self.assertIn("scope", profile["rules"]["required_project_fields"])

    def test_profile_cannot_weaken_parent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = root / "parent.yaml"
            child = root / "child.yaml"
            parent.write_text(
                """
id: parent
version: "0.1.0"
okf_version: "0.2"
extends: []
concept_types: [System]
relation_kinds: []
rules:
  broken_links: error
  stable_requires_verification: true
type_rules: {}
""".lstrip(),
                encoding="utf-8",
            )
            child.write_text(
                """
id: child
version: "0.1.0"
okf_version: "0.2"
extends: [parent.yaml]
concept_types: []
relation_kinds: []
rules:
  broken_links: warning
type_rules: {}
""".lstrip(),
                encoding="utf-8",
            )
            with self.assertRaises(KnowledgeFormatError):
                load_profile(child, project_root=root)


class KnowledgeInputTests(unittest.TestCase):
    def test_duplicate_keys_are_rejected_in_standalone_yaml(self) -> None:
        cases = {
            "top-level": "id: first\nid: second\n",
            "nested": "outer:\n  id: first\n  id: second\n",
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.yaml"
            for name, content in cases.items():
                with self.subTest(name=name):
                    path.write_text(content, encoding="utf-8")
                    with self.assertRaises(KnowledgeFormatError) as raised:
                        load_yaml(path)
                    message = str(raised.exception)
                    self.assertIn("duplicate key", message.lower())
                    self.assertIn("id", message)

    def test_duplicate_keys_are_rejected_in_markdown_frontmatter(self) -> None:
        cases = {
            "top-level": "type: Reference\ntype: Decision\n",
            "nested": "type: Reference\nextension:\n  id: first\n  id: second\n",
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "concept.md"
            for name, frontmatter in cases.items():
                with self.subTest(name=name):
                    path.write_text(
                        f"---\n{frontmatter}---\n\n# Concept\n",
                        encoding="utf-8",
                    )
                    with self.assertRaises(KnowledgeFormatError) as raised:
                        knowledge_common.parse_markdown(path, root)
                    message = str(raised.exception)
                    self.assertIn("duplicate key", message.lower())
                    expected_key = "type" if name == "top-level" else "id"
                    self.assertIn(expected_key, message)

    def test_duplicate_merge_keys_are_rejected_in_both_yaml_inputs(self) -> None:
        duplicate_merges = """\
base1: &base1
  owner: one
base2: &base2
  owner: two
concept:
  <<: *base1
  <<: *base2
"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            yaml_path = root / "input.yaml"
            markdown_path = root / "concept.md"
            yaml_path.write_text(duplicate_merges, encoding="utf-8")
            markdown_path.write_text(
                f"---\ntype: Reference\n{duplicate_merges}---\n\n# Concept\n",
                encoding="utf-8",
            )

            for name, load in (
                ("standalone-yaml", lambda: load_yaml(yaml_path)),
                (
                    "markdown-frontmatter",
                    lambda: knowledge_common.parse_markdown(markdown_path, root),
                ),
            ):
                with self.subTest(name=name):
                    with self.assertRaises(KnowledgeFormatError) as raised:
                        load()
                    message = str(raised.exception)
                    self.assertIn("duplicate key", message.lower())
                    self.assertIn("<<", message)

    def test_supported_yaml_merge_shapes_remain_unchanged(self) -> None:
        cases = {
            "one-merge": (
                "base: &base\n  owner: one\nconcept:\n  <<: *base\n",
                {"owner": "one"},
            ),
            "one-sequence-merge": (
                "base1: &base1\n  owner: one\n"
                "base2: &base2\n  reviewer: two\n"
                "concept:\n  <<: [*base1, *base2]\n",
                {"owner": "one", "reviewer": "two"},
            ),
            "explicit-override": (
                "base: &base\n  owner: inherited\n"
                "concept:\n  <<: *base\n  owner: explicit\n",
                {"owner": "explicit"},
            ),
            "ordinary-unique": (
                "concept:\n  owner: one\n  reviewer: two\n",
                {"owner": "one", "reviewer": "two"},
            ),
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.yaml"
            for name, (content, expected) in cases.items():
                with self.subTest(name=name):
                    path.write_text(content, encoding="utf-8")
                    self.assertEqual(expected, load_yaml(path)["concept"])

    def test_supported_merge_override_remains_valid_in_frontmatter(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "concept.md"
            path.write_text(
                "---\n"
                "type: Reference\n"
                "base: &base\n"
                "  owner: inherited\n"
                "concept:\n"
                "  <<: *base\n"
                "  owner: explicit\n"
                "---\n\n"
                "# Concept\n",
                encoding="utf-8",
            )
            document = knowledge_common.parse_markdown(path, root)
            self.assertEqual({"owner": "explicit"}, document.metadata["concept"])

    def test_okf_v0_2_consumer_sentinel_preserves_extensions(self) -> None:
        fixture = (
            ROOT / "tests" / "fixtures" / "okf-v0.2" / "minimal-extended-concept.md"
        )
        document = knowledge_common.parse_markdown(fixture, fixture.parent)

        self.assertEqual("Reference", document.metadata["type"])
        self.assertEqual(
            {"by": "human:fixture-owner", "at": "2026-08-24T00:00:00Z"},
            document.metadata["verified"],
        )
        self.assertEqual({"retained": True}, document.metadata["x-fixture-extension"])
        self.assertIn("# Minimal extended concept", document.body)

    def test_okf_v0_2_authority_is_bound_to_an_immutable_revision(self) -> None:
        pinned = (
            "https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/"
            "9a15b13ba996bb713b19e053ea744abee01c2714/okf/SPEC.md"
        )
        paths = (
            ROOT / "knowledge" / "decisions" / "0001-okf-as-canonical-format.md",
            ROOT / "guidance" / "reference" / "tool-selection.md",
            ROOT / "guidance" / "practices" / "established-patterns.md",
        )
        for path in paths:
            with self.subTest(path=path.relative_to(ROOT)):
                content = path.read_text(encoding="utf-8")
                self.assertIn(pinned, content)
                self.assertNotIn("knowledge-catalog/blob/main/okf/SPEC.md", content)


class ProfileReadBoundaryTests(unittest.TestCase):
    """Profile inheritance may not read outside the bound project root.

    `extends` is project-controlled input. Before this boundary existed, a
    profile could name an absolute path, traverse out of the project, or point
    through a symlink, and the parent was read and merged. The canary below is
    the evidence that matters: rejection must happen before the outside file is
    opened, so its bytes reach neither the result nor the diagnostic.
    """

    CANARY = "G3-PROFILE-CANARY-8f31c2"

    def _project(self, directory: str) -> tuple[Path, Path, Path]:
        root = Path(directory)
        project = root / "project"
        (project / ".knowledge").mkdir(parents=True)
        (project / ".knowledge-kit" / "core").mkdir(parents=True)
        (project / ".knowledge-kit" / "core" / "profile.yaml").write_text(
            "id: kit\nversion: '1'\n", encoding="utf-8"
        )
        outside = root / "outside.yaml"
        outside.write_text(f"id: outside\ncanary: {self.CANARY}\n", encoding="utf-8")
        return root, project, outside

    def _assert_refused(self, child: Path, project: Path) -> str:
        with self.assertRaises(KnowledgeFormatError) as raised:
            load_profile(child, project_root=project)
        message = str(raised.exception)
        self.assertNotIn(self.CANARY, message)
        return message

    def _run_cli(self, arguments: list[str]) -> tuple[int, str]:
        output = StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            status = cli_main(arguments)
        return status, output.getvalue()

    def _compatibility_project(self, directory: str) -> tuple[Path, Path, Path]:
        root = Path(directory)
        project = root / "project"
        profile = project / ".knowledge" / "profile.yaml"
        toolkit_profile = project / ".knowledge-kit" / "core" / "profile.yaml"
        toolkit_profile.parent.mkdir(parents=True)
        toolkit_profile.write_bytes((ROOT / "core" / "profile.yaml").read_bytes())
        profile.parent.mkdir(parents=True)
        profile.write_text(
            f"# {self.CANARY}\n"
            "id: compatibility-project\n"
            "extends: ['../.knowledge-kit/core/profile.yaml']\n",
            encoding="utf-8",
        )

        bundle = project / "knowledge"
        for source in (ROOT / "examples" / "generic").rglob("*"):
            target = bundle / source.relative_to(ROOT / "examples" / "generic")
            if source.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read_bytes())
        return project, profile, bundle

    def _compatibility_commands(
        self, profile: Path, bundle: Path, *, project_root: Path | None = None
    ) -> tuple[tuple[str, list[str]], ...]:
        root_arguments = (
            ["--project-root", str(project_root)] if project_root is not None else []
        )
        return (
            (
                "validate",
                [
                    "validate",
                    "--profile",
                    str(profile),
                    "--bundle",
                    str(bundle),
                    *root_arguments,
                ],
            ),
            (
                "context-pack",
                [
                    "context-pack",
                    "--profile",
                    str(profile),
                    "--bundle",
                    str(bundle),
                    "--seed",
                    "example.system.processing",
                    *root_arguments,
                ],
            ),
        )

    def test_programmatic_loader_requires_an_explicit_project_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, project, _ = self._project(directory)
            child = project / ".knowledge" / "profile.yaml"
            child.write_text("id: child\n", encoding="utf-8")
            with self.assertRaises(TypeError):
                load_profile(child)  # type: ignore[call-arg]

    def test_profile_without_a_parent_still_loads(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, project, _ = self._project(directory)
            child = project / ".knowledge" / "profile.yaml"
            child.write_text("id: child\n", encoding="utf-8")
            self.assertEqual("child", load_profile(child, project_root=project)["id"])

    def test_relative_traversal_out_of_the_project_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, project, _ = self._project(directory)
            child = project / ".knowledge" / "profile.yaml"
            child.write_text(
                "id: child\nextends: ['../../outside.yaml']\n", encoding="utf-8"
            )
            self.assertIn("escapes", self._assert_refused(child, project))

    def test_absolute_parent_reference_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, project, outside = self._project(directory)
            child = project / ".knowledge" / "profile.yaml"
            child.write_text(f"id: child\nextends: ['{outside}']\n", encoding="utf-8")
            self.assertIn("must be relative", self._assert_refused(child, project))

    def test_symlinked_parent_leaving_the_project_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, project, outside = self._project(directory)
            link = project / ".knowledge" / "parent.yaml"
            link.symlink_to(outside)
            child = project / ".knowledge" / "profile.yaml"
            child.write_text("id: child\nextends: ['parent.yaml']\n", encoding="utf-8")
            # The reference itself looks in-project; only the canonical target
            # escapes, which is why containment is checked after resolution.
            self.assertIn("escapes", self._assert_refused(child, project))

    def test_outside_file_is_not_opened_even_when_it_is_not_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, project, _ = self._project(directory)
            (root / "notyaml.txt").write_text(
                f"broken: [{self.CANARY}\n", encoding="utf-8"
            )
            child = project / ".knowledge" / "profile.yaml"
            child.write_text(
                "id: child\nextends: ['../../notyaml.txt']\n", encoding="utf-8"
            )
            # A parser error here would prove the file was read.
            self.assertIn("escapes", self._assert_refused(child, project))

    def test_etc_hostname_is_rejected_before_the_parent_is_loaded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, project, _ = self._project(directory)
            child = project / ".knowledge" / "profile.yaml"
            child.write_text(
                "id: child\nextends: ['/etc/hostname']\n", encoding="utf-8"
            )
            loaded: list[Path] = []
            original = knowledge_common.load_yaml

            def observe(path: Path) -> dict[str, object]:
                loaded.append(path)
                return original(path)

            with patch("tools.knowledge_common.load_yaml", side_effect=observe):
                message = self._assert_refused(child, project)
            self.assertIn("must be relative", message)
            self.assertNotIn(Path("/etc/hostname"), loaded)

    def test_profile_outside_the_bound_root_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, project, outside = self._project(directory)
            with self.assertRaises(KnowledgeFormatError) as raised:
                load_profile(outside, project_root=project)
            self.assertIn("outside the project root", str(raised.exception))

    def test_documented_and_module_inheritance_still_load(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, project, _ = self._project(directory)
            (project / "profile.yaml").write_text(
                "id: project\nversion: '1'\n", encoding="utf-8"
            )
            # The documented adopting-project shape: .knowledge reaches the
            # pinned toolkit through `..`, which stays inside the project root.
            child = project / ".knowledge" / "profile.yaml"
            child.write_text(
                "id: child\nextends: ['../.knowledge-kit/core/profile.yaml']\n",
                encoding="utf-8",
            )
            self.assertEqual("child", load_profile(child, project_root=project)["id"])

            module = project / "module"
            module.mkdir()
            module_profile = module / "profile.yaml"
            module_profile.write_text(
                "id: module\nextends: ['../profile.yaml']\n", encoding="utf-8"
            )
            self.assertEqual(
                "module", load_profile(module_profile, project_root=project)["id"]
            )

    def test_in_root_symlink_remains_supported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, project, _ = self._project(directory)
            link = project / ".knowledge" / "pinned.yaml"
            link.symlink_to(project / ".knowledge-kit" / "core" / "profile.yaml")
            child = project / ".knowledge" / "profile.yaml"
            child.write_text("id: child\nextends: ['pinned.yaml']\n", encoding="utf-8")
            # Containment is about where a link lands, not about links as such.
            self.assertEqual("child", load_profile(child, project_root=project)["id"])

    def test_in_root_multi_hop_inheritance_still_loads(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, project, _ = self._project(directory)
            parent = project / "profile.yaml"
            parent.write_text(
                "id: project\nextends: ['.knowledge-kit/core/profile.yaml']\n",
                encoding="utf-8",
            )
            child = project / ".knowledge" / "profile.yaml"
            child.write_text(
                "id: child\nextends: ['../profile.yaml']\n", encoding="utf-8"
            )
            profile = load_profile(child, project_root=project)
            self.assertEqual("child", profile["id"])
            self.assertEqual("1", profile["version"])

    def test_inheritance_cycles_remain_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, project, _ = self._project(directory)
            first = project / ".knowledge" / "a.yaml"
            second = project / ".knowledge" / "b.yaml"
            first.write_text("id: a\nextends: ['b.yaml']\n", encoding="utf-8")
            second.write_text("id: b\nextends: ['a.yaml']\n", encoding="utf-8")
            with self.assertRaises(KnowledgeFormatError) as raised:
                load_profile(first, project_root=project)
            self.assertIn("cycle", str(raised.exception))

    def test_supported_cli_routes_refuse_the_relative_escape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, project, _ = self._project(directory)
            child = project / ".knowledge" / "profile.yaml"
            child.write_text(
                "id: child\nextends: ['../../outside.yaml']\n", encoding="utf-8"
            )
            bundle = project / "knowledge"
            bundle.mkdir()

            source = project / "source"
            (source / "core").mkdir(parents=True)
            (source / "core" / "marker.txt").write_text(
                "runtime source\n", encoding="utf-8"
            )
            lock = project / "kit.lock.yaml"
            lock.write_text(
                f"""
version: 1
toolkit:
  source: source
  revision: test-revision
  public_surface_digest: {public_surface_digest(source)}
  profile: .knowledge/profile.yaml
runtime:
  image: registry.example/kit@sha256:{"a" * 64}
  revision: test-revision
""".lstrip(),
                encoding="utf-8",
            )

            commands = (
                (
                    "validate",
                    [
                        "validate",
                        "--project-root",
                        str(project),
                        "--profile",
                        str(child),
                        "--bundle",
                        str(bundle),
                    ],
                    2,
                ),
                (
                    "context-pack",
                    [
                        "context-pack",
                        "--project-root",
                        str(project),
                        "--profile",
                        str(child),
                        "--bundle",
                        str(bundle),
                        "--seed",
                        "unused",
                    ],
                    2,
                ),
                (
                    "check-runtime",
                    [
                        "check-runtime",
                        "--project-root",
                        str(project),
                        "--lock",
                        str(lock),
                    ],
                    1,
                ),
            )
            for route, command, expected_status in commands:
                with self.subTest(route=route):
                    status, output = self._run_cli(command)
                    self.assertEqual(expected_status, status, output)
                    self.assertIn("escapes", output)
                    self.assertNotIn(self.CANARY, output)

    def test_c0_documented_cwd_uses_the_default_project_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project, profile, bundle = self._compatibility_project(directory)
            previous_cwd = Path.cwd()
            try:
                os.chdir(project)
                for route, command in self._compatibility_commands(profile, bundle):
                    with self.subTest(route=route):
                        status, output = self._run_cli(command)
                        self.assertEqual(0, status, output)
            finally:
                os.chdir(previous_cwd)

    def test_c1_external_cwd_without_a_root_fails_before_profile_read(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, profile, bundle = self._compatibility_project(directory)
            operator_cwd = Path(directory) / "operator-cwd"
            operator_cwd.mkdir()
            loaded: list[Path] = []
            original = knowledge_common.load_yaml

            def observe(path: Path) -> dict[str, object]:
                loaded.append(path)
                return original(path)

            previous_cwd = Path.cwd()
            try:
                os.chdir(operator_cwd)
                with patch("tools.knowledge_common.load_yaml", side_effect=observe):
                    for route, command in self._compatibility_commands(profile, bundle):
                        with self.subTest(route=route):
                            status, output = self._run_cli(command)
                            self.assertEqual(2, status, output)
                            self.assertIn("outside the project root", output)
                            self.assertNotIn(self.CANARY, output)
            finally:
                os.chdir(previous_cwd)
            self.assertEqual([], loaded)

    def test_c2_external_cwd_accepts_an_explicit_project_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project, profile, bundle = self._compatibility_project(directory)
            operator_cwd = Path(directory) / "operator-cwd"
            operator_cwd.mkdir()
            previous_cwd = Path.cwd()
            try:
                os.chdir(operator_cwd)
                for route, command in self._compatibility_commands(
                    profile, bundle, project_root=project
                ):
                    with self.subTest(route=route):
                        status, output = self._run_cli(command)
                        self.assertEqual(0, status, output)
            finally:
                os.chdir(previous_cwd)


class MarkdownReferenceAuthorityTests(unittest.TestCase):
    """Local Markdown validation must not observe outside-root targets."""

    CANARY = "G3-MARKDOWN-TARGET-CANARY-76"

    def _fixture(self, directory: str) -> tuple[Path, Path, Path, Path]:
        sandbox = Path(directory)
        project = sandbox / "project"
        bundle = project / "guidance"
        outside = sandbox / "outside"
        bundle.mkdir(parents=True)
        outside.mkdir()
        source = bundle / "source.md"
        source.write_text("source\n", encoding="utf-8")
        return project, bundle, source, outside

    def _validate_target(
        self,
        project: Path,
        bundle: Path,
        source: Path,
        target: str,
    ) -> tuple[list[Issue], list[tuple[str, Path]], list[Path]]:
        issues: list[Issue] = []
        observations: list[tuple[str, Path]] = []
        content_reads: list[Path] = []
        document = Document(source, source.relative_to(bundle), {}, f"[x]({target})")

        original_lstat = os.lstat
        original_stat = os.stat
        original_readlink = os.readlink
        original_resolve = Path.resolve
        original_read_text = Path.read_text

        def observed_path(value: object) -> Path | None:
            if isinstance(value, int):
                return None
            try:
                return Path(value)  # type: ignore[arg-type]
            except TypeError:
                return None

        def observe_lstat(
            path: object, *args: object, **kwargs: object
        ) -> os.stat_result:
            candidate = observed_path(path)
            if candidate is not None:
                observations.append(("lstat", candidate))
            return original_lstat(path, *args, **kwargs)  # type: ignore[arg-type]

        def observe_stat(
            path: object, *args: object, **kwargs: object
        ) -> os.stat_result:
            candidate = observed_path(path)
            if candidate is not None:
                observations.append(("stat", candidate))
            return original_stat(path, *args, **kwargs)  # type: ignore[arg-type]

        def observe_readlink(path: object, *args: object, **kwargs: object) -> str:
            candidate = observed_path(path)
            if candidate is not None:
                observations.append(("readlink", candidate))
            return original_readlink(path, *args, **kwargs)  # type: ignore[arg-type]

        def observe_resolve(path: Path, *args: object, **kwargs: object) -> Path:
            observations.append(("resolve", path))
            return original_resolve(path, *args, **kwargs)

        def observe_read_text(path: Path, *args: object, **kwargs: object) -> str:
            content_reads.append(path)
            return original_read_text(path, *args, **kwargs)

        with (
            patch("os.lstat", side_effect=observe_lstat),
            patch("os.stat", side_effect=observe_stat),
            patch("os.readlink", side_effect=observe_readlink),
            patch.object(Path, "resolve", autospec=True, side_effect=observe_resolve),
            patch.object(
                Path, "read_text", autospec=True, side_effect=observe_read_text
            ),
        ):
            _validate_links(
                [document],
                bundle,
                "error",
                issues,
                project_root=project,
            )
        return issues, observations, content_reads

    def _assert_only_in_root_observations(
        self, project: Path, observations: list[tuple[str, Path]]
    ) -> None:
        for operation, path in observations:
            with self.subTest(operation=operation, path=path):
                self.assertTrue(path.is_absolute())
                path.relative_to(project)

    def _authority_issue(
        self, target: str, *, source_path: str = "source.md"
    ) -> list[Issue]:
        return [
            Issue(
                "error",
                source_path,
                f"local Markdown link {target!r} escapes project root",
            )
        ]

    def test_outside_lexical_variants_are_indistinguishable_and_unobserved(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project, bundle, source, outside = self._fixture(directory)
            target = "../../outside/probe"
            probe = outside / "probe"

            results = []
            results.append(self._validate_target(project, bundle, source, target))
            probe.write_text(self.CANARY, encoding="utf-8")
            results.append(self._validate_target(project, bundle, source, target))
            probe.unlink()
            probe.mkdir()
            results.append(self._validate_target(project, bundle, source, target))
            (probe / "index.md").write_text(self.CANARY, encoding="utf-8")
            results.append(self._validate_target(project, bundle, source, target))

            expected = self._authority_issue(target)
            for issues, observations, content_reads in results:
                self.assertEqual(expected, issues)
                self.assertEqual([], observations)
                self.assertEqual([], content_reads)

    def test_outside_symlink_target_is_not_observed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project, bundle, source, outside = self._fixture(directory)
            target = "outside-link.md"
            external = outside / "target.md"
            link = bundle / target
            link.symlink_to(external)

            absent = self._validate_target(project, bundle, source, target)
            external.write_text(self.CANARY, encoding="utf-8")
            present = self._validate_target(project, bundle, source, target)

            expected = self._authority_issue(target)
            for issues, observations, content_reads in (absent, present):
                self.assertEqual(expected, issues)
                self._assert_only_in_root_observations(project, observations)
                self.assertIn(("readlink", link), observations)
                self.assertEqual([], content_reads)

    def test_in_project_reference_classes_remain_supported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project, bundle, source, _ = self._fixture(directory)
            peer = bundle / "peer.md"
            peer.write_text("peer\n", encoding="utf-8")
            templates = project / "templates"
            templates.mkdir()
            (templates / "example.md").write_text("example\n", encoding="utf-8")
            (bundle / "peer-link.md").symlink_to(peer)

            controls = {
                "M0": "peer.md",
                "M2": "../templates/example.md",
                "M7": "/peer.md",
                "M8": "https://example.invalid/path",
                "M9": "#section",
                "M10": "peer-link.md",
            }
            for control, target in controls.items():
                with self.subTest(control=control):
                    issues, observations, content_reads = self._validate_target(
                        project, bundle, source, target
                    )
                    self.assertEqual([], issues)
                    self._assert_only_in_root_observations(project, observations)
                    if control in {"M8", "M9"}:
                        self.assertEqual([], observations)
                    self.assertEqual([], content_reads)

            issues, observations, content_reads = self._validate_target(
                project, bundle, source, "missing.md"
            )
            self.assertEqual(
                [Issue("error", "source.md", "broken Markdown link 'missing.md'")],
                issues,
            )
            self._assert_only_in_root_observations(project, observations)
            self.assertEqual([], content_reads)

    def test_in_root_directory_index_is_safely_resolved_twice(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project, bundle, source, outside = self._fixture(directory)
            target = "section"
            section = bundle / target
            section.mkdir()
            index = section / "index.md"
            peer = bundle / "peer.md"
            peer.write_text("peer\n", encoding="utf-8")

            index.write_text("index\n", encoding="utf-8")
            direct = self._validate_target(project, bundle, source, target)
            index.unlink()
            index.symlink_to(peer)
            in_root_link = self._validate_target(project, bundle, source, target)

            for issues, observations, content_reads in (direct, in_root_link):
                self.assertEqual([], issues)
                self._assert_only_in_root_observations(project, observations)
                self.assertEqual([], content_reads)

            index.unlink()
            index.symlink_to(outside / "index.md")
            outside_index = self._validate_target(project, bundle, source, target)
            self.assertEqual(self._authority_issue(target), outside_index[0])
            self._assert_only_in_root_observations(project, outside_index[1])
            self.assertEqual([], outside_index[2])

    def test_local_query_and_fragment_suffixes_keep_existing_cleaning(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project, bundle, source, _ = self._fixture(directory)
            (bundle / "page.md").write_text("page\n", encoding="utf-8")
            for target in (
                "page.md#section",
                "page.md?x=y",
                "page.md?x=y#section",
            ):
                with self.subTest(target=target):
                    issues, observations, content_reads = self._validate_target(
                        project, bundle, source, target
                    )
                    self.assertEqual([], issues)
                    self._assert_only_in_root_observations(project, observations)
                    self.assertEqual([], content_reads)

    def test_supported_validation_route_applies_the_markdown_project_root(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            sandbox = Path(directory)
            project = sandbox / "project"
            bundle = project / "knowledge"
            outside = sandbox / "outside"
            bundle.mkdir(parents=True)
            outside.mkdir()
            profile = project / "profile.yaml"
            profile.write_bytes((ROOT / "core" / "profile.yaml").read_bytes())
            target = "../../outside/probe.md"
            index = bundle / "index.md"
            index.write_text(
                f'---\nokf_version: "0.2"\n---\n\n# Project\n\n[outside]({target})\n',
                encoding="utf-8",
            )

            _, absent = validate_bundle(
                profile,
                bundle,
                ROOT / "schemas",
                project_root=project,
            )
            (outside / "probe.md").write_text(self.CANARY, encoding="utf-8")
            _, present = validate_bundle(
                profile,
                bundle,
                ROOT / "schemas",
                project_root=project,
            )

            expected = self._authority_issue(target, source_path="index.md")
            self.assertEqual(expected, absent)
            self.assertEqual(expected, present)
            self.assertNotIn(self.CANARY, repr(absent))
            self.assertNotIn(self.CANARY, repr(present))


class BundleTests(unittest.TestCase):
    def test_generic_example_is_valid(self) -> None:
        _, issues = validate_bundle(
            ROOT / "core" / "profile.yaml",
            ROOT / "examples" / "generic",
            project_root=ROOT,
        )
        self.assertEqual([], issues)

    def test_example_module_bundle_is_valid(self) -> None:
        _, issues = validate_bundle(
            ROOT
            / "examples"
            / "profiles"
            / "example-project"
            / "example-module"
            / "profile.yaml",
            ROOT / "examples" / "example-project-module",
            project_root=ROOT,
        )
        self.assertEqual([], issues)

    def test_guidance_bundle_is_valid(self) -> None:
        _, issues = validate_bundle(
            ROOT / "guidance" / "profile.yaml",
            ROOT / "guidance",
            project_root=ROOT,
        )
        self.assertEqual([], issues)

    def test_self_knowledge_bundle_is_valid(self) -> None:
        _, issues = validate_bundle(
            ROOT / "knowledge" / "profile.yaml",
            ROOT / "knowledge",
            project_root=ROOT,
        )
        self.assertEqual([], issues)

    def test_stable_concept_requires_human_verifier(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            (bundle / "index.md").write_text(
                '---\nokf_version: "0.2"\n---\n\n# Temporary bundle\n',
                encoding="utf-8",
            )
            (bundle / "project.md").write_text(
                """
---
type: Project
title: Unverified project
description: Stable knowledge without the required human verification.
status: stable
generated:
  by: codex/test
x-project-knowledge:
  id: test.unverified
  owners:
    - team:test
---

# Unverified project
""".lstrip(),
                encoding="utf-8",
            )
            _, issues = validate_bundle(
                ROOT / "core" / "profile.yaml", bundle, project_root=ROOT
            )
            messages = [issue.message for issue in issues]
            self.assertIn("stable concept has no human: verifier", messages)

    def test_context_pack_traverses_project_relations(self) -> None:
        pack = build_pack(
            ROOT
            / "examples"
            / "profiles"
            / "example-project"
            / "example-module"
            / "profile.yaml",
            ROOT / "examples" / "example-project-module",
            ["example.module.sample"],
            depth=2,
            max_tokens=2000,
            project_root=ROOT,
        )
        self.assertIn("Example module", pack)
        self.assertIn("Example extension point", pack)
        self.assertIn("Example module contract", pack)
        self.assertIn("derived orientation only", pack)

    def test_guidance_context_pack_excludes_toolkit_self_knowledge(self) -> None:
        pack = build_pack(
            ROOT / "guidance" / "profile.yaml",
            ROOT / "guidance",
            ["guidance.workflow.bootstrap-new-project"],
            depth=1,
            max_tokens=800,
            project_root=ROOT,
        )
        self.assertIn("Bootstrap a new project", pack)
        self.assertIn("derived orientation only", pack)
        self.assertNotIn("kit.project", pack)
        self.assertLessEqual(len(pack), 3400)


class GuardrailTests(unittest.TestCase):
    def test_guardrail_coverage_manifest_is_valid(self) -> None:
        issues = check_guardrails(
            ROOT / "policy" / "guardrails.yaml",
            ROOT,
        )
        self.assertEqual([], issues)

    def test_public_profile_does_not_inherit_self_knowledge(self) -> None:
        profile = load_yaml(ROOT / "core" / "profile.yaml")
        self.assertEqual([], profile["extends"])
        self.assertNotIn("knowledge/", (ROOT / "core" / "profile.yaml").read_text())

    def test_public_change_control_does_not_inherit_gnostoa_self_policy(
        self,
    ) -> None:
        template = load_yaml(ROOT / "templates" / "change-control.project.yaml")
        example = load_yaml(
            ROOT / "examples" / "profiles" / "example-project" / "change-control.yaml"
        )
        self.assertEqual(
            ["../.knowledge-kit/core/change-control.yaml"],
            template["extends"],
        )
        self.assertEqual(
            ["../../../core/change-control.yaml"],
            example["extends"],
        )
        boundary = (
            ROOT / "knowledge" / "contracts" / "public-inheritance-surface.md"
        ).read_text(encoding="utf-8")
        self.assertIn("`policy/`", boundary)
        self.assertIn("outside", boundary)

    def test_project_agent_router_is_bounded(self) -> None:
        router = (ROOT / "templates" / "AGENTS.project.md").read_text(encoding="utf-8")
        self.assertIn("Do not load", router)
        self.assertIn(".knowledge-kit/knowledge/", router)
        self.assertLessEqual(len(router.splitlines()), 24)


class ChangeControlTests(unittest.TestCase):
    def test_generic_baseline_has_protected_change_flow(self) -> None:
        self.assertEqual(
            [],
            check_change_policy(ROOT / "core" / "change-control.yaml"),
        )
        policy = load_change_policy(ROOT / "core" / "change-control.yaml")
        integration = policy["integration"]
        self.assertTrue(integration["protected_default_branch"])
        self.assertTrue(integration["change_request_required"])
        self.assertTrue(integration["required_checks"])
        self.assertTrue(integration["resolved_conversations"])
        self.assertFalse(integration["direct_push"])
        self.assertFalse(integration["force_push"])
        self.assertFalse(integration["branch_deletion"])
        self.assertEqual(168, policy["branches"]["target_lifetime_hours"])

    def test_generic_baseline_is_practical_for_solo_and_community_projects(
        self,
    ) -> None:
        generic = load_change_policy(ROOT / "core" / "change-control.yaml")
        for class_id in ("mechanical", "normal", "normative", "critical"):
            change_class = generic["change_classes"][class_id]
            self.assertEqual(0, change_class["minimum_approvals"], class_id)
            self.assertFalse(change_class["independent_approval"], class_id)
            self.assertFalse(change_class["code_owner_approval"], class_id)
            self.assertFalse(change_class["human_approval"], class_id)

        for class_id in ("normal", "normative", "critical"):
            self.assertEqual(
                "optional",
                generic["change_classes"][class_id]["work_item"],
                class_id,
            )
            self.assertFalse(
                generic["change_classes"][class_id]["decision_record"],
                class_id,
            )
            self.assertEqual(
                "before-merge",
                generic["change_classes"][class_id]["verification"]["evidence_timing"],
                class_id,
            )
            self.assertEqual(
                "when-applicable",
                generic["change_classes"][class_id]["verification"]["failing_evidence"],
                class_id,
            )

        guidance = (
            ROOT / "guidance" / "reference" / "change-classification-and-approval.md"
        ).read_text(encoding="utf-8")
        self.assertIn("solo maintainer", guidance)
        self.assertIn("formal approval", guidance)
        self.assertIn("cooling-off period", guidance)
        self.assertIn("owner attestation", guidance)

        example = load_change_policy(
            ROOT / "examples" / "profiles" / "example-project" / "change-control.yaml"
        )
        self.assertEqual(
            1,
            example["change_classes"]["critical"]["minimum_approvals"],
        )

    def test_gnostoa_self_policy_requires_durable_context_and_test_first(
        self,
    ) -> None:
        self.assertEqual(
            [],
            check_change_policy(ROOT / "policy" / "change-control.yaml"),
        )
        policy = load_change_policy(ROOT / "policy" / "change-control.yaml")

        mechanical = policy["change_classes"]["mechanical"]
        self.assertEqual("optional", mechanical["work_item"])
        self.assertFalse(mechanical["decision_record"])
        self.assertEqual(
            "before-merge",
            mechanical["verification"]["evidence_timing"],
        )

        failing_evidence = {
            "normal": "when-applicable",
            "normative": "required",
            "critical": "required",
        }
        for class_id, expected_failure in failing_evidence.items():
            change_class = policy["change_classes"][class_id]
            self.assertEqual("required", change_class["work_item"], class_id)
            self.assertTrue(change_class["decision_record"], class_id)
            self.assertEqual(
                "before-implementation",
                change_class["verification"]["evidence_timing"],
                class_id,
            )
            self.assertEqual(
                expected_failure,
                change_class["verification"]["failing_evidence"],
                class_id,
            )
            self.assertEqual(0, change_class["minimum_approvals"], class_id)

        emergency = policy["change_classes"]["emergency"]
        self.assertEqual("required-follow-up", emergency["work_item"])
        self.assertTrue(emergency["decision_record"])
        self.assertEqual(
            "post-event",
            emergency["verification"]["evidence_timing"],
        )

    def test_change_policy_cannot_weaken_parent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            child = Path(directory) / "child.yaml"
            child.write_text(
                f"""
id: weakening-child
version: "0.1.0"
extends:
  - {str((ROOT / "core" / "change-control.yaml").resolve())!r}
integration:
  direct_push: true
change_classes:
  critical:
    minimum_approvals: 1
""".lstrip(),
                encoding="utf-8",
            )
            with self.assertRaises(KnowledgeFormatError):
                load_change_policy(child)

    def test_change_policy_has_one_unambiguous_parent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            child = Path(directory) / "child.yaml"
            parent = (ROOT / "core" / "change-control.yaml").resolve()
            child.write_text(
                f"""
id: ambiguous-child
version: "0.1.0"
extends:
  - {str(parent)!r}
  - {str(parent)!r}
""".lstrip(),
                encoding="utf-8",
            )
            with self.assertRaises(KnowledgeFormatError):
                load_change_policy(child)

    def test_agents_cannot_approve_or_bypass(self) -> None:
        policy = load_change_policy(ROOT / "core" / "change-control.yaml")
        self.assertTrue(policy["agents"]["may_author_changes"])
        self.assertFalse(policy["agents"]["may_approve_own_change"])
        self.assertFalse(policy["agents"]["may_bypass_controls"])
        self.assertFalse(
            policy["agents"]["may_promote_stable_without_human"],
        )
        for class_id in ("normal", "normative", "critical"):
            change_class = policy["change_classes"][class_id]
            self.assertFalse(change_class["human_approval"], class_id)
            self.assertTrue(
                change_class["verification"]["human_semantic_verification"],
                class_id,
            )

    def test_required_approval_cannot_be_nonhuman_or_nonindependent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            child = Path(directory) / "child.yaml"
            parent = (ROOT / "core" / "change-control.yaml").resolve()
            child.write_text(
                f"""
id: invalid-approval-child
version: "0.1.0"
owner: team:test
extends:
  - {str(parent)!r}
change_classes:
  mechanical:
    minimum_approvals: 1
    auto_merge: false
""".lstrip(),
                encoding="utf-8",
            )
            issues = check_change_policy(child)
            self.assertTrue(
                any("independent_approval" in issue for issue in issues),
                issues,
            )
            self.assertTrue(
                any("human_approval" in issue for issue in issues),
                issues,
            )

    def test_generic_policy_requires_verification_first_evidence(self) -> None:
        policy = load_change_policy(ROOT / "core" / "change-control.yaml")
        verification = policy["verification"]
        self.assertTrue(verification["expected_behavior_required"])
        self.assertTrue(verification["observable_behavior_over_implementation_details"])
        self.assertTrue(verification["deterministic_required_tests"])
        self.assertTrue(verification["flaky_required_tests_block"])
        self.assertFalse(verification["coverage_alone_sufficient"])
        self.assertLessEqual(
            verification["fast_feedback_target_minutes"],
            10,
        )

        expected = {
            "mechanical": (
                "existing-evidence",
                "optional",
                "before-merge",
                False,
            ),
            "normal": (
                "when-automatable",
                "when-applicable",
                "before-merge",
                True,
            ),
            "normative": (
                "when-automatable",
                "when-applicable",
                "before-merge",
                True,
            ),
            "critical": (
                "required",
                "when-applicable",
                "before-merge",
                True,
            ),
            "emergency": (
                "required",
                "required-follow-up",
                "post-event",
                True,
            ),
        }
        for class_id, values in expected.items():
            evidence = policy["change_classes"][class_id]["verification"]
            self.assertEqual(values[0], evidence["automated_test"])
            self.assertEqual(values[1], evidence["failing_evidence"])
            self.assertEqual(values[2], evidence["evidence_timing"])
            self.assertEqual(values[3], evidence["human_semantic_verification"])

    def test_verification_policy_cannot_weaken_parent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            child = Path(directory) / "child.yaml"
            parent = (ROOT / "core" / "change-control.yaml").resolve()
            child.write_text(
                f"""
id: weakening-verification-child
version: "0.1.0"
owner: team:test
extends:
  - {str(parent)!r}
verification:
  deterministic_required_tests: false
  flaky_required_tests_block: false
  coverage_alone_sufficient: true
  fast_feedback_target_minutes: 60
change_classes:
  critical:
    verification:
      automated_test: existing-evidence
      failing_evidence: optional
      evidence_timing: before-merge
      human_semantic_verification: false
""".lstrip(),
                encoding="utf-8",
            )
            with self.assertRaises(KnowledgeFormatError):
                load_change_policy(child)

    def test_change_request_captures_proportionate_evidence(self) -> None:
        template = (ROOT / "templates" / "change-request.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Expected behavior", template)
        self.assertIn("Evidence available before merge", template)
        self.assertIn("Verification strategy", template)
        self.assertNotIn("Test-first exception", template)

    def test_verification_first_guidance_and_self_route_are_complete(self) -> None:
        workflow = (
            ROOT / "guidance" / "workflows" / "develop-verification-first.md"
        ).read_text(encoding="utf-8")
        reference = (
            ROOT / "guidance" / "reference" / "testing-and-verification-strategy.md"
        ).read_text(encoding="utf-8")
        guidance_index = (ROOT / "guidance" / "index.md").read_text(encoding="utf-8")
        runbook = (ROOT / "knowledge" / "runbooks" / "maintain-the-kit.md").read_text(
            encoding="utf-8"
        )
        plan = (ROOT / "templates" / "verification-plan.md").read_text(encoding="utf-8")

        self.assertIn("Red", workflow)
        self.assertIn("green", workflow.lower())
        self.assertIn("characterization", workflow)
        self.assertIn("non-executable", workflow)
        self.assertIn("observable behavior", reference)
        self.assertIn("coverage", reference)
        self.assertIn("flaky", reference)
        self.assertIn("develop-verification-first.md", guidance_index)
        self.assertIn("reproducer before the fix", runbook)
        self.assertIn("characterization", runbook)
        self.assertIn("Expected behavior", plan)
        self.assertIn("Final evidence required before merge", plan)


class ContinuousIntegrationTests(unittest.TestCase):
    def test_python_compatibility_gates_regression_fail_closed(self) -> None:
        workflow = load_yaml(ROOT / ".github" / "workflows" / "verification.yml")
        jobs = workflow["jobs"]
        compatibility = jobs["python-compatibility"]
        regression = jobs["regression"]

        self.assertEqual(
            ["3.11", "3.12"],
            compatibility["strategy"]["matrix"]["python-version"],
        )
        self.assertEqual(
            ["policy", "fast", "python-compatibility"], regression["needs"]
        )
        condition = regression["if"]
        self.assertIn("always()", condition)
        self.assertIn("github.event_name != 'push'", condition)
        self.assertIn("github.ref == 'refs/heads/main'", condition)

        assertions = [
            step
            for step in regression["steps"]
            if step.get("name") == "Assert successful prerequisites"
        ]
        self.assertEqual(1, len(assertions), assertions)
        assertion = assertions[0]
        self.assertEqual(
            {
                "POLICY_RESULT": "${{ needs.policy.result }}",
                "FAST_RESULT": "${{ needs.fast.result }}",
                "PYTHON_COMPATIBILITY_RESULT": "${{ needs.python-compatibility.result }}",
            },
            assertion["env"],
        )
        for result in (
            "POLICY_RESULT",
            "FAST_RESULT",
            "PYTHON_COMPATIBILITY_RESULT",
        ):
            self.assertIn(f'test "${{{result}}}" = success', assertion["run"])

    def test_generic_ci_policy_is_authoritative_and_tiered(self) -> None:
        module = importlib.import_module("tools.check_ci_policy")
        policy = module.load_ci_policy(ROOT / "core" / "continuous-integration.yaml")

        self.assertTrue(policy["authority"]["centralized_ci_required"])
        self.assertTrue(policy["authority"]["required_checks_authoritative"])
        self.assertTrue(policy["authority"]["latest_revision_required"])
        self.assertTrue(policy["security"]["immutable_dependencies"])
        self.assertTrue(policy["security"]["least_privilege"])
        self.assertTrue(policy["security"]["untrusted_changes_no_secrets"])
        self.assertFalse(policy["local_feedback"]["hooks_authoritative"])
        self.assertTrue(policy["local_feedback"]["shared_commands_required"])
        self.assertLessEqual(policy["feedback"]["fast_max_minutes"], 10)

        events = policy["events"]
        self.assertEqual("required", events["change_request"]["gate"])
        self.assertEqual("required", events["merge_candidate"]["gate"])
        self.assertEqual("restore-green", events["integration"]["gate"])
        self.assertIn("fast", events["branch_revision"]["required_suites"])
        self.assertIn("regression", events["change_request"]["required_suites"])
        self.assertIn("regression", events["merge_candidate"]["required_suites"])
        self.assertEqual("when-deployable", events["release"]["activation"])
        self.assertTrue(policy["delivery"]["promote_same_artifact"])
        self.assertFalse(policy["delivery"]["rebuild_between_environments"])

    def test_ci_policy_cannot_weaken_parent(self) -> None:
        module = importlib.import_module("tools.check_ci_policy")
        with tempfile.TemporaryDirectory() as directory:
            child = Path(directory) / "child.yaml"
            parent = (ROOT / "core" / "continuous-integration.yaml").resolve()
            child.write_text(
                f"""
id: weakening-ci-child
version: "0.1.0"
owner: team:test
extends:
  - {str(parent)!r}
authority:
  centralized_ci_required: false
  latest_revision_required: false
local_feedback:
  hooks_authoritative: true
feedback:
  fast_max_minutes: 60
events:
  change_request:
    required_suites: [policy]
""".lstrip(),
                encoding="utf-8",
            )
            with self.assertRaises(KnowledgeFormatError):
                module.load_ci_policy(child)

    def test_ci_policy_preserves_event_cancellation_semantics(self) -> None:
        module = importlib.import_module("tools.check_ci_policy")
        parent = (ROOT / "core" / "continuous-integration.yaml").resolve()
        cases = (
            ("branch_revision", False),
            ("integration", True),
            ("release", True),
        )
        with tempfile.TemporaryDirectory() as directory:
            child = Path(directory) / "child.yaml"
            for event_id, cancel_superseded in cases:
                with self.subTest(event_id=event_id):
                    child.write_text(
                        f"""
id: cancellation-changing-ci-child
version: "0.1.0"
owner: team:test
extends:
  - {str(parent)!r}
events:
  {event_id}:
    cancel_superseded: {str(cancel_superseded).lower()}
""".lstrip(),
                        encoding="utf-8",
                    )
                    with self.assertRaisesRegex(
                        KnowledgeFormatError,
                        "changes inherited event cancellation semantics",
                    ):
                        module.load_ci_policy(child)

    def test_toolkit_verification_manifest_covers_declared_capabilities(self) -> None:
        module = importlib.import_module("tools.check_ci_policy")
        issues = module.check_ci_policy(
            ROOT / "policy" / "continuous-integration.yaml",
            ROOT / "policy" / "verification.yaml",
        )
        self.assertEqual([], issues)

    def test_verification_manifest_uses_one_pinned_runtime(self) -> None:
        toolkit = load_yaml(ROOT / "policy" / "verification.yaml")
        template = load_yaml(ROOT / "templates" / "verification.project.yaml")

        self.assertEqual("toolkit", toolkit["runtime"]["mode"])
        self.assertNotIn("image", toolkit["runtime"])
        self.assertEqual("project", template["runtime"]["mode"])
        self.assertRegex(
            template["runtime"]["image"],
            r"@sha256:[a-f0-9]{64}$",
        )
        for suite in (*toolkit["suites"].values(), *template["suites"].values()):
            self.assertNotIn("runtime", suite)
            self.assertNotIn("image", suite)

    def test_manifest_runtime_must_match_ci_runtime(self) -> None:
        module = importlib.import_module("tools.check_ci_policy")
        locked = "registry.example.org/example-ci@sha256:" + ("a" * 64)
        executing = "registry.example.org/example-ci@sha256:" + ("b" * 64)
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "verification.yaml"
            manifest.write_text(
                f"""
id: runtime-drift-verification
version: "0.1.0"
owner: team:test
policy: {str((ROOT / "core" / "continuous-integration.yaml").resolve())!r}
runtime:
  mode: project
  image: {locked}
capabilities:
  integration: false
  smoke: false
  extended: false
  deployable_artifact: false
suites:
  fast:
    command: ["./ci/verify", fast]
    timeout_minutes: 5
    evidence: [test-report]
  regression:
    command: ["./ci/verify", regression]
    timeout_minutes: 10
    evidence: [test-report]
""".lstrip(),
                encoding="utf-8",
            )
            issues = module.check_ci_policy(
                ROOT / "core" / "continuous-integration.yaml",
                manifest,
                expected_runtime_image=executing,
            )
            self.assertTrue(
                any(
                    "does not match executing project runtime" in issue
                    for issue in issues
                ),
                issues,
            )

    def test_missing_required_suite_is_rejected(self) -> None:
        module = importlib.import_module("tools.check_ci_policy")
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "verification.yaml"
            manifest.write_text(
                """
id: incomplete-verification
version: "0.1.0"
owner: team:test
policy: continuous-integration.yaml
runtime:
  mode: toolkit
capabilities:
  integration: false
  smoke: false
  extended: false
  deployable_artifact: false
suites:
  fast:
    command: [project-verify, fast]
    timeout_minutes: 5
""".lstrip(),
                encoding="utf-8",
            )
            issues = module.check_ci_policy(
                ROOT / "core" / "continuous-integration.yaml",
                manifest,
            )
            self.assertTrue(
                any("regression" in issue for issue in issues),
                issues,
            )
            self.assertTrue(
                any("shared command" in issue for issue in issues),
                issues,
            )

    def test_provider_adapters_cover_candidate_and_integration_events(self) -> None:
        github = (ROOT / "ci" / "github-actions.yml").read_text(encoding="utf-8")
        gitlab = (ROOT / "ci" / "gitlab-ci.yml").read_text(encoding="utf-8")
        toolkit_gitlab = (ROOT / ".gitlab-ci.yml").read_text(encoding="utf-8")

        self.assertIn("pull_request:", github)
        self.assertIn("merge_group:", github)
        self.assertIn("push:", github)
        self.assertIn("concurrency:", github)
        self.assertIn("cancel-in-progress:", github)
        self.assertIn(
            "github.event.pull_request.number || github.ref",
            github,
        )
        self.assertIn(
            "if: github.event_name != 'push' || github.ref == 'refs/heads/main'",
            github,
        )
        self.assertIn("check-ci-policy", github)
        self.assertIn("./ci/verify fast", github)
        self.assertIn("./ci/verify regression", github)
        self.assertRegex(
            github,
            r"actions/checkout@[a-f0-9]{40}",
        )
        self.assertEqual(
            github.count("actions/checkout@"),
            github.count("persist-credentials: false"),
        )

        self.assertIn("merge_request_event", gitlab)
        self.assertIn("check-ci-policy", gitlab)
        self.assertIn("./ci/verify fast", gitlab)
        self.assertIn("./ci/verify regression", gitlab)
        self.assertIn("./ci/verify policy", toolkit_gitlab)
        self.assertIn("./ci/verify fast", toolkit_gitlab)
        self.assertIn("./ci/verify regression", toolkit_gitlab)
        self.assertIn("./ci/verify smoke", toolkit_gitlab)

    def test_repository_hooks_are_advisory_shared_command_adapters(self) -> None:
        pre_commit = (ROOT / ".githooks" / "pre-commit").read_text(encoding="utf-8")
        pre_push = (ROOT / ".githooks" / "pre-push").read_text(encoding="utf-8")
        guidance = (
            ROOT / "guidance" / "patterns" / "tiered-ci-and-local-feedback.md"
        ).read_text(encoding="utf-8")

        self.assertIn("./ci/verify fast", pre_commit)
        self.assertIn("./ci/verify fast", pre_push)
        self.assertIn("advisory", guidance)
        self.assertIn("authoritative", guidance)
        self.assertIn("core.hooksPath", guidance)

    def test_cli_exposes_ci_policy_validation(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(0, cli_main(["--help"]))
        self.assertIn("check-ci-policy", output.getvalue())


class RuntimeTests(unittest.TestCase):
    def test_source_checkout_is_the_default_toolkit_root(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(ROOT, knowledge_common.toolkit_root())

    def test_native_distribution_requires_explicit_public_source_binding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            installed_module = (
                Path(directory) / "site-packages" / "tools" / "knowledge_common.py"
            )
            with (
                patch.dict(os.environ, {}, clear=True),
                patch.object(
                    knowledge_common,
                    "__file__",
                    str(installed_module),
                ),
            ):
                with self.assertRaisesRegex(
                    KnowledgeFormatError,
                    "KNOWLEDGE_KIT_ROOT.*pinned Gnostoa public-source root",
                ):
                    knowledge_common.toolkit_root()

    def test_explicit_public_source_binding_rejects_wrong_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(
                os.environ,
                {"KNOWLEDGE_KIT_ROOT": directory},
                clear=True,
            ):
                with self.assertRaisesRegex(
                    KnowledgeFormatError,
                    "does not identify a Gnostoa public-source root",
                ):
                    knowledge_common.toolkit_root()

    def test_native_cli_reports_source_binding_error_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            commands = (
                [
                    "validate",
                    "--profile",
                    str(ROOT / "core" / "profile.yaml"),
                    "--bundle",
                    str(ROOT / "examples" / "generic"),
                ],
                ["self-check"],
                ["docs-build", "--site-dir", str(Path(directory) / "site")],
                ["check-guardrails"],
                ["check-change-policy"],
                ["check-ci-policy"],
            )
            for command in commands:
                with self.subTest(command=command):
                    output = StringIO()
                    with (
                        patch.dict(
                            os.environ,
                            {"KNOWLEDGE_KIT_ROOT": directory},
                            clear=True,
                        ),
                        redirect_stderr(output),
                    ):
                        self.assertEqual(2, cli_main(command))
                    message = output.getvalue()
                    self.assertIn("KNOWLEDGE_KIT_ROOT", message)
                    self.assertNotIn("Traceback", message)

    def test_release_smoke_rejects_nonempty_artifact_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "artifacts"
            output.mkdir()
            (output / "existing.txt").write_text("keep\n", encoding="utf-8")
            with self.assertRaisesRegex(
                ReleaseSmokeError,
                "artifact output directory is not empty",
            ):
                release_smoke(ROOT, output)

    def test_execution_wheel_must_not_duplicate_canonical_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            wheel = Path(directory) / "gnostoa-test.whl"
            with zipfile.ZipFile(wheel, "w") as archive:
                archive.writestr("tools/cli.py", "")
                archive.writestr("schemas/profile.schema.json", "{}")
            self.assertEqual(
                ["schemas/profile.schema.json"],
                wheel_canonical_payloads(wheel),
            )

    def test_distribution_archives_match_declared_project_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            wheel, source_distribution = _release_archive_fixtures(Path(directory))
            self.assertEqual(
                [],
                distribution_metadata_issues(ROOT, wheel, source_distribution),
            )

    def test_distribution_metadata_rejects_version_and_notice_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            wheel, source_distribution = _release_archive_fixtures(
                Path(directory),
                version="9.9.9",
                include_notice=False,
            )
            issues = distribution_metadata_issues(ROOT, wheel, source_distribution)
            self.assertTrue(any("version" in issue.casefold() for issue in issues))
            self.assertTrue(any("NOTICE" in issue for issue in issues))

    def test_release_evidence_manifest_is_deterministic_and_path_neutral(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wheel = root / "gnostoa-0.1.0-py3-none-any.whl"
            source_distribution = root / "gnostoa-0.1.0.tar.gz"
            wheel.write_bytes(b"wheel")
            source_distribution.write_bytes(b"source distribution")
            results = [
                ArtifactResult(
                    artifact=wheel,
                    kind="wheel",
                    digest="1" * 64,
                    size_bytes=5,
                    metadata_digest="2" * 64,
                    validation="validation\n",
                    context_pack="context pack\n",
                    surface_digest="sha256:" + "3" * 64 + "\n",
                ),
                ArtifactResult(
                    artifact=source_distribution,
                    kind="sdist",
                    digest="4" * 64,
                    size_bytes=19,
                    metadata_digest="5" * 64,
                    validation="validation\n",
                    context_pack="context pack\n",
                    surface_digest="sha256:" + "3" * 64 + "\n",
                ),
            ]
            revision = "6" * 40
            first = release_evidence_manifest(ROOT, results, revision)
            second = release_evidence_manifest(ROOT, list(reversed(results)), revision)
            self.assertEqual(first, second)
            self.assertEqual("gnostoa-release-evidence/v1", first["format"])
            self.assertEqual(revision, first["source"]["revision"])
            self.assertEqual(
                [wheel.name, source_distribution.name],
                [artifact["filename"] for artifact in first["artifacts"]],
            )
            self.assertNotIn(directory, json.dumps(first, sort_keys=True))

            manifest = root / "release-evidence.json"
            write_release_evidence_manifest(manifest, first)
            written = manifest.read_text(encoding="utf-8")
            self.assertTrue(written.endswith("\n"))
            self.assertEqual(first, json.loads(written))

    def test_release_evidence_manifest_requires_exact_source_revision(self) -> None:
        with self.assertRaisesRegex(ReleaseSmokeError, "source revision"):
            release_evidence_manifest(ROOT, [], "main")

    def test_release_source_must_match_head_and_be_clean(self) -> None:
        revision = "a" * 40

        def completed(output: str) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(
                args=[], returncode=0, stdout=output, stderr=""
            )

        with patch("tools.release_smoke._run") as run:
            run.side_effect = [completed(revision + "\n"), completed("")]
            verify_release_source(ROOT, revision)

        with patch("tools.release_smoke._run") as run:
            run.return_value = completed("b" * 40 + "\n")
            with self.assertRaisesRegex(ReleaseSmokeError, "does not match HEAD"):
                verify_release_source(ROOT, revision)

        with patch("tools.release_smoke._run") as run:
            run.side_effect = [
                completed(revision + "\n"),
                completed(" M tools/release_smoke.py\n"),
            ]
            with self.assertRaisesRegex(ReleaseSmokeError, "clean source tree"):
                verify_release_source(ROOT, revision)

    def test_release_build_frontend_and_backend_are_pinned(self) -> None:
        development_lock = (ROOT / "requirements" / "development.lock").read_text(
            encoding="utf-8"
        )
        self.assertIn("build==1.5.0", development_lock)
        self.assertIn("pyproject-hooks==1.2.0", development_lock)
        self.assertIn("setuptools==83.0.0", development_lock)

    def test_runtime_lock_requires_pinned_public_surface_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source" / "core").mkdir(parents=True)
            (root / "source" / "core" / "marker.txt").write_text(
                "same surface\n",
                encoding="utf-8",
            )
            (root / "profile.yaml").write_text(
                """
id: test-profile
version: "0.1.0"
okf_version: "0.2"
extends: []
concept_types: [Project]
relation_kinds: []
rules: {}
type_rules: {}
""".lstrip(),
                encoding="utf-8",
            )
            lock = root / "kit.lock.yaml"
            lock.write_text(
                f"""
version: 1
toolkit:
  source: source
  revision: fabricated-revision
  profile: profile.yaml
runtime:
  image: registry.example/kit@sha256:{"a" * 64}
  revision: fabricated-revision
""".lstrip(),
                encoding="utf-8",
            )
            issues = check_runtime_lock(
                lock,
                root,
                runtime_root=root / "source",
            )
            self.assertTrue(
                any("public_surface_digest" in issue for issue in issues),
                issues,
            )

    def test_runtime_lock_accepts_matching_revisions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source" / "core").mkdir(parents=True)
            (root / "source" / "core" / "marker.txt").write_text(
                "same surface\n",
                encoding="utf-8",
            )
            (root / "profile.yaml").write_text(
                """
id: test-profile
version: "0.1.0"
okf_version: "0.2"
extends: []
concept_types: [Project]
relation_kinds: []
rules: {}
type_rules: {}
""".lstrip(),
                encoding="utf-8",
            )
            lock = root / "kit.lock.yaml"
            surface_digest = public_surface_digest(root / "source")
            lock.write_text(
                f"""
version: 1
toolkit:
  source: source
  revision: revision-1
  public_surface_digest: {surface_digest}
  profile: profile.yaml
runtime:
  image: registry.example/kit@sha256:{"a" * 64}
  revision: revision-1
""".lstrip(),
                encoding="utf-8",
            )
            issues = check_runtime_lock(
                lock,
                root,
                expected_revision="revision-1",
                expected_image=f"registry.example/kit@sha256:{'a' * 64}",
                runtime_root=root / "source",
            )
            self.assertEqual([], issues)

    def test_runtime_lock_rejects_image_revision_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source" / "core").mkdir(parents=True)
            (root / "source" / "core" / "marker.txt").write_text(
                "same surface\n",
                encoding="utf-8",
            )
            (root / "profile.yaml").write_text(
                """
id: test-profile
version: "0.1.0"
okf_version: "0.2"
extends: []
concept_types: [Project]
relation_kinds: []
rules: {}
type_rules: {}
""".lstrip(),
                encoding="utf-8",
            )
            lock = root / "kit.lock.yaml"
            surface_digest = public_surface_digest(root / "source")
            lock.write_text(
                f"""
version: 1
toolkit:
  source: source
  revision: revision-1
  public_surface_digest: {surface_digest}
  profile: profile.yaml
runtime:
  image: registry.example/kit@sha256:{"b" * 64}
  revision: revision-2
""".lstrip(),
                encoding="utf-8",
            )
            issues = check_runtime_lock(
                lock,
                root,
                expected_revision="revision-3",
                expected_image=f"registry.example/kit@sha256:{'d' * 64}",
                runtime_root=root / "source",
            )
            self.assertTrue(
                any("do not match" in issue for issue in issues),
                issues,
            )
            self.assertTrue(
                any("executing image revision" in issue for issue in issues),
                issues,
            )
            self.assertTrue(
                any("executing image reference" in issue for issue in issues),
                issues,
            )

    def test_runtime_lock_rejects_public_surface_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            runtime = root / "runtime"
            (source / "core").mkdir(parents=True)
            (runtime / "core").mkdir(parents=True)
            (source / "core" / "marker.txt").write_text(
                "source\n",
                encoding="utf-8",
            )
            (runtime / "core" / "marker.txt").write_text(
                "runtime\n",
                encoding="utf-8",
            )
            (root / "profile.yaml").write_text(
                """
id: test-profile
version: "0.1.0"
okf_version: "0.2"
extends: []
concept_types: [Project]
relation_kinds: []
rules: {}
type_rules: {}
""".lstrip(),
                encoding="utf-8",
            )
            lock = root / "kit.lock.yaml"
            surface_digest = public_surface_digest(source)
            lock.write_text(
                f"""
version: 1
toolkit:
  source: source
  revision: revision-1
  public_surface_digest: {surface_digest}
  profile: profile.yaml
runtime:
  image: registry.example/kit@sha256:{"c" * 64}
  revision: revision-1
""".lstrip(),
                encoding="utf-8",
            )
            issues = check_runtime_lock(
                lock,
                root,
                expected_revision="revision-1",
                expected_image=f"registry.example/kit@sha256:{'c' * 64}",
                runtime_root=runtime,
            )
            self.assertTrue(
                any("public surface does not match" in issue for issue in issues),
                issues,
            )

    def test_runtime_lock_rejects_locked_source_digest_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            (source / "core").mkdir(parents=True)
            (source / "core" / "marker.txt").write_text(
                "current surface\n",
                encoding="utf-8",
            )
            (root / "profile.yaml").write_text(
                """
id: test-profile
version: "0.1.0"
okf_version: "0.2"
extends: []
concept_types: [Project]
relation_kinds: []
rules: {}
type_rules: {}
""".lstrip(),
                encoding="utf-8",
            )
            lock = root / "kit.lock.yaml"
            lock.write_text(
                f"""
version: 1
toolkit:
  source: source
  revision: revision-1
  public_surface_digest: sha256:{"0" * 64}
  profile: profile.yaml
runtime:
  image: registry.example/kit@sha256:{"d" * 64}
  revision: revision-1
""".lstrip(),
                encoding="utf-8",
            )
            issues = check_runtime_lock(
                lock,
                root,
                runtime_root=source,
            )
            self.assertTrue(
                any("does not match locked digest" in issue for issue in issues),
                issues,
            )

    def test_runtime_image_contract_is_pinned_and_non_root(self) -> None:
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertRegex(
            dockerfile.splitlines()[0],
            r"dockerfile:1@sha256:[a-f0-9]{64}",
        )
        self.assertRegex(
            dockerfile,
            r"python:3\.12-slim@sha256:[a-f0-9]{64}",
        )
        self.assertIn("FROM base AS runtime", dockerfile)
        self.assertIn("USER kit", dockerfile)
        self.assertIn('ENTRYPOINT ["knowledge"]', dockerfile)
        self.assertNotIn(":latest", dockerfile)

        for filename in ("runtime.lock", "development.lock"):
            requirements = locked_requirements(ROOT / "requirements" / filename)
            self.assertTrue(requirements)
            self.assertTrue(
                all(requirement["artifact_hashes"] for requirement in requirements)
            )

    def test_development_container_uses_development_target(self) -> None:
        definition = json.loads(
            (ROOT / ".devcontainer" / "devcontainer.json").read_text(encoding="utf-8")
        )
        self.assertEqual("development", definition["build"]["target"])
        self.assertEqual("kit", definition["remoteUser"])
        self.assertEqual("/workspace", definition["workspaceFolder"])

    def test_unified_cli_exposes_supported_commands(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(0, cli_main(["--help"]))
            self.assertEqual(0, cli_main(["--version"]))
        self.assertIn("check-runtime", output.getvalue())
        self.assertIn("surface-digest", output.getvalue())
        self.assertIn("check-change-policy", output.getvalue())

    def test_bootstrap_is_container_first_with_native_fallback(self) -> None:
        bootstrap = (
            ROOT / "guidance" / "workflows" / "bootstrap-new-project.md"
        ).read_text(encoding="utf-8")
        preconditions = bootstrap.split("## Procedure", 1)[0]
        self.assertIn("OCI-compatible container runtime", preconditions)
        self.assertNotIn("Python 3.11+", preconditions)
        self.assertIn("supported native fallback", bootstrap)
        self.assertIn("knowledge surface-digest", bootstrap)
        self.assertLess(
            bootstrap.index("11. Check source/runtime lockstep"),
            bootstrap.index("publish the validated baseline"),
        )

    def test_tool_selection_keeps_concrete_product_choices_specialized(self) -> None:
        selection = (ROOT / "guidance" / "reference" / "tool-selection.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "Implementation frameworks and concrete conformance tools",
            selection,
        )
        self.assertNotIn("| HTTP API implementation |", selection)
        self.assertNotIn("| API conformance testing |", selection)

    def test_consumer_ci_templates_use_pinned_runtime_image(self) -> None:
        gitlab = (ROOT / "ci" / "gitlab-ci.yml").read_text(encoding="utf-8")
        github = (ROOT / "ci" / "github-actions.yml").read_text(encoding="utf-8")
        self.assertIn("${KNOWLEDGE_KIT_IMAGE}", gitlab)
        self.assertIn("@sha256:", gitlab)
        self.assertIn("knowledge check-runtime", gitlab)
        self.assertIn("knowledge check-change-policy", gitlab)
        self.assertNotIn("pip install", gitlab)
        self.assertIn("${{ vars.KNOWLEDGE_KIT_IMAGE }}", github)
        self.assertIn("@sha256:", github)
        self.assertIn("docker run", github)
        self.assertIn("check-change-policy", github)

    def test_native_ci_is_explicit_fallback(self) -> None:
        gitlab = (ROOT / "ci" / "gitlab-native-ci.yml").read_text(encoding="utf-8")
        github = (ROOT / "ci" / "github-native-actions.yml").read_text(encoding="utf-8")
        self.assertIn("native", gitlab)
        self.assertIn("pip install", gitlab)
        self.assertIn("native fallback", github)
        self.assertIn("pip install", github)
        self.assertIn("persist-credentials: false", github)


def _toolkit_surface(root: Path) -> None:
    """Write a minimal tree covering both public-surface entry shapes."""

    (root / "tools").mkdir(parents=True, exist_ok=True)
    (root / "tools" / "widget.py").write_text("WIDGET = 1\n", encoding="utf-8")
    (root / "core").mkdir(parents=True, exist_ok=True)
    (root / "core" / "profile.yaml").write_text("id: fixture\n", encoding="utf-8")
    (root / "pyproject.toml").write_text('[project]\nname = "f"\n', encoding="utf-8")
    # Outside the public surface: must never reach the digest either way.
    (root / "knowledge").mkdir(parents=True, exist_ok=True)
    (root / "knowledge" / "note.md").write_text("note\n", encoding="utf-8")


def _git(root: Path, *arguments: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-c", f"safe.directory={root}", "-C", str(root), *arguments],
        check=True,
        capture_output=True,
    )


def _git_toolkit(root: Path) -> None:
    subprocess.run(
        ["git", "init", "--quiet", str(root)], check=True, capture_output=True
    )
    _git(root, "config", "user.email", "fixture@example.invalid")
    _git(root, "config", "user.name", "Fixture")
    _toolkit_surface(root)
    _git(root, "add", "-A")
    _git(root, "commit", "--quiet", "-m", "fixture")


class PublicSurfaceDigestSourceAuthorityTests(unittest.TestCase):
    """Public-surface membership by source form.

    A declared candidate (Git metadata or a packaged manifest) is authoritative
    for membership. A toolkit root that declares neither is a vendored source
    whose physical public surface is what it presents for validation.
    """

    def test_declared_candidate_ignores_local_noncandidate_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "kit"
            root.mkdir()
            _git_toolkit(root)
            clean = public_surface_digest(root)

            # Every host-local class that is not candidate source.
            (root / "tools" / "untracked.py").write_text("x\n", encoding="utf-8")
            for cache in (".mypy_cache", ".ruff_cache", "__pycache__"):
                (root / "tools" / cache).mkdir()
                (root / "tools" / cache / "entry").write_text("c\n", encoding="utf-8")
            (root / "tools" / "stale.pyc").write_bytes(b"stale")

            self.assertEqual(clean, public_surface_digest(root))

    def test_declared_candidate_follows_tracked_content_and_membership(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "kit"
            root.mkdir()
            _git_toolkit(root)
            clean = public_surface_digest(root)

            # Content authority stays the working tree, not committed blobs.
            (root / "tools" / "widget.py").write_text("WIDGET = 2\n", encoding="utf-8")
            self.assertNotEqual(clean, public_surface_digest(root))
            (root / "tools" / "widget.py").write_text("WIDGET = 1\n", encoding="utf-8")
            self.assertEqual(clean, public_surface_digest(root))

            (root / "tools" / "added.py").write_text("A = 1\n", encoding="utf-8")
            _git(root, "add", "tools/added.py")
            staged = public_surface_digest(root)
            self.assertNotEqual(clean, staged)

            _git(root, "rm", "--quiet", "-f", "tools/added.py")
            self.assertEqual(clean, public_surface_digest(root))

    def test_index_removal_is_observed_even_when_the_file_remains(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "kit"
            root.mkdir()
            _git_toolkit(root)
            clean = public_surface_digest(root)

            # The path leaves the candidate but stays on disk. Membership, not
            # the filesystem, decides what the public contract contains.
            _git(root, "rm", "--quiet", "--cached", "tools/widget.py")
            self.assertTrue((root / "tools" / "widget.py").is_file())
            self.assertNotEqual(clean, public_surface_digest(root))

    def test_declared_candidate_path_missing_from_the_tree_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "kit"
            root.mkdir()
            _git_toolkit(root)
            (root / "tools" / "widget.py").unlink()

            with self.assertRaises(KnowledgeFormatError) as raised:
                public_surface_digest(root)
            self.assertIn("tools/widget.py", str(raised.exception))

    def test_submodule_gitdir_file_is_a_declared_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "kit"
            root.mkdir()
            _git_toolkit(root)
            expected = public_surface_digest(root)

            parent = Path(directory) / "parent"
            parent.mkdir()
            subprocess.run(
                ["git", "init", "--quiet", str(parent)], check=True, capture_output=True
            )
            _git(parent, "config", "user.email", "fixture@example.invalid")
            _git(parent, "config", "user.name", "Fixture")
            (parent / "README.md").write_text("parent\n", encoding="utf-8")
            _git(parent, "add", "-A")
            _git(parent, "commit", "--quiet", "-m", "parent")
            subprocess.run(
                [
                    "git",
                    "-c",
                    "protocol.file.allow=always",
                    "-C",
                    str(parent),
                    "submodule",
                    "--quiet",
                    "add",
                    str(root),
                    ".knowledge-kit",
                ],
                check=True,
                capture_output=True,
            )

            pinned = parent / ".knowledge-kit"
            # A submodule's .git is a gitdir file, not a directory.
            self.assertTrue((pinned / ".git").is_file())
            (pinned / "tools" / "local.py").write_text("L = 1\n", encoding="utf-8")
            self.assertEqual(expected, public_surface_digest(pinned))

    def test_packaged_manifest_is_a_declared_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "kit"
            root.mkdir()
            _git_toolkit(root)
            expected = public_surface_digest(root)

            packaged = Path(directory) / "packaged"
            packaged.mkdir()
            _toolkit_surface(packaged)
            manifest = b"\0".join(
                sorted(
                    path.relative_to(root).as_posix().encode("utf-8")
                    for path in root.rglob("*")
                    if path.is_file() and ".git" not in path.relative_to(root).parts
                )
            )
            (packaged / ".gnostoa-source-files").write_bytes(manifest + b"\0")

            # Not a manifest member, so not public source.
            (packaged / "tools" / "extra.py").write_text("E = 1\n", encoding="utf-8")
            self.assertEqual(expected, public_surface_digest(packaged))

    def test_broken_declared_authority_never_degrades_to_the_filesystem(self) -> None:
        for label, prepare in (
            (
                "unsafe manifest entry",
                lambda p: (p / ".gnostoa-source-files").write_bytes(
                    b"tools/widget.py\0../escape.txt\0"
                ),
            ),
            (
                "manifest is a symlink",
                lambda p: (p / ".gnostoa-source-files").symlink_to("elsewhere"),
            ),
            (
                "git metadata is unusable",
                lambda p: (p / ".git").write_text(
                    "gitdir: /nonexistent\n", encoding="utf-8"
                ),
            ),
        ):
            with self.subTest(label):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory) / "kit"
                    root.mkdir()
                    _toolkit_surface(root)
                    prepare(root)
                    # A declaration that cannot be read must never be treated as
                    # no declaration: that would make broken authority weaker
                    # than absent authority.
                    with self.assertRaises(KnowledgeFormatError):
                        public_surface_digest(root)

    def test_metadata_free_vendored_source_presents_its_physical_surface(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            vendored = Path(directory) / ".knowledge-kit"
            vendored.mkdir()
            _toolkit_surface(vendored)
            self.assertFalse((vendored / ".git").exists())
            self.assertFalse((vendored / ".gnostoa-source-files").exists())
            clean = public_surface_digest(vendored)

            # Generated state is excluded by the digest contract.
            for cache in (".mypy_cache", ".ruff_cache", "__pycache__"):
                (vendored / "tools" / cache).mkdir()
                (vendored / "tools" / cache / "e").write_text("c\n", encoding="utf-8")
            (vendored / "tools" / "stale.pyc").write_bytes(b"stale")
            self.assertEqual(clean, public_surface_digest(vendored))

            # An extra non-ignored public file is a source modification. Nothing
            # here can prove it was not part of the vendored source.
            extra = vendored / "tools" / "extra.py"
            extra.write_text("E = 1\n", encoding="utf-8")
            self.assertNotEqual(clean, public_surface_digest(vendored))
            extra.unlink()
            self.assertEqual(clean, public_surface_digest(vendored))

            (vendored / "tools" / "widget.py").write_text("W = 2\n", encoding="utf-8")
            self.assertNotEqual(clean, public_surface_digest(vendored))
            (vendored / "tools" / "widget.py").unlink()
            self.assertNotEqual(clean, public_surface_digest(vendored))

    def test_clean_source_forms_agree_for_one_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "kit"
            root.mkdir()
            _git_toolkit(root)

            vendored = Path(directory) / "vendored"
            vendored.mkdir()
            _toolkit_surface(vendored)

            packaged = Path(directory) / "packaged"
            packaged.mkdir()
            _toolkit_surface(packaged)
            members = sorted(
                path.relative_to(packaged).as_posix().encode("utf-8")
                for path in packaged.rglob("*")
                if path.is_file()
            )
            (packaged / ".gnostoa-source-files").write_bytes(
                b"\0".join(members) + b"\0"
            )

            self.assertEqual(
                public_surface_digest(root), public_surface_digest(vendored)
            )
            self.assertEqual(
                public_surface_digest(root), public_surface_digest(packaged)
            )


class DocumentationTests(unittest.TestCase):
    def test_source_name_conditional_go_is_durably_projected(self) -> None:
        assessment_path = (
            ROOT / "knowledge" / "assessments" / "gnostoa-source-name-screening.md"
        )
        self.assertTrue(assessment_path.is_file())

        assessment = assessment_path.read_text(encoding="utf-8")
        decision = (
            ROOT / "knowledge" / "decisions" / "0009-adopt-gnostoa-project-name.md"
        ).read_text(encoding="utf-8")
        project = (ROOT / "knowledge" / "project" / "gnostoa.md").read_text(
            encoding="utf-8"
        )
        status = (ROOT / "docs" / "status.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        owner_control = (
            "accept-source-name-conditional-go: GNOSTOA/SOURCE-PUBLICATION/2026-08-15"
        )
        approved_artifact = "a7848a000d2618919cf6a247da64f9464bedf1474216bfdaa942e35910fc73ec"  # pragma: allowlist secret
        self.assertIn(owner_control, assessment)
        self.assertIn(approved_artifact, assessment)
        self.assertIn("source-only `CONDITIONAL GO`", assessment)
        for residual in ("JOTSON", "NEOTOA", "crates.io"):
            self.assertIn(residual, assessment)

        assessment_name = "gnostoa-source-name-screening.md"
        for projection in (decision, project, status, readme):
            self.assertIn(assessment_name, projection)
        self.assertNotIn("Gate 3 therefore remains open.", project)
        self.assertNotIn(
            "source-only conditional-go remain a first-publication gate",
            readme,
        )

    def test_publication_front_door_exposes_support_security_and_roadmap(self) -> None:
        security_path = ROOT / "SECURITY.md"
        support_path = ROOT / "SUPPORT.md"
        self.assertTrue(security_path.is_file())
        self.assertTrue(support_path.is_file())

        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        security = security_path.read_text(encoding="utf-8")
        support = support_path.read_text(encoding="utf-8")
        roadmap = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")
        normalized_security = " ".join(security.split())

        self.assertIn("[Security](SECURITY.md)", readme)
        self.assertIn("[Support](SUPPORT.md)", readme)
        self.assertIn("No supported release", normalized_security)
        self.assertIn("private vulnerability reporting", normalized_security)
        self.assertIn("No response-time guarantee", normalized_security)
        self.assertIn("GitHub Issues", support)
        self.assertIn("No support SLA", support)
        for heading in ("## Now", "## Next", "## Research"):
            self.assertIn(heading, roadmap)
        for issue_number in (
            1,
            3,
            5,
            6,
            7,
            8,
            9,
            10,
            11,
            13,
            14,
            15,
            24,
        ):
            self.assertIn(
                f"https://github.com/ktogias/gnostoa/issues/{issue_number}",
                roadmap,
            )

    def test_historical_bootstrap_ledger_is_bounded_and_routed(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        contributing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
        roadmap = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")
        assessment = (
            ROOT
            / "knowledge"
            / "assessments"
            / "gnostoa-self-dogfood-bootstrap-assessment.md"
        ).read_text(encoding="utf-8")

        boundary = "not the expected contribution workflow"
        self.assertIn(boundary, readme)
        self.assertIn(boundary, contributing)
        self.assertIn("## Historical provider ledger", assessment)
        self.assertIn("2,580,461", assessment)

        next_section = roadmap.split("## Next", maxsplit=1)[1].split(
            "## Research", maxsplit=1
        )[0]
        research_section = roadmap.split("## Research", maxsplit=1)[1]
        self.assertIn("https://github.com/ktogias/gnostoa/issues/109", next_section)
        self.assertNotIn("https://github.com/ktogias/gnostoa/issues/24", next_section)
        self.assertIn("https://github.com/ktogias/gnostoa/issues/24", roadmap)
        self.assertNotIn("https://github.com/ktogias/gnostoa/issues/12", next_section)
        self.assertIn("https://github.com/ktogias/gnostoa/issues/12", research_section)

        for comment_id in (
            5136593706,
            5136603642,
            5136719584,
            5136937206,
            5210352156,
            5221535175,
            5225850683,
            5284129277,
            5287954039,
            5288022522,
            5288102848,
            5288213713,
            5288289068,
        ):
            self.assertIn(
                f"issuecomment-{comment_id}",
                assessment,
            )

    def test_human_agent_workflow_need_is_planned_without_blocking_publication(
        self,
    ) -> None:
        decision_path = (
            ROOT
            / "knowledge"
            / "decisions"
            / "0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md"
        )
        self.assertTrue(decision_path.is_file())

        decision = decision_path.read_text(encoding="utf-8")
        roadmap = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")
        status = (ROOT / "docs" / "status.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        normalized_readme = " ".join(readme.split())
        assessment = (
            ROOT
            / "knowledge"
            / "assessments"
            / "gnostoa-self-dogfood-bootstrap-assessment.md"
        ).read_text(encoding="utf-8")

        for required in (
            "## Resume card",
            "The need is demonstrated; the minimum sufficient implementation is not.",
            "not a first-publication prerequisite",
            "one active delivery item and one active enabling slice",
            "task envelope",
            "checkpoint/resume",
            "current projection",
            "https://github.com/ktogias/gnostoa/issues/24",
        ):
            self.assertIn(required, decision)

        decision_name = (
            "0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md"
        )
        for projection in (roadmap, status, readme, assessment):
            self.assertIn(decision_name, projection)

        # The invariant is that the workflow need stays durably planned while
        # completed B2 evidence remains distinct from the not-yet-started B3
        # experiment and from the separately admitted readiness correction.
        self.assertIn("B2/P1 and B2/P2 are both complete", roadmap)
        self.assertIn("B2/P1 completed", status)
        for projection in (roadmap, status):
            self.assertIn("https://github.com/ktogias/gnostoa/issues/24", projection)
            self.assertIn("B3 has not begun", projection)
            self.assertNotIn("Active B2/P1", projection)
        self.assertIn("https://github.com/ktogias/gnostoa/issues/109", roadmap)
        self.assertIn("need has already been demonstrated", status)
        self.assertIn(
            "full workflow platform is not a publication prerequisite",
            normalized_readme,
        )

    def test_container_first_verification_bypass_is_recorded_and_routed(
        self,
    ) -> None:
        incident_path = (
            ROOT
            / "knowledge"
            / "failure-modes"
            / "container-first-verification-routing-bypass.md"
        )
        self.assertTrue(incident_path.is_file())

        incident = incident_path.read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        maintainer_runbook = (
            ROOT / "knowledge" / "runbooks" / "maintain-the-kit.md"
        ).read_text(encoding="utf-8")
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        index = (ROOT / "knowledge" / "index.md").read_text(encoding="utf-8")

        for required in (
            "## Resume card",
            "routing error",
            "discoverability and enforcement gap",
            "no false PASS",
            "development container",
            "one-command wrapper",
            "https://github.com/ktogias/gnostoa/issues/24",
        ):
            self.assertIn(required, incident)

        incident_name = "container-first-verification-routing-bypass.md"
        self.assertIn(incident_name, index)
        self.assertIn("--target development", readme)
        self.assertIn("--target development", maintainer_runbook)
        self.assertIn("--target development", agents)
        self.assertIn("./ci/verify extended", readme)
        self.assertIn("./ci/verify extended", maintainer_runbook)
        self.assertIn("./ci/verify extended", agents)

    def test_public_front_door_exposes_verified_evaluation_path(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        index = (ROOT / "docs" / "index.md").read_text(encoding="utf-8")
        quick_start = (ROOT / "docs" / "quick-start.md").read_text(encoding="utf-8")
        status = (ROOT / "docs" / "status.md").read_text(encoding="utf-8")
        roadmap = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

        self.assertIn("## Try Gnostoa from this checkout", readme)
        self.assertIn("--seed example.system.processing", readme)
        self.assertIn("python -m pip install --no-deps -e .", readme)
        self.assertIn("pre-stable v0.1.1 source and OCI release", readme)
        self.assertIn("B3 independent-adoption methodology", readme)
        self.assertIn("digest-pinned `linux/amd64` OCI image", index)
        self.assertNotIn("not published package, image", index)
        self.assertIn("navigation projection", quick_start)
        self.assertIn("knowledge validate", quick_start)
        self.assertIn("KNOWLEDGE_KIT_ROOT", quick_start)
        self.assertIn("navigation projection", status)
        self.assertIn("Source and publication status", status)
        for projection in (status, roadmap):
            self.assertIn("B3 has not begun", projection)
            self.assertIn("candidate selection", projection)
            self.assertIn("0043-prepare-a-bounded-v0-1-2", projection)

    def test_repository_documentation_links_resolve(self) -> None:
        paths = [
            ROOT / "README.md",
            ROOT / "CONTRIBUTING.md",
            ROOT / "SECURITY.md",
            ROOT / "SUPPORT.md",
            *(ROOT / "docs").rglob("*.md"),
        ]
        broken: list[str] = []
        for path in paths:
            body = path.read_text(encoding="utf-8")
            for target in markdown_links(body):
                resolved = resolve_target(ROOT, path, target)
                if resolved is not None and not resolved.exists():
                    broken.append(f"{path.relative_to(ROOT)} -> {target}")
        self.assertEqual([], broken)

    def test_mkdocs_pages_are_explicit_projections(self) -> None:
        missing_marker = [
            str(path.relative_to(ROOT))
            for path in (ROOT / "docs").rglob("*.md")
            if "navigation projection" not in path.read_text(encoding="utf-8")
        ]
        self.assertEqual([], missing_marker)

    def test_docs_builder_stages_canonical_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            staging = Path(directory)
            config = prepare_projection(
                ROOT,
                staging,
                staging / "site",
            )
            content = staging / "content"
            self.assertTrue((content / "core" / "change-control.yaml").is_file())
            self.assertTrue((content / "docs" / "index.md").is_file())
            self.assertTrue((content / "guidance" / "index.md").is_file())
            self.assertTrue((content / "knowledge" / "index.md").is_file())
            self.assertTrue((content / "policy" / "guardrails.yaml").is_file())
            self.assertTrue(
                (content / "schemas" / "v1" / "profile.schema.json").is_file()
            )
            projected_config = config.read_text(encoding="utf-8")
            self.assertIn("- Home: docs/index.md", projected_config)
            self.assertIn(
                "- Reusable guidance: guidance/index.md",
                projected_config,
            )
            self.assertIn(
                "- Project status: knowledge/project/gnostoa.md",
                projected_config,
            )
            self.assertNotIn("docs/guidance/index.md", projected_config)
            self.assertNotIn("docs/knowledge/project/gnostoa.md", projected_config)
            self.assertIn("not_in_nav:", projected_config)
            self.assertIn("!templates/**", projected_config)
            self.assertIn("docs_dir:", projected_config)


if __name__ == "__main__":
    unittest.main()
