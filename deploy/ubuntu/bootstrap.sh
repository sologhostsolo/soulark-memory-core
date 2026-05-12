#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/soulark-memory-core}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

mkdir -p "$APP_DIR"
cd "$APP_DIR"

if [ ! -f "requirements.txt" ] || [ ! -f "run.py" ]; then
  echo "Place the soulark-memory-core project at $APP_DIR before running bootstrap." >&2
  exit 1
fi

if [ ! -d ".venv" ]; then
  "$PYTHON_BIN" -m venv .venv
fi

. .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

mkdir -p data

echo "Bootstrap completed."
echo "Next:"
echo "1. cp deploy/ubuntu/env.example deploy/ubuntu/.env"
echo "2. sudo cp deploy/ubuntu/soulark-memory-core.service /etc/systemd/system/"
echo "3. sudo systemctl daemon-reload && sudo systemctl enable --now soulark-memory-core@$(whoami)"