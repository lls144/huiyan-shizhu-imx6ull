"""M10 HMI data-model tests; no Qt display server is required."""

from __future__ import annotations

import unittest

from device.imx6ull.hmi.view_model import HmiViewModel


def _state(
    queue=None,
    station="idle",
    transition="idle",
    last_key=None,
    last_sort=None,
):
    queue = list(queue or [])
    return {
        "queue_length": len(queue),
        "capacity": 3,
        "queue": queue,
        "front": queue[0] if queue else None,
        "station": station,
        "last_transition": transition,
        "last_key": last_key,
        "last_sort": last_sort,
    }


def _command(command_id, shape):
    return {"command_id": command_id, "shape": shape, "source_event_id": None, "source_object_id": None}


class HmiViewModelTests(unittest.TestCase):
    def setUp(self):
        self.model = HmiViewModel()

    def test_offline_state_is_safe(self):
        state = self.model.set_offline("connection refused")
        self.assertFalse(state.online)
        self.assertEqual(state.station, "OFFLINE")
        self.assertEqual(state.error, "connection refused")

    def test_empty_fifo_is_idle(self):
        state = self.model.apply_pipeline_state(_state())
        self.assertTrue(state.online)
        self.assertEqual((state.queue_length, state.capacity), (0, 3))
        self.assertEqual(state.queue_shapes, ())
        self.assertEqual(state.process_state, "IDLE")

    def test_fifo_order_and_full_capacity_are_preserved_for_display(self):
        queue = [_command(1, "triangle"), _command(2, "circle"), _command(3, "rectangle")]
        state = self.model.apply_pipeline_state(_state(queue, station="Station1", transition="waiting"))
        self.assertEqual((state.queue_length, state.capacity), (3, 3))
        self.assertEqual(state.queue_shapes, ("triangle", "circle", "rectangle"))
        self.assertEqual((state.front_id, state.front_shape), ("1", "triangle"))
        self.assertEqual(state.process_state, "WAITING")

    def test_all_station_values_are_displayed(self):
        command = [_command(7, "rectangle")]
        for station in ("Station1", "Station2", "Station3"):
            with self.subTest(station=station):
                state = self.model.apply_pipeline_state(_state(command, station=station, transition="moved"))
                self.assertEqual(state.station, station)
                self.assertEqual(state.process_state, "WAITING")

    def test_sorted_event_counts_once_across_repeated_polls(self):
        sort = {"sequence": 4, "command": _command(9, "circle"), "branch": "Branch2"}
        first = self.model.apply_pipeline_state(_state(transition="sorted", last_key="KEY2", last_sort=sort))
        second = self.model.apply_pipeline_state(_state(transition="sorted", last_key="KEY2", last_sort=sort))
        self.assertEqual(first.last_sort, "circle -> Branch2")
        self.assertEqual(second.circle_count, 1)
        self.assertEqual(second.total_count, 1)
        self.assertEqual(second.last_key, "KEY2")
        self.assertEqual(second.process_state, "SORTED")

    def test_all_branch_shapes_increment_matching_session_counter(self):
        cases = (("triangle", "Branch1"), ("circle", "Branch2"), ("rectangle", "Branch3"))
        for sequence, (shape, branch) in enumerate(cases, 1):
            self.model.apply_pipeline_state(
                _state(transition="sorted", last_sort={"sequence": sequence, "command": _command(sequence, shape), "branch": branch})
            )
        state = self.model.state
        self.assertEqual((state.triangle_count, state.circle_count, state.rectangle_count, state.total_count), (1, 1, 1, 3))

    def test_reset_snapshot_preserves_session_counters_but_returns_idle(self):
        self.model.apply_pipeline_state(
            _state(transition="sorted", last_sort={"sequence": 1, "command": _command(1, "triangle"), "branch": "Branch1"})
        )
        state = self.model.apply_pipeline_state(_state())
        self.assertEqual(state.process_state, "IDLE")
        self.assertEqual(state.triangle_count, 1)
        self.assertEqual(state.last_sort, "-")

    def test_malformed_state_fails_closed_without_crashing(self):
        state = self.model.apply_pipeline_state({"queue_length": "bad"})
        self.assertFalse(state.online)
        self.assertIn("invalid controller state", state.error)
