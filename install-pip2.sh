#!/bin/bash
# pip2-installer - Install pip for Python 2
# GitHub: https://github.com/YOUR_USERNAME/pip2-installer

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== pip2 Installer ===${NC}"

# Check if Python 2 is installed
if ! command -v python2 &> /dev/null; then
    echo -e "${YELLOW}Python 2 not found. Installing...${NC}"
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        sudo apt update
        sudo apt install -y python2
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        brew install python@2 || echo "Python 2 not available via Homebrew. Install manually."
    else
        echo -e "${RED}Unsupported OS. Please install Python 2 manually.${NC}"
        exit 1
    fi
fi

# Download get-pip.py for Python 2
echo -e "${GREEN}Downloading get-pip.py for Python 2...${NC}"
curl -sSL https://bootstrap.pypa.io/pip/2.7/get-pip.py -o get-pip.py

# Install pip2
echo -e "${GREEN}Installing pip2...${NC}"
sudo python2 get-pip.py

# Verify installation
echo -e "${GREEN}Verifying installation...${NC}"
if command -v pip2 &> /dev/null; then
    echo -e "${GREEN}✓ pip2 installed successfully:${NC}"
    pip2 --version
elif python2 -m pip --version &> /dev/null; then
    echo -e "${GREEN}✓ pip2 installed successfully:${NC}"
    python2 -m pip --version
else
    echo -e "${RED}✗ Installation failed${NC}"
    exit 1
fi

# Clean up
rm -f get-pip.py

echo -e "${GREEN}=== Installation Complete ===${NC}"
echo -e "Use pip2 with: ${YELLOW}pip2 install <package>${NC}"
echo -e "Or: ${YELLOW}python2 -m pip install <package>${NC}"
