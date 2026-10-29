"""The protected detect-secrets plugin for the forms its default detectors miss (#389 H-PYSEC-2; Decision 0122).

Measured on the default plugins (#389 6506406920): a literal assignment in a Dockerfile `ENV`/`ARG`, a Makefile, or a
YAML mapping whose name ends in token/secret/password/key, and an encrypted PKCS#8 private key. The scope is closed:
- Dockerfiles (`Dockerfile*`, `*.dockerfile`): `ENV`/`ARG` `NAME=value` pairs, quoted or bare, and `ENV NAME value`;
- Makefiles (`Makefile`, `GNUmakefile`, `makefile`, `*.mk`): `NAME = | := | ::= | ?= | += | != value`;
- YAML (`*.yml`, `*.yaml`): one-line `NAME: value` mappings, plain or quoted, a comment starting at a `#` after
  whitespace;
- any file: an encrypted PKCS#8 private key's BEGIN header line followed by a base64 body line.

A name qualifies when its last `_`/`-` part is token, secret, password, passwd or pwd, or it ends in api_key,
access_key, private_key, client_secret or auth_token. A value is benign, and never reported, when it is empty, a
reference (a leading `$NAME`, any `${...}` or `$(...)`, `${{ ... }}`, `%NAME%`), a filesystem path made only of path
segments, a placeholder, numeric, or shorter than 8. A `$` in any other place is part of the value.
Continuations, heredocs, block or flow YAML scalars and Makefile `define` blocks are not read, and not claimed.

Each line is read in linear time: a short anchored head pattern per form, then string operations, so no pattern
backtracks over a long run (Sonar S8786 and Revix on #470).

The scanner pins these bytes (tools/security_scan.py, PLUGIN_PINS) and loads only a verified copy of them."""

from __future__ import annotations

import re
from collections.abc import Generator, Iterable
from typing import Any

from detect_secrets.core.potential_secret import PotentialSecret
from detect_secrets.plugins.base import BasePlugin

_NAME = re.compile(
    r"(?i)(?:^|[_-])(?:token|secret|password|passwd|pwd)$"
    r"|(?:api[_-]?key|access[_-]?key|private[_-]?key|client[_-]?secret|auth[_-]?token)$"
)
_PLACEHOLDER_WORDS = frozenset(
    {
        "changeme",
        "change-me",
        "example",
        "dummy",
        "placeholder",
        "null",
        "none",
        "~",
        "true",
        "false",
    }
)
_REFERENCE = re.compile(r"\$[{(]|^\$[A-Za-z_]|%[A-Za-z_]+%")
_PATH = re.compile(r"(?:\.{0,2}|~)(?:/[\w.-]+)+/?", re.ASCII)
_IDENTIFIER = re.compile(r"[A-Za-z_]\w*", re.ASCII)
_DOCKER_LINE = re.compile(r"^\s*(?:ENV|ARG)\s", re.IGNORECASE)
# A name starts a word, so a long word run is scanned once, never from each of its positions (quadratic).
_DOCKER_PAIR = re.compile(
    r"""(?<!\w)([A-Za-z_]\w*)=(?:"([^"]*)"|'([^']*)'|(\S+))""", re.ASCII
)
_MAKE_HEAD = re.compile(
    r"(?:(?:export|override)\s+)?([A-Za-z_][\w.-]*)\s*(?::{1,2}|[?+!])?=", re.ASCII
)
_YAML_HEAD = re.compile(r"(?:-\s+)?([A-Za-z_][\w.-]*)\s*:\s", re.ASCII)
_YAML_COMMENT = re.compile(r"\s#")
# The header from parts, so this file holds no key header a scanner would take for a key.
_ENCRYPTED_HEADER = "-----BEGIN " + "ENCRYPTED PRIVATE KEY-----"
_BASE64_BODY = re.compile(r"^[A-Za-z0-9+/=]{40,}$")
_LABEL = "Gnostoa Assignment Secret"


