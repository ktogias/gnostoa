import hashlib
import os
import socket
from pathlib import Path


def read_bytes(path: str) -> bytes:
    return Path(path).read_bytes()


def write_bytes(path: str, payload: bytes) -> None:
    Path(path).write_bytes(payload)


def inherited_environment() -> dict[str, str]:
    return dict(os.environ)


def connect(host: str, port: int) -> None:
    with socket.create_connection((host, port), timeout=2) as connection:
        connection.sendall(b"unsafe-egress")


def bare_sha256(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def materialize_then_check(path: str, limit: int) -> dict[str, int | bool]:
    payload = Path(path).read_bytes()
    return {
        "materialized_bytes": len(payload),
        "oversize": len(payload) > limit,
    }
