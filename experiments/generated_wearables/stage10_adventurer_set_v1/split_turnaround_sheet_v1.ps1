param(
    [Parameter(Mandatory = $true)][string]$InputImage,
    [Parameter(Mandatory = $true)][string]$OutputDirectory
)

Add-Type -AssemblyName System.Drawing
$resolvedInput = (Resolve-Path -LiteralPath $InputImage).Path
$resolvedOutput = [System.IO.Path]::GetFullPath($OutputDirectory)
[System.IO.Directory]::CreateDirectory($resolvedOutput) | Out-Null
$source = [System.Drawing.Bitmap]::FromFile($resolvedInput)
try {
    $panelWidth = [int][Math]::Floor($source.Width / 4)
    $canvasSize = [Math]::Max($panelWidth, $source.Height)
    $names = @('front', 'right', 'back', 'left')
    for ($index = 0; $index -lt 4; $index++) {
        $canvas = New-Object System.Drawing.Bitmap($canvasSize, $canvasSize)
        try {
            $graphics = [System.Drawing.Graphics]::FromImage($canvas)
            try {
                $graphics.Clear([System.Drawing.Color]::White)
                $graphics.CompositingMode = [System.Drawing.Drawing2D.CompositingMode]::SourceCopy
                $graphics.DrawImage(
                    $source,
                    (New-Object System.Drawing.Rectangle(([int](($canvasSize - $panelWidth) / 2)), 0, $panelWidth, $source.Height)),
                    (New-Object System.Drawing.Rectangle(($index * $panelWidth), 0, $panelWidth, $source.Height)),
                    [System.Drawing.GraphicsUnit]::Pixel
                )
            }
            finally {
                $graphics.Dispose()
            }
            $target = Join-Path $resolvedOutput ($names[$index] + '.png')
            $canvas.Save($target, [System.Drawing.Imaging.ImageFormat]::Png)
        }
        finally {
            $canvas.Dispose()
        }
    }
}
finally {
    $source.Dispose()
}

Write-Output "TURNAROUND_SPLIT_PASS input=$resolvedInput output=$resolvedOutput"
