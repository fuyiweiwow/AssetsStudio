param(
    [string]$BlenderPath,
    [string]$PythonPath,
    [string]$InputBlend = "milestones\body\chibi_actor_mixamo_walk_v1.blend",
    [string]$Output = "workspace\face\face_randomization_v2",
    [int[]]$Seeds = @(20260802, 20260807, 20260800, 20260803),
    [int]$FrameCount = 2
)

$ErrorActionPreference = "Stop"
if ($FrameCount -lt 1) { throw "FrameCount must be positive" }
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
. (Join-Path $PSScriptRoot "resolve_python.ps1")
$python = Resolve-PythonExecutable -RequestedPath $PythonPath -ProjectRoot $root
$defaultBlender = "E:\Env\Blender\blender.exe"
$blender = if ($BlenderPath) { $BlenderPath } else { $defaultBlender }
if (-not (Test-Path -LiteralPath $blender -PathType Leaf)) { throw "Blender executable not found: $blender" }
$inputPath = Join-Path $root $InputBlend
if (-not (Test-Path -LiteralPath $inputPath -PathType Leaf)) { throw "Input Blend not found: $inputPath" }
$outputPath = [System.IO.Path]::GetFullPath((Join-Path $root $Output))
$workspaceRoot = [System.IO.Path]::GetFullPath((Join-Path $root "workspace"))
if (-not $outputPath.StartsWith($workspaceRoot + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Output must remain under workspace: $outputPath"
}
if (Test-Path -LiteralPath $outputPath) {
    Remove-Item -LiteralPath $outputPath -Recurse -Force
}
New-Item -ItemType Directory -Path $outputPath -Force | Out-Null

foreach ($seed in $Seeds) {
    $seedRoot = Join-Path $outputPath "seed_$seed"
    $renderRoot = Join-Path $seedRoot "render"
    $pixelRoot = Join-Path $seedRoot "pixel"
    & $blender --background --python (Join-Path $root "tools\blender\render_accurig_chibi_walk_test.py") -- `
        --input-blend $inputPath `
        --output $renderRoot `
        --appearance-seed $seed `
        --frame-count $FrameCount `
        --soft-toon-lighting
    if ($LASTEXITCODE -ne 0) { throw "Face render failed for seed $seed" }
    & $python (Join-Path $root "tools\process_accurig_walk_pixels.py") `
        --render-dir $renderRoot `
        --output-dir $pixelRoot `
        --frame-count $FrameCount `
        --fps 4
    if ($LASTEXITCODE -ne 0) { throw "Pixel processing failed for seed $seed" }
}

& $python (Join-Path $root "tools\build_chibi_face_variant_contact_sheet.py") --root $outputPath
if ($LASTEXITCODE -ne 0) { throw "Face contact-sheet generation failed" }
& $python (Join-Path $root "tools\validate_chibi_face_randomization.py") --root $outputPath --frame-count $FrameCount
if ($LASTEXITCODE -ne 0) { throw "Face randomization validation failed" }
Write-Output "CHIBI_FACE_RANDOMIZATION_PREVIEW_WRAPPER_PASS output=$outputPath seeds=$($Seeds.Count)"
