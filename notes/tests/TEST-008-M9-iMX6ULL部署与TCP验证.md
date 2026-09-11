---
title: TEST-008 M9 i.MX6ULL 部署与真实 TCP 验证
date: 2026-09-10
tags: [慧眼识珠, M9, imx6ull, hardware, tcp]
status: PASS_WITH_GPIO_PENDING
---

# TEST-008 M9 i.MX6ULL 部署与真实 TCP 验证

## 范围、版本与环境

- 实现版本：`9906133a6db4e5391704fadf3c3b94b0b893b765`；本测试后编写的记录不改变该已验证源码。
- Ubuntu 开发机：dev-host；仓库 `/home/developer/huiyan-shizhu`；分支 `imx6ull-development`。
- 目标：野火 i.MX6ULL，Debian GNU/Linux 10 (buster)，`armv7l`，内核 `4.19.35-imx6`，RAM 486 MiB，`/usr/bin/python3` 为 Python 3.7.3。
- 链路：USB Gadget Ethernet，Ubuntu → `198.51.100.2`；SSH alias `imx6ull`（BatchMode 公钥认证）。
- GPIO：`gpioinfo` 已安装，但项目配置三个 key 均为 `null`；本轮没有查看/请求任何 GPIO line，没有接线、按键或输出试验。

## 输入、步骤与预期

1. 运行 M7/M8 相关 unittest、Python 3.7 静态兼容检查和 build 编译检查；预期 FIFO、协议、FSM 原有语义不回归。
2. 使用 `device/imx6ull/scripts/deploy.sh` 的显式 SCP 17 文件清单部署到 `/home/debian/huiyan-shizhu/`；预期不含 PC 虚拟环境、缓存、测试、视觉/GUI、模型或数据。
3. 在板端运行 `python3 --version`、`python3 -m compileall /home/debian/huiyan-shizhu/`、直接入口 `--help`、协议/安全 GPIO 配置导入；预期 Python 3.7 可编译和导入，GPIO 状态为 `NOT_CONFIGURED`。
4. 启动 `/usr/bin/python3 device/imx6ull/controller_main.py --mode imx6ull --config device/imx6ull/config/controller.json --host 0.0.0.0`；预期监听 9000。
5. 从 Ubuntu 运行 `python3 device/imx6ull/scripts/tcp_smoke_test.py --host 198.51.100.2 --port 9000 --timeout 5`；预期真实板端服务完成全部协议向量。

## 实际结果

| 项目 | 实际 | 结果 |
|---|---|---|
| 本地相关回归 | 24 unittest passed in 1.399s；另 `build.sh` 的兼容检查 2 passed | PASS |
| Python 3.7.3 | `Python 3.7.3` | PASS |
| board `compileall` | 全部 17 个运行文件编译；复查 `compileall -q` exit 0 | PASS |
| 直接入口 / 导入 | 从部署根目录 `controller_main.py --help` PASS；关键导入 PASS | PASS |
| GPIO 安全状态 | `{'key1': None, 'key2': None, 'key3': None}`，`NOT_CONFIGURED` | PASS（未访问硬件） |
| TCP listener | PID 2011，`ss -ltn` 为 `0.0.0.0:9000` | PASS |
| heartbeat / state | `ack/alive`；空队列、capacity=3、idle | PASS |
| 三类入队 / full / duplicate | triangle/circle/rectangle 依次 accepted；第4项 `queue_full`；ID 101 `duplicate` | PASS |
| reset | ACK reset 后 FIFO empty/idle | PASS |
| FIFO 顺序 / FSM | ID 201 triangle 先 Branch1，ID 202 circle 后经 KEY1/KEY2 至 Branch2 | PASS |
| disconnect/reconnect | 关闭第一个 TCP socket 后新连接 heartbeat `ack/alive` | PASS |

实机测试时间：板端 2026-09-10 20:27:52 +08:00；PC 复核 2026-09-10 20:27:54 +08:00。完整命令、运行清单和逐项响应见 `docs/IMX6ULL_DEPLOYMENT.md`；该文档是本次文本证据位置。

## 结论与限制

软件 Controller 的 Python 3.7 部署、导入、编译和真实网络 TCP 验收通过。此记录本身不证明任何实体按键、GPIO 输入、GPIO 输出或接线；这些证据后来分别由 TEST-009、TEST-010 和 TEST-011 补齐。2026-09-11 起，批准的 i.MX6ULL M9 路线已由 TEST-011 标记 DONE；原始 PLC 路线仍独立 TODO。
