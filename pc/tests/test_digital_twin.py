from __future__ import annotations

from pc.communication.state_monitor import PipelineState, QueueItem
from pc.gui.digital_twin import SortSequenceTracker, bin_for_branch, station_for_branch


def _pipeline(
    *,
    station: str = "idle",
    queue: tuple[QueueItem, ...] = (),
    last_sort: str | None = None,
    sequence: int | None = None,
) -> PipelineState:
    return PipelineState(
        capacity=3,
        queue_length=len(queue),
        station=station,
        current_object=queue[0].shape if queue else None,
        last_key=None,
        last_sort=last_sort,
        last_sort_sequence=sequence,
        last_transition="idle" if not queue else "waiting",
        queue=queue,
    )


def test_front_and_station_mapping_stay_board_ordered() -> None:
    pipeline = _pipeline(
        station="Station2",
        queue=(QueueItem(12, "circle"), QueueItem(13, "triangle")),
    )

    assert pipeline.current_object == "circle"
    assert pipeline.display_station == "STATION2"
    assert [item.shape for item in pipeline.queue] == ["circle", "triangle"]


def test_last_sort_sequence_deduplicates_and_maps_all_bins() -> None:
    tracker = SortSequenceTracker()

    assert tracker.update(_pipeline()) is None
    assert tracker.update(_pipeline(last_sort="Branch1", sequence=1)) == "Branch1"
    assert tracker.update(_pipeline(last_sort="Branch1", sequence=1)) is None
    assert tracker.update(_pipeline(last_sort="Branch2", sequence=2)) == "Branch2"
    assert tracker.update(_pipeline(last_sort="Branch3", sequence=3)) == "Branch3"

    assert tracker.counts == {"Branch1": 1, "Branch2": 1, "Branch3": 1}
    assert [bin_for_branch(branch) for branch in ("Branch1", "Branch2", "Branch3")] == [
        "Triangle Bin",
        "Circle Bin",
        "Rectangle Bin",
    ]
    assert [station_for_branch(branch) for branch in ("Branch1", "Branch2", "Branch3")] == [
        "Station1",
        "Station2",
        "Station3",
    ]


def test_reset_pipeline_clears_fifo_and_current_station_object() -> None:
    before_reset = _pipeline(
        station="Station3",
        queue=(QueueItem(12, "rectangle"),),
        last_sort="Branch2",
        sequence=8,
    )
    after_reset = _pipeline()

    assert before_reset.queue_length == 1
    assert before_reset.current_object == "rectangle"
    assert after_reset.queue_length == 0
    assert after_reset.current_object is None
    assert after_reset.display_station == "IDLE"
