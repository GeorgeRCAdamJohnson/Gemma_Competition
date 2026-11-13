#!/usr/bin/env bash
# Keep-alive re-attach loop only (the tail of _ab_chain.sh), for a VM that is already mounted + prepping.
# usage: bash _ab_attach.sh <session>
set -u
S="$1"
R=/mnt/c/Users/biges/Gemma/Gemma_Competition/colab_fasteval
C="$HOME/colabw"
: > "/tmp/keepalive_$S.log"
fast=0
for n in $(seq 1 200); do
  t0=$(date +%s)
  "$C" exec -s "$S" -f "$R/_keepalive_auto.py" --timeout 43200 2>&1 | tee -a "/tmp/keepalive_$S.log"
  if grep -q "stop:" "/tmp/keepalive_$S.log"; then
    echo "ATTACH: keep-alive finished by rule -> stopping VM (results are on Drive)"; "$C" stop -s "$S"; exit 0
  fi
  if [ $(( $(date +%s) - t0 )) -lt 60 ]; then fast=$((fast+1)); else fast=0; fi
  [ "$fast" -ge 6 ] && { echo "ATTACH: 6 attaches in a row died within 60 s -> VM gone"; exit 3; }
  echo "$(date -u +%H:%M:%S) ATTACH: connection dropped (attach $n, fast $fast) -> re-attaching in 15 s"; sleep 15
done
