"""Bounded FIFO for semantic commands, independent of transport and hardware."""

from __future__ import annotations

from collections import deque
from typing import Deque, Optional, Tuple

from .models import Command


class FifoQueue:
    def __init__(self, capacity: int = 3) -> None:
        if type(capacity) is not int or capacity <= 0:
            raise ValueError("capacity must be a positive integer")
        self.capacity = capacity
        self._items = deque()  # type: Deque[Command]

    @property
    def queue_length(self) -> int:
        return len(self._items)

    @property
    def empty(self) -> bool:
        return not self._items

    @property
    def full(self) -> bool:
        return self.queue_length >= self.capacity

    @property
    def front(self) -> Optional[Command]:
        return self._items[0] if self._items else None

    def enqueue(self, command: Command) -> bool:
        if self.full:
            return False
        self._items.append(command)
        return True

    def dequeue(self) -> Optional[Command]:
        return self._items.popleft() if self._items else None

    def peek(self) -> Optional[Command]:
        return self.front

    def snapshot(self) -> Tuple[Command, ...]:
        """Return the FIFO contents in dequeue order without mutating it."""

        return tuple(self._items)

    def clear(self) -> None:
        self._items.clear()
