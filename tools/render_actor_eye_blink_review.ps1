param(
    [string]$BlenderPath = "E:\Env\Blender\blender.exe"
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$blender = (Resolve-Path -LiteralPath $BlenderPath).Path
$output = Join-Path $projectRoot "workspace\face\eye_assembly_v2\blink_review"

& $blender --background --factory-startup --python-exit-code 1 `
    --python (Join-Path $projectRoot "tools\blender\render_actor_eye_blink_review.py") -- `
    --blend (Join-Path $projectRoot "milestones\body\chibi_actor_eye_assembly_v2.blend") `
    --output $output `
    --resolution 256 `
    --lighting-profile soft_flat
if ($LASTEXITCODE -ne 0) { throw "Eye blink review render failed with exit code $LASTEXITCODE" }

python (Join-Path $projectRoot "tools\make_review_gifs.py") $output
if ($LASTEXITCODE -ne 0) { throw "Eye blink GIF packaging failed with exit code $LASTEXITCODE" }

python (Join-Path $projectRoot "tools\validate_actor_eye_blink_review.py") --render-dir $output
if ($LASTEXITCODE -ne 0) { throw "Eye blink review validation failed with exit code $LASTEXITCODE" }

Write-Output "ASSETSSTUDIO_EYE_BLINK_REVIEW_PASS output=$output"
