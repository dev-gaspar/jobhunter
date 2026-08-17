# Build local de JobHunter Desktop: assets -> PyInstaller -> selftest -> Inno Setup.
# Uso:  powershell -File desktop/packaging/build.ps1 [-SkipInstaller]
param([switch]$SkipInstaller)

$ErrorActionPreference = "Stop"
$repo = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $repo

Write-Host "== 1/4 Assets ==" -ForegroundColor Cyan
python desktop/packaging/gen_assets.py

Write-Host "== 2/4 PyInstaller ==" -ForegroundColor Cyan
pyinstaller --noconfirm desktop/packaging/jobhunter.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller fallo" }

Write-Host "== 3/4 Selftest ==" -ForegroundColor Cyan
& "$repo\dist\JobHunter\JobHunter.exe" --selftest
if ($LASTEXITCODE -ne 0) {
    Get-Content "$env:TEMP\jobhunter_selftest.txt" -ErrorAction SilentlyContinue
    throw "Selftest fallo"
}
Get-Content "$env:TEMP\jobhunter_selftest.txt"
Write-Host "Selftest OK" -ForegroundColor Green

if ($SkipInstaller) { Write-Host "Instalador omitido (-SkipInstaller)"; exit 0 }

Write-Host "== 4/4 Inno Setup ==" -ForegroundColor Cyan
# Bootstrapper de WebView2 (para Windows 10 sin WebView2)
$bootstrapper = "$PSScriptRoot\MicrosoftEdgeWebView2Setup.exe"
if (-not (Test-Path $bootstrapper)) {
    Write-Host "Descargando bootstrapper de WebView2..."
    Invoke-WebRequest -Uri "https://go.microsoft.com/fwlink/p/?LinkId=2124703" -OutFile $bootstrapper
}

$iscc = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles(x86)\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "ISCC.exe no encontrado. Instala Inno Setup 6." }

# La version se extrae de jobhunter/constants.py
$version = (python -c "from jobhunter.constants import VERSION; print(VERSION)").Trim()
& $iscc "/DAppVersion=$version" "$PSScriptRoot\installer.iss"
if ($LASTEXITCODE -ne 0) { throw "ISCC fallo" }

Write-Host "Instalador listo: dist\JobHunterSetup-x64.exe" -ForegroundColor Green
