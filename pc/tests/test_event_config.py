import json
from pathlib import Path

import pytest

from pc.events.config import EventConfig, load_event_config

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_committed_event_config_loads_expected_values() -> None:
    config = load_event_config(REPO_ROOT / "pc/config/events.json")

    assert config == EventConfig(
        min_confirm_frames=2,
        max_missing_frames=3,
        occlusion_grace_frames=25,
        iou_threshold=0.3,
        center_distance_threshold=80.0,
    )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("min_confirm_frames", 0, "min_confirm_frames"),
        ("max_missing_frames", -1, "max_missing_frames"),
        ("occlusion_grace_frames", 0, "occlusion_grace_frames"),
        ("iou_threshold", 1.1, "iou_threshold"),
        ("center_distance_threshold", -1, "center_distance_threshold"),
    ],
)
def test_invalid_event_config_is_rejected(
    tmp_path: Path,
    field: str,
    value: object,
    message: str,
) -> None:
    values = {
        "min_confirm_frames": 2,
        "max_missing_frames": 3,
        "occlusion_grace_frames": 25,
        "iou_threshold": 0.3,
        "center_distance_threshold": 80.0,
    }
    values[field] = value
    path = tmp_path / "events.json"
    path.write_text(json.dumps({"tracking": values}), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        load_event_config(path)
