#!/usr/bin/env python3
"""Build and exercise clean native Gnostoa distribution artifacts."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile


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
    digest: str
    validation: str
    context_pack: str
    surface_digest: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


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


def _environment_commands(environment: Path) -> tuple[Path, Path]:
    scripts = environment / ("Scripts" if os.name == "nt" else "bin")
    return scripts / "python", scripts / "knowledge"


def _exercise_artifact(
    artifact: Path,
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
    if version != "0.1.0":
        raise ReleaseSmokeError(
            f"installed artifact reports version {version!r}, expected '0.1.0'"
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
        digest=sha256_file(artifact),
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
        for index, artifact in enumerate((wheel, source_distribution), start=1):
            results.append(
                _exercise_artifact(
                    artifact,
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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        results = release_smoke(args.repository_root, args.output_dir)
    except (OSError, ReleaseSmokeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    for result in results:
        print(
            f"OK: {result.artifact.name} sha256:{result.digest} passed native "
            "source-binding smoke"
        )
    print("OK: wheel and source-distribution declared results are identical")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
