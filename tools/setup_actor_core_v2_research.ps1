param(
    [string]$RuntimeRoot,
    [string]$SourceRoot,
    [string]$ModelRoot,
    [switch]$CheckOnly,
    [switch]$SkipWeights
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$projectParent = Split-Path -Parent $projectRoot

function Resolve-ExistingDirectory([string[]]$Candidates, [string]$Marker) {
    foreach ($candidate in $Candidates) {
        if ([string]::IsNullOrWhiteSpace($candidate)) { continue }
        $resolved = [System.IO.Path]::GetFullPath($candidate)
        $probe = if ([string]::IsNullOrWhiteSpace($Marker)) { $resolved } else { Join-Path $resolved $Marker }
        if (Test-Path -LiteralPath $probe) { return $resolved }
    }
    return $null
}

function Test-TripoSGModelRoot([string]$Candidate) {
    if ([string]::IsNullOrWhiteSpace($Candidate)) { return $false }
    $resolved = [System.IO.Path]::GetFullPath($Candidate)
    $required = @(
        @{ Path = "model_index.json"; MinimumBytes = 100 },
        @{ Path = "transformer\diffusion_pytorch_model.safetensors"; MinimumBytes = 5000000000 },
        @{ Path = "vae\diffusion_pytorch_model.safetensors"; MinimumBytes = 800000000 },
        @{ Path = "image_encoder_dinov2\model.safetensors"; MinimumBytes = 1000000000 }
    )
    foreach ($item in $required) {
        $file = Join-Path $resolved $item.Path
        if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { return $false }
        if ((Get-Item -LiteralPath $file).Length -lt $item.MinimumBytes) { return $false }
    }
    return $true
}

function Resolve-TripoSGModelRoot([string[]]$Candidates) {
    foreach ($candidate in $Candidates) {
        if (Test-TripoSGModelRoot $candidate) {
            return [System.IO.Path]::GetFullPath($candidate)
        }
    }
    return $null
}

function Invoke-Native([string]$Program, [string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed ($LASTEXITCODE): $Program $($Arguments -join ' ')"
    }
}

function Assert-WorkspaceRuntimePath([string]$Path) {
    $runtimePrefix = $RuntimeRoot.TrimEnd('\') + '\'
    $resolved = [System.IO.Path]::GetFullPath($Path)
    if (-not $resolved.StartsWith($runtimePrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to modify a path outside the Actor Core V2 runtime: $resolved"
    }
    return $resolved
}

if ([string]::IsNullOrWhiteSpace($RuntimeRoot)) {
    $RuntimeRoot = if ($env:ASSETSSTUDIO_ACTOR_CORE_V2_RUNTIME) {
        $env:ASSETSSTUDIO_ACTOR_CORE_V2_RUNTIME
    } else {
        Join-Path $projectRoot "workspace\runtime\actor_core_v2"
    }
}
$RuntimeRoot = [System.IO.Path]::GetFullPath($RuntimeRoot)

$sourceCandidates = @(
    $SourceRoot,
    $env:ASSETSSTUDIO_TRIPOSG_SOURCE,
    (Join-Path $RuntimeRoot "source\TripoSG"),
    (Join-Path $projectParent "TripoSG")
)
$SourceRoot = Resolve-ExistingDirectory $sourceCandidates "scripts\inference_triposg.py"

if ([string]::IsNullOrWhiteSpace($SourceRoot)) {
    if ($CheckOnly) { throw "TripoSG source was not found. Checked explicit path, ASSETSSTUDIO_TRIPOSG_SOURCE, workspace runtime, and adjacent directory." }
    $sourceRevision = "fc5c40990181e2a756c4e0b1c2f4d6b5202faf8c"
    $SourceRoot = Join-Path $RuntimeRoot "source\TripoSG"
    $SourceRoot = Assert-WorkspaceRuntimePath $SourceRoot
    New-Item -ItemType Directory -Path (Split-Path -Parent $SourceRoot) -Force | Out-Null
    if (Test-Path -LiteralPath $SourceRoot) { Remove-Item -LiteralPath $SourceRoot -Recurse -Force }
    $archive = Assert-WorkspaceRuntimePath (Join-Path $RuntimeRoot "downloads\TripoSG-$sourceRevision.zip")
    $extractRoot = Assert-WorkspaceRuntimePath (Join-Path $RuntimeRoot "downloads\TripoSG-$sourceRevision")
    New-Item -ItemType Directory -Path (Split-Path -Parent $archive) -Force | Out-Null
    $curl = (Get-Command curl.exe -ErrorAction Stop).Source
    Invoke-Native $curl @("--location", "--fail", "--retry", "5", "--retry-delay", "2", "--silent", "--show-error", "--output", $archive, "https://codeload.github.com/VAST-AI-Research/TripoSG/zip/$sourceRevision")
    if (Test-Path -LiteralPath $extractRoot) { Remove-Item -LiteralPath $extractRoot -Recurse -Force }
    Expand-Archive -LiteralPath $archive -DestinationPath (Split-Path -Parent $extractRoot) -Force
    if (-not (Test-Path -LiteralPath (Join-Path $extractRoot "scripts\inference_triposg.py") -PathType Leaf)) {
        throw "The official TripoSG source archive did not contain the expected inference entrypoint."
    }
    Move-Item -LiteralPath $extractRoot -Destination $SourceRoot
    Set-Content -LiteralPath (Join-Path $SourceRoot "ASSETSSTUDIO_SOURCE_REVISION.txt") -Value $sourceRevision -Encoding ASCII
    Remove-Item -LiteralPath $archive -Force
}

$venvRoot = Join-Path $RuntimeRoot "venv"
$venvPython = Join-Path $venvRoot "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
    if ($CheckOnly) { throw "Actor Core V2 virtual environment was not found: $venvRoot" }
    $uv = (Get-Command uv.exe -ErrorAction Stop).Source
    New-Item -ItemType Directory -Path $RuntimeRoot -Force | Out-Null
    Invoke-Native $uv @("venv", "--python", "3.10", "--seed", "--quiet", $venvRoot)
}

if ($CheckOnly) {
    Invoke-Native $venvPython @("-c", "import torch, torchvision, modelscope, diffusers, trimesh; assert torch.cuda.is_available()")
} else {
    $uv = (Get-Command uv.exe -ErrorAction Stop).Source
    # CUDA 12.8 supports the current teacher GPU while remaining usable on RTX 3060.
    # uv keeps this idempotent and reuses its local package cache.
    Invoke-Native $uv @("pip", "install", "--python", $venvPython, "--quiet", "--index-url", "https://download.pytorch.org/whl/cu128", "torch", "torchvision")
    Invoke-Native $uv @("pip", "install", "--python", $venvPython, "--quiet", "modelscope")
    # The optional flash decoder depends on a locally compiled diso CUDA extension.
    # Our portable teacher runner uses the official hierarchical decoder and skimage
    # marching cubes, so it does not require a machine-specific compiler toolchain.
    $portableRequirements = Join-Path $RuntimeRoot "requirements-portable.txt"
    Get-Content -LiteralPath (Join-Path $SourceRoot "requirements.txt") |
        Where-Object { $_ -notmatch '^\s*diso(?:\s|$)' } |
        Set-Content -LiteralPath $portableRequirements -Encoding UTF8
    Invoke-Native $uv @("pip", "install", "--python", $venvPython, "--quiet", "-r", $portableRequirements)
}

$modelCandidates = @(
    $ModelRoot,
    $env:ASSETSSTUDIO_TRIPOSG_MODEL,
    (Join-Path $projectRoot "workspace\models\modelscope\VAST-AI-Research\TripoSG"),
    (Join-Path $env:USERPROFILE ".cache\modelscope\hub\models\VAST-AI-Research\TripoSG")
)
$ModelRoot = Resolve-TripoSGModelRoot $modelCandidates

if ([string]::IsNullOrWhiteSpace($ModelRoot) -and (-not $SkipWeights)) {
    if ($CheckOnly) { throw "TripoSG weights were not found. Checked explicit path, ASSETSSTUDIO_TRIPOSG_MODEL, workspace models, and ModelScope cache." }
    $ModelRoot = Join-Path $projectRoot "workspace\models\modelscope\VAST-AI-Research\TripoSG"
    New-Item -ItemType Directory -Path $ModelRoot -Force | Out-Null
    $downloadHelper = Join-Path $projectRoot "tools\model_test\download_modelscope_snapshot.py"
    Invoke-Native $venvPython @($downloadHelper, "--model-id", "VAST-AI-Research/TripoSG", "--output", $ModelRoot)
    if (-not (Test-TripoSGModelRoot $ModelRoot)) {
        throw "ModelScope download completed without a full TripoSG snapshot: $ModelRoot"
    }
}

$gpu = $null
if (Get-Command nvidia-smi.exe -ErrorAction SilentlyContinue) {
    $gpu = (& nvidia-smi.exe --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>$null | Select-Object -First 1)
}

Write-Output "ASSETSSTUDIO_ACTOR_CORE_V2_RESEARCH_READY"
Write-Output "RuntimeRoot=$RuntimeRoot"
Write-Output "SourceRoot=$SourceRoot"
Write-Output "Python=$venvPython"
Write-Output "ModelRoot=$ModelRoot"
Write-Output "WeightsSkipped=$([bool]$SkipWeights)"
Write-Output "GPU=$gpu"
