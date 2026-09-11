"""Minimal M3 multi-object preview and paired lighting-method evidence."""

from __future__ import annotations

import csv
import json
import platform
import sys
import time
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Sequence

import cv2
import numpy as np

from pc.events.adapters import detections_from_analysis
from pc.events.config import EventConfig, load_event_config
from pc.events.models import FrameUpdate, VisionEvent
from pc.events.tracker import ObjectStateManager

from .config import VisionConfig
from .live import (
    FpsMeter,
    LiveCamera,
    _camera_actual_properties,
    _filename_timestamp,
    _git_state,
    _timestamp,
    _write_session_report,
    open_live_camera,
)
from .pipeline import MultiImageAnalysis, analyze_multiple_objects, annotated_multi_image
from .preprocess import Image
from .reporting import write_image
from .roi import (
    CalibrationResult,
    NormalizedRoi,
    RoiMode,
    calibrate_roi,
    load_runtime_calibration,
    save_runtime_calibration,
    select_manual_roi,
)

SCENARIO_KEYS = {
    ord("1"): "normal_light",
    ord("2"): "bright_or_side_light",
    ord("3"): "dark_light",
    ord("4"): "partial_occlusion",
    ord("5"): "touching_or_merged",
}
SUPPORTED_PREPROCESS_MODES = ("otsu", "clahe_otsu")


def _config_for_mode(config: VisionConfig, mode: str) -> VisionConfig:
    if mode not in SUPPORTED_PREPROCESS_MODES:
        raise ValueError(f"unsupported preprocess mode: {mode}")
    return replace(config, preprocess_mode=mode)


def analyze_preprocess_modes(
    frame: Image,
    config: VisionConfig,
    roi: NormalizedRoi,
) -> dict[str, MultiImageAnalysis]:
    """Run the configured baseline and comparison modes over the same frame."""

    modes = (config.preprocess_mode, config.comparison_preprocess_mode)
    return {
        mode: analyze_multiple_objects(frame, _config_for_mode(config, mode), roi)
        for mode in modes
    }


def _lighting_statistics(analysis: MultiImageAnalysis) -> dict[str, float]:
    gray = analysis.preprocessing.gray
    return {
        "mean": round(float(np.mean(gray)), 3),
        "standard_deviation": round(float(np.std(gray)), 3),
        "p10": round(float(np.percentile(gray, 10)), 3),
        "median": round(float(np.percentile(gray, 50)), 3),
        "p90": round(float(np.percentile(gray, 90)), 3),
    }


def _matches_expected(
    analysis: MultiImageAnalysis,
    expected_labels: Sequence[str],
) -> bool | None:
    if not expected_labels:
        return None
    return sorted(detection.label for detection in analysis.detections) == sorted(expected_labels)


def render_m3_overlay(
    frame: Image,
    analysis: MultiImageAnalysis,
    fps: float,
    calibration: CalibrationResult,
    event_update: FrameUpdate | None = None,
    latest_event: VisionEvent | None = None,
) -> Image:
    """Draw M3 objects plus optional compact M4 state and event information."""

    output = annotated_multi_image(frame, analysis, draw_summary=False)
    labels = ", ".join(detection.label for detection in analysis.detections) or "no_object"
    lines = [
        f"M3 raw objects={len(analysis.detections)} [{labels}]",
        f"mode={analysis.preprocessing.preprocess_mode}  FPS={fps:.1f}",
        f"ROI={calibration.selected_mode}/{calibration.source}",
        "T toggle method | R recalibrate | Q/ESC quit",
        "save pair: 1 normal | 2 bright/side | 3 dark | 4 occlusion | 5 touching",
    ]
    if event_update is not None:
        tracked = ", ".join(
            f"#{state.object_id}:{state.label}"
            for state in event_update.active_objects
        ) or "none"
        lines.append(f"M4 tracked={tracked}")
        if latest_event is not None:
            lines.append(
                f"M4 last={latest_event.event_type.value} "
                f"#{latest_event.object_id}:{latest_event.label}"
            )
    for index, text in enumerate(lines):
        y = 30 + index * 28
        cv2.putText(output, text, (18, y), cv2.FONT_HERSHEY_SIMPLEX, 0.68, (0, 0, 0), 4)
        cv2.putText(output, text, (18, y), cv2.FONT_HERSHEY_SIMPLEX, 0.68, (255, 255, 255), 2)
    return output


