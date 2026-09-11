# i.MX6ULL deployment and runtime

## Board baseline

- Wildfire i.MX6ULL, Debian GNU/Linux 10, armv7l, kernel 4.19.35-imx6, Python 3.7.3.
- Controller listens on `0.0.0.0:9000` through `huiyan-controller.service` as ordinary `debian`.
- `huiyan-led-helper.service` is the restricted root-only RGB Linux LED-class helper.
- `huiyan-hmi.service` is an ordinary-user PySide2/linuxfb HMI service; LCD is 800×480 and Goodix touch is discovered dynamically.
- `huiyan-keys` provides verified physical KEY1/KEY2/KEY3 input. Project overlay and existing LCD/touch/LED overlays are already enabled; no deployment script edits boot configuration.

## Networking

- USB maintenance: `usb0`, `198.51.100.2/30`; keep intact.
- Demo RJ45 profile: `203.0.113.2/24`, no gateway/DNS; see `docs/WINDOWS_ETHERNET_DEMO.md`.
- The actual demo RJ45 port is `eth1` (`platform-2188000.ethernet`). Its
  kernel MAC is random without a dedicated link policy. First install the
  script's stable-MAC policy and reboot, then apply the ConnMan static profile.
  The policy uses `02:00:00:00:00:01`, is matched only to `eth1`, and does not
  change `usb0`.
- Apply/check the board profile with `device/imx6ull/scripts/configure_demo_ethernet.sh`; it requires an explicit interface and creates timestamped backups of the relevant ConnMan settings and link policy.

### Verified persistent RJ45 profile — 2026-09-11

- Physical carrier identified the demo port as `eth1`; `eth2` remained down.
- A narrow `/etc/systemd/network/10-huiyan-demo-eth1.link` policy fixes only
  `eth1` to `02:00:00:00:00:01`. This is necessary because the FEC otherwise
  reports a kernel-random MAC and ConnMan consequently changes its service ID
  on every boot.
- After a normal reboot, ConnMan restored service
  `ethernet_020000000001_cable` with manual `203.0.113.2/24`,
  `Gateway=0.0.0.0`, and no configured DNS servers.
- `usb0` remained `198.51.100.2/30`; USB SSH and a TCP heartbeat to port 9000
  passed. Controller, HMI and LED-helper services all restarted active.

The first static-profile backup is
`/var/backups/huiyan-demo-ethernet/20260911T160638+0800-eth1`.
For any later script-generated backup, use the printed directory with
`sudo .../configure_demo_ethernet.sh --rollback BACKUP_DIRECTORY`; a
stable-MAC-policy rollback requires one normal reboot. This board-side result
is not Windows Ethernet end-to-end evidence.

## Verification

```bash
cd /home/debian/huiyan-shizhu
./device/imx6ull/scripts/final_smoke_check.sh
```

Expected result is `OVERALL ............ PASS`. It only reads status; it never resets, enqueues, drives LEDs or consumes input.

## Known display rule

Never set `QT_QPA_FB_HIDECURSOR=1`. On this Qt 5.11 linuxfb stack it produces a native crash in `app.exec_()`.
