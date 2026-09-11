"""Minimal, hardware-safe Qt-to-framebuffer smoke window for M10.

It deliberately has no Controller, GPIO, LED, TCP, or touch-control logic.
The program verifies only that the already-installed PySide2/Qt runtime can
render a visible full-screen widget on the board's current display backend.
"""

from __future__ import print_function

import argparse
import os
import sys


def _arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--platform",
        default=None,
        help="Qt QPA platform override; defaults to linuxfb when no graphical session exists",
    )
    parser.add_argument(
        "--duration-seconds",
        type=int,
        default=0,
        help="automatically close after this many seconds; zero waits for interruption",
    )
    parser.add_argument(
        "--probe",
        action="store_true",
        help="initialize Qt and print screen geometry without creating a window",
    )
    args = parser.parse_args()
    if args.duration_seconds < 0:
        parser.error("--duration-seconds must be non-negative")
    return args


def _select_platform(requested):
    if requested:
        return requested
    configured = os.environ.get("QT_QPA_PLATFORM")
    if configured:
        return configured
    if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
        return ""
    return "linuxfb"


def main():
    args = _arguments()
    platform = _select_platform(args.platform)
    if platform:
        os.environ["QT_QPA_PLATFORM"] = platform

    from PySide2 import QtCore, QtGui, QtWidgets

    app = QtWidgets.QApplication(sys.argv)
    screen = app.primaryScreen()
    geometry = screen.geometry() if screen is not None else None
    print(
        "HUIYAN_M10_QT_SMOKE platform={0} screen={1}".format(
            os.environ.get("QT_QPA_PLATFORM", "default"),
            "{0}x{1}".format(geometry.width(), geometry.height()) if geometry else "unavailable",
        )
    )
    if args.probe:
        return 0

    window = QtWidgets.QWidget()
    window.setWindowTitle("Huiyan M10 Qt Test")
    window.setStyleSheet("background: #101820; color: #f4f7fb;")
    layout = QtWidgets.QVBoxLayout(window)
    layout.setContentsMargins(48, 48, 48, 48)
    layout.setSpacing(20)

    title = QtWidgets.QLabel("Huiyan M10 Qt Test")
    title.setAlignment(QtCore.Qt.AlignCenter)
    title.setFont(QtGui.QFont("Sans Serif", 30, QtGui.QFont.Bold))
    title.setStyleSheet("color: #4fc3f7;")
    layout.addStretch(1)
    layout.addWidget(title)

    display_size = "{0}x{1}".format(geometry.width(), geometry.height()) if geometry else "unknown"
    detail = QtWidgets.QLabel("PySide2 / Qt {0}  |  LCD {1}".format(QtCore.qVersion(), display_size))
    detail.setAlignment(QtCore.Qt.AlignCenter)
    detail.setFont(QtGui.QFont("Sans Serif", 16))
    layout.addWidget(detail)
    layout.addStretch(1)

    window.showFullScreen()
    if args.duration_seconds:
        QtCore.QTimer.singleShot(args.duration_seconds * 1000, app.quit)
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
