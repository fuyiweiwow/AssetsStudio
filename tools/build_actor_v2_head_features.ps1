param(
    [Parameter(Mandatory = $true)]
    [string]$ActorBlend,
    [string]$OutputDir = "workspace\actor_v2\head_feature_build",
    [string]$StudioFeedback = "",
    [string]$BlenderPath = "E:\Env\Blender\blender.exe"
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$blender = (Resolve-Path -LiteralPath $BlenderPath).Path
$actor = (Resolve-Path -LiteralPath $ActorBlend).Path
$outputRoot = [System.IO.Path]::GetFullPath((Join-Path $projectRoot $OutputDir))
New-Item -ItemType Directory -Force -Path $outputRoot | Out-Null

function Invoke-BlenderStage {
    param([string]$Script, [string[]]$StageArgs)
    & $blender --background --python-exit-code 1 --python (Join-Path $projectRoot $Script) -- @StageArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Actor V2 head-feature stage failed: $Script (exit $LASTEXITCODE)"
    }
}

$calibration = Join-Path $outputRoot "head_feature_calibration_v1.json"
$calibrationDebug = Join-Path $outputRoot "head_feature_calibration_v1.blend"
$eyeBlend = Join-Path $outputRoot "actor_eye_calibrated.blend"
$earBlend = Join-Path $outputRoot "actor_eye_ears_calibrated.blend"
$hairBlend = Join-Path $outputRoot "actor_head_hair_calibrated.blend"
$finalBlend = Join-Path $outputRoot "actor_head_complete_calibrated.blend"
$autoBlend = if ([string]::IsNullOrWhiteSpace($StudioFeedback)) { $finalBlend } else { Join-Path $outputRoot "actor_head_complete_calibrated_auto.blend" }
$eyeReview = Join-Path $outputRoot "eye_review"
$hairReview = Join-Path $outputRoot "hair_review"
$validation = Join-Path $outputRoot "validation"
$blinkReview = Join-Path $validation "blink"
$actionReview = Join-Path $validation "action"
New-Item -ItemType Directory -Force -Path $validation | Out-Null

Invoke-BlenderStage "tools\model_test\calibrate_actor_v2_head_features.py" @(
    "--input", $actor,
    "--output", $calibration,
    "--debug-blend", $calibrationDebug,
    "--frame", "1"
)

$eyeTextureRoot = Join-Path $projectRoot "references\actor_v2\face_v1\eye_textures"
Invoke-BlenderStage "tools\blender\build_actor_eye_assembly.py" @(
    "--source-blend", $actor,
    "--left-texture", (Join-Path $eyeTextureRoot "eye_right.png"),
    "--right-texture", (Join-Path $eyeTextureRoot "eye_left.png"),
    "--half-left-texture", (Join-Path $eyeTextureRoot "eye_half_right.png"),
    "--half-right-texture", (Join-Path $eyeTextureRoot "eye_half_left.png"),
    "--closed-left-texture", (Join-Path $eyeTextureRoot "eye_closed_right.png"),
    "--closed-right-texture", (Join-Path $eyeTextureRoot "eye_closed_left.png"),
    "--calibration", $calibration,
    "--texture-side-contract", "viewer_named_swap",
    "--output", $eyeReview,
    "--save-blend", $eyeBlend,
    "--frame", "1"
)

$mikuSource = Join-Path $projectRoot "milestones\body\chibi_actor_eye_assembly_v2.blend"
Invoke-BlenderStage "tools\blender\fit_miku_ears_from_head_calibration.py" @(
    "--input", $eyeBlend,
    "--source-blend", $mikuSource,
    "--calibration", $calibration,
    "--output", $earBlend,
    "--outward-scale", "1.0",
    "--frame", "1"
)

$hairSource = Join-Path $projectRoot "workspace\actor_v2\slots\head_hair\paired_v2_clean\head_hair_paired_v2_review128k.blend"
Invoke-BlenderStage "tools\blender\fit_blend_hair_candidate.py" @(
    "--hair-source-blend", $hairSource,
    "--hair-object", "HeadHair_DefaultAdventurer_V1_Source",
    "--actor-blend", $earBlend,
    "--head-calibration", $calibration,
    "--output-blend", $hairBlend,
    "--output-dir", $hairReview,
    "--q-height-ratio", "1.15",
    "--width-ratio", "1.10",
    "--top-clearance", "0.06",
    "--radial-clearance", "0.09",
    "--add-actor-cap",
    "--cap-bottom-offset", "0.44",
    "--cap-surface-offset", "0.055",
    "--color", "0.12", "0.045", "0.025", "1.0"
)

# Preserve the calibrated root seam, but extend the detachable Miku ear
# silhouette through the source-locked side hair. Cutting an ellipsoidal hole
# in the final hair is explicitly rejected because it exposes jagged scalp.
Invoke-BlenderStage "tools\blender\fit_miku_ears_from_head_calibration.py" @(
    "--input", $hairBlend,
    "--source-blend", $mikuSource,
    "--calibration", $calibration,
    "--output", $autoBlend,
    "--outward-scale", "2.0",
    "--frame", "1"
)

if (-not [string]::IsNullOrWhiteSpace($StudioFeedback)) {
    $feedback = (Resolve-Path -LiteralPath $StudioFeedback).Path
    Invoke-BlenderStage "tools\blender\apply_studio_head_feature_feedback.py" @(
        "--input", $autoBlend,
        "--feedback", $feedback,
        "--output", $finalBlend,
        "--report", (Join-Path $validation "studio_head_feature_feedback.json"),
        "--frame", "1"
    )
}

Invoke-BlenderStage "tools\blender\validate_actor_eye_assembly.py" @(
    "--blend", $finalBlend,
    "--expected-texture-side-contract", "viewer_named_swap"
)
Invoke-BlenderStage "tools\model_test\analyze_hair_undercap_coverage.py" @(
    "--input", $finalBlend,
    "--calibration", $calibration,
    "--output", (Join-Path $validation "scalp_coverage.json"),
    "--grid", "25"
)
Invoke-BlenderStage "tools\model_test\analyze_head_component_fit.py" @(
    "--blend", $finalBlend,
    "--output", (Join-Path $validation "head_component_fit.json")
)
Invoke-BlenderStage "tools\blender\render_actor_eye_blink_review.py" @(
    "--blend", $finalBlend,
    "--output", $blinkReview,
    "--resolution", "256",
    "--lighting-profile", "soft_flat"
)
python (Join-Path $projectRoot "tools\validate_actor_eye_blink_review.py") --render-dir $blinkReview
if ($LASTEXITCODE -ne 0) { throw "Actor V2 blink review validation failed (exit $LASTEXITCODE)" }
Invoke-BlenderStage "tools\model_test\render_actor_v2_action_review.py" @(
    "--input", $finalBlend,
    "--output-dir", $actionReview,
    "--sample-count", "8",
    "--resolution", "256"
)

Write-Output "ACTOR_V2_HEAD_FEATURE_BUILD_PASS final=$finalBlend validation=$validation"
