param(
    [string]$BlenderPath = "E:\Env\Blender\blender.exe",
    [ValidateSet("conservative", "coverage")][string]$Variant = "coverage",
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$blender = (Resolve-Path -LiteralPath $BlenderPath).Path
$actorBlend = Join-Path $projectRoot "milestones\body\chibi_actor_mixamo_walk_v1.blend"
$variantSlug = if ($Variant -eq "conservative") { "conservative" } else { "coverage" }
$outputDirectory = Join-Path $projectRoot "workspace\cache\hair\seed04_scalp_base_${variantSlug}_v1"
$outputBlend = Join-Path $outputDirectory "seed04_scalp_base_${variantSlug}_v1.blend"
$manifest = Join-Path $outputDirectory "manifest.json"
$requiredOutputs = @($outputBlend, $manifest, (Join-Path $outputDirectory "front.png"), (Join-Path $outputDirectory "right.png"), (Join-Path $outputDirectory "back.png"), (Join-Path $outputDirectory "left.png"))
$inputs = @($actorBlend, (Join-Path $projectRoot "tools\blender\generate_hair_under_cap.py"), (Join-Path $projectRoot "tools\blender\hair_fit_support.py"))
$needsBuild = $Force -or ($requiredOutputs | Where-Object { -not (Test-Path -LiteralPath $_ -PathType Leaf) } | Select-Object -First 1)
if (-not $needsBuild) {
    $outputTime = (Get-Item -LiteralPath $outputBlend).LastWriteTimeUtc
    $needsBuild = [bool]($inputs | Where-Object { (Get-Item -LiteralPath $_).LastWriteTimeUtc -gt $outputTime } | Select-Object -First 1)
}
if ($needsBuild) {
    New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
    & $blender --factory-startup --background --python-exit-code 1 --python (Join-Path $projectRoot "tools\blender\generate_hair_under_cap.py") -- `
        --actor-blend $actorBlend `
        --output-blend $outputBlend `
        --output-dir $outputDirectory `
        --profile seed04_scalp_base `
        --variant $Variant `
        --bottom-offset 0.74 `
        --surface-offset 0.060
    if ($LASTEXITCODE -ne 0) { throw "Hair under-cap build failed with exit code $LASTEXITCODE" }
} else {
    Write-Output "ASSETSSTUDIO_HAIR_UNDER_CAP_CACHE_HIT output=$outputBlend"
}
python (Join-Path $projectRoot "tools\validate_hair_under_cap.py") --manifest $manifest
if ($LASTEXITCODE -ne 0) { throw "Hair under-cap validation failed with exit code $LASTEXITCODE" }
Write-Output "ASSETSSTUDIO_HAIR_UNDER_CAP_BUILD_PASS output=$outputBlend"
