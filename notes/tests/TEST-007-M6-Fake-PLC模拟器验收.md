---
title: TEST-007 M6 Fake PLC 模拟器验收
date: 2026-09-05
tags: [慧眼识珠, M6, 测试, simulated]
status: PASS
---

# TEST-007 M6 Fake PLC 模拟器验收

> [!important] 验收范围
> Fake PLC / software simulation / no physical PLC。M6 正式验收不需要真实硬件；此 PASS 只关闭 M6，不关闭 M3/M4/M5 真实摄像头测试、M7/M8/M9 或 COMM/PLC 需求。

## Git 与环境

- 开始时 fetch 后 origin/master 与 HEAD：`8ac6d291fa74f1d6012118048ef862599f50fe8f`。
- 基线全量 pytest：110 passed；simulator/ 和 pc/communication/ 只有 .gitkeep；现有最高编号 TEST-006。
- 工作区已有 PLC 资料/规则修改，原样单独保存为 `62f2c71`；不是本次新增 PLC 功能。
- M6 实现/测试 commit：`00fa6fb3256f8d763cb6b8be765fdf34a716b007`。正式 M6 JSON 在此版本生成，dirty=false；后续提交仅含文档和精选证据。
- Windows 11 10.0.26200、Python 3.12.10、项目 .venv；OpenCV 5.0.0、NumPy 2.5.2、PySide6/Qt 6.11.2。没有增加依赖。
- 没有打开摄像头、连接真实 PLC 或运行真实通信。

## 输入与步骤

输入：`simulator/config/fake_plc.json`，capacity=3、heartbeat_interval_ms=1000、heartbeat_timeout_ms=2000、response_timeout_ms=100；三类语义指令及确定性 fault plan。M4 integration 使用原有 EventConfig、Detection、ObjectStateManager、VisionEvent，22 帧持续三目标，再 4 帧空输入。

在仓库根目录使用 `.\.venv\Scripts\python.exe`：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m simulator --scenario all --output-json output/m6/verified-scenarios.json --output-csv output/m6/verified-scenarios.csv
.\.venv\Scripts\python.exe -m pc.vision --config pc/config/vision.json batch --input-root test_data/raw/m2 --output-json output/m6/m2-regression.json --output-csv output/m6/m2-regression.csv --diagnostics-dir output/m6/m2-diagnostics
.\.venv\Scripts\python.exe -m pc.vision --config pc/config/vision.json multi-batch --input-root test_data/m3/synthetic --ground-truth test_data/m3/synthetic/ground_truth.json --output-json output/m6/m3-regression.json --output-csv output/m6/m3-regression.csv --diagnostics-dir output/m6/m3-diagnostics
.\.venv\Scripts\python.exe -m pc.events --config pc/config/events.json simulate --input test_data/m4/detection-sequences.json --output-json output/m6/m4-regression.json --output-csv output/m6/m4-regression.csv
.\.venv\Scripts\python.exe -m pc.gui --source synthetic --offscreen --soak-seconds 5 --summary-json output/m6/m5-regression.json --summary-csv output/m6/m5-regression.csv
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

复制完整小型 M6 JSON/CSV 至 evidence/data/m6；上游回归保留 CSV、汇总及 M5 小型 JSON，未提交原始图片或诊断图。汇总含原始 JSON 哈希。重跑会变化的性能时间/环境元数据不参与核心场景重放比较。

## 预期与实际

