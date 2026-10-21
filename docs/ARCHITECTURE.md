# 控制权留在控制器

[首页](../README.md) · [文档索引](INDEX.md)

## 平台与模块

正常演示端为 Windows 11 + Insta360 Ace Pro 2；Ubuntu 用于开发维护。板端为 i.MX6ULL / Debian 10 / ARMv7，现场 Python 3.7.3。PC 用 OpenCV 处理图像，板端只处理控制、Linux I/O 和 HMI。

TCP 使用 UTF-8 JSON Lines，以换行界定报文，协议版本为 1，单条最大 16 KiB。消息覆盖 enqueue、heartbeat、key_event、pipeline_state 和 reset。FIFO 接受合法命令后，客户端回读控制状态；PC 列表里的检测目标不等于已入队物料。

## 三工位的规则

| 形状 | 推进顺序 | 分流 |
|---|---|---|
| triangle | KEY1 | Branch1 |
| circle | KEY1 → KEY2 | Branch2 |
| rectangle | KEY1 → KEY2 → KEY3 | Branch3 |

容量为 3；只有队首响应当前工位的按键，错误工位输入不改变队列。PC 监视器和 LCD HMI 都读取 `pipeline_state`。分拣序号用于避免界面重复统计；Reset 通过控制器协议清空状态，然后显示回读结果。

这与 PLC 版本的 triangle / rectangle / circle 对应 1 / 2 / 3 灯不同，不能直接复用其形状到工位映射。

## Linux I/O 与界面

实体按键由 Linux input 设备读取；设备树 overlay 定义 KEY 引脚。Controller 和 HMI 以普通用户运行，RGB 写入由单独的 LED helper 承担，通过受限 Unix socket 接口调用。

HMI 使用 PySide2 / linuxfb，800×480 LCD，启动脚本动态找到 Goodix input 设备。Controller 是状态来源，界面按连接状态显示 OFFLINE / ONLINE，并在恢复后重新同步。此板的 Qt 5.11 环境不能设置 `QT_QPA_FB_HIDECURSOR=1`：实际调试中会在事件循环发生原生崩溃。

[控制器入口](../device/imx6ull/controller_main.py) · [FSM](../device/imx6ull/core/pipeline.py) · [HMI](../device/imx6ull/hmi) · [服务定义](../device/imx6ull/systemd)
