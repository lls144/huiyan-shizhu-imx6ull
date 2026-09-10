"""Input abstraction; M9-A adds a configuration-only GPIO backend."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass
from enum import Enum
import os
from pathlib import Path
import select
import struct
from typing import Deque, Dict, Mapping, Optional, Set, Union

from .models import Key


class KeyInputStatus(str, Enum):
    EVENT = "EVENT"
    NO_EVENT = "NO_EVENT"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class KeyInputResult:
    status: KeyInputStatus
    key: Optional[Key] = None


class IKeyInput(ABC):
    @abstractmethod
    def poll(self) -> KeyInputResult:
        """Return one input observation without binding the core to a device API."""

    def read_key(self) -> Optional[Key]:
        """Compatibility helper for the M8 FSM; unavailable input yields None."""

        return self.poll().key


class KeyboardKeyInput(IKeyInput):
    """Desktop test input queue; callers explicitly submit KEY1/KEY2/KEY3."""

    def __init__(self) -> None:
        self._events = deque()  # type: Deque[Key]

    def submit(self, key: Union[Key, str]) -> None:
        self._events.append(Key(key))

    def poll(self) -> KeyInputResult:
        key = self._events.popleft() if self._events else None
        return KeyInputResult(KeyInputStatus.EVENT, key) if key is not None else KeyInputResult(KeyInputStatus.NO_EVENT)


class GpioKeyInput(IKeyInput):
    """Future GPIO backend that is deliberately inert until all pins are configured.

    M9-A neither opens a GPIO chip nor assumes Linux numbering. A later board
    integration can add event reads behind this same interface after the board
    pin mapping and electrical polarity are verified.
    """

    def __init__(self, gpio_keys: Mapping[str, Optional[int]]) -> None:
        self.gpio_keys = {name: gpio_keys.get(name) for name in ("key1", "key2", "key3")}
        for name, line in self.gpio_keys.items():
            if line is not None and (type(line) is not int or line < 0):
                raise ValueError(f"{name} must be a non-negative GPIO line or null")

    @property
    def configured(self) -> bool:
        return all(line is not None for line in self.gpio_keys.values())

    def poll(self) -> KeyInputResult:
        if not self.configured:
            return KeyInputResult(KeyInputStatus.NOT_CONFIGURED)
        return KeyInputResult(KeyInputStatus.NO_EVENT)


class LinuxInputKeyInput(IKeyInput):
    """Read gpio-keys events by stable input-device name, never event number.

    gpio-keys performs electrical debounce and active-low conversion in the
    kernel. This backend accepts only EV_KEY press values, suppresses held-key
    repeats defensively, and leaves release events out of the Pipeline FSM.
    """

    _EV_KEY = 0x01
    _INPUT_EVENT = struct.Struct("@llHHi")

    def __init__(
        self,
        device_name: Optional[str],
        key_codes: Mapping[int, Union[Key, str]],
        sys_class_input: Path = Path("/sys/class/input"),
        input_directory: Path = Path("/dev/input"),
    ) -> None:
        if device_name is not None and (not isinstance(device_name, str) or not device_name):
            raise ValueError("device_name must be a non-empty string or null")
        self.device_name = device_name
        self.key_codes = {int(code): Key(key) for code, key in key_codes.items()}
        if not self.key_codes or any(code <= 0 for code in self.key_codes):
            raise ValueError("key_codes must map positive input codes")
        if len(set(self.key_codes.values())) != len(self.key_codes):
            raise ValueError("key_codes must map each controller key once")
        self._sys_class_input = sys_class_input
        self._input_directory = input_directory
        self._descriptor = None  # type: Optional[int]
        self._buffer = bytearray()
        self._pending = deque()  # type: Deque[Key]
        self._pressed_codes = set()  # type: Set[int]

    @property
    def configured(self) -> bool:
        return self.device_name is not None

    def poll(self) -> KeyInputResult:
        if not self.configured:
            return KeyInputResult(KeyInputStatus.NOT_CONFIGURED)
        if self._pending:
            return KeyInputResult(KeyInputStatus.EVENT, self._pending.popleft())
        try:
            self._open_if_needed()
            self._read_available()
        except (OSError, RuntimeError):
            self._close()
            return KeyInputResult(KeyInputStatus.UNAVAILABLE)
        return KeyInputResult(KeyInputStatus.EVENT, self._pending.popleft()) if self._pending else KeyInputResult(KeyInputStatus.NO_EVENT)

    def _open_if_needed(self) -> None:
        if self._descriptor is not None:
            return
        device_path = self._find_device_path()
        self._descriptor = os.open(str(device_path), os.O_RDONLY | os.O_NONBLOCK)

    def _find_device_path(self) -> Path:
        matches = []
        for event_path in sorted(self._sys_class_input.glob("event*")):
            try:
                name = (event_path / "device" / "name").read_text(encoding="utf-8").strip()
            except OSError:
                continue
            if name == self.device_name:
                matches.append(self._input_directory / event_path.name)
        if len(matches) != 1:
            raise RuntimeError("input device {0!r} is unavailable or ambiguous".format(self.device_name))
        return matches[0]

    def _read_available(self) -> None:
        if self._descriptor is None:
            return
        readable, _, _ = select.select([self._descriptor], [], [], 0)
        if not readable:
            return
        data = os.read(self._descriptor, self._INPUT_EVENT.size * 64)
        if not data:
            raise OSError("input device closed")
        self._buffer.extend(data)
        while len(self._buffer) >= self._INPUT_EVENT.size:
            raw = bytes(self._buffer[:self._INPUT_EVENT.size])
            del self._buffer[:self._INPUT_EVENT.size]
            _, _, event_type, code, value = self._INPUT_EVENT.unpack(raw)
            if event_type != self._EV_KEY or code not in self.key_codes:
                continue
            if value == 0:
                self._pressed_codes.discard(code)
            elif value == 1 and code not in self._pressed_codes:
                self._pressed_codes.add(code)
                self._pending.append(self.key_codes[code])

    def _close(self) -> None:
        if self._descriptor is not None:
            try:
                os.close(self._descriptor)
            except OSError:
                pass
        self._descriptor = None
        self._buffer.clear()
        self._pressed_codes.clear()
