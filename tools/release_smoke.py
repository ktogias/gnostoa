#!/usr/bin/env python3
"""Build and exercise clean native Gnostoa distribution artifacts."""

from __future__ import annotations

import argparse
import configparser
import hashlib
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import zipfile
from dataclasses import dataclass
from email import policy
from email.parser import BytesParser
from pathlib import Path, PurePosixPath
from typing import Any

CANONICAL_SOURCE_ROOTS = {
    "ci",
    "core",
    "docs",
    "examples",
    "guidance",
    "knowledge",
    "policy",
    "schemas",
    "templates",
}


class ReleaseSmokeError(RuntimeError):
    """A release-smoke precondition or assertion failed."""


@dataclass(frozen=True)
class ArtifactResult:
    artifact: Path
    kind: str
    digest: str
    size_bytes: int
    metadata_digest: str
    validation: str
    context_pack: str
    surface_digest: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _project_distribution(repository_root: Path) -> dict[str, Any]:
    document = tomllib.loads(
        (repository_root / "pyproject.toml").read_text(encoding="utf-8")
    )
    project = document.get("project")
    if not isinstance(project, dict):
        raise ReleaseSmokeError("pyproject.toml has no [project] table")
    required = (
        "name",
        "version",
        "license",
        "requires-python",
        "dependencies",
        "scripts",
    )
    missing = [name for name in required if name not in project]
    if missing:
        raise ReleaseSmokeError(
            "pyproject.toml is missing release metadata: " + ", ".join(missing)
        )
    if not isinstance(project["license"], str):
        raise ReleaseSmokeError("project.license must be an SPDX expression string")
    if not isinstance(project["dependencies"], list) or not all(
        isinstance(item, str) for item in project["dependencies"]
    ):
        raise ReleaseSmokeError("project.dependencies must be a list of strings")
    if not isinstance(project["scripts"], dict) or not all(
        isinstance(name, str) and isinstance(target, str)
        for name, target in project["scripts"].items()
    ):
        raise ReleaseSmokeError("project.scripts must map command names to targets")
    return project


def _normalized_requirement(value: str) -> str:
    requirement, separator, marker = value.partition(";")
    match = re.fullmatch(
        r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)(\[[^]]+\])?(.*)",
        requirement,
    )
    if match is None:
        return re.sub(r"\s+", "", value).casefold()
    name = re.sub(r"[-_.]+", "-", match.group(1)).casefold()
    extras = ""
    if match.group(2):
        extras = (
            "["
            + ",".join(
                sorted(
                    item.strip().casefold() for item in match.group(2)[1:-1].split(",")
                )
            )
            + "]"
        )
    clauses = sorted(
        clause.strip().casefold()
        for clause in match.group(3).split(",")
        if clause.strip()
    )
    specification = ",".join(clauses)
    normalized_marker = ""
    if separator:
        normalized_marker = ";" + re.sub(r"\s+", "", marker).casefold()
    return f"{name}{extras}{specification}{normalized_marker}"


def _metadata_issues(
    label: str,
    content: bytes,
    project: dict[str, Any],
) -> list[str]:
    message = BytesParser(policy=policy.default).parsebytes(content)
    issues: list[str] = []
    expected_fields = {
        "Name": project["name"],
        "Version": project["version"],
        "License-Expression": project["license"],
        "Requires-Python": project["requires-python"],
    }
    for field, expected in expected_fields.items():
        actual = message.get(field)
        if actual != expected:
            issues.append(
                f"{label} metadata {field} is {actual!r}, expected {expected!r}"
            )

    declared_dependencies = list(project["dependencies"])
    optional_dependencies = project.get("optional-dependencies", {})
    if isinstance(optional_dependencies, dict):
        for extra, requirements in optional_dependencies.items():
            if isinstance(extra, str) and isinstance(requirements, list):
                declared_dependencies.extend(
                    f'{item}; extra == "{extra}"'
                    for item in requirements
                    if isinstance(item, str)
                )
    expected_dependencies = {
        _normalized_requirement(item) for item in declared_dependencies
    }
    actual_dependencies = {
        _normalized_requirement(item) for item in message.get_all("Requires-Dist", [])
    }
    if actual_dependencies != expected_dependencies:
        issues.append(
            f"{label} metadata dependencies are {sorted(actual_dependencies)!r}, "
            f"expected {sorted(expected_dependencies)!r}"
        )
    return issues


