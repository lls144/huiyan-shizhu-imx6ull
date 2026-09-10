# M6 Fake PLC 离线模拟器

M6 提供确定性、可脚本化的软件 PLC 实验台。所有结果是 **Fake PLC / software simulation / no physical PLC**；无需摄像头或实验室。本阶段只验收模拟器，不关闭任何真实 PLC、通信或摄像头需求。

## 使用

在仓库根目录运行：

```powershell
.\.venv\Scripts\python.exe -m simulator --scenario all
.\.venv\Scripts\python.exe -m simulator --scenario ack_loss
.\.venv\Scripts\python.exe -m pytest pc/tests/test_m6_simulator.py -q
```

默认 JSON/CSV 写入被忽略的 `output/m6/`。用 `--output-json`、`--output-csv` 指定路径，`--config` 指定 JSON 配置。场景均通过且确定性重放一致时退出 0，预期不符时退出 1；非法 CLI/配置以非零退出。正式精选证据在 `evidence/data/m6/`。

## 架构与接口

```text
M4 VisionEvent → CommandAdapter → SemanticCommand
→ InMemoryLink → FaultInjector → FakePLC → FIFO / SemanticResponse
```

| 模块 | 职责 |
|---|---|
| `simulator/models.py` | immutable command/response、状态枚举、配置校验、M4 adapter |
| `simulator/fake_plc.py` | FIFO、设备侧幂等、心跳状态、统计和结构化日志 |
| `simulator/link.py` | 虚拟时钟、单次故障计划、异步 exchange、断连与迟到响应 |
| `simulator/scenarios.py` | 16 个场景、独立 expected/actual、真实 M4 状态管理器集成 |
| `simulator/reporting.py` | JSON/CSV、Git/Python/源码哈希、重放、轻量 benchmark |
| `simulator/__main__.py` | headless CLI |

`CommandAdapter.adapt(event)`：仅 OBJECT_ENTER 分配递增 ID（1 起）；OBJECT_EXIT 返回 None 且不消耗 ID。保留 source_event_id/source_object_id。未知事件种类抛 ValueError，非法 shape 传至 FakePLC 明确拒绝。adapter 不负责重复播放同一 ENTER 的去重；上游生命周期由 M4 管理，端到端可靠性由 M9 设计。

`SemanticCommand`：command_id、shape、source_event_id、source_object_id；这是语义 ID，不是最终帧序号。`SemanticResponse`：command_id、status、queue_length、message。状态为 ACCEPTED、QUEUE_FULL、INVALID、DUPLICATE、OFFLINE、TIMEOUT。TIMEOUT/OFFLINE 可由调用方生成，其 queue_length 是实验台观察值，不冒充线上反馈。

`FakePLC.snapshot()` 返回可序列化副本：online、queue、capacity、queue_length、empty/full、accepted_command_ids、last_heartbeat_ms、heartbeat_state/alive、accepted/rejected/duplicate/consumed_count。`queue` 属性为不可变 tuple；内部命令为 frozen dataclass。

## FIFO 与设备侧重复保护

合法命令在设备 online、ID/来源 ID 合法、shape 属于 triangle/rectangle/circle、未重复、队列未满时入队。ID 必须是正整数，bool 不作为整数接受。满队列拒绝且不修改已有内容，不登记被拒命令为已接受，释放容量后可手动重新发送。

`consume_one()` 仅模拟软件消费队头，返回命令；空队列或设备 offline 返回 None。它不是实际按钮，不实现 LED。队列严格 FIFO。相同 ID 和完整 payload 再次到达返回 DUPLICATE；同 ID 改写 shape/来源字段返回 INVALID。重复检查先于满队列检查；已消费 ID 仍保留。断连/重连保留 FIFO 和去重历史，设备新实例才清空。

## 配置与时间边界

`simulator/config/fake_plc.json`：

| 参数 | 默认 | 校验/含义 |
|---|---|---|
| capacity | 3 | 正整数；模型允许 1/2 用于边界测试，全套三目标验收需 ≥3 |
| heartbeat_interval_ms | 1000 | 正整数，严格小于 timeout；仅场景输入间隔 |
| heartbeat_timeout_ms | 2000 | 正整数；达到 last + timeout 即 lost |
| response_timeout_ms | 100 | 正整数；到达截止时刻即 TIMEOUT |

没有实际 scheduler，没有 sleep。`VirtualClock.advance(N)` 推进整数虚拟毫秒，禁止负数、浮点和 bool；按时间及插入序号稳定执行回调。ACK 必须在 deadline **之前**送达；恰好 deadline 的 ACK 算迟到。超时回调在请求发出时登记，因此一次大幅推进也不会把迟到 ACK 当成功。迟到 ACK 留在 exchange.late_response 并记 LATE_ACK，不改写原 TIMEOUT。

