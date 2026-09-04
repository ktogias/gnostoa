"""Subject-preparation contract.

Reads exact project metadata from a materialised tree and decides whether the
tree is directly runnable or needs a named deterministic preparation. Every
inference records where it came from; nothing is guessed silently.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

# Explicit, reviewable option-prefix to distribution table. A pytest option
# namespace is only attributed to a plugin when it is listed here; unknown
# namespaces are reported as unknown rather than attributed by guesswork.
OPTION_PLUGINS: Mapping[str, str] = {
    "--benchmark": "pytest-benchmark",
    "--cov": "pytest-cov",
    "--timeout": "pytest-timeout",
    "--asyncio": "pytest-asyncio",
    "--xdist": "pytest-xdist",
    "-n": "pytest-xdist",
    "--hypothesis": "hypothesis",
    "--mock": "pytest-mock",
}


@dataclass(frozen=True, slots=True)
class TestConfig:
    """Discovered repository test configuration and what it demands."""

    source: str | None
    addopts: tuple[str, ...] = ()
    required_plugins: tuple[str, ...] = ()
    unknown_option_namespaces: tuple[str, ...] = ()
    inference: tuple[str, ...] = ()

    def as_json(self) -> dict[str, object]:
        return {
            "source": self.source,
            "addopts": list(self.addopts),
            "required_plugins": list(self.required_plugins),
            "unknown_option_namespaces": list(self.unknown_option_namespaces),
            "inference": list(self.inference),
        }


@dataclass(frozen=True, slots=True)
class PreparationRequirement:
    """A deterministic build-generated artifact the frozen tree does not carry."""

    required: bool
    kind: str | None = None
    generated_paths: tuple[str, ...] = ()
    tool_names: tuple[str, ...] = ()
    inference: tuple[str, ...] = ()

    def as_json(self) -> dict[str, object]:
        return {
            "required": self.required,
            "kind": self.kind,
            "generated_paths": list(self.generated_paths),
            "tool_names": list(self.tool_names),
            "inference": list(self.inference),
        }


def _load_pyproject(tree: Path) -> tuple[dict, str | None]:
    path = tree / "pyproject.toml"
    if not path.is_file():
        return {}, None
    try:
        return tomllib.loads(path.read_text()), "pyproject.toml"
    except tomllib.TOMLDecodeError:
        return {}, None


def _pytest_section(data: Mapping[str, object]) -> tuple[Mapping[str, object], str | None]:
    """pytest 9 reads [tool.pytest]; earlier versions read [tool.pytest.ini_options]."""
    tool = data.get("tool")
    if not isinstance(tool, dict):
        return {}, None
    pytest_table = tool.get("pytest")
    if not isinstance(pytest_table, dict):
        return {}, None
    ini_options = pytest_table.get("ini_options")
    if isinstance(ini_options, dict):
        return ini_options, "pyproject.toml [tool.pytest.ini_options]"
    return pytest_table, "pyproject.toml [tool.pytest]"


def discover_test_config(tree: Path) -> TestConfig:
    data, origin = _load_pyproject(tree)
    if not data:
        return TestConfig(source=None)
    section, where = _pytest_section(data)
    if not section:
        return TestConfig(source=None)

    raw_addopts = section.get("addopts", [])
    if isinstance(raw_addopts, str):
        addopts = tuple(raw_addopts.split())
    elif isinstance(raw_addopts, list):
        addopts = tuple(str(item) for item in raw_addopts)
    else:
        addopts = ()

    plugins: list[str] = []
    unknown: list[str] = []
    inference: list[str] = []
    for option in addopts:
        if not option.startswith("-"):
            continue
        namespace = option.split("=", 1)[0]
        matched = None
        for prefix, distribution in OPTION_PLUGINS.items():
            if namespace == prefix or namespace.startswith(prefix + "-"):
                matched = distribution
                break
        if matched is None:
            unknown.append(namespace)
        elif matched not in plugins:
            plugins.append(matched)
            inference.append(f"{where}: addopts {namespace} requires {matched}")

    return TestConfig(
        source=where,
        addopts=addopts,
        required_plugins=tuple(plugins),
        unknown_option_namespaces=tuple(sorted(set(unknown))),
        inference=tuple(inference),
    )


def discover_preparation(tree: Path) -> PreparationRequirement:
    """Detect build-generated files the frozen tree omits (the D3 class)."""
    data, origin = _load_pyproject(tree)
    if not data:
        return PreparationRequirement(required=False)

    tool = data.get("tool")
    scm = tool.get("setuptools_scm") if isinstance(tool, dict) else None
    if not isinstance(scm, dict):
        return PreparationRequirement(required=False)

    inference = [f"{origin} [tool.setuptools_scm] present"]
    project = data.get("project")
    if isinstance(project, dict) and "version" in (project.get("dynamic") or []):
        inference.append(f"{origin} project.dynamic includes 'version'")

    targets: list[str] = []
    for key in ("write_to", "version_file"):
        value = scm.get(key)
        if isinstance(value, str) and value:
            targets.append(value)
            inference.append(f"{origin} [tool.setuptools_scm] {key} = {value}")

    missing = tuple(target for target in targets if not (tree / target).exists())
    if not missing:
        return PreparationRequirement(
            required=False, kind="setuptools-scm-version-file", inference=tuple(inference)
        )
    inference.append("declared version file is absent from the frozen tree")
    return PreparationRequirement(
        required=True,
        kind="setuptools-scm-version-file",
        generated_paths=missing,
        tool_names=("setuptools-scm",),
        inference=tuple(inference),
    )


def missing_plugins(config: TestConfig, available: Sequence[str]) -> tuple[str, ...]:
    have = set(available)
    return tuple(plugin for plugin in config.required_plugins if plugin not in have)
