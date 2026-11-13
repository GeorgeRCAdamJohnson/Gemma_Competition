#!/usr/bin/env bash
# Update the official Colab CLI inside WSL (installed with `uv tool install google-colab-cli`).
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"
command -v uv >/dev/null || { echo "uv not found in $HOME/.local/bin"; exit 1; }
echo "before: $(colab --auth=adc version 2>/dev/null | tail -1)"
uv tool install -U google-colab-cli 2>&1 | tail -3
echo "after:  $(colab --auth=adc version 2>/dev/null | tail -1)"
