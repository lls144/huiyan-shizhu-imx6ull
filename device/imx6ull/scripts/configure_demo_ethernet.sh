#!/usr/bin/env bash
# Configure one explicit RJ45 interface through the board's existing ConnMan.
# USB Gadget is deliberately excluded and remains the maintenance path.
set -euo pipefail

address='203.0.113.2'
netmask='255.255.255.0'
stable_mac='02:00:00:00:00:01'
interface=''
mode='dry-run'
rollback_dir=''
backup_root='/var/backups/huiyan-demo-ethernet'
link_dir='/etc/systemd/network'

usage() {
    cat <<'EOF'
Usage:
  configure_demo_ethernet.sh --interface IFACE [--check|--dry-run|--install-stable-mac|--apply]
  configure_demo_ethernet.sh --rollback BACKUP_DIRECTORY

Uses ConnMan, the board's existing network manager.  --dry-run is the default.
--apply requires root, a carrier, and the ConnMan service belonging to IFACE.
It configures 203.0.113.2/24 with no gateway.  It supplies no DNS servers
and never touches usb0.

The demonstration FEC starts with a kernel-random MAC address. Run
--install-stable-mac once, reboot, then run --apply.
EOF
}

fail() {
    printf 'huiyan-demo-ethernet: %s\n' "$*" >&2
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --interface) interface="${2:-}"; shift 2 ;;
        --check) mode='check'; shift ;;
        --dry-run) mode='dry-run'; shift ;;
        --install-stable-mac) mode='install-stable-mac'; shift ;;
        --apply) mode='apply'; shift ;;
        --rollback) mode='rollback'; rollback_dir="${2:-}"; shift 2 ;;
        --help|-h) usage; exit 0 ;;
        *) fail "unknown argument: $1" ;;
    esac
done

if [[ "$mode" == rollback ]]; then
    [[ -n "$rollback_dir" && -d "$rollback_dir" ]] || fail 'rollback directory is missing'
    [[ $EUID -eq 0 ]] || fail '--rollback requires root'
    if [[ -f "$rollback_dir/link-file" ]]; then
        link_file="$(cat "$rollback_dir/link-file")"
        if [[ "$(cat "$rollback_dir/link-existed")" == 1 ]]; then
            [[ -f "$rollback_dir/link.before" ]] || fail 'rollback link policy is missing'
            install -m 0644 "$rollback_dir/link.before" "$link_file"
        else
            rm -f "$link_file"
        fi
    fi
    if [[ -f "$rollback_dir/service-id" && -f "$rollback_dir/settings-existed" ]]; then
        service_id="$(cat "$rollback_dir/service-id")"
        settings_file='/var/lib/connman/settings'
        service_settings_file="/var/lib/connman/$service_id/settings"
        if [[ "$(cat "$rollback_dir/settings-existed")" == 1 ]]; then
            [[ -f "$rollback_dir/settings.before" ]] || fail 'rollback settings are missing'
            install -m 0600 "$rollback_dir/settings.before" "$settings_file"
        else
            rm -f "$settings_file"
        fi
        if [[ -f "$rollback_dir/service-settings-existed" ]]; then
            if [[ "$(cat "$rollback_dir/service-settings-existed")" == 1 ]]; then
                [[ -f "$rollback_dir/service-settings.before" ]] || fail 'rollback service settings are missing'
                mkdir -p "/var/lib/connman/$service_id"
                install -m 0600 "$rollback_dir/service-settings.before" "$service_settings_file"
            else
                rm -f "$service_settings_file"
            fi
        else
            # Backward-compatible recovery for the first field deployment,
            # whose service did not exist before the static profile.
            rm -f "$service_settings_file"
        fi
        systemctl restart connman.service
        printf 'restored ConnMan settings for %s; usb0 was not edited\n' "$service_id"
    elif [[ -f "$rollback_dir/link-file" ]]; then
        printf 'restored stable-MAC link policy; reboot to apply it; usb0 was not edited\n'
    else
        fail 'rollback backup is incomplete'
    fi
    exit 0
fi

[[ -n "$interface" ]] || fail '--interface is required'
[[ "$interface" != usb0 ]] || fail 'refusing to modify USB Gadget interface usb0'
[[ -d "/sys/class/net/$interface" ]] || fail "unknown interface: $interface"
command -v connmanctl >/dev/null 2>&1 || fail 'ConnMan client is unavailable'
systemctl is-active --quiet connman.service || fail 'connman.service is not active'

