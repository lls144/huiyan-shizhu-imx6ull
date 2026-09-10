"""Background-thread TCP client; public send methods never block the GUI thread."""

from __future__ import annotations

import queue
import select
import socket
import threading
import time
import uuid
from collections import deque
from concurrent.futures import Future
from dataclasses import dataclass
from typing import Any

from .protocol import PROTOCOL_VERSION, encode_line


class ControllerClientError(RuntimeError):
    """A controller error response or a local client lifecycle failure."""


class ControllerTimeout(ControllerClientError):
    """A request exhausted its bounded ACK retry budget."""


@dataclass
class _PendingRequest:
    message: dict[str, Any]
    future: Future[dict[str, Any]]
    attempts: int = 0
    sent_at: float | None = None
    queued_for_write: bool = False


class ControllerClient:
    """Reconnect-capable M7 JSON Lines client owned by one network thread.

    Callers receive a Future immediately. The worker thread alone owns the
    socket, so PySide6 UI and vision worker threads never wait on network I/O.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 9000,
        *,
        connect_timeout: float = 0.25,
        ack_timeout: float = 0.25,
        reconnect_delay: float = 0.05,
        max_retries: int = 2,
    ) -> None:
        if not host:
            raise ValueError("host must not be empty")
        if not 1 <= port <= 65535:
            raise ValueError("port must be in [1, 65535]")
        if min(connect_timeout, ack_timeout, reconnect_delay) <= 0:
            raise ValueError("timeouts and reconnect_delay must be positive")
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        self.host = host
        self.port = port
        self.connect_timeout = connect_timeout
        self.ack_timeout = ack_timeout
        self.reconnect_delay = reconnect_delay
        self.max_retries = max_retries
        self._inbox: queue.Queue[_PendingRequest] = queue.Queue()
        self._stop = threading.Event()
        self._connected = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, name="controller-client", daemon=True)
            self._thread.start()

    def close(self, timeout: float = 2.0) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout)

    def wait_connected(self, timeout: float = 1.0) -> bool:
        return self._connected.wait(timeout)

    def send_enqueue(
        self,
        command_id: int,
        shape: str,
        *,
        source_event_id: int | None = None,
        source_object_id: int | None = None,
    ) -> Future[dict[str, Any]]:
        payload: dict[str, Any] = {"command_id": command_id, "shape": shape}
        if source_event_id is not None:
            payload["source_event_id"] = source_event_id
        if source_object_id is not None:
            payload["source_object_id"] = source_object_id
        return self._submit("enqueue", payload)

    def send_heartbeat(self) -> Future[dict[str, Any]]:
        return self._submit("heartbeat", {})

    def send_key_event(self, key: str) -> Future[dict[str, Any]]:
        return self._submit("key_event", {"key": key})

    def request_pipeline_state(self) -> Future[dict[str, Any]]:
        return self._submit("pipeline_state", {})

    def send_reset(self) -> Future[dict[str, Any]]:
        return self._submit("reset", {})

    def _submit(self, message_type: str, payload: dict[str, Any]) -> Future[dict[str, Any]]:
        self.start()
        request_id = str(uuid.uuid4())
        future: Future[dict[str, Any]] = Future()
        self._inbox.put(
            _PendingRequest(
                {"version": PROTOCOL_VERSION, "type": message_type, "request_id": request_id, **payload},
                future,
            )
        )
        return future

    @staticmethod
    def _close_socket(sock: socket.socket | None) -> None:
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass

    def _connect(self) -> socket.socket | None:
        try:
            sock = socket.create_connection((self.host, self.port), self.connect_timeout)
            sock.setblocking(False)
            self._connected.set()
            return sock
        except OSError:
            self._connected.clear()
            return None

    def _run(self) -> None:
        pending: dict[str, _PendingRequest] = {}
        outbound: deque[tuple[str, bytes]] = deque()
        socket_buffer = bytearray()
        sock: socket.socket | None = None
        next_connect = 0.0
        try:
            while not self._stop.is_set():
                while True:
                    try:
                        request = self._inbox.get_nowait()
                    except queue.Empty:
                        break
                    pending[request.message["request_id"]] = request

                now = time.monotonic()
                if sock is None and now >= next_connect:
                    sock = self._connect()
                    next_connect = now + self.reconnect_delay
                    if sock is not None:
                        for request_id, request in pending.items():
                            if not request.future.done():
                                request.queued_for_write = True
                                outbound.append((request_id, encode_line(request.message)))

                if sock is not None:
                    for request_id, request in pending.items():
                        if (
                            not request.future.done()
                            and request.sent_at is None
                            and not request.queued_for_write
                        ):
                            request.queued_for_write = True
                            outbound.append((request_id, encode_line(request.message)))

                for request_id, request in tuple(pending.items()):
                    if request.future.done():
                        pending.pop(request_id, None)
                        continue
                    if request.sent_at is not None and now - request.sent_at >= self.ack_timeout:
                        if request.attempts > self.max_retries:
                            request.future.set_exception(
                                ControllerTimeout(f"no ACK for request {request_id} after {request.attempts} sends")
                            )
                            pending.pop(request_id, None)
                        elif sock is not None and not request.queued_for_write:
                            request.sent_at = None
                            request.queued_for_write = True
                            outbound.append((request_id, encode_line(request.message)))

                if sock is None:
                    self._stop.wait(min(self.reconnect_delay, 0.02))
                    continue

                readable, writable, _ = select.select([sock], [sock] if outbound else [], [], 0.02)
                if writable and outbound:
                    request_id, data = outbound[0]
                    try:
                        sent = sock.send(data)
                    except OSError:
                        sent = 0
                    if sent <= 0:
                        self._close_socket(sock)
                        sock = None
                        self._connected.clear()
                        socket_buffer.clear()
                        outbound.clear()
                        for request in pending.values():
                            request.sent_at = None
                            request.queued_for_write = False
                        continue
                    if sent == len(data):
                        outbound.popleft()
                        request = pending.get(request_id)
                        if request is not None:
                            request.queued_for_write = False
                            request.sent_at = time.monotonic()
                            request.attempts += 1
                    else:
                        outbound[0] = (request_id, data[sent:])

                if readable:
                    try:
                        received = sock.recv(4096)
                    except BlockingIOError:
                        continue
                    except OSError:
                        received = b""
                    if not received:
                        self._close_socket(sock)
                        sock = None
                        self._connected.clear()
                        socket_buffer.clear()
                        outbound.clear()
                        for request in pending.values():
                            request.sent_at = None
                            request.queued_for_write = False
                        continue
                    socket_buffer.extend(received)
                    while b"\n" in socket_buffer:
                        line, _, remaining = socket_buffer.partition(b"\n")
                        socket_buffer = bytearray(remaining)
                        try:
                            import json

                            response = json.loads(line.decode("utf-8"))
                        except (UnicodeDecodeError, json.JSONDecodeError):
                            continue
                        if not isinstance(response, dict):
                            continue
                        request_id = response.get("request_id")
                        request = pending.pop(request_id, None) if isinstance(request_id, str) else None
                        if request is None or request.future.done():
                            continue
                        if response.get("type") == "error":
                            request.future.set_exception(
                                ControllerClientError(f"{response.get('code', 'ERROR')}: {response.get('message', '')}")
                            )
                        else:
                            request.future.set_result(response)
        finally:
            self._close_socket(sock)
            self._connected.clear()
            error = ControllerClientError("controller client closed")
            for request in pending.values():
                if not request.future.done():
                    request.future.set_exception(error)
            while True:
                try:
                    request = self._inbox.get_nowait()
                except queue.Empty:
                    break
                if not request.future.done():
                    request.future.set_exception(error)
