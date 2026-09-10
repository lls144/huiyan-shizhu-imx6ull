#!/usr/bin/env bash
set -euo pipefail

: "${IMX6ULL_HOST:?Set IMX6ULL_HOST to the SSH destination before deploying.}"
remote_dir="${IMX6ULL_REMOTE_DIR:-/opt/huiyan-controller}"
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd -- "$script_dir/../../.." && pwd)"

ssh "$IMX6ULL_HOST" "mkdir -p '$remote_dir'"
scp -r "$project_dir/device" "$project_dir/pc" "$IMX6ULL_HOST:$remote_dir/"
echo "Transferred source tree to $IMX6ULL_HOST:$remote_dir; install dependencies and configure service manually."
