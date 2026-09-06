#!/bin/bash

# Burp Suite Professional Installation Script
# Version: 2025.9.4

# https://portswigger.net/burp/releases/

# sudo rm -rf /opt/burpsuite_pro_v2025.9.4/burpsuite_pro_v2025.9.4.jar &&  sudo mv /home/kali/Downloads/burpsuite_desktop_v2026.4.3.jar /opt/burpsuite_pro_v2025.9.4/burpsuite_pro_v2025.9.4.jar

set -e  # Exit on error

echo "========================================="
echo "  Burp Suite Professional Installation"
echo "========================================="

# Check if running with sudo
if [ "$EUID" -eq 0 ]; then 
    echo "Please run without sudo (script will use sudo when needed)"
    exit 1
fi

# Install JDK 21
echo "[1/7] Installing OpenJDK 21..."
sudo apt update
sudo apt install -y openjdk-21-jdk

# Set JDK 21 as default
echo "[2/7] Setting JDK 21 as default..."
echo "2" | sudo update-alternatives --config java 2>/dev/null || sudo update-alternatives --set java /usr/lib/jvm/java-21-openjdk-amd64/bin/java

# Create /opt directory if it doesn't exist
sudo mkdir -p /opt

# Download icon
echo "[3/7] Downloading Burp Suite icon..."
wget -q --show-progress https://raw.githubusercontent.com/boboaung1337/again/main/burp-suite-professional-logo.png
sudo mv burp-suite-professional-logo.png /opt/

# Create desktop entry
echo "[4/7] Creating desktop entry..."
mkdir -p ~/.local/share/applications

# if have
rm -rf ~/.local/share/applications/myburp.desktop

cat > ~/.local/share/applications/myburp.desktop << 'EOF'
[Desktop Entry]
Name=Burpsuite Pro
Exec=java --add-opens=java.desktop/javax.swing=ALL-UNNAMED --add-opens=java.base/java.lang=ALL-UNNAMED --add-opens=java.base/jdk.internal.org.objectweb.asm=ALL-UNNAMED --add-opens=java.base/jdk.internal.org.objectweb.asm.tree=ALL-UNNAMED --add-opens=java.base/jdk.internal.org.objectweb.asm.Opcodes=ALL-UNNAMED -javaagent:/opt/burpsuite_pro_v2025.9.4/burploader.jar -noverify -jar /opt/burpsuite_pro_v2025.9.4/burpsuite_pro_v2025.9.4.jar
Icon=/opt/burp-suite-professional-logo.png
Terminal=false
Type=Application
Categories=Development;Security;
EOF

# Make desktop entry executable
chmod +x ~/.local/share/applications/myburp.desktop

# Refresh the menu (for XFCE)
echo "[5/7] Refreshing application menu..."
if command -v xfce4-panel &> /dev/null; then
    xfce4-panel -r
fi

# Update desktop database if available
if command -v update-desktop-database &> /dev/null; then
    update-desktop-database ~/.local/share/applications/
fi

# Download and extract Burp Suite
echo "[6/7] Downloading and extracting Burp Suite Pro..."
wget -q --show-progress "https://drive.usercontent.google.com/download?id=17rtj2y-nQ_fTw5RnfU6nVqo4_8hmQeG6&export=download&authuser=0&confirm=t&uuid=babd0491-b5c3-47ae-86bd-8a67f4e70a16&at=ALBwUgn8HjLqZCbTOPyokSPODlDq%3A1779303166457" -O burp.7z

# Extract archive
if command -v 7z &> /dev/null; then
    7z x burp.7z
else
    echo "7z not found. Installing p7zip..."
    sudo apt install -y p7zip-full
    7z x burp.7z
fi

# Clean up
rm -rf burp.7z

# if have
sudo rm -rf /opt/burpsuite_pro_v2025.9.4

# Move to /opt
echo "[7/7] Moving files to /opt..."
sudo mv burpsuite_pro_v2025.9.4 /opt/

echo ""
echo "========================================="
echo "  Installation Complete!"
echo "========================================="
echo ""
echo "To start Burp Suite Pro:"
echo ""
echo "  You must need to use the loader to activate the software."
echo ""
echo "  1. cd /opt/burpsuite_pro_v2025.9.4 && java -jar burploader.jar"
echo ""
echo "  2. - Activation Process:"
echo "      • Copy License key from burploader.jar and paste in Burp Suite Pro"
echo "      • Click 'Next'"
echo "      • Select 'Manual Activation' option"
echo "      • Copy License Request from Burp Suite Pro and paste in burploader.jar"
echo "      • Copy license response from burploader.jar and paste in Burp Suite Pro"
echo "      • Click 'Next' and Done"
echo ""
echo "  3. Use the application menu (search for 'Burpsuite Pro')"
echo "========================================="


