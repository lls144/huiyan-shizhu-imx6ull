"""Run the i.MX6ULL M10 LCD HMI through the Controller TCP interface."""

from __future__ import print_function

import atexit
import argparse
import os
import sys


def _arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument("--windowed", action="store_true", help="diagnostic mode; do not use for LCD acceptance")
    return parser.parse_args()


def _release_fallback_lock():
    """Remove only the fallback lock owned by this exec-replaced process."""

    lock_dir = os.environ.get("HUIYAN_HMI_FALLBACK_LOCKDIR")
    if not lock_dir:
        return
    pid_path = os.path.join(lock_dir, "pid")
    try:
        with open(pid_path, "r") as source:
            owner = source.read().strip()
        if owner == str(os.getpid()):
            os.unlink(pid_path)
            os.rmdir(lock_dir)
    except OSError:
        pass


def main():
    args = _arguments()
    if not 1 <= args.port <= 65535:
        raise SystemExit("--port must be in [1, 65535]")
    # The service/display launcher selects linuxfb.  Never force cursor hiding:
    # QT_QPA_FB_HIDECURSOR=1 crashes Qt 5.11 linuxfb on this target.
    if not os.environ.get("QT_QPA_PLATFORM"):
        os.environ["QT_QPA_PLATFORM"] = "linuxfb"

    from PySide2 import QtWidgets

    from .main_window import MainWindow
    from .state_client import ControllerStateClient

    atexit.register(_release_fallback_lock)
    app = QtWidgets.QApplication(sys.argv)
    client = ControllerStateClient(args.host, args.port)
    window = MainWindow(client)
    if args.windowed:
        window.show()
    else:
        window.showFullScreen()
    screen = app.primaryScreen()
    geometry = screen.geometry() if screen is not None else None
    print(
        "HUIYAN_M10_HMI platform={0} screen={1}".format(
            os.environ.get("QT_QPA_PLATFORM", "default"),
            "{0}x{1}".format(geometry.width(), geometry.height()) if geometry else "unavailable",
        ),
        flush=True,
    )
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
