$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not (Test-Path (Join-Path $Root '.venv\Scripts\python.exe'))) { throw '.venv is missing. Create the project environment first.' }
if (-not (Test-Path (Join-Path $Root 'app\frontend\dist\index.html'))) { throw 'Frontend dist is missing. Run the frontend build first.' }
$env:PYTHONPATH = Join-Path $Root 'src'
$env:APP_HOST = if ($env:APP_HOST) { $env:APP_HOST } else { '127.0.0.1' }
$env:APP_PORT = if ($env:APP_PORT) { $env:APP_PORT } else { '8000' }
$env:PYTHONPATH = "$Root\src;$env:PYTHONPATH"
Start-Process "http://$($env:APP_HOST):$($env:APP_PORT)"
& (Join-Path $Root '.venv\Scripts\python.exe') -m uvicorn app.api.main:app --host $env:APP_HOST --port $env:APP_PORT
