#!/usr/bin/env bash
# Pin the official Colab CLI in WSL to a given version (default 0.7.5 = the version every successful batch ran on;
# every attempt since the 0.8.0 update lost its connection after 6-8 min).
# usage: bash wsl_pin_cli.sh [version]
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"
V="${1:-0.7.5}"
uv tool install --force "google-colab-cli==$V" 2>&1 | tail -3
uv tool list 2>/dev/null | grep -i colab
