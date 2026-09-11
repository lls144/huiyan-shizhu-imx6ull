---
title: 2026-09-10 i.MX6ULL M9 硬件进度收尾
date: 2026-09-10
tags: [慧眼识珠, daily, M7, M8, M9, imx6ull]
status: m9-doing
---

# 2026-09-10 i.MX6ULL M9 硬件进度收尾

> 后续更新（2026-09-11）：本页记录的是当日结束时的只读 LED 审计，因此其中“未实施/未测试”仅描述该时点。受限 helper、实体 RGB LED、实体按键/FSM/LED 闭环的后续 PASS 证据见 `notes/tests/TEST-010-M9-iMX6ULL实体LED闭环验收.md`；M9 整体仍因 PC vision 端到端未验收而保持 DOING。

## 今日已完成且有实机证据

- M7 PC–i.MX6ULL TCP 与 M8 FIFO/三级 Pipeline FSM：真实 `198.51.100.2:9000` smoke 10/10 PASS，覆盖 heartbeat、state、三类 enqueue、满队列、重复 ID、reset、顺序和 reconnect（TEST-008）。
- M9 部署：Debian 10、armv7l、kernel 4.19.35-imx6、Python 3.7.3；Controller 曾实际监听 `0.0.0.0:9000`，板端 compileall 通过。
- M9 输入：项目 `huiyan-keys.dtbo` 使用 GPIO1_IO24/25/26（gpiochip0 lines 24/25/26）及 UART3 TX/RX/CTS_B PAD，内部 100 KOhm pull-up、`GPIO_ACTIVE_LOW` 和 20 ms debounce。KEY1/2/3 的实际 input_event 分别为 148/149/202，各一次 press `1` 与 release `0`，无异常重复。
- `LinuxInputKeyInput` 按名称 `huiyan-keys` 动态定位设备，使用 Python 标准库 `os`、`select`、`struct`，不固定 `eventX`、不依赖 python-evdev。实体按键已完成 triangle → Branch1、circle → Branch2、rectangle → Branch3 的 FSM 闭环（TEST-009）。
- `debian` 的 `id` 已包含 `106(input)`，用于读取 `/dev/input/event*`；不记录认证材料。

## 只读审计，非输出验收

官方 `imx-fire-led.dtbo` 已提供板载 red / green / blue LED。推荐未来映射为 Branch1 = red、Branch2 = red + green、Branch3 = red + green + blue，以表示 1/2/3 灯。对应为 GPIO1_IO04 / gpiochip0 line 4、GPIO4_IO20 / gpiochip3 line 20、GPIO4_IO19 / gpiochip3 line 19，均 active-low，并通过 `/sys/class/leds/*/brightness` 暴露。

本项只完成映射、内核 ownership 和权限的只读审计。没有编写 LED helper、没有建立权限通道或 systemd 服务、没有写 LED brightness、没有观察任何灯、没有验证 reset 全灭。因此 LED 输出为 **NOT YET VERIFIED**，不是 PASS。

## 测试层级

1. Unit/integration：M7/M8/M9 相关 Python 回归。
2. TCP `key_event`：软件协议注入，不等同于物理按键。
3. 真实 i.MX6ULL TCP smoke：10/10 PASS。
4. 真实 Linux `input_event`：三键 press/release PASS。
5. 真实实体按键 FSM：三类路线 PASS。
6. 实体 LED 输出：未实施、未测试。
7. PC 视觉完整闭环：未测试。

## 下一次继续

1. 实现受限 LED output abstraction 与 root-owned 最小权限 helper。
2. systemd 部署并分别观察 red/green/blue。
3. 验证 Branch1/2/3 的 1/2/3 灯、timeout 自动全灭和 reset 立即全灭。
4. 验证实体按键加 LED FSM，再进行 PC vision → TCP → i.MX6ULL → 实体按键/分拣 → LED 完整验收。
5. M9 完成后才开始 M10 Qt LCD HMI。

M9 当前为 **DOING**。
