@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "DEVICE=cpu"
if /I "%~1"=="--cuda" set "DEVICE=cuda"
if /I not "%~1"=="" if /I not "%~1"=="--cpu" if /I not "%~1"=="--cuda" if /I not "%~1"=="--non-interactive" (
  echo Usage: setup.bat [--cpu^|--cuda] [--non-interactive]
  exit /b 2
)

py -3 --version >nul 2>&1 || (echo [ERROR] Python 3.10-3.12 is required & exit /b 1)
git --version >nul 2>&1 || (echo [ERROR] Git is required & exit /b 1)
py -3 -c "import sys; assert (3,10) <= sys.version_info < (3,13)" || exit /b 1
if not exist models mkdir models || exit /b 1
if not exist logs mkdir logs || exit /b 1
if not exist temp mkdir temp || exit /b 1
if not exist .venv py -3 -m venv .venv || exit /b 1
set "PYTHON=%CD%\.venv\Scripts\python.exe"
"%PYTHON%" -m pip install --upgrade pip || exit /b 1

if not exist "models\melody_model.safetensors" goto download
for %%F in ("models\melody_model.safetensors") do if %%~zF LSS 100000000 goto download
if not exist "models\melody_model_config.json" goto download
dir /b "models\alv_tokenizer-*.whl" >nul 2>&1 || goto download
goto install

:download
if exist "temp\hf-download\.git" (
  git -C "temp\hf-download" pull --ff-only || exit /b 1
) else (
  if exist "temp\hf-download" rmdir /s /q "temp\hf-download"
  git clone --depth 1 https://huggingface.co/alvanalrakib/Aurora-Labs "temp\hf-download" || exit /b 1
)
copy /y "temp\hf-download\melody_model.safetensors" "models\melody_model.safetensors.tmp" >nul || exit /b 1
copy /y "temp\hf-download\melody_model_config.json" "models\melody_model_config.json.tmp" >nul || exit /b 1
copy /y "temp\hf-download\alv_tokenizer-*.whl" "models\" >nul || exit /b 1
for %%F in ("models\melody_model.safetensors.tmp") do if %%~zF LSS 100000000 (echo [ERROR] Incomplete model; install Git LFS & exit /b 1)
move /y "models\melody_model.safetensors.tmp" "models\melody_model.safetensors" >nul || exit /b 1
move /y "models\melody_model_config.json.tmp" "models\melody_model_config.json" >nul || exit /b 1

:install
if /I "%DEVICE%"=="cuda" (
  "%PYTHON%" -m pip install torch==2.7.0 --index-url https://download.pytorch.org/whl/cu128 || exit /b 1
) else (
  "%PYTHON%" -m pip install torch==2.7.0 --index-url https://download.pytorch.org/whl/cpu || exit /b 1
)
"%PYTHON%" -m pip install -r requirements.txt || exit /b 1
for %%F in (models\alv_tokenizer-*.whl) do "%PYTHON%" -m pip install --upgrade "%%F" || exit /b 1
"%PYTHON%" -c "import torch, numpy, safetensors, mido, fastapi, uvicorn, alv_tokenizer; print('Runtime imports: OK')" || exit /b 1
echo Setup complete. Run: .venv\Scripts\python.exe main.py
exit /b 0
