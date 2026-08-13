param(
    [string]$BlenderPath = "E:\Env\Blender\blender.exe",
    [string]$HairBlend = "",
    [string]$HairObject = "HairUnderCapCandidate",
    [string]$HairBundleId = "hair_under_cap_v1",
    [string]$HairStatus = "candidate",
    [ValidateSet("conservative", "coverage")][string]$ScalpVariant = "coverage",
    [switch]$AssembleWithSeed04
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$blender = (Resolve-Path -LiteralPath $BlenderPath).Path
$hairRecipePath = Join-Path $projectRoot "milestones\hair\first_bundle_recipe_v1.json"
$variantSlug = if ($ScalpVariant -eq "conservative") { "conservative" } else { "coverage" }
$defaultHairBlend = Join-Path $projectRoot "workspace\cache\hair\seed04_scalp_base_${variantSlug}_v1\seed04_scalp_base_${variantSlug}_v1.blend"
$hairBlendPath = if ([string]::IsNullOrWhiteSpace($HairBlend)) { $defaultHairBlend } else { $HairBlend }
$hairBlend = (Resolve-Path -LiteralPath $hairBlendPath).Path
$seedRecipe = Get-Content -LiteralPath $hairRecipePath -Raw -Encoding UTF8 | ConvertFrom-Json
$seedHairBlend = Join-Path (Join-Path $projectRoot $seedRecipe.cache.directory) $seedRecipe.cache.blend
$primaryHairBlend = if ($AssembleWithSeed04) { $seedHairBlend } else { $hairBlend }
$primaryHairObject = if ($AssembleWithSeed04) { "HairCandidate_Blend" } else { $HairObject }
$outputDirectory = if ($AssembleWithSeed04) { Join-Path $projectRoot "studio\public\generated\hair-candidates\workflow-seed04-scalp-${variantSlug}-v1" } else { Join-Path $projectRoot "studio\public\generated\hair-candidates\seed04-scalp-${variantSlug}-v1" }
$output = if ($AssembleWithSeed04) { Join-Path $outputDirectory "actor-hair-workflow-v2.glb" } else { Join-Path $outputDirectory "actor-seed04-scalp-base-v1.glb" }
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null

if ($AssembleWithSeed04 -and -not (Test-Path -LiteralPath $seedHairBlend -PathType Leaf)) {
    & (Join-Path $projectRoot "tools\build_first_hair_bundle.ps1") -BlenderPath $blender
    if ($LASTEXITCODE -ne 0) { throw "First hair bundle build failed with exit code $LASTEXITCODE" }
}

$blenderArguments = @(
    "--factory-startup", "--background", "--python-exit-code", "1",
    "--python", (Join-Path $projectRoot "tools\blender\export_studio_actor_preview.py"), "--",
    "--base-blend", (Join-Path $projectRoot "milestones\shoes\cartoon_sneaker_v10\actor_cartoon_sneaker_fbx_v10_length_expanded.blend"),
    "--face-blend", (Join-Path $projectRoot "milestones\body\chibi_actor_eye_assembly_v2.blend"),
    "--top-blend", (Join-Path $projectRoot "milestones\tops\actor_native_tshirt_v5\actor_native_tshirt_body_component_v5_upperarm_coverage.blend"),
    "--pants-blend", (Join-Path $projectRoot "milestones\pants\native_control_v0\native_control_shorts_v0.blend"),
    "--hair-blend", $primaryHairBlend,
    "--hair-object", $primaryHairObject,
    "--hair-bundle-id", $HairBundleId,
    "--hair-status", $HairStatus
)
if ($AssembleWithSeed04) {
    $blenderArguments += @("--hair-components", "Chloe_hair_bangs_04", "Chloe_hair_side_01", "Chloe_hair_back_01", "under_cap")
} else {
    $blenderArguments += @("--hair-components", "under_cap")
}
if ($AssembleWithSeed04) {
    $blenderArguments += @("--hair-extra-blend", $hairBlend, "--hair-extra-object", "HairUnderCapCandidate", "--hair-extra-name", "HairSeed04ScalpBase")
}
$blenderArguments += @("--hair-recipe", $hairRecipePath, "--output", $output)
& $blender @blenderArguments
if ($LASTEXITCODE -ne 0) { throw "Hair candidate Actor preview export failed with exit code $LASTEXITCODE" }

$validationHairNode = if ($AssembleWithSeed04) { "HairBundle_Female_Seed04" } else { "HairUnderCap_Candidate" }
$validationArguments = @(
    (Join-Path $projectRoot "tools\validate_studio_actor_preview.py"),
    "--glb", $output,
    "--manifest", ([System.IO.Path]::ChangeExtension($output, ".manifest.json")),
    "--hair-recipe", $hairRecipePath,
    "--hair-node", $validationHairNode,
    "--hair-bundle-id", $HairBundleId
)
if ($AssembleWithSeed04) { $validationArguments += @("--hair-node", "HairSeed04ScalpBase") }
python @validationArguments
if ($LASTEXITCODE -ne 0) { throw "Hair candidate Actor preview validation failed with exit code $LASTEXITCODE" }
Write-Output "ASSETSSTUDIO_HAIR_CANDIDATE_PREVIEW_PASS output=$output"
