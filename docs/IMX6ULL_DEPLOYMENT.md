# i.MX6ULL Controller Deployment and M9 Verification

状态：**M9 DOING**。2026-09-10 已完成 i.MX6ULL 上的 Python 3.7.3 兼容部署和真实 USB Gadget Ethernet TCP 验证；GPIO 按键/输出的实际 line、chip、接线和极性尚未确认，故未访问任何 GPIO，也不能将 M9 整体标记为 DONE。

## Deployment baseline

| Item | Verified value |
|---|---|
| board | Wildfire i.MX6ULL |
| OS | Debian GNU/Linux 10 (buster) |
| arch / kernel | armv7l / 4.19.35-imx6 |
| RAM | 486 MiB |
| Python | `/usr/bin/python3`, Python 3.7.3 |
| controller IP | 198.51.100.2 |
| transport | USB Gadget Ethernet (dev-host Ubuntu ↔ i.MX6ULL) |
| TCP listener | `0.0.0.0:9000` |
| SSH | alias `imx6ull`, non-interactive public-key authentication |
| GPIO | `gpioinfo` exists; project mapping remains `key1/key2/key3 = null` |

The committed configuration has no GPIO number. `GpioKeyInput.poll()` therefore returns `NOT_CONFIGURED` without opening a chip, requesting a line, changing a device tree, or accessing a physical pin.

## Python 3.7.3 compatibility work

Implementation commit: `9906133a6db4e5391704fadf3c3b94b0b893b765`.

- Replaced `enum.StrEnum` with `str, Enum` for wire-visible enum values.
- Replaced PEP 604 and PEP 585 annotations with `Optional`/`Union` and `Dict`/`Deque`/`Tuple`/`Set` from `typing`, including the protocol module used by the board.
- Kept the protocol fields, FIFO capacity/order, duplicate-ID handling, reset semantics and Pipeline FSM routes unchanged.
- Made `controller_main.py` add the repository root only when executed as a script, so both `python3 device/imx6ull/controller_main.py` from the deployment root and `python3 -m device.imx6ull.controller_main` work without an externally supplied `PYTHONPATH`.
- Added a standard-library static compatibility test that rejects `StrEnum`, PEP 604 unions and PEP 585 builtin generics in the board runtime and its imported protocol package; it also executes the direct entrypoint import path.

## Minimal transfer

The deployment command is:

```bash
IMX6ULL_HOST=imx6ull IMX6ULL_REMOTE_DIR=/home/debian/huiyan-shizhu \
  device/imx6ull/scripts/deploy.sh
```

It creates the needed remote directories with SSH and transfers only this explicit 17-file runtime manifest with SCP:

- `device/__init__.py`, `device/imx6ull/{__init__.py,controller_main.py}`;
- `device/imx6ull/config/`, `core/`, and `network/` Python sources plus `controller.json`;
- `pc/__init__.py` and `pc/communication/{__init__.py,protocol.py}`.

It excludes tests, `.venv`, `__pycache__`, pytest caches, visual/GUI code, models, datasets, videos, evidence and documents. `compileall` may subsequently create board-local `__pycache__`; it was not transferred.

## 2026-09-10 real-board verification

Test record: `notes/tests/TEST-008-M9-iMX6ULL部署与TCP验证.md`. Test time was 2026-09-10 20:27:52–20:27:54 +08:00.

On the physical board, from `/home/debian/huiyan-shizhu`:

```bash
python3 --version
python3 -m compileall /home/debian/huiyan-shizhu/
python3 device/imx6ull/controller_main.py --mode imx6ull \
  --config device/imx6ull/config/controller.json --host 0.0.0.0
```

Actual results:

- `Python 3.7.3`; `compileall` compiled all 17 deployed runtime files and returned 0 (rechecked with `-q`, exit 0).
- Direct entrypoint import check: PASS.
- Safe GPIO configuration check: `{'key1': None, 'key2': None, 'key3': None}`, status `NOT_CONFIGURED`.
- Controller process PID 2011 listened on `0.0.0.0:9000`, verified by `ss -ltn`.

From the Ubuntu PC, the dependency-free smoke client addressed **`198.51.100.2:9000`**, not localhost or a fake controller. All 10 checks passed:

| Check | Actual result |
|---|---|
| heartbeat | `ack/alive` |
| pipeline_state | `idle`, empty FIFO, capacity 3 |
| enqueue triangle / circle / rectangle | three `accepted` ACKs in that order |
| FIFO full | fourth command returned `queue_full` |
| duplicate command_id | command ID 101 returned `duplicate` while the queue was full |
| reset | `reset` ACK; FIFO empty and `idle` |
| FIFO order | protocol `key_event` sorted triangle ID 201 before circle ID 202; circle followed KEY1 → Station2, KEY2 → Branch2 |
| disconnect / reconnect | new TCP connection received `ack/alive` |

`key_event` is a pre-existing TCP controller protocol test interface. It verifies the software FSM over the real board network only; it is not evidence of a physical key press or GPIO event.

## Remaining M9 work

1. Obtain a real board schematic/connector and `gpioinfo` survey, then record verified GPIO chip, line, active polarity and wiring. Do not infer a global GPIO number.
2. Add and test actual debounced key-event reads only after that mapping is approved; separately validate required output/branch hardware.
3. Record physical key and output evidence. Until then, GPIO hardware verification remains **TODO**, and no status above substitutes for it.
