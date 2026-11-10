#!/usr/bin/env bash
# Mount Drive on a CLI session non-interactively: the CLI's "Press Enter after you have granted access" prompt is
# fed by a waiter that blocks until /tmp/colab_drive_go exists (touched by the agent once the user has consented).
# usage: bash wsl_drivemount.sh <session>
S="${1:-drvprobe}"
rm -f /tmp/colab_drive_go
( while [ ! -f /tmp/colab_drive_go ]; do sleep 2; done; echo ) | "$HOME/colabw" drivemount -s "$S"
