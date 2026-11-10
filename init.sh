#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [[ -x ".venv/bin/python" ]]; then
  PYTHON=".venv/bin/python"
elif command -v python3.11 >/dev/null 2>&1; then
  PYTHON="$(command -v python3.11)"
else
  echo "Sentinel requires Python 3.11.9. Install it, then rerun ./init.sh." >&2
  exit 1
fi

exec "$PYTHON" scripts/bootstrap.py "$@"
