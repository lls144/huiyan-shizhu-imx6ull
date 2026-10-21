# 运行与板端部署

[首页](../README.md) · [文档索引](INDEX.md)

## 1. 离线控制器

在 Linux 中使用 Python 3，仓库根目录运行：

```bash
python3 device/imx6ull/controller_main.py --mode desktop --host 127.0.0.1
python3 -m unittest discover -s device/imx6ull/tests -p 'test_*.py'
bash device/imx6ull/scripts/build.sh
```

第一条是常驻进程，测试在另一个终端执行。默认配置不启用 LED 后端，Desktop 模式使用键盘输入抽象。完整板端测试依赖 Linux 的 `grp`、`select` 与 input 行为，不能用 Windows 测试结果代替。

## 2. PC 视觉端

建议 Windows / Python 3.12 独立虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest -q pc/tests
python -m pc.gui --source synthetic
```

真实视觉联调前修改 `pc/config/controller_windows_ethernet.json` 和相机配置。示例网段已经脱敏，不能直接用于现场。启动与操作顺序见 [Windows 以太网指南](WINDOWS_ETHERNET_DEMO.md) 和 [演示 Runbook](DEMO_RUNBOOK.md)。仓库提供源码和 Windows 打包脚本，当前首页不依赖未发布的 EXE 下载。

## 3. i.MX6ULL / Debian 10

板端已验证基线为 Python 3.7.3、PySide2 / Qt 5.11、Linux 4.19.35-imx6。按 [部署记录](IMX6ULL_DEPLOYMENT.md) 核对 Linux input、RGB LED-class、LCD、Goodix 和现有 overlay，再选择本机网络与运行账户。

`device/imx6ull/scripts/deploy.sh` 只通过 SSH 传输清单中的最小 Controller 运行文件；需要先显式设置 `IMX6ULL_HOST`，可覆盖 `IMX6ULL_REMOTE_DIR`。它不会一键安装 HMI、LED helper、systemd 或改写启动配置。服务定义在 `device/imx6ull/systemd/`，现场启用前核对工作目录和账户。

安装后用 `device/imx6ull/scripts/final_smoke_check.sh` 检查状态；它只读状态，不 Reset、不入队、不消费按键。真正的 KEY / RGB / 触摸验收仍需操作者按 [验收索引](ACCEPTANCE.md) 执行。

网络服务用于受控实验局域网，协议未提供 TLS 或身份认证；不要将端口 9000 直接暴露到公网。
