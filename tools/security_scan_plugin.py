"""The protected detect-secrets plugin for the forms its default detectors miss (#389 H-PYSEC-2; Decision 0122).

Measured on the default plugins (#389 6506406920): a literal assignment in a Dockerfile `ENV`/`ARG`, a Makefile, or a
YAML mapping whose name ends in token/secret/password/key, and an encrypted PKCS#8 private key. The scope is closed:
- Dockerfiles (`Dockerfile*`, `*.dockerfile`): `ENV`/`ARG` `NAME=value` pairs, quoted or bare, and `ENV NAME value`;
- Makefiles (`Makefile`, `GNUmakefile`, `makefile`, `*.mk`): `NAME = | := | ::= | ?= | += | != value`;
- YAML (`*.yml`, `*.yaml`): one-line `NAME: value` mappings, plain or quoted;
- any file: a `-----BEGIN ENCRYPTED PRIVATE KEY-----` header followed by a base64 body line.

A name qualifies when its last `_`/`-` part is token, secret, password, passwd or pwd, or it ends in api_key,
access_key, private_key, client_secret or auth_token. A value is benign, and never reported, when it is empty, a
reference (`$`, `${...}`, `$(...)`, `${{ ... }}`, `%...%`), a path, a placeholder, numeric, or shorter than 8.
Continuations, heredocs, block or flow YAML scalars and Makefile `define` blocks are not read, and not claimed.

The scanner pins these bytes (tools/security_scan.py, PLUGIN_PINS) and loads only a verified copy of them."""

from __future__ import annotations

import re
from collections.abc import Generator, Iterable
from typing import Any

from detect_secrets.core.potential_secret import PotentialSecret
from detect_secrets.plugins.base import BasePlugin

_NAME = re.compile(
    r"(?i)(?:^|[_-])(?:token|secret|password|passwd|pwd)$"
    r"|(?i:api[_-]?key|access[_-]?key|private[_-]?key|client[_-]?secret|auth[_-]?token)$"
)
_PLACEHOLDER = re.compile(
    r"(?i)^(?:<[^>]*>|change-?me|example|dummy|placeholder|null|none|~|true|false|x{3,}|\*+)$"
)
_REFERENCE = re.compile(r"\$|%[A-Za-z_]+%")
_DOCKER_LINE = re.compile(r"^\s*(?:ENV|ARG)\s", re.IGNORECASE)
_DOCKER_PAIR = re.compile(r"""([A-Za-z_][A-Za-z0-9_]*)=(?:"([^"]*)"|'([^']*)'|(\S+))""")
_DOCKER_LEGACY = re.compile(
    r"""^\s*ENV\s+([A-Za-z_][A-Za-z0-9_]*)\s+(?!.*=)(?:"([^"]*)"|'([^']*)'|(\S+))\s*$""",
    re.IGNORECASE,
)
_MAKE = re.compile(
    r"^\s*(?:export\s+|override\s+)?([A-Za-z_][A-Za-z0-9_.-]*)\s*(?::{1,2}=|\?=|\+=|!=|=)\s*(.*?)\s*$"
)
_YAML = re.compile(
    r"""^\s*(?:-\s+)?([A-Za-z_][A-Za-z0-9_.-]*)\s*:\s+(?:"([^"]*)"|'([^']*)'|([^#\s][^#]*?))\s*(?:#.*)?$"""
)
_ENCRYPTED_HEADER = "-----BEGIN ENCRYPTED PRIVATE KEY-----"
_BASE64_BODY = re.compile(r"^[A-Za-z0-9+/=]{40,}$")


def _kind(filename: str) -> str | None:
    base = filename.replace("\\", "/").rsplit("/", 1)[-1]
    if base.startswith("Dockerfile") or base.endswith(".dockerfile"):
        return "docker"
    if base in ("Makefile", "GNUmakefile", "makefile") or base.endswith(".mk"):
        return "make"
    if base.endswith((".yml", ".yaml")):
        return "yaml"
    return None


def _secret_value(value: str) -> bool:
    text = value.strip()
    return not (
        len(text) < 8
        or text.isdigit()
        or _REFERENCE.search(text)
        or text.startswith(("/", "./", "~/"))
        or _PLACEHOLDER.match(text)
    )


def _first_group(match: re.Match[str], first: int) -> str:
    return next(group for group in match.groups()[first:] if group is not None)


def _docker_values(line: str) -> list[str]:
    if not _DOCKER_LINE.match(line):
        return []
    pairs = [(m[1], _first_group(m, 1)) for m in _DOCKER_PAIR.finditer(line)]
    legacy = _DOCKER_LEGACY.match(line)
    if legacy and not pairs:
        pairs = [(legacy[1], _first_group(legacy, 1))]
    return [
        value for name, value in pairs if _NAME.search(name) and _secret_value(value)
    ]


def _make_values(line: str) -> list[str]:
    match = _MAKE.match(line)
    if match is None or not _NAME.search(match[1]):
        return []
    value = match[2].strip().strip("'\"")
    return [value] if _secret_value(value) else []


def _yaml_values(line: str) -> list[str]:
    match = _YAML.match(line)
    if match is None or not _NAME.search(match[1]):
        return []
    value = _first_group(match, 1)
    return [value] if _secret_value(value) else []


_BY_KIND = {"docker": _docker_values, "make": _make_values, "yaml": _yaml_values}


def _encrypted_key(line: str, following: str | None) -> list[str]:
    if _ENCRYPTED_HEADER not in line or following is None:
        return []
    body = following.strip()
    return [body] if _BASE64_BODY.match(body) else []


def _following_line(context: Any) -> str | None:
    lines = getattr(context, "lines", None)
    index = getattr(context, "target_index", None)
    if (
        not isinstance(lines, list)
        or not isinstance(index, int)
        or index + 1 >= len(lines)
    ):
        return None
    following = lines[index + 1]
    return following if isinstance(following, str) else None


def secret_values(filename: str, line: str, following: str | None) -> Iterable[str]:
    """The secret-like literals on `line` of `filename`; `following` is the next line, for an encrypted key."""
    found = _encrypted_key(line, following)
    reader = _BY_KIND.get(_kind(filename) or "")
    if reader is not None:
        found += reader(line)
    return found


class GnostoaAssignmentDetector(BasePlugin):
    """Literal secret-like assignments in Dockerfiles, Makefiles and YAML, and encrypted PKCS#8 private keys."""

    secret_type = "Gnostoa Assignment Secret"  # pragma: allowlist secret -- the detector's metadata label, not a credential

    def analyze_string(self, string: str) -> Generator[str, None, None]:
        """No file type, so nothing is claimed for a bare string."""
        del string
        yield from ()

    def analyze_line(
        self,
        filename: str,
        line: str,
        line_number: int = 0,
        context: Any = None,
        **kwargs: Any,
    ) -> set[PotentialSecret]:
        del kwargs
        return {
            PotentialSecret(
                type=self.secret_type,
                filename=filename,
                secret=value,
                line_number=line_number,
            )
            for value in secret_values(filename, line, _following_line(context))
        }
