from __future__ import annotations

import threading
import time
from concurrent.futures import Future
from pathlib import Path

import cv2

from pc.communication.vision_dispatcher import VisionEventDispatcher
from pc.communication.vision_bridge import VisionEventEnqueuer
from pc.events.config import load_event_config
from pc.events.models import EventType, VisionEvent
from pc.gui.worker import EvidenceRequestBuffer, LatestSnapshotBuffer, VisionWorker
from pc.vision.config import load_vision_config
from pc.vision.pipeline import analyze_multiple_objects
from pc.vision.roi import fixed_roi


REPO_ROOT = Path(__file__).resolve().parents[2]
VISION_CONFIG = load_vision_config(REPO_ROOT / "pc/config/vision.json")
EVENT_CONFIG = load_event_config(REPO_ROOT / "pc/config/events.json")
NORMAL_IMAGE = cv2.imread(str(REPO_ROOT / "test_data/m3/synthetic/multi_normal.png"))
assert NORMAL_IMAGE is not None


def _event(event_id: int = 1, label: str = "circle") -> VisionEvent:
    return VisionEvent(event_id, EventType.OBJECT_ENTER, 9, label, 0.95, 2)


def _drain_until(dispatcher: VisionEventDispatcher) -> tuple[object, ...]:
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        results = dispatcher.drain()
        if results:
            return results
        time.sleep(0.01)
    raise AssertionError("dispatcher did not return a bounded result")


class _AcceptedEnqueuer:
    def __init__(self) -> None:
        self.events: list[VisionEvent] = []

    def handle(self, event: VisionEvent) -> dict[str, object]:
        self.events.append(event)
        return {"command_id": 500 + event.event_id, "response": {"status": "accepted"}}


class _QueueFullEnqueuer:
    def handle(self, event: VisionEvent) -> None:
        from pc.communication.vision_bridge import ControllerEnqueueRejected

        raise ControllerEnqueueRejected(501, {"status": "queue_full", "type": "ack"})


class _ControllerAckClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def send_enqueue(self, command_id: int, shape: str, **payload: object) -> Future:
        self.calls.append({"command_id": command_id, "shape": shape, **payload})
        future: Future = Future()
        future.set_result({"type": "ack", "status": "accepted", "command_id": command_id})
        return future


def test_accepted_enqueue_is_reported_only_after_existing_enqueuer_ack() -> None:
    enqueuer = _AcceptedEnqueuer()
    dispatcher = VisionEventDispatcher(enqueuer, board_online=lambda: True)  # type: ignore[arg-type]
    try:
        dispatcher.submit(_event())
        result = _drain_until(dispatcher)[0]
    finally:
        dispatcher.close()

    assert enqueuer.events == [_event()]
    assert result.outcome == "accepted"  # type: ignore[attr-defined]
    assert result.command_id == 501  # type: ignore[attr-defined]


def test_dispatcher_integrates_actual_vision_event_enqueuer_command_mapping() -> None:
    client = _ControllerAckClient()
    enqueuer = VisionEventEnqueuer(client, command_id_start=900)  # type: ignore[arg-type]
    dispatcher = VisionEventDispatcher(enqueuer, board_online=lambda: True)
    try:
        dispatcher.submit(_event(event_id=4, label="triangle"))
        result = _drain_until(dispatcher)[0]
    finally:
        dispatcher.close()

    assert client.calls == [
        {
            "command_id": 903,
            "shape": "triangle",
            "source_event_id": 4,
            "source_object_id": 9,
        }
    ]
    assert result.outcome == "accepted"  # type: ignore[attr-defined]
    assert result.command_id == 903  # type: ignore[attr-defined]


def test_offline_and_queue_full_are_visible_terminal_results_without_replay() -> None:
    offline = VisionEventDispatcher(_AcceptedEnqueuer(), board_online=lambda: False)  # type: ignore[arg-type]
    try:
        offline.submit(_event())
        offline_result = offline.drain()[0]
    finally:
        offline.close()
    assert offline_result.outcome == "board_offline"

    full = VisionEventDispatcher(_QueueFullEnqueuer(), board_online=lambda: True)  # type: ignore[arg-type]
    try:
        full.submit(_event())
        full_result = _drain_until(full)[0]
    finally:
        full.close()
    assert full_result.outcome == "queue_full"
    assert full_result.command_id == 501


class _FixedSource:
    source_type = "synthetic"
    target_fps = 0.0
    roi_mode = "fixed_normalized"
    roi_source = "configured"
    failed_reads = 0

    def __init__(self) -> None:
        self.roi = fixed_roi(VISION_CONFIG)
        self._frames = [NORMAL_IMAGE, NORMAL_IMAGE, NORMAL_IMAGE]
        self._index = 0

    def open(self) -> None:
        self._index = 0

    def read(self):
        if self._index >= len(self._frames):
            return None
        frame = self._frames[self._index]
        self._index += 1
        return frame

    def close(self) -> None:
        pass

    def metadata(self) -> dict[str, object]:
        return {"source_type": self.source_type}


class _RecordingDispatcher:
    def __init__(self) -> None:
        self.events: list[VisionEvent] = []
        self.called = threading.Event()

    def submit(self, event: VisionEvent) -> None:
        self.events.append(event)
        self.called.set()


def test_existing_worker_lifecycle_submits_one_enter_per_continuing_object() -> None:
    dispatcher = _RecordingDispatcher()
    worker = VisionWorker(
        _FixedSource(),
        VISION_CONFIG,
        EVENT_CONFIG,
        LatestSnapshotBuffer(),
        EvidenceRequestBuffer(),
        REPO_ROOT / "output/test-evidence",
        ("triangle", "rectangle", "circle"),
        analyze_multiple_objects,
        dispatcher,  # type: ignore[arg-type]
    )

    worker.run()

    assert dispatcher.called.is_set()
    assert [event.event_type for event in dispatcher.events] == [EventType.OBJECT_ENTER] * 3
    assert [event.label for event in dispatcher.events] == ["triangle", "rectangle", "circle"]
    assert len({event.object_id for event in dispatcher.events}) == 3
