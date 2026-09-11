"""Three-station sorting FSM. It has no GPIO, display or TCP dependency."""

from __future__ import annotations

from typing import Dict

from .fifo import FifoQueue
from .models import Key, PipelineTransition, TransitionKind


class PipelineFSM:
    """Advance only the FIFO front command through its shape-specific route."""

    _ROUTES = {
        "triangle": ((Key.KEY1, "Branch1"),),
        "circle": ((Key.KEY1, None), (Key.KEY2, "Branch2")),
        "rectangle": ((Key.KEY1, None), (Key.KEY2, None), (Key.KEY3, "Branch3")),
    }

    def __init__(self, fifo: FifoQueue) -> None:
        self.fifo = fifo
        self._station_index = 0

    @property
    def station(self) -> str:
        return "idle" if self.fifo.empty else f"Station{self._station_index + 1}"

    def reset(self) -> None:
        self._station_index = 0

    def handle_key(self, key: Key) -> PipelineTransition:
        command = self.fifo.peek()
        if command is None:
            self.reset()
            return PipelineTransition(TransitionKind.EMPTY, self.station)
        expected_key, branch = self._ROUTES[command.shape][self._station_index]
        if key != expected_key:
            return PipelineTransition(TransitionKind.WRONG_STATION, self.station, command)
        if branch is not None:
            sorted_command = self.fifo.dequeue()
            self.reset()
            return PipelineTransition(TransitionKind.SORTED, self.station, sorted_command, branch)
        self._station_index += 1
        return PipelineTransition(TransitionKind.MOVED, self.station, command)

    def snapshot(self) -> Dict[str, object]:
        front = self.fifo.front
        return {
            "station": self.station,
            "queue_length": self.fifo.queue_length,
            "capacity": self.fifo.capacity,
            "empty": self.fifo.empty,
            "full": self.fifo.full,
            "front": front.to_record() if front is not None else None,
            # The ordered list is additive state for observers such as the
            # LCD HMI.  It never grants them mutation access to the FIFO.
            "queue": [command.to_record() for command in self.fifo.snapshot()],
        }
