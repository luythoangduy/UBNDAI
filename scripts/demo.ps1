$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "Không tìm thấy .venv. Hãy cài dependencies trước bằng: py -3.11 -m venv .venv"
}

Push-Location (Join-Path $projectRoot "frontend")
try {
    & npm.cmd ci
    & npm.cmd run build
} finally {
    Pop-Location
}

Push-Location $projectRoot
try {
    & $pythonExe scripts\seed_db.py
    Write-Host "Demo: http://127.0.0.1:8000/citizen và http://127.0.0.1:8000/officer"
    & $pythonExe -m uvicorn src.main:app --host 127.0.0.1 --port 8000
} finally {
    Pop-Location
}
