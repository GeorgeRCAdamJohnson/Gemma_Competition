#!/usr/bin/env bash
# One-time setup of the official Colab CLI inside WSL Ubuntu (the CLI is Linux/macOS only).
# Auth: reuses the Windows ADC file (already granted the colaboratory scope) via --auth=adc.
set -u
export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv >/dev/null; then
  curl -LsSf https://astral.sh/uv/install.sh | sh >/tmp/uv_install.log 2>&1
fi
echo "uv: $(uv --version 2>&1)"
if ! command -v colab >/dev/null; then
  uv tool install google-colab-cli >/tmp/colab_install.log 2>&1 || tail -5 /tmp/colab_install.log
fi
echo "colab: $(colab version 2>&1 | tail -1)"
# copy ADC credentials from Windows (same user, same machine); never printed
WIN_ADC="/mnt/c/Users/biges/AppData/Roaming/gcloud/application_default_credentials.json"
mkdir -p "$HOME/.config/gcloud"
if [ -f "$WIN_ADC" ]; then
  install -m 600 "$WIN_ADC" "$HOME/.config/gcloud/application_default_credentials.json"
  echo "ADC copied ($(stat -c %s "$HOME/.config/gcloud/application_default_credentials.json") bytes, mode 600)"
else
  echo "Windows ADC file not found at $WIN_ADC"
fi
