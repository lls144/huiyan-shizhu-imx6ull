---
title: TEST-012 M10 i.MX6ULL LCD Qt HMI 验收
date: 2026-09-11
tags: [慧眼识珠, M10, imx6ull, lcd, qt, pyside2, tslib, hmi, hardware]
status: PASS
---

# TEST-012 M10 i.MX6ULL LCD Qt HMI 验收

## 范围与版本

- Test-time revision: `def7c95` plus the uncommitted M10 closeout worktree subsequently committed by this record's change.
- Board: Wildfire i.MX6ULL, Debian GNU/Linux 10, armv7l, kernel 4.19.35-imx6, Python 3.7.3.
- Display: `/dev/fb0`, `mxs-lcdif`, 800×480, virtual 800×480, 16 bpp, stride 1600.
- Qt: PySide2 5.11.2 / Qt 5.11.3, `QT_QPA_PLATFORM=linuxfb:fb=/dev/fb0`.
- Touch: Goodix Capacitive TouchScreen.  The observed event node was `/dev/input/event3`; the launcher resolves it by device name and does not commit that number.
- Controller: ordinary `debian` process on `0.0.0.0:9000`; the HMI connects only to `127.0.0.1:9000`.  `huiyan-led-helper.service` remained root-owned and active.

This records the i.MX6ULL HMI route.

## Launch and conflict closure

The reproducible operator command is:

```bash
cd /home/debian/huiyan-shizhu
./device/imx6ull/scripts/start_hmi.sh
```

The launcher verified `/dev/fb0`, `/usr/lib/plugins/generic/libqtslibplugin.so`, `/usr/lib/fonts`, `/etc/ts.conf` and touchscreen read permission.  It set tslib, font and plugin variables, including `QT_QPA_GENERIC_PLUGINS=tslib:/dev/input/eventX`; it explicitly cleared old evdev input variables.  It did not set `QT_QPA_FB_HIDECURSOR=1`, because that value was independently reproduced to crash Qt 5.11 linuxfb in native `app.exec_()`.

The vendor Demo startup source was `/lib/systemd/system/ebf-qtdemo.service`, enabled through `multi-user.target` and executing `/usr/local/qt-app/run.sh`.  It was disabled with `systemctl disable --now ebf-qtdemo.service`, a reversible operation; `/usr/local/qt-app/` and its `App` binary were not altered.  At acceptance time its historical systemd state was `failed`, but process inspection confirmed neither `run.sh` nor `App` was running.

`huiyan-hmi.service` is an ordinary-user `debian` service.  It calls the same launcher, uses `flock` to reject concurrent HMI launches, and therefore cannot create a second `python3 -m device.imx6ull.hmi.app` process through manual and systemd entry points.

## Actual physical results

| Check | Actual result | Result |
|---|---|---|
| First LCD display | Full 800×480 HUIYAN screen; no visible clipping; title, six status panels and large RESET button readable; Controller ONLINE, TCP CONNECTED, FIFO 0/3, IDLE | PASS |
| Runtime environment | One `debian` HMI process held verified linuxfb, plugin, font and tslib event3 environment; vendor Demo process absent | PASS |
| Triangle live path | Ace Pro 2 `/dev/video2` MJPG 1920×1080@30: M4 triangle confidence 0.932, command 16002 accepted; physical KEY1 → Branch1; FIFO empty; operator observed red about 1 s then off; HMI Triangle/Total counters +1 | PASS |
| Circle live path | M4 circle confidence 0.975, command 16003 accepted; KEY1 retained FIFO at Station2 with LEDs off/no early count; KEY2 → Branch2, dequeue; operator confirmed red+green about 1 s then off; HMI circle counter +1 | PASS |
| Rectangle live path | M4 rectangle confidence 0.993, command 16004 accepted; KEY1 → Station2 and KEY2 → Station3 with LEDs off; KEY3 → Branch3, dequeue; operator confirmed RGB three-channel result and HMI rectangle counter +1 | PASS |
| FIFO ordering | Three separate true vision/M4/TCP enters: 16010 triangle (0.947), 16011 circle (0.861), 16012 rectangle (0.987).  Board snapshot: `3/3`, `full=true`, ordered `[triangle, circle, rectangle]`, front triangle | PASS |
| Fail-closed bridge | While expecting triangle, an on-camera rectangle was rejected before TCP enqueue; it did not alter FIFO | PASS |
| Wrong physical key | True vision circle command 16020 at Station1; physical KEY3 left Station1, queue length 1, front circle and LEDs unchanged; no new sort result | PASS |
| LCD touch RESET | Operator touched the LCD RESET button while FIFO was non-empty.  Existing Controller reset API returned idle/empty; board observed `queue_length=0`, `empty=true`, all LED brightness 0; HMI service stayed active and vendor page did not run | PASS |
| Controller recovery | Controller was intentionally stopped for 8 seconds.  Operator observed HMI OFFLINE then automatic ONLINE recovery; HMI service stayed active; heartbeat/state returned alive and idle after ordinary-user Controller restart | PASS |

## Automated checks

- Local M10/M7/M8/M9-related unittest: 42 tests passed.
- Python 3.7 static compatibility guard: PASS.
- `device/imx6ull/scripts/build.sh`: PASS, including HMI modules.
- `bash -n device/imx6ull/scripts/start_hmi.sh`: PASS on Ubuntu and board.
- Board `python3 -m compileall -q device/imx6ull`: PASS.
- `git diff --check`: PASS before closeout commit.
- `shellcheck` was not installed; no package was added for it.

## Conclusion

M10 is **DONE** for the i.MX6ULL Controller/LCD route.  PC vision remains on Ubuntu; the i.MX6ULL runs Controller, Linux input, restricted LED helper and the LCD HMI.  No boot overlay, framebuffer driver, GPIO mapping or vendor binary was changed.
