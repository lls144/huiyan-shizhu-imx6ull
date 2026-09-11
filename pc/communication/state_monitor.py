"""Non-blocking board-state polling built on the existing ControllerClient."""

from __future__ import annotations

import time
from concurrent.futures import Future
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Callable, Mapping, Protocol


class _ControllerClientLike(Protocol):
    def start(self) -> None: ...

    def close(self) -> None: ...

    def send_heartbeat(self) -> Future: ...

    def request_pipeline_state(self) -> Future: ...


class ConnectionStatus(StrEnum):
    CONNECTING = "connecting"
    ONLINE = "online"
    OFFLINE = "offline"


@dataclass(frozen=True)
class QueueItem:
    """One Controller-owned FIFO record, kept in board order."""

    command_id: int
    shape: str


@dataclass(frozen=True)
class PipelineState:
    """Validated, UI-ready subset of the Controller pipeline snapshot."""

    capacity: int
    queue_length: int
    station: str
    current_object: str | None
    last_key: str | None
    last_sort: str | None
    last_sort_sequence: int | None
    last_transition: str
    queue: tuple[QueueItem, ...]

    @property
    def display_station(self) -> str:
        return "IDLE" if self.station == "idle" else self.station.upper()


@dataclass(frozen=True)
class BoardMonitorSnapshot:
    """One immutable update for the GUI; no Controller mutation is possible."""

    connection: ConnectionStatus
    pipeline: PipelineState | None
    error: str | None
    transport: ConnectionStatus = ConnectionStatus.CONNECTING


@dataclass
class _PendingRequest:
    future: Future
    deadline: float


