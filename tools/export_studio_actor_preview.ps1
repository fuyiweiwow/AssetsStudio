param(
    [string]$BlenderPath = "E:\Env\Blender\blender.exe"
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$blender = (Resolve-Path -LiteralPath $BlenderPath).Path
$outputDirectory = Join-Path $projectRoot "studio\public\generated"
$output = Join-Path $outputDirectory "actor-composite-v1.glb"

New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null

& $blender --factory-startup --background `
    --python (Join-Path $projectRoot "tools\blender\export_studio_actor_preview.py") -- `
    --base-blend (Join-Path $projectRoot "milestones\shoes\cartoon_sneaker_v10\actor_cartoon_sneaker_fbx_v10_length_expanded.blend") `
    --top-blend (Join-Path $projectRoot "milestones\tops\actor_native_tshirt_v5\actor_native_tshirt_body_component_v5_upperarm_coverage.blend") `
    --pants-blend (Join-Path $projectRoot "milestones\pants\native_control_v0\native_control_shorts_v0.blend") `
    --output $output

if ($LASTEXITCODE -ne 0) {
    throw "Actor preview export failed with exit code $LASTEXITCODE"
}
if (-not (Test-Path -LiteralPath $output -PathType Leaf)) {
    throw "Actor preview GLB was not created: $output"
}

Write-Output "ASSETSSTUDIO_ACTOR_PREVIEW_WRAPPER_PASS output=$output"
