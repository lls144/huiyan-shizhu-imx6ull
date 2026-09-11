from __future__ import annotations

from pc.communication.state_monitor import PipelineState, QueueItem
from pc.gui.animation_controller import AnimationController, AnimationEventType


def _pipeline(
    *,
    queue: tuple[QueueItem, ...] = (),
    station: str = "idle",
    branch: str | None = None,
    sequence: int | None = None,
) -> PipelineState:
    return PipelineState(
        capacity=3,
        queue_length=len(queue),
        station=station,
        current_object=queue[0].shape if queue else None,
        last_key=None,
        last_sort=branch,
        last_sort_sequence=sequence,
        last_transition="waiting" if queue else "idle",
        queue=queue,
    )


def test_first_snapshot_is_a_silent_baseline_then_queue_addition_spawns_once() -> None:
    controller = AnimationController()
    circle = QueueItem(10, "circle")

    assert controller.update(_pipeline()) == ()
    events = controller.update(_pipeline(queue=(circle,), station="Station1"))
    assert [(event.event_type, event.command_id, event.shape) for event in events] == [
        (AnimationEventType.SPAWN, 10, "circle")
    ]
    assert controller.update(_pipeline(queue=(circle,), station="Station1")) == ()


def test_same_front_station_change_creates_one_transition() -> None:
    controller = AnimationController()
    circle = QueueItem(10, "circle")

    controller.update(_pipeline(queue=(circle,), station="Station1"))
    events = controller.update(_pipeline(queue=(circle,), station="Station2"))
    assert [(event.event_type, event.source_station, event.target_station) for event in events] == [
        (AnimationEventType.STATION_TRANSITION, "Station1", "Station2")
    ]
    assert controller.update(_pipeline(queue=(circle,), station="Station2")) == ()


def test_branch_sort_uses_sequence_once_and_last_known_front() -> None:
    controller = AnimationController()
    rectangle = QueueItem(30, "rectangle")

    controller.update(_pipeline(queue=(rectangle,), station="Station3"))
    events = controller.update(_pipeline(branch="Branch3", sequence=8))
    assert [(event.event_type, event.command_id, event.shape, event.branch, event.sequence) for event in events] == [
        (AnimationEventType.BRANCH_SORT, 30, "rectangle", "Branch3", 8)
    ]
    assert controller.update(_pipeline(branch="Branch3", sequence=8)) == ()


def test_reset_to_empty_does_not_fake_sort_and_new_queue_can_spawn() -> None:
    controller = AnimationController()
    first = QueueItem(10, "circle")
    second = QueueItem(11, "triangle")

    controller.update(_pipeline(queue=(first,), station="Station1"))
    assert controller.update(_pipeline()) == ()
    events = controller.update(_pipeline(queue=(second,), station="Station1"))
    assert [(event.event_type, event.command_id) for event in events] == [
        (AnimationEventType.SPAWN, 11)
    ]
