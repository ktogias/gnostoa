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
from tools.validate_bundle import validate_bundle

ROOT = Path(__file__).resolve().parent.parent


def _add_tar_bytes(archive: tarfile.TarFile, name: str, content: bytes) -> None:
    member = tarfile.TarInfo(name)
    member.size = len(content)
    archive.addfile(member, BytesIO(content))


def _release_archive_fixtures(
    directory: Path,
    *,
    version: str = "0.1.0",
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
        self.assertIn(
            "if: github.event_name != 'push' || github.ref == 'refs/heads/main'",
            workflow,
        )
        self.assertRegex(workflow, r"actions/checkout@[a-f0-9]{40}")
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
        self.assertIn(
            'org.opencontainers.image.licenses="Apache-2.0"',
            (ROOT / "Dockerfile").read_text(encoding="utf-8"),
        )

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
            / "profile.yaml"
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
                load_profile(child)


class BundleTests(unittest.TestCase):
    def test_generic_example_is_valid(self) -> None:
        _, issues = validate_bundle(
            ROOT / "core" / "profile.yaml",
            ROOT / "examples" / "generic",
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
        )
        self.assertEqual([], issues)

    def test_guidance_bundle_is_valid(self) -> None:
        _, issues = validate_bundle(
            ROOT / "guidance" / "profile.yaml",
            ROOT / "guidance",
        )
        self.assertEqual([], issues)

    def test_self_knowledge_bundle_is_valid(self) -> None:
        _, issues = validate_bundle(
            ROOT / "knowledge" / "profile.yaml",
            ROOT / "knowledge",
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
            _, issues = validate_bundle(ROOT / "core" / "profile.yaml", bundle)
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
        self.assertIn("https://github.com/ktogias/gnostoa/issues/24", next_section)
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
        # the projections name the *current* experiment, not that any one slice
        # is active. P1 is historical; Issue #24's P2 is the bounded experiment.
        for projection in (roadmap, status):
            self.assertIn("B2/P1 completed", projection)
            self.assertIn("https://github.com/ktogias/gnostoa/issues/24", projection)
            self.assertNotIn("Active B2/P1", projection)
        self.assertIn("B2/P2", roadmap)
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
        quick_start = (ROOT / "docs" / "quick-start.md").read_text(encoding="utf-8")
        status = (ROOT / "docs" / "status.md").read_text(encoding="utf-8")

        self.assertIn("## Try Gnostoa from this checkout", readme)
        self.assertIn("--seed example.system.processing", readme)
        self.assertIn("python -m pip install --no-deps -e .", readme)
        self.assertIn("No package, image or site has been released yet", readme)
        self.assertIn("navigation projection", quick_start)
        self.assertIn("knowledge validate", quick_start)
        self.assertIn("KNOWLEDGE_KIT_ROOT", quick_start)
        self.assertIn("navigation projection", status)
        self.assertIn("Pre-release", status)

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
