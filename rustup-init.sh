#!/bin/bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
exec zsh -d -f -c 'source ~/.zshrc; source "$HOME/.cargo/env"; exec zsh'
