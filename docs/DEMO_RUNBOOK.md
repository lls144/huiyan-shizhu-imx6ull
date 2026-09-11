# 慧眼识珠现场演示 Runbook

适用范围：已部署的批准 i.MX6ULL Controller 路线。PC 负责视觉；i.MX6ULL 负责控制、实体按键、RGB LED 和 LCD HMI。原始 PLC 路线仍独立 TODO，不在本 runbook 内。

## 上电与自检（约 1 分钟）

1. 接通 i.MX6ULL 电源，等待 Debian 完成启动；确认 USB Gadget Ethernet 已连接。
2. Ubuntu 执行 `ssh imx6ull`，确认可登录。
3. 在板端执行：

   ```bash
   cd /home/debian/huiyan-shizhu
   ./device/imx6ull/scripts/final_smoke_check.sh
   ```

   仅当输出 `OVERALL ............ PASS` 时继续。该脚本只读取状态：不会 reset、入队、按键或点灯。
4. LCD 应显示 HUIYAN HMI；不要手工运行第二个 HMI。服务日志可用 `journalctl -u huiyan-hmi.service -n 50 --no-pager` 查看。

## Ubuntu 视觉检查

1. 确认 Ace Pro 2 是 `/dev/video2`，不要使用默认 camera index 0。
2. 使用仓库已有 Ubuntu `.venv`，以 `MJPG`、1920×1080、30 fps 启动既有 M3/M4/vision bridge 入口；保持既有 ROI、阈值和算法配置，不在现场临时修改。
3. 视觉端收到 Controller 的 `accepted` 前，不按实体键。

## 三类形状演示

每次只摆放一个目标，确认 PC 视觉输出正确标签且 TCP 返回 `accepted`，再操作板端实体键。

| 目标 | 实体按键顺序 | 预期 |
|---|---|---|
| triangle | KEY1 | Branch1；RGB 红约 1 秒后灭；FIFO 出队 |
| circle | KEY1，再 KEY2 | Station2 时不亮；Branch2 为红+绿约 1 秒后灭；FIFO 出队 |
| rectangle | KEY1，再 KEY2，再 KEY3 | Station2/3 时不亮；Branch3 三通道混色约 1 秒后灭；FIFO 出队 |

观察 LCD：FIFO、front、Station、Last Sort、session counters 与最近有效 key 应同步更新。

## FIFO、错误按键与触摸 RESET

1. 连续完成 triangle、circle、rectangle 三个真实视觉 `accepted`，LCD/FIFO 应显示 `3/3`，顺序为 triangle → circle → rectangle。
2. 在 circle 的 Station1 故意按 KEY3：station、FIFO、counter 与 LED 应保持不变。
3. FIFO 非空时，在 LCD 触摸 **RESET**。预期 FIFO `0/3`、Pipeline IDLE、RGB 全灭，页面仍是 HUIYAN。

## 快速恢复

| 现象 | 只做下列最小检查/恢复 |
|---|---|
| 相机 timeout | 确认 `/dev/video2`、USB Webcam 模式和 `v4l2-ctl --list-devices`；关闭占用相机的 preview 后按既有视觉命令重新打开。 |
| Controller 未启动 | `systemctl status huiyan-controller.service --no-pager`；`sudo systemctl restart huiyan-controller.service`。 |
| HMI 黑屏 | `systemctl status huiyan-hmi.service --no-pager`；确认 `/dev/fb0`；`sudo systemctl restart huiyan-hmi.service`。禁止设置 `QT_QPA_FB_HIDECURSOR=1`。 |
| LED helper failed | `systemctl status huiyan-led-helper.service --no-pager`；`sudo systemctl restart huiyan-led-helper.service`。不要直接写 LED brightness 或抢 GPIO。 |
| OTG 地址/接口变化 | Ubuntu 执行 `ip addr`，确认 USB Gadget 链路与 `198.51.100.2`；恢复物理 USB/供电后重试 SSH。 |
| Debian 无法联网 | 本路线只要求 PC 与板端 OTG 链路；先检查 USB Gadget Ethernet、`ip addr` 和 `ping 198.51.100.2`，不为演示升级系统。 |
| 野火 Demo 覆盖 LCD | `systemctl is-enabled ebf-qtdemo.service` 应为 `disabled`；确认无 `/usr/local/qt-app/App` 进程。不要删除厂商目录。 |

## 安全结束

结束视觉程序后，确认 FIFO 为空、RGB 已灭，再在板端执行：

```bash
sudo poweroff
```

等待系统断电完成后再断开电源或 USB。不要强行断电正在写入文件的系统。
