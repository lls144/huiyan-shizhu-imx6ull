---
title: TEST-010 M9 i.MX6ULL 实体 LED helper 与按键/FSM 闭环验收
date: 2026-09-11
tags: [慧眼识珠, M9, imx6ull, led, systemd, unix-socket, hardware]
status: PASS_OUTPUT_SUBSCOPE
---

# TEST-010 M9 i.MX6ULL 实体 LED helper 与按键/FSM 闭环验收

## 范围、版本与环境

- 实现版本：`a8b54179ef16d85946407ae86d8cee9661b3744d`。
- dev-host Ubuntu 经 USB Gadget Ethernet 对实体板 `198.51.100.2:9000` 执行 TCP 测试；目标为野火 i.MX6ULL、Debian 10、`armv7l`、kernel `4.19.35-imx6`、Python 3.7.3。
- 本次只验收板载 RGB LED、helper 与实体按键/FSM 闭环；不构成 PC 视觉到 LED 的完整端到端验收。

## 权限和安全边界

- 未修改 `uEnv.txt`、`imx-fire-led.dtbo`、主 DTB 或 LED GPIO 的内核 ownership；helper 只写现有 `/sys/class/leds/{red,green,blue}/brightness`。
- `huiyan-led-helper.service` 以 root 启动固定 Python module；代码在 `/opt/huiyan-led-helper`、配置在 `/etc/huiyan-led-helper.json`，均为 root-owned。Controller 以普通用户 `debian` 运行，PID 2022，监听 `0.0.0.0:9000`。
- Unix socket 为 `/run/huiyan-led/helper.sock`；观察到目录 `0750 root:huiyan-led`、socket `0660 root:huiyan-led`。`debian` 属于 `huiyan-led` 并可连接 socket。
- 协议仅接受 Branch1/2/3 或 OFF；不接受 GPIO、brightness 或任意文件路径。非法 `gpio` 消息未改变 LED 状态。
- 初版 unit 的 `ProtectSystem`/`PrivateTmp` 等 mount-namespace isolation 在该板的 Debian 10 kernel 上导致 `status=226/NAMESPACE`，helper 未运行。兼容 unit 删除这些内核不支持项，保留 root-owned 固定代码、`NoNewPrivileges`、`CAP_CHOWN CAP_DAC_OVERRIDE`、`UMask=0007` 与 `RestrictAddressFamilies=AF_UNIX`；修复后 service active 且 journal 无异常。

## 实际步骤和结果

1. 启动 helper 后，普通 `debian` 连接 socket 成功；red/green/blue 初始 brightness 都为 0。
2. 直接协议测试：Branch1 = red 255；Branch2 = red/green 255；Branch3 = red/green/blue 255。每次约 1 秒自动回到 0。OFF 与非法消息均保持全灭。操作者确认单个 RGB 封装的实际颜色依次为红、黄绿色、蓝白，符合通道组合。
3. 板端运行时配置才启用 `led_output.enabled=true`；仓库默认配置保持 false。普通用户 Controller 成功监听 `0.0.0.0:9000`，helper active。
4. 从 dev-host 对 `198.51.100.2:9000` 测试 heartbeat、state、enqueue circle 9101、错误 `KEY2`、普通 `KEY1` Station1→Station2 与 reset。错误工位、enqueue、普通移动均未点灯，reset 返回 empty/idle 且三灯为 0。
5. triangle 9201：实体 KEY1 使 Controller 记录 `sorted Branch1`、FIFO 长度 0；操作者观察红色约一秒后熄灭。
6. circle 9202：实体 KEY3 记录 `wrong_station` 且不点灯；KEY1 移至 Station2；实体 KEY2 raw input 为 code 149、press 1/release 0，并完成 `sorted Branch2`。操作者观察黄绿色约一秒后熄灭。
7. rectangle 9203：KEY1 移至 Station2；错误工位键不改变队列；实体 KEY2 raw code 149、press 1/release 0 后移至 Station3；实体 KEY3 raw code 202、press 1/release 0 后完成 `sorted Branch3`。LED 采样在 12616 ms 记录 red/green/blue 全部 255，在 13612 ms 记录全部 0，持续约 996 ms。操作者观察蓝白约一秒后熄灭。
8. Branch3 后 TCP `pipeline_state` 为 empty/idle；真实 TCP reset ACK 后仍为 empty/idle、三灯全 0，helper active。

## 验收矩阵

| 项目 | 实际结果 | 结论 |
|---|---|---|
| 最小权限 | root helper + ordinary `debian` Controller，0660 group socket | PASS |
| Branch1 | 实体 KEY1 → Branch1 → red → 自动全灭 | PASS |
| Branch2 | 错误键无灯；实体 KEY1/KEY2 → Branch2 → red+green → 自动全灭 | PASS |
| Branch3 | 实体 KEY1/KEY2/KEY3 → Branch3 → three channels → 约 996 ms 后全灭 | PASS |
| 非分拣无输出 | enqueue、错误工位、Station move 不点灯 | PASS |
| reset | TCP reset 后 FIFO idle/empty、三灯全 0 | PASS |
| TCP/helper 存活 | `0.0.0.0:9000`、helper active、socket ordinary-user access | PASS |

## 结论与限制

M9 的板端输出子范围与实体按键/FSM/LED 闭环为 PASS。本记录形成时 PC 视觉事件到实体按键/LED 的完整端到端流程尚未实测。后续 TEST-011 已完成该缺口，因此 i.MX6ULL M9 路线现为 DONE；本记录没有提前标记后续 M10 工作。
