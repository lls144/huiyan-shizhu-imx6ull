# Adopt i.MX6ULL Embedded Linux Controller

Decision ID: `DECISION-IMX6ULL-001`

## Background

原控制端方案基于 S7-1200 PLC。

M1–M6 已完成 PC 视觉、事件生成、PySide6 GUI 和 Fake PLC 验证。Fake PLC 提供了语义命令、FIFO、ACK、心跳和故障注入的可测试模型，但不是实际控制器实现。

## Decision

指导教师允许采用 Linux 开发板替代 PLC；这是工程路线调整，不是对 PLC 方案或既有工作的否定。

后续控制端采用 i.MX6ULL Embedded Linux。

## Reason

1. 三级流水线逻辑更适合以显式、可测试的状态机实现。
2. 开发板提供 Linux、Ethernet、LCD 和 GPIO，能够覆盖控制器所需的软硬件边界。
3. 控制器可以提供 LCD 可视化交互，并保留 PC 端 PySide6 GUI 的现有能力。
4. 该路线避免 TIA Portal 和 PLC 专用环境对后续控制器开发的限制。

## Architecture

```text
PC Vision / GUI
  -> semantic command over TCP Ethernet
  -> i.MX6ULL Embedded Linux controller
  -> FIFO -> Pipeline FSM -> branch control
                   |             |
                GPIO keys      Qt LCD HMI
```

PC:

- OpenCV vision
- target lifecycle and semantic command generation
- PySide6 GUI
- TCP client

i.MX6ULL:

- TCP server
- FIFO
- Pipeline FSM
- GPIO keys
- Qt HMI
- heartbeat, ACK and status feedback

## Compatibility

原 PLC 分支、`plc/` 目录和历史实验记录完整保留，不删除、不继续作为当前控制器目标开发。

本独立仓库用于后续 Linux 控制器路线开发；M7–M12 的计划见 [ROADMAP.md](../ROADMAP.md)。
