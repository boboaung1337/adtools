#!/bin/bash

# Author: MrDark0x7
# Enhanced KeePass Password Cracking Tool

# Clear screen and show header
# ASCII Art Header
clear
echo -e "\033[1;36m"
echo "   ██╗  ██╗███████╗███████╗██████╗  █████╗ ███████╗███████╗  ██╗"
echo "   ██║ ██╔╝██╔════╝██╔════╝██╔══██╗██╔══██╗██╔════╝██╔════╝  ╚═╝"
echo "   █████╔╝ █████╗  █████╗  ██████╔╝███████║███████╗███████╗  ██╗"
echo "   ██╔═██╗ ██╔══╝  ██╔══╝  ██╔═══╝ ██╔══██║╚════██║╚════██║  ╚═╝"
echo "   ██║  ██╗███████╗███████╗██║     ██║  ██║███████║███████║  ██╗"
echo "   ╚═╝  ╚═╝╚══════╝╚══════╝╚═╝     ╚═╝  ╚═╝╚══════╝╚══════╝  ╚═╝ v1.0"
echo "                          Author: MrDark0x7"
echo -e "\033[0m"

# Check for keepassxc-cli installation
if ! command -v keepassxc-cli &> /dev/null; then
    echo -e "\033[1;31mError: 'keepassxc-cli' is not installed or not in PATH.\033[0m"
    exit 1
fi

# Interactive parameter collection
read -e -p $'\033[1;33m[?] Path to KeePass database: \033[0m' DB
until [[ -f "$DB" ]]; do
    echo -e "\033[1;31m[-] Database file not found\033[0m"
    read -e -p $'\033[1;33m[?] Path to KeePass database: \033[0m' DB
done

read -e -p $'\033[1;33m[?] Path to wordlist: \033[0m' WL
until [[ -f "$WL" ]]; do
    echo -e "\033[1;31m[-] Wordlist file not found\033[0m"
    read -e -p $'\033[1;33m[?] Path to wordlist: \033[0m' WL
done

read -p $'\033[1;33m[?] Use keyfile? (y/n) [n]: \033[0m' -n 1 USE_KEYFILE
echo
KEYFILE=""
if [[ $USE_KEYFILE =~ [Yy] ]]; then
    read -e -p $'\033[1;33m[?] Path to keyfile: \033[0m' KEYFILE
    until [[ -f "$KEYFILE" ]]; do
        echo -e "\033[1;31m[-] Keyfile not found\033[0m"
        read -e -p $'\033[1;33m[?] Path to keyfile: \033[0m' KEYFILE
    done
fi

read -p $'\033[1;33m[?] Delay between attempts (seconds) [0]: \033[0m' DELAY
DELAY=${DELAY:-0}

read -p $'\033[1;33m[?] Maximum attempts [all]: \033[0m' MAX_ATTEMPTS
TOTAL=$(wc -l < "$WL")
MAX_ATTEMPTS=${MAX_ATTEMPTS:-$TOTAL}

read -p $'\033[1;33m[?] Enable color output? (y/n) [y]: \033[0m' -n 1 COLOR
echo
COLOR=${COLOR:-y}

# Prepare CLI parameters
CLI_OPTIONS=("--quiet")
if [[ -n "$KEYFILE" ]]; then
    CLI_OPTIONS+=("--key-file" "$KEYFILE")
fi

# Color configuration
if [[ $COLOR =~ [Yy] ]]; then
    COLOR_OK="\033[1;32m"
    COLOR_FAIL="\033[1;31m"
    COLOR_INFO="\033[1;33m"
    COLOR_RESET="\033[0m"
else
    COLOR_OK=""
    COLOR_FAIL=""
    COLOR_INFO=""
    COLOR_RESET=""
fi

# Initialize counters
COUNT=0
FOUND=0
START_TIME=$SECONDS

# Progress bar function
print_progress() {
    local PROGRESS=$((COUNT * 50 / MAX_ATTEMPTS))
    local REMAINING=$((50 - PROGRESS))
    printf "\r${COLOR_INFO}[%-*s%*s] %d/%d (Elapsed: %ds)${COLOR_RESET}" \
        $PROGRESS "" $REMAINING "" $COUNT $MAX_ATTEMPTS $((SECONDS - START_TIME))
}

# Capture CTRL+C
trap 'echo -e "\n${COLOR_FAIL}[-] Operation cancelled by user${COLOR_RESET}"; exit 1' SIGINT

# Main cracking loop
echo -e "\n${COLOR_INFO}[*] Starting attack...${COLOR_RESET}"
while IFS= read -r PASS && [[ $COUNT -lt $MAX_ATTEMPTS ]]; do
    ((COUNT++))
    print_progress
    
    if printf '%s\n' "$PASS" | keepassxc-cli ls "$DB" "${CLI_OPTIONS[@]}" >/dev/null 2>&1; then
        FOUND=1
        break
    fi
    
    sleep "$DELAY"
done < <(head -n "$MAX_ATTEMPTS" "$WL")

# Display results
if [[ $FOUND -eq 1 ]]; then
    echo -e "\n\n${COLOR_OK}[+] Password found:${COLOR_RESET} '$PASS'"
    echo -e "${COLOR_OK}[+] Time elapsed: $((SECONDS - START_TIME)) seconds${COLOR_RESET}"
    exit 0
else
    echo -e "\n\n${COLOR_FAIL}[-] Password not found after $COUNT attempts${COLOR_RESET}"
    echo -e "${COLOR_FAIL}[-] Tested $COUNT/$MAX_ATTEMPTS entries${COLOR_RESET}"
    echo -e "${COLOR_FAIL}[-] Time elapsed: $((SECONDS - START_TIME)) seconds${COLOR_RESET}"
    exit 1
fi
