#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
output_path="${1:-$script_dir/huiyan-keys.dtbo}"
dtc_bin="${DTC:-dtc}"
cpp_bin="${CPP:-cpp}"
source_path="$script_dir/huiyan-keys.dts"

command -v "$dtc_bin" >/dev/null
command -v "$cpp_bin" >/dev/null

temporary_source="$(mktemp)"
trap 'rm -f "$temporary_source"' EXIT
"$cpp_bin" -nostdinc -undef -x assembler-with-cpp -I "$script_dir" "$source_path" > "$temporary_source"
"$dtc_bin" -@ -I dts -O dtb -o "$output_path" "$temporary_source"
"$dtc_bin" -I dtb -O dts "$output_path" >/dev/null
