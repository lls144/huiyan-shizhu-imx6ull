# DECISION-IMX6ULL-001

## Background

本项目原控制端方案基于 PLC。

M1-M6 已完成 PC 视觉、事件生成、GUI 和 Fake PLC 验证。

## Decision

指导教师允许采用 Linux 开发板替代 PLC。

后续控制端采用 i.MX6ULL Embedded Linux。

## Architecture

PC:
- OpenCV vision
- PySide6 GUI
- TCP client

i.MX6ULL:
- TCP server
- FIFO
- Pipeline FSM
- GPIO keys
- Qt HMI

## Compatibility

原 PLC 分支和历史实验记录保留。

新仓库用于 i.MX6ULL 控制器路线开发。
