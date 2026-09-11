---
title: TEST-006 M5 GUI 离线与实时验收
date: 2026-09-04
tags:
  - 慧眼识珠
  - test
  - M5
result: pass
---

# TEST-006 M5 GUI 离线与实时验收

- **Test ID**：TEST-006
- **对应 Requirement ID**：GUI-001
- **实现 commit**：`bbb6fa7`
- **自动化测试 commit**：`eb7a1fd`
- **真实运行 HEAD / 精选证据 commit**：`78597f58e63f8f262fd0df25757218994345dc39` / `68c89d9`
- **环境**：Windows 11 10.0.26200、Python 3.12.10、PySide6 6.11.2、Qt 6.11.2、OpenCV 5.0.0、NumPy 2.5.2
- **总结果**：Part A synthetic/offscreen PASS；Part B Insta360 live PASS

## Part A：离线软件验收

### 自动化检查

| 检查项 | 实际验证 | 结果 |
|---|---|---|
| window create | offscreen `QApplication` 创建、显示并关闭 `MainWindow`；无 Card，72:28 splitter、40 px app bar、≤26 px status bar | PASS |
| synthetic start | 注入 synthetic sequence，worker 进入 RUNNING 并产生 snapshot | PASS |
| frame/result sync | 每个 detection 的 `frame_index` 等于 snapshot frame | PASS |
| multi-target | `multi_normal.png` 得到 triangle、rectangle、circle | PASS |
| confidence | GUI snapshot 与 M3 直接输出逐项相同 | PASS |
| M4 states | 第二帧出现 3 个 confirmed object states | PASS |
| M4 events | 第二帧显示 3 个 ENTER；blank 后 summary 出现 3 个 EXIT | PASS |
| start-stop | worker 正常停止，session `clean_shutdown=true` | PASS |
| restart | 同一窗口 Start/Stop 两轮，无重复连接或残留 thread | PASS |
| source open failure | 显示类型和 message，转 ERROR，随后可重新 Start | PASS |
| source read failure | 显示错误、worker 退出、GUI 可重试 | PASS |
| vision failure | 注入 `ValueError` 后显示错误且进程不崩溃 | PASS |
| close running | `closeEvent` 请求中断并等待 worker 正常退出 | PASS |
| backpressure | 容量 1；连续发布 1/2/3 后只取得 frame 3，2 次 overwrite | PASS |
| resize | pixmap 使用 `KeepAspectRatio`，不触发视觉重算 | PASS |
| compact overlay | ROI 细线、类别色 bbox、深色外描边、自动黑白文字、ID-aware label、源图不被修改 | PASS |

相关 pytest 文件：`../../pc/tests/test_gui_buffer.py`、`../../pc/tests/test_gui_overlay.py`、`../../pc/tests/test_gui_window.py`。测试没有使用几秒固定 `sleep()`，而是确定性 source 和有上限的 Qt event-loop 条件等待。

### 60 秒 synthetic soak

| 字段 | 实际值 |
|---|---:|
| source | `synthetic` |
| requested cadence | 30 FPS |
| duration | 60.011330 s |
| frames read / processed | 1284 / 1284 |
| GUI updates | 1284 |
| processing FPS | 21.395960 |
| GUI update FPS | 21.395960 |
| average / P95 processing | 6.537603 / 9.372350 ms |
| display drops / buffer overwrites | 0 / 0 |
| failed reads | 0 |
| error | `null` |
| ended reason | `stopped` |
| clean shutdown | `true` |

soak 由真实 `.venv` 进程运行，但输入是 synthetic、Qt 平台是 offscreen。循环过程中真实产生 64 个 M4 事件；其中 touching/occlusion 段出现 `unknown`，与 M3 已记录的合并轮廓局限一致，不隐藏也不作为 GUI 故障。`tracemalloc` current/peak 为 55,931,591 / 64,671,161 bytes，仅是 Python 可追踪分配粗测。

### 回归

- M5 UI/UX 阶段当时完整 pytest 为 `110 passed in 3.81s`；2026-09-07 最终仓库回归为 `172 passed in 3.59s`。
- M2 十张真实离线图片：`10/10`，background 1/1、circle 3/3、rectangle 3/3、triangle 3/3。
- M3 synthetic：4 个强制光照场景、两种方案均精确输出三类，`all_required_scenes_pass=true`；遮挡/接触局限未改写。
- M4：12/12 detection-sequence 场景通过，`failing_scenarios=0`。
- `pip check`：`No broken requirements found.`。
- 同次 M5 synthetic/offscreen 冒烟 5.021020 秒、87 帧、0 failed read、`error=null`、正常关闭；其 17.327158 FPS 只作为短时功能回归，不替代真实 camera 的 29.315668 FPS 性能验收。

