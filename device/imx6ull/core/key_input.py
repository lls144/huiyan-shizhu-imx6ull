"""Input abstraction; M9-A adds a configuration-only GPIO backend."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Deque, Dict, Mapping, Optional, Union

from .models import Key


class KeyInputStatus(str, Enum):
    EVENT = "EVENT"
    NO_EVENT = "NO_EVENT"
    NOT_CONFIGURED = "NOT_CONFIGURED"


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
