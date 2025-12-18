#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# Pick venv python path (Windows vs POSIX)
if [ -x "venv/bin/python" ]; then
  PY="venv/bin/python"
else
  PY="venv/Scripts/python.exe"
fi

# Ensure setup has been run
if [ ! -f "$PY" ]; then
  echo "Running setup.sh first..."
  bash ./setup.sh
fi

# Be sure to use `exec` so that termination signals reach the python process,
# or handle forwarding termination signals manually
echo "Starting module..."
exec "$PY" -m src.main "$@"
