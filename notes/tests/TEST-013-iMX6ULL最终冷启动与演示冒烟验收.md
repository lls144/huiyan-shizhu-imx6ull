---
title: TEST-013 i.MX6ULL 最终冷启动与演示冒烟验收
date: 2026-09-11
tags: [慧眼识珠, imx6ull, cold-start, systemd, final-smoke, hardware]
status: PASS
---

# TEST-013 i.MX6ULL 最终冷启动与演示冒烟验收

## 范围与环境

- Branch: `imx6ull-development`; test-time revision was `23de87e` plus this uncommitted final-closeout worktree.
- Board: Wildfire i.MX6ULL, Debian GNU/Linux 10, armv7l, kernel `4.19.35-imx6`, Python 3.7.3; PC link is USB Gadget Ethernet and Controller is `198.51.100.2:9000`.
- Controller: `huiyan-controller.service`, ordinary `debian`, fixed existing `controller_main.py --mode imx6ull --config .../controller.json --host 0.0.0.0` entry point; `input` and `huiyan-led` supplementary groups.
- Other services: root-owned `huiyan-led-helper.service`; ordinary-user `huiyan-hmi.service`; vendor `ebf-qtdemo.service` remains reversibly disabled.  No vendor binary, boot configuration, overlay, DTB, kernel, GPIO mapping or LED mapping was changed in this test.
- HMI: PySide2 5.11.2 / Qt 5.11.3, `linuxfb:fb=/dev/fb0`, 800×480 LCD, dynamically discovered Goodix Capacitive TouchScreen.  `QT_QPA_FB_HIDECURSOR=1` remains prohibited because it causes a native crash on this target.

This is an i.MX6ULL Controller-route record.

## Cold-start procedure

1. Before shutdown, `huiyan-led-helper.service`, `huiyan-controller.service` and `huiyan-hmi.service` were each verified `enabled` and `active`; `final_smoke_check.sh` returned PASS.
2. Operator ran normal `sudo poweroff`, then physically removed/reapplied board power.  This is a true power-cycle check, not a service restart treated as a cold start.
3. After USB OTG and SSH recovered, no manual Controller, HMI or helper launch command was issued.
4. At approximately three minutes uptime, all three services were again `enabled` and `active`.  Main PIDs observed for helper/Controller/HMI were 367/402/407; Controller 402 listened on `0.0.0.0:9000`.

## Automatic post-boot checks

`device/imx6ull/scripts/final_smoke_check.sh` is a read-only field test.  It completed with `OVERALL ............ PASS` after the physical power cycle and again after the controlled reconnect below.

| Check | Actual post-boot result | Result |
|---|---|---|
| Controller | `huiyan-controller.service` active; 9000 listener; TCP heartbeat `alive` | PASS |
| FIFO | state reachable, `queue_length=0`, `empty=true`, `station=idle` | PASS |
| LED | helper active, Unix socket present, red/green/blue brightness all 0 | PASS |
| HMI/LCD | HMI service active, exactly one process, `linuxfb:fb=/dev/fb0`, virtual 800×480 | PASS |
| Input | `huiyan-keys` and Goodix Capacitive TouchScreen registered | PASS |
| Overlay / vendor Demo | expected LCD/touch/LED/huiyan-keys overlay lines present; `ebf-qtdemo.service` disabled and no vendor process | PASS |

The operator visually confirmed the post-boot HUIYAN LCD page and touched RESET: the button gave feedback, page remained HUIYAN, FIFO stayed `0/3` / IDLE.

## Minimal true-vision functional smoke

The Ubuntu `.venv` opened Ace Pro 2 explicitly with the committed `pc/config/camera_ubuntu_acepro2.json`: `/dev/video2`, V4L2, MJPG, 1920×1080@30.  Existing M3/M4 logic and the fail-closed single-shape bridge were used; no TCP injection substituted for recognition.  Before the triangle run, a live circle was correctly rejected by the triangle guard before TCP enqueue.

| Shape | Real M4 / accepted command | Physical action and verified result | Result |
|---|---|---|---|
| triangle | `OBJECT_ENTER #1`, confidence 0.933, command 20001 accepted | KEY1 → Branch1; operator observed red; board state idle/empty, Branch1; RGB all 0 after 1.1 s | PASS |
| circle | `OBJECT_ENTER #1`, confidence 0.967, command 20002 accepted | KEY1 → Station2 with LED off; KEY2 → Branch2; operator confirmed red+green; board idle/empty and RGB all 0 after 1.1 s | PASS |
| rectangle | `OBJECT_ENTER #1`, confidence 0.999, command 20003 accepted | KEY1 → Station2, KEY2 → Station3, KEY3 → Branch3; operator confirmed three-channel RGB; board idle/empty and RGB all 0 after 1.1 s | PASS |

## Controlled Controller disconnect/reconnect

The operator stopped only `huiyan-controller.service`.  The HMI remained alive and the operator observed OFFLINE.  Systemd then started the same service; the HMI returned ONLINE and Controller resumed listening with a new ordinary-user PID (773).  A final complete smoke result was PASS.  This tests HMI resilience to the actual service endpoint disappearing.

## Automated regression

- i.MX6ULL M7–M10-related unittest: `43/43 PASS`.
- Python 3.7 static compatibility guard: `2/2 PASS`.
- `device/imx6ull/scripts/build.sh`: PASS.
- `bash -n` over all `device/imx6ull/scripts/*.sh`: PASS.
- `python3 -m compileall -q device/imx6ull pc`: PASS; board `compileall` also PASS.
- Ubuntu `.venv` was reconciled only with the already pinned `PySide6==6.11.2` from `requirements.txt`; PC test suite: `184 passed, 1 skipped`.
- `git diff --check`: PASS before final commit.

## Conclusion

The M7–M10 i.MX6ULL route now has a real power-cycle recovery path, a read-only field smoke command and a concise demo runbook.  M3, M4, M5, M7, M8, M9 and M10 remain DONE for their recorded scopes.
