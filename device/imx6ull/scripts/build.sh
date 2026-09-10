#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd -- "$script_dir/../../.." && pwd)"
python_bin="${PYTHON_BIN:-python3}"

cd "$project_dir"
"$python_bin" -m py_compile \
  device/__init__.py \
  device/imx6ull/__init__.py \
  device/imx6ull/controller_main.py \
  device/imx6ull/config/*.py \
  device/imx6ull/core/*.py \
  device/imx6ull/network/*.py \
  pc/communication/*.py
