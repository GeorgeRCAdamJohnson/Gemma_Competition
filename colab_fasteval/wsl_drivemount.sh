#!/usr/bin/env bash
# Mount Drive on a CLI session non-interactively. drive.mount() times out 120 s after the consent link appears,
# so the CLI's "Press Enter after you have granted access" prompt is released automatically after AUTO seconds
# (or earlier if /tmp/colab_drive_go is touched). The user only has to approve the link in time.
# usage: bash wsl_drivemount.sh <session> [auto_release_seconds]
S="${1:-drvprobe}"
AUTO="${2:-75}"
rm -f /tmp/colab_drive_go
( t=0; while [ ! -f /tmp/colab_drive_go ] && [ $t -lt "$AUTO" ]; do sleep 1; t=$((t+1)); done; echo ) \
  | "$HOME/colabw" drivemount -s "$S"
