"""Input abstraction; M9 can provide GpioKeyInput without changing the FSM."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque

from .models import Key


class IKeyInput(ABC):
    @abstractmethod
    def read_key(self) -> Key | None:
        """Return one edge-like key event, or None when no event is pending."""


class KeyboardKeyInput(IKeyInput):
    """Desktop test input queue; callers explicitly submit KEY1/KEY2/KEY3."""

    def __init__(self) -> None:
        self._events: deque[Key] = deque()

    def submit(self, key: Key | str) -> None:
        self._events.append(Key(key))

    def read_key(self) -> Key | None:
        return self._events.popleft() if self._events else None
