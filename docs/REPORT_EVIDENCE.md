# 报告证据链

本表用于从真实项目记录反向生成综合实验报告、测试报告、答辩 PPT 和演示视频。只有实际完成并可定位的材料才能替换 `TODO`。不得填写预测准确率、虚构测试结果或补拍后无法关联版本的截图。

| Requirement ID | 实现代码 | Git commit | Test ID | 实验日志 | 截图 | 数据文件 | 报告章节 |
|---|---|---|---|---|---|---|---|
| SCOPE-001 | TODO | TODO | TODO | TODO | TODO | TODO | 系统总体设计/系统集成 |
| VISION-001 | `pc/vision/preprocess.py`、`contours.py`、`roi.py`、`live.py`、`pc/config/vision.json` | 实现 `9f7ae794`；证据 `d8f6f60b` | TEST-002（离线 PASS）、TEST-003（实时 PASS） | `notes/daily/2026-09-04-M2-离线单目标轮廓识别.md`、`2026-09-04-M2-最终真实验收.md` | 离线：`evidence/screenshots/m2/`；实时：`evidence/screenshots/m2/live/` | 离线：`test_data/m2/2026-09-04-offline-results.*`；实时精选摘要：`evidence/data/m2-live-acceptance-summary.json` | 视觉算法/图像预处理 |
| VISION-002 | `pc/vision/classifier.py`、`pipeline.py`、`live.py` | 实现 `9f7ae794`；证据 `d8f6f60b` | TEST-002（离线 PASS）、TEST-003（实时 PASS） | 同上 | 离线：`evidence/screenshots/m2/`；实时：`evidence/screenshots/m2/live/` | 离线：`test_data/m2/2026-09-04-offline-results.*`；实时：`evidence/data/m2-live-acceptance-summary.json` | 视觉算法/形状分类 |
| VISION-003 | `pc/vision/pipeline.py`、`m3_live.py`、`m3_reporting.py`、`synthetic.py` | 基础实现 `8815e443`；离线证据 `445f0b2`；真实运行 `78597f58`；精选证据 `68c89d9` | TEST-004（synthetic + camera PASS） | `notes/daily/2026-09-04-M3-离线合成验证.md`、`2026-09-07-M3-M4-M5-最终真实验收.md` | 合成：`evidence/screenshots/m3/synthetic/`；真实：`evidence/screenshots/m3/live/` | 合成：`evidence/data/m3/m3-offline-synthetic-results.*`；真实五场景：`evidence/data/m3/live/` | 视觉算法/多目标检测 |
| VISION-004 | `pc/vision/preprocess.py`、`m3_live.py`、`m3_reporting.py`、`pc/config/vision.json` | 基础实现 `8815e443`；离线证据 `445f0b2`；真实运行 `78597f58`；精选证据 `68c89d9` | TEST-004（真实三种光照双方案 PASS） | 同上 | `evidence/screenshots/m3/live/normal_light/`、`bright_or_side_light/`、`dark_light/`；失败样例同级保留 | 每场景原始 `evidence.json` / `comparison.csv` 位于 `evidence/data/m3/live/` | 视觉算法/抗光照处理 |
| GUI-001 | `pc/gui/`（PySide6、QThread worker、source adapters、snapshot/latest-frame buffer、desktop workspace theme/overlay） | 实现 `bbb6fa7`；自动化测试 `eb7a1fd`；真实运行 `78597f58`；精选证据 `68c89d9` | TEST-006（Part A synthetic、Part B camera 均 PASS） | `notes/daily/2026-09-04-M5-GUI离线软件验证.md`、`2026-09-07-M3-M4-M5-最终真实验收.md` | synthetic：`evidence/screenshots/m5/synthetic/`；真实 running/Idle：`evidence/screenshots/m5/live/` | synthetic soak：`evidence/data/m5/m5-offline-gui-results.*`；真实摘要：`evidence/data/m5/m5-live-camera-session-summary.json` | 上位机界面 |
| PLC-001 | TODO | TODO | TODO | TODO | TODO | TODO | PLC 设计/FIFO |
| PLC-002 | M4 子能力：`pc/events/`、`pc/config/events.json`；PLC 部分 TODO | M4 实现 `7d83c57`；离线证据 `46bb2a6`；真实运行 `78597f58`；精选证据 `68c89d9`；PLC TODO | TEST-005（M4 离线 + camera 生命周期 PASS）；完整 PLC 测试 TODO | `notes/daily/2026-09-04-M4-离线事件去重验证.md`、`2026-09-07-M3-M4-M5-最终真实验收.md` | `evidence/screenshots/m4/live/m4-live-lifecycle-events.png.png` | 离线：`evidence/data/m4/m4-offline-event-results.*`；真实：`evidence/data/m4/m4-live-lifecycle-summary.json`、`evidence/data/m4/m4-live-lifecycle-events.csv` | 事件去重/生产者消费者前置 |
| PLC-003 | TODO | TODO | TODO | TODO | TODO | TODO | PLC 设计/LED 分拣 |
| PLC-004 | TODO | TODO | TODO | TODO | TODO | TODO | PLC 设计/队列状态与复位 |
| COMM-001 | TODO | TODO | TODO | TODO | TODO | TODO | 通信协议/帧格式 |
| COMM-002 | TODO | TODO | TODO | TODO | TODO | TODO | 通信协议/心跳报警 |
| COMM-003 | TODO | TODO | TODO | TODO | TODO | TODO | 通信协议/重发与满通知 |
| SYS-001 | TODO | TODO | TODO | TODO | TODO | TODO | 系统集成与联调 |
| TEST-001 | TODO | TODO | TODO | TODO | TODO | TODO | 测试方案与结果 |
| DOC-001 | TODO | TODO | TODO | TODO | TODO | TODO | 问题分析与改进方向 |
| HW-001 | TODO | TODO | TODO | TODO | TODO | TODO | 硬件平台/PLC |
| HW-002 | `pc/camera/`、`requirements.txt` | `d2b864d` | TEST-001 | `notes/daily/2026-09-03-M1-USB摄像头稳定采集.md` | `evidence/screenshots/M1-insta360-1080p-sample.jpg` | `test_data/m1/2026-09-03-insta360-stability.json` | 软件与运行环境 |
| HW-003 | `pc/camera/`、`pc/config/camera.json` | `d2b864d` | TEST-001 | `notes/daily/2026-09-03-M1-USB摄像头稳定采集.md` | `evidence/screenshots/M1-insta360-1080p-sample.jpg` | `test_data/m1/2026-09-03-insta360-stability.json` | 硬件平台/摄像头 |
| HW-004 | TODO | TODO | TODO | TODO | TODO | TODO | 实验对象与样本 |
| HW-005 | TODO | TODO | TODO | TODO | TODO | TODO | 实验场地与背景 |
| HW-006 | TODO | TODO | TODO | TODO | TODO | TODO | 硬件平台/通信连接 |
| DELIV-001 | TODO | TODO | TODO | TODO | TODO | TODO | 综合实验报告自检 |
| DELIV-002 | TODO | TODO | TODO | TODO | TODO | TODO | 源码交付自检 |
| DELIV-003 | TODO | TODO | TODO | TODO | TODO | TODO | PLC 工程交付自检 |
| DELIV-004 | TODO | TODO | TODO | TODO | TODO | TODO | 通信协议文档自检 |
| DELIV-005 | TODO | TODO | TODO | TODO | TODO | TODO | 测试报告自检 |
| DELIV-006 | TODO | TODO | TODO | TODO | TODO | TODO | 答辩材料自检 |
| DELIV-007 | TODO | TODO | TODO | TODO | TODO | TODO | 演示视频自检 |
| PLAN-001 | TODO | TODO | TODO | TODO | TODO | TODO | 实验过程与进度 |

