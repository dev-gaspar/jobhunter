# JobHunter AI - Instalador para Windows
# Ejecutar: irm https://raw.githubusercontent.com/dev-gaspar/jobhunter/main/install.ps1 | iex

Write-Host ""
Write-Host "       ██╗ ██████╗ ██████╗ ██╗  ██╗██╗   ██╗███╗   ██╗████████╗███████╗██████╗ " -ForegroundColor Cyan
Write-Host "       ██║██╔═══██╗██╔══██╗██║  ██║██║   ██║████╗  ██║╚══██╔══╝██╔════╝██╔══██╗" -ForegroundColor Cyan
Write-Host "       ██║██║   ██║██████╔╝███████║██║   ██║██╔██╗ ██║   ██║   █████╗  ██████╔╝" -ForegroundColor Cyan
Write-Host "  ██   ██║██║   ██║██╔══██╗██╔══██║██║   ██║██║╚██╗██║   ██║   ██╔══╝  ██╔══██╗" -ForegroundColor Cyan
Write-Host "  ╚█████╔╝╚██████╔╝██████╔╝██║  ██║╚██████╔╝██║ ╚████║   ██║   ███████╗██║  ██║" -ForegroundColor Cyan
Write-Host "   ╚════╝  ╚═════╝ ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝   ╚═╝   ╚══════╝╚═╝  ╚═╝" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Busqueda de empleo con IA  |  Instalador Windows" -ForegroundColor DarkGray
Write-Host ""

$InstallDir = "$env:USERPROFILE\.jobhunter"

Write-Host "Instalando JobHunter AI" -ForegroundColor White
Write-Host ""

# ── Verificar requisitos ──
Write-Host "  Verificando requisitos..." -ForegroundColor DarkGray
Write-Host ""
$ok = $true

# Git
if (Get-Command git -ErrorAction SilentlyContinue) {
    $gitVersion = (git --version) -replace 'git version ', ''
    Write-Host "  ✓ Git $gitVersion" -ForegroundColor Green
} else {
    Write-Host "  ✗ Git no encontrado" -ForegroundColor Red
    Write-Host "    Instalalo desde: https://git-scm.com/downloads/win" -ForegroundColor Yellow
    $ok = $false
}

# Python
$py = $null
if (Get-Command python -ErrorAction SilentlyContinue) { $py = "python" }
elseif (Get-Command python3 -ErrorAction SilentlyContinue) { $py = "python3" }

if ($py) {
    $pythonVersion = & $py --version 2>&1
    Write-Host "  ✓ $pythonVersion" -ForegroundColor Green

    # pip
    $pipCheck = & $py -m pip --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ pip disponible" -ForegroundColor Green
    } else {
        Write-Host "  ✗ pip no encontrado" -ForegroundColor Red
        Write-Host "    Ejecuta: $py -m ensurepip --upgrade" -ForegroundColor Yellow
        $ok = $false
    }
} else {
    Write-Host "  ✗ Python no encontrado" -ForegroundColor Red
    Write-Host "    Instalalo desde: https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "    (Marca 'Add Python to PATH' durante la instalacion)" -ForegroundColor Yellow
    $ok = $false
}

# Chrome o Edge
$chrome = $null
$chromePaths = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LocalAppData\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe"
)
foreach ($p in $chromePaths) {
    if (Test-Path $p) { $chrome = $p; break }
}

if ($chrome) {
    $browserName = if ($chrome -like "*Edge*") { "Microsoft Edge" } else { "Google Chrome" }
    Write-Host "  ✓ $browserName encontrado" -ForegroundColor Green
} else {
    Write-Host "  ✗ Google Chrome o Microsoft Edge no encontrado" -ForegroundColor Red
    Write-Host "    Instala uno de estos navegadores:" -ForegroundColor Yellow
    Write-Host "    Chrome: https://www.google.com/chrome/" -ForegroundColor Yellow
    Write-Host "    Edge:   https://www.microsoft.com/edge" -ForegroundColor Yellow
    $ok = $false
}

# Si falta algo, parar
if (-not $ok) {
    Write-Host ""
    Write-Host "  Instala los requisitos faltantes y vuelve a ejecutar el instalador." -ForegroundColor Red
    return
}

Write-Host ""

# ── Clonar o actualizar ──
if (Test-Path $InstallDir) {
    Write-Host "  → Actualizando instalacion existente..." -ForegroundColor Cyan
    Push-Location $InstallDir
    git pull --quiet 2>&1 | Out-Null
    Pop-Location
} else {
    Write-Host "  → Clonando repositorio..." -ForegroundColor Cyan
    git clone --quiet https://github.com/dev-gaspar/jobhunter.git $InstallDir 2>&1 | Out-Null
}

Write-Host "  ✓ Repositorio listo" -ForegroundColor Green

# ── Instalar dependencias ──
Write-Host "  → Instalando dependencias de Python..." -ForegroundColor Cyan
& $py -m pip install --quiet rich requests playwright reportlab 2>&1 | Out-Null

Write-Host "  → Instalando navegador para Playwright..." -ForegroundColor Cyan
& $py -m playwright install chromium 2>&1 | Out-Null

Write-Host "  ✓ Dependencias instaladas" -ForegroundColor Green

# ── Crear directorios ──
New-Item -ItemType Directory -Force -Path "$InstallDir\output\cvs" | Out-Null
New-Item -ItemType Directory -Force -Path "$InstallDir\output\logs" | Out-Null
New-Item -ItemType Directory -Force -Path "$InstallDir\.session" | Out-Null

# ── Crear comando global ──
Write-Host "  → Instalando comando 'jobhunter'..." -ForegroundColor Cyan

$BinDir = "$env:USERPROFILE\.jobhunter\bin"
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null

$WrapperContent = "@echo off`r`n$py `"$InstallDir\job.py`" %*"
[System.IO.File]::WriteAllText("$BinDir\jobhunter.cmd", $WrapperContent)

$WrapperPs1Content = "& $py `"$InstallDir\job.py`" @args"
[System.IO.File]::WriteAllText("$BinDir\jobhunter.ps1", $WrapperPs1Content)

# Agregar al PATH del usuario si no esta
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($UserPath -notlike "*$BinDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$BinDir;$UserPath", "User")
    Write-Host "  ✓ Agregado al PATH del usuario" -ForegroundColor Green
    Write-Host "    (Reinicia la terminal para que surta efecto)" -ForegroundColor Yellow
} else {
    Write-Host "  ✓ Ya esta en el PATH" -ForegroundColor Green
}

$env:Path = "$BinDir;$env:Path"

Write-Host ""
Write-Host "Instalacion completa!" -ForegroundColor Green
Write-Host ""
Write-Host "  Primeros pasos:" -ForegroundColor White
Write-Host "  jobhunter setup                  " -NoNewline -ForegroundColor Cyan; Write-Host "# Configurar API keys y perfil" -ForegroundColor DarkGray
Write-Host "  jobhunter login                  " -NoNewline -ForegroundColor Cyan; Write-Host "# Iniciar sesion en LinkedIn" -ForegroundColor DarkGray
Write-Host "  jobhunter --test tu@email.com    " -NoNewline -ForegroundColor Cyan; Write-Host "# Modo prueba" -ForegroundColor DarkGray
Write-Host "  jobhunter run                    " -NoNewline -ForegroundColor Cyan; Write-Host "# Modo produccion" -ForegroundColor DarkGray
Write-Host ""
