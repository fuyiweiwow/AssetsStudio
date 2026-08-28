param(
    [string]$BundleRoot,
    [string]$ComfyRoot,
    [string]$OutputRoot,
    [switch]$ColdStart
)

$ErrorActionPreference = "Stop"
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$projectParent = Split-Path -Parent $projectRoot
$setupScript = Join-Path $PSScriptRoot "setup_actor_core_production.ps1"
$gateScript = Join-Path $PSScriptRoot "model_test\run_actor_core_hardware_gate.py"

function Resolve-ComfyRoot([string]$RequestedPath) {
    $candidates = @(
        $RequestedPath,
        $env:ASSETSSTUDIO_COMFY_ROOT,
        (Join-Path $projectParent "ComfyUI"),
        (Join-Path $env:USERPROFILE "ComfyUI")
    )
    foreach ($candidate in $candidates) {
        if ([string]::IsNullOrWhiteSpace($candidate)) { continue }
        $resolved = [System.IO.Path]::GetFullPath($candidate)
        if (Test-Path -LiteralPath (Join-Path $resolved "main.py") -PathType Leaf) { return $resolved }
    }
    throw "ComfyUI was not found. Pass -ComfyRoot or set ASSETSSTUDIO_COMFY_ROOT."
}

function Resolve-BundleRoot([string]$RequestedPath) {
    $candidates = @(
        $RequestedPath,
        $env:ASSETSSTUDIO_ACTOR_CORE_BUNDLE,
        (Join-Path $projectRoot "workspace\portability\actor_core_v6_rtx3060_bundle"),
        (Join-Path $projectParent "actor_core_v6_rtx3060_bundle")
    )
    foreach ($candidate in $candidates) {
        if ([string]::IsNullOrWhiteSpace($candidate)) { continue }
        $resolved = [System.IO.Path]::GetFullPath($candidate)
        if (Test-Path -LiteralPath (Join-Path $resolved "manifest.json") -PathType Leaf) { return $resolved }
    }
    throw "Actor Core validation bundle was not found. Pass -BundleRoot or set ASSETSSTUDIO_ACTOR_CORE_BUNDLE."
}

function Resolve-Python([string]$ResolvedComfyRoot) {
    $candidates = @(
        (Join-Path $ResolvedComfyRoot ".venv\Scripts\python.exe"),
        (Join-Path $ResolvedComfyRoot "venv\Scripts\python.exe"),
        "python.exe"
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { return (Resolve-Path -LiteralPath $candidate).Path }
        $command = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($null -ne $command -and $command.CommandType -eq "Application") { return $command.Source }
    }
    throw "Python was not found in ComfyUI or PATH."
}

function Test-ComfyReady() {
    try {
        Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:8190/system_stats" -TimeoutSec 2 | Out-Null
        return $true
    }
    catch { return $false }
}

$BundleRoot = Resolve-BundleRoot $BundleRoot
$ComfyRoot = Resolve-ComfyRoot $ComfyRoot
$manifest = Get-Content -LiteralPath (Join-Path $BundleRoot "manifest.json") -Raw -Encoding UTF8 | ConvertFrom-Json
if ($manifest.schema -ne "assetsstudio_actor_core_rtx3060_bundle_v1") { throw "Unsupported Actor Core bundle schema." }

& $setupScript -ComfyRoot $ComfyRoot -BundleRoot $BundleRoot

$wasRunning = Test-ComfyReady
if ($ColdStart -and $wasRunning) {
    throw "ColdStart requires ComfyUI port 8190 to be stopped before this command. Stop the existing local-generation process and retry."
}
$coldStartObserved = -not $wasRunning
if (-not $wasRunning) {
    $python = Resolve-Python $ComfyRoot
    $logRoot = Join-Path $ComfyRoot "logs"
    New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
    $comfyArgs = @(
        "main.py", "--lowvram", "--disable-async-offload", "--disable-pinned-memory",
        "--cache-none", "--preview-method", "none", "--reserve-vram", "1.5",
        "--listen", "127.0.0.1", "--port", "8190"
    )
    Start-Process -FilePath $python -ArgumentList $comfyArgs -WorkingDirectory $ComfyRoot -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $logRoot "actor_core_3060_gate_stdout.log") `
        -RedirectStandardError (Join-Path $logRoot "actor_core_3060_gate_stderr.log") | Out-Null
    $ready = $false
    foreach ($attempt in 1..120) {
        if (Test-ComfyReady) { $ready = $true; break }
        Start-Sleep -Seconds 1
    }
    if (-not $ready) { throw "ComfyUI did not become ready on port 8190." }
}

$python = Resolve-Python $ComfyRoot
$source = Join-Path $BundleRoot $manifest.gate.source
$loraRelative = "assetsstudio\$($manifest.lora.filename)"
if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $OutputRoot = Join-Path $projectRoot "workspace\hardware_validation\actor_core\runs"
}
$qualificationRecord = Join-Path $projectRoot "workspace\hardware_validation\actor_core\rtx3060_qualification.json"
$gateArgs = @(
    $gateScript,
    "--source", $source,
    "--output-root", $OutputRoot,
    "--seed", "$($manifest.gate.seed)",
    "--lora", $loraRelative,
    "--lora-strength", "$($manifest.gate.lora_strength)",
    "--expected-lora-sha256", $manifest.lora.sha256,
    "--qualification-record", $qualificationRecord
)
if ($coldStartObserved) { $gateArgs += "--cold-start-observed" }
& $python @gateArgs
if ($LASTEXITCODE -ne 0) { throw "RTX 3060 Actor Core Gate failed with exit code $LASTEXITCODE." }

$qualification = Get-Content -LiteralPath $qualificationRecord -Raw -Encoding UTF8 | ConvertFrom-Json
Write-Output "ASSETSSTUDIO_RTX3060_GATE_$($qualification.status.ToUpperInvariant())"
Write-Output "QualificationRecord=$qualificationRecord"
Write-Output "Report=$($qualification.report)"
