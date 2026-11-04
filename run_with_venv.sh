#!/usr/bin/env bash
set -euo pipefail

VENV_DIR=".venv"

if [[ "${1:-}" == "" ]]; then
  echo "Usage: $0 <python_file> [args ...]"
  exit 1
fi

PYTHON_FILE="$1"
shift

if [[ ! -f "$PYTHON_FILE" ]]; then
  echo "Error: file not found: $PYTHON_FILE"
  exit 1
fi

if [[ ! -d "$VENV_DIR" ]]; then
  python3 -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

if [[ -f "requirements.txt" ]]; then
  pip install -r requirements.txt
fi

python "$PYTHON_FILE" "$@"
