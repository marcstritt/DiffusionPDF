$ErrorActionPreference = "Stop"

$versionLine = Get-Content diffusion_pdf/version.py | Select-String '__version__ = "(.*)"'
$version = $versionLine.Matches.Groups[1].Value

pyinstaller packaging/diffusion_pdf.spec --noconfirm

$exePath = "dist/DiffusionPDF-win64.exe"
$hash = (Get-FileHash $exePath -Algorithm SHA256).Hash.ToLower()
"$hash  DiffusionPDF-win64.exe" | Set-Content "$exePath.sha256" -Encoding ascii

Write-Host "Build v$version -> $exePath"
Write-Host "A publier sur GitHub Releases (tag v$version) : $exePath et $exePath.sha256"
