"""M8 FIFO and three-station pipeline tests without TCP or hardware."""

from __future__ import annotations

import unittest

from device.imx6ull.core.controller import ControllerCore
from device.imx6ull.core.fifo import FifoQueue
from device.imx6ull.core.key_input import KeyboardKeyInput
from device.imx6ull.core.models import Command, Key, TransitionKind


class ControllerCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.core = ControllerCore(capacity=3)

    def test_triangle_complete_flow(self) -> None:
        self.assertEqual(self.core.enqueue(1, "triangle").status, "accepted")
        result = self.core.handle_key(Key.KEY1)
        self.assertEqual(result.status, "sorted")
        self.assertEqual(result.branch, "Branch1")
        self.assertEqual(result.command.shape, "triangle")
        self.assertTrue(result.pipeline_state["empty"])
        self.assertEqual(result.pipeline_state["station"], "idle")

    def test_circle_complete_flow(self) -> None:
        self.core.enqueue(1, "circle")
        moved = self.core.handle_key(Key.KEY1)
        self.assertEqual(moved.status, "moved")
        self.assertEqual(moved.pipeline_state["station"], "Station2")
        sorted_result = self.core.handle_key(Key.KEY2)
        self.assertEqual(sorted_result.status, "sorted")
        self.assertEqual(sorted_result.branch, "Branch2")
        self.assertTrue(sorted_result.pipeline_state["empty"])

    def test_rectangle_complete_flow(self) -> None:
        self.core.enqueue(1, "rectangle")
        self.assertEqual(self.core.handle_key(Key.KEY1).pipeline_state["station"], "Station2")
        self.assertEqual(self.core.handle_key(Key.KEY2).pipeline_state["station"], "Station3")
        sorted_result = self.core.handle_key(Key.KEY3)
        self.assertEqual(sorted_result.status, "sorted")
        self.assertEqual(sorted_result.branch, "Branch3")
        self.assertTrue(sorted_result.pipeline_state["empty"])

    def test_wrong_station_preserves_queue_and_state(self) -> None:
        self.core.enqueue(1, "circle")
        before = self.core.pipeline_state()
        result = self.core.handle_key(Key.KEY2)
        self.assertEqual(result.status, "wrong_station")
        self.assertEqual(result.pipeline_state, before)
        self.assertEqual(self.core.pipeline.handle_key(Key.KEY2).kind, TransitionKind.WRONG_STATION)

    def test_fifo_capacity_and_order(self) -> None:
        fifo = FifoQueue(capacity=3)
        commands = [Command(1, "triangle"), Command(2, "circle"), Command(3, "rectangle")]
        for command in commands:
            self.assertTrue(fifo.enqueue(command))
        self.assertTrue(fifo.full)
        self.assertEqual(fifo.queue_length, 3)
        self.assertEqual(fifo.front, commands[0])
        self.assertFalse(fifo.enqueue(Command(4, "triangle")))
        self.assertEqual([fifo.dequeue(), fifo.dequeue(), fifo.dequeue()], commands)
        self.assertTrue(fifo.empty)
        self.assertIsNone(fifo.peek())

    def test_reset_clears_fifo_pipeline_and_duplicate_history(self) -> None:
        self.core.enqueue(1, "rectangle")
        self.core.handle_key(Key.KEY1)
        reset = self.core.reset()
        self.assertEqual(reset.status, "reset")
        self.assertTrue(reset.pipeline_state["empty"])
        self.assertEqual(reset.pipeline_state["station"], "idle")
        self.assertEqual(self.core.enqueue(1, "rectangle").status, "accepted")

    def test_duplicate_command_does_not_change_fifo(self) -> None:
        self.assertEqual(self.core.enqueue(7, "triangle").status, "accepted")
        duplicate = self.core.enqueue(7, "triangle")
        self.assertEqual(duplicate.status, "duplicate")
        self.assertEqual(duplicate.pipeline_state["queue_length"], 1)

    def test_keyboard_key_input_is_hardware_independent(self) -> None:
        keyboard = KeyboardKeyInput()
        self.core.enqueue(1, "circle")
        keyboard.submit("KEY1")
        result = self.core.process_key_input(keyboard)
        self.assertIsNotNone(result)
        self.assertEqual(result.pipeline_state["station"], "Station2")
        self.assertIsNone(self.core.process_key_input(keyboard))

