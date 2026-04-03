#!/bin/bash
set -e

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[0;33m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

echo -e "${CYAN}${BOLD}"
echo "       ██╗ ██████╗ ██████╗ ██╗  ██╗██╗   ██╗███╗   ██╗████████╗███████╗██████╗ "
echo "       ██║██╔═══██╗██╔══██╗██║  ██║██║   ██║████╗  ██║╚══██╔══╝██╔════╝██╔══██╗"
echo "       ██║██║   ██║██████╔╝███████║██║   ██║██╔██╗ ██║   ██║   █████╗  ██████╔╝"
echo "  ██   ██║██║   ██║██╔══██╗██╔══██║██║   ██║██║╚██╗██║   ██║   ██╔══╝  ██╔══██╗"
echo "  ╚█████╔╝╚██████╔╝██████╔╝██║  ██║╚██████╔╝██║ ╚████║   ██║   ███████╗██║  ██║"
echo "   ╚════╝  ╚═════╝ ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝   ╚═╝   ╚══════╝╚═╝  ╚═╝"
echo -e "${NC}"
echo -e "${DIM}  Busqueda de empleo con IA  |  Instalador${NC}"
echo ""

INSTALL_DIR="${JOBHUNTER_DIR:-$HOME/.jobhunter}"
BIN_DIR="/usr/local/bin"

# Si no hay acceso a /usr/local/bin, usar ~/.local/bin
if [ ! -w "$BIN_DIR" ] && [ "$(id -u)" -ne 0 ]; then
    BIN_DIR="$HOME/.local/bin"
    mkdir -p "$BIN_DIR"
fi

echo -e "${BOLD}Instalando JobHunter AI${NC}"
echo ""

# ── Verificar requisitos ──
echo -e "  ${DIM}Verificando requisitos...${NC}"
echo ""
OK=true

# Git
if command -v git &> /dev/null; then
    GIT_VERSION=$(git --version | sed 's/git version //')
    echo -e "  ${GREEN}✓${NC} Git ${GIT_VERSION}"
else
    echo -e "  ${RED}✗ Git no encontrado${NC}"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo -e "    ${YELLOW}Instalalo con: xcode-select --install${NC}"
        echo -e "    ${YELLOW}O desde: https://git-scm.com/downloads/mac${NC}"
    else
        echo -e "    ${YELLOW}Instalalo con: sudo apt install git  (Debian/Ubuntu)${NC}"
        echo -e "    ${YELLOW}               sudo dnf install git  (Fedora)${NC}"
        echo -e "    ${YELLOW}O desde: https://git-scm.com/downloads/linux${NC}"
    fi
    OK=false
fi

# Python
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    echo -e "  ${GREEN}✓${NC} Python ${PYTHON_VERSION}"

    # pip
    if python3 -m pip --version &> /dev/null; then
        echo -e "  ${GREEN}✓${NC} pip disponible"
    else
        echo -e "  ${RED}✗ pip no encontrado${NC}"
        echo -e "    ${YELLOW}Instalalo con: python3 -m ensurepip --upgrade${NC}"
        echo -e "    ${YELLOW}O con: sudo apt install python3-pip  (Debian/Ubuntu)${NC}"
        OK=false
    fi
else
    echo -e "  ${RED}✗ Python 3 no encontrado${NC}"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo -e "    ${YELLOW}Instalalo con: brew install python3${NC}"
    else
        echo -e "    ${YELLOW}Instalalo con: sudo apt install python3  (Debian/Ubuntu)${NC}"
        echo -e "    ${YELLOW}               sudo dnf install python3  (Fedora)${NC}"
    fi
    echo -e "    ${YELLOW}O desde: https://www.python.org/downloads/${NC}"
    OK=false
fi

# Chrome o navegador compatible
BROWSER=""
for p in \
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
    "/usr/bin/google-chrome" \
    "/usr/bin/google-chrome-stable" \
    "/usr/bin/chromium-browser" \
    "/usr/bin/chromium" \
    "/usr/bin/microsoft-edge" \
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"; do
    if [ -f "$p" ]; then
        BROWSER="$p"
        break
    fi
done

# Tambien buscar en PATH
if [ -z "$BROWSER" ]; then
    BROWSER=$(which google-chrome 2>/dev/null || which google-chrome-stable 2>/dev/null || which chromium-browser 2>/dev/null || which chromium 2>/dev/null || which microsoft-edge 2>/dev/null || echo "")
fi

if [ -n "$BROWSER" ]; then
    BROWSER_NAME=$(basename "$BROWSER")
    echo -e "  ${GREEN}✓${NC} Navegador: ${BROWSER_NAME}"
else
    echo -e "  ${RED}✗ Google Chrome o Chromium no encontrado${NC}"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo -e "    ${YELLOW}Instalalo desde: https://www.google.com/chrome/${NC}"
    else
        echo -e "    ${YELLOW}Instalalo con: sudo apt install google-chrome-stable  (Debian/Ubuntu)${NC}"
        echo -e "    ${YELLOW}O desde: https://www.google.com/chrome/${NC}"
    fi
    OK=false
fi

# Si falta algo, parar
if [ "$OK" = false ]; then
    echo ""
    echo -e "  ${RED}Instala los requisitos faltantes y vuelve a ejecutar el instalador.${NC}"
    exit 1
fi

echo ""

# ── Clonar o actualizar ──
if [ -d "$INSTALL_DIR" ]; then
    echo -e "  ${CYAN}→${NC} Actualizando instalacion existente..."
    cd "$INSTALL_DIR"
    git pull --quiet
else
    echo -e "  ${CYAN}→${NC} Clonando repositorio..."
    git clone --quiet https://github.com/dev-gaspar/jobhunter.git "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

echo -e "  ${GREEN}✓${NC} Repositorio listo"

# ── Instalar dependencias ──
echo -e "  ${CYAN}→${NC} Instalando dependencias de Python..."
python3 -m pip install --quiet rich requests playwright reportlab 2>/dev/null

echo -e "  ${CYAN}→${NC} Instalando navegador para Playwright..."
python3 -m playwright install chromium --quiet 2>/dev/null || python3 -m playwright install chromium

echo -e "  ${GREEN}✓${NC} Dependencias instaladas"

# ── Crear directorios ──
mkdir -p output/cvs output/logs .session

# ── Crear comando global ──
echo -e "  ${CYAN}→${NC} Instalando comando 'jobhunter'..."

WRAPPER="${BIN_DIR}/jobhunter"
cat > "$WRAPPER" << SCRIPT
#!/bin/bash
exec python3 "${INSTALL_DIR}/job.py" "\$@"
SCRIPT
chmod +x "$WRAPPER"

echo -e "  ${GREEN}✓${NC} CLI instalado en ${WRAPPER}"

# ── Verificar PATH ──
if ! echo "$PATH" | tr ':' '\n' | grep -qx "$BIN_DIR"; then
    echo ""
    echo -e "  ${CYAN}→${NC} Agregando ${BIN_DIR} al PATH..."

    SHELL_NAME=$(basename "$SHELL")
    if [ "$SHELL_NAME" = "zsh" ]; then
        RC_FILE="$HOME/.zshrc"
    elif [ "$SHELL_NAME" = "fish" ]; then
        RC_FILE="$HOME/.config/fish/config.fish"
    else
        RC_FILE="$HOME/.bashrc"
    fi

    if [ "$SHELL_NAME" = "fish" ]; then
        echo "set -gx PATH ${BIN_DIR} \$PATH" >> "$RC_FILE"
    else
        echo "export PATH=\"${BIN_DIR}:\$PATH\"" >> "$RC_FILE"
    fi

    echo -e "  ${GREEN}✓${NC} Agregado a ${RC_FILE} (reinicia la terminal o ejecuta: source ${RC_FILE})"
fi

echo ""
echo -e "${GREEN}${BOLD}Instalacion completa!${NC}"
echo ""
echo -e "  ${BOLD}Primeros pasos:${NC}"
echo -e "  ${CYAN}jobhunter setup${NC}                    # Configurar API keys y perfil"
echo -e "  ${CYAN}jobhunter login${NC}                    # Iniciar sesion en LinkedIn"
echo -e "  ${CYAN}jobhunter --test tu@email.com${NC}      # Modo prueba"
echo -e "  ${CYAN}jobhunter run${NC}                      # Modo produccion"
echo ""
