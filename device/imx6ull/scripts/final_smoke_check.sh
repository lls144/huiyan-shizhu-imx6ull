#!/usr/bin/env bash
# Read-only field check for the approved i.MX6ULL Controller route.
set -u -o pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd -- "$script_dir/../../.." && pwd)"
pass_count=0
fail_count=0
hmi_pid=""

pass() {
    printf '%-24s PASS\n' "$1"
    pass_count=$((pass_count + 1))
}

fail() {
    printf '%-24s FAIL%s\n' "$1" "${2:+ ($2)}"
    fail_count=$((fail_count + 1))
}

check_command() {
    local label="$1"
    shift
    if "$@" >/dev/null 2>&1; then
        pass "$label"
    else
        fail "$label"
    fi
}

find_hmi_pid() {
    ps -u "$UID" -o pid= -o args= 2>/dev/null |
        awk '$2 == "/usr/bin/python3" && $3 == "-m" && $4 == "device.imx6ull.hmi.app" { print $1 }'
}

echo 'HUIYAN FINAL SMOKE'
echo "System .............. $(uname -srmo)"
echo "Python .............. $(/usr/bin/python3 --version 2>&1)"
echo "Uptime .............. $(uptime -p 2>/dev/null || uptime)"

check_command 'Controller service' systemctl is-active --quiet huiyan-controller.service
check_command 'TCP port 9000' bash -c 'ss -lnt | grep -q "[.:]9000[[:space:]]"'

controller_state="$({
    cd "$project_dir" || exit 1
    /usr/bin/python3 - <<'PY'
from __future__ import print_function

from device.imx6ull.hmi.state_client import ControllerStateClient

client = ControllerStateClient("127.0.0.1", 9000, request_timeout=1.0)
heartbeat = client._request("heartbeat")
state = client._request("state")["pipeline_state"]
if heartbeat.get("status") != "alive":
    raise SystemExit("heartbeat is not alive")
if state.get("queue_length") != 0 or not state.get("empty") or state.get("station") != "idle":
    raise SystemExit("FIFO is not empty/idle: {0}".format(state))
print("ok")
PY
} 2>&1)"
if [[ "$controller_state" == ok ]]; then
    pass 'TCP heartbeat'
    pass 'FIFO idle/empty'
else
    fail 'TCP heartbeat/FIFO' "$controller_state"
fi

check_command 'LED helper service' systemctl is-active --quiet huiyan-led-helper.service
if [[ -S /run/huiyan-led/helper.sock ]]; then
    pass 'LED helper socket'
else
    fail 'LED helper socket'
fi
rgb_off=true
for led in red green blue; do
    value="$(tr -d '[:space:]' < "/sys/class/leds/$led/brightness" 2>/dev/null || true)"
    [[ "$value" == 0 ]] || rgb_off=false
done
if [[ "$rgb_off" == true ]]; then
    pass 'RGB off'
else
    fail 'RGB off'
fi

check_command 'HMI service' systemctl is-active --quiet huiyan-hmi.service
hmi_pids="$(find_hmi_pid)"
if [[ "$(printf '%s\n' "$hmi_pids" | sed '/^$/d' | wc -l)" -eq 1 ]]; then
    hmi_pid="$hmi_pids"
    pass 'HMI single instance'
else
    fail 'HMI single instance' "pid(s): ${hmi_pids:-none}"
fi
if [[ -e /dev/fb0 && "$(cat /sys/class/graphics/fb0/virtual_size 2>/dev/null || true)" == '800,480' ]] && \
    [[ -n "$hmi_pid" ]] && tr '\0' '\n' < "/proc/$hmi_pid/environ" 2>/dev/null | grep -Fxq 'QT_QPA_PLATFORM=linuxfb:fb=/dev/fb0'; then
    pass 'LCD linuxfb 800x480'
else
    fail 'LCD linuxfb 800x480'
fi

if grep -Fq 'Name="huiyan-keys"' /proc/bus/input/devices 2>/dev/null; then
    pass 'KEY input device'
else
    fail 'KEY input device'
fi
if grep -Eq 'Goodix Capacitive TouchScreen|goodix-ts|iMX6UL Touchscreen Controller' /proc/bus/input/devices 2>/dev/null; then
    pass 'Touch input device'
else
    fail 'Touch input device'
fi
if grep -Fq 'huiyan-keys.dtbo' /boot/uEnv.txt 2>/dev/null && \
    grep -Fq 'imx-fire-lcd.dtbo' /boot/uEnv.txt 2>/dev/null && \
    grep -Fq 'imx-fire-touch-capacitive-gt1151.dtbo' /boot/uEnv.txt 2>/dev/null && \
    grep -Fq 'imx-fire-led.dtbo' /boot/uEnv.txt 2>/dev/null; then
    pass 'Required overlays'
else
    fail 'Required overlays'
fi
if systemctl is-enabled --quiet ebf-qtdemo.service 2>/dev/null; then
    fail 'Vendor Qt demo disabled'
else
    pass 'Vendor Qt demo disabled'
fi

echo
if [[ "$fail_count" -eq 0 ]]; then
    echo 'OVERALL ............ PASS'
    exit 0
fi
echo "OVERALL ............ FAIL ($fail_count failed, $pass_count passed)"
exit 1
