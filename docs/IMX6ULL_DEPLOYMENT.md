# i.MX6ULL Controller Deployment and M9/M10 Verification

状态：**M9 DONE（批准的 i.MX6ULL Controller 路线）**。已完成 i.MX6ULL 上的 Python 3.7.3 兼容部署、真实 USB Gadget Ethernet TCP 验证、三枚实体按键到 Controller FSM、板载 RGB LED 的受限 helper 与实体按键/FSM/LED 闭环，以及 PC 摄像头视觉至实体 LED 的三类端到端验收。该结论不关闭原始 PLC 路线或 M10。

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
| input permission | `debian` is a member of group `input` (`id` includes `106(input)`), permitting reads of `/dev/input/event*` |
| GPIO input | `gpiochip0` lines 24/25/26, active-low, verified through `gpio-keys` as `huiyan-keys` |
| GPIO output | root-owned LED helper、Linux LED class、实体按键/FSM/RGB LED 与 PC vision E2E PASS |

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

It creates the needed remote directories with SSH and transfers only the unprivileged Controller runtime manifest with SCP:

- `device/__init__.py`, `device/imx6ull/{__init__.py,controller_main.py}`;
- `device/imx6ull/config/`, `core/`, `network/` and `output` client Python sources plus `controller.json`;
- `pc/__init__.py` and `pc/communication/{__init__.py,protocol.py}`.

It excludes tests, `.venv`, `__pycache__`, pytest caches, visual/GUI code, models, datasets, videos, evidence and documents. The privileged helper/service/config are deliberately installed through the separate audited root procedure below, never by this unprivileged transfer. `compileall` may subsequently create board-local `__pycache__`; it was not transferred.

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
- Its `fsl,pins` setting is `0x0001b0b1`: HYS is enabled; PKE enables the pull/keeper circuit; PUE separately selects pull rather than keeper; and the selected resistor is the internal 100 KOhm pull-up. This is required by the passive button-to-GND wiring. `GPIO_ACTIVE_LOW` makes released keys logical high at the GPIO layer and pressed keys logical active in the Linux input layer. UART3's official overlay remains disabled, so these three UART3 pads remain assigned only to this project input overlay.
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

## 2026-09-10 board-LED output audit — pre-implementation baseline

This was a read-only board audit, not an output test. The enabled official `imx-fire-led.dtbo` already registers three independent `gpio-leds` with trigger `none`; it was not modified. The recommended future Branch display pattern is Branch1/triangle = red (one lamp), Branch2/circle = red + green (two lamps), and Branch3/rectangle = red + green + blue (three lamps), preserving the task's 1/2/3-lamp requirement.

| LED | GPIO mapping | polarity | Linux interface | current implementation/test status |
|---|---|---|---|---|
| red | GPIO1_IO04, gpiochip0 line 4 | active-low | `/sys/class/leds/red/brightness` | physical helper output verified below |
| green | GPIO4_IO20, gpiochip3 line 20 | active-low | `/sys/class/leds/green/brightness` | physical helper output verified below |
| blue | GPIO4_IO19, gpiochip3 line 19 | active-low | `/sys/class/leds/blue/brightness` | physical helper output verified below |

The application uses the LED class and never claims these kernel-owned lines through libgpiod. No new LED overlay was added and `imx-fire-led.dtbo` remains unchanged. The original brightness attributes were `root:root` mode `0644`, so an unprivileged Controller cannot write them directly; the later helper deployment below preserves that boundary.

## 2026-09-10/11 restricted LED helper and physical output closure — PASS

Test record: `notes/tests/TEST-010-M9-iMX6ULL实体LED闭环验收.md`. Implementation: `a8b54179ef16d85946407ae86d8cee9661b3744d`.

- The helper runs as `root` in ordinary `huiyan-led-helper.service`, while Controller PID 2022 ran as ordinary user `debian`; Controller was never run as root.
- Root-owned code is installed at `/opt/huiyan-led-helper`; root-only config `/etc/huiyan-led-helper.json` fixes `/run/huiyan-led/helper.sock`, mode `0660`, group `huiyan-led` and a 1000 ms duration. `debian` was added to that group. The runtime directory/socket were observed as `0750 root:huiyan-led` and `0660 root:huiyan-led`.
- The initial mount-namespace hardening failed on this image with systemd `status=226/NAMESPACE`; it was removed because this kernel cannot establish the required namespace. The compatible unit retains root-owned immutable helper code/config, direct fixed `ExecStart` (no shell), `NoNewPrivileges`, `CapabilityBoundingSet=CAP_CHOWN CAP_DAC_OVERRIDE`, `UMask=0007`, `RestrictAddressFamilies=AF_UNIX`, fixed paths and a strict branch/off protocol.
- The repository `controller.json` remains safely disabled. Only the board runtime copy was backed up and changed to `led_output.enabled=true` for this supervised test; its backup is `/home/debian/huiyan-shizhu/device/imx6ull/config/controller.json.pre-led-enable-20260910T222433+0800`.