def _kind(filename: str) -> str | None:
    base = filename.replace("\\", "/").rsplit("/", 1)[-1]
    if base.startswith("Dockerfile") or base.endswith(".dockerfile"):
        return "docker"
    if base in ("Makefile", "GNUmakefile", "makefile") or base.endswith(".mk"):
        return "make"
    if base.endswith((".yml", ".yaml")):
        return "yaml"
    return None


def _placeholder(text: str) -> bool:
    lowered = text.lower()
    return (
        lowered in _PLACEHOLDER_WORDS
        or (text.startswith("<") and text.endswith(">") and ">" not in text[1:-1])
        or (len(lowered) >= 3 and set(lowered) == {"x"})
        or set(text) == {"*"}
    )


def _secret_value(value: str) -> bool:
    text = value.strip()
    return not (
        len(text) < 8
        or text.isdigit()
        or _REFERENCE.search(text)
        or _PATH.fullmatch(text)
        or _placeholder(text)
    )


def _first_group(match: re.Match[str], first: int) -> str:
    return next(group for group in match.groups()[first:] if group is not None)


def _single_value(rest: str) -> str | None:
    """A double-quoted, a single-quoted, or one bare word: the forms a legacy `ENV NAME value` takes."""
    quoted = len(rest) >= 2 and rest[0] in "\"'" and rest[-1] == rest[0]
    if quoted and rest[0] not in rest[1:-1]:
        return rest[1:-1]
    return rest if rest and not any(c.isspace() for c in rest) else None


def _docker_legacy(line: str) -> list[tuple[str, str]]:
    parts = line.split(None, 2)
    if len(parts) != 3 or parts[0].upper() != "ENV" or "=" in line:
        return []
    if not _IDENTIFIER.fullmatch(parts[1]):
        return []
    value = _single_value(parts[2].rstrip())
    return [] if value is None else [(parts[1], value)]


def _docker_values(line: str) -> list[str]:
    if not _DOCKER_LINE.match(line):
        return []
    pairs = [(m[1], _first_group(m, 1)) for m in _DOCKER_PAIR.finditer(line)]
    pairs = pairs or _docker_legacy(line)
    return [
        value for name, value in pairs if _NAME.search(name) and _secret_value(value)
    ]


def _make_values(line: str) -> list[str]:
    text = line.lstrip()
    match = _MAKE_HEAD.match(text)
    if match is None or not _NAME.search(match[1]):
        return []
    value = text[match.end() :].strip().strip("'\"")
    return [value] if _secret_value(value) else []


def _yaml_scalar(rest: str) -> str | None:
    """The value after `NAME:`: a quoted scalar followed by nothing or a comment, else the plain scalar up to the
    first `#` after whitespace, where YAML starts a comment."""
    if not rest or rest.startswith("#"):
        return None
    if rest[0] in "\"'":
        end = rest.find(rest[0], 1)
        tail = rest[end + 1 :].lstrip() if end != -1 else None
        if tail is not None and (not tail or tail.startswith("#")):
            return rest[1:end]
    return _YAML_COMMENT.split(rest, 1)[0].rstrip() or None


def _yaml_values(line: str) -> list[str]:
    text = line.lstrip()
    match = _YAML_HEAD.match(text)
    if match is None or not _NAME.search(match[1]):
        return []
    value = _yaml_scalar(text[match.end() :].strip())
    return [value] if value is not None and _secret_value(value) else []


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
    """The secret-like literals on `line` of `filename`; `following` is the next line, for an encrypted key. Public,
    as the plugin's tested reading (tests/test_security_scan_plugin.py)."""
    found = _encrypted_key(line, following)
    reader = _BY_KIND.get(_kind(filename) or "")
    if reader is not None:
        found += reader(line)
    return found


class GnostoaAssignmentDetector(BasePlugin):
    """Literal secret-like assignments in Dockerfiles, Makefiles and YAML, and encrypted PKCS#8 private keys."""

    secret_type = _LABEL

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
