#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd -- "$script_dir/../../.." && pwd)"
lock_file="${XDG_RUNTIME_DIR:-/tmp}/huiyan-hmi-${UID}.lock"
fallback_lock_dir="${XDG_RUNTIME_DIR:-/tmp}/huiyan-hmi-${UID}.lockdir"

fail() {
    printf 'huiyan-hmi: %s\n' "$*" >&2
    exit 1
}

find_touch_event() {
    local scanner=""
    local device_name
    local result
    local candidate
    local event_path
    local name

    if command -v devscan >/dev/null 2>&1; then
        scanner="$(command -v devscan)"
    elif [[ -x /usr/sbin/devscan ]]; then
        scanner=/usr/sbin/devscan
    fi

    if [[ -n "$scanner" ]]; then
        for device_name in "Goodix Capacitive TouchScreen" "goodix-ts" "iMX6UL Touchscreen Controller"; do
            result="$($scanner "$device_name" 2>/dev/null || true)"
            result="${result##*$'\n'}"
            result="${result//[[:space:]]/}"
            case "$result" in
                event[0-9]*)
                    printf '/dev/input/%s\n' "$result"
                    return 0
                    ;;
                /dev/input/event[0-9]*)
                    printf '%s\n' "$result"
                    return 0
                    ;;
            esac
        done
    fi

    # The kernel sysfs input name is stable while event numbering is not.
    for event_path in /sys/class/input/event*; do
        [[ -e "$event_path" ]] || continue
        name="$(cat "$event_path/device/name" 2>/dev/null || true)"
        case "$name" in
            "Goodix Capacitive TouchScreen"|goodix-ts|"iMX6UL Touchscreen Controller")
                candidate="/dev/input/${event_path##*/}"
                printf '%s\n' "$candidate"
                return 0
                ;;
        esac
    done
    return 1
}

[[ -e /dev/fb0 ]] || fail '/dev/fb0 is unavailable'
[[ -e /usr/lib/plugins/generic/libqtslibplugin.so ]] || fail 'missing Qt tslib plugin: /usr/lib/plugins/generic/libqtslibplugin.so'
[[ -d /usr/lib/fonts ]] || fail 'missing Qt font directory: /usr/lib/fonts'
[[ -f /etc/ts.conf ]] || fail 'missing tslib configuration: /etc/ts.conf'

touch_device="$(find_touch_event)" || fail 'no supported touchscreen found (Goodix Capacitive TouchScreen, goodix-ts, iMX6UL Touchscreen Controller)'
[[ -r "$touch_device" ]] || fail "touchscreen is not readable: $touch_device (add the service user to the input group)"

# The current i.MX6ULL Qt 5.11 linuxfb stack needs tslib, plugin and font
# paths explicitly.  Do not set QT_QPA_FB_HIDECURSOR: it causes a native crash.
unset QT_QPA_EVDEV_TOUCHSCREEN_PARAMETERS QT_QPA_EVDEV_MOUSE_PARAMETERS
unset QT_QPA_EVDEV_TABLET_PARAMETERS QT_QPA_FB_DISABLE_INPUT QT_QPA_FB_HIDECURSOR
export QT_QPA_PLATFORM='linuxfb:fb=/dev/fb0'
export QT_QPA_PLATFORM_PLUGIN_PATH=/usr/lib/plugins
export QT_QPA_FONTDIR=/usr/lib/fonts
export TSLIB_TSDEVICE="$touch_device"
export TSLIB_CONFFILE=/etc/ts.conf
export TSLIB_CALIBFILE=/etc/pointercal
export QT_QPA_GENERIC_PLUGINS="tslib:$touch_device"
export QT_QPA_FB_TSLIB=1
export QT_QPA_EGLFS_TSLIB=1
export QWS_MOUSE_PROTO=tslib

# Reject a pre-existing manual or service-launched HMI before claiming the
# advisory flock.  The exact ps columns avoid a pgrep self-match; flock then
# closes the small simultaneous-launch race.
if command -v ps >/dev/null 2>&1; then
    existing="$(ps -u "$UID" -o pid= -o args= | awk '$2 == "/usr/bin/python3" && $3 == "-m" && $4 == "device.imx6ull.hmi.app" { print $1 }')"
    [[ -z "$existing" ]] || fail "HMI is already running (pid(s): $existing)"
fi
if command -v flock >/dev/null 2>&1; then
    exec 9>"$lock_file"
    flock -n 9 || fail 'HMI startup is already in progress or running'
else
    # Fallback for minimal images without flock.  mkdir is atomic; a stale
    # directory is reclaimed only when its recorded owner PID is dead.
    if [[ -d "$fallback_lock_dir" ]]; then
        [[ -O "$fallback_lock_dir" ]] || fail "unsafe fallback lock owner: $fallback_lock_dir"
        fallback_pid="$(cat "$fallback_lock_dir/pid" 2>/dev/null || true)"
        if [[ "$fallback_pid" =~ ^[0-9]+$ ]] && kill -0 "$fallback_pid" 2>/dev/null; then
            fail "HMI is already running (pid: $fallback_pid)"
        fi
        rm -f "$fallback_lock_dir/pid"
        rmdir "$fallback_lock_dir" 2>/dev/null || fail "cannot clear stale fallback lock: $fallback_lock_dir"
    fi
    mkdir "$fallback_lock_dir" 2>/dev/null || fail 'HMI startup is already in progress or running'
    printf '%s\n' "$$" > "$fallback_lock_dir/pid"
    export HUIYAN_HMI_FALLBACK_LOCKDIR="$fallback_lock_dir"
fi

cd "$project_dir"
exec /usr/bin/python3 -m device.imx6ull.hmi.app "$@"
