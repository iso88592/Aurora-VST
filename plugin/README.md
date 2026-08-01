# Arura Melody clean-room plugin

This is a source-available clean-room implementation based on the public backend
contract and historical reference screenshots. It is not recovered original
source and is not binary-compatible with the removed legacy build. No compiled
plugin is checked into this repository.

The reconstruction implements model discovery/loading, parameterized generation,
MIDI seed upload, generated MIDI preview output, session persistence, drag-in,
and MIDI export. It uses a native JUCE editor styled from the reference images,
so WebView2 and remote JavaScript are not runtime dependencies.

## Build on Windows

Install Visual Studio 2022 with **Desktop development with C++**, Git, and
CMake 3.22 or newer. From a Developer PowerShell:

```powershell
cmake -S plugin -B build/plugin -G "Visual Studio 17 2022" -A x64
cmake --build build/plugin --config Release --parallel
```

The plugin bundle is produced below
`build/plugin/AruraMelody_artefacts/Release/VST3/Arura Melody.vst3`.
Copy the entire `.vst3` directory to:

```text
C:\Program Files\Common Files\VST3\
```

In Ableton, enable VST3 system folders and rescan while holding `Alt` for a
full rescan. Do not copy only the DLL from inside the bundle.

The Release build statically links the MSVC runtime. The editor is native and
does not require Microsoft Edge WebView2.

## Build on Ubuntu

Install the JUCE development dependencies before configuring:

```bash
sudo apt-get update
sudo apt-get install --yes --no-install-recommends \
  libasound2-dev libcurl4-openssl-dev \
  libfontconfig1-dev libfreetype-dev \
  libx11-dev libxcomposite-dev libxcursor-dev libxext-dev \
  libxinerama-dev libxrandr-dev libxrender-dev
cmake -S plugin -B build/plugin -DCMAKE_BUILD_TYPE=Release
cmake --build build/plugin --config Release --parallel 2
```

WebKitGTK and OpenGL development packages are intentionally unnecessary: the
plugin uses a native JUCE editor, disables `JUCE_WEB_BROWSER`, and does not link
the JUCE OpenGL module.

The editor always opens before attempting network access. Its welcome screen
tries the configured backend three times, reports API errors, and provides
**Retry Now** and **Open Log** controls. On Windows the diagnostic log is stored
at `%APPDATA%\AruraMelody\plugin.log`. Backend connectivity never participates
in VST3 scanning or processor construction.

The VST3 release is only the native plugin client. It does not bundle or launch
Python or the model server. On Windows, run `setup.bat --cpu` from the repository
and start `.venv\Scripts\python.exe main.py` before connecting the plugin.
Python 3.10, 3.11, and 3.12 are supported.

## CI and releases

`.github/workflows/plugin.yml` builds from source on Windows and Linux for pull
requests, manual runs, and version tags. Ordinary pushes to `main` do not build,
avoiding a duplicate matrix run immediately before tagging. The workflow checks
the generated VST3 bundle metadata and uploads the built bundle. A tag such as
`v0.2.0` additionally creates or updates a GitHub Release and attaches
`AruraMelody-Windows-x64.zip` and
`AruraMelody-Linux-x86_64.tar.gz`. This also works when the release was created
first in the GitHub UI. CI artifacts and tagged release downloads are the only
distributed binaries; none are committed to the repository.
