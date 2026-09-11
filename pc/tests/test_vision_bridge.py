"""Unit coverage for the narrow M4-to-M7 enqueue bridge."""

from __future__ import annotations

from concurrent.futures import Future
import unittest

from pc.communication.vision_bridge import VisionEventEnqueuer
from pc.events.models import EventType, VisionEvent


class _FakeClient:
    def __init__(self, response: dict[str, object] | None = None) -> None:
        self.response = response or {"status": "accepted"}
        self.calls: list[tuple[int, str, int | None, int | None]] = []

    def send_enqueue(
        self,
        command_id: int,
        shape: str,
        *,
        source_event_id: int | None = None,
        source_object_id: int | None = None,
    ) -> Future:
        self.calls.append((command_id, shape, source_event_id, source_object_id))
        future = Future()
        future.set_result(self.response)
        return future


def _event(event_type: EventType, event_id: int = 4, label: str = "circle") -> VisionEvent:
    return VisionEvent(event_id, event_type, 9, label, 0.95, 42)


class VisionEventEnqueuerTests(unittest.TestCase):
    def test_confirmed_enter_maps_to_existing_enqueue_protocol(self) -> None:
        client = _FakeClient()
        bridge = VisionEventEnqueuer(client, 12000, expected_labels=("circle",))  # type: ignore[arg-type]

        record = bridge.handle(_event(EventType.OBJECT_ENTER))

        self.assertEqual(client.calls, [(12003, "circle", 4, 9)])
        self.assertEqual(record["command_id"], 12003)  # type: ignore[index]
        self.assertEqual(record["response"], {"status": "accepted"})  # type: ignore[index]

    def test_exit_does_not_enqueue(self) -> None:
        client = _FakeClient()
        bridge = VisionEventEnqueuer(client, 1)  # type: ignore[arg-type]

        self.assertIsNone(bridge.handle(_event(EventType.OBJECT_EXIT)))
        self.assertEqual(client.calls, [])

    def test_unexpected_or_non_sortable_label_is_rejected_before_tcp(self) -> None:
        client = _FakeClient()
        bridge = VisionEventEnqueuer(client, 1, expected_labels=("triangle",))  # type: ignore[arg-type]

        with self.assertRaisesRegex(ValueError, "unexpected"):
            bridge.handle(_event(EventType.OBJECT_ENTER, label="circle"))
        with self.assertRaisesRegex(ValueError, "non-sortable"):
            VisionEventEnqueuer(client, 1).handle(_event(EventType.OBJECT_ENTER, label="unknown"))  # type: ignore[arg-type]
        self.assertEqual(client.calls, [])

    def test_duplicate_or_rejected_ack_is_not_success(self) -> None:
        bridge = VisionEventEnqueuer(_FakeClient({"status": "duplicate"}), 1)  # type: ignore[arg-type]

        with self.assertRaisesRegex(RuntimeError, "did not accept"):
            bridge.handle(_event(EventType.OBJECT_ENTER))


if __name__ == "__main__":
    unittest.main()
