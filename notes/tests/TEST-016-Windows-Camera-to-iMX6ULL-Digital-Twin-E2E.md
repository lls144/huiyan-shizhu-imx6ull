---
title: TEST-016 Windows Camera 到 i.MX6ULL Digital Twin 实机端到端验证
date: 2026-09-11
tags: [慧眼识珠, Windows, Insta360, RJ45, PySide6, Digital-Twin, hardware]
status: pass
---

# TEST-016 Windows Camera 到 i.MX6ULL Digital Twin 实机端到端验证

## 范围与边界

本记录验证唯一既有 PySide6 Vision Console 的真实链路：

`Insta360 Ace Pro 2 -> OpenCV detection/tracking -> confirmed OBJECT_ENTER -> VisionEventEnqueuer -> ControllerClient -> i.MX6ULL enqueue -> physical KEY -> pipeline_state -> Digital Sorting Line`

未创建第二套 detector、tracker、GUI、socket client 或 protocol；没有在 PC 复制 i.MX6ULL FSM，也没有改动 Controller/i.MX6ULL、USB maintenance profile、GUI 动画或 PyInstaller。Digital Sorting Line 的 FIFO、front、station、last sort 都只取 `BoardStateMonitor` 的真实 `pipeline_state`。

## 环境与启动

- Windows 11 Ethernet：`203.0.113.1/24`；真实 i.MX6ULL Controller：`203.0.113.2:9000`。
- Camera：`Insta360 Ace Pro 2`（USB VID `2e1a` / PID `1003`），DirectShow (`DSHOW`, id 700)，MJPG，实际 `1920x1080`、reported `30.00003 FPS`；本次 GUI 处理 `29.372224 FPS`，`8828/8828` frames read/processed，0 failed reads。
- 正式 Controller profile：`pc/config/controller_windows_ethernet.json`；Camera profile：`pc/config/camera.json`。
- 实景桌面没有满足既有自动 ROI 的中央亮矩形条件，因此本次明确使用已有配置的 fixed normalized ROI `[461, 86, 1459, 810]`；这不是替换 detector 或 ROI 算法。

测试前使用既有 `scripts/windows_controller_protocol_smoke.py` 的 ControllerClient 路径确认真实 heartbeat/state/reset，并得到 FIFO `0/3`、`idle`。

```powershell
& .\.venv\Scripts\python.exe -m pc.gui --source camera --roi-mode fixed_normalized --command-id-start 180000 --session-dir output\m16-camera-e2e-rerun --summary-json output\m16-camera-e2e-rerun-summary.json --soak-seconds 300 --screenshot output\m16-camera-e2e-rerun.png
```

`output/` 为忽略的本地实机证据，非提交工件。

## 真实 Camera / Controller 结果

会话时间为 `2026-09-11T20:42:59+08:00` 至 `20:48:00+08:00`（300.556 s），`error=null`、`worker_clean_shutdown=true`。下表的 enqueue ACK 都来自真实 i.MX6ULL；FIFO 仅在随后来自 `pipeline_state` 的 board snapshot 中显示。

| 实物与 lifecycle | 真实检测证据 | Controller ACK / board 状态 | 实体键与分拣结果 |
|---|---|---|---|
| Circle object 1 | `OBJECT_ENTER` id 1 / object 1，confidence `0.976284`，frame 1；持续在 ROI 内至 frame 240，无第二个 ENTER；frame 244 EXIT | `command_id=180000`，`accepted`；ACK snapshot: FIFO `1/3`、front circle、Station1 | 真实 KEY1、KEY2 后，下一次真实 ACK 已见 `last_key=KEY2`、`last_sort.sequence=2`、`Branch2`，Circle Bin 计数 +1 |
| Circle object 2 | object 1 已在 frame 244 EXIT 后，frame 277 出现新的 object 2（ENTER id 3，confidence `0.976278`）；frame 289 EXIT | `command_id=180002`，`accepted` | 此条是“离开再进入”产生的新 object，符合 M4，不是持续停留重复入队；最终 Circle Bin session count 为 2 |
| Triangle object 3 | `OBJECT_ENTER` id 5 / object 3，confidence `0.953626`，frame 393；frame 735 EXIT | `command_id=180004`，`accepted`；后来真实 ACK 见 `last_sort.sequence=4`、`Branch1`、对应 triangle command | 实体 KEY1；Triangle Bin 计数 1，Station1 显示 MATCH |
| Rectangle object 4 | `OBJECT_ENTER` id 7 / object 4，confidence `1.000000`，frame 847；frame 1062 EXIT | `command_id=180006`，`accepted`；ACK snapshot: FIFO `1/3`、front rectangle、Station1 | 实体 KEY1、KEY2、KEY3；最终真实 state: FIFO `0/3`、idle、`last_key=KEY3`、`last_sort.sequence=5`、`Branch3`，Rectangle Bin 计数 1 |

因此三种目标 shape 均已真实 Camera 入队。每个 confirmed object 各只生成一个 `OBJECT_ENTER` 和一个 enqueue；circle 的两条 accepted 是两个 object（中间已经 EXIT），没有持续留在 ROI 时的重复 enqueue。

## Digital Twin 映射验收

- GUI 与真实 camera、BOARD/CONTROLLER ONLINE 同时运行。每条 accepted 后，FIFO 只等待 `pipeline_state.queue` 的真实更新，不以本地识别列表加一。
- 真实 ACK 中 circle/rectangle 的 `front` 与 `queue[0]` 一致，并映射为 Station1 的对应圆形/矩形与 FIFO front 高亮；实体 KEY 后，station 由真实 board 状态推动，PC 不提前移动物体。
- 最终截图显示 FIFO `0/3`、IDLE、Last Key `KEY3`、Last Sort `Branch3`、Last Enqueue `ACCEPTED rectangle cmd 180006`；静态线同时显示 Triangle Bin `MATCHES 1`、Circle Bin `MATCHES 2`、Rectangle Bin `MATCHES 1`。
- `last_sort.sequence` 是 session 去重键：5 Hz 轮询反复读到同一 sequence 不会重复计数/高亮。最终计数对应 Branch1/2/3 至 Triangle/Circle/Rectangle bins；同一次 sort 只短暂高亮对应 bin 和 station 的 `MATCH`。
- 本阶段不含传送带/推杆连续动画，也不包含电机或 EXE 打包。

## 自动化回归

```powershell
& .\.venv\Scripts\python.exe -m pytest pc/tests -q
```

结果：`135 passed, 1 skipped`。

新增/补充覆盖包括：真实 `VisionEventEnqueuer` 的 GUI dispatcher command/source-event 映射、accepted/queue_full/board offline、持续对象的单 ENTER、front/station queue 映射、Branch1/2/3 到 bin、`last_sort.sequence` 去重，以及 reset 后 FIFO/当前物体/站点清空。

## 结论

Windows Camera 到真实 i.MX6ULL Digital Twin E2E 为 **PASS**。本记录仅对本次 Windows 11、Insta360 Ace Pro 2、RJ45、实体 KEY 实测负责；自动 ROI 场景标定、连续动画、PyInstaller/EXE 仍为后续 TODO。
