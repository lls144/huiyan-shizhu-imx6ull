#!/usr/bin/env bash
set -euo pipefail

: "${IMX6ULL_HOST:?Set IMX6ULL_HOST to the SSH destination before deploying.}"
remote_dir="${IMX6ULL_REMOTE_DIR:-/home/debian/huiyan-shizhu}"
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd -- "$script_dir/../../.." && pwd)"

ssh "$IMX6ULL_HOST" "mkdir -p '$remote_dir'"
files=(
  device/__init__.py
  device/imx6ull/__init__.py
  device/imx6ull/controller_main.py
  device/imx6ull/config/__init__.py
  device/imx6ull/config/controller.json
  device/imx6ull/config/controller_config.py
  device/imx6ull/core/__init__.py
  device/imx6ull/core/controller.py
  device/imx6ull/core/fifo.py
  device/imx6ull/core/key_input.py
  device/imx6ull/core/models.py
  device/imx6ull/core/pipeline.py
  device/imx6ull/network/__init__.py
  device/imx6ull/network/tcp_server.py
  pc/__init__.py
  pc/communication/__init__.py
  pc/communication/protocol.py
)

# Copy an explicit manifest.  This deliberately excludes .venv, caches,
# tests, visual modules/models, evidence and all non-controller sources.
for file in "${files[@]}"; do
  remote_parent="$(dirname -- "$remote_dir/$file")"
  ssh "$IMX6ULL_HOST" "mkdir -p '$remote_parent'"
  scp "$project_dir/$file" "$IMX6ULL_HOST:$remote_dir/$file"
done
echo "Transferred the minimal controller runtime to $IMX6ULL_HOST:$remote_dir."
