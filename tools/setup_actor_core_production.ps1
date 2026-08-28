param(
    [string]$ComfyRoot,
    [string]$BundleRoot,
    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$projectParent = Split-Path -Parent $projectRoot
$productionLoraName = "strip_to_actor_core_teacher_v6_distilled_native_canonical_5pair_e75_rank16.safetensors"
$productionLoraSha256 = "f0656f068ca5a76092af289a3129451e3faace67467f552c85ab27a97131da4c"

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
        if (Test-Path -LiteralPath (Join-Path $resolved "main.py") -PathType Leaf) {
            return $resolved
        }
    }
    throw "ComfyUI was not found. Pass -ComfyRoot, set ASSETSSTUDIO_COMFY_ROOT, or place it beside AssetsStudio/in the current user profile."
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
        if (Test-Path -LiteralPath $resolved -PathType Container) { return $resolved }
    }
    return $null
}

function Install-ModelScopeFile([hashtable]$Item, [string]$ResolvedComfyRoot) {
    $target = Join-Path $ResolvedComfyRoot $Item.RelativePath
    if (Test-Path -LiteralPath $target -PathType Leaf) {
        $length = (Get-Item -LiteralPath $target).Length
        if ($length -lt $Item.MinimumBytes) {
            throw "Existing model file is truncated: $target ($length bytes)"
        }
        return
    }
    if ($CheckOnly) { throw "Required production model is missing: $target" }
    if (-not (Get-Command curl.exe -ErrorAction SilentlyContinue)) {
        throw "curl.exe is required for resumable ModelScope downloads."
    }
    $parent = Split-Path -Parent $target
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
    $partial = "$target.partial"
    Write-Output "Downloading missing model from ModelScope: $($Item.ModelId)/$($Item.File)"
    & curl.exe --location --fail --retry 5 --retry-delay 2 --continue-at - --silent --show-error --output $partial $Item.Url
    if ($LASTEXITCODE -ne 0) { throw "ModelScope download failed: $($Item.ModelId)/$($Item.File)" }
    $length = (Get-Item -LiteralPath $partial).Length
    if ($length -lt $Item.MinimumBytes) {
        throw "Downloaded model is truncated: $partial ($length bytes)"
    }
    Move-Item -LiteralPath $partial -Destination $target -Force
}

$ComfyRoot = Resolve-ComfyRoot $ComfyRoot
$models = @(
    @{
        ModelId = "black-forest-labs/FLUX.2-klein-4b-fp8"
        File = "flux-2-klein-4b-fp8.safetensors"
        RelativePath = "models\diffusion_models\flux-2-klein-4b-fp8.safetensors"
        MinimumBytes = 4000000000
        Url = "https://modelscope.cn/models/black-forest-labs/FLUX.2-klein-4b-fp8/resolve/master/flux-2-klein-4b-fp8.safetensors"
    },
    @{
        ModelId = "Comfy-Org/flux2-klein-4B"
        File = "split_files/text_encoders/qwen_3_4b.safetensors"
        RelativePath = "models\text_encoders\qwen_3_4b.safetensors"
        MinimumBytes = 8000000000
        Url = "https://modelscope.cn/models/Comfy-Org/flux2-klein-4B/resolve/master/split_files/text_encoders/qwen_3_4b.safetensors"
    },
    @{
        ModelId = "Comfy-Org/flux2-klein-4B"
        File = "split_files/vae/flux2-vae.safetensors"
        RelativePath = "models\vae\flux2-vae.safetensors"
        MinimumBytes = 330000000
        Url = "https://modelscope.cn/models/Comfy-Org/flux2-klein-4B/resolve/master/split_files/vae/flux2-vae.safetensors"
    }
)
foreach ($model in $models) { Install-ModelScopeFile $model $ComfyRoot }

$loraTarget = Join-Path $ComfyRoot "models\loras\assetsstudio\$productionLoraName"
if (-not (Test-Path -LiteralPath $loraTarget -PathType Leaf)) {
    if ($CheckOnly) { throw "Production Actor Core LoRA is missing: $loraTarget" }
    $BundleRoot = Resolve-BundleRoot $BundleRoot
    if ($null -eq $BundleRoot) {
        throw "Actor Core bundle was not found. Pass -BundleRoot or set ASSETSSTUDIO_ACTOR_CORE_BUNDLE."
    }
    $loraSource = Get-ChildItem -LiteralPath $BundleRoot -Recurse -File -Filter $productionLoraName | Select-Object -First 1
    if ($null -eq $loraSource) { throw "Bundle does not contain $productionLoraName" }
    New-Item -ItemType Directory -Path (Split-Path -Parent $loraTarget) -Force | Out-Null
    Copy-Item -LiteralPath $loraSource.FullName -Destination $loraTarget
}
$actualLoraSha256 = (Get-FileHash -LiteralPath $loraTarget -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualLoraSha256 -ne $productionLoraSha256) {
    throw "Production Actor Core LoRA SHA256 mismatch: expected $productionLoraSha256, got $actualLoraSha256"
}

Write-Output "ASSETSSTUDIO_ACTOR_CORE_PRODUCTION_READY"
Write-Output "ComfyRoot=$ComfyRoot"
Write-Output "ActorCoreLoRA=$loraTarget"
Write-Output "ActorCoreLoRASHA256=$actualLoraSha256"
