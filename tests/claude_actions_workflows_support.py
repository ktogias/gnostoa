"""What other test modules share from tests/test_claude_actions_workflows.py, outside the discovered test modules (#389 N1b; Decision 0128)."""

from __future__ import annotations

import re

_PROMPT_EXPRESSION = re.compile(r"\$\{\{(.+?)\}\}", re.DOTALL)


_PROMPT_LITERAL = re.compile(r"'(?:[^']|'')*'")


_SECRETS_CONTEXT = re.compile(r"(?<![\w.])secrets\b", re.IGNORECASE)


_NAMED_SECRET = re.compile(
    r"\s*(?:\.\s*([A-Za-z_][A-Za-z0-9_]*)\b(?!\s*\*)|\[\s*'((?:[^']|'')*)'\s*\])"
)


def _secret_references(expression: str) -> list[str | None]:
    """Return, for each `secrets` reference in ``expression``, the secret it names.

    None stands for a reference that names no single secret, which reaches them all.
    The first detector listed the spellings that reach the credential, and each review
    found another: an index, whole-context `toJSON(secrets)`, then the same with a
    space before the parenthesis. The spellings that name one secret are the small
    set, so those are recognised and everything else is treated as reaching it.
    """
    literals = [match.span() for match in _PROMPT_LITERAL.finditer(expression)]
    names: list[str | None] = []
    for match in _SECRETS_CONTEXT.finditer(expression):
        if any(start <= match.start() < end for start, end in literals):
            continue
        named = _NAMED_SECRET.match(expression, match.end())
        if named is None:
            names.append(None)
        elif named.group(1) is not None:
            names.append(named.group(1))
        else:
            names.append(named.group(2).replace("''", "'"))
    return names


def _expression_secrets(text: str) -> list[str | None]:
    """Return the secret each expression in ``text`` names, as `_secret_references`."""
    return [
        name
        for expression in _PROMPT_EXPRESSION.findall(text)
        for name in _secret_references(expression)
    ]
