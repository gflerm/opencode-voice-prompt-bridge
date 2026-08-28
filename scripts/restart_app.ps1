# Restart the OpenCode Voice Prompt Bridge (single windowless instance).
#
# Kills any running app.py instances, then starts a fresh one with the
# tray icon. The model takes ~15 s to load before dictation is live -
# check the tray tooltip or data\app.log.

$root = Split-Path -Parent $PSScriptRoot
$pythonw = Join-Path $root ".venv\Scripts\pythonw.exe"
$app = Join-Path $root "src\app.py"

if (-not (Test-Path $pythonw)) {
    Write-Error "pythonw.exe not found at $pythonw - create the venv first"
    exit 1
}

Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
    Where-Object { $_.CommandLine -like "*app.py*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

Start-Sleep -Milliseconds 800
Start-Process -FilePath $pythonw -ArgumentList ('"{0}"' -f $app) -WorkingDirectory $root