心跳初始 never_received；成功接收转 healthy，达到阈值转 lost，再收到则恢复 healthy。日志同时保存观察时刻与精确 transition_time_ms、last_heartbeat_ms、threshold_ms。connected（链路）、online（设备）与 heartbeat_state 是独立维度。1 s / 2 s 只模拟任务语义，真实链路时序与全灯报警仍由 M9/M8 验证。

## 故障计划与可观察操作

```python
from simulator.fake_plc import FakePLC
from simulator.link import VirtualClock, InMemoryLink, FaultInjector, Fault
from simulator.models import SemanticCommand

clock = VirtualClock()
plc = FakePLC(clock)
faults = FaultInjector([Fault("response", "drop", command_id=1)])
link = InMemoryLink(plc, faults)
exchange = link.send(SemanticCommand(1, "circle"))
clock.advance(100)
assert link.poll(exchange).status == "TIMEOUT"
assert len(plc.queue) == 1
assert link.send(SemanticCommand(1, "circle")).response.status == "DUPLICATE"
```

Fault(channel, action, command_id=None, delay_ms=0)：channel 为 request/response/heartbeat，action 为 drop/delay。按计划顺序消费首条匹配规则，None 匹配下一条该通道消息；已注入规则单列记录。delay 必须为非负整数，drop 不允许附带延迟，heartbeat 无 command ID。重复暂停心跳可停止调用或显式列出多次 heartbeat drop。没有随机验收。

`send()` 返回 Exchange（sent_ms/deadline_ms/response/completed_ms/late_response）；`poll()` 查看结果；`advance()` 推进时钟；`heartbeat()` 显式投递。`clock.schedule(N, link.disconnect)` 可安排断连。断连取消旧连接代际尚未送达的请求/响应，重连不会恢复这些旧投递；已经入队的内容保留。链路离线发送立即 OFFLINE。设备 offline 拒收，link 仍可 connected。

结构化日志字段：step、virtual_time_ms、direction、command_id、action、status、queue_length、fault，附必要 command/心跳详情。覆盖 SEND、PLC_ACCEPTED、请求/响应丢弃及延迟、ACK_RX/LATE_ACK、TIMEOUT、DISCONNECT/RECONNECT、DEQUEUE、HEARTBEAT_RX/TIMEOUT。JSON 留全部小型场景步骤与最终设备状态；CSV 每行一个场景。

## 16 个验收场景

normal_fifo、dequeue_order、queue_full、full_recovery、invalid_shape、duplicate、request_loss、ack_loss、delayed_ack、timeout、disconnect、reconnect、heartbeat_normal、heartbeat_lost、heartbeat_recovery、m4_integration。

每场景使用全新设备/时钟。默认顺序 triangle → rectangle → circle，容量 3。正常延迟为 50 ms，超时延迟为 101 ms，对比 100 ms 截止。request_loss 不入队；ack_loss 已入队，手动重发后仍一项。M4 集成使用实际 EventConfig、Detection、ObjectStateManager、VisionEvent：连续存在 22 帧，再缺失 4 帧，产生三 ENTER 和三 EXIT；只有三个命令入队。它是确定性检测序列，不是摄像头证据。

## 验收证据与边界

TEST-007：`notes/tests/TEST-007-M6-Fake-PLC模拟器验收.md`。JSON 含 source_type、Git HEAD/origin、dirty、Python、配置、源码哈希、expected/actual、passed、输入事件、步骤、最终状态、故障与 benchmark。核心结果两次运行逐字段相等；性能时间只作元数据。benchmark 250 轮共 1500 次显式操作，含发送、重复、消费、心跳、请求丢弃和时钟推进。

后续 i.MX6ULL Controller M7 已以真实 TCP transport + codec 替换 InMemoryLink，并保留 command/response 语义边界；当前共享 PLC 接口仍未冻结，不定义 PLC 字节帧、地址、编码或物理协议。i.MX6ULL Controller M8 FIFO/按键 FSM 已完成，但真实 PLC FIFO、按钮、LED、I/O、TIA 工程仍待完成。M9 可复用故障计划；实体 LED 输出、heartbeat scheduler、retry、超时/满队列恢复与端到端去重仍待验证。

已知限制：单进程单线程测试模型；去重历史和事件日志在实例生命周期内无限保留，适用于有界测试，不宣称生产级容量；无持久化/掉电恢复、自动重发、真实电气/LED、网络或 PLC 扫描周期仿真；无 GUI 集成。M3/M4/M5 已于 2026-09-07 另用真实摄像头完成验收，但该结果与 M6 的纯离线结论相互独立。