def _mapping(value: object, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
    return value


def _bounded_int(value: object, field: str, *, minimum: int, maximum: int | None = None) -> int:
    if type(value) is not int or value < minimum or (maximum is not None and value > maximum):
        range_text = f"[{minimum}, {maximum}]" if maximum is not None else f">= {minimum}"
        raise ValueError(f"{field} must be an integer in {range_text}")
    return value


def parse_pipeline_state(response: Mapping[str, Any]) -> PipelineState:
    """Validate and normalize one existing ``pipeline_state`` response."""

    if response.get("type") != "pipeline_state":
        raise ValueError("response type must be pipeline_state")
    payload = _mapping(response.get("pipeline_state"), "pipeline_state")
    capacity = _bounded_int(payload.get("capacity"), "capacity", minimum=1)
    queue_length = _bounded_int(payload.get("queue_length"), "queue_length", minimum=0, maximum=capacity)
    station = payload.get("station")
    if station not in {"idle", "Station1", "Station2", "Station3"}:
        raise ValueError("station must be idle, Station1, Station2, or Station3")
    if response.get("state") != station:
        raise ValueError("response state must match pipeline_state.station")

    queue_payload = payload.get("queue")
    if not isinstance(queue_payload, list):
        raise ValueError("queue must be an array")
    if len(queue_payload) != queue_length:
        raise ValueError("queue length must match queue_length")
    queue: list[QueueItem] = []
    for index, item in enumerate(queue_payload):
        command = _mapping(item, f"queue[{index}]")
        command_id = _bounded_int(command.get("command_id"), f"queue[{index}].command_id", minimum=1)
        shape = command.get("shape")
        if shape not in {"triangle", "circle", "rectangle"}:
            raise ValueError(f"queue[{index}].shape must be triangle, circle, or rectangle")
        queue.append(QueueItem(command_id, shape))

    front = payload.get("front")
    if front is None:
        current_object = None
    else:
        front_record = _mapping(front, "front")
        current_object = front_record.get("shape")
        if current_object not in {"triangle", "circle", "rectangle"}:
            raise ValueError("front.shape must be triangle, circle, or rectangle")
        if not queue or (
            front_record.get("command_id") != queue[0].command_id
            or current_object != queue[0].shape
        ):
            raise ValueError("front must match the first queue item")

    last_key = payload.get("last_key")
    if last_key is not None and last_key not in {"KEY1", "KEY2", "KEY3"}:
        raise ValueError("last_key must be KEY1, KEY2, KEY3, or null")
    last_sort_payload = payload.get("last_sort")
    last_sort_sequence: int | None
    if last_sort_payload is None:
        last_sort = None
        last_sort_sequence = None
    else:
        last_sort_record = _mapping(last_sort_payload, "last_sort")
        last_sort = last_sort_record.get("branch")
        if last_sort not in {"Branch1", "Branch2", "Branch3"}:
            raise ValueError("last_sort.branch must be Branch1, Branch2, or Branch3")
        last_sort_sequence = _bounded_int(last_sort_record.get("sequence"), "last_sort.sequence", minimum=1)
    last_transition = payload.get("last_transition")
    if not isinstance(last_transition, str) or not last_transition:
        raise ValueError("last_transition must be a non-empty string")

    if queue_length == 0 and (front is not None or station != "idle"):
        raise ValueError("empty queue must have no front object and idle station")
    return PipelineState(
        capacity,
        queue_length,
        station,
        current_object,
        last_key,
        last_sort,
        last_sort_sequence,
        last_transition,
        tuple(queue),
    )


class BoardStateMonitor:
    """Schedule heartbeat/state requests without blocking the Qt main thread.

    ``poll`` is intentionally called by a GUI-owned timer.  It never waits for
    a Future and it issues at most one outstanding heartbeat and one
    outstanding pipeline-state request.  ``ControllerClient`` retains socket
    ownership and reconnection responsibility.
    """

    def __init__(
        self,
        client: _ControllerClientLike,
        *,
        heartbeat_interval: float = 1.0,
        state_interval: float = 0.2,
        request_timeout: float = 4.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if min(heartbeat_interval, state_interval, request_timeout) <= 0:
            raise ValueError("monitor intervals and request_timeout must be positive")
        self._client = client
        self._heartbeat_interval = heartbeat_interval
        self._state_interval = state_interval
        self._request_timeout = request_timeout
        self._clock = clock
        self._connection = ConnectionStatus.CONNECTING
        self._transport = ConnectionStatus.CONNECTING
        self._pipeline: PipelineState | None = None
        self._error: str | None = None
        self._heartbeat: _PendingRequest | None = None
        self._state: _PendingRequest | None = None
        self._next_heartbeat = 0.0
        self._next_state = 0.0
        self._started = False

    @property
    def snapshot(self) -> BoardMonitorSnapshot:
        return BoardMonitorSnapshot(self._connection, self._pipeline, self._error, self._transport)

    def start(self) -> BoardMonitorSnapshot:
        if not self._started:
            self._client.start()
            now = self._clock()
            self._next_heartbeat = now
            self._next_state = now
            self._started = True
        return self.snapshot

    def close(self) -> None:
        self._client.close()
        self._started = False

    def poll(self) -> BoardMonitorSnapshot | None:
        """Process completed Futures and schedule due work without waiting."""

        if not self._started:
            return None
        now = self._clock()
        before = self.snapshot
        changed = self._collect_heartbeat(now) | self._collect_state(now)
        if self._heartbeat is None and now >= self._next_heartbeat:
            self._heartbeat = self._submit(self._client.send_heartbeat, now, "heartbeat")
            self._next_heartbeat = now + self._heartbeat_interval
            changed = self._collect_heartbeat(now) or changed
        if self._state is None and now >= self._next_state:
            self._state = self._submit(self._client.request_pipeline_state, now, "pipeline_state")
            self._next_state = now + self._state_interval
            changed = self._collect_state(now) or changed
        changed = self._refresh_transport() or changed
        return self.snapshot if changed or self.snapshot != before else None

    def _refresh_transport(self) -> bool:
        """Read ControllerClient's socket event without waiting in the GUI thread.

        The transport state is presentation-only health data.  BOARD/CONTROLLER
        online remains governed by the validated heartbeat ACK in
        ``_collect_heartbeat``.
        """

        wait_connected = getattr(self._client, "wait_connected", None)
        if callable(wait_connected):
            try:
                connected = bool(wait_connected(0.0))
            except Exception:
                connected = False
            next_status = (
                ConnectionStatus.ONLINE
                if connected
                else (
                    ConnectionStatus.OFFLINE
                    if self._connection is ConnectionStatus.OFFLINE
                    else ConnectionStatus.CONNECTING
                )
            )
        else:
            next_status = self._connection
        changed = next_status is not self._transport
        self._transport = next_status
        return changed

    def _submit(
        self, request: Callable[[], Future], now: float, label: str
    ) -> _PendingRequest | None:
        try:
            return _PendingRequest(request(), now + self._request_timeout)
        except Exception as error:
            self._error = f"{label} request failed: {type(error).__name__}: {error}"
            if label == "heartbeat":
                self._connection = ConnectionStatus.OFFLINE
            return None

    def _collect_heartbeat(self, now: float) -> bool:
        pending = self._heartbeat
        if pending is None:
            return False
        if not pending.future.done() and now < pending.deadline:
            return False
        self._heartbeat = None
        if not pending.future.done():
            pending.future.cancel()
            self._connection = ConnectionStatus.OFFLINE
            self._error = "heartbeat timed out"
            return True
        try:
            response = pending.future.result()
        except Exception as error:
            self._connection = ConnectionStatus.OFFLINE
            self._error = f"heartbeat failed: {type(error).__name__}: {error}"
            return True
        if not isinstance(response, Mapping) or response.get("type") != "ack" or response.get("status") != "alive":
            self._connection = ConnectionStatus.OFFLINE
            self._error = f"invalid heartbeat response: {response!r}"
            return True
        changed = self._connection is not ConnectionStatus.ONLINE or self._error is not None
        self._connection = ConnectionStatus.ONLINE
        self._error = None
        return changed

    def _collect_state(self, now: float) -> bool:
        pending = self._state
        if pending is None:
            return False
        if not pending.future.done() and now < pending.deadline:
            return False
        self._state = None
        if not pending.future.done():
            pending.future.cancel()
            self._error = "pipeline_state timed out"
            return True
        try:
            response = pending.future.result()
            if not isinstance(response, Mapping):
                raise ValueError("pipeline_state response must be an object")
            parsed = parse_pipeline_state(response)
        except Exception as error:
            self._error = f"pipeline_state failed: {type(error).__name__}: {error}"
            return True
        changed = parsed != self._pipeline or self._error is not None
        self._pipeline = parsed
        self._error = None
        return changed
