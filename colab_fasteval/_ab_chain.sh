#!/usr/bin/env bash
# Run in WSL as a foreground process so the user can approve Drive consent in this terminal.
# usage: bash _ab_chain.sh <session> <launch.json> <input-bundle.tar> [gpu]
set -uo pipefail
S="${1:?session name required}"
LAUNCH="${2:?launch.json required}"
INPUT="${3:?input bundle required}"
GPU="${4:-L4}"
R="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
C="$HOME/colabw"

if [[ ! -x "$C" || ! -f "$LAUNCH" || ! -f "$INPUT" ]]; then
  echo "CHAIN: Colab CLI, launch config, or input bundle is missing" >&2
  exit 1
fi
"$C" new -s "$S" --gpu "$GPU" || { echo "CHAIN: runtime creation failed"; exit 1; }
"$C" upload -s "$S" "$INPUT" /content/ab_inputs.tar &&
"$C" upload -s "$S" "$LAUNCH" /content/launch.json &&
"$C" upload -s "$S" "$R/_gpu_prep_ab.py" /content/gpu_prep_ab.py &&
"$C" upload -s "$S" "$R/_launch_if_ready.py" /content/launch_if_ready.py &&
"$C" upload -s "$S" "$R/_keepalive_auto.py" /content/_keepalive_auto.py &&
"$C" upload -s "$S" "$R/_prep_guarded.py" /content/_prep_guarded.py &&
"$C" upload -s "$S" "$R/_probe_mount.py" /content/_probe_mount.py &&
"$C" upload -s "$S" "$R/_preflight_output_tag.py" /content/_preflight_output_tag.py &&
"$C" upload -s "$S" "$R/_verify_model_dir.py" /content/_verify_model_dir.py || {
  echo "CHAIN: upload failed; runtime $S remains active. Stop it with: $C stop -s $S" >&2
  exit 1
}

echo "CHAIN: uploads done; starting interactive Drive mount."
echo "Approve the browser consent, then press Enter in this terminal when prompted."
"$C" drivemount -s "$S" || {
  echo "CHAIN: Drive mount failed; runtime $S remains active. Stop it with: $C stop -s $S" >&2
  exit 2
}
if ! PROBE=$("$C" exec -s "$S" -f "$R/_probe_mount.py" 2>&1); then
  printf '%s\n' "$PROBE"
  echo "CHAIN: Drive mount probe failed; runtime $S remains active." >&2
  exit 2
fi
printf '%s\n' "$PROBE"
if ! grep -q "drive mounted: True" <<< "$PROBE"; then
  echo "CHAIN: Drive is not mounted; runtime $S remains active." >&2
  exit 2
fi

if ! "$C" exec -s "$S" -f "$R/_preflight_output_tag.py"; then
  echo "CHAIN: output tag is unavailable; stopping runtime $S before prep." >&2
  "$C" stop -s "$S" || { echo "CHAIN: failed to stop runtime $S" >&2; exit 4; }
  exit 2
fi

"$C" exec -s "$S" -f "$R/_prep_guarded.py" || {
  echo "CHAIN: guarded prep failed; runtime $S remains active." >&2
  exit 2
}
echo "CHAIN: prep started; attaching keep-alive + auto-launch."
# Reattach after dropped CLI streams; the remote monitor resumes rather than launching a second driver.
: > "/tmp/keepalive_$S.log"
fast=0
for n in $(seq 1 200); do
  t0=$(date +%s)
  if "$C" exec -s "$S" -f "$R/_keepalive_auto.py" --timeout 43200 2>&1 | tee -a "/tmp/keepalive_$S.log"; then
    attach_status=0
  else
    attach_status=${PIPESTATUS[0]}
  fi
  if grep -q "stop:" "/tmp/keepalive_$S.log"; then
    echo "CHAIN: keep-alive finished by rule; stopping runtime (results persist on Drive)."
    "$C" stop -s "$S" || { echo "CHAIN: failed to stop runtime $S" >&2; exit 4; }
    exit 0
  fi
  if [ $(( $(date +%s) - t0 )) -lt 60 ]; then fast=$((fast+1)); else fast=0; fi
  if [ "$fast" -ge 6 ]; then
    echo "CHAIN: six attach attempts ended within 60 seconds; runtime is not reachable." >&2
    exit 3
  fi
  echo "$(date -u +%H:%M:%S) CHAIN: CLI stream ended (status $attach_status); reattaching in 15 seconds."
  sleep 15
done
echo "CHAIN: gave up after 200 attaches; runtime $S may still be active." >&2
exit 3
