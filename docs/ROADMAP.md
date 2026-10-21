> 公开整理说明：以下保留开发时约定与阶段记录。当前入口及验证范围见 [文档索引](INDEX.md)；历史 TODO 不代表后续没有实现，需求目标也不自动等于验收通过。

# 产品路线图

当前产品闭环：

```text
Windows PC Vision -> Ethernet TCP -> i.MX6ULL Controller
-> FIFO / three-station FSM -> physical keys -> RGB indication
-> LCD HMI -> Windows sorting animation
```

| Milestone | Scope | Status |
|---|---|---|
| M3 | Shape recognition | DONE |
| M4 | Object lifecycle / `OBJECT_ENTER` event | DONE |
| M5 | Windows visual control interface baseline | DONE |
| M7 | TCP Controller protocol | DONE |
| M8 | FIFO and three-station pipeline FSM | DONE |
| M9 | i.MX6ULL physical keys, RGB output and vision-to-board loop | DONE |
| M10 | i.MX6ULL LCD Qt HMI and Goodix touch RESET | DONE |
| Final demo | Windows Ethernet profile, packaging and live sorting animation | DOING |

## Current delivery focus

1. Use the Windows Ethernet profile at `pc/config/controller_windows_ethernet.json`.
2. Complete Windows-side RJ45 connectivity and GUI animation validation; the
   board `eth1` persistent profile is already verified.
3. Keep USB Gadget `198.51.100.2` as the Ubuntu maintenance path.
4. Finish the Windows presentation animation without changing the verified Controller, FIFO, key, LED or HMI semantics.
