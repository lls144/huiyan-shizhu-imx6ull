from __future__ import annotations

from concurrent.futures import Future

import pytest

from pc.communication.state_monitor import (
    BoardStateMonitor,
    ConnectionStatus,
    parse_pipeline_state,
)


def _result(value: object) -> Future:
    future = Future()
    future.set_result(value)
    return future


def _failure(error: Exception) -> Future:
    future = Future()
    future.set_exception(error)
    return future


def _state(*, station: str = "idle", queue_length: int = 0) -> dict[str, object]:
    front = None if queue_length == 0 else {"command_id": 21, "shape": "rectangle"}
    return {
        "version": 1,
        "type": "pipeline_state",
        "request_id": "state-1",
        "state": station,
        "pipeline_state": {
            "capacity": 3,
            "queue_length": queue_length,
            "empty": queue_length == 0,
            "full": queue_length == 3,
            "station": station,
            "front": front,
            "queue": [] if front is None else [front],
            "last_key": "KEY2" if queue_length else None,
            "last_sort": {"branch": "Branch1"} if queue_length else None,
        },
    }


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class FakeClient:
    def __init__(self, heartbeats: list[Future], states: list[Future]) -> None:
        self.heartbeats = heartbeats
        self.states = states
        self.start_calls = 0
        self.close_calls = 0
        self.heartbeat_calls = 0
        self.state_calls = 0

    def start(self) -> None:
        self.start_calls += 1

    def close(self) -> None:
        self.close_calls += 1

    def send_heartbeat(self) -> Future:
        self.heartbeat_calls += 1
        return self.heartbeats.pop(0)

    def request_pipeline_state(self) -> Future:
        self.state_calls += 1
        return self.states.pop(0)


def test_parse_pipeline_state_normalizes_existing_controller_response() -> None:
    parsed = parse_pipeline_state(_state(station="Station3", queue_length=1))

    assert parsed.capacity == 3
    assert parsed.queue_length == 1
    assert parsed.display_station == "STATION3"
    assert parsed.current_object == "rectangle"
    assert parsed.last_key == "KEY2"
    assert parsed.last_sort == "Branch1"


def test_parse_pipeline_state_rejects_state_mismatch() -> None:
    response = _state()
    response["state"] = "Station1"

    with pytest.raises(ValueError, match="must match"):
        parse_pipeline_state(response)


def test_heartbeat_failure_maps_offline_then_next_ack_returns_online() -> None:
    clock = Clock()
    client = FakeClient(
        [
            _failure(RuntimeError("temporary disconnect")),
            _result({"version": 1, "type": "ack", "request_id": "hb-2", "status": "alive"}),
        ],
        [_result(_state()), _result(_state())],
    )
    monitor = BoardStateMonitor(client, heartbeat_interval=1.0, state_interval=0.2, clock=clock)

    assert monitor.start().connection is ConnectionStatus.CONNECTING
    first = monitor.poll()
    assert first is not None
    assert first.connection is ConnectionStatus.OFFLINE
    assert first.pipeline is not None
    assert client.start_calls == 1

    clock.now = 1.0
    second = monitor.poll()
    assert second is not None
    assert second.connection is ConnectionStatus.ONLINE
    assert client.heartbeat_calls == 2


def test_pending_requests_are_single_flight_and_timeout_maps_offline() -> None:
    clock = Clock()
    pending_heartbeat = Future()
    pending_state = Future()
    client = FakeClient([pending_heartbeat], [pending_state])
    monitor = BoardStateMonitor(
        client,
        heartbeat_interval=0.1,
        state_interval=0.1,
        request_timeout=0.5,
        clock=clock,
    )

    monitor.start()
    assert monitor.poll() is None
    clock.now = 0.2
    assert monitor.poll() is None
    assert client.heartbeat_calls == 1
    assert client.state_calls == 1

    clock.now = 0.5
    timed_out = monitor.poll()
    assert timed_out is not None
    assert timed_out.connection is ConnectionStatus.OFFLINE
    assert pending_heartbeat.cancelled()
    assert pending_state.cancelled()
