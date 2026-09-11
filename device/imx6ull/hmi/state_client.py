"""Non-blocking controller-state polling for the i.MX6ULL Qt HMI."""

from __future__ import annotations

import json
import queue
import socket
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional

from pc.communication.protocol import MAX_LINE_BYTES, PROTOCOL_VERSION, decode_line, encode_line


class StateClientError(RuntimeError):
    """A bounded local TCP request did not yield a valid controller response."""


@dataclass(frozen=True)
class StateClientSnapshot:
    online: bool
    pipeline_state: Optional[Dict[str, Any]]
    error: str


class ControllerStateClient:
    """Own short TCP requests in one worker so Qt's main thread never blocks.

    The HMI is only a Controller TCP client. It does not import ControllerCore,
    access `/dev/input`, GPIO, or Linux LED brightness paths.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 9000,
        request_timeout: float = 0.20,
        heartbeat_interval: float = 1.0,
    ) -> None:
        if not host or not 1 <= port <= 65535:
            raise ValueError("controller host and port are invalid")
        if request_timeout <= 0 or heartbeat_interval <= 0:
            raise ValueError("timeouts must be positive")
        self.host = host
        self.port = port
        self.request_timeout = request_timeout
        self.heartbeat_interval = heartbeat_interval
        self._requests = queue.Queue()  # type: queue.Queue
        self._stop = threading.Event()
        self._thread = None  # type: Optional[threading.Thread]
        self._lock = threading.Lock()
        self._snapshot = StateClientSnapshot(False, None, "not connected")
        self._state_pending = False
        self._heartbeat_pending = False
        self._next_heartbeat = 0.0

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, name="hmi-state-client", daemon=True)
            self._thread.start()

    def close(self, timeout: float = 1.0) -> None:
        self._stop.set()
        self._requests.put(None)
        thread = self._thread
        if thread is not None:
            thread.join(timeout)

    def snapshot(self) -> StateClientSnapshot:
        with self._lock:
            return self._snapshot

    def refresh(self) -> None:
        self.start()
        now = time.monotonic()
        with self._lock:
            if not self._state_pending:
                self._state_pending = True
                self._requests.put("state")
            if now >= self._next_heartbeat and not self._heartbeat_pending:
                self._heartbeat_pending = True
                self._next_heartbeat = now + self.heartbeat_interval
                self._requests.put("heartbeat")

    def request_reset(self) -> None:
        self.start()
        self._requests.put("reset")

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                request = self._requests.get(timeout=0.1)
            except queue.Empty:
                continue
            if request is None:
                continue
            try:
                response = self._request(request)
                self._handle_response(request, response)
            except (OSError, StateClientError, ValueError, UnicodeDecodeError) as error:
                self._set_offline(str(error))
            finally:
                with self._lock:
                    if request == "state":
                        self._state_pending = False
                    elif request == "heartbeat":
                        self._heartbeat_pending = False

    def _request(self, request_type: str) -> Dict[str, Any]:
        message = {
            "version": PROTOCOL_VERSION,
            "type": "pipeline_state" if request_type == "state" else request_type,
            "request_id": str(uuid.uuid4()),
        }
        with socket.create_connection((self.host, self.port), self.request_timeout) as connection:
            connection.settimeout(self.request_timeout)
            connection.sendall(encode_line(message))
            data = bytearray()
            while b"\n" not in data:
                chunk = connection.recv(4096)
                if not chunk:
                    raise StateClientError("controller closed TCP connection")
                data.extend(chunk)
                if len(data) > MAX_LINE_BYTES:
                    raise StateClientError("controller response exceeds protocol limit")
        line, _, _ = bytes(data).partition(b"\n")
        response = decode_line(line)
        if response.get("request_id") != message["request_id"]:
            raise StateClientError("controller response request_id mismatch")
        if response.get("type") == "error":
            raise StateClientError("{0}: {1}".format(response.get("code", "ERROR"), response.get("message", "")))
        return response

    def _handle_response(self, request: str, response: Dict[str, Any]) -> None:
        if request == "heartbeat":
            if response.get("type") != "ack" or response.get("status") != "alive":
                raise StateClientError("invalid heartbeat response")
            self._set_online_without_state()
            return
        state = response.get("pipeline_state")
        if not isinstance(state, dict):
            raise StateClientError("controller did not provide pipeline_state")
        self._set_online(state)

    def _set_online(self, state: Dict[str, Any]) -> None:
        with self._lock:
            self._snapshot = StateClientSnapshot(True, dict(state), "")

    def _set_online_without_state(self) -> None:
        with self._lock:
            self._snapshot = StateClientSnapshot(True, self._snapshot.pipeline_state, "")

    def _set_offline(self, error: str) -> None:
        with self._lock:
            self._snapshot = StateClientSnapshot(False, self._snapshot.pipeline_state, error)