Direct socket tests as ordinary `debian` passed: Branch1 set red only, Branch2 set red+green, Branch3 set all three, each automatically returned to all-zero; `OFF` returned all-zero; an invalid `gpio` message had no effect; service remained active. The single RGB package presents red, yellow-green (red+green) and blue-white (red+green+blue), which is the expected physical mixing of the required logical 1/2/3 channel patterns.

The real Controller listened on `0.0.0.0:9000` as `debian`. From dev-host, TCP heartbeat and state passed; enqueue, wrong-station KEY2, ordinary KEY1 station movement and reset were checked without lighting any LED. This proves those non-sort paths do not produce a branch-output event.

| Physical queue item | observed physical keys and Controller result | LED evidence | Result |
|---|---|---|---|
| triangle 9201 | KEY1 → `sorted Branch1`, FIFO length 0 | operator observed red; subsequently all brightness values were 0 | PASS |
| circle 9202 | KEY3 → `wrong_station`; KEY1 → Station2; KEY2 (raw code 149 press/release) → `sorted Branch2` | operator observed yellow-green then auto-off | PASS |
| rectangle 9203 | KEY1 → Station2; wrong keys preserved state; KEY2 (raw 149 press/release) → Station3; KEY3 (raw code 202 press/release) → `sorted Branch3` | sampler observed all three brightness values 255 from 12616 ms to 13612 ms (about 996 ms), then all 0; operator observed blue-white | PASS |
| reset | real TCP reset returned empty/idle | red/green/blue all read 0 after reset | PASS |

This closes the M9 board LED-output and entity-key/FSM/LED sub-scope. It is not evidence of PC vision to physical LED end-to-end operation, and it does not change the status of the original PLC requirements.

## 2026-09-11 PC vision → TCP → entity key/LED end-to-end closure — PASS

Test record: `notes/tests/TEST-011-M9-PC视觉至实体LED端到端验收.md`. The Ubuntu PC explicitly opened Ace Pro 2 at `/dev/video2` with V4L2/MJPG/1920×1080/30 fps, then reused the existing M3 detector and M4 lifecycle tracker. A narrow fail-closed bridge accepted only one declared `OBJECT_ENTER` label at a time and sent it with the existing `ControllerClient` to `198.51.100.2:9000`.

| recognized shape | real M4 confidence / accepted command | physical pipeline and observed RGB result | result |
|---|---|---|---|
| triangle | 0.954029 / 14001 | KEY1 → Branch1 → red about 1 s → off → dequeue | PASS |
| circle | 0.977329 / 14010 | KEY1 → Station2 (off), KEY2 → Branch2 → red+green about 1 s → off → dequeue | PASS |
| rectangle | 0.979300 / 14020 | KEY1 → Station2 (off), KEY2 → Station3 (off), KEY3 → Branch3 → red+green+blue about 1 s → off → dequeue | PASS |

The same session also rechecked a wrong physical station (no state change/no LED), TCP reset (idle/empty/all LEDs off), heartbeat and new-client reconnect. Controller remained an ordinary `debian` process on `0.0.0.0:9000`; the root helper remained active and had no error entries in the E2E interval. This completes M9 for this approved Controller route. A persistent ordinary-user Controller service is a future operational improvement, not an untested M9 acceptance requirement.

## 2026-09-11 M10 LCD Qt HMI — PASS

Test record: `notes/tests/TEST-012-M10-iMX6ULL-LCD-HMI验收.md`.

- The real LCD uses `/dev/fb0` (`mxs-lcdif`), 800×480, 16 bpp and stride 1600.  The board runtime is Python 3.7.3, PySide2 5.11.2 / Qt 5.11.3, with `linuxfb:fb=/dev/fb0`.
- `device/imx6ull/scripts/start_hmi.sh` dynamically locates the touchscreen by the kernel input-device name (Goodix names first, `/sys/class/input` fallback), rather than hard-coding `event3`.  The actual Goodix device in this session was `/dev/input/event3`.
- The launcher checks fb0, the tslib generic Qt plugin, fonts, tslib configuration and read permission before starting one HMI instance.  It sets the verified tslib/plugin/font environment and unsets stale evdev variables.  It deliberately never sets `QT_QPA_FB_HIDECURSOR=1`: Qt 5.11 linuxfb on this target segfaults in `app.exec_()` when that variable is used.
- `huiyan-hmi.service` runs as ordinary `debian` with the `input` supplementary group, starts after basic networking and the LED helper, and delegates all single-instance protection to the same launcher.  The HMI only uses `127.0.0.1:9000`; it does not access GPIO, LED sysfs, FIFO internals or `/dev/input` itself.
- The vendor `ebf-qtdemo.service` was identified as the auto-start source for `/usr/local/qt-app/run.sh` and `/usr/local/qt-app/App`.  It was disabled reversibly; neither the vendor directory nor binary was modified.  Its historical `failed` state is not a running process.
- Physical LCD display, real `/dev/input` tslib touch RESET, three true camera/M4/TCP enqueue paths, physical key/FSM/LED routing, ordered 3/3 FIFO, wrong-key retention, and an observable Controller OFFLINE→ONLINE recovery all passed.  The HMI stayed a single ordinary-user process and the vendor Demo process was absent.
