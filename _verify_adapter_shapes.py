"""Verify which BASE MODEL each adapter actually fits, from tensor shapes.
A LoRA lora_A has shape [rank, in_features]; in_features = hidden_size of the base.
So the adapter's hidden size identifies the base: must match the model we serve.
Resolves the log conflict 'adapters are 31B' vs 'no adapter fits the scored 31B model'."""
import json
import struct
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent
CANDS = [
    "adapter_dataset",
    "adapter_v2_dataset",
    "adapter_v2_s05",
    "adapter_dataset-r32-s0.25",
    "Outputs/v19_lora/submission/adapters/main_lora",
    "v2_gate_out/submission/adapters/main_lora",
    "submit_v6z_on_v6w/lora025/out/submission/adapters/main_lora",
]


def header(p):
    with open(p, "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        return json.loads(f.read(n))


def main():
    for name in CANDS:
        p = ROOT / name / "adapter_model.safetensors"
        if not p.exists():
            continue
        h = header(p)
        cfg_p = ROOT / name / "adapter_config.json"
        claimed = "?"
        r_cfg = a_cfg = "?"
        if cfg_p.exists():
            c = json.loads(cfg_p.read_text(encoding="utf-8"))
            claimed = c.get("base_model_name_or_path", "?")
            r_cfg = c.get("r")
            a_cfg = c.get("lora_alpha")
        wkeys = [k for k in h if k.endswith("weight")]
        hidden = rank = None
        layers = set()
        for k in wkeys:
            s = h[k]["shape"]
            if k.endswith("lora_A.weight") and len(s) == 2:
                rank, hidden = s[0], s[1]
                break
        for k in wkeys:
            for seg in k.split("."):
                if seg.isdigit():
                    layers.add(int(seg))
        lm_head = any("lm_head" in k for k in wkeys)
        print(f"--- {name}")
        print(f"    claimed base : {claimed}   (config r={r_cfg} alpha={a_cfg})")
        print(f"    shape-derived: rank={rank} hidden={hidden} layers={len(layers)} lm_head={'yes' if lm_head else 'no'}")
        print(f"    tensors={len(wkeys)}  size={p.stat().st_size/1e6:.0f} MB")


if __name__ == "__main__":
    main()
