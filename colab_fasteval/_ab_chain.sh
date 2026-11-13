#!/usr/bin/env bash
# One-shot A/B VM bring-up, run in WSL as ONE background process so a CLI connection is held the whole time
# (Colab reclaims VMs with no client connection after a few minutes; 4 VMs were lost that way).
# new -> upload inputs -> Drive mount (user approves the link; up to 3 links) -> guarded prep -> keep-alive that
# also launches the driver once prep succeeded (`exec --timeout 0` holds the connection until the batch is done).
# usage: bash _ab_chain.sh <session> <launch.json>
set -u
S="$1"; LAUNCH="$2"
R=/mnt/c/Users/biges/Gemma/Gemma_Competition/colab_fasteval
C="$HOME/colabw"
"$C" new -s "$S" --gpu L4 || { echo "CHAIN: new failed"; exit 1; }
"$C" upload -s "$S" "$R/_abL_inputs.tar" /content/ab_inputs.tar &&
"$C" upload -s "$S" "$LAUNCH" /content/launch.json &&
"$C" upload -s "$S" "$R/_gpu_prep_ab.py" /content/gpu_prep_ab.py &&
"$C" upload -s "$S" "$R/_launch_if_ready.py" /content/launch_if_ready.py || { echo "CHAIN: upload failed"; exit 1; }
echo "CHAIN: uploads done -- mounting Drive (approve the link)"
for i in 1 2 3; do
  bash "$HOME/drivemount.sh" "$S" 110
  if "$C" exec -s "$S" -f "$R/_probe_mount.py" 2>&1 | grep -q "drive mounted: True"; then echo "CHAIN: mounted (try $i)"; break; fi
  echo "CHAIN: not mounted after try $i"
  [ "$i" = 3 ] && { echo "CHAIN: giving up; stopping VM"; "$C" stop -s "$S"; exit 2; }
done
"$C" exec -s "$S" -f "$R/_prep_guarded.py" || true
echo "CHAIN: prep started; keep-alive + auto-launch"
# A dropped CLI connection does NOT kill the VM (2026-11-12: e4bloc3 ran >= 2 more passes after the drop) but nothing
# then holds it, so it is reclaimed later. Re-attach the keep-alive until it ends by rule or the session is gone.
# `colab sessions` wrongly reported the VM gone right after a drop twice (2026-11-12), so it is NOT consulted: keep
# re-attaching; give up only after 6 consecutive attaches that each die within 60 s (= the VM really is gone).
# --timeout 43200: on CLI 0.7.5 --timeout is a hard execution cap (not 0.8.0's "seconds without output").
: > "/tmp/keepalive_$S.log"
fast=0
for n in $(seq 1 200); do
  t0=$(date +%s)
  "$C" exec -s "$S" -f "$R/_keepalive_auto.py" --timeout 43200 2>&1 | tee -a "/tmp/keepalive_$S.log"
  if grep -q "stop:" "/tmp/keepalive_$S.log"; then
    echo "CHAIN: keep-alive finished by rule -> stopping VM (results are on Drive)"; "$C" stop -s "$S"; exit 0
  fi
  if [ $(( $(date +%s) - t0 )) -lt 60 ]; then fast=$((fast+1)); else fast=0; fi
  [ "$fast" -ge 6 ] && { echo "CHAIN: 6 attaches in a row died within 60 s -> VM gone"; exit 3; }
  echo "$(date -u +%H:%M:%S) CHAIN: keep-alive connection dropped (attach $n, fast $fast) -> re-attaching in 15 s"; sleep 15
done
echo "CHAIN: gave up after 200 attaches (VM left running)"
