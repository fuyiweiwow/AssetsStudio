param(
    [string]$ComfyRoot,
    [string]$Python,
    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$projectParent = Split-Path -Parent $projectRoot
$ggufCommit = "6ea2651e7df66d7585f6ffee804b20e92fb38b8a"

function Resolve-ComfyRoot([string]$RequestedPath) {
    $candidates = @(
        $RequestedPath,
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

function Resolve-Python([string]$RequestedPath, [string]$ResolvedComfyRoot) {
    $candidates = @(
        $RequestedPath,
        $env:ASSETSSTUDIO_PYTHON,
        (Join-Path $ResolvedComfyRoot ".venv\Scripts\python.exe"),
        (Join-Path $ResolvedComfyRoot "venv\Scripts\python.exe"),
        (Join-Path $ResolvedComfyRoot "python_embeded\python.exe"),
        "python.exe",
        "python3.exe"
    )
    foreach ($candidate in $candidates) {
        if ([string]::IsNullOrWhiteSpace($candidate)) {
            continue
        }
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
        $command = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($null -ne $command -and $command.CommandType -eq "Application") {
            return $command.Source
        }
    }
    throw "A Python executable for ComfyUI was not found. Pass -Python or set ASSETSSTUDIO_PYTHON."
}

function Test-ExactFile([string]$Path, [long]$ExpectedSize) {
    return (Test-Path -LiteralPath $Path -PathType Leaf) -and ((Get-Item -LiteralPath $Path).Length -eq $ExpectedSize)
}

function Install-ModelScopeFile([hashtable]$Item) {
    $destination = Join-Path $ComfyRoot $Item.RelativePath
    if (Test-ExactFile $destination $Item.Size) {
        Write-Output "VERIFIED $($Item.RelativePath)"
        return
    }
    if ($CheckOnly) {
        throw "Missing or incomplete model file: $($Item.RelativePath)"
    }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
    $curl = Get-Command "curl.exe" -ErrorAction SilentlyContinue
    if ($null -eq $curl) {
        throw "curl.exe is required for resumable ModelScope downloads."
    }
    & $curl.Source -L --fail --retry 8 --retry-delay 5 --continue-at - --output $destination $Item.Url
    if ($LASTEXITCODE -ne 0) {
        throw "ModelScope download failed: $($Item.Url)"
    }
    if (-not (Test-ExactFile $destination $Item.Size)) {
        throw "Downloaded file size mismatch: $($Item.RelativePath)"
    }
    Write-Output "VERIFIED $($Item.RelativePath)"
}

$ComfyRoot = Resolve-ComfyRoot $ComfyRoot
$Python = Resolve-Python $Python $ComfyRoot
$nodeRoot = Join-Path $ComfyRoot "custom_nodes\ComfyUI-GGUF"

if (-not $CheckOnly) {
    if (-not (Test-Path -LiteralPath (Join-Path $nodeRoot ".git") -PathType Container)) {
        git clone --filter=blob:none https://github.com/city96/ComfyUI-GGUF.git $nodeRoot
        if ($LASTEXITCODE -ne 0) {
            throw "Unable to clone ComfyUI-GGUF."
        }
    }
    git -C $nodeRoot fetch --depth 1 origin $ggufCommit
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to fetch pinned ComfyUI-GGUF commit $ggufCommit."
    }
    git -C $nodeRoot checkout --detach $ggufCommit
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to select pinned ComfyUI-GGUF commit $ggufCommit."
    }
    & $Python -m pip install -r (Join-Path $nodeRoot "requirements.txt")
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to install ComfyUI-GGUF Python requirements."
    }
}

if (-not (Test-Path -LiteralPath (Join-Path $nodeRoot ".git") -PathType Container)) {
    throw "ComfyUI-GGUF is missing: $nodeRoot"
}
$installedCommit = (git -C $nodeRoot rev-parse HEAD).Trim()
if ($installedCommit -ne $ggufCommit) {
    throw "ComfyUI-GGUF commit mismatch: $installedCommit != $ggufCommit"
}

$modelFiles = @(
    @{
        RelativePath = "models\diffusion_models\qwen-image-edit-2511-Q3_K_M.gguf"
        Size = 9920805472
        Url = "https://modelscope.cn/models/unsloth/Qwen-Image-Edit-2511-GGUF/resolve/master/qwen-image-edit-2511-Q3_K_M.gguf"
    },
    @{
        RelativePath = "models\text_encoders\qwen_2.5_vl_7b_fp8_scaled.safetensors"
        Size = 9384670680
        Url = "https://modelscope.cn/models/Comfy-Org/Qwen-Image_ComfyUI/resolve/master/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors"
    },
    @{
        RelativePath = "models\vae\qwen_image_vae.safetensors"
        Size = 253806246
        Url = "https://modelscope.cn/models/Comfy-Org/Qwen-Image_ComfyUI/resolve/master/split_files/vae/qwen_image_vae.safetensors"
    }
)
foreach ($modelFile in $modelFiles) {
    Install-ModelScopeFile $modelFile
}

Write-Output "ASSETSSTUDIO_QWEN_ACTOR_CORE_ENVIRONMENT_READY"
Write-Output "ComfyRoot=$ComfyRoot"
Write-Output "Python=$Python"
Write-Output "ComfyUIGGUF=$installedCommit"
