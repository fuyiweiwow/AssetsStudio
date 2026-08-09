param(
    [string]$BlenderPath = "E:\Env\Blender\blender.exe"
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$blender = (Resolve-Path -LiteralPath $BlenderPath).Path
$outputDirectory = Join-Path $projectRoot "studio\public\generated"
$output = Join-Path $outputDirectory "actor-composite-v1.glb"
$hairBlend = Join-Path $projectRoot "workspace\cache\hair\first_bundle\actor_hair_seed_04.blend"

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
    --top-blend (Join-Path $projectRoot "milestones\tops\actor_native_tshirt_v5\actor_native_tshirt_body_component_v5_upperarm_coverage.blend") `
    --pants-blend (Join-Path $projectRoot "milestones\pants\native_control_v0\native_control_shorts_v0.blend") `
    --hair-blend $hairBlend `
    --output $output

if ($LASTEXITCODE -ne 0) {
    throw "Actor preview export failed with exit code $LASTEXITCODE"
}
if (-not (Test-Path -LiteralPath $output -PathType Leaf)) {
    throw "Actor preview GLB was not created: $output"
}

python (Join-Path $projectRoot "tools\validate_studio_actor_preview.py") `
    --glb $output `
    --manifest ([System.IO.Path]::ChangeExtension($output, ".manifest.json"))
if ($LASTEXITCODE -ne 0) {
    throw "Actor preview contract validation failed with exit code $LASTEXITCODE"
}

Write-Output "ASSETSSTUDIO_ACTOR_PREVIEW_WRAPPER_PASS output=$output"
