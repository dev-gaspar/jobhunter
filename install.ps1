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

# Verificar Python
$py = $null
if (Get-Command python -ErrorAction SilentlyContinue) { $py = "python" }
elseif (Get-Command python3 -ErrorAction SilentlyContinue) { $py = "python3" }

if (-not $py) {
    Write-Host "  x Error: Se requiere Python 3 pero no esta instalado." -ForegroundColor Red
    Write-Host "    Instalalo desde https://www.python.org/downloads/" -ForegroundColor Yellow
    return
}

$pythonVersion = & $py --version 2>&1
Write-Host "  ✓ $pythonVersion encontrado" -ForegroundColor Green

# Clonar o actualizar
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

# Instalar dependencias
Write-Host "  → Instalando dependencias..." -ForegroundColor Cyan
& $py -m pip install --quiet rich requests playwright reportlab 2>&1 | Out-Null
& $py -m playwright install chromium 2>&1 | Out-Null

Write-Host "  ✓ Dependencias instaladas" -ForegroundColor Green

# Crear directorios
New-Item -ItemType Directory -Force -Path "$InstallDir\output\cvs" | Out-Null
New-Item -ItemType Directory -Force -Path "$InstallDir\output\logs" | Out-Null
New-Item -ItemType Directory -Force -Path "$InstallDir\.session" | Out-Null

Write-Host "  ✓ Directorios creados" -ForegroundColor Green

# Crear script wrapper .cmd en un directorio del PATH
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

# Tambien agregar al PATH de la sesion actual
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
