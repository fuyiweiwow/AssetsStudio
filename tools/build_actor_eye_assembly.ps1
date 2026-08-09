param(
    [string]$BlenderPath = "E:\Env\Blender\blender.exe"
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$blender = (Resolve-Path -LiteralPath $BlenderPath).Path
$review = Join-Path $projectRoot "workspace\face\eye_assembly_v2\review"
$output = Join-Path $projectRoot "milestones\body\chibi_actor_eye_assembly_v2.blend"

& $blender --background --factory-startup --python-exit-code 1 `
    --python (Join-Path $projectRoot "tools\blender\build_actor_eye_assembly.py") -- `
    --source-blend (Join-Path $projectRoot "milestones\body\chibi_actor_mixamo_walk_v1.blend") `
    --left-texture (Join-Path $projectRoot "milestones\body\eye_textures\eye_left.png") `
    --right-texture (Join-Path $projectRoot "milestones\body\eye_textures\eye_right.png") `
    --half-left-texture (Join-Path $projectRoot "milestones\body\eye_textures\eye_half_left.png") `
    --half-right-texture (Join-Path $projectRoot "milestones\body\eye_textures\eye_half_right.png") `
    --closed-left-texture (Join-Path $projectRoot "milestones\body\eye_textures\eye_closed_left.png") `
    --closed-right-texture (Join-Path $projectRoot "milestones\body\eye_textures\eye_closed_right.png") `
    --output $review `
    --save-blend $output
if ($LASTEXITCODE -ne 0) { throw "Eye assembly build failed with exit code $LASTEXITCODE" }

& $blender --background --factory-startup --python-exit-code 1 `
    --python (Join-Path $projectRoot "tools\blender\validate_actor_eye_assembly.py") -- `
    --blend $output
if ($LASTEXITCODE -ne 0) { throw "Eye assembly validation failed with exit code $LASTEXITCODE" }

Write-Output "ASSETSSTUDIO_EYE_ASSEMBLY_BUILD_PASS output=$output review=$review"
