param(
    [string]$BlenderPath = $env:BLENDER_PATH
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$workspaceParent = Split-Path -Parent $projectRoot

if ([string]::IsNullOrWhiteSpace($BlenderPath)) {
    $blenderCommand = Get-Command blender.exe -ErrorAction SilentlyContinue
    if ($null -ne $blenderCommand) {
        $BlenderPath = $blenderCommand.Source
    }
}

if ([string]::IsNullOrWhiteSpace($BlenderPath)) {
    $portableBlender = Get-ChildItem -LiteralPath $workspaceParent -Directory -Filter "blender-*" -ErrorAction SilentlyContinue |
        ForEach-Object { Join-Path $_.FullName "blender.exe" } |
        Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
        Select-Object -First 1
    if ($null -ne $portableBlender) {
        $BlenderPath = $portableBlender
    }
}

if ([string]::IsNullOrWhiteSpace($BlenderPath) -and -not [string]::IsNullOrWhiteSpace($env:ProgramFiles)) {
    $blenderFoundation = Join-Path $env:ProgramFiles "Blender Foundation"
    if (Test-Path -LiteralPath $blenderFoundation -PathType Container) {
        $installedBlender = Get-ChildItem -LiteralPath $blenderFoundation -Directory -ErrorAction SilentlyContinue |
            ForEach-Object { Join-Path $_.FullName "blender.exe" } |
            Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
            Sort-Object -Descending |
            Select-Object -First 1
        if ($null -ne $installedBlender) {
            $BlenderPath = $installedBlender
        }
    }
}

if ([string]::IsNullOrWhiteSpace($BlenderPath)) {
    throw "Blender was not found. Pass -BlenderPath, set BLENDER_PATH, add blender.exe to PATH, or place a blender-* portable directory beside the repository."
}

$blender = (Resolve-Path -LiteralPath $BlenderPath).Path
$outputDirectory = Join-Path $projectRoot "studio\public\generated"
$output = Join-Path $outputDirectory "actor-composite-v1.glb"
$hairRecipePath = Join-Path $projectRoot "milestones\hair\first_bundle_recipe_v1.json"
$hairRecipe = Get-Content -LiteralPath $hairRecipePath -Raw -Encoding UTF8 | ConvertFrom-Json
$hairBlend = Join-Path (Join-Path $projectRoot $hairRecipe.cache.directory) $hairRecipe.cache.blend

New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null

if (-not (Test-Path -LiteralPath $hairBlend -PathType Leaf)) {
    & (Join-Path $projectRoot "tools\build_first_hair_bundle.ps1") -BlenderPath $blender
    if ($LASTEXITCODE -ne 0) {
        throw "First hair bundle build failed with exit code $LASTEXITCODE"
    }
}

& $blender --factory-startup --background --python-exit-code 1 `
    --python (Join-Path $projectRoot "tools\blender\export_studio_actor_preview.py") -- `
    --base-blend (Join-Path $projectRoot "milestones\shoes\cartoon_sneaker_v10\actor_cartoon_sneaker_fbx_v10_length_expanded.blend") `
    --face-blend (Join-Path $projectRoot "milestones\body\chibi_actor_eye_assembly_v2.blend") `
    --top-blend (Join-Path $projectRoot "milestones\tops\garmentcode_short_sleeve_v1\output\actor_transfer.blend") `
    --pants-blend (Join-Path $projectRoot "milestones\pants\native_control_v0\native_control_shorts_v0.blend") `
    --hair-blend $hairBlend `
    --hair-recipe $hairRecipePath `
    --output $output

if ($LASTEXITCODE -ne 0) {
    throw "Actor preview export failed with exit code $LASTEXITCODE"
}
if (-not (Test-Path -LiteralPath $output -PathType Leaf)) {
    throw "Actor preview GLB was not created: $output"
}

python (Join-Path $projectRoot "tools\validate_studio_actor_preview.py") `
    --glb $output `
    --manifest ([System.IO.Path]::ChangeExtension($output, ".manifest.json")) `
    --hair-recipe $hairRecipePath
if ($LASTEXITCODE -ne 0) {
    throw "Actor preview contract validation failed with exit code $LASTEXITCODE"
}

Write-Output "ASSETSSTUDIO_ACTOR_PREVIEW_WRAPPER_PASS output=$output"
