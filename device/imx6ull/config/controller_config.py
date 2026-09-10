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
class ControllerConfig:
    tcp_port: int
    fifo_capacity: int
    heartbeat_interval: int
    gpio: GpioKeyConfig

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
        return cls(tcp_port, fifo_capacity, heartbeat_interval, GpioKeyConfig.from_dict(value.get("gpio")))


def load_controller_config(path: Union[str, Path]) -> ControllerConfig:
    payload: Any = json.loads(Path(path).read_text(encoding="utf-8"))
    return ControllerConfig.from_dict(payload)
