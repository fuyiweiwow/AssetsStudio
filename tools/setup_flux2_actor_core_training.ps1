[CmdletBinding()]
param(
    [string]$ComfyRoot,
    [string]$Python,
    [string]$DiffSynthRoot,
    [switch]$SkipModelDownload
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

function Find-ComfyRoot {
    param([string]$Configured)
    $candidates = @(
        $Configured,
        $env:ASSETSSTUDIO_COMFY_ROOT,
        (Join-Path (Split-Path $projectRoot -Parent) "ComfyUI"),
        (Join-Path $env:USERPROFILE "ComfyUI")
    ) | Where-Object { $_ }
    foreach ($candidate in $candidates) {
        $resolved = Resolve-Path -LiteralPath $candidate -ErrorAction SilentlyContinue
        if ($resolved -and (Test-Path -LiteralPath (Join-Path $resolved "main.py"))) {
            return $resolved.Path
        }
    }
    throw "ComfyUI was not found. Pass -ComfyRoot or set ASSETSSTUDIO_COMFY_ROOT."
}

function Find-Python {
    param([string]$Configured, [string]$ResolvedComfyRoot)
    $candidates = @(
        $Configured,
        $env:ASSETSSTUDIO_PYTHON,
        (Join-Path $ResolvedComfyRoot ".venv\Scripts\python.exe"),
        (Join-Path $ResolvedComfyRoot "venv\Scripts\python.exe")
    ) | Where-Object { $_ }
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
        $command = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($command) { return $command.Source }
    }
    $fallback = Get-Command python -ErrorAction SilentlyContinue
    if ($fallback) { return $fallback.Source }
    throw "Python was not found. Pass -Python or set ASSETSSTUDIO_PYTHON."
}

$ComfyRoot = Find-ComfyRoot $ComfyRoot
$Python = Find-Python $Python $ComfyRoot

if (-not $DiffSynthRoot) {
    $DiffSynthRoot = $env:ASSETSSTUDIO_DIFFSYNTH_ROOT
}
if (-not $DiffSynthRoot) {
    $DiffSynthRoot = Join-Path $projectRoot "workspace\runtime\DiffSynth-Studio"
}
if (-not (Test-Path -LiteralPath (Join-Path $DiffSynthRoot "pyproject.toml"))) {
    New-Item -ItemType Directory -Force -Path (Split-Path $DiffSynthRoot -Parent) | Out-Null
    git clone --depth 1 https://gitee.com/mirrors/diffsynth-studio.git $DiffSynthRoot
    if ($LASTEXITCODE -ne 0) { throw "Unable to clone the DiffSynth-Studio source mirror." }
}
$DiffSynthRoot = (Resolve-Path -LiteralPath $DiffSynthRoot).Path

$uv = Get-Command uv -ErrorAction SilentlyContinue
if ($uv) {
    & $uv.Source pip install --python $Python --no-deps -e $DiffSynthRoot
    if ($LASTEXITCODE -ne 0) { throw "Unable to register DiffSynth-Studio in the selected Python environment." }
    & $uv.Source pip install --python $Python imageio imageio-ffmpeg ftfy pandas accelerate peft datasets
} else {
    & $Python -m pip install --no-deps -e $DiffSynthRoot
    if ($LASTEXITCODE -ne 0) { throw "Unable to register DiffSynth-Studio in the selected Python environment." }
    & $Python -m pip install imageio imageio-ffmpeg ftfy pandas accelerate peft datasets
}
if ($LASTEXITCODE -ne 0) { throw "Unable to install DiffSynth training dependencies." }

$requiredComfyFiles = @(
    (Join-Path $ComfyRoot "models\text_encoders\qwen_3_4b.safetensors"),
    (Join-Path $ComfyRoot "models\vae\flux2-vae.safetensors")
)
$missing = $requiredComfyFiles | Where-Object { -not (Test-Path -LiteralPath $_ -PathType Leaf) }
if ($missing) {
    throw "The reusable FLUX.2 text encoder or VAE is missing:`n$($missing -join "`n")"
}

$modelRoot = Join-Path $projectRoot "workspace\models\modelscope\black-forest-labs\FLUX.2-klein-base-4B"
if (-not $SkipModelDownload) {
    New-Item -ItemType Directory -Force -Path $modelRoot | Out-Null
    & $Python -m modelscope.cli.cli download black-forest-labs/FLUX.2-klein-base-4B `
        --local-dir $modelRoot --max-workers 4 `
        --include "transformer/*" "tokenizer/*" "model_index.json"
    if ($LASTEXITCODE -ne 0) { throw "ModelScope download failed." }
}

$revision = git -C $DiffSynthRoot rev-parse HEAD
Write-Output "ComfyRoot=$ComfyRoot"
Write-Output "Python=$Python"
Write-Output "DiffSynthRoot=$DiffSynthRoot"
Write-Output "DiffSynthRevision=$revision"
Write-Output "ModelRoot=$modelRoot"