def _unique_name(
    names: list[str],
    suffix: str,
    label: str,
    issues: list[str],
) -> str | None:
    matches = [name for name in names if name == suffix or name.endswith(f"/{suffix}")]
    if len(matches) != 1:
        issues.append(
            f"{label} must contain exactly one {suffix}; found {len(matches)}"
        )
        return None
    return matches[0]


def _unique_sdist_name(
    names: list[str],
    relative: str,
    issues: list[str],
) -> str | None:
    relative_parts = PurePosixPath(relative).parts
    matches = [
        name for name in names if PurePosixPath(name).parts[1:] == relative_parts
    ]
    if len(matches) != 1:
        issues.append(
            "source distribution must contain exactly one root "
            f"{relative}; found {len(matches)}"
        )
        return None
    return matches[0]


def _entry_point_issues(content: bytes, project: dict[str, Any]) -> list[str]:
    class CaseSensitiveConfigParser(configparser.ConfigParser):
        def optionxform(self, optionstr: str) -> str:
            return optionstr

    parser = CaseSensitiveConfigParser(interpolation=None)
    try:
        parser.read_string(content.decode("utf-8"))
    except (UnicodeDecodeError, configparser.Error) as exc:
        return [f"wheel console entry points are invalid: {exc}"]
    actual = (
        dict(parser["console_scripts"]) if parser.has_section("console_scripts") else {}
    )
    expected = project["scripts"]
    if actual != expected:
        return [f"wheel console entry points are {actual!r}, expected {expected!r}"]
    return []


def distribution_metadata_issues(
    repository_root: Path,
    wheel: Path,
    source_distribution: Path,
) -> list[str]:
    """Compare built archive identity and policy metadata with canonical source."""

    root = repository_root.resolve()
    project = _project_distribution(root)
    name = project["name"]
    version = project["version"]
    normalized_name = re.sub(r"[-_.]+", "_", name)
    expected_wheel = f"{normalized_name}-{version}-py3-none-any.whl"
    expected_sdist = f"{name}-{version}.tar.gz"
    issues: list[str] = []
    if wheel.name != expected_wheel:
        issues.append(f"wheel filename is {wheel.name!r}, expected {expected_wheel!r}")
    if source_distribution.name != expected_sdist:
        issues.append(
            "source-distribution filename is "
            f"{source_distribution.name!r}, expected {expected_sdist!r}"
        )

    expected_files = {
        "LICENSE": (root / "LICENSE").read_bytes(),
        "NOTICE": (root / "NOTICE").read_bytes(),
    }
    try:
        with zipfile.ZipFile(wheel) as wheel_archive:
            names = wheel_archive.namelist()
            metadata_name = _unique_name(names, "METADATA", "wheel", issues)
            entry_points_name = _unique_name(names, "entry_points.txt", "wheel", issues)
            if metadata_name is not None:
                issues.extend(
                    _metadata_issues(
                        "wheel",
                        wheel_archive.read(metadata_name),
                        project,
                    )
                )
            if entry_points_name is not None:
                issues.extend(
                    _entry_point_issues(
                        wheel_archive.read(entry_points_name),
                        project,
                    )
                )
            for filename, expected in expected_files.items():
                member = _unique_name(names, f"licenses/{filename}", "wheel", issues)
                if member is not None and wheel_archive.read(member) != expected:
                    issues.append(f"wheel {filename} does not match canonical source")
    except (OSError, zipfile.BadZipFile) as exc:
        issues.append(f"cannot inspect wheel metadata: {exc}")

    try:
        with tarfile.open(source_distribution, "r:gz") as sdist_archive:
            members = [
                member for member in sdist_archive.getmembers() if member.isfile()
            ]
            names = [member.name for member in members]
            member_by_name = {member.name: member for member in members}

            def read_member(suffix: str) -> bytes | None:
                selected = _unique_sdist_name(names, suffix, issues)
                if selected is None:
                    return None
                stream = sdist_archive.extractfile(member_by_name[selected])
                if stream is None:
                    issues.append(f"cannot read source-distribution member {selected}")
                    return None
                return stream.read()

            metadata = read_member("PKG-INFO")
            if metadata is not None:
                issues.extend(
                    _metadata_issues("source distribution", metadata, project)
                )
            for filename, expected in expected_files.items():
                content = read_member(filename)
                if content is not None and content != expected:
                    issues.append(
                        f"source-distribution {filename} does not match "
                        "canonical source"
                    )
            for filename in ("README.md", "pyproject.toml", "tools/cli.py"):
                content = read_member(filename)
                if content is not None and content != (root / filename).read_bytes():
                    issues.append(
                        f"source-distribution {filename} does not match "
                        "canonical source"
                    )
    except (OSError, tarfile.TarError) as exc:
        issues.append(f"cannot inspect source-distribution metadata: {exc}")

    return sorted(set(issues))