### Part A 证据

- JSON：`../../evidence/data/m5/m5-offline-gui-results.json`
- CSV：`../../evidence/data/m5/m5-offline-gui-results.csv`
- 三目标 GUI：`../../evidence/screenshots/m5/synthetic/m5-gui-three-target-demo.png`
- soak 结束画面：`../../evidence/screenshots/m5/synthetic/m5-gui-soak.png`
- desktop workspace 重构验收图：`../../evidence/screenshots/m5/synthetic/m5-gui-desktop-workspace.png`

## Part B：真实 Insta360 摄像头 GUI 验收 — PASS

2026-09-07 审计 `output/m5/sessions/session-2026-09-07T145826.788_0800.json`，SHA-256 `ADF9E4E0D438B076210F5AADDDB7D82BBFE050ED471842143F9C2F9D97184F96`。该文件由真实 camera source 生成；设备为 Insta360 Ace Pro 2（VID 2E1A、PID 1003）、DirectShow、MJPG，请求与实际分辨率 1920×1080，reported FPS 30.000030。

### 启动校准

启动请求 `roi-mode=auto`，但 auto 没有找到合格的中央白色四边形，记录为 `area=6, not_convex_quadrilateral=1`；程序按设计降级为 manual。manual/selected ROI `[548, 126, 1346, 698]` 接受后在整次运行中锁定，normalized ROI 为 `(0.285417, 0.116667, 0.701042, 0.646296)`，没有逐帧追踪。此结果证明 fallback 有效，不声称 auto ROI 本次成功或 100% 成功。

### Session 实际值

| 字段 | 实际值 | 判定 |
|---|---:|---|
| start / finish | 14:58:26.788 / 15:24:43.931 (+08:00) | 同一真实 session |
| duration | 1577.142974 s | 长时间运行 |
| frames read / processed | 46235 / 46235 | 一致 |
| GUI updates | 46235 | 与处理帧一致 |
| detections / events | 94975 / 117 | 已记录 |
| processing FPS | 29.315668 | ≥20 目标，PASS |
| GUI update FPS | 29.315668 | ≥15 目标，PASS |
| average / P95 processing | 3.342837 / 4.620590 ms | 如实记录 |
| failed reads | 0 | PASS |
| display drops / buffer overwrites | 0 / 0 | PASS |
| error | `null` | PASS |
| ended reason | `stopped` | 用户 Stop |
| worker / GUI clean shutdown | true / true | PASS |

running 截图显示真实 camera 画面、`#76 CIRCLE 96.9%`、Detections、Tracked Objects、ENTER/EXIT events、29.3 FPS、ROI MANUAL 和 `Last error: No errors`；Stop 后截图显示顶部及底部 `Idle/IDLE`，且最后一帧保留供检查。五个 M3 evidence record 也在同一 session 中完整登记。

Qt 控制台曾输出 `QFont::setPointSize Point size <=0 (-1)`。该文字未进入 session JSON，仅有现场操作者观察；结合 GUI 正常运行、`Last error: No errors`、session `error=null`、`clean_shutdown=true`，判定为非阻断 UI warning，不冒充视觉、摄像头或线程错误。

session 原样记录 `git.dirty=true`；审计开始时没有 tracked diff，只有操作者保存的 M4/M5 live 截图未跟踪。真实运行代码基线仍由 commit `78597f58` 唯一定位。

### Part B 证据

- 摘要：`../../evidence/data/m5/m5-live-camera-session-summary.json`
- running：`../../evidence/screenshots/m5/live/m5-live-camera-running.png`
- Stop → Idle：`../../evidence/screenshots/m5/live/m5-live-after-stop-idle.png`
- M4 lifecycle：`../../evidence/data/m4/m4-live-lifecycle-summary.json`
- M3 五场景：`../../evidence/data/m3/live/`、`../../evidence/screenshots/m3/live/`

> [!success] 验收结论
> Part A 与 Part B 均满足原定验收条件，GUI-001 与 M5 为 `DONE`。这不包含通信、FIFO、ACK、心跳或重发功能。

## 关联记录

- [[../daily/2026-09-04-M5-GUI离线软件验证]]
- [[../daily/2026-09-07-M3-M4-M5-最终真实验收]]
- `../../docs/M5_GUI.md`
