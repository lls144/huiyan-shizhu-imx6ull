#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd -- "$script_dir/../../.." && pwd)"
python_bin="${PYTHON_BIN:-python3}"
mode="${CONTROLLER_MODE:-desktop}"
config_path="${CONTROLLER_CONFIG:-$project_dir/device/imx6ull/config/controller.json}"

cd "$project_dir"
exec "$python_bin" -m device.imx6ull.controller_main --mode "$mode" --config "$config_path" "$@"
