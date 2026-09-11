"""Single-host experimental storage; cooperative writers, no security boundary."""

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read(path: Path) -> Any:
    return json.loads(path.read_bytes())


def write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".capture-")
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(name).unlink(missing_ok=True)


def write(path: Path, value: Any) -> None:
    write_bytes(path, (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode())


def native_events(data: bytes) -> list[dict[str, Any]]:
    events = [json.loads(line) for line in data.splitlines() if line.strip()]
    if any(not isinstance(event, dict) for event in events):
        raise ValueError("Native stream contains a non-object event")
    return events


def normalize(data: bytes, adapter: str) -> dict[str, Any]:
    """Retained native response -> original review; never a semantic verdict."""
    if adapter == "plain":
        value = json.loads(data)
    elif adapter == "codex-jsonl":
        events = native_events(data)
        if not any(event.get("type") == "turn.completed" for event in events):
            raise ValueError("No completed Codex turn")
        messages = [
            event["item"]["text"]
            for event in events
            if event.get("type") == "item.completed"
            and isinstance(event.get("item"), dict)
            and event.get("item", {}).get("type") == "agent_message"
        ]
        if not messages:
            raise ValueError("No final agent message")
        value = json.loads(messages[-1])
    elif adapter == "claude-jsonl":
        events = native_events(data)
        results = [event for event in events if event.get("type") == "result"]
        if len(results) != 1 or results[0].get("is_error") is not False:
            raise ValueError("No unique successful Claude result")
        value = json.loads(results[0]["result"])
    else:
        raise ValueError("Unqualified normalizer")
    if not isinstance(value, dict) or not isinstance(value.get("findings"), list):
        raise ValueError("Review must explicitly supply findings")
    if not isinstance(value.get("recommendation"), str):
        raise ValueError("Review must explicitly supply recommendation")
    ids = set()
    for finding in value["findings"]:
        if (
            not isinstance(finding, dict)
            or not isinstance(finding.get("id"), str)
            or not isinstance(finding.get("text"), str)
            or not isinstance(finding.get("material"), bool)
            or finding["id"] in ids
        ):
            raise ValueError("Malformed or duplicate finding")
        ids.add(finding["id"])
    return value
