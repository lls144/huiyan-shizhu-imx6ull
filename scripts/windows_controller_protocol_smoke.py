#!/usr/bin/env python3
"""Smoke-test the real Windows Ethernet Controller route through ControllerClient.

This is an operator-run verification utility.  It intentionally performs only
heartbeat, pipeline-state inspection, and reset; it neither starts a server nor
implements the wire protocol itself.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import TimeoutError as FutureTimeout
from pathlib import Path
from typing import Any, Callable, Dict


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO_ROOT / "pc" / "config" / "controller_windows_ethernet.json"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pc.communication.controller_client import ControllerClientError, ControllerTimeout
from pc.communication.vision_bridge import load_controller_connection_config


def _await_response(label: str, request: Callable[[], Any], timeout: float) -> Dict[str, Any]:
    """Wait for one ControllerClient future and print its complete board reply."""

    started = time.monotonic()
    response = request().result(timeout)
    elapsed_ms = round((time.monotonic() - started) * 1000, 1)
    if not isinstance(response, dict):
        raise AssertionError(f"{label}: expected object response, got {response!r}")
    print(
        f"PASS {label} ({elapsed_ms} ms): "
        f"{json.dumps(response, ensure_ascii=False, sort_keys=True)}"
    )
    return response


def run_smoke(config_path: Path) -> int:
    """Run the minimal real-board protocol vector using the configured client."""

    connection = load_controller_connection_config(config_path)
    result_timeout = connection.ack_timeout * (connection.max_retries + 2) + connection.connect_timeout
    client = connection.make_client()
    print(
        "CONFIG "
        + json.dumps(
            {
                "config": str(config_path),
                "host": connection.host,
                "port": connection.port,
                "connect_timeout": connection.connect_timeout,
                "ack_timeout": connection.ack_timeout,
                "reconnect_delay": connection.reconnect_delay,
                "max_retries": connection.max_retries,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    try:
        client.start()
        if not client.wait_connected(connection.connect_timeout + connection.reconnect_delay):
            raise ConnectionError(
                f"ControllerClient did not connect to {connection.host}:{connection.port} "
                f"within {connection.connect_timeout + connection.reconnect_delay:.1f}s"
            )
        print(f"PASS connect: {connection.host}:{connection.port}")

        heartbeat = _await_response("heartbeat", client.send_heartbeat, result_timeout)
        if heartbeat.get("type") != "ack" or heartbeat.get("status") != "alive":
            raise AssertionError(f"heartbeat: expected ack/alive, got {heartbeat!r}")

        state = _await_response("pipeline_state", client.request_pipeline_state, result_timeout)
        if state.get("type") != "pipeline_state" or not isinstance(state.get("pipeline_state"), dict):
            raise AssertionError(f"pipeline_state: expected a pipeline snapshot, got {state!r}")

        reset = _await_response("reset", client.send_reset, result_timeout)
        if reset.get("type") != "ack" or reset.get("status") != "reset":
            raise AssertionError(f"reset: expected ack/reset, got {reset!r}")

        # ControllerClient's public API exposes a timeout error, not retry-count
        # telemetry.  A clean reply means the configured retry policy was not
        # needed on this live link; packet-loss retry remains a separate fault test.
        print(
            "PASS timeout/retry: no ControllerTimeout; "
            f"policy max_retries={connection.max_retries}, ack_timeout={connection.ack_timeout}s; "
            "retries not exercised by this clean live-link smoke"
        )
        return 0
    finally:
        client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--controller-config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="Controller JSON profile (defaults to the formal Windows Ethernet profile)",
    )
    args = parser.parse_args()
    try:
        return run_smoke(args.controller_config)
    except (AssertionError, ConnectionError, ControllerTimeout, ControllerClientError, FutureTimeout, OSError) as error:
        print(f"SMOKE FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