mac="$(tr -d ':' < "/sys/class/net/$interface/address")"
service_id="ethernet_${mac}_cable"
carrier="$(cat "/sys/class/net/$interface/carrier" 2>/dev/null || echo 0)"
usb_before="$(ip -4 -o addr show dev usb0 2>/dev/null || true)"

printf 'interface=%s mac=%s carrier=%s connman_service=%s\n' "$interface" "$mac" "$carrier" "$service_id"
printf 'target=%s netmask=%s gateway=none dns=none\n' "$address" "$netmask"
printf 'required_stable_mac=%s current_mac=%s\n' "$stable_mac" "$(cat "/sys/class/net/$interface/address")"
printf 'usb0=%s\n' "${usb_before:-missing}"

if [[ "$mode" == check ]]; then
    ip -4 -br addr show dev "$interface"
    connmanctl services | grep -F "$service_id" || true
    exit 0
fi

if [[ "$mode" == dry-run ]]; then
    if [[ "$carrier" != 1 ]]; then
        printf 'DRY-RUN: no carrier; connect the intended RJ45 port before --apply\n'
    else
        printf 'DRY-RUN: would run: connmanctl config %s --ipv4 manual %s %s 0.0.0.0\n' \
            "$service_id" "$address" "$netmask"
    fi
    exit 0
fi

if [[ "$mode" == install-stable-mac ]]; then
    [[ $EUID -eq 0 ]] || fail '--install-stable-mac requires root (run with sudo)'
    timestamp="$(date +%Y%m%dT%H%M%S%z)"
    backup_dir="$backup_root/$timestamp-$interface"
    link_file="$link_dir/10-huiyan-demo-$interface.link"
    mkdir -p "$backup_dir" "$link_dir"
    printf '%s\n' "$interface" > "$backup_dir/interface"
    printf '%s\n' "$link_file" > "$backup_dir/link-file"
    if [[ -f "$link_file" ]]; then
        install -m 0644 "$link_file" "$backup_dir/link.before"
        printf '1\n' > "$backup_dir/link-existed"
    else
        printf '0\n' > "$backup_dir/link-existed"
    fi
    cat > "$link_file" <<EOF
[Match]
OriginalName=$interface

[Link]
MACAddress=$stable_mac
EOF
    chmod 0644 "$link_file"
    printf 'installed stable-MAC policy at %s; reboot before --apply; backup=%s\n' "$link_file" "$backup_dir"
    exit 0
fi

[[ "$mode" == apply ]] || fail "unsupported mode: $mode"
[[ $EUID -eq 0 ]] || fail '--apply requires root (run with sudo)'
[[ "$carrier" == 1 ]] || fail 'no RJ45 carrier; refusing to apply an unverified interface'
[[ "$(cat "/sys/class/net/$interface/address")" == "$stable_mac" ]] || fail \
    'interface MAC is not stable; run --install-stable-mac, reboot, then retry --apply'
connmanctl services | awk '{print $NF}' | grep -Fxq "$service_id" || fail "ConnMan service not found: $service_id"

timestamp="$(date +%Y%m%dT%H%M%S%z)"
backup_dir="$backup_root/$timestamp-$interface"
settings_file='/var/lib/connman/settings'
service_settings_file="/var/lib/connman/$service_id/settings"
mkdir -p "$backup_dir"
printf '%s\n' "$service_id" > "$backup_dir/service-id"
if [[ -f "$settings_file" ]]; then
    install -m 0600 "$settings_file" "$backup_dir/settings.before"
    printf '1\n' > "$backup_dir/settings-existed"
else
    printf '0\n' > "$backup_dir/settings-existed"
fi
if [[ -f "$service_settings_file" ]]; then
    install -m 0600 "$service_settings_file" "$backup_dir/service-settings.before"
    printf '1\n' > "$backup_dir/service-settings-existed"
else
    printf '0\n' > "$backup_dir/service-settings-existed"
fi

connmanctl config "$service_id" --ipv4 manual "$address" "$netmask" 0.0.0.0
sleep 1
ip -4 -o addr show dev "$interface" | grep -Fq "$address/24" || fail "address was not applied to $interface"
ip -4 -o addr show dev usb0 | grep -Fq '198.51.100.2/30' || fail 'USB Gadget address changed unexpectedly'
printf 'applied %s/24 to %s; backup=%s\n' "$address" "$interface" "$backup_dir"
