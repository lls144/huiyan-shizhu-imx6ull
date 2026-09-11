"""Asynchronous GUI delivery of existing M4 events through VisionEventEnqueuer."""

from __future__ import annotations

import queue
import threading
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import asdict, dataclass
from typing import Any, Callable, Iterable

from pc.events.models import EventType, VisionEvent

from .controller_client import ControllerClientError
from .vision_bridge import ControllerEnqueueRejected, SORTABLE_SHAPES, VisionEventEnqueuer


@dataclass(frozen=True)
class EnqueueResult:
    """Terminal status for one current-frame OBJECT_ENTER delivery attempt."""

    event_id: int
    object_id: int
    shape: str
    outcome: str
    message: str
    command_id: int | None = None
    response: dict[str, Any] | None = None

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


class VisionEventDispatcher:
    """Deliver only fresh OBJECT_ENTER events without blocking the vision worker.

    There is no local retry queue: an offline or already-busy controller path
    records one result and drops that current visual event.  M4's tracker will
    only create another opportunity after the physical object exits and later
    re-enters the camera view.
    """

    def __init__(
        self,
        enqueuer: VisionEventEnqueuer,
        *,
        board_online: Callable[[], bool],
        supported_shapes: Iterable[str] = SORTABLE_SHAPES,
    ) -> None:
        self._enqueuer = enqueuer
        self._board_online = board_online
        self._supported_shapes = frozenset(supported_shapes)
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="vision-enqueue")
        self._lock = threading.Lock()
        self._in_flight = False
        self._closed = False
        self._results: queue.SimpleQueue[EnqueueResult] = queue.SimpleQueue()

    def submit(self, event: VisionEvent) -> None:
        """Return immediately; any final result is available from ``drain``."""

        if event.event_type is not EventType.OBJECT_ENTER:
            return
        if event.label not in self._supported_shapes:
            self._record(event, "unsupported_shape", f"unsupported shape: {event.label!r}")
            return
        try:
            online = self._board_online()
        except Exception as error:
            self._record(event, "board_offline", f"board status unavailable: {type(error).__name__}: {error}")
            return
        if not online:
            self._record(event, "board_offline", "board heartbeat is not ONLINE; event was not queued")
            return
        with self._lock:
            if self._closed:
                self._record(event, "dispatcher_closed", "GUI is closing; event was not queued")
                return
            if self._in_flight:
                self._record(event, "busy_dropped", "previous enqueue is still pending; event was not queued")
                return
            self._in_flight = True
        self._executor.submit(self._deliver, event)

    def drain(self) -> tuple[EnqueueResult, ...]:
        """Return completed GUI-facing results in completion order."""

        results: list[EnqueueResult] = []
        while True:
            try:
                results.append(self._results.get_nowait())
            except queue.Empty:
                return tuple(results)

    def close(self) -> None:
        with self._lock:
            self._closed = True
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _deliver(self, event: VisionEvent) -> None:
        try:
            record = self._enqueuer.handle(event)
            if record is None:
                return
            response = record["response"]
            self._record(
                event,
                "accepted",
                "Controller ACK accepted; authoritative FIFO will update from pipeline_state",
                command_id=int(record["command_id"]),
                response=response if isinstance(response, dict) else None,
            )
        except ControllerEnqueueRejected as error:
            outcome = error.status if error.status in {"queue_full", "duplicate"} else "rejected"
            self._record(event, outcome, str(error), command_id=error.command_id, response=error.response)
        except FutureTimeout:
            self._record(event, "timeout", "Controller ACK timed out; event was cancelled and will not replay")
        except ControllerClientError as error:
            self._record(event, "protocol_error", str(error))
        except ValueError as error:
            self._record(event, "unsupported_shape", str(error))
        except Exception as error:
            self._record(event, "error", f"{type(error).__name__}: {error}")
        finally:
            with self._lock:
                self._in_flight = False

    def _record(
        self,
        event: VisionEvent,
        outcome: str,
        message: str,
        *,
        command_id: int | None = None,
        response: dict[str, Any] | None = None,
    ) -> None:
        self._results.put(
            EnqueueResult(
                event.event_id,
                event.object_id,
                event.label,
                outcome,
                message,
                command_id,
                response,
            )
        )
