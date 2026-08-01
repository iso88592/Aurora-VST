#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${AURORA_PYTHON:-$ROOT_DIR/.venv/bin/python}"
BASE_URL="${AURORA_URL:-http://127.0.0.1:8000}"
SERVER_PID=""

cleanup() {
  if [[ -n "$SERVER_PID" ]]; then kill "$SERVER_PID" 2>/dev/null || true; wait "$SERVER_PID" 2>/dev/null || true; fi
}
trap cleanup EXIT

[[ -x "$PYTHON" ]] || { echo "Missing virtual environment; run ./setup.sh --cpu" >&2; exit 1; }
if ! curl -fsS "$BASE_URL/health" >/dev/null 2>&1; then
  "$PYTHON" "$ROOT_DIR/main.py" --host 127.0.0.1 --port 8000 >"$ROOT_DIR/logs/smoke-server.log" 2>&1 &
  SERVER_PID=$!
  for _ in {1..60}; do curl -fsS "$BASE_URL/health" >/dev/null 2>&1 && break; sleep 1; done
fi
curl -fsS "$BASE_URL/health" >/dev/null

MODELS_JSON="$(curl -fsS "$BASE_URL/api/v1/models")"
MODEL="$(printf '%s' "$MODELS_JSON" | "$PYTHON" -c 'import json,sys; d=json.load(sys.stdin)["models"]; usable=[n for n,v in d.items() if v["file_exists"] and v["supported"]]; assert len(usable)==1, usable; print(usable[0])')"
curl -fsS -H 'Content-Type: application/json' -d "{\"model_name\":\"$MODEL\"}" "$BASE_URL/api/v1/models/load" >/dev/null
RESULT="$(curl -fsS -H 'Content-Type: application/json' -d "{\"model_name\":\"$MODEL\",\"params\":{\"max_length\":32},\"num_generations\":1}" "$BASE_URL/api/v1/generate")"
printf '%s' "$RESULT" | "$PYTHON" -c 'import base64,io,json,sys,mido; d=json.load(sys.stdin); b=base64.b64decode(d["melodies"][0]["midi_base64"]); assert b; midi=mido.MidiFile(file=io.BytesIO(b)); msgs=[m for t in midi.tracks for m in t]; assert any(m.type=="note_on" and m.velocity>0 for m in msgs); assert any(m.type=="note_off" or (m.type=="note_on" and m.velocity==0) for m in msgs)'
curl -fsS -H 'Content-Type: application/json' -d "{\"model_name\":\"$MODEL\"}" "$BASE_URL/api/v1/models/unload" >/dev/null
echo "Smoke test passed for $MODEL"
