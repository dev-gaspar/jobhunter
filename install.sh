#!/bin/bash
set -e

# Colors
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
echo -e "${DIM}  AI-Powered Job Search & Auto Apply  |  Installer${NC}"
echo ""

INSTALL_DIR="${JOBHUNTER_DIR:-$HOME/.jobhunter}"
BIN_DIR="/usr/local/bin"

# Fallback to ~/.local/bin if no sudo access
if [ ! -w "$BIN_DIR" ] && [ "$(id -u)" -ne 0 ]; then
    BIN_DIR="$HOME/.local/bin"
    mkdir -p "$BIN_DIR"
fi

echo -e "${BOLD}Installing JobHunter AI${NC}"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is required but not installed.${NC}"
    echo -e "Install it from https://www.python.org/downloads/"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo -e "  ${GREEN}✓${NC} Python ${PYTHON_VERSION} found"

# Clone or update
if [ -d "$INSTALL_DIR" ]; then
    echo -e "  ${CYAN}→${NC} Updating existing installation..."
    cd "$INSTALL_DIR"
    git pull --quiet
else
    echo -e "  ${CYAN}→${NC} Cloning repository..."
    git clone --quiet https://github.com/dev-gaspar/jobhunter.git "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

echo -e "  ${GREEN}✓${NC} Repository ready"

# Install Python dependencies
echo -e "  ${CYAN}→${NC} Installing dependencies..."
python3 -m pip install --quiet rich requests playwright reportlab 2>/dev/null
python3 -m playwright install chromium --quiet 2>/dev/null || python3 -m playwright install chromium

echo -e "  ${GREEN}✓${NC} Dependencies installed"

# Create directories
mkdir -p output/cvs output/logs .session

echo -e "  ${GREEN}✓${NC} Directories created"

# Create global CLI wrapper
echo -e "  ${CYAN}→${NC} Installing 'jobhunter' command..."

WRAPPER="${BIN_DIR}/jobhunter"
cat > "$WRAPPER" << SCRIPT
#!/bin/bash
exec python3 "${INSTALL_DIR}/job.py" "\$@"
SCRIPT
chmod +x "$WRAPPER"

echo -e "  ${GREEN}✓${NC} CLI installed at ${WRAPPER}"

# Check if BIN_DIR is in PATH
if ! echo "$PATH" | tr ':' '\n' | grep -qx "$BIN_DIR"; then
    echo ""
    echo -e "  ${CYAN}→${NC} Adding ${BIN_DIR} to PATH..."

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

    echo -e "  ${GREEN}✓${NC} Added to ${RC_FILE} (restart terminal or run: source ${RC_FILE})"
fi

echo ""
echo -e "${GREEN}${BOLD}Installation complete!${NC}"
echo ""
echo -e "  ${BOLD}Get started:${NC}"
echo -e "  ${CYAN}jobhunter setup${NC}                    # Configure API keys and profile"
echo -e "  ${CYAN}jobhunter login${NC}                    # Login to LinkedIn"
echo -e "  ${CYAN}jobhunter --test your@email.com${NC}    # Test run"
echo -e "  ${CYAN}jobhunter run${NC}                      # Production mode"
echo ""
