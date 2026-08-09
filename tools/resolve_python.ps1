function Resolve-PythonExecutable {
    param(
        [Parameter(Mandatory = $false)]
        [string]$RequestedPath,

        [Parameter(Mandatory = $true)]
        [string]$ProjectRoot
    )

    $requestedValue = $RequestedPath
    if ([string]::IsNullOrWhiteSpace($requestedValue)) {
        $requestedValue = $env:PYTHON_BIN
    }

    if (-not [string]::IsNullOrWhiteSpace($requestedValue)) {
        $command = Get-Command $requestedValue -ErrorAction SilentlyContinue
        if ($null -ne $command -and ($command.CommandType -eq "Application" -or $command.CommandType -eq "Alias")) {
            return $command.Source
        }
        if (Test-Path -LiteralPath $requestedValue -PathType Leaf) {
            return (Resolve-Path -LiteralPath $requestedValue).Path
        }
        throw "Python executable was not found at '$requestedValue'. Set PYTHON_BIN or pass -PythonPath."
    }

    $fallbackCandidates = @(
        "E:\env\venv\Scripts\python.exe",
        (Join-Path $ProjectRoot ".venv\Scripts\python.exe")
    )
    foreach ($candidate in $fallbackCandidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    foreach ($commandName in @("python", "python3", "py")) {
        $command = Get-Command $commandName -ErrorAction SilentlyContinue
        if ($null -ne $command -and $command.CommandType -eq "Application") {
            return $command.Source
        }
    }

    if (Test-Path -LiteralPath "C:\Python314\python.exe" -PathType Leaf) {
        return (Resolve-Path -LiteralPath "C:\Python314\python.exe").Path
    }

    throw "Python executable was not found. Set PYTHON_BIN, pass -PythonPath, or add Python to PATH."
}
