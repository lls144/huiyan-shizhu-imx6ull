from collections import Counter
from pathlib import Path

import cv2
import pytest

from pc.events.adapters import detections_from_analysis
from pc.events.config import EventConfig
from pc.events.models import Detection, EventType, VisionEvent
from pc.events.tracker import ObjectStateManager, bbox_iou
from pc.vision.config import load_vision_config
from pc.vision.pipeline import analyze_multiple_objects

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG = EventConfig(
    min_confirm_frames=2,
    max_missing_frames=3,
    occlusion_grace_frames=25,
    iou_threshold=0.3,
    center_distance_threshold=80.0,
)


def _detection(
    frame_index: int,
    label: str = "circle",
    bbox: tuple[int, int, int, int] = (100, 100, 100, 100),
    confidence: float = 0.95,
) -> Detection:
    return Detection(label, confidence, bbox, frame_index)


def _run(frames: list[list[dict[str, object]]]) -> tuple[ObjectStateManager, list[VisionEvent]]:
    manager = ObjectStateManager(CONFIG)
    events: list[VisionEvent] = []
    for frame_index, records in enumerate(frames):
        detections = [
            _detection(
                frame_index,
                str(record.get("label", "circle")),
                record.get("bbox", (100, 100, 100, 100)),  # type: ignore[arg-type]
                float(record.get("confidence", 0.95)),
            )
            for record in records
        ]
        events.extend(manager.process_frame(frame_index, detections).events)
    return manager, events


def _event_keys(events: list[VisionEvent]) -> list[tuple[str, int, str, int]]:
    return [
        (event.event_type.value, event.object_id, event.label, event.frame_index)
        for event in events
    ]


def test_bbox_iou_uses_xywh_format() -> None:
    assert bbox_iou((0, 0, 100, 100), (50, 0, 100, 100)) == 1 / 3
    assert bbox_iou((0, 0, 10, 10), (20, 20, 10, 10)) == 0


def test_persistent_object_emits_one_enter_only() -> None:
    manager, events = _run([[{}] for _ in range(10)])

    assert _event_keys(events) == [("OBJECT_ENTER", 1, "circle", 1)]
    assert manager.object_states()[0].hit_count == 10
    assert manager.object_states()[0].active is True


def test_single_frame_noise_never_confirms() -> None:
    manager, events = _run([[], [{}], []])

    assert events == []
    assert manager.object_states()[0].confirmed is False
    assert manager.object_states()[0].active is True
    assert manager.object_states()[0].status == "candidate"


def test_short_hand_occlusion_keeps_identity_without_exit_or_second_enter() -> None:
    manager, events = _run([[{}], [{}], [], [{}], [{}]])

    assert _event_keys(events) == [("OBJECT_ENTER", 1, "circle", 1)]
    assert manager.object_states()[0].object_id == 1
    assert manager.object_states()[0].hit_count == 4


def test_near_grace_occlusion_recovers_original_track_without_lifecycle_events() -> None:
    manager, events = _run([[{}], [{}]] + [[] for _ in range(25)] + [[{}], [{}]])

    assert _event_keys(events) == [("OBJECT_ENTER", 1, "circle", 1)]
    recovered = manager.object_states()[0]
    assert recovered.object_id == 1
    assert recovered.active is True
    assert recovered.status == "confirmed"
    assert recovered.miss_count == 0


def test_true_removal_emits_exit_once_after_occlusion_grace() -> None:
    manager, events = _run([[{}], [{}]] + [[] for _ in range(26)])

    assert _event_keys(events) == [
        ("OBJECT_ENTER", 1, "circle", 1),
        ("OBJECT_EXIT", 1, "circle", 27),
    ]
    assert manager.object_states()[0].status == "exited"


def test_reentry_uses_new_object_id() -> None:
    _, events = _run([[{}], [{}]] + [[] for _ in range(26)] + [[{}], [{}]])

    assert _event_keys(events) == [
        ("OBJECT_ENTER", 1, "circle", 1),
        ("OBJECT_EXIT", 1, "circle", 27),
        ("OBJECT_ENTER", 2, "circle", 29),
    ]


def test_two_classes_have_independent_states_and_enters() -> None:
    frame = [
        {"label": "triangle", "bbox": (100, 100, 80, 100)},
        {"label": "circle", "bbox": (400, 100, 100, 100)},
    ]
    manager, events = _run([frame, list(reversed(frame))])

    assert Counter(event.label for event in events) == {"triangle": 1, "circle": 1}
    assert len([state for state in manager.object_states() if state.active]) == 2


def test_three_classes_generate_three_enter_events() -> None:
    frame = [
        {"label": "triangle", "bbox": (100, 100, 80, 100)},
        {"label": "rectangle", "bbox": (350, 100, 120, 100)},
        {"label": "circle", "bbox": (650, 100, 100, 100)},
    ]
    _, events = _run([frame, frame])

    assert [event.event_type for event in events] == [EventType.OBJECT_ENTER] * 3
    assert {event.label for event in events} == {"triangle", "rectangle", "circle"}


