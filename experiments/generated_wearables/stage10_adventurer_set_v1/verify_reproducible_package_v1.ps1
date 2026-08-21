[CmdletBinding()]
param(
    [string]$BlenderExe = $env:BLENDER_EXE,
    [switch]$SkipBlenderAudits,
    [switch]$RebuildWaistSmoke
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$stageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $stageRoot "..\..\..")).Path
$manifestPath = Join-Path $stageRoot "REPRODUCIBLE_PACKAGE_V1.json"
$manifest = Get-Content -Raw -Encoding UTF8 $manifestPath | ConvertFrom-Json
$failures = [System.Collections.Generic.List[string]]::new()

foreach ($entry in $manifest.required_files) {
    $path = Join-Path $stageRoot ($entry.path -replace "/", "\")
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        $failures.Add("missing: $($entry.path)")
        continue
    }
    $payload = [System.IO.File]::ReadAllBytes($path)
    if ($entry.hash_mode -eq "text_utf8_lf") {
        $text = [System.Text.Encoding]::UTF8.GetString($payload)
        $text = $text.Replace("`r`n", "`n").Replace("`r", "`n")
        $payload = [System.Text.UTF8Encoding]::new($false).GetBytes($text)
    } elseif ($entry.hash_mode -ne "binary_exact") {
        $failures.Add("unknown hash mode: $($entry.path): $($entry.hash_mode)")
        continue
    }
    if ($payload.Length -ne [long]$entry.bytes) {
        $failures.Add("size mismatch: $($entry.path)")
        continue
    }
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $actualHash = ([System.BitConverter]::ToString($sha.ComputeHash($payload))).Replace("-", "").ToLowerInvariant()
    } finally {
        $sha.Dispose()
    }
    if ($actualHash -ne $entry.sha256) {
        $failures.Add("hash mismatch: $($entry.path)")
    }
}

$expected = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
foreach ($entry in $manifest.required_files) {
    [void]$expected.Add($entry.path)
}
$actualFiles = Get-ChildItem -Recurse -File $stageRoot | Where-Object {
    $_.FullName -ne $manifestPath -and
    $_.FullName -notmatch "[\\/]__pycache__[\\/]" -and
    $_.Extension -ne ".blend1"
}
foreach ($file in $actualFiles) {
    $relative = $file.FullName.Substring($stageRoot.Length + 1).Replace("\", "/")
    if (-not $expected.Contains($relative)) {
        $failures.Add("unmanifested file: $relative")
    }
}

if ($failures.Count -gt 0) {
    $failures | ForEach-Object { Write-Error $_ }
    throw "Package integrity validation failed with $($failures.Count) error(s)."
}
Write-Host "Package hashes: PASS ($($manifest.file_count) files, $($manifest.package_bytes) bytes)"

if ($SkipBlenderAudits) {
    Write-Host "Blender audits: SKIPPED"
    exit 0
}

if ([string]::IsNullOrWhiteSpace($BlenderExe)) {
    $workspaceCandidate = Join-Path (Split-Path -Parent $repoRoot) "blender-4.5.10-windows-x64\blender.exe"
    if (Test-Path -LiteralPath $workspaceCandidate) {
        $BlenderExe = $workspaceCandidate
    } else {
        $command = Get-Command blender -ErrorAction SilentlyContinue
        if ($null -ne $command) {
            $BlenderExe = $command.Source
        }
    }
}
if ([string]::IsNullOrWhiteSpace($BlenderExe) -or -not (Test-Path -LiteralPath $BlenderExe)) {
    throw "Blender was not found. Set BLENDER_EXE or pass -BlenderExe."
}

$validationRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("assetslab-stage10-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $validationRoot | Out-Null
$blend = Join-Path $stageRoot "milestone\adventurer_set_workflow_v3.blend"

function Invoke-BlenderAudit {
    param([string]$Script, [string]$Output)
    & $BlenderExe --background --factory-startup --python (Join-Path $stageRoot $Script) -- --input-blend $blend --output $Output
    if ($LASTEXITCODE -ne 0) {
        throw "$Script failed with exit code $LASTEXITCODE"
    }
}

try {
    $structureOutput = Join-Path $validationRoot "checkpoint_structure.json"
    $sleeveOutput = Join-Path $validationRoot "sleeve_torso_self_intersection.json"
    $bootOutput = Join-Path $validationRoot "boot_sole_contact.json"
    Invoke-BlenderAudit "audit_reproducible_checkpoint_v1.py" $structureOutput
    Invoke-BlenderAudit "audit_sleeve_torso_self_intersection_v1.py" $sleeveOutput
    Invoke-BlenderAudit "audit_boot_sole_contact_workflow_v1.py" $bootOutput

    $structure = Get-Content -Raw -Encoding UTF8 $structureOutput | ConvertFrom-Json
    $sleeve = Get-Content -Raw -Encoding UTF8 $sleeveOutput | ConvertFrom-Json
    $boot = Get-Content -Raw -Encoding UTF8 $bootOutput | ConvertFrom-Json
    if ($structure.status -ne "pass") {
        throw "Checkpoint structure audit did not pass."
    }
    if ($sleeve.summary.side_frame_tests -ne 16 -or $sleeve.summary.frames_with_intersection -ne 16) {
        throw "Sleeve blocker was not reproduced exactly across all 16 side/frame tests."
    }
    if ($boot.summary.maximum_sole_height_spread -lt 0.19) {
        throw "Boot sole blocker was not reproduced; expected spread >= 0.19."
    }

    if ($RebuildWaistSmoke) {
        $rebuiltBlend = Join-Path $validationRoot "waist_rebuild_smoke.blend"
        $rebuiltManifest = Join-Path $validationRoot "waist_rebuild_smoke.json"
        & $BlenderExe --background --factory-startup --python (Join-Path $stageRoot "build_adventurer_waist_accessory_v1.py") -- --input-blend $blend --source-glb (Join-Path $stageRoot "assets\generated_sources\adventurer_waist_accessory_2mv_v1.glb") --output-blend $rebuiltBlend --manifest $rebuiltManifest
        if ($LASTEXITCODE -ne 0) {
            throw "Waist rebuild smoke test failed with exit code $LASTEXITCODE"
        }
        $waistAudit = Join-Path $validationRoot "waist_rebuild_audit.json"
        & $BlenderExe --background --factory-startup --python (Join-Path $stageRoot "audit_waist_interface_workflow_v1.py") -- --input-blend $rebuiltBlend --output $waistAudit
        if ($LASTEXITCODE -ne 0) {
            throw "Rebuilt waist audit failed with exit code $LASTEXITCODE"
        }
        $waist = Get-Content -Raw -Encoding UTF8 $waistAudit | ConvertFrom-Json
        if ($waist.status -ne "pass") {
            throw "Rebuilt waist did not pass its interface audit."
        }
        Write-Host "Waist rebuild smoke test: PASS"
    }

    Write-Host "Checkpoint structure and known-blocker reproduction: PASS"
} finally {
    if (Test-Path -LiteralPath $validationRoot) {
        Remove-Item -Recurse -Force -LiteralPath $validationRoot
    }
}
