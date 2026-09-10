"""Two cooperative scripted protocols; neither confers acceptance authority."""

from collections.abc import Iterator
from typing import Any


def tagged_events(stream: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
    """Decode individually tagged command, capability and terminal records."""
    for record in stream:
        if record["type"] == "instruction":
            operation = record["operation"]
            if operation == "check":
                yield {"kind": "worker-check-requested"}
            elif operation == "dispatch":
                yield {"kind": "dispatch-requested"}
            else:
                raise ValueError(f"Unknown tagged instruction: {operation}")
        elif record["type"] == "capability" and record["available"] is False:
            yield {
                "kind": "runtime-guarantee-lost",
                "capability": record["name"],
            }
        elif record["type"] == "terminal":
            yield {
                "kind": "completed",
                "status": "completed" if record["status"] == "done" else "failed",
            }
        else:
            raise ValueError(f"Unknown tagged record: {record}")


def batched_events(stream: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Decode tuple envelopes, including several operations within one batch."""
    for channel, payload in stream["messages"]:
        if channel == "work":
            for command in payload["queued"]:
                if command == "request-check":
                    yield {"kind": "worker-check-requested"}
                elif command == "followup":
                    yield {"kind": "dispatch-requested"}
                else:
                    raise ValueError(f"Unknown batched command: {command}")
        elif channel == "health":
            for capability in payload["lost"]:
                yield {"kind": "runtime-guarantee-lost", "capability": capability}
        elif channel == "done":
            yield {
                "kind": "completed",
                "status": "completed" if payload["exit_code"] == 0 else "failed",
            }
        else:
            raise ValueError(f"Unknown batched channel: {channel}")


ADAPTERS = {"tagged": tagged_events, "batched": batched_events}