def _write_comparison_csv(
    path: Path,
    scenario: str,
    analyses: dict[str, MultiImageAnalysis],
    expected_labels: Sequence[str],
) -> None:
    fieldnames = [
        "scenario",
        "preprocess_mode",
        "matches_expected_labels",
        "object_index",
        "predicted_label",
        "confidence",
        "center_x",
        "center_y",
        "vertices",
        "area_ratio",
        "solidity",
        "circularity",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for mode, analysis in analyses.items():
            matches = _matches_expected(analysis, expected_labels)
            if not analysis.detections:
                writer.writerow(
                    {
                        "scenario": scenario,
                        "preprocess_mode": mode,
                        "matches_expected_labels": matches,
                    }
                )
                continue
            for index, detection in enumerate(analysis.detections, start=1):
                center = detection.center or (None, None)
                features = detection.candidate.features
                writer.writerow(
                    {
                        "scenario": scenario,
                        "preprocess_mode": mode,
                        "matches_expected_labels": matches,
                        "object_index": index,
                        "predicted_label": detection.label,
                        "confidence": detection.confidence,
                        "center_x": center[0],
                        "center_y": center[1],
                        "vertices": features.vertices,
                        "area_ratio": features.area_ratio,
                        "solidity": features.solidity,
                        "circularity": features.circularity,
                    }
                )


def save_m3_comparison_evidence(
    frame: Image,
    analyses: dict[str, MultiImageAnalysis],
    scenario: str,
    expected_labels: Sequence[str],
    calibration: CalibrationResult,
    camera: LiveCamera,
    vision_config: VisionConfig,
    evidence_root: Path,
    event_update: FrameUpdate | None = None,
) -> Path:
    """Save paired same-frame results; acceptance remains pending human review."""

    evidence_dir = evidence_root / f"{_filename_timestamp()}-{scenario}"
    write_image(evidence_dir / "frame.jpg", frame)
    first_analysis = next(iter(analyses.values()))
    write_image(evidence_dir / "roi.jpg", first_analysis.preprocessing.roi)
    method_records: dict[str, dict[str, object]] = {}
    artifacts: dict[str, dict[str, str]] = {}
    for mode, analysis in analyses.items():
        normalized_name = f"{mode}-normalized-gray.png"
        binary_name = f"{mode}-binary.png"
        canny_name = f"{mode}-canny.png"
        annotated_name = f"{mode}-annotated.jpg"
        write_image(evidence_dir / normalized_name, analysis.preprocessing.normalized_gray)
        write_image(evidence_dir / binary_name, analysis.preprocessing.binary)
        write_image(evidence_dir / canny_name, analysis.preprocessing.canny)
        write_image(evidence_dir / annotated_name, annotated_multi_image(frame, analysis))
        record = analysis.to_record()
        record["matches_expected_labels"] = _matches_expected(analysis, expected_labels)
        method_records[mode] = record
        artifacts[mode] = {
            "normalized_gray": normalized_name,
            "binary": binary_name,
            "canny": canny_name,
            "annotated": annotated_name,
        }

    height, width = frame.shape[:2]
    payload = {
        "schema_version": 1,
        "milestone": "M3",
        "acceptance_status": "pending_user_validation",
        "timestamp": _timestamp(),
        "scenario": scenario,
        "scenario_source": "operator_hotkey",
        "expected_labels": list(expected_labels),
        "git": _git_state(),
        "environment": {
            "platform": platform.platform(),
            "python": sys.version.split()[0],
            "opencv": cv2.__version__,
            "numpy": np.__version__,
        },
        "camera_device": asdict(camera.device),
        "camera_config": asdict(camera.config),
        "camera_actual_properties": _camera_actual_properties(camera.capture),
        "frame_resolution": {"width": width, "height": height},
        "roi_mode": calibration.selected_mode,
        "roi_source": calibration.source,
        "normalized_roi": calibration.roi.to_dict(),
        "pixel_roi": list(first_analysis.preprocessing.roi_bounds),
        "lighting_statistics": _lighting_statistics(first_analysis),
        "methods": method_records,
        "vision_config_snapshot": asdict(vision_config),
        "m4_event_snapshot": event_update.to_record() if event_update is not None else None,
        "artifacts": {
            "frame": "frame.jpg",
            "roi": "roi.jpg",
            "comparison_csv": "comparison.csv",
            "methods": artifacts,
        },
    }
    json_path = evidence_dir / "evidence.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_comparison_csv(
        evidence_dir / "comparison.csv",
        scenario,
        analyses,
        expected_labels,
    )
    return json_path


