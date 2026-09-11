---
title: TEST-004 M3 多目标与抗光照验收
date: 2026-09-04
tags:
  - 慧眼识珠
  - test
  - M3
  - camera
result: pass
---

# TEST-004 M3 多目标与抗光照验收

- **Test ID**：TEST-004
- **对应 Requirement ID**：VISION-003、VISION-004
- **Git commit**：多目标基础 `8815e443`；合成数据集 `935e637`；离线 runner `32c06ba`；离线证据 `445f0b2`；真实运行 HEAD `78597f58e63f8f262fd0df25757218994345dc39`（五组 evidence 均 `dirty=false`）；精选真实证据 `68c89d9`
- **环境**：Windows 11 10.0.26200、Python 3.12.10、OpenCV 5.0.0、NumPy 2.5.2、Insta360 Ace Pro 2、DirectShow、MJPG、1920×1080@30
- **结果**：离线 synthetic 与真实 M3 摄像头验收均 PASS；遮挡和接触失败按预定规则记为诊断局限

## 测试目标

以最少操作验证同屏多个独立目标，以及 Otsu 与 CLAHE+Otsu 在三种真实光照下的同帧结果；额外记录部分遮挡和目标接触/粘连，不要求后两者必须完全识别。

## 启动命令

```powershell
.\.venv\Scripts\python.exe -m pc.vision `
  --config pc/config/vision.json `
  multi-live `
  --camera-config pc/config/camera.json `
  --roi-mode auto `
  --expected-labels triangle rectangle circle
