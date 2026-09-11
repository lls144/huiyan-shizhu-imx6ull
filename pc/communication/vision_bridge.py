"""Explicit M4 lifecycle-event bridge to the M7 Controller TCP client.

This module deliberately accepts only confirmed ``OBJECT_ENTER`` events.  It
does not participate in recognition, tracking, FIFO handling, or the pipeline
FSM; it converts one already-confirmed vision fact into one existing enqueue
request and records the Controller acknowledgement for the live-session log.
"""

from __future__ import annotations

import json
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from pc.events.models import EventType, VisionEvent

from .controller_client import ControllerClient


SORTABLE_SHAPES = frozenset(("triangle", "circle", "rectangle"))


class ControllerEnqueueRejected(RuntimeError):
    """A valid Controller ACK that did not accept a vision command."""

    def __init__(self, command_id: int, response: Dict[str, Any]) -> None:
        self.command_id = command_id
        self.response = response
        self.status = str(response.get("status", "unknown"))
        super().__init__(f"Controller did not accept vision enqueue {command_id}: {response!r}")


@dataclass(frozen=True)
class ControllerConnectionConfig:
    """Connection settings kept in a PC-side JSON file, not vision code."""

    host: str
    port: int
    connect_timeout: float = 1.0
    ack_timeout: float = 1.0
    reconnect_delay: float = 0.1
    max_retries: int = 2

    def validate(self) -> None:
        if not self.host:
            raise ValueError("controller host must not be empty")
        if not 1 <= self.port <= 65535:
            raise ValueError("controller port must be in [1, 65535]")
        if min(self.connect_timeout, self.ack_timeout, self.reconnect_delay) <= 0:
            raise ValueError("controller timeouts must be positive")
        if self.max_retries < 0:
            raise ValueError("controller max_retries must be non-negative")

    def make_client(self) -> ControllerClient:
        self.validate()
        return ControllerClient(
            host=self.host,
            port=self.port,
            connect_timeout=self.connect_timeout,
            ack_timeout=self.ack_timeout,
            reconnect_delay=self.reconnect_delay,
            max_retries=self.max_retries,
        )


def load_controller_connection_config(path: str | Path) -> ControllerConnectionConfig:
    """Load and validate the narrowly scoped PC-to-Controller JSON config."""

    source = Path(path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("controller config root must be an object")
    try:
        config = ControllerConnectionConfig(
            host=str(payload["host"]),
            port=int(payload["port"]),
            connect_timeout=float(payload.get("connect_timeout", 1.0)),
            ack_timeout=float(payload.get("ack_timeout", 1.0)),
            reconnect_delay=float(payload.get("reconnect_delay", 0.1)),
            max_retries=int(payload.get("max_retries", 2)),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"invalid controller config {source}: {error}") from error
    config.validate()
    return config


class VisionEventEnqueuer:
    """Send only approved M4 ``OBJECT_ENTER`` events to the Controller.

    ``command_id_start`` is explicitly supplied by an operator/test run.  It
    avoids collisions between independent M4 sessions, whose event IDs each
    begin at one.  An optional expected-label allow-list is a fail-closed guard
    for single-shape physical acceptance tests: a misclassified valid shape is
    never silently enqueued.
    """

    def __init__(
        self,
        client: ControllerClient,
        command_id_start: int,
        *,
        expected_labels: Optional[Iterable[str]] = None,
        result_timeout: float = 2.0,
    ) -> None:
        if command_id_start < 1:
            raise ValueError("command_id_start must be positive")
        if result_timeout <= 0:
            raise ValueError("result_timeout must be positive")
        labels = None if expected_labels is None else frozenset(expected_labels)
        if labels is not None and (not labels or not labels <= SORTABLE_SHAPES):
            raise ValueError("expected_labels must contain supported sortable shapes")
        self._client = client
        self._command_id_start = command_id_start
        self._expected_labels = labels
        self._result_timeout = result_timeout

    def handle(self, event: VisionEvent) -> Optional[Dict[str, Any]]:
        """Return an acknowledgement record, or ignore a non-enter event."""

        if event.event_type != EventType.OBJECT_ENTER:
            return None
        if event.label not in SORTABLE_SHAPES:
            raise ValueError(f"refusing non-sortable M4 label: {event.label!r}")
        if self._expected_labels is not None and event.label not in self._expected_labels:
            raise ValueError(
                "refusing unexpected recognized label "
                f"{event.label!r}; expected one of {sorted(self._expected_labels)!r}"
            )

        command_id = self._command_id_start + event.event_id - 1
        response_future = self._client.send_enqueue(
            command_id,
            event.label,
            source_event_id=event.event_id,
            source_object_id=event.object_id,
        )
        try:
            response = response_future.result(self._result_timeout)
        except FutureTimeout:
            # Do not let ControllerClient replay a stale visual event if the
            # board reconnects after this live-frame decision has expired.
            response_future.cancel()
            raise
        if response.get("status") != "accepted":
            raise ControllerEnqueueRejected(command_id, response)
        return {
            "command_id": command_id,
            "shape": event.label,
            "response": response,
        }
