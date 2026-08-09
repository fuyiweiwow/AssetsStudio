@echo off
setlocal
title AssetsStudio local server
cd /d "%~dp0studio"

where node.exe >nul 2>nul
if errorlevel 1 (
  echo [AssetsStudio] Node.js was not found. Install Node.js 22 or newer first.
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

echo [AssetsStudio] Preparing the local Actor preview and starting http://127.0.0.1:4173/
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
