---
title: TEST-005 M4 事件去重离线验收
date: 2026-09-04
tags:
  - 慧眼识珠
  - test
  - M4
result: pass
---

# TEST-005 M4 事件去重离线验收

- **Test ID**：TEST-005
- **对应 Requirement ID**：PC 端事件生成前置子能力
- **实现 commit**：`7d83c57`
- **测试 commit**：离线场景 `bdaca0b`；live 证据结构 `506fad2`
- **证据 commit**：`46bb2a6`
- **真实运行 HEAD / 精选证据 commit**：`78597f58e63f8f262fd0df25757218994345dc39` / `68c89d9`
- **环境**：Windows 11、Python 3.12.10；核心状态测试不使用墙钟等待
- **结果**：离线 detection-sequence 12/12 PASS；真实摄像头生命周期 PASS

## 配置

- `min_confirm_frames=2`
- `max_missing_frames=3`
- `iou_threshold=0.30`
- `center_distance_threshold=80.0 px`

## 实际结果

| 场景 | 预期 | 实际 | 结果 |
|---|---|---|---|
| persistent object | 一个 ENTER，无重复 | F1 `ENTER #1 circle` | PASS |
| single-frame noise | 不产生事件 | 无事件 | PASS |
| short dropout | 同一 ID、无第二次 ENTER | 仅 F1 `ENTER #1` | PASS |
| true removal | 一个 ENTER、一个 EXIT | F1 ENTER；F5 EXIT | PASS |
| re-entry | #1 EXIT 后 #2 ENTER | F1 ENTER #1；F5 EXIT #1；F7 ENTER #2 | PASS |
| multi-class | triangle、circle 分别 ENTER | 两个独立 ID/ENTER | PASS |
| three objects | 三类分别 ENTER | #1 triangle、#2 rectangle、#3 circle | PASS |
| same-label objects | 两个 circle 两个 ID | #1 与 #2 分离 | PASS |
| small movement | ID 不变 | 仅一次 ENTER #1 | PASS |
| confidence variation | 不因置信度波动重建 | 仅一次 ENTER #1 | PASS |
| detection order change | ID 不因列表顺序改变 | triangle #1、circle #2 保持 | PASS |
| clear all | 三个对象分别且仅 EXIT 一次 | F5 三个 EXIT | PASS |

所有期望与逐帧 object states、actual events、confidence 和 frame index 均位于结构化 JSON；CSV 为事件摘要。输入明确标为 `offline_simulated_detection_sequence`。

## M3 → M4 集成

测试 `test_m3_synthetic_detections_feed_m4_without_classifier_changes` 实际读取 M3 `multi_normal.png`，获得 triangle、rectangle、circle 三个 detections，连续输入两帧：第一帧无事件，第二帧产生三个独立 ENTER。该测试直接复用 M3 pipeline，没有复制 classifier。

## 2026-09-07 真实摄像头生命周期

审计源为 `output/m5/sessions/session-2026-09-07T145826.788_0800.json`，SHA-256 `ADF9E4E0D438B076210F5AADDDB7D82BBFE050ED471842143F9C2F9D97184F96`。该真实 Insta360 session 共保存 117 个事件，字段 `event_count=117` 与数组数量一致，event ID 由 1 连续至 117；全量审计未发现同一 object ID 重复 ENTER、重复 EXIT 或 EXIT/ENTER 次序异常。

| event ID | frame | event | object | label | confidence | 结论 |
|---:|---:|---|---:|---|---:|---|
| 115 | 31606 | OBJECT_ENTER | 75 | circle | 0.924981 | 两帧确认后进入 |
| 116 | 33660 | OBJECT_EXIT | 75 | circle | 0.973510 | 离场并连续缺失后退出 |
| 117 | 33928 | OBJECT_ENTER | 76 | circle | 0.957774 | 重新放入后获得新 ID |

#75 的 `first_seen=31605`、`last_seen=33656`、`hit_count=2050`，期间仅 event 115 一次 ENTER；最终状态为 exited。#76 的 `first_seen=33927`，截至 Stop 的 `last_seen=46234`、`hit_count=12308`，保持 active/confirmed，且只产生一次 ENTER。这组结构化数据直接证明“持续停留不重复、离场 EXIT、重入新 ID”。

短暂遮挡保持 ID 是项目负责人在现场 GUI 中人工观察通过；session summary 没有保存该短区段的逐帧 snapshot，故本记录只写“现场人工观察 + GUI 截图”，不把它冒充 JSON 单独可证明结论。GUI 事件截图显示 #75 ENTER/EXIT 与 #76 ENTER 的时间顺序。

精选证据：

- `../../evidence/data/m4/m4-live-lifecycle-summary.json`
- `../../evidence/data/m4/m4-live-lifecycle-events.csv`
- `../../evidence/screenshots/m4/live/m4-live-lifecycle-events.png.png`

session 报告 `git.dirty=true`，本字段未修改或隐藏；审计开始时没有 tracked diff，只有操作者保存的 M4/M5 live 截图为未跟踪文件。运行基线 commit 仍明确记录为 `78597f58`。

## 性能

300 帧、每帧 3 个 detection，共 900 detections；状态管理实测 `4.294 ms`，产生 3 个 ENTER。该值不含图像处理和文件 I/O，仅证明 M4 状态层不是当前视觉链路瓶颈。

## 回归

- M4 离线阶段当时完整 pytest：`95 passed in 1.52s`；2026-09-07 最终仓库回归：`172 passed in 3.59s`。
- M2 十张真实离线图片：`10/10`。
- M3 synthetic：normal、bright、dark、side-light 在两种方案下仍全部精确识别三类；遮挡/接触局限未改写。
- `pip check`：`No broken requirements found.`。
- 同次最终回归：M2 10/10、M3 synthetic 必验光照 4/4、M4 12/12、M5 短时功能冒烟正常关闭。

## 证据

- 输入：`../../test_data/m4/detection-sequences.json`
- JSON：`../../evidence/data/m4/m4-offline-event-results.json`
- CSV：`../../evidence/data/m4/m4-offline-event-results.csv`

> [!warning] 验收边界
> M4 `DONE` 代表 PC 端把逐帧 detection 转为去重 ENTER/EXIT 的子能力完成。FIFO、按键出队、通信和 ACK 由后续控制器阶段完成。

## 关联记录

- [[../decisions/DECISION-004-M4-确定性关联与事件状态机]]
- [[../daily/2026-09-04-M4-离线事件去重验证]]
- [[../daily/2026-09-07-M3-M4-M5-最终真实验收]]