def _artifact_metadata_digest(artifact: Path, kind: str) -> str:
    if kind == "wheel":
        with zipfile.ZipFile(artifact) as wheel_archive:
            wheel_matches = [
                name for name in wheel_archive.namelist() if name.endswith("/METADATA")
            ]
            if len(wheel_matches) != 1:
                raise ReleaseSmokeError(
                    "wheel must contain exactly one METADATA; "
                    f"found {len(wheel_matches)}"
                )
            return _sha256_bytes(wheel_archive.read(wheel_matches[0]))
    if kind == "sdist":
        with tarfile.open(artifact, "r:gz") as sdist_archive:
            sdist_matches = [
                member
                for member in sdist_archive.getmembers()
                if member.isfile()
                and PurePosixPath(member.name).parts[1:] == ("PKG-INFO",)
            ]
            if len(sdist_matches) != 1:
                raise ReleaseSmokeError(
                    "source distribution must contain exactly one PKG-INFO; "
                    f"found {len(sdist_matches)}"
                )
            stream = sdist_archive.extractfile(sdist_matches[0])
            if stream is None:
                raise ReleaseSmokeError("cannot read source-distribution PKG-INFO")
            return _sha256_bytes(stream.read())
    raise ReleaseSmokeError(f"unknown artifact kind: {kind!r}")


def wheel_canonical_payloads(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        return sorted(
            name
            for name in archive.namelist()
            if name.split("/", 1)[0] in CANONICAL_SOURCE_ROOTS
        )


def _run(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    expect: int = 0,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != expect:
        rendered = " ".join(command)
        raise ReleaseSmokeError(
            f"command returned {result.returncode}, expected {expect}: {rendered}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def verify_release_source(repository_root: Path, source_revision: str) -> None:
    if re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", source_revision) is None:
        raise ReleaseSmokeError(
            "source revision must be an exact lowercase 40- or 64-character "
            "Git object ID"
        )
    root = repository_root.resolve()
    current = _run(["git", "rev-parse", "HEAD"], cwd=root).stdout.strip()
    if current != source_revision:
        raise ReleaseSmokeError(
            f"source revision {source_revision} does not match HEAD {current}"
        )
    status = _run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=root,
    ).stdout
    if status:
        raise ReleaseSmokeError(
            "release evidence requires a clean source tree; Git reports:\n"
            + status.rstrip()
        )


def _environment_commands(environment: Path) -> tuple[Path, Path]:
    scripts = environment / ("Scripts" if os.name == "nt" else "bin")
    return scripts / "python", scripts / "knowledge"


def _exercise_artifact(
    artifact: Path,
    kind: str,
    expected_version: str,
    repository_root: Path,
    workspace: Path,
    environment: Path,
) -> ArtifactResult:
    _run(
        [sys.executable, "-m", "venv", str(environment)],
        cwd=workspace,
    )
    python, knowledge = _environment_commands(environment)
    _run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "-r",
            str(repository_root / "requirements" / "runtime.lock"),
        ],
        cwd=workspace,
    )
    _run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-deps",
            str(artifact),
        ],
        cwd=workspace,
    )

    unbound_environment = os.environ.copy()
    for name in (
        "KNOWLEDGE_KIT_ROOT",
        "KNOWLEDGE_KIT_REVISION",
        "KNOWLEDGE_KIT_IMAGE",
    ):
        unbound_environment.pop(name, None)
    unbound = _run(
        [
            str(knowledge),
            "validate",
            "--profile",
            str(repository_root / "core" / "profile.yaml"),
            "--bundle",
            str(repository_root / "examples" / "generic"),
        ],
        cwd=workspace,
        env=unbound_environment,
        expect=2,
    )
    if "KNOWLEDGE_KIT_ROOT" not in unbound.stderr or "Traceback" in unbound.stderr:
        raise ReleaseSmokeError(
            "unbound native execution did not fail with the declared source-binding "
            f"diagnostic:\n{unbound.stderr}"
        )

    bound_environment = unbound_environment | {
        "KNOWLEDGE_KIT_ROOT": str(repository_root)
    }
    version = _run(
        [str(knowledge), "--version"],
        cwd=workspace,
        env=bound_environment,
    ).stdout.strip()
    if version != expected_version:
        raise ReleaseSmokeError(
            "installed artifact reports version "
            f"{version!r}, expected {expected_version!r}"
        )

    validation = _run(
        [
            str(knowledge),
            "validate",
            "--profile",
            str(repository_root / "core" / "profile.yaml"),
            "--bundle",
            str(repository_root / "examples" / "generic"),
        ],
        cwd=workspace,
        env=bound_environment,
    ).stdout
    expected_validation = (
        "OK: bundle conforms to project-knowledge-core 0.1.0 (OKF 0.2)\n"
    )
    if validation != expected_validation:
        raise ReleaseSmokeError(
            "installed artifact returned an unexpected validation result:\n"
            f"{validation}"
        )

    context_pack = _run(
        [
            str(knowledge),
            "context-pack",
            "--profile",
            str(repository_root / "core" / "profile.yaml"),
            "--bundle",
            str(repository_root / "examples" / "generic"),
            "--seed",
            "example.system.processing",
            "--depth",
            "2",
            "--max-tokens",
            "800",
        ],
        cwd=workspace,
        env=bound_environment,
    ).stdout
    surface_digest = _run(
        [
            str(knowledge),
            "surface-digest",
            "--root",
            str(repository_root),
        ],
        cwd=workspace,
        env=bound_environment,
    ).stdout

    return ArtifactResult(
        artifact=artifact,
        kind=kind,
        digest=sha256_file(artifact),
        size_bytes=artifact.stat().st_size,
        metadata_digest=_artifact_metadata_digest(artifact, kind),
        validation=validation,
        context_pack=context_pack,
        surface_digest=surface_digest,
    )