| 场景 | 预期 | 实际 | 结果 |
|---|---|---|---|
| normal_fifo | 三类依次 ACCEPTED | triangle, rectangle, circle；长度3 | PASS |
| dequeue_order | 严格 FIFO，最后空 | 三类同序出队；空出队 None | PASS |
| queue_full | 第4条拒绝，前三项不变 | QUEUE_FULL，长度3 | PASS |
| full_recovery | 消费后可手动再发 | ACCEPTED；rectangle,circle,triangle | PASS |
| invalid_shape | 非法 shape 不入队 | hexagon → INVALID，空队列 | PASS |
| duplicate | 同ID只接受一次 | ACCEPTED → DUPLICATE，一项 | PASS |
| request_loss | PLC未收到，调用方超时 | TIMEOUT；accepted_count=0、空队列 | PASS |
| ack_loss | PLC已入队、调用方超时；手动重发不重复 | TIMEOUT → DUPLICATE，始终一项 | PASS |
| delayed_ack | 截止前确认 | 50ms ACCEPTED | PASS |
| timeout | 101ms ACK 超过100ms截止 | TIMEOUT；队列一项；LATE_ACK 保留 | PASS |
| disconnect | 不投递，已有队列保留 | OFFLINE；原 triangle 保留 | PASS |
| reconnect | 保留队列且可继续 | 保留后消费原项，circle ACCEPTED | PASS |
| heartbeat_normal | 显式心跳保持健康 | healthy | PASS |
| heartbeat_lost | 心跳停止达到阈值 lost | last=1000ms，transition=3000ms；link仍connected | PASS |
| heartbeat_recovery | 再收心跳恢复 | healthy | PASS |
| m4_integration | 三 ENTER 入队，三 EXIT忽略，停留不重复 | ID=1,2,3；FIFO三项且顺序一致 | PASS |

16/16 场景全部通过；每个场景再次运行，输入事件、fault、完整 event log、expected/actual 和最终状态逐字段完全相同。

额外单元边界：非法配置与 fault；空队列；已消费 ID 去重；同 ID 不同 payload 拒绝；满队列优先识别 duplicate；指定 ID 的单次 ACK drop；延迟请求断连取消；超时后请求才入队；大幅推进时钟不误收迟到 ACK；ACK 恰好 deadline 视为迟到；同 ID 并发 exchange 不串响应；设备 online、link connected、heartbeat 独立；CLI 成功/失败退出码与 JSON/CSV。

## 回归与性能实际记录

- M6 专项：62 passed in 0.19s。
- 全量：172 passed in 3.78s，0 fail、0 skip，包含 M2–M6。
- M2 真实离线图片：10/10 匹配目录标签；是已有照片回归，没有本次摄像头实测。
- M3：6 场景 × 2 方法；4 个必验光照场景全部通过；遮挡/接触属于诊断场景，仍为 triangle + unknown，不能写成6/6完整识别。
- M4：12/12 场景通过。
- M5：5.019595s synthetic/offscreen 冒烟，84帧，16.734417 processing FPS，0 failed_reads，error=null，worker_clean_shutdown=true。测试与其他回归并行；仅证明功能/正常关闭，不作为20 FPS性能验收，也不替换已有60秒 soak 或后来 2026-09-07 的独立真实摄像头验收。
- M6 benchmark：250轮、1500次显式操作，0.0107343s；250 accepted、250 duplicate、250 consumed。含 enqueue/dequeue/duplicate/heartbeat/故障与时钟推进；只作开发效率参考，无硬件性能结论。
- pip check：No broken requirements found。
- git diff --check：通过；Git 的 LF/CRLF 提示不是 whitespace error。

## 证据位置

- `evidence/data/m6/m6-fake-plc-scenario-results.json`：正式模拟器完整证据、干净代码commit、源码SHA-256、16场景及重放。
- `evidence/data/m6/m6-fake-plc-scenario-results.csv`：16行场景摘要。
- `evidence/data/m6/m6-regression-summary.json`：M2–M5、pytest 汇总及原始JSON哈希。
- `evidence/data/m6/m2-regression.csv`、`m3-regression.csv`、`m4-regression.csv`、`m5-regression.csv`。
- `evidence/data/m6/m5-synthetic-smoke.json`：M5完整小型运行记录。
- 实现说明：`docs/M6_FAKE_PLC.md`；证据索引：`docs/REPORT_EVIDENCE.md`。
- Daily：[[daily/2026-09-05-M6-Fake-PLC离线验收]]。

## 结论与限制

M6 **PASS / DONE**。FIFO/ACK/队列满/丢包/延迟/断连/心跳/重放/M4 集成均有实际软件测试证据。未执行真实 PLC、M7 帧编解码、M8按钮/LED、M9自动重发及可靠性闭环。M6 验收当时 M3/M4/M5 仍为 DOING，三者后来于 2026-09-07 通过独立真实摄像头验收；其后 i.MX6ULL Controller 路线完成 M7/M8、M9 输入、输出和 PC vision E2E（TEST-008～011），但不改变本 M6 纯离线结论。去重历史与日志只在进程内保留且无上限，适用于有界测试；正式重启/持久化策略未定义。
