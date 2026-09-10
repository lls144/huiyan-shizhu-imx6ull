# i.MX6ULL Linux Deployment Preparation

状态：M9-A 部署准备。当前没有真实开发板；本页只说明可复现的 Ubuntu/Desktop 验证和未来部署步骤，不代表已完成板端、GPIO、LCD 或 ARM 验收。

## Desktop Ubuntu validation

在仓库根目录执行：

```bash
device/imx6ull/scripts/build.sh
python3 -m unittest pc.tests.test_controller_tcp pc.tests.test_controller_pipeline_tcp device.imx6ull.tests.test_controller_core device.imx6ull.tests.test_deployment
device/imx6ull/scripts/run.sh --mode desktop
```

Desktop 模式使用 `KeyboardKeyInput`。它用于测试事件注入，不访问 GPIO；网络监听端口、FIFO 容量和心跳间隔来自 `device/imx6ull/config/controller.json`。

## Future i.MX6ULL transfer

1. 在确认开发板网络地址、SSH 用户和目标目录后，在操作者终端设置 `IMX6ULL_HOST`；本仓库不提供默认 IP。
2. 运行 `device/imx6ull/scripts/deploy.sh`，它通过 SCP 传输当前 `device/` 与 `pc/` 源码树。
3. 通过 SSH 登录目标板，安装经确认的 Python 运行依赖，并从目标目录运行 `device/imx6ull/scripts/run.sh`。
4. 根据目标板的实际服务用户、工作目录与配置路径复制并填写 `device/imx6ull/systemd/huiyan-controller.service` 模板；由操作者审核后再安装或启用服务。

## GPIO replacement boundary

`GpioKeyInput` 读取 `gpio.key1`、`gpio.key2`、`gpio.key3` 配置。默认值均为 `null`；只要任一键未配置，`poll()` 返回 `NOT_CONFIGURED`，不会访问 Linux GPIO API。

开发板到位后，先根据原理图、设备树、内核 GPIO character-device 信息、电平有效性和去抖测试确认每一条 GPIO line。确认后才可填写配置并实现实际 GPIO 事件读取。`KeyboardKeyInput`、FIFO 与 Pipeline FSM 无需因该替换而重写。

## Systemd template

模板位于 `device/imx6ull/systemd/huiyan-controller.service`。其中尖括号字段必须替换为已核实值；本阶段不会复制、安装、启用或启动 systemd 服务。
