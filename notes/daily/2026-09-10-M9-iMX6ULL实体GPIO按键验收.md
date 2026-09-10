---
title: 2026-09-10 M9 i.MX6ULL 实体 GPIO 三按键验收
date: 2026-09-10
tags: [慧眼识珠, daily, M9, imx6ull, gpio-keys]
status: partial-complete
---

# 2026-09-10 M9 i.MX6ULL 实体 GPIO 三按键验收

今天在实体野火 i.MX6ULL 上完成 KEY1/KEY2/KEY3 的 `gpio-keys` 设备树接入和真实 Linux input 验证。确认的 GPIO1_IO24/25/26 对应 gpiochip0 lines 24/25/26；按键到 GND，采用内部上拉和 `GPIO_ACTIVE_LOW`。原始输入记录证实 148/149/202 均各有一次 press `1` 和 release `0`，没有异常重复。

`LinuxInputKeyInput` 仅使用 Python 3.7 标准库，按 `huiyan-keys` 设备名发现 input 节点而不固定 `eventX`。实体按键在真实 TCP 入队后的 FSM 流程中完成 triangle → Branch1、circle → Branch2、rectangle → Branch3；错误工位键保持状态，保持和快速重复操作未造成松开重复触发。随后真实 `198.51.100.2:9000` TCP smoke 仍为 10/10 PASS。

本次输入验证实现为 `468f7bb223efe97af1a76198bde7dc237ba14b3e`。GPIO 输出、分支执行器接线和完整物理闭环尚未验证，故 M9 保持 DOING。详见 [[../tests/TEST-009-M9-iMX6ULL实体GPIO按键验收]] 和 `docs/IMX6ULL_DEPLOYMENT.md`。
