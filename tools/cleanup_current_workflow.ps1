param([switch]$Apply)

$ErrorActionPreference = "Stop"
$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$workspaceRoot = Join-Path $repoRoot "workspace"
$testsRoot = Split-Path -Parent $repoRoot
$hunyuanRoot = Join-Path $testsRoot "Hunyuan3D_Experiment"
$protectedRigged = Join-Path $workspaceRoot "actor_core\0ef398ca94d445f18226a8bf2a991c79\accurig_handoff\actor_core_0ef398ca_v1_accurig_input_rigged.fbx"

function Assert-Descendant([string]$Root, [string]$Target) {
    $resolvedRoot = [IO.Path]::GetFullPath($Root).TrimEnd('\')
    $resolvedTarget = [IO.Path]::GetFullPath($Target).TrimEnd('\')
    if ($resolvedTarget -eq $resolvedRoot -or -not $resolvedTarget.StartsWith($resolvedRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw "Unsafe cleanup target: $resolvedTarget (root: $resolvedRoot)"
    }
}

function Remove-WorkflowPath([string]$Root, [string]$Target, [string]$Reason) {
    Assert-Descendant $Root $Target
    if (-not (Test-Path -LiteralPath $Target)) { return }
    $resolved = (Resolve-Path -LiteralPath $Target).Path
    Write-Output "CLEANUP_TARGET reason=$Reason path=$resolved"
    if ($Apply) {
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
}

if (-not (Test-Path -LiteralPath $protectedRigged -PathType Leaf)) {
    throw "Protected AccuRIG export is missing: $protectedRigged"
}
$protectedHash = (Get-FileHash -LiteralPath $protectedRigged -Algorithm SHA256).Hash
if ($protectedHash -ne "76CDFB3B70A357625DC5CFEEA95F033D49A06871DCF1BE4477255DE0DF4FE065") {
    throw "Protected AccuRIG export hash changed: $protectedHash"
}
Write-Output "PROTECTED_ACCURIG path=$protectedRigged sha256=$protectedHash"

$workspaceKeep = @("actor_core", "local_asset_library", "local_3d_asset_library", "local_animation_library")
Get-ChildItem -LiteralPath $workspaceRoot -Force | Where-Object {
    $workspaceKeep -notcontains $_.Name
} | ForEach-Object {
    Remove-WorkflowPath $workspaceRoot $_.FullName "obsolete workspace experiment"
}

$actorRoot = Join-Path $workspaceRoot "actor_core\0ef398ca94d445f18226a8bf2a991c79"
$intakesRoot = Join-Path $actorRoot "manual_accurig\intakes"
if (Test-Path -LiteralPath $intakesRoot) {
    Get-ChildItem -LiteralPath $intakesRoot -Directory -Force | ForEach-Object {
        $manifestPath = Join-Path $_.FullName "intake.json"
        if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
            throw "AccuRIG intake has no manifest: $($_.FullName)"
        }
        $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding utf8 | ConvertFrom-Json
        if ($manifest.status -eq "failed") {
            Remove-WorkflowPath $intakesRoot $_.FullName "failed AccuRIG intake"
        }
    }
}
if (Test-Path -LiteralPath (Join-Path $actorRoot "rig_calibration_v2\rig_calibration.json")) {
    Remove-WorkflowPath $actorRoot (Join-Path $actorRoot "rig_calibration") "superseded rig calibration"
}

Remove-WorkflowPath $repoRoot (Join-Path $repoRoot "third_party") "retired GarmentCode runtimes"
Remove-WorkflowPath $repoRoot (Join-Path $repoRoot "studio\public") "retired generated Studio previews"
Remove-WorkflowPath $repoRoot (Join-Path $repoRoot "studio\dist") "rebuildable Studio output"

$hunyuanObsolete = @(
    "Hunyuan3D-2-mv-source.zip",
    "Hunyuan3D-2.1-source",
    "Hunyuan3D-2.1-sparse",
    "stage2_imagegen_adventurer",
    "stage3_adventurer_parts",
    "stage4_full_config_adventurer",
    "stage5_old_actor_hunyuan_clothing",
    "stage6_dota_wearable_v1",
    "stage7_dota_torso_rigid_authored_v1",
    "stage8_adventurer_torso_closefit_v1",
    "stage9_hunyuan_adapter_transfer_v1",
    "ACTOR_V2_MULTIVIEW_CLOTHING_WORKFLOW_CURRENT_ADDENDUM_2026-08-19.md",
    "ACTOR_V2_MULTIVIEW_CLOTHING_WORKFLOW_V1.md",
    "compare_glb_bounds_v1.py",
    "render_glb_views.py",
    "local_models\Hunyuan3D-2.1",
    "local_models\Hunyuan3D-2mv\.cache",
    "local_models\Hunyuan3D-2mv\hunyuan3d-dit-v2-mv\model.fp16.ckpt"
)
foreach ($relative in $hunyuanObsolete) {
    Remove-WorkflowPath $hunyuanRoot (Join-Path $hunyuanRoot $relative) "non-current Hunyuan experiment/model"
}

$sourceRoot = Join-Path $hunyuanRoot "Hunyuan3D-2-main"
$sourceObsolete = @(
    "assets", "docs", "examples", ".gitignore", ".readthedocs.yaml",
    "api_server.py", "blender_addon.py", "gradio_app.py", "minimal_demo.py",
    "minimal_vae_demo.py", "README.md", "README_ja_jp.md"
)
foreach ($relative in $sourceObsolete) {
    Remove-WorkflowPath $sourceRoot (Join-Path $sourceRoot $relative) "official source demo/document asset"
}

if ($Apply) {
    Write-Output "CURRENT_WORKFLOW_CLEANUP_APPLIED"
} else {
    Write-Output "CURRENT_WORKFLOW_CLEANUP_DRY_RUN use=-Apply"
}
