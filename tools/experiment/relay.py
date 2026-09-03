from __future__ import annotations

import json
import socket
import threading
from collections.abc import Sequence

from .profile import RunnerError, split_target

_MAX_RELAY_HEADER = 16 * 1024


def log_relay(event: str, **fields: object) -> None:
    payload: dict[str, object] = {"event": event, **fields}
    print(json.dumps(payload, sort_keys=True), flush=True)


def recv_header(client: socket.socket) -> bytes:
    data = bytearray()
    while b"\r\n\r\n" not in data:
        chunk = client.recv(4096)
        if not chunk:
            break
        data.extend(chunk)
        if len(data) > _MAX_RELAY_HEADER:
            raise RunnerError("relay-header-too-large")
    return bytes(data)


def relay_one_way(source: socket.socket, destination: socket.socket) -> None:
    try:
        while True:
            data = source.recv(64 * 1024)
            if not data:
                break
            destination.sendall(data)
    except OSError:
        pass
    finally:
        try:
            destination.shutdown(socket.SHUT_WR)
        except OSError:
            pass


def handle_relay_client(client: socket.socket, allow: frozenset[str]) -> None:
    peer = repr(client.getpeername())
    target = ""
    try:
        client.settimeout(20)
        header = recv_header(client)
        first_line = header.split(b"\r\n", 1)[0].decode("ascii", errors="replace")
        parts = first_line.split()
        if len(parts) != 3 or parts[0] != "CONNECT":
            client.sendall(
                b"HTTP/1.1 405 Method Not Allowed\r\nConnection: close\r\n\r\n"
            )
            log_relay("REFUSED", peer=peer, reason="connect-only")
            return
        target = parts[1]
        if target not in allow:
            client.sendall(b"HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n")
            log_relay("REFUSED", peer=peer, target=target, reason="not-allowlisted")
            return
        host, port = split_target(target)
        upstream = socket.create_connection((host, port), timeout=20)
        with upstream:
            client.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            log_relay("ADMITTED", peer=peer, target=target)
            client.settimeout(None)
            upstream.settimeout(None)
            outgoing = threading.Thread(
                target=relay_one_way,
                args=(client, upstream),
                daemon=True,
            )
            incoming = threading.Thread(
                target=relay_one_way,
                args=(upstream, client),
                daemon=True,
            )
            outgoing.start()
            incoming.start()
            outgoing.join()
            incoming.join()
            log_relay("CLOSED", peer=peer, target=target)
    except (OSError, RunnerError) as exc:
        log_relay("ERROR", peer=peer, target=target, reason=type(exc).__name__)


def _relay_client_context(client: socket.socket, allow: frozenset[str]) -> None:
    with client:
        handle_relay_client(client, allow)


def relay_server(listen: str, port: int, allow: Sequence[str]) -> int:
    checked = frozenset(allow)
    for target in checked:
        split_target(target)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((listen, port))
        server.listen(32)
        log_relay("READY", listen=listen, port=port, allow=sorted(checked))
        while True:
            client, _ = server.accept()
            thread = threading.Thread(
                target=_relay_client_context,
                args=(client, checked),
                daemon=True,
            )
            thread.start()
