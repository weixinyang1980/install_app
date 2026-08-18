$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$env:ELECTRON_MIRROR = "https://npmmirror.com/mirrors/electron/"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd `"$root\backend`"; python -m uvicorn app.main:app --host 127.0.0.1 --port 8765"
Start-Sleep -Seconds 2
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd `"$root\admin`"; if (-not (Test-Path node_modules)) { npm install }; npm run dev"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$env:ELECTRON_MIRROR='https://npmmirror.com/mirrors/electron/'; cd `"$root\desktop`"; if (-not (Test-Path node_modules)) { npm install }; npm run dev"
Write-Host "装了吗正在开门：后端 8765 / 后台 5174 / 桌面 Electron"
