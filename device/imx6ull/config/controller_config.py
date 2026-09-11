"""Load the deployment-neutral JSON configuration for the controller process."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Union


@dataclass(frozen=True)
class GpioKeyConfig:
    key1: Optional[int]
    key2: Optional[int]
    key3: Optional[int]

    @classmethod
    def from_dict(cls, value: object) -> "GpioKeyConfig":
        if not isinstance(value, dict):
            raise ValueError("gpio must be an object")
        fields = {name: value.get(name) for name in ("key1", "key2", "key3")}
        for name, line in fields.items():
            if line is not None and (type(line) is not int or line < 0):
                raise ValueError(f"gpio.{name} must be a non-negative integer or null")
        return cls(**fields)

    def to_mapping(self) -> Dict[str, Optional[int]]:
        return {"key1": self.key1, "key2": self.key2, "key3": self.key3}


@dataclass(frozen=True)
class LinuxInputConfig:
    """Stable Linux input identity and code mapping for the gpio-keys device."""

    device_name: Optional[str]
    key1_code: int
    key2_code: int
    key3_code: int

    @classmethod
    def from_dict(cls, value: object) -> "LinuxInputConfig":
        if not isinstance(value, dict):
            raise ValueError("linux_input must be an object")
        device_name = value.get("device_name")
        if device_name is not None and (not isinstance(device_name, str) or not device_name):
            raise ValueError("linux_input.device_name must be a non-empty string or null")
        codes = value.get("key_codes", {})
        if not isinstance(codes, dict):
            raise ValueError("linux_input.key_codes must be an object")
        fields = {name: codes.get(name, default) for name, default in (("KEY1", 148), ("KEY2", 149), ("KEY3", 202))}
        if set(codes) - set(fields):
            raise ValueError("linux_input.key_codes must contain only KEY1, KEY2, and KEY3")
        if any(type(code) is not int or code <= 0 for code in fields.values()):
            raise ValueError("linux_input key codes must be positive integers")
        if len(set(fields.values())) != 3:
            raise ValueError("linux_input key codes must be distinct")
        return cls(device_name, fields["KEY1"], fields["KEY2"], fields["KEY3"])

    def to_mapping(self) -> Dict[int, str]:
        return {self.key1_code: "KEY1", self.key2_code: "KEY2", self.key3_code: "KEY3"}


@dataclass(frozen=True)
class LedOutputConfig:
    """Unprivileged Controller connection details; helper policy remains root-owned."""

    enabled: bool
    socket_path: str

    @classmethod
    def from_dict(cls, value: object) -> "LedOutputConfig":
        if not isinstance(value, dict):
            raise ValueError("led_output must be an object")
        enabled = value.get("enabled", False)
        socket_path = value.get("socket_path", "/run/huiyan-led/helper.sock")
        if type(enabled) is not bool:
            raise ValueError("led_output.enabled must be a boolean")
        if not isinstance(socket_path, str) or not socket_path.startswith("/"):
            raise ValueError("led_output.socket_path must be an absolute path")
        return cls(enabled, socket_path)


@dataclass(frozen=True)
class ControllerConfig:
    tcp_port: int
    fifo_capacity: int
    heartbeat_interval: int
    gpio: GpioKeyConfig
    linux_input: LinuxInputConfig
    led_output: LedOutputConfig

    @classmethod
    def from_dict(cls, value: object) -> "ControllerConfig":
        if not isinstance(value, dict):
            raise ValueError("controller config root must be an object")
        tcp_port = value.get("tcp_port")
        fifo_capacity = value.get("fifo_capacity")
        heartbeat_interval = value.get("heartbeat_interval")
        if type(tcp_port) is not int or not 1 <= tcp_port <= 65535:
            raise ValueError("tcp_port must be an integer in [1, 65535]")
        if type(fifo_capacity) is not int or fifo_capacity <= 0:
            raise ValueError("fifo_capacity must be a positive integer")
        if type(heartbeat_interval) is not int or heartbeat_interval <= 0:
            raise ValueError("heartbeat_interval must be a positive integer")
        return cls(
            tcp_port,
            fifo_capacity,
            heartbeat_interval,
            GpioKeyConfig.from_dict(value.get("gpio")),
            LinuxInputConfig.from_dict(value.get("linux_input", {})),
            LedOutputConfig.from_dict(value.get("led_output", {})),
        )


def load_controller_config(path: Union[str, Path]) -> ControllerConfig:
    payload: Any = json.loads(Path(path).read_text(encoding="utf-8"))
    return ControllerConfig.from_dict(payload)
