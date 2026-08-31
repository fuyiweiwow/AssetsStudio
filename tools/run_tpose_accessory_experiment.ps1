param(
    [string]$Actor,
    [string]$Profile,
    [string]$SourceAuthority,
    [string]$SlotId = "waist_accessory",
    [string]$Subject = "Q版日漫西幻皮革腰带与腰包",
    [int]$Seed = 20260831,
    [int]$Steps = 20,
    [ValidateRange(0.01, 1.0)]
    [double]$WidthFactor = 1.0,
    [ValidateRange(0.01, 1.0)]
    [double]$DepthFactor = 1.0,
    [ValidatePattern("^[A-Za-z0-9_-]*$")]
    [string]$FitVariant = "",
    [switch]$SurfaceConform,
    [switch]$ReuseShape,
    [switch]$NoRegister,
    [switch]$CheckEnvironment
)

$ErrorActionPreference = "Stop"
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$testsRoot = Split-Path -Parent $projectRoot

if ([string]::IsNullOrWhiteSpace($Actor)) {
    $Actor = Join-Path $projectRoot "milestones\actor_core\chibi3_standard_v1_source_review_20260831\candidates\v9b_balanced\chibi3_v9b_balanced.glb"
}
if ([string]::IsNullOrWhiteSpace($Profile)) {
    $Profile = Join-Path $projectRoot "references\actor_core\actor_core_chibi3_v9b\actor_slot_profile_v2.json"
}
if ([string]::IsNullOrWhiteSpace($SourceAuthority)) {
    $SourceAuthority = Join-Path $projectRoot "references\slot_authorities\waist_accessory\waist_accessory_turnaround_v1.png"
}

function Resolve-Executable([string]$Configured, [string[]]$Candidates) {
    foreach ($candidate in @($Configured) + $Candidates) {
        if ([string]::IsNullOrWhiteSpace($candidate)) { continue }
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
        $command = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($null -ne $command -and $command.CommandType -eq "Application") {
            return $command.Source
        }
    }
    throw "No usable executable was found. Configure the corresponding ASSETSSTUDIO environment variable."
}

$Python = Resolve-Executable $env:ASSETSSTUDIO_PYTHON @("python.exe", "python3.exe")
$HunyuanPython = Resolve-Executable $env:ASSETSSTUDIO_HUNYUAN_PYTHON @(
    (Join-Path $testsRoot "Hunyuan3D_Experiment\venv-py310\Scripts\python.exe"),
    (Join-Path $testsRoot "Hunyuan3D_Experiment\.venv\Scripts\python.exe"),
    (Join-Path $testsRoot "Hunyuan3D-2\.venv\Scripts\python.exe")
)
$Blender = & $Python -c "import sys; sys.path.insert(0, r'$($projectRoot.Replace("'", "''"))\tools\model_test'); from blender_environment import discover_blender; print(discover_blender(None))"
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $Blender -PathType Leaf)) {
    throw "Blender discovery failed. Set ASSETSSTUDIO_BLENDER or install Blender beside the workspace."
}
if ($CheckEnvironment) {
    Write-Output "ASSETSSTUDIO_TPOSE_ACCESSORY_ENVIRONMENT_READY"
    Write-Output "Python=$Python"
    Write-Output "HunyuanPython=$HunyuanPython"
    Write-Output "Blender=$Blender"
    exit 0
}

$shapeId = "waist_belt_pouch_chibi3_v9b_seed$Seed"
$candidateId = $shapeId
if (-not [string]::IsNullOrWhiteSpace($FitVariant)) {
    $candidateId = "${candidateId}_$FitVariant"
}
$workRoot = Join-Path $projectRoot "workspace\accessory_fit\chibi3_v9b\$SlotId\seed_$Seed"
$rgbRoot = Join-Path $workRoot "source_rgb"
$rgbaRoot = Join-Path $workRoot "source_rgba"
$shapeRoot = Join-Path $workRoot "hunyuan"
$fitRoot = Join-Path $workRoot $(if ([string]::IsNullOrWhiteSpace($FitVariant)) { "fitted" } else { "fitted_$FitVariant" })
$preparation = Join-Path $workRoot "source_preparation.json"
$shape = Join-Path $shapeRoot "$shapeId.glb"
$shapeManifest = Join-Path $shapeRoot "shape_manifest.json"

Push-Location $projectRoot
try {
    & $Python tools/model_test/prepare_accessory_multiview.py --input $SourceAuthority --output-dir $rgbRoot --manifest $preparation
    if ($LASTEXITCODE -ne 0) { throw "Accessory multiview preparation failed." }

    & $HunyuanPython tools/model_test/remove_background_hunyuan.py --input-dir $rgbRoot --output-dir $rgbaRoot
    if ($LASTEXITCODE -ne 0) { throw "Hunyuan background removal failed." }

    if (-not $ReuseShape -or -not (Test-Path -LiteralPath $shape -PathType Leaf)) {
        & $HunyuanPython tools/model_test/run_hunyuan3d_mv_shape.py `
            --asset-kind accessory `
            --cpu-offload `
            --front (Join-Path $rgbaRoot "front.png") `
            --left (Join-Path $rgbaRoot "left.png") `
            --back (Join-Path $rgbaRoot "back.png") `
            --output $shape `
            --manifest $shapeManifest `
            --seed $Seed `
            --steps $Steps `
            --octree-resolution 256
        if ($LASTEXITCODE -ne 0) { throw "Accessory Hunyuan shape gate failed." }
    }

    $fitArguments = @(
        "--background", "--factory-startup", "--python", "tools/model_test/fit_tpose_accessory_blender.py", "--",
        "--actor", $Actor,
        "--accessory", $shape,
        "--profile", $Profile,
        "--slot-id", $SlotId,
        "--source-preparation", $preparation,
        "--shape-manifest", $shapeManifest,
        "--output-dir", $fitRoot,
        "--asset-id", $candidateId,
        "--width-factor", $WidthFactor,
        "--depth-factor", $DepthFactor,
        "--resolution", 768
    )
    if ($SurfaceConform) { $fitArguments += "--surface-conform" }
    & $Blender @fitArguments
    if ($LASTEXITCODE -ne 0) { throw "Static T-Pose fit gate failed." }

    if (-not $NoRegister) {
        & $Python tools/model_test/register_tpose_accessory_candidate.py `
            --fit-report (Join-Path $fitRoot "fit_report.json") `
            --shape-manifest $shapeManifest `
            --source-preparation $preparation `
            --subject $Subject
        if ($LASTEXITCODE -ne 0) { throw "Local candidate registration failed." }
    }

    Write-Output "ASSETSSTUDIO_TPOSE_ACCESSORY_WORKFLOW_PASS"
    Write-Output "CandidateId=$candidateId"
    Write-Output "FitReport=$(Join-Path $fitRoot 'fit_report.json')"
    Write-Output "Registered=$(-not $NoRegister)"
}
finally {
    Pop-Location
}
