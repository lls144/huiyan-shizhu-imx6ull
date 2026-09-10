"""Controller composition root: TCP-facing operations over FIFO and PipelineFSM."""

from __future__ import annotations

from .fifo import FifoQueue
from .key_input import IKeyInput
from .models import Command, CoreResult, Key, TransitionKind
from .pipeline import PipelineFSM


class ControllerCore:
    def __init__(self, capacity: int = 3) -> None:
        self.fifo = FifoQueue(capacity)
        self.pipeline = PipelineFSM(self.fifo)
        self._accepted_command_ids: set[int] = set()

    def pipeline_state(self) -> dict[str, object]:
        return self.pipeline.snapshot()

    def enqueue(
        self,
        command_id: int,
        shape: str,
        *,
        source_event_id: int | None = None,
        source_object_id: int | None = None,
    ) -> CoreResult:
        command = Command(command_id, shape, source_event_id, source_object_id)
        if command.command_id in self._accepted_command_ids:
            return CoreResult("duplicate", self.pipeline_state())
        if not self.fifo.enqueue(command):
            return CoreResult("queue_full", self.pipeline_state())
        self._accepted_command_ids.add(command.command_id)
        return CoreResult("accepted", self.pipeline_state())

    def handle_key(self, key: Key | str) -> CoreResult:
        transition = self.pipeline.handle_key(Key(key))
        return CoreResult(
            transition.kind.value.lower(),
            self.pipeline_state(),
            transition.command,
            transition.branch,
        )

    def process_key_input(self, key_input: IKeyInput) -> CoreResult | None:
        key = key_input.read_key()
        return self.handle_key(key) if key is not None else None

    def reset(self) -> CoreResult:
        self.fifo.clear()
        self.pipeline.reset()
        self._accepted_command_ids.clear()
        return CoreResult("reset", self.pipeline_state())
