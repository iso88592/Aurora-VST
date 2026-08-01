$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$BaseUrl = if ($env:AURORA_URL) { $env:AURORA_URL } else { "http://127.0.0.1:8000" }
if (-not (Test-Path $Python)) { throw "Missing virtual environment; run setup.bat --cpu" }
$models = Invoke-RestMethod "$BaseUrl/api/v1/models"
$usable = @($models.models.PSObject.Properties | Where-Object { $_.Value.file_exists -and $_.Value.supported })
if ($usable.Count -ne 1) { throw "Expected exactly one usable model" }
$name = $usable[0].Name
$body = @{ model_name = $name } | ConvertTo-Json
Invoke-RestMethod "$BaseUrl/api/v1/models/load" -Method Post -ContentType "application/json" -Body $body | Out-Null
$request = @{ model_name = $name; params = @{ max_length = 32 }; num_generations = 1 } | ConvertTo-Json -Depth 3
$result = Invoke-RestMethod "$BaseUrl/api/v1/generate" -Method Post -ContentType "application/json" -Body $request
$midi = [Convert]::FromBase64String($result.melodies[0].midi_base64)
if ($midi.Length -eq 0) { throw "Generated MIDI is empty" }
$tmp = Join-Path $env:TEMP "aurora-smoke.mid"
[IO.File]::WriteAllBytes($tmp, $midi)
& $Python -c "import mido,sys; m=mido.MidiFile(sys.argv[1]); x=[a for t in m.tracks for a in t]; assert any(a.type=='note_on' and a.velocity for a in x); assert any(a.type=='note_off' or (a.type=='note_on' and not a.velocity) for a in x)" $tmp
Invoke-RestMethod "$BaseUrl/api/v1/models/unload" -Method Post -ContentType "application/json" -Body $body | Out-Null
Write-Host "Smoke test passed for $name"
