"""Config-driven Desktop or future i.MX6ULL controller process entry point."""

from __future__ import annotations

import argparse
import sys
import threading
from dataclasses import dataclass
from pathlib import Path

# ``python3 device/imx6ull/controller_main.py`` is the operator-facing launch
# form used on the board.  In that form Python puts ``device/imx6ull`` rather
# than the repository root on sys.path, so make the package root explicit.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from device.imx6ull.config import ControllerConfig, load_controller_config
from device.imx6ull.core import IKeyInput, KeyboardKeyInput, LinuxInputKeyInput
from device.imx6ull.core.models import Key
from device.imx6ull.core.controller import ControllerCore
from device.imx6ull.network.tcp_server import DesktopControllerServer
from device.imx6ull.output import BranchOutputDispatcher, NullBranchOutputBackend, UnixSocketBranchOutputBackend


@dataclass(frozen=True)
class ControllerRuntime:
    config: ControllerConfig
    key_input: IKeyInput
    server: DesktopControllerServer
    output_dispatcher: BranchOutputDispatcher


def build_runtime(config: ControllerConfig, mode: str, host: str = "0.0.0.0") -> ControllerRuntime:
    if mode == "desktop":
        key_input = KeyboardKeyInput()  # type: IKeyInput
    elif mode == "imx6ull":
        key_input = LinuxInputKeyInput(
            config.linux_input.device_name,
            {code: Key(key) for code, key in config.linux_input.to_mapping().items()},
        )
    else:
        raise ValueError("mode must be desktop or imx6ull")
    core = ControllerCore(capacity=config.fifo_capacity)
    backend = (
        UnixSocketBranchOutputBackend(config.led_output.socket_path)
        if config.led_output.enabled
        else NullBranchOutputBackend()
    )
    return ControllerRuntime(
        config,
        key_input,
        DesktopControllerServer(host, config.tcp_port, core=core),
        BranchOutputDispatcher(backend),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("desktop", "imx6ull"), default="desktop")
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("config") / "controller.json")
    parser.add_argument("--host", default="0.0.0.0")
    return parser


def main() -> int:
    args = _parser().parse_args()
    runtime = build_runtime(load_controller_config(args.config), args.mode, args.host)
    runtime.server.start()
    runtime.output_dispatcher.start()
    host, port = runtime.server.address
    print(f"controller mode={args.mode} listening on {host}:{port}", flush=True)
    print(f"key input status={runtime.key_input.poll().status.value}", flush=True)
    try:
        while True:
            result = runtime.server.core.process_key_input(runtime.key_input)
            for event in runtime.server.core.drain_output_events():
                runtime.output_dispatcher.submit(event)
            if result is not None:
                print(
                    "hardware key status={0} branch={1} queue_length={2}".format(
                        result.status, result.branch, result.pipeline_state["queue_length"]
                    ),
                    flush=True,
                )
            threading.Event().wait(0.01)
    except KeyboardInterrupt:
        return 0
    finally:
        runtime.output_dispatcher.close()
        runtime.server.close()


if __name__ == "__main__":
    raise SystemExit(main())
