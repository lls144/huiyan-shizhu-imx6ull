# 慧眼识珠证据索引

| Scope | Implementation | Test record | Verified evidence |
|---|---|---|---|
| Vision / multi-object | `pc/vision/` | TEST-003/004 | Ace Pro 2 real camera recognition and lighting records |
| Lifecycle events | `pc/events/` | TEST-005 | one ENTER/EXIT lifecycle behavior |
| PC GUI | `pc/gui/` | TEST-006 | real camera GUI session/performance |
| TCP / FIFO / FSM | `device/imx6ull/` + `pc/communication/` | TEST-008/009 | real board TCP and physical key transitions |
| RGB branch output | `device/imx6ull/output/` | TEST-010 | restricted helper and physical RGB observation |
| Vision end-to-end | `pc/communication/vision_bridge.py` | TEST-011 | camera → TCP → key → branch → LED |
| LCD HMI | `device/imx6ull/hmi/` | TEST-012 | real LCD, Goodix touch and state recovery |
| Cold start / final smoke | services + `final_smoke_check.sh` | TEST-013 | real power cycle, service recovery and final visual smoke |
| RJ45 board persistence | `configure_demo_ethernet.sh` | deployment record | real `eth1` carrier, stable MAC, static board address and reboot recovery; Windows E2E remains TODO |
| Windows RJ45 Python protocol smoke | `scripts/windows_controller_protocol_smoke.py` | TEST-014 | real Windows `ControllerClient` to `203.0.113.2:9000`: connect, heartbeat, state and reset PASS; retry fault path not injected |
| Windows GUI board-state monitor | `pc/communication/state_monitor.py` + `pc/gui/` | TEST-015 | real Windows Vision Console to `203.0.113.2:9000`: heartbeat-derived ONLINE and physical KEY1/2/3 state transitions shown in the Board State panel |
| Windows Camera to digital sorting line | `pc/gui/`, `pc/communication/vision_dispatcher.py` + `vision_bridge.py` | TEST-016 | real Insta360 Ace Pro 2 Camera -> confirmed OBJECT_ENTER -> existing ControllerClient enqueue ACK -> physical keys -> real FIFO/FSM/Branch1/2/3 reflected in the single PySide6 Digital Sorting Line |
| Windows camera occlusion lifecycle | `pc/events/tracker.py` + `pc/config/events.json` | TEST-017 | real hand occlusion preserves one confirmed object/one enqueue; 25-frame grace with shape and spatial re-association, followed by verified true EXIT and new-ID re-entry |

Runtime recordings under ignored `output/` are local evidence, not automatically committed artifacts. Test records state their evidence limits explicitly.
