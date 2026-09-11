# Windows ↔ i.MX6ULL RJ45 演示网络

## 正式地址

| Endpoint | Address | Netmask | Gateway / DNS |
|---|---|---|---|
| Windows Ethernet NIC | `203.0.113.1` | `255.255.255.0` | none / none |
| i.MX6ULL demo Ethernet | `203.0.113.2` | `255.255.255.0` | none / none |
| Controller TCP | `203.0.113.2:9000` | — | — |

`203.0.113.0/24` was selected after read-only route checks found no explicit route using that subnet on the Ubuntu maintenance host or board. It is an isolated direct-link subnet; do not configure a default gateway or DNS for this NIC.

The board FEC starts with a kernel-random MAC address. Before applying the
static profile, run the repository script's `--install-stable-mac` once and
reboot; it writes a narrowly matched `eth1` systemd link policy with locally
administered MAC `02:00:00:00:00:01`. This keeps ConnMan's Ethernet service ID
stable across subsequent boots and does not alter `usb0`.

## Profiles

- Windows demo client: `pc/config/controller_windows_ethernet.json`
- Ubuntu maintenance client: `pc/config/controller_ubuntu_usb_maintenance.json`
- Board persistent configuration: `device/imx6ull/scripts/configure_demo_ethernet.sh`

USB Gadget remains a separate maintenance interface at `198.51.100.2/30`; it is not part of normal demonstration traffic and must remain available.

## Verification boundary

Board-side persistence is **PASS**: the real carrier identified `eth1`; one
normal reboot applied the stable-MAC policy, and the subsequent normal reboot
retained both that MAC and the `203.0.113.2/24` profile while USB maintenance
and the Controller services recovered. This was performed from Ubuntu without
configuring its physical Ethernet interface.

Windows NIC configuration, `ping`, TCP port 9000, GUI connection and
disconnect/reconnect remain **TODO for Windows validation**. Do not interpret
the board-only result as Windows RJ45 end-to-end PASS.

## Windows configuration

Set the selected physical Ethernet adapter to IPv4 manual configuration: address `203.0.113.1`, prefix `/24`, with gateway and DNS empty. Connect it directly to the board’s configured RJ45 port. Verify:

```powershell
ping 203.0.113.2
Test-NetConnection 203.0.113.2 -Port 9000
```

Only after carrier and these commands are successful is the RJ45 end-to-end link PASS. A board-side static profile without carrier is only configuration preparation, not link evidence.
