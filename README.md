# Aurora VST backend

Aurora is a local FastAPI service that loads the supplied `melody_model` checkpoint and returns generated MIDI. This repository is an incomplete prototype; the currently supported path is the HTTP backend on Python 3.10-3.12.

## Install

The setup scripts create an isolated `.venv`, reuse a valid existing model download, install every runtime dependency (including PyTorch, NumPy, safetensors and mido), install the supplied tokenizer wheel, and verify all imports before reporting success.

Linux/macOS (CPU):

```bash
./setup.sh --cpu
```

Windows Command Prompt (CPU):

```bat
setup.bat --cpu
```

Pass `--cuda` for the pinned CUDA 12.8 PyTorch build. Run either script again safely; files that pass the size checks are reused. Internet access, Git, Git LFS, and roughly 5 GB of free space are needed for a first install.

Development tools are separate:

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
```

## Run and verify

```bash
.venv/bin/python main.py
./scripts/smoke-test.sh
```

On Windows, run `.venv\Scripts\python.exe main.py`, then `powershell -ExecutionPolicy Bypass -File scripts\smoke-test.ps1` in another terminal.

The API is at <http://localhost:8000>, with interactive documentation at `/docs`. Clients must discover the canonical model identifier instead of guessing it:

```bash
curl http://localhost:8000/api/v1/models
curl -H "Content-Type: application/json" -d '{"model_name":"melody_model"}' http://localhost:8000/api/v1/models/load
```

Important paths are independent of the caller's working directory. Override them with `AURORA_CONFIG`, `AURORA_MODELS_DIR`, `AURORA_LOG_DIR`, and `AURORA_TEMP_DIR`, or pass `--config` to `main.py`/`start_server.py`.

## VST3 status

No compiled VST is stored in this repository. The clean-room plugin source and
local build instructions are under [`plugin/`](plugin/). GitHub Actions builds
the VST3 from that source for each plugin change and exposes the resulting
bundles as workflow artifacts. Version tags additionally publish the Windows
x64 bundle as a downloadable GitHub Release asset.

Users should install a CI/release artifact or build from source; do not expect a
plugin under `Assets/`. The HTTP API remains independently usable on every
supported backend platform.

## Troubleshooting

- An incomplete model usually means Git LFS was missing during clone. Install Git LFS and rerun setup.
- Startup intentionally fails if no matching `.safetensors` and JSON config are present in `models/`.
- Load failures distinguish unknown/missing files, unsupported model types, missing tokenizer, and checkpoint/device-memory errors.
- Generated MIDI files are stored under `temp/` (or `AURORA_TEMP_DIR`).
