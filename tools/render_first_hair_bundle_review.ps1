param(
    [string]$BlenderPath = "E:\Env\Blender\blender.exe"
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$blender = (Resolve-Path -LiteralPath $BlenderPath).Path
& (Join-Path $projectRoot "tools\build_first_hair_bundle.ps1") -BlenderPath $blender
if ($LASTEXITCODE -ne 0) {
    throw "First hair bundle build failed with exit code $LASTEXITCODE"
}

$blend = Join-Path $projectRoot "workspace\cache\hair\first_bundle\actor_hair_seed_04.blend"
$output = Join-Path $projectRoot "workspace\cache\hair\first_bundle\walk_review"
& $blender --factory-startup --background --python-exit-code 1 `
    --python (Join-Path $projectRoot "tools\blender\render_actor_clothing_eevee.py") -- `
    --blend $blend `
    --output $output `
    --frames 8 `
    --appearance-seed 20260809 `
    --highlight-object HairCandidate_Blend `
    --highlight-color "0.12,0.045,0.025,1.0"
if ($LASTEXITCODE -ne 0) {
    throw "First hair bundle review render failed with exit code $LASTEXITCODE"
}
python (Join-Path $projectRoot "tools\make_clothing_review_gifs.py") --root $output --size 320 --duration 120
if ($LASTEXITCODE -ne 0) {
    throw "First hair bundle GIF packaging failed with exit code $LASTEXITCODE"
}
Write-Output "ASSETSSTUDIO_HAIR_BUNDLE_REVIEW_PASS output=$output"
