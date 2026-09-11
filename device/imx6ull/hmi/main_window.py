"""Small 800x480 PySide2 Widgets dashboard for the i.MX6ULL LCD."""

from __future__ import annotations

from typing import Dict

from PySide2 import QtCore, QtGui, QtWidgets

from .state_client import ControllerStateClient
from .view_model import HmiViewModel, HmiViewState


class MainWindow(QtWidgets.QWidget):
    """Presentation-only HMI; all actions use the Controller TCP API."""

    def __init__(self, client: ControllerStateClient) -> None:
        super().__init__()
        self._client = client
        self._model = HmiViewModel()
        self._fields = {}  # type: Dict[str, QtWidgets.QLabel]
        self._build_ui()
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(300)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()
        self._refresh()

    def _build_ui(self) -> None:
        self.setWindowTitle("HUIYAN SORTING CONTROL")
        self.setStyleSheet(
            "QWidget { background: #111820; color: #edf4f8; font-family: Sans Serif; }"
            "QFrame#panel { background: #1c2935; border: 1px solid #405364; border-radius: 4px; }"
            "QLabel#heading { color: #69d5ff; font-size: 16px; font-weight: bold; }"
            "QLabel#value { color: #ffffff; font-size: 15px; }"
            "QPushButton { background: #b94141; color: white; border: 1px solid #ef7777;"
            " font-size: 20px; font-weight: bold; min-height: 38px; border-radius: 4px; }"
            "QPushButton:pressed { background: #7e2727; }"
        )
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(6)

        title = QtWidgets.QLabel("HUIYAN  |  INTELLIGENT SORTING CONTROL")
        title.setAlignment(QtCore.Qt.AlignCenter)
        title.setFont(QtGui.QFont("Sans Serif", 20, QtGui.QFont.Bold))
        title.setStyleSheet("color: #69d5ff;")
        root.addWidget(title)

        grid = QtWidgets.QGridLayout()
        grid.setSpacing(6)
        grid.addWidget(self._system_panel(), 0, 0)
        grid.addWidget(self._current_panel(), 0, 1)
        grid.addWidget(self._fifo_panel(), 1, 0)
        grid.addWidget(self._sort_panel(), 1, 1)
        grid.addWidget(self._counter_panel(), 2, 0)
        grid.addWidget(self._keys_panel(), 2, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 2)
        grid.setRowStretch(0, 3)
        grid.setRowStretch(1, 3)
        grid.setRowStretch(2, 2)
        root.addLayout(grid, 1)

        reset = QtWidgets.QPushButton("RESET")
        reset.clicked.connect(self._reset)
        root.addWidget(reset)

    def _panel(self, title: str) -> QtWidgets.QFrame:
        frame = QtWidgets.QFrame()
        frame.setObjectName("panel")
        layout = QtWidgets.QVBoxLayout(frame)
        layout.setContentsMargins(9, 6, 9, 6)
        layout.setSpacing(3)
        heading = QtWidgets.QLabel(title)
        heading.setObjectName("heading")
        layout.addWidget(heading)
        return frame

    def _value(self, layout: QtWidgets.QVBoxLayout, key: str, prefix: str = "") -> QtWidgets.QLabel:
        value = QtWidgets.QLabel(prefix + "-")
        value.setObjectName("value")
        value.setWordWrap(True)
        layout.addWidget(value)
        self._fields[key] = value
        return value

    def _system_panel(self) -> QtWidgets.QFrame:
        panel = self._panel("SYSTEM")
        layout = panel.layout()
        self._value(layout, "controller", "Controller: ")
        self._value(layout, "tcp", "TCP: ")
        self._value(layout, "output", "LED: ")
        return panel

    def _current_panel(self) -> QtWidgets.QFrame:
        panel = self._panel("CURRENT OBJECT")
        layout = panel.layout()
        self._value(layout, "front_id", "ID: ")
        self._value(layout, "shape", "Shape: ")
        self._value(layout, "station", "Station: ")
        self._value(layout, "state", "State: ")
        return panel

    def _fifo_panel(self) -> QtWidgets.QFrame:
        panel = self._panel("FIFO")
        layout = panel.layout()
        self._value(layout, "fifo_size", "FIFO: ")
        self._value(layout, "fifo_items")
        return panel

    def _sort_panel(self) -> QtWidgets.QFrame:
        panel = self._panel("SORT RESULT")
        layout = panel.layout()
        self._value(layout, "last_sort", "Last: ")
        self._value(layout, "branch_map")
        self._fields["branch_map"].setText("B1 red | B2 red+green | B3 RGB")
        return panel

    def _counter_panel(self) -> QtWidgets.QFrame:
        panel = self._panel("SESSION COUNTERS")
        layout = panel.layout()
        self._value(layout, "counters")
        self._value(layout, "total")
        return panel

    def _keys_panel(self) -> QtWidgets.QFrame:
        panel = self._panel("PHYSICAL KEYS")
        layout = panel.layout()
        self._value(layout, "keys", "KEY1  |  KEY2  |  KEY3")
        self._value(layout, "last_key", "Last key: ")
        return panel

    def _refresh(self) -> None:
        self._client.refresh()
        snapshot = self._client.snapshot()
        if snapshot.online and snapshot.pipeline_state is not None:
            state = self._model.apply_pipeline_state(snapshot.pipeline_state)
        else:
            state = self._model.set_offline(snapshot.error)
        self._render(state)

    def _render(self, state: HmiViewState) -> None:
        self._fields["controller"].setText("Controller: " + ("ONLINE" if state.online else "OFFLINE"))
        self._fields["tcp"].setText("TCP: " + ("CONNECTED" if state.online else "RETRYING"))
        self._fields["output"].setText("LED: via Controller")
        self._fields["front_id"].setText("ID: " + state.front_id)
        self._fields["shape"].setText("Shape: " + state.front_shape)
        self._fields["station"].setText("Station: " + state.station)
        self._fields["state"].setText("State: " + state.process_state)
        self._fields["fifo_size"].setText("FIFO: {0}/{1}".format(state.queue_length, state.capacity))
        self._fields["fifo_items"].setText("\n".join("{0}. {1}".format(index + 1, shape) for index, shape in enumerate(state.queue_shapes)) or "(empty)")
        self._fields["last_sort"].setText("Last: " + state.last_sort)
        self._fields["counters"].setText(
            "triangle {0}   circle {1}   rectangle {2}".format(
                state.triangle_count, state.circle_count, state.rectangle_count
            )
        )
        self._fields["total"].setText("Total: {0}".format(state.total_count))
        self._fields["last_key"].setText("Last key: " + state.last_key)
        color = "#61d095" if state.online else "#ef7777"
        self._fields["controller"].setStyleSheet("color: {0}; font-weight: bold;".format(color))

    def _reset(self) -> None:
        self._client.request_reset()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self._timer.stop()
        self._client.close()
        event.accept()
