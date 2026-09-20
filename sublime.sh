#!/usr/bin/env bash
set -euo pipefail

curl -X GET "https://download.sublimetext.com/sublime-text_build-4200_amd64.deb" -o s.deb
sudo dpkg -i s.deb
rm s.deb
