#!/usr/bin/env bash
# Run the offline gate test. pytest comes from a pure-python --target install made on Windows (WSL has no pip):
#   python -m pip install --target %TEMP%\wsl_pytest --no-compile pytest==8.3.3
export EXTRA_PY="${EXTRA_PY:-/mnt/c/Users/biges/AppData/Local/Temp/wsl_pytest}"
PYTHONPATH="$EXTRA_PY" python3 -c "import pytest; print('pytest', pytest.__version__)" || { echo "NO PYTEST"; exit 1; }
cd "$(dirname "$0")" && sed -i 's/\r$//' _test_repro_gate.sh && bash _test_repro_gate.sh
