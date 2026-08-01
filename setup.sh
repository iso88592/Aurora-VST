#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${AURORA_VENV:-$ROOT_DIR/.venv}"
DEVICE="cpu"
NON_INTERACTIVE=0

usage() { echo "Usage: $0 [--cpu|--cuda] [--non-interactive]"; }
for arg in "$@"; do
  case "$arg" in
    --cpu) DEVICE="cpu" ;;
    --cuda) DEVICE="cuda" ;;
    --non-interactive) NON_INTERACTIVE=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; usage; exit 2 ;;
  esac
done

command -v python3 >/dev/null || { echo "Python 3.10-3.12 is required" >&2; exit 1; }
command -v git >/dev/null || { echo "Git is required" >&2; exit 1; }
python3 -c 'import sys; assert (3,10) <= sys.version_info < (3,13), "Python 3.10-3.12 is required"'

mkdir -p "$ROOT_DIR/models" "$ROOT_DIR/logs" "$ROOT_DIR/temp"
python3 -m venv "$VENV_DIR"
PYTHON="$VENV_DIR/bin/python"
"$PYTHON" -m pip install --upgrade pip

MODEL="$ROOT_DIR/models/melody_model.safetensors"
CONFIG="$ROOT_DIR/models/melody_model_config.json"
TOKENIZER_GLOB="$ROOT_DIR"/models/alv_tokenizer-*.whl
needs_download=0
[[ -s "$MODEL" && $(wc -c < "$MODEL") -gt 100000000 ]] || needs_download=1
[[ -s "$CONFIG" && $(wc -c < "$CONFIG") -gt 100 ]] || needs_download=1
compgen -G "$TOKENIZER_GLOB" >/dev/null || needs_download=1

if [[ "$needs_download" -eq 1 ]]; then
  DOWNLOAD_DIR="$ROOT_DIR/temp/hf-download"
  if [[ -d "$DOWNLOAD_DIR/.git" ]]; then
    git -C "$DOWNLOAD_DIR" pull --ff-only
  else
    rm -rf "$DOWNLOAD_DIR"
    git clone --depth 1 https://huggingface.co/alvanalrakib/Aurora-Labs "$DOWNLOAD_DIR"
  fi
  cp "$DOWNLOAD_DIR/melody_model.safetensors" "$MODEL.tmp"
  cp "$DOWNLOAD_DIR/melody_model_config.json" "$CONFIG.tmp"
  cp "$DOWNLOAD_DIR"/alv_tokenizer-*.whl "$ROOT_DIR/models/"
  [[ $(wc -c < "$MODEL.tmp") -gt 100000000 ]] || { echo "Downloaded model is incomplete (is Git LFS installed?)" >&2; exit 1; }
  [[ $(wc -c < "$CONFIG.tmp") -gt 100 ]] || { echo "Downloaded config is incomplete" >&2; exit 1; }
  mv "$MODEL.tmp" "$MODEL"
  mv "$CONFIG.tmp" "$CONFIG"
fi

if [[ "$DEVICE" == "cuda" ]]; then
  "$PYTHON" -m pip install torch==2.7.0 --index-url https://download.pytorch.org/whl/cu128
else
  "$PYTHON" -m pip install torch==2.7.0 --index-url https://download.pytorch.org/whl/cpu
fi
"$PYTHON" -m pip install -r "$ROOT_DIR/requirements.txt"
"$PYTHON" -m pip install --upgrade $TOKENIZER_GLOB
"$PYTHON" -c "import torch, numpy, safetensors, mido, fastapi, uvicorn, alv_tokenizer; print('Runtime imports: OK')"

echo "Setup complete. Run: $VENV_DIR/bin/python $ROOT_DIR/main.py"
