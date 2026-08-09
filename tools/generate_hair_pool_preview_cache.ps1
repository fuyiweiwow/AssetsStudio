param(
    [string]$Blender = "",
    [ValidateSet("all", "female", "male")]
    [string]$Gender = "all",
    [string]$OutputRoot = "workspace\hair\pool_preview_gallery"
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $projectRoot
try {
    if ([string]::IsNullOrWhiteSpace($Blender)) {
        $parentBlender = Join-Path (Split-Path $projectRoot -Parent) "blender-4.5.10-windows-x64\blender.exe"
        if (Test-Path -LiteralPath $parentBlender -PathType Leaf) {
            $Blender = $parentBlender
        } else {
            $command = Get-Command blender -ErrorAction SilentlyContinue
            if ($null -eq $command) { throw "Blender executable not found; pass -Blender explicitly." }
            $Blender = $command.Source
        }
    }
    if (-not (Test-Path -LiteralPath $Blender -PathType Leaf)) { throw "Blender executable is missing: $Blender" }

    $pool = (Get-Content -Raw "milestones\hair\hair_random_pool_v1.json" | ConvertFrom-Json).components
    $actor = "milestones\body\chibi_actor_mixamo_walk_v1.blend"
    $fitScript = "tools\blender\fit_blend_hair_candidate.py"
    $total = 0

    function Invoke-HairPreview([string]$genderName, [string[]]$objects, [string]$sourceBlend, [string]$anchor, [bool]$normalizeSource) {
        $script:total++
        if ($genderName -eq "female") {
            $name = "pool_female_{0}_{1}" -f $objects[1].Split('_')[-1], $objects[2].Split('_')[-1]
        } else {
            $backSuffix = if ($objects.Count -gt 2) { $objects[2].Split('_')[-1] } else { "none" }
            $name = "pool_male_{0}_{1}_{2}" -f $objects[0].Split('_')[-1], $objects[1].Split('_')[-1], $backSuffix
        }
        $output = Join-Path $OutputRoot $name
        New-Item -ItemType Directory -Force -Path $output | Out-Null
        $arguments = @(
            "-b", "--python", $fitScript, "--",
            "--hair-source-blend", $sourceBlend,
            "--hair-objects"
        ) + $objects + @(
            "--source-anchor-object", $anchor,
            "--actor-blend", $actor,
            "--output-blend", (Join-Path $output "actor.blend"),
            "--output-dir", $output
        )
        if ($normalizeSource) { $arguments += "--normalize-source-component-layout" }
        else { $arguments += "--normalize-components-to-head" }
        & $Blender @arguments 2>&1 | Select-String -Pattern "CHIBI_BLEND_HAIR_CANDIDATE_PASS|Error|error"
        if ($LASTEXITCODE -ne 0) { throw "Hair preview generation failed: $name" }
    }

    $genders = if ($Gender -eq "all") { @("female", "male") } else { @($Gender) }
    foreach ($genderName in $genders) {
        $items = @($pool | Where-Object { $_.gender -eq $genderName })
        $base = @($items | Where-Object { $_.role -eq "base_cap" })
        $side = @($items | Where-Object { $_.role -eq "side_coverage" })
        if ($genderName -eq "female") {
            $front = @($items | Where-Object { $_.role -eq "front_bangs" })
            foreach ($b in $base) { foreach ($f in $front) { foreach ($s in $side) {
                Invoke-HairPreview $genderName @($b.object, $f.object, $s.object) "milestones\hair\Blender-Chloe_Hair.blend" "Chloe_head_dummy" $true
            }}}
        } else {
            $back = @($items | Where-Object { $_.role -eq "back_section" })
            foreach ($b in $base) { foreach ($s in $side) {
                Invoke-HairPreview $genderName @($b.object, $s.object) "milestones\hair\male_source\Blend_Hair.blend" "Colin_head_dummy" $false
                foreach ($k in $back) {
                    Invoke-HairPreview $genderName @($b.object, $s.object, $k.object) "milestones\hair\male_source\Blend_Hair.blend" "Colin_head_dummy" $false
                }
            }}
        }
    }
    Write-Output "HAIR_POOL_PREVIEW_CACHE_PASS generated=$total output=$OutputRoot"
} finally {
    Pop-Location
}
