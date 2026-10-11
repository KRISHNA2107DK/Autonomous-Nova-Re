#!/usr/bin/env bash
# AutoHeal launcher for Linux / macOS / Git-Bash.
#   ./nova.sh demo | serve | campaign | status | help
# Creates a virtual environment outside the repo (~/.cache/novasurge/venv, or
# %LOCALAPPDATA%\AutoHeal\venv on Windows) and installs requirements.txt once.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -n "${NOVASURGE_HOME:-}" ]]; then HOME_DIR="$NOVASURGE_HOME"
elif [[ -n "${LOCALAPPDATA:-}" ]]; then HOME_DIR="$LOCALAPPDATA/AutoHeal"
else HOME_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/novasurge"; fi
VENV="$HOME_DIR/venv"
if [[ -x "$VENV/Scripts/python.exe" ]]; then PY="$VENV/Scripts/python.exe"; else PY="$VENV/bin/python"; fi

mkdir -p "$HOME_DIR"
if [[ ! -x "$PY" ]]; then
  BASE="$(command -v python3.13 || command -v python3.12 || command -v python3.11 || command -v python3 || command -v python)"
  "$BASE" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' || { echo "Python 3.11+ required"; exit 1; }
  echo "[novasurge] creating virtual environment in $VENV"
  "$BASE" -m venv "$VENV"
  if [[ -x "$VENV/Scripts/python.exe" ]]; then PY="$VENV/Scripts/python.exe"; else PY="$VENV/bin/python"; fi
fi
STAMP="$HOME_DIR/requirements.sha256"
HASH="$("$PY" -c "import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest().upper())" "$REPO/requirements.txt")"
if [[ ! -f "$STAMP" || "$(cat "$STAMP")" != "$HASH" ]]; then
  echo "[novasurge] installing Python dependencies (first run downloads ~250 MB)"
  "$PY" -m pip install --disable-pip-version-check -q --upgrade pip
  "$PY" -m pip install --disable-pip-version-check -q -r "$REPO/requirements.txt"
  echo "$HASH" > "$STAMP"
fi
cd "$REPO"
if [[ $# -eq 0 || "$1" == "help" ]]; then exec "$PY" -m novasurge --help; fi
exec "$PY" -m novasurge "$@"