def run_m3_live_session(
    camera_config_path: Path,
    vision_config: VisionConfig,
    requested_roi_mode: RoiMode,
    calibration_path: Path,
    evidence_root: Path,
    expected_labels: Sequence[str],
    reuse_calibration: bool = False,
    event_config_path: Path | None = None,
    event_sink: Optional[Callable[[VisionEvent], Optional[Dict[str, Any]]]] = None,
    stop_after_event_sink_accept: bool = False,
) -> int:
    """Run M3 preview with optional M4 events and paired evidence on keys 1-5.

    ``event_sink`` is deliberately optional and is invoked only after M4 has
    produced a lifecycle event.  The M9 PC-to-Controller bridge uses it for a
    confirmed ``OBJECT_ENTER``; ordinary M3/M4 sessions retain their existing
    no-network behavior.

    When ``stop_after_event_sink_accept`` is true, a non-``None`` result from
    the sink ends the live session successfully after the frame/report have
    been written.  The M9 one-object acceptance path uses this to guarantee
    that one confirmed visual object produces at most one enqueue per run.
    """

    event_config: EventConfig | None = (
        load_event_config(event_config_path) if event_config_path is not None else None
    )
    event_manager = ObjectStateManager(event_config) if event_config is not None else None
    event_records: list[dict[str, object]] = []
    latest_event: VisionEvent | None = None
    camera = open_live_camera(camera_config_path)
    capture = camera.capture
    session_started = time.perf_counter()
    session_path = evidence_root / f"session-{_filename_timestamp()}.json"
    frames_processed = 0
    failed_reads = 0
    consecutive_failures = 0
    processing_started: float | None = None
    completed_normally = False
    session_error: str | None = None
    evidence_records: list[dict[str, str]] = []
    calibration_history: list[dict[str, object]] = []
    session_report: dict[str, Any] = {
        "schema_version": 1,
        "milestone": "M3",
        "acceptance_status": "pending_user_validation",
        "status": "starting",
        "started_at": _timestamp(),
        "git": _git_state(),
        "camera_device": asdict(camera.device),
        "camera_config": asdict(camera.config),
        "camera_actual_properties": _camera_actual_properties(capture),
        "requested_roi_mode": requested_roi_mode,
        "expected_labels": list(expected_labels),
        "preprocess_modes": [
            vision_config.preprocess_mode,
            vision_config.comparison_preprocess_mode,
        ],
        "calibration_file": str(calibration_path),
        "calibration_history": calibration_history,
        "evidence_records": evidence_records,
        "m4_event_tracking": {
            "enabled": event_manager is not None,
            "config_path": str(event_config_path) if event_config_path is not None else None,
            "config": asdict(event_config) if event_config is not None else None,
            "detection_preprocess_mode": (
                vision_config.preprocess_mode if event_manager is not None else None
            ),
            "events": event_records,
            "live_acceptance_status": "pending_user_validation",
        },
    }
    _write_session_report(session_path, session_report)

    try:
        first_frame: Image | None = None
        for _ in range(camera.config.warmup_frames + 1):
            success, candidate = capture.read()
            if success:
                first_frame = candidate
        if first_frame is None:
            raise RuntimeError("camera opened but no frame was received during warmup")

        if reuse_calibration and calibration_path.exists():
            calibration = load_runtime_calibration(calibration_path, first_frame.shape)
            print(f"restored runtime ROI from {calibration_path}: {calibration.roi.to_dict()}")
        else:
            if reuse_calibration:
                print(f"requested saved ROI does not exist: {calibration_path}; starting calibration")
            calibration = calibrate_roi(
                first_frame,
                vision_config,
                requested_roi_mode,
                lambda image: select_manual_roi(image, vision_config),
                print,
            )
        save_runtime_calibration(calibration, first_frame.shape, calibration_path)
        calibration_history.append({"timestamp": _timestamp(), **calibration.to_dict()})
        session_report["status"] = "running"
        session_report["runtime_roi"] = calibration.to_dict()
        _write_session_report(session_path, session_report)

        active_mode = vision_config.preprocess_mode
        fps_meter = FpsMeter(vision_config.fps_smoothing_window)
        frame = first_frame
        window_name = "Huiyan Shizhu M3 Multi-object and Lighting"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(
            window_name,
            vision_config.live_preview_width,
            vision_config.live_preview_height,
        )
        processing_started = time.perf_counter()
        while True:
            accepted_controller_dispatch = False
            active_config = _config_for_mode(vision_config, active_mode)
            analysis = analyze_multiple_objects(frame, active_config, calibration.roi)
            event_update: FrameUpdate | None = None
            if event_manager is not None:
                event_analysis = (
                    analysis
                    if active_mode == vision_config.preprocess_mode
                    else analyze_multiple_objects(
                        frame,
                        _config_for_mode(vision_config, vision_config.preprocess_mode),
                        calibration.roi,
                    )
                )
                event_update = event_manager.process_frame(
                    frames_processed,
                    detections_from_analysis(event_analysis, frames_processed),
                )
                if event_update.events:
                    for event in event_update.events:
                        latest_event = event
                        event_record = event.to_record()
                        if event_sink is not None:
                            dispatch = event_sink(event)
                            if dispatch is not None:
                                event_record["controller_enqueue"] = dispatch
                                accepted_controller_dispatch = True
                        event_records.append(event_record)
                        print(
                            f"M4 {event.event_type.value} event_id={event.event_id} "
                            f"object_id={event.object_id} label={event.label} "
                            f"confidence={event.confidence:.3f} frame={event.frame_index}"
                        )
                    _write_session_report(session_path, session_report)
            fps = fps_meter.update()
            annotated = render_m3_overlay(
                frame,
                analysis,
                fps,
                calibration,
                event_update,
                latest_event,
            )
            cv2.imshow(window_name, annotated)
            if accepted_controller_dispatch and stop_after_event_sink_accept:
                completed_normally = True
                return 0
            frames_processed += 1
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), ord("Q"), 27):
                break
            if key in (ord("t"), ord("T")):
                active_mode = (
                    vision_config.comparison_preprocess_mode
                    if active_mode == vision_config.preprocess_mode
                    else vision_config.preprocess_mode
                )
                print(f"active preprocess mode: {active_mode}")
            elif key in (ord("r"), ord("R")):
                print("ROI recalibration requested; recognition is paused")
                calibration = calibrate_roi(
                    frame,
                    vision_config,
                    requested_roi_mode,
                    lambda image: select_manual_roi(image, vision_config),
                    print,
                )
                save_runtime_calibration(calibration, frame.shape, calibration_path)
                calibration_history.append({"timestamp": _timestamp(), **calibration.to_dict()})
                session_report["runtime_roi"] = calibration.to_dict()
                _write_session_report(session_path, session_report)
            elif key in SCENARIO_KEYS:
                scenario = SCENARIO_KEYS[key]
                analyses = analyze_preprocess_modes(frame, vision_config, calibration.roi)
                evidence_path = save_m3_comparison_evidence(
                    frame,
                    analyses,
                    scenario,
                    expected_labels,
                    calibration,
                    camera,
                    vision_config,
                    evidence_root,
                    event_update,
                )
                evidence_records.append(
                    {
                        "timestamp": _timestamp(),
                        "scenario": scenario,
                        "evidence_json": str(evidence_path),
                    }
                )
                _write_session_report(session_path, session_report)
                print(f"saved M3 paired evidence: {evidence_path}")

            success, next_frame = capture.read()
            if success:
                frame = next_frame
                consecutive_failures = 0
            else:
                failed_reads += 1
                consecutive_failures += 1
                if consecutive_failures >= vision_config.live_max_consecutive_read_failures:
                    raise RuntimeError(
                        f"camera read failed {consecutive_failures} consecutive times"
                    )

        completed_normally = True
        return 0
    except Exception as error:
        session_error = f"{type(error).__name__}: {error}"
        raise
    finally:
        elapsed = time.perf_counter() - session_started
        processing_elapsed = (
            time.perf_counter() - processing_started if processing_started is not None else 0.0
        )
        capture.release()
        cv2.destroyAllWindows()
        session_report.update(
            {
                "status": "completed" if completed_normally else "failed",
                "finished_at": _timestamp(),
                "duration_seconds": round(elapsed, 6),
                "active_processing_seconds": round(processing_elapsed, 6),
                "frames_processed": frames_processed,
                "failed_reads": failed_reads,
                "measured_processing_fps": (
                    round(frames_processed / processing_elapsed, 6)
                    if processing_elapsed
                    else 0.0
                ),
                "evidence_frames_saved": len(evidence_records),
                "error": session_error,
            }
        )
        if event_manager is not None:
            session_report["m4_event_tracking"]["final_object_states"] = [
                state.to_record() for state in event_manager.object_states()
            ]
        _write_session_report(session_path, session_report)
