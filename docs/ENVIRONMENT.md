# 运行环境

## Windows demonstration PC

- Windows 11
- Ace Pro 2 USB Webcam
- Python 3.12 / PySide6 6.11.2 / Qt 6.11.2
- OpenCV 5.0.0.93, NumPy 2.5.2
- RJ45 static profile: `pc/config/controller_windows_ethernet.json`

## i.MX6ULL controller

- Wildfire i.MX6ULL, Debian GNU/Linux 10, armv7l, kernel 4.19.35-imx6
- Python 3.7.3
- LCD `/dev/fb0`, mxs-lcdif, 800×480, 16 bpp
- PySide2 5.11.2 / Qt 5.11.3 with `linuxfb:fb=/dev/fb0`
- Goodix Capacitive TouchScreen, dynamically resolved at launch
- `huiyan-led-helper.service` root-owned; `huiyan-controller.service` and `huiyan-hmi.service` ordinary `debian`
- Demo RJ45: `eth1`, stable MAC `02:00:00:00:00:01`, board address
  `203.0.113.2/24`; static ConnMan profile persisted across reboot.

## Development / maintenance host

- Ubuntu dev-host
- USB Gadget maintenance profile: board `198.51.100.2/30`, host `198.51.100.1/30`
- local `.venv` is ignored and must satisfy `requirements.txt`
- The maintenance host's physical Ethernet interface was intentionally not
  configured during the board-side RJ45 persistence verification.
