$ErrorActionPreference = "Stop"

$versionLine = Get-Content diffusion_pdf/version.py | Select-String '__version__ = "(.*)"'
$version = $versionLine.Matches.Groups[1].Value

pyinstaller packaging/diffusion_pdf.spec --noconfirm

$exePath = "dist/DiffusionPDF-win64.exe"

Write-Host "Build v$version -> $exePath"
