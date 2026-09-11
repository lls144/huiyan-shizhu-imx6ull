"""Controller-side asynchronous output dispatcher; it never writes GPIO/sysfs."""

from __future__ import annotations

import socket
import threading
from abc import ABC, abstractmethod
from typing import Optional

from device.imx6ull.core.models import OutputEvent

from .protocol import encode_output_event


class IBranchOutputBackend(ABC):
    @abstractmethod
    def send(self, event: OutputEvent) -> None:
        """Deliver one already-authorized output event. May raise OSError."""


class NullBranchOutputBackend(IBranchOutputBackend):
    """Desktop/local backend that intentionally produces no hardware output."""

    def send(self, event: OutputEvent) -> None:
        del event


class UnixSocketBranchOutputBackend(IBranchOutputBackend):
    """Unprivileged client for the fixed root-owned LED-helper socket."""

    def __init__(self, socket_path: str, timeout_seconds: float = 0.1) -> None:
        if not socket_path:
            raise ValueError("socket_path must not be empty")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.socket_path = socket_path
        self.timeout_seconds = timeout_seconds

    def send(self, event: OutputEvent) -> None:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            client.settimeout(self.timeout_seconds)
            client.connect(self.socket_path)
            client.sendall(encode_output_event(event))
        finally:
            client.close()


class BranchOutputDispatcher:
    """Move output I/O to one daemon worker so Controller processing never waits."""

    def __init__(self, backend: IBranchOutputBackend) -> None:
        self._backend = backend
        self._condition = threading.Condition()
        self._pending = None  # type: Optional[OutputEvent]
        self._closed = False
        self._thread = None  # type: Optional[threading.Thread]
        self._last_error = None  # type: Optional[OSError]

    @property
    def last_error(self) -> Optional[OSError]:
        with self._condition:
            return self._last_error

    @property
    def backend(self) -> IBranchOutputBackend:
        """Expose the selected non-privileged backend for composition tests."""

        return self._backend

    def start(self) -> None:
        with self._condition:
            if self._closed:
                raise RuntimeError("dispatcher is closed")
            if self._thread is not None:
                return
            self._thread = threading.Thread(target=self._run, name="huiyan-branch-output", daemon=True)
            self._thread.start()

    def submit(self, event: OutputEvent) -> None:
        """Replace pending work; a newer branch deliberately supersedes an older one."""

        with self._condition:
            if self._closed:
                return
            if self._thread is None:
                self.start()
            self._pending = event
            self._condition.notify()

    def close(self, timeout: float = 1.0) -> None:
        with self._condition:
            self._closed = True
            self._condition.notify_all()
            thread = self._thread
        if thread is not None:
            thread.join(timeout)

    def _run(self) -> None:
        while True:
            with self._condition:
                while self._pending is None and not self._closed:
                    self._condition.wait()
                if self._closed:
                    return
                event = self._pending
                self._pending = None
            try:
                self._backend.send(event)
            except OSError as error:
                with self._condition:
                    self._last_error = error
