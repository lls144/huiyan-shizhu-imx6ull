"""Desktop Linux TCP adapter for the M8 FIFO and pipeline controller core."""

from __future__ import annotations

import selectors
import socket
import threading
import argparse
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Optional, Tuple

from device.imx6ull.core.controller import ControllerCore
from pc.communication.protocol import (
    MAX_LINE_BYTES,
    PROTOCOL_VERSION,
    ProtocolError,
    decode_line,
    encode_line,
    error_message,
    request_id_from,
    validate_request,
)


@dataclass
class _Connection:
    socket: socket.socket
    received: bytearray = field(default_factory=bytearray)
    outgoing: Deque[bytes] = field(default_factory=deque)


class DesktopControllerServer:
    """Selector-based TCP server suitable for localhost integration tests.

    It validates JSON Lines and delegates accepted requests to ControllerCore.
    GPIO, Qt LCD and ARM deployment remain intentionally outside this module.
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 9000, *, core: Optional[ControllerCore] = None) -> None:
        if not host:
            raise ValueError("host must not be empty")
        if not 0 <= port <= 65535:
            raise ValueError("port must be in [0, 65535]")
        self.host = host
        self.port = port
        self._selector = selectors.DefaultSelector()
        self._listener = None  # type: Optional[socket.socket]
        self._connections = {}  # type: Dict[socket.socket, _Connection]
        self.core = core or ControllerCore()
        self._stop = threading.Event()
        self._disconnect_clients = threading.Event()
        self._thread = None  # type: Optional[threading.Thread]
        self._lock = threading.Lock()

    @property
    def address(self) -> Tuple[str, int]:
        if self._listener is None:
            raise RuntimeError("server is not running")
        host, port = self._listener.getsockname()[:2]
        return str(host), int(port)

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind((self.host, self.port))
            listener.listen()
            listener.setblocking(False)
            self._listener = listener
            self._selector.register(listener, selectors.EVENT_READ, data=None)
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, name="desktop-controller-server", daemon=True)
            self._thread.start()

    def close(self, timeout: float = 2.0) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout)

    def disconnect_clients(self) -> None:
        """Cause active peers to reconnect; used only by Desktop Linux tests."""

        self._disconnect_clients.set()

    def __enter__(self) -> "DesktopControllerServer":
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _run(self) -> None:
        try:
            while not self._stop.is_set():
                if self._disconnect_clients.is_set():
                    self._disconnect_clients.clear()
                    for connection in tuple(self._connections.values()):
                        self._close_connection(connection)
                for key, mask in self._selector.select(timeout=0.05):
                    if key.data is None:
                        self._accept(key.fileobj)
                        continue
                    connection: _Connection = key.data
                    if mask & selectors.EVENT_READ:
                        self._read(connection)
                    if connection.socket in self._connections and mask & selectors.EVENT_WRITE:
                        self._write(connection)
        finally:
            for connection in tuple(self._connections.values()):
                self._close_connection(connection)
            listener = self._listener
            if listener is not None:
                try:
                    self._selector.unregister(listener)
                except Exception:
                    pass
                listener.close()
            self._listener = None
            self._selector.close()

    def _accept(self, listener: socket.socket) -> None:
        try:
            peer, _ = listener.accept()
        except BlockingIOError:
            return
        peer.setblocking(False)
        connection = _Connection(peer)
        self._connections[peer] = connection
        self._selector.register(peer, selectors.EVENT_READ, data=connection)

    def _read(self, connection: _Connection) -> None:
        try:
            data = connection.socket.recv(4096)
        except BlockingIOError:
            return
        except OSError:
            self._close_connection(connection)
            return
        if not data:
            self._close_connection(connection)
            return
        connection.received.extend(data)
        if len(connection.received) > MAX_LINE_BYTES and b"\n" not in connection.received:
            self._queue(connection, error_message("LINE_TOO_LONG", "JSON Line exceeds 16 KiB"))
            return
        while b"\n" in connection.received:
            line, _, remainder = connection.received.partition(b"\n")
            connection.received = bytearray(remainder)
            if line.endswith(b"\r"):
                line = line[:-1]
            if len(line) > MAX_LINE_BYTES:
                self._queue(connection, error_message("LINE_TOO_LONG", "JSON Line exceeds 16 KiB"))
                continue
            self._handle_line(connection, line)

    def _handle_line(self, connection: _Connection, line: bytes) -> None:
        message = None  # type: Optional[Dict[str, Any]]
        try:
            message = decode_line(line)
            validate_request(message)
        except ProtocolError as error:
            self._queue(connection, error_message(error.code, str(error), request_id_from(message)))
            return

        request_id = message["request_id"]
        message_type = message["type"]
        if message_type == "enqueue":
            result = self.core.enqueue(
                message["command_id"],
                message["shape"],
                source_event_id=message.get("source_event_id"),
                source_object_id=message.get("source_object_id"),
            )
            self._queue(
                connection,
                {
                    "version": PROTOCOL_VERSION,
                    "type": "ack",
                    "request_id": request_id,
                    "command_id": message["command_id"],
                    "status": result.status,
                    "pipeline_state": result.pipeline_state,
                },
            )
        elif message_type == "heartbeat":
            self._queue(
                connection,
                {"version": PROTOCOL_VERSION, "type": "ack", "request_id": request_id, "status": "alive"},
            )
        elif message_type == "reset":
            result = self.core.reset()
            self._queue(
                connection,
                {
                    "version": PROTOCOL_VERSION,
                    "type": "ack",
                    "request_id": request_id,
                    "status": result.status,
                    "pipeline_state": result.pipeline_state,
                },
            )
        elif message_type == "key_event":
            result = self.core.handle_key(message["key"])
            if result.status == "sorted":
                self._queue(
                    connection,
                    {
                        "version": PROTOCOL_VERSION,
                        "type": "sorted",
                        "request_id": request_id,
                        "command": result.command.to_record() if result.command is not None else None,
                        "branch": result.branch,
                        "pipeline_state": result.pipeline_state,
                    },
                )
            elif result.status in {"wrong_station", "empty"}:
                code = "WRONG_STATION" if result.status == "wrong_station" else "EMPTY_QUEUE"
                self._queue(
                    connection,
                    {
                        **error_message(code, result.status.replace("_", " "), request_id),
                        "pipeline_state": result.pipeline_state,
                    },
                )
            else:
                self._queue(
                    connection,
                    {
                        "version": PROTOCOL_VERSION,
                        "type": "pipeline_state",
                        "request_id": request_id,
                        "status": result.status,
                        "state": result.pipeline_state["station"],
                        "pipeline_state": result.pipeline_state,
                    },
                )
        else:  # pipeline_state query
            state = self.core.pipeline_state()
            self._queue(
                connection,
                {
                    "version": PROTOCOL_VERSION,
                    "type": "pipeline_state",
                    "request_id": request_id,
                    "state": state["station"],
                    "pipeline_state": state,
                },
            )

    def _queue(self, connection: _Connection, message: Dict[str, Any]) -> None:
        connection.outgoing.append(encode_line(message))
        try:
            self._selector.modify(connection.socket, selectors.EVENT_READ | selectors.EVENT_WRITE, data=connection)
        except KeyError:
            pass

    def _write(self, connection: _Connection) -> None:
        if not connection.outgoing:
            return
        data = connection.outgoing[0]
        try:
            sent = connection.socket.send(data)
        except (BlockingIOError, InterruptedError):
            return
        except OSError:
            self._close_connection(connection)
            return
        if sent == len(data):
            connection.outgoing.popleft()
        else:
            connection.outgoing[0] = data[sent:]
        if not connection.outgoing and connection.socket in self._connections:
            self._selector.modify(connection.socket, selectors.EVENT_READ, data=connection)

    def _close_connection(self, connection: _Connection) -> None:
        self._connections.pop(connection.socket, None)
        try:
            self._selector.unregister(connection.socket)
        except Exception:
            pass
        try:
            connection.socket.close()
        except OSError:
            pass


def main() -> int:
    """Run the M8 Desktop Linux controller server until interrupted by its operator."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=9000)
    args = parser.parse_args()
    server = DesktopControllerServer(args.host, args.port)
    server.start()
    host, port = server.address
    print(f"M8 Desktop controller listening on {host}:{port}")
    try:
        while True:
            threading.Event().wait(3600)
    except KeyboardInterrupt:
        return 0
    finally:
        server.close()


if __name__ == "__main__":
    raise SystemExit(main())