```

## 操作步骤

1. 固定相机和白色工作区，启动后完成 auto 或 manual ROI 校准。
2. 将 triangle、rectangle、circle 三个目标彼此分开放入 ROI；确认画面分别标注后，在正常光照按 `1`。
3. 保持目标位置，增加亮度或形成可重复侧光，按 `2`。
4. 保持目标位置，降低环境亮度，按 `3`。
5. 恢复正常光照，使一个目标被部分遮挡，按 `4`。
6. 让两个目标边缘接触或产生粘连，按 `5`。
7. 可按 `T` 切换屏幕显示，但每个数字键都会自动保存两种方案对同一帧的结果。
8. 按 `Q` 或 Esc 退出；保留控制台输出和完整 session JSON。

> [!warning] 真值与场景声明
> `--expected-labels` 和数字键场景来自操作者声明，不是算法自动获得的真值。验收时必须查看 `frame.jpg` 和两张 annotated 图确认实际摆放与光照，不能只读取 `matches_expected_labels`。

## 预期及判定

| 场景 | 最小验收要求 | 当前结果 |
|---|---|---|
| 正常光照、三个目标分离 | 至少 2 个目标分别输出；优先要求三类全部输出 | Otsu 与 CLAHE+Otsu 均为 3 个对象、三类正确，PASS |
| 较亮/侧光 | 两种方案对同一帧均有完整记录 | 手机侧向补光真实帧；两种方案均为 3 个对象、三类正确，PASS |
| 较暗 | 两种方案对同一帧均有完整记录 | 整体亮度降低真实帧；两种方案均为 3 个对象、三类正确，PASS |
| 部分遮挡 | 记录真实输出、几何特征和失败情况 | 两种方案均为 `circle, unknown, triangle`；被遮挡目标 unknown，局限已记录 |
| 接触/粘连 | 记录真实输出；合并为一个轮廓可作为已知局限 | 矩形与圆形实际接触；两种方案均为 `unknown, triangle`，局限已记录 |

VISION-003 的真实分离多目标条件已满足；VISION-004 的三种真实光照同帧双方案条件已满足。遮挡/粘连失败已保留并分析，按预先定义不阻碍 M3。

## 输出

- 完整 runtime：`output/m3/live-evidence/`，Git ignored 且未删除。
- 每个场景：原帧、ROI、两种 normalized gray、binary、Canny、annotated、`evidence.json`、`comparison.csv`。
- 运行级 session：`output/m5/sessions/session-2026-09-07T145826.788_0800.json`，Git ignored；精选摘要另见 M5 证据。

## 2026-09-07 真实摄像头实际结果

启动请求 auto ROI；程序记录 `auto ROI found no acceptable central white quadrilateral (area=6, not_convex_quadrilateral=1)`，随后按设计进入 manual，选择 ROI `[548, 126, 1346, 698]`，normalized ROI 为 `(0.285417, 0.116667, 0.701042, 0.646296)`，并在整次运行中锁定。五组 evidence 均记录相同 ROI、Insta360 设备信息和运行 HEAD。

| 场景（runtime 目录） | 灰度统计 mean / median | Otsu：数量、标签、match | CLAHE+Otsu：数量、标签、match | 图片人工核对 |
|---|---:|---|---|---|
| `20260907-150301-528140-normal_light` | 163.293 / 188 | 3；circle/rectangle/triangle；true | 3；circle/rectangle/triangle；true | 三个分离黑色图形、普通室内光照 |
| `20260907-150808-200943-bright_or_side_light` | 171.017 / 194 | 3；circle/rectangle/triangle；true | 3；circle/rectangle/triangle；true | 左侧手机补光形成明显亮斑/侧光 |
| `20260907-151059-411630-dark_light` | 147.725 / 170 | 3；circle/rectangle/triangle；true | 3；circle/rectangle/triangle；true | 画面整体相对更暗 |
| `20260907-151234-170483-partial_occlusion` | 167.640 / 200 | 3；circle/unknown/triangle；false | 3；circle/unknown/triangle；false | 手部实际遮挡目标区域 |
| `20260907-151345-909809-touching_or_merged` | 173.214 / 201 | 2；unknown/triangle；false | 2；unknown/triangle；false | 矩形与圆形实际接触并形成合并外轮廓 |

每个目录 12 个文件齐全：`evidence.json`、`comparison.csv`、`frame.jpg`、`roi.jpg`、两种方法各自的 normalized gray/binary/Canny/annotated。CSV 分别有 6/6/6/6/4 个对象行，与 JSON 的 method、标签、confidence 和几何特征一致。人工逐张核对了 5 张 frame 和 10 张 annotated 图，不只依赖 `matches_expected_labels`。

### 方案结论

在本轮真实 normal、bright/side、dark 三种工况中，Otsu 与 CLAHE+Otsu 均完整识别 triangle/rectangle/circle。CLAHE+Otsu 未体现额外分类正确性收益，因此保留 Otsu 为默认实时方案，CLAHE+Otsu 作为对照/诊断方法。本次没有对两者做独立性能 benchmark，不声称存在速度差异。

### 精选真实证据

- 数据：`../../evidence/data/m3/live/`，每个场景保留原始 `evidence.json` 与 `comparison.csv`。
- 图片：`../../evidence/screenshots/m3/live/`，每个场景保留 `frame.jpg`、`otsu-annotated.jpg`、`clahe_otsu-annotated.jpg`。
- 完整 normalized gray/binary/Canny/ROI 继续保留在 ignored runtime，不无脑提交。

## 离线 synthetic 实际结果

2026-09-04 使用固定生成器参数运行 6 个场景、2 种方案。分离目标场景要求精确匹配；遮挡/接触只记录观察，不强制通过。

| 场景 | 期望 | Otsu | CLAHE+Otsu | 结论 |
|---|---|---|---|---|
| normal | 3：triangle、rectangle、circle | 3，三类正确 | 3，三类正确 | PASS（synthetic） |
| bright | 3：triangle、rectangle、circle | 3，三类正确 | 3，三类正确 | PASS（synthetic） |
| dark | 3：triangle、rectangle、circle | 3，三类正确 | 3，三类正确 | PASS（synthetic） |
| side_light | 3：triangle、rectangle、circle | 3，三类正确 | 3，三类正确 | PASS（synthetic） |
| partial_occlusion | 物理目标 3 | 2：triangle、unknown | 2：triangle、unknown | 已记录合并轮廓局限 |
| touching | 物理目标 3 | 2：triangle、unknown | 2：triangle、unknown | 已记录合并轮廓局限 |

版本化原始结果位于 `../../evidence/data/m3/m3-offline-synthetic-results.json` 和 `.csv`；其中包含每个目标的 confidence、bbox、area ratio、solidity、circularity、处理耗时、真值匹配和环境。12 张两方案标注图位于 `../../evidence/screenshots/m3/synthetic/`。

## 自动化与回归结果

- M3 离线阶段当时完整 pytest：`72 passed in 1.40s`；2026-09-07 最终仓库回归：`172 passed in 3.59s`。
- M2 真实离线数据回归：10/10 与标签一致。
- `pip check`：`No broken requirements found.`。
- 数据集测试确认 6 张图片、尺寸、确定性和 ground truth 字段完整。
- 离线 runner 测试确认双方案结构一致、JSON 可序列化、CSV 字段完整。
- 正常合成三目标图验证 triangle、rectangle、circle 分别输出并按中心从左到右排序。
- 接触/遮挡结果只记录观察，不把合并轮廓虚假拆分成多个对象。
- 2026-09-07 另行运行 M2 真实照片 10/10、M3 synthetic 必验光照 4/4、M4 离线 12/12、M5 5.021020 秒功能冒烟正常关闭。
- synthetic PASS 与真实 camera PASS 在本记录中分节列出，不互相替代。

## 关联记录

- [[../decisions/DECISION-003-M3-多目标与抗光照最小扩展]]
- [[../daily/2026-09-04-M3-最小实现与验收准备]]
- [[../daily/2026-09-04-M3-离线合成验证]]
- [[../daily/2026-09-07-M3-M4-M5-最终真实验收]]
