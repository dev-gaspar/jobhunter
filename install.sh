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

INSTALL_DIR="${JOBHUNTER_DIR:-$HOME/jobhunter}"

echo -e "${BOLD}Installing JobHunter AI to ${INSTALL_DIR}${NC}"
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

echo ""
echo -e "${GREEN}${BOLD}Installation complete!${NC}"
echo ""
echo -e "  ${BOLD}Get started:${NC}"
echo -e "  ${CYAN}cd ${INSTALL_DIR}${NC}"
echo -e "  ${CYAN}python3 job.py setup${NC}    # Configure API keys and profile"
echo -e "  ${CYAN}python3 job.py login${NC}    # Login to LinkedIn"
echo -e "  ${CYAN}python3 job.py --test your@email.com${NC}  # Test run"
echo ""
