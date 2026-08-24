@echo off
setlocal EnableExtensions EnableDelayedExpansion
title AssetsStudio Local Turnaround

set "PROJECT_ROOT=%~dp0"
set "STUDIO_ROOT=%PROJECT_ROOT%studio"
set "LAUNCHER=%PROJECT_ROOT%tools\start_studio_local_generation.ps1"
set "STUDIO_URL=http://127.0.0.1:4173/"

if /I "%~1"=="--help" goto :help
if /I "%~1"=="/?" goto :help

if not exist "%LAUNCHER%" (
    echo [ERROR] Missing launcher: "%LAUNCHER%"
    goto :failed
)

where powershell.exe >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Windows PowerShell was not found.
    goto :failed
)

where npm.cmd >nul 2>nul
if errorlevel 1 (
    echo [ERROR] npm was not found. Install Node.js 22 or newer first.
    goto :failed
)

if not exist "%STUDIO_ROOT%\node_modules\.bin\vite.cmd" (
    echo [SETUP] Studio dependencies are missing. Installing them now...
    pushd "%STUDIO_ROOT%"
    call npm.cmd install --package-lock=false --no-audit --no-fund
    set "NPM_EXIT=%ERRORLEVEL%"
    popd
    if not "!NPM_EXIT!"=="0" (
        echo [ERROR] npm install failed with exit code !NPM_EXIT!.
        goto :failed
    )
)

if /I not "%~1"=="--no-open" (
    start "" /b powershell.exe -NoProfile -WindowStyle Hidden -Command ^
        "$url='%STUDIO_URL%'; for($attempt=0; $attempt -lt 180; $attempt++){ try { $response=Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2; if($response.StatusCode -eq 200 -and $response.Content -match 'AssetsStudio'){ Start-Process $url; exit 0 } } catch {}; Start-Sleep -Seconds 1 }; exit 1"
)

echo [START] AssetsStudio local turnaround stack
echo [URL]   %STUDIO_URL%
echo [STOP]  Press Ctrl+C, then Y, to stop services started here.
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%LAUNCHER%"
set "LAUNCH_EXIT=%ERRORLEVEL%"

if not "%LAUNCH_EXIT%"=="0" (
    echo.
    echo [ERROR] Launcher stopped with exit code %LAUNCH_EXIT%.
    goto :failed
)

endlocal
exit /b 0

:help
echo AssetsStudio local turnaround one-click launcher
echo.
echo Usage:
echo   start-local-generation-studio.bat
echo   start-local-generation-studio.bat --no-open
echo.
echo Optional environment variables:
echo   ASSETSSTUDIO_COMFY_ROOT  Path to the ComfyUI directory
echo   ASSETSSTUDIO_PYTHON      Python command or path used by ComfyUI
echo.
echo Example:
echo   set "ASSETSSTUDIO_COMFY_ROOT=%%USERPROFILE%%\ComfyUI"
echo   set "ASSETSSTUDIO_PYTHON=python.exe"
echo   start-local-generation-studio.bat
echo.
echo The default command starts ComfyUI, the local generation bridge, and
echo Studio, then opens %STUDIO_URL% in the default browser.
endlocal
exit /b 0

:failed
echo.
pause
endlocal
exit /b 1
