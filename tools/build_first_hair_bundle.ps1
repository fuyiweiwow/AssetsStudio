param(
    [string]$BlenderPath = "E:\Env\Blender\blender.exe",
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$blender = (Resolve-Path -LiteralPath $BlenderPath).Path
$recipePath = Join-Path $projectRoot "milestones\hair\first_bundle_recipe_v1.json"
$recipe = Get-Content -LiteralPath $recipePath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($recipe.schema -ne "assetsstudio_hair_bundle_recipe_v1") {
    throw "Unexpected first hair bundle recipe schema: $($recipe.schema)"
}

$sourceBlend = Join-Path $projectRoot $recipe.source_blend
$actorBlend = Join-Path $projectRoot $recipe.actor_blend
$outputDirectory = Join-Path $projectRoot $recipe.cache.directory
$outputBlend = Join-Path $outputDirectory $recipe.cache.blend
$manifest = Join-Path $outputDirectory "manifest.json"
$requiredOutputs = @(
    $outputBlend,
    $manifest,
    (Join-Path $outputDirectory "front.png"),
    (Join-Path $outputDirectory "right.png"),
    (Join-Path $outputDirectory "back.png"),
    (Join-Path $outputDirectory "left.png")
)
$inputs = @(
    $recipePath,
    $sourceBlend,
    $actorBlend,
    (Join-Path $projectRoot "tools\blender\fit_blend_hair_candidate.py"),
    (Join-Path $projectRoot "tools\blender\hair_fit_support.py")
)

$needsBuild = $Force -or ($requiredOutputs | Where-Object { -not (Test-Path -LiteralPath $_ -PathType Leaf) } | Select-Object -First 1)
if (-not $needsBuild) {
    $outputTime = (Get-Item -LiteralPath $outputBlend).LastWriteTimeUtc
    $needsBuild = [bool]($inputs | Where-Object { (Get-Item -LiteralPath $_).LastWriteTimeUtc -gt $outputTime } | Select-Object -First 1)
}
if ($needsBuild) {
    New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
    $culture = [System.Globalization.CultureInfo]::InvariantCulture
    $arguments = @(
    "--factory-startup",
    "--background",
    "--python-exit-code", "1",
    "--python", (Join-Path $projectRoot "tools\blender\fit_blend_hair_candidate.py"),
    "--",
    "--hair-source-blend", $sourceBlend,
    "--hair-objects"
) + @($recipe.components) + @(
    "--source-anchor-object", [string]$recipe.source_anchor_object,
    "--normalize-source-component-layout",
    "--actor-blend", $actorBlend,
    "--output-blend", $outputBlend,
    "--output-dir", $outputDirectory,
    "--q-height-ratio", ([double]$recipe.fit.q_height_ratio).ToString($culture),
    "--width-ratio", ([double]$recipe.fit.width_ratio).ToString($culture),
    "--color"
) + @($recipe.material.rgba | ForEach-Object { ([double]$_).ToString($culture) })

    & $blender @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "First hair bundle build failed with exit code $LASTEXITCODE"
    }
} else {
    Write-Output "ASSETSSTUDIO_HAIR_BUNDLE_CACHE_HIT output=$outputBlend"
}
foreach ($path in $requiredOutputs) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "First hair bundle output is missing: $path"
    }
}
python (Join-Path $projectRoot "tools\validate_first_hair_bundle.py") --recipe $recipePath --manifest $manifest
if ($LASTEXITCODE -ne 0) {
    throw "First hair bundle validation failed with exit code $LASTEXITCODE"
}
Write-Output "ASSETSSTUDIO_HAIR_BUNDLE_BUILD_PASS output=$outputBlend"
