# M2 第一阶段：离线单目标轮廓识别

## 范围与状态

本阶段仅处理 `test_data/raw/m2/` 下的离线图片，不打开摄像头，不实现多目标、抗光照、GUI 或网络通信。项目负责人已确认离线阶段通过；后续 TEST-003 真实摄像头验收也已通过，因此整个 M2、VISION-001、VISION-002 现为 `DONE`。

## 主处理链路

```text
原图
  -> 归一化 ROI
  -> BGR 转灰度
  -> 5x5 Gaussian Blur
  -> THRESH_BINARY_INV + Otsu
  -> 3x3 形态学开运算
  -> RETR_EXTERNAL 外轮廓
  -> 面积/solidity/触边筛选
  -> 选择最大的有效轮廓（M2 单目标约束）
  -> approxPolyDP 与几何规则
  -> triangle / rectangle / circle / unknown
```

Canny 从滤波后的灰度图单独产生，只用于人工检查和实验报告，不参与当前轮廓提取或分类。

## 参数与来源

所有运行参数集中在 `pc/config/vision.json`。当前 ROI 为归一化坐标 `(0.24, 0.08) - (0.76, 0.75)`；在 1920×1080 图片上对应像素范围 `[461, 86, 1459, 810]`。

关键初始阈值如下：

| 参数 | 当前值 | 工程含义 |
|---|---:|---|
| `min_area_ratio` / `max_area_ratio` | 0.02 / 0.25 | 有效轮廓占 ROI 面积范围 |
| `min_solidity` | 0.90 | 剔除破碎或强凹轮廓 |
| `border_margin_pixels` | 2 | 剔除与 ROI 边界连接的桌边、人体或支架干扰 |
| `approx_epsilon_ratio` | 0.02 | `approxPolyDP` 的周长比例 |
| 矩形最大直角偏差 | 25° | 保留透视和打印边缘误差容差 |
| 矩形最小填充率 | 0.80 | 轮廓面积 / 最小外接矩形面积 |
| 圆形最小顶点数 | 6 | 多边形近似后排除三角形和四边形 |
| 圆形最小圆度 | 0.78 | `4πA/P²` |
| 圆形最小宽高比 | 0.80 | 边界框短边 / 长边 |

这些值来自 2026-09-04 对当前 3 个三角形、3 个矩形、3 个圆形和 1 张空背景的勘察，并刻意保留了宽于当前观测范围的容差。它们不是一般化结论，也不是准确率保证；M3 仍需在更多位置、尺度、旋转、光照、遮挡和多目标条件下重新验证。

## 分类规则

- `triangle`：轮廓凸且近似顶点数等于 3。
- `rectangle`：轮廓凸、近似顶点数等于 4、最大直角偏差不超过配置阈值，且最小外接矩形填充率达到阈值。
- `circle`：轮廓凸、近似顶点数不少于配置值、圆度和宽高比均达到阈值。
- `unknown`：轮廓通过有效性筛选，但不满足以上三类规则。
- `no_object`：没有轮廓通过有效性筛选。

## confidence 的工程含义

`confidence` 是几何规则符合度，不是神经网络概率、统计置信度或识别正确率。其范围为 `[0, 1]`：

```text
confidence = 0.50 * topology_score
           + 0.30 * geometry_score
           + 0.20 * quality_score
```

- `topology_score`：顶点数及类别拓扑规则符合程度。
- `geometry_score`：圆度、宽高比、矩形角度/填充率等相对决策阈值的余量。
- `quality_score`：solidity 与轮廓面积距离筛选边界的余量。
- `unknown` 和 `no_object` 当前返回 `0.0`，避免用一个非类别分数制造确定性错觉。

各项达到“较好”分数的位置也全部位于配置文件中。`confidence=0.90` 只能解释为“该轮廓较充分地符合当前几何规则”，不能解释为“90% 概率分类正确”。

## 输出与复现

```powershell
.venv\Scripts\python.exe -m pc.vision `
  --config pc/config/vision.json `
  batch `
  --input-root test_data/raw/m2 `
  --output-json test_data/m2/2026-09-04-offline-results.json `
  --output-csv test_data/m2/2026-09-04-offline-results.csv `
  --diagnostics-dir output/m2/diagnostics `
  --evidence-dir evidence/screenshots/m2 `
  --acceptance-status offline_stage_user_validated
```

- 原始图片目录被 Git 忽略。
- `output/m2/diagnostics/` 保存全部 10 张图片的本地拼图，但作为运行输出被 Git 忽略。
- `evidence/screenshots/m2/` 保存每类第一张图片的代表性拼图。
- JSON 保存配置快照、环境、源文件 SHA-256 和完整特征；CSV 提供便于核对的一行一图摘要。
- JSON 的 `acceptance_status` 默认是 `pending_user_validation`；只有得到项目负责人明确确认后，才可在命令中写入 `offline_stage_user_validated`。当前归档结果使用后者。
