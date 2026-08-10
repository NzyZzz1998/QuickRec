param(
    [string]$Version = "8.0.1",
    [string]$Destination = "ffmpeg"
)

$ErrorActionPreference = "Stop"

& choco install ffmpeg "--version=$Version" --no-progress -y --allow-downgrade
$installExitCode = $LASTEXITCODE
if (@(0, 1641, 3010) -notcontains $installExitCode) {
    throw "Chocolatey FFmpeg install failed with exit code $installExitCode"
}

$packageRoot = Join-Path $env:ChocolateyInstall "lib\ffmpeg"
if (-not (Test-Path -LiteralPath $packageRoot -PathType Container)) {
    throw "Chocolatey FFmpeg package directory was not found: $packageRoot"
}

$toolPair = $null
$candidates = Get-ChildItem -LiteralPath $packageRoot -Recurse -File -Filter "ffmpeg.exe" |
    Where-Object { $_.Length -gt 1MB } |
    Sort-Object FullName
foreach ($candidate in $candidates) {
    $probePath = Join-Path $candidate.DirectoryName "ffprobe.exe"
    if (Test-Path -LiteralPath $probePath -PathType Leaf) {
        $probe = Get-Item -LiteralPath $probePath
        if ($probe.Length -gt 1MB) {
            $toolPair = @($candidate, $probe)
            break
        }
    }
}

if ($null -eq $toolPair) {
    throw "Matching FFmpeg and FFprobe executables were not found in $packageRoot"
}

New-Item -ItemType Directory -Path $Destination -Force | Out-Null
Copy-Item -LiteralPath $toolPair[0].FullName -Destination (Join-Path $Destination "ffmpeg.exe") -Force
Copy-Item -LiteralPath $toolPair[1].FullName -Destination (Join-Path $Destination "ffprobe.exe") -Force

foreach ($toolName in @("ffmpeg.exe", "ffprobe.exe")) {
    $path = Join-Path $Destination $toolName
    $file = Get-Item -LiteralPath $path
    if ($file.Length -le 1MB) {
        throw "Staged media tool is not a real executable: $path"
    }
    $versionOutput = & $path -version 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Staged media tool failed to start: $path"
    }
    $expectedPrefix = if ($toolName -eq "ffmpeg.exe") {
        "ffmpeg version $Version"
    } else {
        "ffprobe version $Version"
    }
    if (-not ($versionOutput | Select-Object -First 1).StartsWith($expectedPrefix)) {
        throw "Unexpected media tool version for ${path}: $($versionOutput | Select-Object -First 1)"
    }
    Write-Output ($versionOutput | Select-Object -First 1)
}
