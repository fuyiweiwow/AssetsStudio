param(
    [string]$ComfyRoot,
    [string]$Python,
    [int]$ComfyPort = 8190,
    [switch]$CheckEnvironment
)

$ErrorActionPreference = "Stop"
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$studioRoot = Join-Path $projectRoot "studio"
$bridgeScript = Join-Path $projectRoot "tools\model_test\studio_local_generation_api.py"
$projectParent = Split-Path -Parent $projectRoot

function Resolve-ComfyRoot([string]$RequestedPath) {
    if (-not [string]::IsNullOrWhiteSpace($RequestedPath)) {
        $resolved = [System.IO.Path]::GetFullPath($RequestedPath)
        if (Test-Path -LiteralPath (Join-Path $resolved "main.py") -PathType Leaf) {
            return $resolved
        }
        throw "ComfyUI was not found at '$resolved'. Expected main.py in that directory."
    }

    $candidates = @(
        $env:ASSETSSTUDIO_COMFY_ROOT,
        (Join-Path $projectParent "ComfyUI"),
        (Join-Path $env:USERPROFILE "ComfyUI")
    )
    foreach ($candidate in $candidates) {
        if ([string]::IsNullOrWhiteSpace($candidate)) {
            continue
        }
        $resolved = [System.IO.Path]::GetFullPath($candidate)
        if (Test-Path -LiteralPath (Join-Path $resolved "main.py") -PathType Leaf) {
            return $resolved
        }
    }
    throw "ComfyUI was not found. Pass -ComfyRoot, set ASSETSSTUDIO_COMFY_ROOT, or place ComfyUI beside AssetsStudio/in the current user profile."
}

function Resolve-ComfyPython([string]$RequestedPath, [string]$ResolvedComfyRoot) {
    function Resolve-PythonCandidate([string]$Candidate) {
        if ([string]::IsNullOrWhiteSpace($Candidate)) {
            return $null
        }
        if (Test-Path -LiteralPath $Candidate -PathType Leaf) {
            return (Resolve-Path -LiteralPath $Candidate).Path
        }
        $command = Get-Command $Candidate -ErrorAction SilentlyContinue
        if ($null -ne $command -and $command.CommandType -eq "Application") {
            return $command.Source
        }
        return $null
    }

    $requestedValues = @(
        @{ Source = "-Python"; Value = $RequestedPath },
        @{ Source = "ASSETSSTUDIO_PYTHON"; Value = $env:ASSETSSTUDIO_PYTHON }
    )
    foreach ($requested in $requestedValues) {
        if ([string]::IsNullOrWhiteSpace($requested.Value)) {
            continue
        }
        $resolved = Resolve-PythonCandidate $requested.Value
        if ($null -ne $resolved) {
            return $resolved
        }
        throw "Python configured by $($requested.Source) was not found at '$($requested.Value)'."
    }

    $candidates = @(
        (Join-Path $ResolvedComfyRoot ".venv\Scripts\python.exe"),
        (Join-Path $ResolvedComfyRoot "venv\Scripts\python.exe"),
        (Join-Path $ResolvedComfyRoot "python_embeded\python.exe"),
        (Join-Path $ResolvedComfyRoot "python.exe"),
        $(if (-not [string]::IsNullOrWhiteSpace($env:VIRTUAL_ENV)) {
            Join-Path $env:VIRTUAL_ENV "Scripts\python.exe"
        }),
        $(if (-not [string]::IsNullOrWhiteSpace($env:CONDA_PREFIX)) {
            Join-Path $env:CONDA_PREFIX "python.exe"
        }),
        "python.exe",
        "python3.exe"
    )
    foreach ($candidate in $candidates) {
        $resolved = Resolve-PythonCandidate $candidate
        if ($null -ne $resolved) {
            return $resolved
        }
    }
    throw "ComfyUI Python was not found. Pass -Python, set ASSETSSTUDIO_PYTHON, activate a venv/conda environment, add Python to PATH, or create a ComfyUI virtual environment."
}

$ComfyRoot = Resolve-ComfyRoot $ComfyRoot
$Python = Resolve-ComfyPython $Python $ComfyRoot
$logRoot = Join-Path $ComfyRoot "logs"
$bridgePort = 8765
New-Item -ItemType Directory -Path $logRoot -Force | Out-Null

