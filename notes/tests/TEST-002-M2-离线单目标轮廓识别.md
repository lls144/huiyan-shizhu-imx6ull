---
title: TEST-002 M2 离线单目标轮廓识别
date: 2026-09-04
tags:
  - 慧眼识珠
  - test
  - M2
result: pass-offline-only
---

# TEST-002 M2 离线单目标轮廓识别

- **Test ID**：TEST-002
- **对应 Requirement ID**：VISION-001、VISION-002
- **日期**：2026-09-04
- **Git commit**：真实测试工作区基于 `58507475b304748a81c3d4e0349f9d6536f01070`；实现归档于 `9f7ae794070a9d1cd853cc2893e71e742f25da52`，验收证据归档于 `d8f6f60b7801c7a8ff8d6d5d6bc809a3875069bb`

## 测试目标

验证配置化离线单目标处理管线能够读取 10 张真实图片，产生 ROI、灰度、滤波、Otsu 二值和 Canny 中间图，从二值图提取并筛选轮廓，输出五种状态之一：`triangle / rectangle / circle / unknown / no_object`。验证几何 confidence 与完整特征能够复现。

## 环境

- 电脑：项目 Windows 11 主开发电脑
- OS：Windows 11 10.0.26200
- Python：3.12.10，仓库 `.venv`
- OpenCV：5.0.0
- NumPy：2.5.2
- pytest：9.1.1
- 摄像头：本测试不打开摄像头；图片由项目负责人说明为 Insta360 Ace Pro 2 固定拍摄
- 控制器通信：不涉及
- 光照/实验条件：固定三脚架、固定白色背景；精确照度未测量

## 输入条件

- `test_data/raw/m2/background/`：1 张
- `test_data/raw/m2/triangle/`：3 张
- `test_data/raw/m2/rectangle/`：3 张
- `test_data/raw/m2/circle/`：3 张
- 10 张均为 JPEG、1920×1080；目录被 Git 忽略，JSON 中记录每张源文件 SHA-256。

## 操作步骤

1. 使用仓库 `.venv` 运行完整 pytest。
2. 使用 `python -m pc.vision ... batch` 读取四个目录。
3. 对每张图保存本地处理拼图，并保存每类第一张的精选证据拼图。
4. 输出带配置快照和环境的 JSON，以及一行一图的 CSV。
5. 人工查看四张代表性拼图，核对 ROI、二值结果、Canny 和标注轮廓。

## 预期结果

- 空背景输出 `no_object`；三类目标均输出对应类别。
- 每张目标图恰有一个有效目标轮廓，背景图没有有效轮廓。
- Canny 不参与分类主链路。
- `unknown` 至少由合成五边形单元测试覆盖。
- 原始图片缺失时真实数据集测试应 `skip`，不得伪造结果。

## 实际结果（项目负责人已确认离线阶段）

| 图片 | 真实类别 | 预测类别 | confidence | 顶点 | 面积占比 | solidity | circularity | 通过筛选 |
|---|---|---|---:|---:|---:|---:|---:|---|
| background_01.jpg | no_object | no_object | 0.000000 | — | — | — | — | 否（符合预期） |
| circle_01.jpg | circle | circle | 0.978040 | 8 | 0.097008 | 0.996319 | 0.899504 | 是 |
| circle_02.jpg | circle | circle | 0.968281 | 8 | 0.086336 | 0.995849 | 0.895046 | 是 |
| circle_03.jpg | circle | circle | 0.975308 | 8 | 0.093219 | 0.996088 | 0.896954 | 是 |
| rectangle_01.jpg | rectangle | rectangle | 1.000000 | 4 | 0.122621 | 0.992200 | 0.736207 | 是 |
| rectangle_02.jpg | rectangle | rectangle | 1.000000 | 4 | 0.140317 | 0.995591 | 0.766089 | 是 |
| rectangle_03.jpg | rectangle | rectangle | 1.000000 | 4 | 0.144051 | 0.994591 | 0.758628 | 是 |
| triangle_01.jpg | triangle | triangle | 1.000000 | 3 | 0.053818 | 0.988284 | 0.562930 | 是 |
| triangle_02.jpg | triangle | triangle | 1.000000 | 3 | 0.057311 | 0.990848 | 0.556580 | 是 |
| triangle_03.jpg | triangle | triangle | 0.991126 | 3 | 0.047338 | 0.984387 | 0.545774 | 是 |

- 批处理观测：10/10 与目录标签一致，0 个误分类；9/9 目标图各有 1 个有效轮廓；背景图 0 个有效轮廓。
- 离线第一阶段完成时 pytest：`35 passed in 0.44s`。（加入完整流水线的合成 `unknown` 用例前，两次回归分别得到 34 项通过。）
- M2 最终实时集成后的最新完整回归：`57 passed in 0.47s`；10 张真实离线图片仍为 10/10，与本表一致。
- 合成轮廓覆盖 triangle、旋转 rectangle、circle 和五边形 `unknown`；五边形另经完整筛选/分类流水线验证，空白图覆盖 `no_object`。
- 四张代表性拼图已人工查看，目标标注与二值轮廓一致。
- 系统级 `python -m pytest -q` 首次没有执行测试，原因是该解释器缺少 pytest；随后使用锁定依赖的 `.venv` 成功执行。这条环境问题不计为测试 Fail，也没有被隐藏。

## 原始数据位置

- 原始图片（不进 Git）：`test_data/raw/m2/`
- 完整 JSON：`test_data/m2/2026-09-04-offline-results.json`
- CSV 摘要：`test_data/m2/2026-09-04-offline-results.csv`
- 全部本地诊断拼图（不进 Git）：`output/m2/diagnostics/`

## 截图位置

- `evidence/screenshots/m2/M2-background_01-pipeline.jpg`
- `evidence/screenshots/m2/M2-triangle_01-pipeline.jpg`
- `evidence/screenshots/m2/M2-rectangle_01-pipeline.jpg`
- `evidence/screenshots/m2/M2-circle_01-pipeline.jpg`

## Pass / Fail

PASS（仅 M2 离线阶段）

> [!warning] 验收边界
> 离线 PASS 本身不构成整个 M2 `DONE`，也不能从 9 张目标图推导一般识别准确率。后续两种机位实时验收已在 [[TEST-003-M2-实时摄像头与ROI验收]] 通过，因此 M2 当前为 `DONE`。

## 已观察到的问题与局限

- ROI 底部仍包含桌边、人物或支架；其二值轮廓因触碰边界被筛除。若后续干扰完全进入 ROI 内部，当前规则可能误检。
- 只有 3 张/类且背景只有 1 张，未覆盖明显光照变化、尺度极端、遮挡、破损或多个目标。
- 当前真实图没有 `unknown` 物体；该分支只有合成五边形测试证据。
- 当前未观察到误检或漏检，但样本量不足以说明 M3 工况下的鲁棒性。

## 关联记录

- [[../daily/2026-09-04-M2-离线单目标轮廓识别]]
- [[../decisions/DECISION-001-M2-离线视觉管线与几何置信度]]
