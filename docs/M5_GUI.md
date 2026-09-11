# M5：PySide6 实时视觉 GUI

## 当前状态与边界

M5 为 `DONE`。离线软件、线程生命周期、异常处理、自动化测试和 60 秒 synthetic soak 已完成；2026-09-07 的真实 Insta360 摄像头 GUI 又完成连续刷新、信息同步、性能和 Stop→Idle 正常关闭验收。本模块不承担 Controller FIFO 或实体执行逻辑。

## 数据流与线程边界

```text
FrameSource (synthetic / camera)
    -> VisionWorker in QObject + QThread
    -> existing M3 analyze_multiple_objects()
    -> existing M4 ObjectStateManager
    -> immutable GuiSnapshot
    -> bounded latest-frame buffer + Qt signal
    -> MainWindow on the UI thread
```

UI 线程只做 `QImage/QPixmap` 转换和控件刷新，不读取摄像头、不执行 OpenCV 轮廓识别，也不更新 M4 状态机。每个 `GuiSnapshot` 在 worker 内一次性组装，图像、detections、confidence 和 object states 来自同一帧。confidence 直接使用 M3 的几何规则符合度，不是神经网络或统计概率。

显示帧使用容量为 1 的 `LatestSnapshotBuffer`。当 UI 尚未消费上一帧时，新帧覆盖旧帧且不再追加 Qt 通知，从结构上避免无界 signal backlog。过期画面允许被丢弃，处理与事件完整记录仍保留在 session summary 中。

## 界面与交互

界面采用克制的深色桌面工具风格，参考现代编辑器的信息层级和密度，但不复制 Claude、Codex、VS Code 或 JetBrains 的品牌资源。2026-09-04 的 UI/UX 重构移除了“大标题 + 多个圆角 Card”的 Dashboard 结构，改为：

```text
Application Bar
└── QSplitter
    ├── Vision Workspace
    │   ├── compact workspace toolbar
    │   ├── borderless video viewport
    │   └── compact evidence toolbar
    └── continuous Inspector
        ├── Session
        ├── Detections
        ├── Tracked objects
        └── Events
└── Status Bar
```

Vision Workspace 与 Inspector 初始比例约为 72:28，允许拖动；Inspector 宽度限制在 300～420 px。1366×768 下无需整体滚动，视频仍是视觉主体。Inspector section 依靠 1 px divider、紧凑间距和小型 uppercase heading 分层，不再使用独立卡片或标题底板。

底部连续 Status Bar 显示 source、processed FPS、processing latency、frame、ROI mode、preprocess 和 state。顶部 Application Bar 压缩为 40 px，仅显示项目名、弱化副标题和小型状态点。Start/Stop 与 evidence 场景均使用 28 px `QToolButton`，没有网页 CTA、渐变、阴影或动画。

颜色、字体、尺寸、间距和 overlay 参数集中在 `pc/gui/theme.py` 的 `ThemeTokens` / `OverlayTokens`。主色为 `#181818` / `#1e1e1e`，侧栏 `#1b1b1b`，divider `#303030`，主要文字 `#d4d4d4`，强调蓝 `#3f86d9`，成功/错误色仅用于状态。Windows 使用 Segoe UI，并保留 Microsoft YaHei UI 中文回退。

已实现：

- 视频、bbox、label 和几何 confidence；
- M4 object ID、confirmed/active 状态和 ENTER/EXIT；
- processed FPS、单帧 processing ms、frame index；
- ROI mode/source/coordinates、preprocess、source 和 last error；
- Start、Stop、再次 Start、安全关闭；
- source open/read failure 和 vision exception 可见且可重试；
- synthetic 与 camera 两种 source adapter。

GUI 专用 overlay 位于 `pc/gui/overlay.py`：ROI 为 1 px 低权重灰线；detection 使用 YOLO 风格的类别色边框、深色外描边和同色实心标签，triangle/rectangle/circle/unknown 分别使用可区分颜色，标签文字根据底色亮度自动选择深色或白色，格式为 `#1 TRIANGLE 99.1%`。object ID、类别和 confidence 全部来自现有 M3/M4 结果，overlay 不重新分类或关联，也不改变用于 runtime evidence 的既有 M3 annotation。

没有加入无实际功能的重校准按钮。camera source 启动时直接复用 M2/M3 的 `auto -> manual -> fixed_normalized` 校准流程，ROI 在本次运行内锁定，不做逐帧动态追踪。

