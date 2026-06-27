#!/usr/bin/env bash
# Convenience launcher for Unix (Linux/macOS). Windows users: `python run.py`.
set -euo pipefail
cd "$(dirname "$0")"

if [ -d .venv ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

exec python run.py "$@"
