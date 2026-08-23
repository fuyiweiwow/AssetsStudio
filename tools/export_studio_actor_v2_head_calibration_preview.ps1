param(
    [string]$InputBlend = "workspace\actor_v2\head_feature_hairline_fix\actor_head_complete_calibrated.blend",
    [string]$BlenderPath = "E:\Env\Blender\blender.exe"
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$input = (Resolve-Path -LiteralPath (Join-Path $projectRoot $InputBlend)).Path
$blender = (Resolve-Path -LiteralPath $BlenderPath).Path
$output = Join-Path $projectRoot "studio\public\generated\actor-v2-head-calibration.glb"

& $blender --background --python-exit-code 1 --python `
    (Join-Path $projectRoot "tools\blender\export_studio_actor_v2_head_calibration.py") -- `
    --input $input `
    --output $output
if ($LASTEXITCODE -ne 0) {
    throw "Actor V2 Studio head calibration export failed (exit $LASTEXITCODE)"
}

Write-Output "ASSETSSTUDIO_ACTOR_V2_HEAD_PREVIEW_WRAPPER_PASS output=$output"
