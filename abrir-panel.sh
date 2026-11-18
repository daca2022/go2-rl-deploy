#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if [[ ! -x .venv-a2/bin/python ]]; then
  printf 'Primero ejecuta: bash install-panel.sh\n' >&2
  exit 1
fi
exec .venv-a2/bin/python panel.py
