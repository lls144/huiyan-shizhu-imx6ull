---
title: TEST-014 Windows RJ45 Python ControllerClient 协议冒烟
date: 2026-09-11
tags: [慧眼识珠, Windows, RJ45, TCP, ControllerClient, hardware]
status: pass
---

# TEST-014 Windows RJ45 Python ControllerClient 协议冒烟

## 目的与边界

在 Windows 11 上用仓库既有 `pc.communication.controller_client.ControllerClient`，经正式 RJ45 演示地址访问真实 i.MX6ULL Controller。此记录只覆盖 connect、`heartbeat`、`pipeline_state` 与 `reset` 的最小 Python 协议路径；未启动或修改 GUI，未使用 mock server，未使用 USB Gadget `198.51.100.2`。

它不替代摄像头、GUI、实体按键、LED 或 LCD 验收。没有注入丢包/ACK 丢失，故不把本次结果表述为“重试路径已在实体网络故障下验证”。

## 环境

- Windows Ethernet: `203.0.113.1/24`。
- i.MX6ULL Controller: `203.0.113.2:9000`。
- Profile: `pc/config/controller_windows_ethernet.json`，`connect_timeout=1.0`、`ack_timeout=1.0`、`reconnect_delay=0.1`、`max_retries=2`。
- Python environment: repository `.venv`（OpenCV、PySide6、numpy、pytest 已安装）；本测试只使用标准库和已有 PC communication 模块。

## 步骤

先前已由操作者确认 `ping 203.0.113.2` 与 `Test-NetConnection 203.0.113.2 -Port 9000` 通过。随后在仓库根目录运行：

```powershell
& .\.venv\Scripts\python.exe scripts\windows_controller_protocol_smoke.py
```

脚本默认加载正式 Windows profile，调用 `ControllerConnectionConfig.make_client()` 创建现有 `ControllerClient`；没有自行创建 socket client 或绕过 `pc/communication/protocol.py`。

## 实际结果

`connect` PASS：`203.0.113.2:9000`。

`heartbeat` 在 46.0 ms 返回：

```json
{"request_id":"bf1cbae5-553b-4427-9995-db2d2769f2a9","status":"alive","type":"ack","version":1}
```

`pipeline_state` 在 16.0 ms 返回：

```json
{"pipeline_state":{"capacity":3,"empty":true,"front":null,"full":false,"last_key":null,"last_sort":null,"last_transition":"idle","queue":[],"queue_length":0,"station":"idle"},"request_id":"3eeb258e-5a4d-438a-bac5-2f10a011c3bf","state":"idle","type":"pipeline_state","version":1}
```

`reset` 在 31.0 ms 返回 ACK，且返回的快照仍为空队列、`idle`：

```json
{"pipeline_state":{"capacity":3,"empty":true,"front":null,"full":false,"last_key":null,"last_sort":null,"last_transition":"idle","queue":[],"queue_length":0,"station":"idle"},"request_id":"476e43bd-02d6-4ffa-9256-2d4e79d8b09a","status":"reset","type":"ack","version":1}
```

本次没有 `ControllerTimeout`。配置的 `max_retries=2` 保持生效，但所有请求均在首次 ACK timeout 前收到回复；`ControllerClient` 公共 API 不暴露尝试次数，且本测试没有故意制造网络故障，因此“重试实际触发”是 **未测试**，不是 PASS 结论。

## 结论

Windows → RJ45 → i.MX6ULL 的最小 Python protocol smoke 为 **PASS**。`pc/config/controller_windows_ethernet.json` 已为可验证的正式 Windows 路径；`pc/config/controller_ubuntu_usb_maintenance.json` 未读取、未修改，仍保留为 Ubuntu USB 维护配置。
