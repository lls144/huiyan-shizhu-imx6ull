---
title: TEST-009 M9 i.MX6ULL 实体 GPIO 三按键验收
date: 2026-09-10
tags: [慧眼识珠, M9, imx6ull, gpio-keys, linux-input, hardware]
status: PASS_INPUT_OUTPUT_PENDING
---

# TEST-009 M9 i.MX6ULL 实体 GPIO 三按键验收

## 范围、版本与环境

- 实现版本：`468f7bb223efe97af1a76198bde7dc237ba14b3e`；此前的 TCP/Python 3.7 基线为 `9906133a6db4e5391704fadf3c3b94b0b893b765`。
- Ubuntu 开发机：dev-host，仓库 `/home/developer/huiyan-shizhu`，分支 `imx6ull-development`；通过 USB Gadget Ethernet 访问实体板 `198.51.100.2`（SSH alias `imx6ull`）。
- 目标板：野火 i.MX6ULL，Debian GNU/Linux 10 (buster)，`armv7l`，kernel `4.19.35-imx6`，Python 3.7.3。
- 机械按键接线已经实体确认：KEY1/KEY2/KEY3 分别接 GPIO1_IO24/25/26，另一端共接 GND；VCC 未接。因此为被动、active-low 按键。
- `debian` 已加入 `input` 组；实际 `id` 包含 `106(input)`，以普通用户读取 `/dev/input/event*`。本记录不包含密码或其他认证材料。
- 本记录只验收 GPIO **输入**。GPIO 输出、LED/分支执行器与完整视觉闭环不在本次范围。

## 输入、配置与安全边界

项目独立 overlay `device/imx6ull/overlay/huiyan-keys.dts` 作为 `/usr/lib/linux-image-4.19.35-imx6/overlays/huiyan-keys.dtbo` 安装，并且只新增一条 `uEnv.txt` 配置：

```text
dtoverlay=/usr/lib/linux-image-4.19.35-imx6/overlays/huiyan-keys.dtbo
```

未修改主 DTB、U-Boot、官方 `imx-fire-key.dtbo`、任何现存 overlay 或 UART3 节点。重启前备份为 `/home/debian/huiyan-shizhu/overlay-staging/20260910-huiyan-keys/uEnv.txt.before-huiyan-keys-20260910T212854+0800`；回滚是从该备份恢复 `/boot/uEnv.txt`、移除上述新增行和项目 dtbo 后再重启。

只使用下列确认的未占用 PAD：

| key | PAD | GPIO | input code | debounce |
|---|---|---|---:|---:|
| KEY1 | `MX6UL_PAD_UART3_TX_DATA__GPIO1_IO24` | gpiochip0 line 24 | `KEY_PROG1` / 148 | 20 ms |
| KEY2 | `MX6UL_PAD_UART3_RX_DATA__GPIO1_IO25` | gpiochip0 line 25 | `KEY_PROG2` / 149 | 20 ms |
| KEY3 | `MX6UL_PAD_UART3_CTS_B__GPIO1_IO26` | gpiochip0 line 26 | `KEY_PROG3` / 202 | 20 ms |

`fsl,pins` 的 `0x0001b0b1` 启用输入路径和 HYS；PKE 启用 pull/keeper 电路，PUE 独立选择 pull（而不是 keeper），并选中内部 100 KOhm pull-up，匹配按键到 GND 的接线。`GPIO_ACTIVE_LOW` 只描述电气极性；Linux input 的按下事件仍为 value `1`，松开为 value `0`。UART3 overlay 保持禁用，项目未修改官方 `imx-fire-key.dtbo`。

## 实际步骤与结果

1. 重启后 SSH 恢复；`gpioinfo gpiochip0` 显示 lines 24/25/26 为 `Huiyan KEY1/2/3`、`input active-low [used]`。
2. `/proc/bus/input/devices` 显示 `Name="huiyan-keys"`，并有稳定路径 `/dev/input/by-path/platform-huiyan-keys-event`。本次启动时内核分配了 `event1`，但应用和采集程序不依赖该编号。
3. 使用 Python 3.7 标准库采集器按 `/sys/class/input/event*/device/name` 定位 `huiyan-keys`，读取 `struct input_event`。操作者依次实体按下并松开三键，板端原始记录为 `/home/debian/huiyan-shizhu/overlay-staging/20260910-huiyan-keys/huiyan-keys-input-events-20260910T214016+0800.log`。

| 验收项 | 预期 | 实际 | 结果 |
|---|---|---|---|
| KEY1 | code 148，press `1`、release `0` | `[1, 0]` | PASS |
| KEY2 | code 149，press `1`、release `0` | `[1, 0]` | PASS |
| KEY3 | code 202，press `1`、release `0` | `[1, 0]` | PASS |
| 机械消抖 | 单次操作无异常重复 | 共 6 条 EV_KEY：每键一按一松 | PASS |
| 不写死 eventX | 按名称发现设备 | 采集器和 Controller 均按 `huiyan-keys` 名称发现 | PASS |

4. 部署 `LinuxInputKeyInput` 后，以真实 TCP 从 dev-host 向 `198.51.100.2:9000` 依次入队 triangle 301、circle 302、rectangle 303。实体键使既有 FSM 完成：triangle 经 KEY1 → Branch1；circle 经 KEY1/KEY2 → Branch2；rectangle 经 KEY1/KEY2/KEY3 → Branch3。先前的非预期工位键产生 `wrong_station`，FIFO/FSM 状态未受损，随后正确操作完成出队，最终 `idle` 且 FIFO 长度 0。
5. 实体保持 KEY1 两秒：队列清空后仅产生一次 `empty`；快速双按 KEY1（triangle 401 已入队）产生一次 `sorted Branch1` 和随后一次 `empty`，未出现保持键或松开键的重复业务触发。
6. 随后再次从 dev-host 对实体板地址执行 TCP smoke：heartbeat、state、三类 enqueue、FIFO full、duplicate command ID、reset、FIFO order（该项是协议 `key_event` 注入）和 reconnect 共 10/10 PASS。此项与上面的原始 `/dev/input` 实体证据明确分开。

## 结论与限制

gpio-keys、内部上拉、active-low 电气极性、Linux input 事件和 Python 3.7 的标准库输入后端均已在实体 i.MX6ULL 与实体按键上通过。TCP、FIFO、FSM、重复命令和 reset 语义未改变。M9 GPIO **输入**为 PASS。本记录仅限输入；后续实体 LED 输出/按键闭环见 TEST-010，PC 摄像头到物理输出闭环见 TEST-011。自 TEST-011 起，批准的 i.MX6ULL M9 路线为 DONE；原始 PLC 路线仍独立 TODO。

同日完成了板载 red/green/blue LED 的只读方案审计：Branch1 = red、Branch2 = red + green、Branch3 = red + green + blue。审计时它不是 LED 输出测试；后续 helper、权限通道、systemd、1/2/3 通道观察、reset 全灭及实体输出验收已在 `TEST-010-M9-iMX6ULL实体LED闭环验收.md` 中独立记录。
