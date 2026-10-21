# 板端代码地图

[项目首页](../../README.md) · [架构](../../docs/ARCHITECTURE.md) · [运行指南](../../docs/GETTING_STARTED.md)

| 目录 | 责任 |
|---|---|
| `config/` | FIFO 容量、端口、Linux input 和 LED 输出配置 |
| `core/` | FIFO、命令、三工位 FSM、输入抽象；不依赖 Qt |
| `network/` | TCP JSON Lines 服务，连接协议与核心状态 |
| `output/` | 分流输出抽象、Unix socket 与受限 LED helper |
| `hmi/` | 状态视图、800×480 UI、触摸 Reset |
| `overlay/` | KEY 引脚 overlay 和来源注明的 pinfunc 常量 |
| `systemd/` | Controller、HMI、LED helper 服务定义 |
| `scripts/` | 构建、最小运行时传输、启动、只读检查与网络维护 |
| `tests/` | Linux 平台回归与 Python 3.7 静态语法兼容检查 |

Controller 不运行视觉推理。HMI 与 GPIO 依赖真实板端条件，Desktop 模式用于逻辑和协议复现。
