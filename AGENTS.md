# 慧眼识珠最终产品协作规则

## 产品边界

本仓库的唯一产品链路为：

`Windows 11 / Ace Pro 2 -> OpenCV vision -> Ethernet TCP -> i.MX6ULL -> FIFO / 3-station FSM -> physical KEY1/2/3 -> RGB LED + LCD HMI`

Windows 是老师演示端；i.MX6ULL 是实体控制器；Ubuntu 只用于开发、部署、SSH 与维护。PC GUI 用推杆/分流动画表达分拣动作，不需要电机。板端不运行 OpenCV 或 AI。

开始每次工作前阅读本文件、`docs/PROJECT_SPEC.md` 与当前测试记录。真实硬件结论必须有真实记录；未执行时写 `TODO`，不得伪造通过。

## 已验证基线

- M3、M4、M5、M7、M8、M9、M10 均为 DONE，证据见 TEST-003～006、TEST-008～013。
- i.MX6ULL：Debian 10、armv7l、Python 3.7.3；Controller/HMI 为普通 `debian` systemd 服务，LED helper 为受限 root 服务。
- LCD：800×480、PySide2 5.11.2 / Qt 5.11.3、linuxfb；Goodix touch 由启动脚本动态发现。
- USB Gadget `198.51.100.2` 是维护后门，任何网络工作不得删除、替换或抢占它。

## 工程规则

- 保持视觉、TCP、Controller Core、Linux input、LED helper 和 HMI 解耦；不得改变 FIFO、FSM、KEY mapping 或 TCP 既有语义来迁就 UI。
- 配置中的设备、地址、端口、ROI 和超时不得散落硬编码。
- 网络、boot、overlay、GPIO 或系统服务变更前必须先只读审计；网络变更必须备份、幂等、可回滚，且不能影响 USB Gadget。
- 不提交 `.venv`、缓存、运行输出、视频、原始大文件、密码或密钥。
- 每次实体测试更新 `notes/tests/` 和 `docs/REPORT_EVIDENCE.md`；每个记录包含环境、步骤、实际结果和证据边界。
- 小步提交并推送当前功能分支；不重写历史、不自动合并 `master`。