## 填写约定

- **实现代码**：仓库相对路径，必要时精确到函数、PLC 程序块或文档标题。
- **Git commit**：能够重建该证据的 commit hash；工作区未提交状态不能作为最终证据。
- **Test ID**：链接到 `notes/tests/` 中的实际测试记录。
- **实验日志**：链接到 `notes/daily/` 中对应日期记录。
- **截图/数据文件**：只登记真实存在的仓库路径或明确的外部归档位置。
- `output/m2/` 中完整 runtime 数据被 Git 忽略；最终证据链只引用从这些真实文件审计后筛选出的标注图和摘要，不提交完整运行数据。
- M3 的 `synthetic/` 子目录与 `m3-offline-synthetic-results.*` 仍只表示合成软件验证；真实证据必须明确指向 `evidence/data/m3/live/` 和 `evidence/screenshots/m3/live/`，二者不可混称。
- M4 的 `m4-offline-event-results.*` 是 detection-sequence 离线模拟；`m4-live-lifecycle-*` 与 `screenshots/m4/live/` 才是 camera 生命周期证据。即使 M4 已 DONE，也不是 PLC 队列证据。
- M5 的 `screenshots/m5/synthetic/` 和 `m5-offline-gui-results.*` 仍是离线证据；`m5-live-camera-session-summary.json` 与 `screenshots/m5/live/` 才是本次真实 camera GUI 验收材料。
- **报告章节**：当前仅是建议归属；最终目录确定后再填写准确章节号。

## M3/M4/M5 最终真实验收（2026-09-07）

真实运行基线为 `78597f58e63f8f262fd0df25757218994345dc39`，精选原始证据 commit 为 `68c89d9`。M3 的 5 个原始场景 JSON/CSV、15 张 frame/annotated 图片，M4 focused lifecycle JSON/CSV 和截图，以及 M5 camera session 摘要与 running/Idle 截图均已进入上表对应路径。完整 runtime 继续位于 ignored `output/`，未提交、未覆盖、未删除。

