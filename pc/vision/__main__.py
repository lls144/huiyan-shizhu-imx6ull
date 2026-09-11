"""Command-line entry point for M2 single-object and M3 multi-object vision."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2

from .config import load_vision_config
from .pipeline import analyze_image
from .reporting import (
    diagnostic_montage,
    discover_images,
    result_record,
    write_csv_report,
    write_image,
    write_json_report,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("pc/config/vision.json"),
        help="vision JSON config path",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    batch = subparsers.add_parser("batch", help="analyze the labeled offline M2 image folders")
    batch.add_argument("--input-root", type=Path, required=True)
    batch.add_argument("--output-json", type=Path, required=True)
    batch.add_argument("--output-csv", type=Path, required=True)
    batch.add_argument("--diagnostics-dir", type=Path, required=True)
    batch.add_argument(
        "--acceptance-status",
        choices=("pending_user_validation", "offline_stage_user_validated"),
        default="pending_user_validation",
        help="recorded acceptance state; use validated only after explicit user confirmation",
    )
    batch.add_argument(
        "--evidence-dir",
        type=Path,
        help="optional directory for the first diagnostic montage of each source category",
    )
    live = subparsers.add_parser("live", help="run M2 OpenCV preview with startup ROI calibration")
    live.add_argument(
        "--camera-config",
        type=Path,
        default=Path("pc/config/camera.json"),
        help="existing M1 camera JSON config path",
    )
    live.add_argument(
        "--roi-mode",
        choices=("auto", "manual", "fixed_normalized"),
        default="auto",
        help="startup calibration mode; auto falls back to manual then fixed_normalized",
    )
    live.add_argument(
        "--calibration-file",
        type=Path,
        default=Path("output/m2/runtime-calibration.json"),
        help="ignored local runtime calibration JSON",
    )
    live.add_argument(
        "--reuse-calibration",
        action="store_true",
        help="explicitly restore the saved normalized ROI instead of recalibrating at startup",
    )
    live.add_argument(
        "--evidence-dir",
        type=Path,
        default=Path("output/m2/live-evidence"),
        help="ignored directory for S-key frame evidence and session JSON",
    )
    multi_live = subparsers.add_parser(
        "multi-live",
        help="run M3 multi-object preview and paired lighting-method evidence capture",
    )
    multi_live.add_argument(
        "--camera-config",
        type=Path,
        default=Path("pc/config/camera.json"),
        help="existing M1 camera JSON config path",
    )
    multi_live.add_argument(
        "--roi-mode",
        choices=("auto", "manual", "fixed_normalized"),
        default="auto",
        help="startup calibration mode; auto falls back to manual then fixed_normalized",
    )
    multi_live.add_argument(
        "--calibration-file",
        type=Path,
        default=Path("output/m3/runtime-calibration.json"),
        help="ignored local M3 runtime calibration JSON",
    )
    multi_live.add_argument(
        "--reuse-calibration",
        action="store_true",
        help="explicitly restore the saved normalized ROI instead of recalibrating at startup",
    )
    multi_live.add_argument(
        "--evidence-dir",
        type=Path,
        default=Path("output/m3/live-evidence"),
        help="ignored directory for paired evidence and session JSON",
    )
    multi_live.add_argument(
        "--expected-labels",
        nargs="*",
        choices=("triangle", "rectangle", "circle"),
        default=(),
        help="operator-declared shapes actually placed in the work area",
    )
    multi_live.add_argument(
        "--events",
        action="store_true",
        help="enable optional M4 frame-detection deduplication and lifecycle events",
    )
    multi_live.add_argument(
        "--event-config",
        type=Path,
        default=Path("pc/config/events.json"),
        help="M4 event association JSON config used only with --events",
    )
    multi_live.add_argument(
        "--controller-config",
        type=Path,
        help=(
            "optional M9 PC-to-Controller JSON config; requires --events and "
            "exactly one --expected-labels shape as a fail-closed live-test guard"
        ),
    )
    multi_live.add_argument(
        "--command-id-start",
        type=int,
        help="positive Controller command ID assigned to M4 event_id=1 for this run",
    )
    multi_batch = subparsers.add_parser(
        "multi-batch",
        help="evaluate an M3 scene manifest with both preprocessing modes",
    )
    multi_batch.add_argument("--input-root", type=Path, required=True)
    multi_batch.add_argument("--ground-truth", type=Path, required=True)
    multi_batch.add_argument("--output-json", type=Path, required=True)
    multi_batch.add_argument("--output-csv", type=Path, required=True)
    multi_batch.add_argument(
        "--diagnostics-dir",
        type=Path,
        help="optional directory for annotated results from every scene and mode",
    )
    return parser


def main() -> int:
    parser = _parser()
    args = parser.parse_args()
    config = load_vision_config(args.config)
    if args.command == "live":
        from .live import run_live_session

        return run_live_session(
            camera_config_path=args.camera_config,
            vision_config=config,
            requested_roi_mode=args.roi_mode,
            calibration_path=args.calibration_file,
            evidence_root=args.evidence_dir,
            reuse_calibration=args.reuse_calibration,
        )
    if args.command == "multi-live":
        from .m3_live import run_m3_live_session
        event_sink = None
        client = None
        if args.controller_config is not None:
            if not args.events:
                parser.error("--controller-config requires --events")
            if len(args.expected_labels) != 1:
                parser.error("--controller-config requires exactly one --expected-labels shape")
            if args.command_id_start is None or args.command_id_start < 1:
                parser.error("--controller-config requires a positive --command-id-start")
            from pc.communication.vision_bridge import (
                VisionEventEnqueuer,
                load_controller_connection_config,
            )

            connection = load_controller_connection_config(args.controller_config)
            client = connection.make_client()
            event_sink = VisionEventEnqueuer(
                client,
                args.command_id_start,
                expected_labels=tuple(args.expected_labels),
                result_timeout=connection.ack_timeout * (connection.max_retries + 2),
            ).handle
        try:
            return run_m3_live_session(
                camera_config_path=args.camera_config,
                vision_config=config,
                requested_roi_mode=args.roi_mode,
                calibration_path=args.calibration_file,
                evidence_root=args.evidence_dir,
                expected_labels=tuple(args.expected_labels),
                reuse_calibration=args.reuse_calibration,
                event_config_path=args.event_config if args.events else None,
                event_sink=event_sink,
                stop_after_event_sink_accept=args.controller_config is not None,
            )
        finally:
            if client is not None:
                client.close()
    if args.command == "multi-batch":
        from .m3_reporting import (
            evaluate_synthetic_dataset,
            write_m3_csv_report,
            write_m3_json_report,
        )

        report = evaluate_synthetic_dataset(
            args.input_root,
            args.ground_truth,
            config,
            args.config,
            args.diagnostics_dir,
        )
        write_m3_json_report(report, args.output_json)
        write_m3_csv_report(report, args.output_csv)
        print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
        return 0 if report["summary"]["all_required_scenes_pass"] else 1

    paths = discover_images(args.input_root)
    if not paths:
        print(f"no supported images found under {args.input_root}")
        return 2

    records: list[dict[str, object]] = []
    evidence_categories: set[str] = set()
    for path in paths:
        source = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if source is None:
            raise RuntimeError(f"failed to read image: {path}")
        analysis = analyze_image(source, config)
        record = result_record(path, args.input_root, analysis)
        records.append(record)
        relative_stem = path.relative_to(args.input_root).with_suffix("")
        montage = diagnostic_montage(source, analysis)
        write_image(args.diagnostics_dir / relative_stem.parent / f"{relative_stem.name}_pipeline.jpg", montage)
        source_category = path.parent.name
        if args.evidence_dir is not None and source_category not in evidence_categories:
            write_image(args.evidence_dir / f"M2-{path.stem}-pipeline.jpg", montage)
            evidence_categories.add(source_category)

    report = write_json_report(
        records,
        config,
        args.config,
        args.input_root,
        args.output_json,
        args.acceptance_status,
    )
    write_csv_report(records, args.output_csv)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["summary"]["mismatching_expected_label"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
