@echo off
setlocal
title AssetsStudio local server
set "STUDIO_URL=http://127.0.0.1:4173/"
cd /d "%~dp0studio"

rem Reusing an existing Studio server makes this launcher safe to double-click
rem more than once. Check the page marker before doing any expensive rebuild.
powershell.exe -NoProfile -Command "$ErrorActionPreference='SilentlyContinue'; $r=Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 '%STUDIO_URL%'; if ($r.StatusCode -eq 200 -and $r.Content -match '<title>AssetsStudio') { exit 0 } else { exit 1 }" >nul 2>nul
if not errorlevel 1 (
  echo [AssetsStudio] Studio is already running at %STUDIO_URL%
  if /i not "%~1"=="--no-open" start "" "%STUDIO_URL%"
  exit /b 0
)

rem Refuse an unrelated process on the reserved port with a useful message.
powershell.exe -NoProfile -Command "$c=New-Object Net.Sockets.TcpClient; try { $c.Connect('127.0.0.1',4173); exit 0 } catch { exit 1 } finally { $c.Dispose() }" >nul 2>nul
if not errorlevel 1 (
  echo [AssetsStudio] Port 4173 is in use by another program.
  echo [AssetsStudio] Close that program or free the port, then run this file again.
  pause
  exit /b 1
)

where node.exe >nul 2>nul
if errorlevel 1 (
  echo [AssetsStudio] Node.js was not found. Install Node.js 22 or newer first.
  pause
  exit /b 1
)

where npm.cmd >nul 2>nul
if errorlevel 1 (
  echo [AssetsStudio] npm.cmd was not found next to Node.js. Repair the Node.js installation first.
  pause
  exit /b 1
)

if not exist "node_modules\.bin\vite.cmd" (
  echo [AssetsStudio] Installing frontend dependencies...
  call npm.cmd install --no-audit --no-fund
  if errorlevel 1 (
    echo [AssetsStudio] Dependency installation failed.
    pause
    exit /b 1
  )
)

echo [AssetsStudio] Preparing the local Actor preview and starting %STUDIO_URL%
echo [AssetsStudio] Keep this window open. Closing it stops the local page.
if /i "%~1"=="--no-open" (
  call npm.cmd run dev
) else (
  call npm.cmd run dev -- --open
)

if errorlevel 1 (
  echo [AssetsStudio] The local server stopped with an error.
  pause
)
