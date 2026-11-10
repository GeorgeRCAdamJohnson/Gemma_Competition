#!/usr/bin/env bash
# Run the official Colab CLI in WSL with ADC auth.
# From PowerShell:  wsl -d Ubuntu -- bash /mnt/c/Users/biges/Gemma/Gemma_Competition/colab_fasteval/colabw.sh <args>
# The script is stored with CRLF-safe content; it only uses quoted variables, so Windows PATH entries with
# spaces and parentheses cannot break it.
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"
exec colab --auth=adc "$@"