## Synthetic source

`SyntheticFrameSource` 复用 `test_data/m3/synthetic/`：blank、normal、normal hold、bright、dark、partial occlusion、touching、blank。默认 20 FPS、每场景 20 帧并循环；blank 为由已加载图像尺寸构造的确定性纯白帧。normal 连续帧触发 M4 ENTER，末尾 blank 触发 EXIT；遮挡/接触场景仍保留 M3 已知 merged contour / unknown 局限。

```powershell
.\.venv\Scripts\python.exe -m pc.gui --source synthetic
```

## 性能定义与离线实测

- `processed FPS`：worker 完成 source read、M3、M4 和标注后的实际吞吐，不使用摄像头 advertised FPS。
- `GUI update FPS`：主线程实际消费并展示 snapshot 的速率。
- M5 软件目标：处理链不低于 20 FPS，GUI 更新不低于 15 FPS；2026-09-07 真实摄像头实测已达到该目标。

2026-09-04 的 offscreen synthetic soak 请求 30 FPS，实际运行 60.011 s，处理和展示 1284 帧：`processing_fps=21.395960`、`gui_update_fps=21.395960`、平均处理 6.538 ms、P95 9.372 ms、0 failed read、0 display drop、0 buffer overwrite、`error=null`、正常停止。Python `tracemalloc` 峰值 64,671,161 bytes，只代表 Python 可追踪分配，不是进程总内存，也不据此宣称无内存泄漏。

上述仍只是 synthetic/offscreen 软件证据；真实摄像头验收数据单独列于下节，没有混用。

## Camera 启动与联合验收

```powershell
.\.venv\Scripts\python.exe -m pc.gui `
  --source camera `
  --camera-config pc/config/camera.json `
  --vision-config pc/config/vision.json `
  --event-config pc/config/events.json `
  --roi-mode auto `
  --expected-labels triangle rectangle circle
```

相机模式下数字键或界面按钮 `1`～`5` 分别保存 normal、bright/side、dark、occlusion、touching 的 M3 同帧双预处理 runtime evidence。M4 状态和事件自动进入 M5 session JSON。完整 runtime 位于被忽略的 `output/`；审计后才能精选真实证据进入 `evidence/`。

### 2026-09-07 真实结果

- 设备：Insta360 Ace Pro 2，DirectShow / MJPG / 1920×1080，请求 30 FPS，reported 30.000030 FPS。
- calibration：请求 auto；未找到合格中央白色四边形后降级 manual/selected；ROI `[548,126,1346,698]` 全程锁定。
- session：1577.142974 秒；46235 read / processed / GUI updates；processing 和 GUI update 均 29.315668 FPS。
- 健康：0 failed read、0 display drop、0 buffer overwrite、`error=null`、`ended_reason=stopped`、worker 与 GUI 均 clean shutdown。
- 同步展示：running 截图同时显示真实 circle 画面、`#76`、96.9% 几何 confidence、confirmed state、事件、29.3 FPS、ROI MANUAL 和 No errors。
- 停止：Stop 后截图显示顶部 Idle 与底部 IDLE，最后画面保留用于检查。

精选摘要位于 `evidence/data/m5/m5-live-camera-session-summary.json`；截图位于 `evidence/screenshots/m5/live/`。完整 session 继续保留在 ignored `output/m5/sessions/`，未覆盖或删除。

## 已知限制

- 当前 recent events 控件最多保留 30 条，完整事件保存在 session JSON。
- M3 合并轮廓的 `unknown` 会原样进入 M4/GUI，GUI 不负责修复分类。
- Stop 等待 worker 最多 5 秒；若未退出，窗口拒绝关闭并显示错误，不强杀线程。
- camera manual ROI 继续使用现有 OpenCV selector，没有为 Qt 重写一套 ROI 工具。
- UI/UX 重构截图为 synthetic/offscreen 画面：`evidence/screenshots/m5/synthetic/m5-gui-desktop-workspace.png`，不能冒充 camera evidence。
- 本次 auto ROI 未找到合格中央白色四边形；manual fallback 成功。这不支持“auto 100% 成功”的结论。
- 控制台曾出现 `QFont::setPointSize Point size <=0 (-1)`；该警告未进入 session JSON。由于 GUI 正常运行、Last error 为 No errors、session `error=null` 且 clean shutdown，归类为非阻断 UI warning，不视为视觉或摄像头错误。
