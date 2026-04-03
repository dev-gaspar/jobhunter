#!/bin/bash
set -e

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
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

# Verificar Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Se requiere Python 3 pero no esta instalado.${NC}"
    echo -e "Instalalo desde https://www.python.org/downloads/"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo -e "  ${GREEN}✓${NC} Python ${PYTHON_VERSION} encontrado"

# Clonar o actualizar
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

# Instalar dependencias de Python
echo -e "  ${CYAN}→${NC} Instalando dependencias..."
python3 -m pip install --quiet rich requests playwright reportlab 2>/dev/null
python3 -m playwright install chromium --quiet 2>/dev/null || python3 -m playwright install chromium

echo -e "  ${GREEN}✓${NC} Dependencias instaladas"

# Crear directorios
mkdir -p output/cvs output/logs .session

echo -e "  ${GREEN}✓${NC} Directorios creados"

# Crear comando global
echo -e "  ${CYAN}→${NC} Instalando comando 'jobhunter'..."

WRAPPER="${BIN_DIR}/jobhunter"
cat > "$WRAPPER" << SCRIPT
#!/bin/bash
exec python3 "${INSTALL_DIR}/job.py" "\$@"
SCRIPT
chmod +x "$WRAPPER"

echo -e "  ${GREEN}✓${NC} CLI instalado en ${WRAPPER}"

# Verificar si BIN_DIR esta en el PATH
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