def test_two_same_label_objects_get_distinct_ids_independent_of_input_order() -> None:
    left = {"label": "circle", "bbox": (100, 100, 100, 100)}
    right = {"label": "circle", "bbox": (500, 100, 100, 100)}
    manager, events = _run([[right, left], [left, right]])

    assert {event.object_id for event in events} == {1, 2}
    active = [state for state in manager.object_states() if state.active]
    assert [state.bbox[0] for state in active] == [100, 500]


def test_small_movement_keeps_one_object_id() -> None:
    frames = [
        [{"bbox": (100 + offset, 100 + offset, 100, 100)}]
        for offset in (0, 8, 14, 20)
    ]
    manager, events = _run(frames)

    assert _event_keys(events) == [("OBJECT_ENTER", 1, "circle", 1)]
    assert manager.object_states()[0].bbox == (120, 120, 100, 100)


def test_confidence_variation_does_not_create_new_identity() -> None:
    manager, events = _run(
        [
            [{"confidence": 0.98}],
            [{"confidence": 0.91}],
            [{"confidence": 0.95}],
        ]
    )

    assert len(events) == 1
    assert events[0].object_id == 1
    assert manager.object_states()[0].confidence == pytest.approx(0.946667, abs=1e-6)


def test_detection_order_change_does_not_change_object_ids() -> None:
    triangle = {"label": "triangle", "bbox": (100, 100, 80, 100)}
    circle = {"label": "circle", "bbox": (500, 100, 100, 100)}
    manager, events = _run([[triangle, circle], [circle, triangle]])

    assert len(events) == 2
    states = {state.label: state.object_id for state in manager.object_states() if state.active}
    assert states == {"triangle": 1, "circle": 2}


def test_clear_all_exits_every_confirmed_object_once() -> None:
    frame = [
        {"label": "triangle", "bbox": (100, 100, 80, 100)},
        {"label": "rectangle", "bbox": (350, 100, 120, 100)},
        {"label": "circle", "bbox": (650, 100, 100, 100)},
    ]
    manager, events = _run([frame, frame] + [[] for _ in range(26)])

    counts = Counter((event.object_id, event.event_type) for event in events)
    assert len(events) == 6
    assert all(count == 1 for count in counts.values())
    assert all(not state.active for state in manager.object_states())


def test_m3_synthetic_detections_feed_m4_without_classifier_changes() -> None:
    image = cv2.imread(
        str(REPO_ROOT / "test_data/m3/synthetic/multi_normal.png"),
        cv2.IMREAD_COLOR,
    )
    assert image is not None
    vision_config = load_vision_config(REPO_ROOT / "pc/config/vision.json")
    analysis = analyze_multiple_objects(image, vision_config)
    manager = ObjectStateManager(CONFIG)

    first = manager.process_frame(0, detections_from_analysis(analysis, 0))
    second = manager.process_frame(1, detections_from_analysis(analysis, 1))

    assert first.events == ()
    assert [event.label for event in second.events] == [
        "triangle",
        "rectangle",
        "circle",
    ]
    assert {event.object_id for event in second.events} == {1, 2, 3}


def test_frame_index_must_increase_without_sleep_or_wall_clock() -> None:
    manager = ObjectStateManager(CONFIG)
    manager.process_frame(0, [_detection(0)])

    with pytest.raises(ValueError, match="increase strictly"):
        manager.process_frame(0, [_detection(0)])


def test_each_confirmed_lifecycle_has_at_most_one_enter_and_exit() -> None:
    _, events = _run(
        [[{}], [{}]]
        + [[] for _ in range(5)]
        + [[{}], [{}]]
        + [[] for _ in range(26)]
        + [[{}], [{}]]
        + [[] for _ in range(26)]
    )
    counts = Counter((event.object_id, event.event_type) for event in events)

    assert all(count == 1 for count in counts.values())


def test_different_shape_during_pending_exit_is_never_reassociated() -> None:
    manager, events = _run(
        [
            [{"label": "circle", "bbox": (100, 100, 100, 100)}],
            [{"label": "circle", "bbox": (100, 100, 100, 100)}],
            [],
            [{"label": "triangle", "bbox": (100, 100, 100, 100)}],
            [{"label": "triangle", "bbox": (100, 100, 100, 100)}],
        ]
    )

    assert _event_keys(events) == [
        ("OBJECT_ENTER", 1, "circle", 1),
        ("OBJECT_ENTER", 2, "triangle", 4),
    ]
    active = {state.object_id: state for state in manager.object_states() if state.active}
    assert active[1].status == "pending_exit"
    assert active[2].label == "triangle"


def test_far_same_shape_during_pending_exit_is_a_distinct_object() -> None:
    manager, events = _run(
        [
            [{"label": "circle", "bbox": (100, 100, 100, 100)}],
            [{"label": "circle", "bbox": (100, 100, 100, 100)}],
            [],
            [{"label": "circle", "bbox": (500, 100, 100, 100)}],
            [{"label": "circle", "bbox": (500, 100, 100, 100)}],
        ]
    )

    assert _event_keys(events) == [
        ("OBJECT_ENTER", 1, "circle", 1),
        ("OBJECT_ENTER", 2, "circle", 4),
    ]
    active = {state.object_id: state for state in manager.object_states() if state.active}
    assert active[1].status == "pending_exit"
    assert active[2].bbox == (500, 100, 100, 100)
