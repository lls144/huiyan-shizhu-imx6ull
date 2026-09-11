---
title: DECISION-004 M4 确定性关联与事件状态机
date: 2026-09-04
tags:
  - 慧眼识珠
  - decision
  - M4
status: accepted-offline-pending-live
---

# DECISION-004 M4 确定性关联与事件状态机

- **Decision ID**：DECISION-004
- **状态**：离线方案已接受，真实摄像头参数仍待验证

## 选择

M4 不重新处理图像，只接收 M3 detections。目标先按 label 隔离，再以 bbox IoU 或中心距离做确定性一对一关联；连续两帧确认，允许三帧漏检，第 4 帧缺失产生 EXIT。object ID 和 event ID 都使用递增整数。

采用 `candidate -> confirmed -> missing -> exited` 最小状态语义。只有确认转换产生 ENTER，只有确认对象超出 missing 容忍产生 EXIT；持续帧和短时重现不产生新 ENTER。

## 理由

- 课程实验中的纸板目标主要静止或缓慢摆放，不需要复杂运动模型。
- label 加空间位置支持同类多个对象，优于全局 `last_label`。
- 纯 frame index 规则使离线测试确定，不依赖 `sleep()` 或系统时间。
- 与 M3 的边界清晰，后续 GUI 和通信只消费事件，不应消费每帧 detection。

## 明确不做

- 不使用 Kalman、SORT/DeepSORT、optical flow、ReID 或深度学习。
- 不建立控制器协议序号、FIFO、ACK、重发或队列满处理。
- 不为交叉、快速运动或遮挡恢复无限优化。
- 不以离线模拟代替真实摄像头生命周期验收。

## 验证入口

- [[../tests/TEST-005-M4-事件去重离线验收]]
- [[../daily/2026-09-04-M4-离线事件去重验证]]