$requiredFiles = @(
    (Join-Path $ComfyRoot "models\diffusion_models\flux-2-klein-4b-fp8.safetensors"),
    (Join-Path $ComfyRoot "models\text_encoders\qwen_3_4b.safetensors"),
    (Join-Path $ComfyRoot "models\vae\flux2-vae.safetensors"),
    $bridgeScript
)
foreach ($requiredFile in $requiredFiles) {
    if (-not (Test-Path -LiteralPath $requiredFile -PathType Leaf)) {
        throw "Required local-generation file is missing: $requiredFile"
    }
}

if ($CheckEnvironment) {
    Write-Output "ASSETSSTUDIO_LOCAL_ENVIRONMENT_READY"
    Write-Output "ComfyRoot=$ComfyRoot"
    Write-Output "Python=$Python"
    exit 0
}

function Test-LocalEndpoint([string]$Url) {
    try {
        Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2 | Out-Null
        return $true
    }
    catch {
        return $false
    }
}

function Test-CurrentBridge() {
    try {
        $payload = Invoke-RestMethod -Uri "http://127.0.0.1:$bridgePort/api/health" -TimeoutSec 2
        return [bool]$payload.profile_registry -and [int]$payload.style_profiles -ge 1 -and [int]$payload.actor_profiles -ge 1
    }
    catch {
        return $false
    }
}

$startedComfy = $null
$startedBridge = $null
try {
    if (-not (Test-LocalEndpoint "http://127.0.0.1:$ComfyPort/system_stats")) {
        $comfyArgs = @(
            "main.py",
            "--lowvram",
            "--disable-async-offload",
            "--disable-pinned-memory",
            "--cache-none",
            "--preview-method", "none",
            "--reserve-vram", "1.5",
            "--listen", "127.0.0.1",
            "--port", "$ComfyPort"
        )
        $startedComfy = Start-Process -FilePath $Python -ArgumentList $comfyArgs -WorkingDirectory $ComfyRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logRoot "studio_flux2_stdout.log") -RedirectStandardError (Join-Path $logRoot "studio_flux2_stderr.log") -PassThru
        $ready = $false
        for ($attempt = 0; $attempt -lt 60; $attempt++) {
            if (Test-LocalEndpoint "http://127.0.0.1:$ComfyPort/system_stats") {
                $ready = $true
                break
            }
            Start-Sleep -Seconds 1
        }
        if (-not $ready) {
            throw "ComfyUI did not become ready on port $ComfyPort"
        }
    }

    $env:ASSETSSTUDIO_COMFY_ROOT = $ComfyRoot
    $env:ASSETSSTUDIO_COMFY_URL = "http://127.0.0.1:$ComfyPort"
    if (-not (Test-CurrentBridge)) {
        $startedBridge = Start-Process -FilePath $Python -ArgumentList @($bridgeScript, "--host", "127.0.0.1", "--port", "$bridgePort") -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logRoot "studio_bridge_stdout.log") -RedirectStandardError (Join-Path $logRoot "studio_bridge_stderr.log") -PassThru
    }

    $bridgeReady = $false
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        if (Test-CurrentBridge) {
            $bridgeReady = $true
            break
        }
        Start-Sleep -Milliseconds 500
    }
    if (-not $bridgeReady) {
        throw "Current AssetsStudio profile-aware bridge did not become ready on port $bridgePort. Close any older launcher using 8765, then retry."
    }

    Push-Location $studioRoot
    try {
        # The checked-in registry is rebuilt by the validation workflow. Start
        # Vite directly so launching the UI never mutates production profiles.
        npm exec vite -- --host 127.0.0.1 --port 4173
        if ($LASTEXITCODE -ne 0) {
            throw "Studio Vite stopped with exit code $LASTEXITCODE"
        }
    }
    finally {
        Pop-Location
    }
}
finally {
    if ($startedBridge -and (Get-Process -Id $startedBridge.Id -ErrorAction SilentlyContinue)) {
        Stop-Process -Id $startedBridge.Id -Force
    }
    if ($startedComfy -and (Get-Process -Id $startedComfy.Id -ErrorAction SilentlyContinue)) {
        Stop-Process -Id $startedComfy.Id -Force
    }
}
