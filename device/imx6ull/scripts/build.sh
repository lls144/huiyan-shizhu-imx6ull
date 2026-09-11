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
  device/imx6ull/hmi/*.py \
  device/imx6ull/network/*.py \
  device/imx6ull/output/*.py \
  pc/communication/*.py
if [[ -f device/imx6ull/tests/test_python37_compat.py ]]; then
  "$python_bin" -m unittest device.imx6ull.tests.test_python37_compat
else
  echo "Python 3.7 static guard skipped: deployment excludes tests"
fi
