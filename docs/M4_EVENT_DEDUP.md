# M4：防重复识别与离散事件生成

## 当前状态

M4 为 `DONE`。软件实现、12 个 detection-only 离线模拟场景、M3 synthetic 集成测试和结构化证据均已完成；2026-09-07 又完成真实 Insta360 camera 生命周期验收。本模块没有修改 M3 分类规则。

## 数据流与边界

```text
M3 detections[]
    -> label + bbox spatial association
    -> candidate / confirmed / missing / exited state
    -> OBJECT_ENTER / OBJECT_EXIT
```

M4 只接收 detections，不接收图像，也不调用灰度化、二值化、轮廓或分类逻辑。`detections_from_analysis()` 是唯一 M3 适配层：M3 的 `ContourFeatures.bounding_box` 格式为 ROI 内 `(x, y, width, height)`，适配器加上 ROI 左上角后转换为整帧坐标。

## 数据模型

- `Detection`：瞬时观察，包含 `label`、几何 confidence、整帧 bbox、`frame_index`。
- `ObjectState`：跨帧逻辑对象快照，包含递增 `object_id`、label、bbox、first/last seen、hit/miss、confirmed、active、event emitted、status 和平均 confidence。
- `VisionEvent`：递增 `event_id`、`OBJECT_ENTER` 或 `OBJECT_EXIT`、object ID、label、平均 confidence、frame index。

一个确认对象的一次生命周期最多产生一次 ENTER 和一次 EXIT。事件 ID 由后续 TCP bridge 映射为 command ID。

## 关联与状态规则

同 label 才能关联；随后满足 `IoU >= 0.30` 或 bbox 中心距离 `<= 80 px` 即成为候选匹配。所有候选按 IoU、中心距离、object ID 确定性排序并一对一贪心匹配；新 detection 按整帧空间位置排序后分配递增 object ID，因此不依赖输入列表顺序。

配置位于 `pc/config/events.json`：

| 参数 | 当前值 | 含义 |
|---|---:|---|
| `min_confirm_frames` | 2 | 连续命中两帧后确认并发出 ENTER |
| `max_missing_frames` | 3 | 已确认对象最多容忍连续三帧漏检 |
| `iou_threshold` | 0.30 | 同 label 的 IoU 关联阈值 |
| `center_distance_threshold` | 80.0 px | 低 IoU 时允许的小幅位置变化 |

未确认 candidate 一旦下一帧丢失即结束且不产生事件。已确认对象第 1～3 帧缺失时保持同一 ID，第 4 帧缺失时产生 EXIT；再次出现会创建新 ID，经两帧确认后产生新 ENTER。

## 离线运行

```powershell
.\.venv\Scripts\python.exe -m pc.events `
  --config pc/config/events.json `
  simulate `
  --input test_data/m4/detection-sequences.json `
  --output-json output/m4/event-results.json `
  --output-csv output/m4/event-results.csv
```

输入固定声明为 `offline_simulated_detection_sequence`。12 个场景全部 PASS，包括持续停留、单帧噪声、短暂漏检、真实移除、重入、多类别、三目标、同类双目标、小幅移动、confidence 变化、检测顺序变化和全部清空。300 帧、900 detections 的状态管理实测 4.294 ms；该数值只包含状态管理，不包含视觉和文件 I/O。

## M3 集成

自动化集成测试实际读取 `test_data/m3/synthetic/multi_normal.png`，调用现有 `analyze_multiple_objects()`，再将同一组三个 detections 连续输入 M4 两帧。第一帧无事件，第二帧产生 triangle、rectangle、circle 三个稳定 ENTER；没有复制或修改 M3 classifier。

## Live 入口与真实验收

```powershell
.\.venv\Scripts\python.exe -m pc.vision `
  --config pc/config/vision.json `
  multi-live `
  --camera-config pc/config/camera.json `
  --roi-mode auto `
  --expected-labels triangle rectangle circle `
  --events `
  --event-config pc/config/events.json
```

事件跟踪固定使用默认 Otsu detection，避免 `T` 键切换显示方案改变状态。画面显示 tracked IDs 和最近事件；控制台逐条打印 ENTER/EXIT；session JSON 自动记录配置、全部事件和最终对象状态。M4 验证无需额外按键，M3 的 `1`～`5` 仍只用于保存五场景成对证据。

2026-09-07 的真实 session 运行 1577.142974 秒并记录 117 个事件。审计确认 event ID 1～117 连续，所有 object ID 至多一次 ENTER 和一次 EXIT。重点 circle 生命周期：frame 31606 `OBJECT_ENTER #75`；#75 持续命中 2050 次且没有第二次 ENTER；离场后 frame 33660 `OBJECT_EXIT #75`；重入后 frame 33928 `OBJECT_ENTER #76`。#76 截至 Stop 仍 active/confirmed。

短暂遮挡保持 ID 是现场人工观察 + GUI 截图结论；session 没有保存该时间段的逐帧 snapshot，故不写成 JSON 单独可证明。结构化摘要与 focused CSV 位于 `evidence/data/m4/`，事件截图位于 `evidence/screenshots/m4/live/`。

## 已知限制

- 关联只使用 label、IoU 和中心距离，不预测运动，不处理交叉后 ReID。
- `max_missing_frames` 按处理帧而非墙钟时间计数；实时运行帧率变化会改变实际容忍时长。
- 严重跳动超过两个空间阈值会创建新对象。
- M3 合并轮廓输出 `unknown` 时，M4 不会把物理目标重新分开。
- M4 已接入 GUI 展示；TCP、FIFO 和实体控制由后续 M7–M10 负责。
