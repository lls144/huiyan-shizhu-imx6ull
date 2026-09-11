"""Explainable deterministic association and lifecycle state manager for M4."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .config import EventConfig
from .models import BBox, Detection, EventType, FrameUpdate, ObjectState, VisionEvent


def bbox_iou(first: BBox, second: BBox) -> float:
    """Return intersection-over-union for two (x, y, width, height) boxes."""

    first_right = first[0] + first[2]
    first_bottom = first[1] + first[3]
    second_right = second[0] + second[2]
    second_bottom = second[1] + second[3]
    intersection_width = max(0, min(first_right, second_right) - max(first[0], second[0]))
    intersection_height = max(
        0,
        min(first_bottom, second_bottom) - max(first[1], second[1]),
    )
    intersection = intersection_width * intersection_height
    if intersection == 0:
        return 0.0
    union = first[2] * first[3] + second[2] * second[3] - intersection
    return intersection / union


def bbox_center_distance(first: BBox, second: BBox) -> float:
    first_center = (first[0] + first[2] / 2.0, first[1] + first[3] / 2.0)
    second_center = (second[0] + second[2] / 2.0, second[1] + second[3] / 2.0)
    return math.dist(first_center, second_center)


@dataclass
class _Track:
    object_id: int
    label: str
    bbox: BBox
    first_seen: int
    last_seen: int
    hit_count: int
    consecutive_hits: int
    miss_count: int
    confirmed: bool
    active: bool
    event_emitted: bool
    confidence_sum: float
    latest_confidence: float

    @property
    def mean_confidence(self) -> float:
        return self.confidence_sum / self.hit_count

    def snapshot(self) -> ObjectState:
        if not self.active:
            status = "exited"
        elif not self.confirmed:
            status = "candidate"
        elif self.miss_count:
            status = "pending_exit"
        else:
            status = "confirmed"
        return ObjectState(
            object_id=self.object_id,
            label=self.label,
            bbox=self.bbox,
            first_seen=self.first_seen,
            last_seen=self.last_seen,
            hit_count=self.hit_count,
            consecutive_hits=self.consecutive_hits,
            miss_count=self.miss_count,
            confirmed=self.confirmed,
            active=self.active,
            event_emitted=self.event_emitted,
            status=status,
            confidence=round(self.mean_confidence, 6),
        )


def _detection_key(detection: Detection) -> tuple[float, float, str, int, int]:
    x, y, width, height = detection.bbox
    return (x + width / 2.0, y + height / 2.0, detection.label, width, height)


class ObjectStateManager:
    """Convert ordered detections into lifecycle facts with occlusion grace.

    A confirmed object remains active during ``occlusion_grace_frames`` misses.
    A same-shape detection can recover that pending track only while it is
    active and passes the existing IoU or center-distance association gate.
    Thus a short hand occlusion preserves identity, while a completed exit
    still releases the object ID for a later genuine re-entry.
    """

    def __init__(self, config: EventConfig) -> None:
        config.validate()
        self.config = config
        self._tracks: dict[int, _Track] = {}
        self._next_object_id = 1
        self._next_event_id = 1
        self._last_frame_index: int | None = None

    def _event(self, event_type: EventType, track: _Track, frame_index: int) -> VisionEvent:
        event = VisionEvent(
            event_id=self._next_event_id,
            event_type=event_type,
            object_id=track.object_id,
            label=track.label,
            confidence=round(track.mean_confidence, 6),
            frame_index=frame_index,
        )
        self._next_event_id += 1
        return event

    def _create_track(self, detection: Detection) -> tuple[_Track, VisionEvent | None]:
        confirmed = self.config.min_confirm_frames == 1
        track = _Track(
            object_id=self._next_object_id,
            label=detection.label,
            bbox=detection.bbox,
            first_seen=detection.frame_index,
            last_seen=detection.frame_index,
            hit_count=1,
            consecutive_hits=1,
            miss_count=0,
            confirmed=confirmed,
            active=True,
            event_emitted=confirmed,
            confidence_sum=detection.confidence,
            latest_confidence=detection.confidence,
        )
        self._tracks[track.object_id] = track
        self._next_object_id += 1
        event = (
            self._event(EventType.OBJECT_ENTER, track, detection.frame_index)
            if confirmed
            else None
        )
        return track, event

    def _eligible_pairs(
        self,
        tracks: list[_Track],
        detections: tuple[Detection, ...],
    ) -> list[tuple[float, float, int, int]]:
        pairs: list[tuple[float, float, int, int]] = []
        for track in tracks:
            for detection_index, detection in enumerate(detections):
                if track.label != detection.label:
                    continue
                iou = bbox_iou(track.bbox, detection.bbox)
                distance = bbox_center_distance(track.bbox, detection.bbox)
                if (
                    iou >= self.config.iou_threshold
                    or distance <= self.config.center_distance_threshold
                ):
                    pairs.append((-iou, distance, track.object_id, detection_index))
        return sorted(pairs)

    def _missing_tolerance(self, track: _Track) -> int:
        """Return candidate or entered-object disappearance allowance."""

        return (
            self.config.occlusion_grace_frames
            if track.confirmed
            else self.config.max_missing_frames
        )

    def process_frame(
        self,
        frame_index: int,
        detections: list[Detection] | tuple[Detection, ...],
    ) -> FrameUpdate:
        """Process exactly one strictly increasing frame without wall-clock state."""

        if frame_index < 0:
            raise ValueError("frame_index must be non-negative")
        if self._last_frame_index is not None and frame_index <= self._last_frame_index:
            raise ValueError("frame_index must increase strictly")
        ordered_detections = tuple(detections)
        if any(detection.frame_index != frame_index for detection in ordered_detections):
            raise ValueError("all detections must carry the processed frame_index")
        self._last_frame_index = frame_index

        active_tracks = sorted(
            (track for track in self._tracks.values() if track.active),
            key=lambda track: track.object_id,
        )
        matched_track_ids: set[int] = set()
        matched_detection_indexes: set[int] = set()
        matches: list[tuple[_Track, Detection]] = []
        for _, _, object_id, detection_index in self._eligible_pairs(
            active_tracks,
            ordered_detections,
        ):
            if object_id in matched_track_ids or detection_index in matched_detection_indexes:
                continue
            matched_track_ids.add(object_id)
            matched_detection_indexes.add(detection_index)
            matches.append((self._tracks[object_id], ordered_detections[detection_index]))

        events: list[VisionEvent] = []
        for track, detection in sorted(matches, key=lambda pair: pair[0].object_id):
            track.bbox = detection.bbox
            track.last_seen = frame_index
            track.hit_count += 1
            track.consecutive_hits += 1
            track.miss_count = 0
            track.latest_confidence = detection.confidence
            track.confidence_sum += detection.confidence
            if not track.confirmed and track.consecutive_hits >= self.config.min_confirm_frames:
                track.confirmed = True
                track.event_emitted = True
                events.append(self._event(EventType.OBJECT_ENTER, track, frame_index))

        for track in active_tracks:
            if track.object_id in matched_track_ids:
                continue
            track.miss_count += 1
            track.consecutive_hits = 0
            if track.miss_count > self._missing_tolerance(track):
                track.active = False
                if track.confirmed:
                    events.append(self._event(EventType.OBJECT_EXIT, track, frame_index))

        unmatched = [
            detection
            for index, detection in enumerate(ordered_detections)
            if index not in matched_detection_indexes
        ]
        for detection in sorted(unmatched, key=_detection_key):
            _, event = self._create_track(detection)
            if event is not None:
                events.append(event)

        states = tuple(
            track.snapshot()
            for track in sorted(self._tracks.values(), key=lambda item: item.object_id)
        )
        return FrameUpdate(frame_index, ordered_detections, states, tuple(events))

    def object_states(self) -> tuple[ObjectState, ...]:
        return tuple(
            track.snapshot()
            for track in sorted(self._tracks.values(), key=lambda item: item.object_id)
        )
