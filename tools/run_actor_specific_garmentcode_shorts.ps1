param(
    [string]$GarmentCodeRoot = ".\third_party\GarmentCode",
    [string]$Blender = "E:\Env\Blender\blender.exe",
    [string]$Output = ".\workspace\garmentcode_pants_actor_v1",
    [string]$Name = "actor_specific_garmentcode_shorts_v1",
    [int]$Seed = 1,
    [double]$PantsLength = 0.30,
    [double]$PantsWidth = 1.05,
    [double]$PantsFlare = 1.0,
    [double]$PantsRise = 1.0,
    [int]$MaxSimSteps = 180,
    [int]$MaxSimTime = 300
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$actor = Join-Path $projectRoot "milestones\body\chibi_actor_mixamo_walk_v1.blend"
$garmentCode = (Resolve-Path $GarmentCodeRoot).Path
$python = Join-Path $garmentCode ".venv\Scripts\python.exe"
$warpRoot = Join-Path (Split-Path -Parent $garmentCode) "NvidiaWarp-GarmentCode"
$outputRoot = if ([System.IO.Path]::IsPathRooted($Output)) {
    [System.IO.Path]::GetFullPath($Output)
} else {
    [System.IO.Path]::GetFullPath((Join-Path $projectRoot $Output))
}
$inputs = Join-Path $outputRoot "inputs"
$candidateRoot = Join-Path $outputRoot "candidate"
$simulationRoot = Join-Path $outputRoot "simulation"
$transferRoot = Join-Path $outputRoot "actor_transfer"
$renderRoot = Join-Path $outputRoot "renders"
New-Item -ItemType Directory -Force $inputs, $candidateRoot, $simulationRoot, $transferRoot, $renderRoot | Out-Null

& $python (Join-Path $projectRoot "tools\garmentcode\validate_garmentcode_actor_patch.py") `
    --garmentcode-root $garmentCode
if ($LASTEXITCODE) { exit $LASTEXITCODE }

& $Blender --background --python (Join-Path $projectRoot "tools\blender\export_actor_pants_measurement_source.py") -- `
    --actor $actor `
    --mesh-output (Join-Path $inputs "actor_rest_complete.obj") `
    --landmarks-output (Join-Path $inputs "actor_pants_landmarks.json")
if ($LASTEXITCODE) { exit $LASTEXITCODE }

& $python (Join-Path $projectRoot "tools\garmentcode\measure_actor_pants_sections.py") `
    --mesh (Join-Path $inputs "actor_rest_complete.obj") `
    --landmarks (Join-Path $inputs "actor_pants_landmarks.json") `
    --output (Join-Path $inputs "actor_pants_measurements.json")
if ($LASTEXITCODE) { exit $LASTEXITCODE }

& $python (Join-Path $projectRoot "tools\garmentcode\make_actor_pants_body.py") `
    --measurements (Join-Path $inputs "actor_pants_measurements.json") `
    --base-body (Join-Path $garmentCode "assets\bodies\mean_all.yaml") `
    --output (Join-Path $inputs "actor_pants_body.yaml")
if ($LASTEXITCODE) { exit $LASTEXITCODE }

& $Blender --background --python (Join-Path $projectRoot "tools\blender\export_actor_lower_body_proxy_source.py") -- `
    --actor $actor `
    --output (Join-Path $inputs "actor_lower_body_surface_cm.obj") `
    --report (Join-Path $inputs "actor_lower_body_surface_report.json") `
    --segmentation (Join-Path $inputs "actor_lower_body_segmentation.json")
if ($LASTEXITCODE) { exit $LASTEXITCODE }

& $Blender --background --python (Join-Path $projectRoot "tools\garmentcode\blender_fill_actor_proxy_boundaries.py") -- `
    --input (Join-Path $inputs "actor_lower_body_surface_cm.obj") `
    --output (Join-Path $inputs "actor_lower_body_collision_m.obj") `
    --report (Join-Path $inputs "actor_lower_body_fill_report.json") `
    --scale 0.01
if ($LASTEXITCODE) { exit $LASTEXITCODE }

& $python (Join-Path $projectRoot "tools\garmentcode\generate_actor_specific_garmentcode_shorts.py") `
    --garmentcode-root $garmentCode `
    --actor $actor `
    --measurements (Join-Path $inputs "actor_pants_measurements.json") `
    --body (Join-Path $inputs "actor_pants_body.yaml") `
    --design-template (Join-Path $garmentCode "assets\design_params\default.yaml") `
    --output $candidateRoot --name $Name --seed $Seed `
    --pants-length $PantsLength --pants-width $PantsWidth `
    --pants-flare $PantsFlare --pants-rise $PantsRise
if ($LASTEXITCODE) { exit $LASTEXITCODE }

$candidate = Join-Path $candidateRoot ("{0}_seed_{1}" -f $Name, $Seed)
$pattern = Join-Path $candidate ("{0}_seed_{1}_specification.json" -f $Name, $Seed)
$manifest = Join-Path $candidate "assetsstudio_candidate_manifest.json"
$env:ASSETSLAB_WARP_SOURCE = $warpRoot
& $python (Join-Path $projectRoot "tools\garmentcode\run_actor_specific_garmentcode_sim.py") `
    --garmentcode-root $garmentCode `
    --pattern-spec $pattern `
    --actor $actor `
    --actor-measurements (Join-Path $inputs "actor_pants_measurements.json") `
    --body-measurements (Join-Path $inputs "actor_pants_body.yaml") `
    --manifest $manifest `
    --body-obj (Join-Path $inputs "actor_lower_body_collision_m.obj") `
    --body-segmentation (Join-Path $inputs "actor_lower_body_segmentation.json") `
    --output $simulationRoot `
    --max-sim-steps $MaxSimSteps --max-sim-time $MaxSimTime --disable-frame-timeout
if ($LASTEXITCODE) { exit $LASTEXITCODE }

$sim = Get-ChildItem $simulationRoot -Recurse -Filter "*_sim.obj" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $sim) { throw "GarmentCode did not produce a simulation OBJ" }
$membership = Join-Path $outputRoot "panel_membership.json"
& $python (Join-Path $projectRoot "tools\garmentcode\export_garmentcode_panel_membership.py") `
    --garmentcode-root $garmentCode --pattern-spec $pattern --sim-obj $sim.FullName --output $membership
if ($LASTEXITCODE) { exit $LASTEXITCODE }

& $Blender --background --python (Join-Path $projectRoot "tools\blender\transfer_garmentcode_shorts_to_actor.py") -- `
    --actor-blend $actor --sim-obj $sim.FullName --panel-membership $membership --output $transferRoot
if ($LASTEXITCODE) { exit $LASTEXITCODE }

$blend = Join-Path $transferRoot "garmentcode_actor_shorts_transfer.blend"
& $Blender --background --python (Join-Path $projectRoot "tools\blender\render_actor_clothing_eevee.py") -- `
    --blend $blend --output $renderRoot --frames 8 --resolution 256 `
    --highlight-object GarmentCodeShorts_ActorTransfer
if ($LASTEXITCODE) { exit $LASTEXITCODE }

& $Blender --background --python (Join-Path $projectRoot "tools\blender\check_garment_actor_fit.py") -- `
    --blend $blend --output (Join-Path $outputRoot "fit_report.json") `
    --garment-kind pants --garment-name GarmentCodeShorts_ActorTransfer
$fitExit = $LASTEXITCODE
& python (Join-Path $projectRoot "tools\make_clothing_review_gifs.py") --root $renderRoot --size 256 --duration 120
if ($LASTEXITCODE) { exit $LASTEXITCODE }

Write-Output "ACTOR_GARMENTCODE_SHORTS_WORKFLOW_COMPLETE output=$outputRoot fit_exit=$fitExit"
exit $fitExit
