# 正式演示 Runbook

正常演示不需要 Ubuntu 终端或 SSH。

## 演示前

1. 给 i.MX6ULL 上电，连接其指定 RJ45 演示口与 Windows Ethernet NIC。
2. 将 Ace Pro 2 以 USB Webcam 模式接到 Windows，确认使用 MJPG 1920×1080@30。
3. Windows 双击最终演示程序。程序读取 `pc/config/controller_windows_ethernet.json`，自动检查 camera 和 Controller。
4. GUI 显示 Camera、Board、Controller 正常后开始；LCD 应显示 HUIYAN HMI。

## 三类演示

1. 放 triangle，Windows GUI 识别并显示入队动画；按 KEY1，GUI 显示 Branch1 推杆/分流动画，板载 RGB 显示红色约一秒。
2. 放 circle；按 KEY1 后到 Station2，再按 KEY2；GUI 显示 Branch2 动画，RGB 显示红+绿约一秒。
3. 放 rectangle；按 KEY1、KEY2、KEY3；GUI 显示 Branch3 动画，RGB 三通道混色约一秒。
4. 可连续入队三种图形，确认 FIFO 3/3 和顺序；在错误工位按键应无分拣。
5. FIFO 非空时在 LCD 点击 RESET，确认 FIFO 0/3、IDLE、RGB off。

## 开发与故障恢复（非正常演示）

- Ubuntu maintenance SSH 使用 USB Gadget 后门：`ssh imx6ull`。
- 板端只读健康检查：`cd /home/debian/huiyan-shizhu && ./device/imx6ull/scripts/final_smoke_check.sh`。
- Controller/HMI/helper 状态分别用 `systemctl status huiyan-{controller,hmi,led-helper}.service --no-pager` 查看。
- HMI 黑屏时确认 `/dev/fb0` 与 HMI 服务；禁止设置 `QT_QPA_FB_HIDECURSOR=1`。
- 相机 timeout 时确认 Windows 使用 Ace Pro 2 对应的摄像头节点，关闭其他占用预览后重启演示程序。
- vendor Demo 不应启动：`ebf-qtdemo.service` 应保持 disabled，且不得删除厂商目录。

## 安全结束

结束 Windows 演示程序，确认 FIFO 空和 RGB off。需要关闭板端时，由维护人员执行 `sudo poweroff` 并等待系统关机完成。
