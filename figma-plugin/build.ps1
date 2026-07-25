param([string]$PluginRoot = $PSScriptRoot)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

function New-QuickRecMarkPngBytes {
    $bitmap = New-Object Drawing.Bitmap(96, 96, [Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $graphics = [Drawing.Graphics]::FromImage($bitmap)
    $stream = New-Object IO.MemoryStream
    try {
        $graphics.SmoothingMode = [Drawing.Drawing2D.SmoothingMode]::AntiAlias
        $graphics.Clear([Drawing.Color]::Transparent)
        $blue = New-Object Drawing.SolidBrush([Drawing.Color]::FromArgb(37, 99, 235))
        $green = New-Object Drawing.SolidBrush([Drawing.Color]::FromArgb(16, 124, 65))
        $red = New-Object Drawing.SolidBrush([Drawing.Color]::FromArgb(196, 43, 28))
        try {
            $graphics.FillEllipse($blue, 6, 6, 84, 84)
            $graphics.FillPie($green, 18, 18, 60, 60, -45, 180)
            $graphics.FillEllipse($red, 34, 34, 28, 28)
        }
        finally {
            $blue.Dispose(); $green.Dispose(); $red.Dispose()
        }
        $bitmap.Save($stream, [Drawing.Imaging.ImageFormat]::Png)
        return $stream.ToArray()
    }
    finally {
        $graphics.Dispose(); $bitmap.Dispose(); $stream.Dispose()
    }
}

function Convert-ToFigmaPngBytes {
    param([Parameter(Mandatory = $true)][string]$Path)
    $source = [Drawing.Image]::FromFile($Path)
    $bitmap = $null; $graphics = $null; $stream = $null
    try {
        $bitmap = New-Object Drawing.Bitmap($source.Width, $source.Height, [Drawing.Imaging.PixelFormat]::Format32bppArgb)
        $graphics = [Drawing.Graphics]::FromImage($bitmap)
        $graphics.Clear([Drawing.Color]::Transparent)
        $graphics.DrawImage($source, 0, 0, $source.Width, $source.Height)
        $stream = New-Object IO.MemoryStream
        $bitmap.Save($stream, [Drawing.Imaging.ImageFormat]::Png)
        return $stream.ToArray()
    }
    finally {
        if ($graphics) { $graphics.Dispose() }
        if ($bitmap) { $bitmap.Dispose() }
        if ($source) { $source.Dispose() }
        if ($stream) { $stream.Dispose() }
    }
}

$templatePath = Join-Path $PluginRoot "ui.template.html"
$outputPath = Join-Path $PluginRoot "ui.html"
$assetRoot = Join-Path $PluginRoot "assets"
$markPath = Join-Path $assetRoot "quickrec-mark.png"
if (-not (Test-Path -LiteralPath $templatePath -PathType Leaf)) { throw "Missing Figma plugin template: $templatePath" }

New-Item -ItemType Directory -Force -Path $assetRoot | Out-Null
[IO.File]::WriteAllBytes($markPath, (New-QuickRecMarkPngBytes))
$markBytes = Convert-ToFigmaPngBytes $markPath
[IO.File]::WriteAllBytes($markPath, $markBytes)
$template = Get-Content -LiteralPath $templatePath -Raw -Encoding UTF8
$html = $template.Replace("__QR_MARK_BASE64__", [Convert]::ToBase64String($markBytes))
[IO.File]::WriteAllText($outputPath, $html, [Text.UTF8Encoding]::new($false))

Write-Host "Generated QR Figma plugin UI: $outputPath"
Write-Host "Static PNG: $markPath"
Write-Host "Runtime screenshots embedded: 0"
Write-Host "ui.html size: $((Get-Item -LiteralPath $outputPath).Length) bytes"
