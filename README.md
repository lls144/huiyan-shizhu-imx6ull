# 慧眼识珠：Windows Vision + i.MX6ULL 智能分拣演示

## 最终产品架构

```text
Ace Pro 2 camera (Windows 11)
  -> OpenCV shape recognition / OBJECT_ENTER
  -> Ethernet TCP
  -> Wildfire i.MX6ULL Controller
  -> FIFO (capacity 3) / 3-station FSM
  -> physical KEY1 / KEY2 / KEY3
  -> Branch1 / Branch2 / Branch3
  -> board RGB LED

i.MX6ULL LCD HMI
  -> localhost Controller TCP state + RESET
  -> 800x480 LCD / Goodix touch

Windows GUI
  -> camera preview, connection state, FIFO/status and sorting animation
```

Windows 11 is the normal demonstration endpoint. i.MX6ULL performs control and HMI; Ubuntu is a development and maintenance host only. The board does not run computer vision or AI.

## Verified milestones

| Milestone | Status | Evidence |
|---|---|---|
| M3 | DONE | multi-object and lighting vision evidence |
| M4 | DONE | deduplicated OBJECT_ENTER lifecycle |
| M5 | DONE | PC PySide6 vision GUI |
| M7 | DONE | PC–Controller TCP |
| M8 | DONE | FIFO and three-station FSM |
| M9 | DONE | physical keys, RGB LED and real vision end-to-end |
| M10 | DONE | LCD HMI, Goodix RESET and cold-start recovery |

## Runtime profiles

- **Windows demo Ethernet:** [pc/config/controller_windows_ethernet.json](pc/config/controller_windows_ethernet.json)
- **Ubuntu USB maintenance:** [pc/config/controller_ubuntu_usb_maintenance.json](pc/config/controller_ubuntu_usb_maintenance.json)
- **Board RJ45 profile:** [device/imx6ull/config/demo_ethernet.json](device/imx6ull/config/demo_ethernet.json)
- **Ubuntu Ace Pro 2:** [pc/config/camera_ubuntu_acepro2.json](pc/config/camera_ubuntu_acepro2.json)

The normal live demo is documented in [DEMO_RUNBOOK](docs/DEMO_RUNBOOK.md). Ethernet addressing and Windows NIC setup are documented in [WINDOWS_ETHERNET_DEMO](docs/WINDOWS_ETHERNET_DEMO.md). Board deployment and service facts are in [IMX6ULL_DEPLOYMENT](docs/IMX6ULL_DEPLOYMENT.md).

## Repository layout

```text
pc/                    Windows/Ubuntu PC vision, GUI and Controller client
device/imx6ull/        Controller, Linux input, LED helper client, LCD HMI, services/scripts
docs/                  product architecture, setup, runbook and evidence index
notes/                 experiment and test records
evidence/              curated vision/HMI evidence
reference/             immutable course source material
```

## Developer verification

```bash
python3 -m unittest discover -s device/imx6ull/tests -p 'test_*.py'
.venv/bin/python -m pytest -q pc/tests
bash device/imx6ull/scripts/build.sh
```
