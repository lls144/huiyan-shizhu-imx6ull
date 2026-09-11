---
title: TEST-017 Windows Vision 遮挡生命周期鲁棒性实机验证
date: 2026-09-11
tags: [慧眼识珠, Windows, Insta360, lifecycle, occlusion, RJ45, hardware]
status: pass
---

# TEST-017 Windows Vision 遮挡生命周期鲁棒性实机验证

## 问题与根因

TEST-016 现场发现：confirmed circle 被手暂时遮挡时，旧 tracker 只有 `max_missing_frames=3`；第 4 个连续 miss（约 `0.13 s`）即发出 `OBJECT_EXIT`。随后恢复的 circle 无法匹配 inactive track，获得新 object id 与新的 `OBJECT_ENTER`，由既有 `VisionEventEnqueuer` 正常发送了不应有的第二条 accepted enqueue。

M4 tracker 接收的是 M3 已过滤后的 ROI 内 detection；M3 对触碰 ROI border 的 contour 直接拒绝，因此 tracker 没有可靠的“已越界”事件。修复不使用全局 cooldown：对 **已 confirmed** track 增加可配置的 `occlusion_grace_frames=25`，并在 grace 内仅在下列条件均成立时恢复同一 track：

- track 仍处于 `pending_exit`，因此时间窗口尚未超过 25 consecutive missing frames；
- shape 相同；
- 与最后 bbox 的 IoU 至少为 `0.30`，或 center distance 不大于 `80 px`。

所以恢复保留 object id、不发 EXIT/ENTER；不同 shape 或远位置同 shape 不会被错误合并。连续 26 个 miss 才执行 fallback `OBJECT_EXIT`，之后新 detection 才分配新 object id。`VisionEventEnqueuer` 没有改变，仍只消费 confirmed `OBJECT_ENTER`。

在本机 29.241 FPS 的实测速度下，25 frames 约 `0.855 s`。

## 自动化覆盖

`pc/tests/test_event_tracker.py` 与 `pc/tests/test_vision_dispatcher.py` 覆盖：

- 5–10 frame 手遮挡与接近 25-frame 遮挡恢复：原 object id、0 EXIT、0 additional ENTER；dispatcher/enqueuer 只处理一条 ENTER；
- 26-frame 真实消失：exactly one EXIT；
- EXIT 后重新进入：新 object id、新 ENTER；
- 不同 shape 与超过 IoU/center gate 的远位置同 shape：不 re-associate；
- 原 M3/M4 sequence manifest、GUI lifecycle、Digital Twin 与 Controller bridge 回归。

## 真实 Camera 验收

### 环境

- Windows 11 / Insta360 Ace Pro 2，DSHOW + MJPG，实际 `1920x1080`、reported `30.00003 FPS`。
- Windows RJ45 `203.0.113.1` -> 真实 i.MX6ULL `203.0.113.2:9000`，正式 Windows Ethernet profile。
- 固定既有 normalized ROI `[461, 86, 1459, 810]`；测试前以既有 `ControllerClient` reset，FIFO `0/3`。

```powershell
& .\.venv\Scripts\python.exe -m pc.gui --source camera --roi-mode fixed_normalized --command-id-start 200000 --session-dir output\m17-camera-occlusion-rerun --summary-json output\m17-camera-occlusion-rerun-summary.json --soak-seconds 240 --screenshot output\m17-camera-occlusion-rerun.png
```

### 现场步骤与真实记录

1. circle 进入并稳定检测，操作者在原 ROI 位置用手短暂遮挡，然后移开手；circle 未离开 ROI。
2. 首次 confirmed `OBJECT_ENTER`: event id `1` / object id `1` / confidence `0.973657` / frame `186`，Controller `command_id=200000` -> `accepted`。
3. object 1 从 first_seen `185` 到 last_seen `346` 共 162 frame span、`hit_count=138`，即此可见生命周期内有 24 个未检测 frame；期间没有 `OBJECT_EXIT` 或第二次 `OBJECT_ENTER`，object id 仍为 `1`，enqueue count 仍为 `1`。这覆盖了实际手遮挡。
4. 随后真正将 circle 拿出，连续 26 个 miss 后，在 frame `372` 产生一次且仅一次 `OBJECT_EXIT`（object id `1`）。
5. 等待超过 grace 后将 circle 重新放入：object id `2` 在 frame `600` 产生新 `OBJECT_ENTER`（confidence `0.977131`），Controller `command_id=200002` -> `accepted`。
6. 会话最终 board state：FIFO `2/3`，queue 为 `(200000, circle, object 1)`、`(200002, circle, object 2)`，front 为 200000；与两次合法 lifecycle 完全一致。没有遮挡导致的第三条 accepted。

会话 `240.551791 s`，`7034/7034` frames processed，`29.241104 FPS`，0 failed reads，`error=null`、`clean_shutdown=true`。忽略目录 `output/m17-camera-occlusion-rerun-summary.json` 和截图为本地实机证据；截图显示 live camera circle、tracked `#2 Circle CONFIRMED`、FIFO 2/3、last enqueue accepted 200002，以及 `ENTER #1 -> EXIT #1 -> ENTER #2`。

## 结论

temporary hand occlusion 不再造成 false EXIT/re-entry：遮挡前后 object id 保持 `1`、ENTER `1`、EXIT `0`、enqueue `1`。真正 EXIT 后的 re-entry 保持原有语义：EXIT `1`、新 object id `2`、新 ENTER `1`、新 accepted enqueue `1`。本项为 **PASS**；连续动画和 PyInstaller/EXE 仍未开始。
