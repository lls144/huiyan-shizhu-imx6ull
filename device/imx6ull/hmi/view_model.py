"""Pure, Python 3.7-compatible presentation model for the M10 LCD HMI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Set, Tuple


_SHAPES = frozenset(("triangle", "circle", "rectangle"))
_BRANCHES = frozenset(("Branch1", "Branch2", "Branch3"))


@dataclass(frozen=True)
class HmiViewState:
    """Display-ready immutable values; Qt widgets do not parse protocol JSON."""

    online: bool
    error: str
    queue_length: int
    capacity: int
    queue_shapes: Tuple[str, ...]
    front_id: str
    front_shape: str
    station: str
    process_state: str
    last_sort: str
    last_key: str
    triangle_count: int
    circle_count: int
    rectangle_count: int

    @property
    def total_count(self) -> int:
        return self.triangle_count + self.circle_count + self.rectangle_count


class HmiViewModel:
    """Validate controller snapshots and maintain de-duplicated session counts."""

    def __init__(self) -> None:
        self._counted_sorts = set()  # type: Set[int]
        self._counts = {shape: 0 for shape in _SHAPES}  # type: Dict[str, int]
        self._state = self._offline_state("")

    @property
    def state(self) -> HmiViewState:
        return self._state

    def set_offline(self, error: str = "") -> HmiViewState:
        self._state = self._offline_state(error)
        return self._state

    def apply_pipeline_state(self, value: object) -> HmiViewState:
        """Accept one additive M10 pipeline-state snapshot or fail closed."""

        if not isinstance(value, dict):
            return self.set_offline("invalid controller state")
        try:
            queue_length = self._positive_int_or_zero(value.get("queue_length"))
            capacity = self._positive_int(value.get("capacity"))
            station = self._station(value.get("station"))
            queue = self._queue(value.get("queue"), queue_length)
            front_id, front_shape = self._front(value.get("front"), queue)
            process_state = self._process_state(value.get("last_transition"), queue_length)
            last_sort = self._record_last_sort(value.get("last_sort"))
            last_key = self._last_key(value.get("last_key"))
        except ValueError as error:
            return self.set_offline("invalid controller state: {0}".format(error))
        self._state = HmiViewState(
            True,
            "",
            queue_length,
            capacity,
            tuple(item["shape"] for item in queue),
            front_id,
            front_shape,
            station,
            process_state,
            last_sort,
            last_key,
            self._counts["triangle"],
            self._counts["circle"],
            self._counts["rectangle"],
        )
        return self._state

    @staticmethod
    def _positive_int(value: object) -> int:
        if type(value) is not int or value <= 0:
            raise ValueError("capacity")
        return value

    @staticmethod
    def _positive_int_or_zero(value: object) -> int:
        if type(value) is not int or value < 0:
            raise ValueError("queue_length")
        return value

    @staticmethod
    def _station(value: object) -> str:
        if value == "idle":
            return "IDLE"
        if value in ("Station1", "Station2", "Station3"):
            return str(value)
        raise ValueError("station")

    @staticmethod
    def _queue(value: object, queue_length: int) -> Tuple[Dict[str, Any], ...]:
        if not isinstance(value, list) or len(value) != queue_length:
            raise ValueError("queue")
        result = []
        for command in value:
            if not isinstance(command, dict) or command.get("shape") not in _SHAPES:
                raise ValueError("queue item")
            if type(command.get("command_id")) is not int or command["command_id"] <= 0:
                raise ValueError("queue command_id")
            result.append(command)
        return tuple(result)

    @staticmethod
    def _front(value: object, queue: Tuple[Dict[str, Any], ...]) -> Tuple[str, str]:
        if not queue:
            if value is not None:
                raise ValueError("front")
            return "-", "-"
        if not isinstance(value, dict):
            raise ValueError("front")
        if value.get("command_id") != queue[0].get("command_id") or value.get("shape") != queue[0].get("shape"):
            raise ValueError("front does not match queue")
        return str(value["command_id"]), str(value["shape"])

    @staticmethod
    def _process_state(transition: object, queue_length: int) -> str:
        if transition == "sorted":
            return "SORTED"
        if queue_length == 0:
            return "IDLE"
        return "WAITING"

    def _record_last_sort(self, value: object) -> str:
        if value is None:
            return "-"
        if not isinstance(value, dict):
            raise ValueError("last_sort")
        sequence = value.get("sequence")
        command = value.get("command")
        branch = value.get("branch")
        if type(sequence) is not int or sequence <= 0 or not isinstance(command, dict):
            raise ValueError("last_sort")
        shape = command.get("shape")
        if shape not in _SHAPES or branch not in _BRANCHES:
            raise ValueError("last_sort")
        if sequence not in self._counted_sorts:
            self._counted_sorts.add(sequence)
            self._counts[shape] += 1
        return "{0} -> {1}".format(shape, branch)

    @staticmethod
    def _last_key(value: object) -> str:
        return value if value in ("KEY1", "KEY2", "KEY3") else "-"

    def _offline_state(self, error: str) -> HmiViewState:
        return HmiViewState(
            False,
            error,
            0,
            3,
            (),
            "-",
            "-",
            "OFFLINE",
            "OFFLINE",
            "-",
            "-",
            self._counts["triangle"],
            self._counts["circle"],
            self._counts["rectangle"],
        )
