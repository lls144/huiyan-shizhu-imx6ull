---
title: TEST-011 M9 PC 视觉至 i.MX6ULL 实体按键与 RGB LED 端到端验收
date: 2026-09-11
tags: [慧眼识珠, M9, e2e, vision, tcp, imx6ull, gpio-keys, led, hardware]
status: PASS
---

# TEST-011 M9 PC 视觉至 i.MX6ULL 实体按键与 RGB LED 端到端验收

## 范围、版本与环境

- PC bridge implementation: `76ce5f180e0d4e1584e6dc0a82409b4cdfcd5a2a` on branch `imx6ull-development`. It reuses M3 detection and M4 lifecycle events; it sends only a confirmed `OBJECT_ENTER` through the existing M7 `ControllerClient`.
- Ubuntu host: dev-host, repository `/home/developer/huiyan-shizhu`, Python 3.12.3 local `.venv`, OpenCV 5.0.0, NumPy 2.5.2. `.venv/` and runtime `output/` are ignored and were not committed.
- Camera: Insta360 Ace Pro 2, explicitly opened as `/dev/video2` via V4L2. Requested and observed mode: MJPG, 1920×1080, 30.0 fps; validation frame shape `[1080, 1920, 3]`. `/dev/video0` was not used.
- Controller: real Wildfire i.MX6ULL, Debian GNU/Linux 10 (buster), armv7l, kernel 4.19.35-imx6, Python 3.7.3, `198.51.100.2:9000` over USB Gadget Ethernet. The listening Controller process ran as ordinary `debian`; `huiyan-led-helper.service` remained root-owned and active.
- Physical input/output: `huiyan-keys` (KEY1/KEY2/KEY3) and the existing board RGB LED helper/official LED class. Their electrical mapping and helper security boundary are recorded separately in TEST-009 and TEST-010.

This test validates the i.MX6ULL Controller route. It does not claim LCD HMI, heartbeat watchdog/alarm requirements, or M10 completion.

## PC bridge and safety boundary

The live command used M3's existing camera/pipeline and M4 event tracker with:

```text
.venv/bin/python -m pc.vision --config pc/config/vision.json multi-live \
  --camera-config pc/config/camera_ubuntu_acepro2.json --reuse-calibration \
  --events --event-config pc/config/events.json \
  --controller-config pc/config/controller_ubuntu_usb_maintenance.json \
  --expected-labels <one-shape> --command-id-start <unique-positive-id>
```

The new bridge is fail-closed: only `OBJECT_ENTER` for triangle/circle/rectangle can enqueue; each E2E run declares exactly one expected shape; another valid-but-unexpected label is rejected before TCP. It preserves M4's source event/object IDs in the existing enqueue fields, requires an `accepted` ACK, and exits normally after the first accepted event so one test run cannot enqueue a second object. It changes neither the vision classifier, ROI configuration, thresholds, M7 protocol, FIFO capacity/order nor Pipeline FSM.

The initial triangle guard observed a remaining rectangle and correctly refused it before TCP. That is recorded as a safety observation, not a failed physical sorting result. The successful accepted records below are retained in ignored local session JSON; no curated still screenshot was saved during this live run, so this record does not claim one.

## Actual end-to-end results

| Test | Real M4 result and Controller ACK | Entity key sequence / FIFO result | Physical LED observation | Result |
|---|---|---|---|---|
| triangle | `OBJECT_ENTER #1`, confidence 0.954029; command 14001 `accepted`, Station1, front triangle | operator KEY1 → Branch1; state then idle/empty | red for about 1 s, then off | PASS |
| circle | `OBJECT_ENTER #1`, confidence 0.977329; command 14010 `accepted`, Station1, front circle | KEY1 → Station2 with all channels 0; KEY2 → Branch2; state then idle/empty | red+green (yellow-green on the RGB package) for about 1 s, then off | PASS |
| rectangle | `OBJECT_ENTER #1`, confidence 0.979300; command 14020 `accepted`, Station1, front rectangle | KEY1 → Station2 with all channels 0; KEY2 → Station3 with all channels 0; KEY3 → Branch3; state then idle/empty | red+green+blue mixed three-channel light for about 1 s, then off | PASS |

Each recognized event received its ACK from **`198.51.100.2:9000`**, not localhost, a mock, or a board-local injection. Each subsequent `pipeline_state` query showed the expected station, queue length and front item. After every completed branch, `red`, `green` and `blue` brightness read `0`; a heartbeat returned `ack/alive` and the helper remained `active`.

## Additional real-board checks

| Check | Actual result | Result |
|---|---|---|
| PC TCP ingress/FIFO boundary | Existing PC `ControllerClient` enqueued triangle 13001, circle 13002, rectangle 13003 in that order; board reached capacity 3 with triangle 13001 as front, then TCP reset returned idle/empty. This is a real-network FIFO ingress check, distinct from the visual one-object acceptance runs. | PASS |
| wrong physical station | PC client enqueued circle 15001 to Station1 with all LEDs 0; operator pressed physical KEY3. Board remained Station1, length 1, same front; no LED lit. | PASS |
| reset | TCP reset after the wrong-station case returned idle/empty; all brightness values were 0. | PASS |
| disconnect / reconnect | Two separately created PC `ControllerClient` connections each received heartbeat `ack/alive`. | PASS |
| Controller/helper health | Controller remained a `debian` process listening on `0.0.0.0:9000`; helper remained active. `journalctl` for the E2E interval reported no helper error entries. | PASS |

The visual acceptance runs are one object at a time, as required by the three physical test procedures. FIFO ordering under a three-item queue and physical-key sequencing were already independently exercised in TEST-008/TEST-009; this test adds the missing true camera/M4/TCP ingress to each of the three branch routes.

## Evidence locations

- ignored local M3/M4 session records: `output/m9-e2e/triangle/session-20260911-103611-532330.json`, `output/m9-e2e/circle/session-20260911-103756-802137.json`, and `output/m9-e2e/rectangle/session-20260911-103953-311346.json`; each successful event record includes the M4 label/confidence, `command_id`, ACK and board FIFO snapshot. The rectangle session completed normally using the one-accepted-event exit; earlier triangle/circle interactive sessions were subsequently interrupted/rejected after their accepted event and are retained as raw facts rather than hidden.
- board state/brightness/service checks were performed through the noninteractive `imx6ull` SSH alias during each transition; the physical RGB color/time observations above are operator observations.
- prior raw Linux input evidence: TEST-009; prior LED helper brightness duration and access-control evidence: TEST-010.

## Conclusion

All three required real paths passed:

```text
Ubuntu Ace Pro 2 camera -> M3 recognition -> M4 OBJECT_ENTER
-> real TCP 198.51.100.2:9000 -> i.MX6ULL FIFO/Pipeline FSM
-> physical KEY1/KEY2/KEY3 -> Branch1/2/3 -> physical RGB LED -> dequeue
```

Therefore **M9 (the i.MX6ULL deployment/GPIO route) is DONE**. This record does not start M10.
