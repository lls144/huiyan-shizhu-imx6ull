# i.MX6ULL Controller Deployment and M9 Verification

状态：**M9 DOING**。2026-09-10 已完成 i.MX6ULL 上的 Python 3.7.3 兼容部署、真实 USB Gadget Ethernet TCP 验证，以及三枚实体按键从 `gpio-keys` 到 Controller FSM 的验证。GPIO 分支输出硬件和完整实体执行链路尚未验证，故不能将 M9 整体标记为 DONE。

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
| GPIO input | `gpiochip0` lines 24/25/26, active-low, verified through `gpio-keys` as `huiyan-keys` |
| GPIO output | no verified mapping, wiring, or physical output test |

The earlier safe-deployment configuration had no GPIO number and remained `NOT_CONFIGURED`. After the real mapping and wiring were confirmed, the committed configuration uses only the verified Linux input device name `huiyan-keys` and input key codes; the application does not open GPIO chips or hard-code an `eventX` number.

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

## 2026-09-10 gpio-keys and physical-key verification

Test record: `notes/tests/TEST-009-M9-iMX6ULL实体GPIO按键验收.md`. This section is distinct from the TCP `key_event` injection above: its raw events came from the entity board's `/dev/input` device.

### Safe board integration

- The official `/usr/lib/linux-image-4.19.35-imx6/overlays/imx-fire-key.dtbo` was inspected but neither edited nor replaced.
- Project overlay: `device/imx6ull/overlay/huiyan-keys.dts`, compiled and installed as `/usr/lib/linux-image-4.19.35-imx6/overlays/huiyan-keys.dtbo` (SHA-256 `873653f867ce0727111498712ad4a5975d5f6fe655031ed9785b353c56e85350`).
- The only added boot line is `dtoverlay=/usr/lib/linux-image-4.19.35-imx6/overlays/huiyan-keys.dtbo`; the pre-change file is retained on the board at `/home/debian/huiyan-shizhu/overlay-staging/20260910-huiyan-keys/uEnv.txt.before-huiyan-keys-20260910T212854+0800`.
- The overlay changes neither the main DTB, U-Boot, existing overlays, nor any UART3 device node. It uses only these confirmed free UART3 pads as GPIO inputs: `MX6UL_PAD_UART3_TX_DATA__GPIO1_IO24`, `MX6UL_PAD_UART3_RX_DATA__GPIO1_IO25`, and `MX6UL_PAD_UART3_CTS_B__GPIO1_IO26`.
- Its `fsl,pins` setting is `0x0001b0b1` (hysteresis plus enabled 100 KOhm pull-up and input path); this is required by the passive button-to-GND wiring. `GPIO_ACTIVE_LOW` makes released keys logical high at the GPIO layer and pressed keys logical active in the Linux input layer.
- Each gpio-keys child uses a 20 ms debounce interval. Linux input codes are KEY1 → `KEY_PROG1` / 148, KEY2 → `KEY_PROG2` / 149, KEY3 → `KEY_PROG3` / 202.

After reboot, `gpioinfo gpiochip0` showed lines 24, 25 and 26 as the active-low, in-use `Huiyan KEY1`, `Huiyan KEY2` and `Huiyan KEY3` inputs. `/proc/bus/input/devices` registered `Name="huiyan-keys"` (it happened to be `event1` for this boot, but that number is not used by the application). The stable board symlink was `/dev/input/by-path/platform-huiyan-keys-event`.

### Actual physical evidence

The standard-library capture program (`device/imx6ull/scripts/capture_input_events.py`) found the device by its sysfs name and read Linux `input_event` records. It produced the board log `/home/debian/huiyan-shizhu/overlay-staging/20260910-huiyan-keys/huiyan-keys-input-events-20260910T214016+0800.log` while the operator pressed and released each wired mechanical key once.

| Physical key | Linux input code | observed values | Result |
|---|---:|---|---|
| KEY1 | 148 (`KEY_PROG1`) | `1`, then `0` | PASS |
| KEY2 | 149 (`KEY_PROG2`) | `1`, then `0` | PASS |
| KEY3 | 202 (`KEY_PROG3`) | `1`, then `0` | PASS |

Exactly six EV_KEY records were captured: one press and one release for each key, with no unexpected duplicate or bounce event. This proves the physical active-low wiring is translated correctly: press is input value `1`, release is input value `0`.

### Controller integration and physical FSM closure

`LinuxInputKeyInput` is a Python 3.7 standard-library backend. It locates `huiyan-keys` dynamically via `/sys/class/input/event*/device/name`, reads `struct input_event` with `os`/`select`/`struct`, maps only the three verified key codes, and feeds only `EV_KEY value == 1` to the existing FSM. It ignores releases and suppresses kernel repeat values until release, so it neither hard-codes `/dev/input/event1` nor changes the TCP protocol, FIFO, duplicate-ID or reset semantics.

With the deployed controller listening on `0.0.0.0:9000`, real TCP commands enqueued triangle 301, circle 302 and rectangle 303. Physical keys then drove the existing FSM: KEY1 sorted triangle to Branch1; KEY1 then KEY2 sorted circle through Station2 to Branch2; and KEY1 then KEY2 then KEY3 sorted rectangle through Stations 2/3 to Branch3. The early out-of-order presses recorded `wrong_station` without changing FIFO order or corrupting state; the later correct presses completed all three items. A two-second held KEY1 yielded only one `empty` FSM input after the queue had drained; a rapid double press after enqueuing triangle 401 yielded exactly `sorted Branch1`, then `empty`. A final real-network TCP smoke test still passed all 10 checks, including reset and reconnect.

## Remaining M9 work

1. Verify and document the actual GPIO output/LED or branch-actuator mapping, polarity, electrical interface and wiring. Do not infer any output line.
2. Implement and physically validate those outputs only after their mapping is approved; keep the input evidence above separate from output evidence.
3. Run the full end-to-end camera-to-controller-to-physical-output demonstration. Until output and end-to-end evidence exist, M9 remains **DOING**.
