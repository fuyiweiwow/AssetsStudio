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
    $panelWidth = [int][Math]::Floor($source.Width / 2)
    $panelHeight = [int][Math]::Floor($source.Height / 2)
    $canvasSize = [Math]::Max($panelWidth, $panelHeight)
    $views = @(
        @{ Name = 'front'; Column = 0; Row = 0 },
        @{ Name = 'right'; Column = 1; Row = 0 },
        @{ Name = 'back'; Column = 0; Row = 1 },
        @{ Name = 'left'; Column = 1; Row = 1 }
    )
    foreach ($view in $views) {
        $canvas = New-Object System.Drawing.Bitmap($canvasSize, $canvasSize)
        try {
            $graphics = [System.Drawing.Graphics]::FromImage($canvas)
            try {
                $graphics.Clear([System.Drawing.Color]::White)
                $graphics.CompositingMode = [System.Drawing.Drawing2D.CompositingMode]::SourceCopy
                $destination = New-Object System.Drawing.Rectangle(
                    ([int](($canvasSize - $panelWidth) / 2)),
                    ([int](($canvasSize - $panelHeight) / 2)),
                    $panelWidth,
                    $panelHeight
                )
                $sourceRectangle = New-Object System.Drawing.Rectangle(
                    ($view.Column * $panelWidth),
                    ($view.Row * $panelHeight),
                    $panelWidth,
                    $panelHeight
                )
                $graphics.DrawImage($source, $destination, $sourceRectangle, [System.Drawing.GraphicsUnit]::Pixel)
            }
            finally {
                $graphics.Dispose()
            }
            $target = Join-Path $resolvedOutput ($view.Name + '.png')
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

Write-Output "TURNAROUND_GRID_SPLIT_PASS input=$resolvedInput output=$resolvedOutput"
