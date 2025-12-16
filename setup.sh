#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# Pick a Python interpreter
choose_py() {
  if command -v py >/dev/null 2>&1; then
    if py -3 -c "import sys" >/dev/null 2>&1; then echo "py -3"; return; fi
  fi
  for c in python3 python; do
    if command -v "$c" >/dev/null 2>&1; then echo "$c"; return; fi
  done
  echo "ERROR: No suitable Python found (need >=3.8)." >&2
  exit 1
}

SYS_PY=$(choose_py)

# Create venv if missing
if [ ! -d venv ]; then
  $SYS_PY -m venv venv
fi

# Pick venv python path (Windows vs POSIX)
if [ -x "venv/bin/python" ]; then
  PY="venv/bin/python"
else
  PY="venv/Scripts/python.exe"
fi

# Upgrade packaging and install deps from pyproject (editable + dev extra)
"$PY" -m pip install -U pip setuptools wheel
"$PY" -m pip install -e ".[dev]"

echo "setup.sh complete."
