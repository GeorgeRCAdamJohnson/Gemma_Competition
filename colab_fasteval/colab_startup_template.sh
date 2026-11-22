#!/usr/bin/env bash
# User-run Colab launcher. Run from a WSL terminal or via `wsl -d Ubuntu -- bash <this-file>`.
# Edit the run settings below, then follow the Drive consent prompt in this same terminal.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
COLAB="$HOME/colabw"

# Edit these values or override the names through the environment for a registered replication.
SESSION_NAME="${SESSION_NAME:-e4b-ctx-history-r4-20261114-1429}"
RUN_TAG="${RUN_TAG:-e4b_context_history_20261114_r4_1429}"
INPUT_BUNDLE="${INPUT_BUNDLE:-$SCRIPT_DIR/_context_history_inputs.tar}"
GPU="${GPU:-L4}"
ARMS_DIR="${ARMS_DIR:-arms}"
ROUNDS="${ROUNDS:-5}"
ROUND_FROM="${ROUND_FROM:-1}"
DEADLINE_H="${DEADLINE_H:-8}"
GPU_UTILIZATION="${GPU_UTILIZATION:-0.85}"
# model served by vLLM; it must match every arm's agent.yaml. MODEL_ARCHIVE (path under MyDrive) is used only when
# the model is not in gemma-4-developer-agent-cache/models; AB_CONC = concurrent tasks per pass.
MODEL_NAME="${MODEL_NAME:-gemma-4-e4b-it-qat-w4a16-ct}"
MODEL_ARCHIVE="${MODEL_ARCHIVE:-}"
AB_CONC="${AB_CONC:-8}"

if ! grep -qiE 'microsoft|wsl' /proc/sys/kernel/osrelease; then
    echo "Run this launcher inside WSL, not Windows Python or a Colab notebook." >&2
    echo "From PowerShell: wsl -d Ubuntu -- bash /mnt/c/Users/biges/Gemma/Gemma_Competition/colab_fasteval/colab_startup_template.sh" >&2
    exit 2
fi

if [[ ! -x "$COLAB" ]]; then
    echo "Colab CLI wrapper not found at $COLAB; set it up in WSL first." >&2
    exit 2
fi
if [[ "$SESSION_NAME" == CHANGE_ME_* || "$RUN_TAG" == CHANGE_ME_* ]]; then
    echo "Edit SESSION_NAME and RUN_TAG before starting a runtime." >&2
    exit 2
fi
if [[ ! "$SESSION_NAME" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$ ||
      ! "$RUN_TAG" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$ ]]; then
    echo "SESSION_NAME and RUN_TAG must be path-safe names." >&2
    exit 2
fi
if [[ ! -f "$INPUT_BUNDLE" ]]; then
    echo "Input bundle not found: $INPUT_BUNDLE" >&2
    exit 2
fi
if (( ROUND_FROM < 1 || ROUNDS < ROUND_FROM )) || ! awk "BEGIN { exit !($DEADLINE_H > 0 && $GPU_UTILIZATION > 0 && $GPU_UTILIZATION <= 1) }"; then
    echo "Invalid round range, deadline, or GPU utilization." >&2
    exit 2
fi
for helper in _ab_chain.sh _gpu_prep_ab.py _prep_guarded.py _launch_if_ready.py _keepalive_auto.py _probe_mount.py _preflight_output_tag.py _verify_model_dir.py; do
    if [[ ! -f "$SCRIPT_DIR/$helper" ]]; then
        echo "Required helper is missing: $SCRIPT_DIR/$helper" >&2
        exit 2
    fi
done

LAUNCH_JSON="$(mktemp "${TMPDIR:-/tmp}/colab-launch.XXXXXX")"
trap 'rm -f "$LAUNCH_JSON"' EXIT
python3 - "$LAUNCH_JSON" "$ARMS_DIR" "$RUN_TAG" "$ROUNDS" "$ROUND_FROM" "$DEADLINE_H" "$GPU_UTILIZATION" \
    "$MODEL_NAME" "$MODEL_ARCHIVE" "$AB_CONC" <<'PY'
import json
import sys

path, arms, tag, rounds, round_from, deadline, gpu_utilization, model, archive, conc = sys.argv[1:]
config = {
    "arms": arms,
    "out": "/content/ab",
    "tag": tag,
    "rounds": int(rounds),
    "round_from": int(round_from),
    "deadline_h": float(deadline),
    "gpu_utilization": float(gpu_utilization),
    "model_name": model,
    "model_archive": archive,
    "conc": int(conc),
}
with open(path, "w", encoding="utf-8") as stream:
    json.dump(config, stream, indent=2)
    stream.write("\n")
PY

echo "Colab WSL run configuration:"
echo "  session: $SESSION_NAME"
echo "  GPU: $GPU"
echo "  Drive tag: $RUN_TAG"
echo "  rounds: $ROUND_FROM..$ROUNDS; deadline: ${DEADLINE_H}h; GPU utilization: $GPU_UTILIZATION"
echo "  input bundle: $INPUT_BUNDLE"
echo "  model: $MODEL_NAME${MODEL_ARCHIVE:+ (archive fallback: $MODEL_ARCHIVE)}"
echo "  concurrency: $AB_CONC tasks per pass"
echo "Check the CU balance now; the deadline is enforced, but CU balance is not polled automatically."
"$COLAB" usage
read -r -p "Type the session name to create the runtime and start: " CONFIRM
if [[ "$CONFIRM" != "$SESSION_NAME" ]]; then
    echo "Cancelled; no runtime was created."
    exit 1
fi

echo
echo "Starting the run in the foreground. When Drive consent appears, grant access in the browser,"
echo "return to this WSL terminal, and press Enter when the Colab CLI prompts."
bash "$SCRIPT_DIR/_ab_chain.sh" "$SESSION_NAME" "$LAUNCH_JSON" "$INPUT_BUNDLE" "$GPU"
echo
echo "Run chain finished. Drive output: My Drive/gemma_fasteval/ab_runs/$RUN_TAG"
echo "On this computer: G:\\My Drive\\gemma_fasteval\\ab_runs\\$RUN_TAG"