本次最终回归为 172 项 pytest 全部通过、M2 10/10、M3 synthetic 必验光照 4/4、M4 12/12、M5 短时功能冒烟正常关闭、M6 16/16 且确定性重放；摘要见 `evidence/data/m3-m5-final-regression-summary.json`。M5 短时 synthetic 的 17.327158 FPS 不作为性能证据，真实性能只引用 camera session 的 29.315668 FPS。

## PLC 资料来源（非测试证据，2026-09-05）

指导书已原样归档到 `reference/PLC实验指导书（实验箱版20251015）(1).docx`，SHA-256 见 `reference/README.md`，核查结果见 `docs/PLC_HARDWARE.md`。负责人确认实物 CPU 1214C DC/DC/DC；没有执行 TIA 编译、下载、I/O、通信或真实 PLC 验收，不替换上表的测试 TODO。PLC 同学后续提交 `plc/records/` 和精选证据，由负责人审核并汇总。

## M6 模拟器独立验收（2026-09-05）

| 范围 | 实现与版本 | Test / Daily | 数据 | 结论 |
|---|---|---|---|---|
| M6 软件模拟器 | `simulator/`、`pc/tests/test_m6_simulator.py`；`00fa6fb3256f8d763cb6b8be765fdf34a716b007` | `notes/tests/TEST-007-M6-Fake-PLC模拟器验收.md`；`notes/daily/2026-09-05-M6-Fake-PLC离线验收.md` | `evidence/data/m6/m6-fake-plc-scenario-results.json` 与 `.csv` | 16/16 场景、确定性重放、M4集成 PASS；M6 DONE |
| 本轮上游离线回归 | 同一代码commit | 同上 | `evidence/data/m6/m6-regression-summary.json`、M2–M5 CSV、`m5-synthetic-smoke.json` | 全量172 passed；照片10/10、M3四必验光照通过、M4十二场景通过、M5功能冒烟正常关闭 |

正式模拟器 JSON 生成时 dirty=false；含源码SHA-256、配置、故障、步骤、expected/actual、最终PLC状态及benchmark。所有 M6 数据为 **simulated / Fake PLC / no physical PLC**，没有截图要求。M5短时冒烟16.73FPS不算性能验收。实现和接口限制见 `M6_FAKE_PLC.md`。

M6 fault scenarios 可供未来 M7/M9 复用，仅为 supporting simulator available；上表 PLC-001–004、COMM-001–003 的真实/正式验收仍待执行，不填未来 PASS。

## M9 i.MX6ULL Controller 实机部署（2026-09-10）

| 范围 | 实现与版本 | Test / Daily | 证据 | 结论 |
|---|---|---|---|---|
| Python 3.7 Controller 与真实 TCP | `device/imx6ull/`、`pc/communication/protocol.py`；`9906133a6db4e5391704fadf3c3b94b0b893b765` | `notes/tests/TEST-008-M9-iMX6ULL部署与TCP验证.md`；`notes/daily/2026-09-10-M9-iMX6ULL实机部署与TCP验证.md` | `docs/IMX6ULL_DEPLOYMENT.md` 记录板端环境、compileall、监听与 10 项真实 `198.51.100.2:9000` smoke 响应 | i.MX6ULL 软件部署/TCP PASS |
| 实体 gpio-keys 三按键与 Controller FSM | `device/imx6ull/overlay/`、`LinuxInputKeyInput`；`468f7bb223efe97af1a76198bde7dc237ba14b3e` | `notes/tests/TEST-009-M9-iMX6ULL实体GPIO按键验收.md`；`notes/daily/2026-09-10-M9-iMX6ULL实体GPIO按键验收.md` | 板端 overlay、`gpioinfo`、`huiyan-keys` raw `/dev/input` log（148/149/202 的 press/release）及真实 TCP 上的物理 FSM 闭环 | GPIO 输入 PASS；输出另见 TEST-010，M9 DOING |
| 受限 LED helper 与实体按键/FSM/LED 闭环 | `device/imx6ull/output/`、`huiyan-led-helper.service`；`a8b54179ef16d85946407ae86d8cee9661b3744d` | `notes/tests/TEST-010-M9-iMX6ULL实体LED闭环验收.md`；`notes/daily/2026-09-11-M9-iMX6ULL实体LED闭环验收.md` | root helper socket/权限、普通用户 Controller、raw code 149/202、Branch3 约 996 ms brightness 序列、操作者 RGB 观察与真实 TCP state/reset | M9 输出子范围 PASS；完整 PC vision E2E 未测，M9 DOING |

本条不是 PLC 证据，也不证明完整 PC-vision 视觉闭环；这些原始 PLC/视觉端到端项目继续保持 TODO。