def _artifacts(output: Path) -> tuple[Path, Path]:
    wheels = sorted(output.glob("gnostoa-*.whl"))
    source_distributions = sorted(output.glob("gnostoa-*.tar.gz"))
    if len(wheels) != 1 or len(source_distributions) != 1:
        raise ReleaseSmokeError(
            "build must produce exactly one Gnostoa wheel and one source "
            f"distribution; found {wheels!r} and {source_distributions!r}"
        )
    return wheels[0], source_distributions[0]


def release_smoke(repository_root: Path, output_dir: Path) -> list[ArtifactResult]:
    root = repository_root.resolve()
    project = _project_distribution(root)
    output = output_dir.resolve()
    if output.exists() and any(output.iterdir()):
        raise ReleaseSmokeError(f"artifact output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)

    _run(
        [
            sys.executable,
            "-m",
            "build",
            "--no-isolation",
            "--outdir",
            str(output),
            str(root),
        ],
        cwd=root,
    )
    wheel, source_distribution = _artifacts(output)
    metadata_issues = distribution_metadata_issues(root, wheel, source_distribution)
    if metadata_issues:
        raise ReleaseSmokeError(
            "distribution metadata validation failed:\n- "
            + "\n- ".join(metadata_issues)
        )
    duplicated = wheel_canonical_payloads(wheel)
    if duplicated:
        raise ReleaseSmokeError(
            "execution-only wheel duplicates canonical source roots: "
            + ", ".join(duplicated)
        )

    results: list[ArtifactResult] = []
    with tempfile.TemporaryDirectory(prefix="gnostoa-release-smoke-") as directory:
        smoke_root = Path(directory)
        workspace = smoke_root / "workspace"
        workspace.mkdir()
        artifacts = (("wheel", wheel), ("sdist", source_distribution))
        for index, (kind, artifact) in enumerate(artifacts, start=1):
            results.append(
                _exercise_artifact(
                    artifact,
                    kind,
                    project["version"],
                    root,
                    workspace,
                    smoke_root / f"environment-{index}",
                )
            )

    first = results[0]
    for result in results[1:]:
        if (
            result.validation,
            result.context_pack,
            result.surface_digest,
        ) != (
            first.validation,
            first.context_pack,
            first.surface_digest,
        ):
            raise ReleaseSmokeError(
                "wheel and source-distribution installs produced different "
                "declared results"
            )
    return results


def release_evidence_manifest(
    repository_root: Path,
    results: list[ArtifactResult],
    source_revision: str,
) -> dict[str, Any]:
    """Build a path-neutral, machine-readable record of release-smoke evidence."""

    if re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", source_revision) is None:
        raise ReleaseSmokeError(
            "source revision must be an exact lowercase 40- or 64-character "
            "Git object ID"
        )
    kinds = {result.kind for result in results}
    if len(results) != 2 or kinds != {"wheel", "sdist"}:
        raise ReleaseSmokeError(
            "release evidence requires exactly one wheel and one source distribution"
        )
    declared_results = {
        (result.validation, result.context_pack, result.surface_digest)
        for result in results
    }
    if len(declared_results) != 1:
        raise ReleaseSmokeError(
            "release evidence cannot record divergent artifact results"
        )

    project = _project_distribution(repository_root.resolve())
    first = results[0]
    surface_digest = first.surface_digest.strip()
    if re.fullmatch(r"sha256:[0-9a-f]{64}", surface_digest) is None:
        raise ReleaseSmokeError(
            f"public-surface digest is malformed: {surface_digest!r}"
        )
    ordered = sorted(
        results,
        key=lambda result: (
            {"wheel": 0, "sdist": 1}[result.kind],
            result.artifact.name,
        ),
    )
    return {
        "format": "gnostoa-release-evidence/v1",
        "package": {
            "name": project["name"],
            "version": project["version"],
            "requires_python": project["requires-python"],
            "license_expression": project["license"],
            "console_commands": sorted(project["scripts"]),
        },
        "source": {
            "revision": source_revision,
            "public_surface_digest": surface_digest,
        },
        "artifacts": [
            {
                "filename": result.artifact.name,
                "kind": result.kind,
                "sha256": f"sha256:{result.digest}",
                "size_bytes": result.size_bytes,
                "metadata_sha256": f"sha256:{result.metadata_digest}",
            }
            for result in ordered
        ],
        "checks": {
            "artifact_count": 2,
            "archive_metadata_matches_source": True,
            "license_and_notice_match_source": True,
            "console_commands_match_source": True,
            "clean_install": True,
            "unbound_source_rejected": True,
            "explicit_source_binding": True,
            "wheel_canonical_payloads": [],
            "declared_results_identical": True,
            "source_revision_verified": True,
            "source_tree_clean": True,
            "validation_output_sha256": (
                "sha256:" + _sha256_bytes(first.validation.encode("utf-8"))
            ),
            "context_pack_output_sha256": (
                "sha256:" + _sha256_bytes(first.context_pack.encode("utf-8"))
            ),
        },
    }


def write_release_evidence_manifest(path: Path, manifest: dict[str, Any]) -> None:
    target = path.resolve()
    if target.exists():
        raise ReleaseSmokeError(f"release evidence manifest already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build a wheel and source distribution, install each into a clean "
            "environment and verify explicit public-source binding."
        )
    )
    parser.add_argument(
        "--repository-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--evidence-manifest",
        type=Path,
        help="write deterministic JSON evidence after all checks pass",
    )
    parser.add_argument(
        "--source-revision",
        help="exact Git object ID bound into --evidence-manifest",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.evidence_manifest is not None:
            if args.source_revision is None:
                raise ReleaseSmokeError(
                    "--source-revision is required with --evidence-manifest"
                )
            verify_release_source(args.repository_root, args.source_revision)
        results = release_smoke(args.repository_root, args.output_dir)
        if args.evidence_manifest is not None:
            manifest = release_evidence_manifest(
                args.repository_root,
                results,
                args.source_revision,
            )
            write_release_evidence_manifest(args.evidence_manifest, manifest)
    except (OSError, ReleaseSmokeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    for result in results:
        print(
            f"OK: {result.artifact.name} sha256:{result.digest} passed native "
            "source-binding smoke"
        )
    print("OK: wheel and source-distribution declared results are identical")
    if args.evidence_manifest is not None:
        print(f"OK: release evidence written to {args.evidence_manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
