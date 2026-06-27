#!/usr/bin/env bash
# Convenience wrapper for Unix (Linux/macOS). Windows users: `python run.py`.
# Forwards all arguments, so: ./run.sh [start|stop|status|restart] [--watch]
set -euo pipefail
cd "$(dirname "$0")"

if [ -d .venv ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

exec python run.py "$@"
