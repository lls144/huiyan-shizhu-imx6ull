# 慧眼识珠最终产品规格

## 目标

在 Windows 11 上展示 Ace Pro 2 对 triangle、circle、rectangle 的实时识别，并通过 RJ45 Ethernet 将确认的 `OBJECT_ENTER` 发送至 i.MX6ULL。控制器按 FIFO 和三级 FSM 接收实体 KEY1/2/3，输出 Branch1/2/3；板载 RGB LED 和 LCD HMI 反馈状态，Windows GUI 用动画表示分流动作。

## 责任边界

| Component | Responsibility |
|---|---|
| Windows PC | camera, OpenCV recognition, lifecycle events, TCP client, presentation GUI/animation |
| i.MX6ULL Controller | TCP server, FIFO, FSM, physical key input, branch event dispatch |
| LED helper | restricted root-only Linux LED-class output |
| LCD HMI | localhost TCP state display and existing RESET API only |
| Ubuntu | development, deployment, SSH and maintenance only |

## Functional acceptance

1. Each confirmed shape produces one accepted TCP enqueue.
2. FIFO capacity is three and preserves order.
3. triangle follows KEY1 → Branch1; circle follows KEY1 → KEY2 → Branch2; rectangle follows KEY1 → KEY2 → KEY3 → Branch3.
4. Branches use logical 1/2/3 RGB channels for approximately one second, then return off.
5. HMI displays online status, FIFO, front object, station, last sort, counters, key state and RESET.
6. Controller restart does not crash HMI; it visibly transitions OFFLINE then ONLINE.
7. After a real power cycle, helper, Controller and HMI recover automatically; `final_smoke_check.sh` is PASS.

## Safety and constraints

- Controller and HMI run as ordinary `debian`; only the fixed-protocol LED helper runs as root.
- HMI never accesses GPIO, LED brightness, input events or Controller internals.
- USB Gadget maintenance networking remains intact.
- The normal demonstration uses Windows↔RJ45; no terminal is required during the normal flow.
- `QT_QPA_FB_HIDECURSOR=1` must not be set on the board because it causes a native Qt/linuxfb crash.
