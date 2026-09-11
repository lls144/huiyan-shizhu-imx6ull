"""Controller composition root: TCP-facing operations over FIFO and PipelineFSM."""

from __future__ import annotations

import threading
from collections import deque
from typing import Any, Deque, Dict, Optional, Set, Tuple, Union

from .fifo import FifoQueue
from .key_input import IKeyInput
from .models import BranchOutputEvent, Command, CoreResult, Key, OutputEvent, OutputOffEvent, TransitionKind
from .pipeline import PipelineFSM


class ControllerCore:
    def __init__(self, capacity: int = 3) -> None:
        self.fifo = FifoQueue(capacity)
        self.pipeline = PipelineFSM(self.fifo)
        self._accepted_command_ids = set()  # type: Set[int]
        self._output_events = deque()  # type: Deque[OutputEvent]
        self._last_key = None  # type: Optional[str]
        self._last_sort = None  # type: Optional[Dict[str, Any]]
        self._last_transition = "idle"
        self._sort_sequence = 0
        self._lock = threading.RLock()

    def pipeline_state(self) -> Dict[str, object]:
        with self._lock:
            state = self.pipeline.snapshot()
            state["last_key"] = self._last_key
            state["last_transition"] = self._last_transition
            state["last_sort"] = dict(self._last_sort) if self._last_sort is not None else None
            return state

    def enqueue(
        self,
        command_id: int,
        shape: str,
        *,
        source_event_id: Optional[int] = None,
        source_object_id: Optional[int] = None,
    ) -> CoreResult:
        with self._lock:
            command = Command(command_id, shape, source_event_id, source_object_id)
            if command.command_id in self._accepted_command_ids:
                return CoreResult("duplicate", self.pipeline_state())
            if not self.fifo.enqueue(command):
                return CoreResult("queue_full", self.pipeline_state())
            self._accepted_command_ids.add(command.command_id)
            self._last_transition = "waiting"
            return CoreResult("accepted", self.pipeline_state())

    def handle_key(self, key: Union[Key, str]) -> CoreResult:
        with self._lock:
            normalized_key = Key(key)
            transition = self.pipeline.handle_key(normalized_key)
            # A wrong/empty key must be observationally inert to preserve the
            # M8 state contract.  The HMI therefore shows the most recent key
            # that actually advanced or completed the front command.
            if transition.kind not in (TransitionKind.WRONG_STATION, TransitionKind.EMPTY):
                self._last_key = normalized_key.value
                self._last_transition = transition.kind.value.lower()
            if transition.kind is TransitionKind.SORTED and transition.command is not None:
                self._sort_sequence += 1
                self._last_sort = {
                    "sequence": self._sort_sequence,
                    "command": transition.command.to_record(),
                    "branch": transition.branch,
                }
            result = CoreResult(
                transition.kind.value.lower(),
                self.pipeline_state(),
                transition.command,
                transition.branch,
            )
            if transition.kind is TransitionKind.SORTED:
                # PipelineFSM remains hardware-agnostic.  The composition root
                # drains this small in-memory event queue without blocking TCP
                # or key input processing.
                self._output_events.append(BranchOutputEvent(transition.branch or ""))
            return result

    def process_key_input(self, key_input: IKeyInput) -> Optional[CoreResult]:
        key = key_input.read_key()
        return self.handle_key(key) if key is not None else None

    def reset(self) -> CoreResult:
        with self._lock:
            self.fifo.clear()
            self.pipeline.reset()
            self._accepted_command_ids.clear()
            self._last_key = None
            self._last_sort = None
            self._last_transition = "idle"
            self._output_events.append(OutputOffEvent())
            return CoreResult("reset", self.pipeline_state())

    def drain_output_events(self) -> Tuple[OutputEvent, ...]:
        """Return and clear pending branch-display events without hardware I/O."""

        with self._lock:
            events = tuple(self._output_events)
            self._output_events.clear()
            return events
