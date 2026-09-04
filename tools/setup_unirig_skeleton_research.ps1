param(
    [string]$RuntimeRoot,
    [string]$SourceRoot,
    [string]$ModelRoot,
    [string]$VenvRoot,
    [switch]$CheckOnly,
    [switch]$SkipWeights
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$projectParent = Split-Path -Parent $projectRoot
$sourceRevision = "6793c6640ff01c8fb389f3993434124bb43d2933"

function Resolve-ExistingDirectory([string[]]$Candidates, [string]$Marker) {
    foreach ($candidate in $Candidates) {
        if ([string]::IsNullOrWhiteSpace($candidate)) { continue }
        $resolved = [System.IO.Path]::GetFullPath($candidate)
        if (Test-Path -LiteralPath (Join-Path $resolved $Marker) -PathType Leaf) { return $resolved }
    }
    return $null
}

function Invoke-Native([string]$Program, [string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Command failed ($LASTEXITCODE): $Program $($Arguments -join ' ')" }
}

if ([string]::IsNullOrWhiteSpace($RuntimeRoot)) {
    $RuntimeRoot = if ($env:ASSETSSTUDIO_ACTOR_CORE_V2_RUNTIME) {
        $env:ASSETSSTUDIO_ACTOR_CORE_V2_RUNTIME
    } else {
        Join-Path $projectRoot "workspace\runtime\actor_core_v2"
    }
}
$RuntimeRoot = [System.IO.Path]::GetFullPath($RuntimeRoot)

$SourceRoot = Resolve-ExistingDirectory @(
    $SourceRoot,
    $env:ASSETSSTUDIO_UNIRIG_SOURCE,
    (Join-Path $RuntimeRoot "source\UniRig"),
    (Join-Path $projectParent "UniRig")
) "run.py"
if ([string]::IsNullOrWhiteSpace($SourceRoot)) {
    if ($CheckOnly) { throw "UniRig source not found through explicit path, environment, workspace, or adjacent directory." }
    $SourceRoot = Join-Path $RuntimeRoot "source\UniRig"
    $downloadRoot = Join-Path $RuntimeRoot "downloads"
    $archive = Join-Path $downloadRoot "UniRig-$sourceRevision.zip"
    $extractRoot = Join-Path $downloadRoot "UniRig-$sourceRevision"
    New-Item -ItemType Directory -Path $downloadRoot -Force | Out-Null
    $curl = (Get-Command curl.exe -ErrorAction Stop).Source
    Invoke-Native $curl @("--location", "--fail", "--retry", "5", "--retry-delay", "2", "--silent", "--show-error", "--output", $archive, "https://codeload.github.com/VAST-AI-Research/UniRig/zip/$sourceRevision")
    if (Test-Path -LiteralPath $extractRoot) { Remove-Item -LiteralPath $extractRoot -Recurse -Force }
    Expand-Archive -LiteralPath $archive -DestinationPath $downloadRoot -Force
    Move-Item -LiteralPath $extractRoot -Destination $SourceRoot
    Set-Content -LiteralPath (Join-Path $SourceRoot "ASSETSSTUDIO_SOURCE_REVISION.txt") -Value $sourceRevision -Encoding ASCII
}

if ([string]::IsNullOrWhiteSpace($VenvRoot)) { $VenvRoot = Join-Path $RuntimeRoot "unirig_venv_py311" }
$venvPython = Join-Path $VenvRoot "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
    if ($CheckOnly) { throw "UniRig Python 3.11 environment not found: $VenvRoot" }
    $uv = (Get-Command uv.exe -ErrorAction Stop).Source
    Invoke-Native $uv @("venv", "--python", "3.11", "--seed", "--quiet", $VenvRoot)
}

if (-not $CheckOnly) {
    $uv = (Get-Command uv.exe -ErrorAction Stop).Source
    Invoke-Native $uv @("pip", "install", "--python", $venvPython, "--quiet", "--index-url", "https://download.pytorch.org/whl/cu128", "torch==2.7.0", "torchvision==0.22.0")
    Invoke-Native $uv @("pip", "install", "--python", $venvPython, "--quiet", "numpy==1.26.4", "transformers==4.51.3", "python-box", "einops", "omegaconf", "pytorch-lightning==2.6.5", "lightning==2.6.5", "addict", "timm", "fast-simplification", "bpy==4.2.0", "trimesh", "huggingface_hub", "wandb", "modelscope")
    Invoke-Native $venvPython @((Join-Path $projectRoot "tools\model_test\patch_unirig_skeleton_runtime.py"), "--source", $SourceRoot)
}

function Test-UniRigModelRoot([string]$Candidate) {
    if ([string]::IsNullOrWhiteSpace($Candidate)) { return $false }
    $checkpoint = Join-Path ([System.IO.Path]::GetFullPath($Candidate)) "skeleton\articulation-xl_quantization_256\model.ckpt"
    return (Test-Path -LiteralPath $checkpoint -PathType Leaf) -and ((Get-Item -LiteralPath $checkpoint).Length -gt 1400000000)
}

foreach ($candidate in @(
    $ModelRoot,
    $env:ASSETSSTUDIO_UNIRIG_MODEL,
    (Join-Path $projectRoot "workspace\models\modelscope\VAST-AI-Research\UniRig-skeleton"),
    (Join-Path $projectRoot "workspace\models\modelscope\VAST-AI-Research\UniRig"),
    (Join-Path $env:USERPROFILE ".cache\modelscope\hub\models\VAST-AI-Research\UniRig")
)) {
    if (Test-UniRigModelRoot $candidate) { $ModelRoot = [System.IO.Path]::GetFullPath($candidate); break }
}
if (-not (Test-UniRigModelRoot $ModelRoot) -and -not $SkipWeights) {
    if ($CheckOnly) { throw "UniRig skeleton checkpoint not found through the configured search order." }
    $ModelRoot = Join-Path $projectRoot "workspace\models\modelscope\VAST-AI-Research\UniRig-skeleton"
    Invoke-Native $venvPython @(
        (Join-Path $projectRoot "tools\model_test\download_modelscope_snapshot.py"),
        "--model-id", "VAST-AI-Research/UniRig",
        "--output", $ModelRoot,
        "--allow-patterns", "skeleton/articulation-xl_quantization_256/model.ckpt", "README.md"
    )
}

if (-not $SkipWeights) {
    $checkpoint = Join-Path $ModelRoot "skeleton\articulation-xl_quantization_256\model.ckpt"
    $runtimeCheckpoint = Join-Path $SourceRoot "experiments\skeleton\articulation-xl_quantization_256\model.ckpt"
    if (-not (Test-Path -LiteralPath $runtimeCheckpoint -PathType Leaf)) {
        if ($CheckOnly) { throw "UniRig runtime checkpoint link is missing: $runtimeCheckpoint" }
        New-Item -ItemType Directory -Path (Split-Path -Parent $runtimeCheckpoint) -Force | Out-Null
        try { New-Item -ItemType HardLink -Path $runtimeCheckpoint -Target $checkpoint | Out-Null }
        catch { Copy-Item -LiteralPath $checkpoint -Destination $runtimeCheckpoint }
    }
}

Invoke-Native $venvPython @("-c", "import torch, bpy, transformers, lightning; assert torch.cuda.is_available()")
if (-not (Test-Path -LiteralPath (Join-Path $SourceRoot "ASSETSSTUDIO_SKELETON_PATCH_V1.txt") -PathType Leaf)) {
    throw "UniRig offline skeleton patch marker is missing. Run setup without -CheckOnly once."
}
$gpu = if (Get-Command nvidia-smi.exe -ErrorAction SilentlyContinue) {
    (& nvidia-smi.exe --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>$null | Select-Object -First 1)
} else { $null }
Write-Output "ASSETSSTUDIO_UNIRIG_SKELETON_READY"
Write-Output "SourceRoot=$SourceRoot"
Write-Output "Python=$venvPython"
Write-Output "ModelRoot=$ModelRoot"
Write-Output "WeightsSkipped=$([bool]$SkipWeights)"
Write-Output "GPU=$gpu"
