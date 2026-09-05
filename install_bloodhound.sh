#!/bin/bash


sudo apt update && sudo apt install -y bloodhound

sudo bloodhound-setup

sudo sed -i 's/"secret": "neo4j"/"secret": "admin"/' /etc/bhapi/bhapi.json


# Download and extract BloodHound
wget https://github.com/SpecterOps/BloodHound-Legacy/releases/latest/download/BloodHound-linux-x64.zip && \
unzip BloodHound-linux-x64.zip && \
rm BloodHound-linux-x64.zip && \
sudo mv BloodHound-linux-x64 /opt/BloodHound-linux-x64

# Create desktop entry
cat > ~/.local/share/applications/myapp.desktop << EOF
[Desktop Entry]
Name=BloodHound
Exec=/opt/BloodHound-linux-x64/BloodHound --no-sandbox
Icon=/opt/BloodHound-linux-x64/resources/app/src/img/logo-white-transparent-full.png
Terminal=false
Type=Application
EOF

# Make desktop entry executable
chmod +x ~/.local/share/applications/myapp.desktop

#  refresh the menu 
xfce4-panel -r

sudo systemctl enable bloodhound.service

sudo systemctl enable postgresql

# Fix collation errors if they occur
sudo -u postgres psql -c "ALTER DATABASE postgres REFRESH COLLATION VERSION;"
sudo -u postgres psql -c "ALTER DATABASE template1 REFRESH COLLATION VERSION;"
