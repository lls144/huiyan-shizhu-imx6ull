---
title: TEST-015 Windows GUI Board State Monitor 实机验证
date: 2026-09-11
tags: [慧眼识珠, Windows, PySide6, RJ45, ControllerClient, hardware]
status: pass
---

# TEST-015 Windows GUI Board State Monitor 实机验证

## 范围与边界

本记录验证现有 PySide6 Vision Console 新增的 Board State 区域。状态监控仅使用既有 `ControllerClient`，并以真实 i.MX6ULL Controller 的 `heartbeat` ACK 作为 BOARD/CONTROLLER ONLINE 的唯一依据；`pipeline_state` 只提供 FIFO/FSM 显示数据。

没有创建第二套 GUI、socket client 或协议，未修改 Controller/i.MX6ULL/USB maintenance profile。为使实体三键在既有 FSM 语义下产生可观察变化，测试前用现有 `ControllerClient` 向真实板端入队一条 `rectangle` 测试项；这不是摄像头识别或 `VisionEventEnqueuer` 端到端验收。

## 环境与启动

- Windows 11 Ethernet：`203.0.113.1/24`。
- 实体 i.MX6ULL Controller：`203.0.113.2:9000`。
- GUI 使用正式 profile：`pc/config/controller_windows_ethernet.json`。
- 可见窗口启动命令：

```powershell
& .\.venv\Scripts\python.exe -m pc.gui --source synthetic
```

`synthetic` 只用于不占用相机的 Board State GUI 验证；现有 Camera/检测/跟踪/`OBJECT_ENTER` 路径未更改。本次渲染检查的忽略本地截图为 `output/gui-phase1-board-monitor.png` 与 `output/gui-phase1-key-result.png`。

## 实际结果

窗口启动后，Board State 面板立即出现，先显示 CAMERA OFFLINE、BOARD/CONTROLLER CONNECTING；后台 `ControllerClient` 得到真实 heartbeat `ack/alive` 后，显示 BOARD ONLINE、CONTROLLER ONLINE。实时 `pipeline_state` 显示 FIFO `0/3`、IDLE、Current object `NONE`。

测试准备：真实板端接受 `command_id=15001`、`shape=rectangle`，返回 FIFO `1/3`、`Station1`、front=`rectangle`。

随后操作者按实体键，独立的既有 `ControllerClient.request_pipeline_state()` 观察到以下真实状态；GUI 的同一 Board State monitor 同时按 5 Hz 轮询同一 `pipeline_state`：

| 实体操作 | 实际 Controller 状态 | GUI 显示字段 |
|---|---|---|
| 初始入队 | `1, Station1, rectangle, last_key=null, last_sort=null` | FIFO 1/3；STATION1；RECTANGLE |
| KEY1 | `1, Station2, rectangle, last_key=KEY1` | STATION2；LAST KEY KEY1 |
| KEY2 | `1, Station3, rectangle, last_key=KEY2` | STATION3；LAST KEY KEY2 |
| KEY3 | `0, idle, front=null, last_key=KEY3, last_sort=Branch3` | FIFO 0/3；IDLE；NONE；LAST KEY KEY3；LAST SORT Branch3 |

末次实际返回的 `last_sort` 含 `branch=Branch3` 与同一 `command_id=15001`。离屏渲染的最终 GUI 截图也显示 BOARD ONLINE、Current object NONE、LAST KEY KEY3、LAST SORT Branch3。

## 自动化回归

```powershell
& .\.venv\Scripts\python.exe -m pytest pc/tests -q
```

结果：`127 passed, 1 skipped`。新增 `pc/tests/test_state_monitor.py` 覆盖 pipeline state parsing、heartbeat failure 到 OFFLINE、下一次 heartbeat ACK 返回 ONLINE，以及 per-request single-flight/timeout cancel；`test_gui_window.py` 覆盖窗口初始 Board State 区域。

## 结论

Windows GUI Phase 1 的 Board State Monitor 为 **PASS**：真实 RJ45 heartbeat 驱动 ONLINE，真实实体 KEY1/2/3 的 FIFO/FSM 状态可被现有 Vision Console 异步显示。流水线/推杆动画、EXE/PyInstaller 和视觉入队到 GUI 的进一步编排不在本阶段范围内。
