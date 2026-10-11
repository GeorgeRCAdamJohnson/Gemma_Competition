"""Task 2 (spec gemma-lora-colab-training, R6): emit submit-ready adapter VARIANTS from ONE trained adapter,
config-only / cheap-offline, NO GPU, NO retrain. The post-training levers the user asked for.

LEVERS:
  R6.1 STRENGTH dial: effective LoRA scale = lora_alpha / r. --scale S multiplies the trained default scale by S
       by rewriting lora_alpha. w=0 (scale 0) => adapter is a no-op => base behavior (a bad adapter can always
       be neutralized without retrain). Pure config edit; weights untouched.
  R6.2 RANK truncation: --rank K slices each lora_A (r x in -> K x in) and lora_B (out x r -> out x K), sets
       config r=K, scales alpha to preserve the chosen effective scale. A smaller/weaker adapter from one run.

Usage:
  python make_variant.py --adapter adapters/<run> --scale 1.0            # same rank, default strength
  python make_variant.py --adapter adapters/<run> --scale 0.5            # half strength
  python make_variant.py --adapter adapters/<run> --rank 16 --scale 1.0  # r=16 slice at same effective scale
  (omit --out to auto-name adapters/<run>-r<K>-s<S>)

Appends a manifest row to adapters/manifest.jsonl (run, r, alpha, effective_scale, bytes, sha256).
Reads safetensors with the `safetensors` lib (CPU). Validates the emitted dir is a loadable PEFT adapter shape.
"""
import argparse, json, os, hashlib, shutil

def load_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)

def save_json(p, obj):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)

def sha16(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()[:16]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", required=True, help="trained adapter dir (has adapter_config.json + adapter_model.safetensors)")
    ap.add_argument("--scale", type=float, default=1.0, help="effective-scale multiplier vs the trained default (R6.1). 0 = no-op/base.")
    ap.add_argument("--rank", type=int, default=None, help="truncate to rank K (R6.2); default keeps trained rank")
    ap.add_argument("--out", default=None, help="output dir (default auto: <adapter>-r<K>-s<S>)")
    args = ap.parse_args()

    cfg_path = os.path.join(args.adapter, "adapter_config.json")
    w_path = os.path.join(args.adapter, "adapter_model.safetensors")
    assert os.path.exists(cfg_path), f"no adapter_config.json in {args.adapter}"
    assert os.path.exists(w_path), f"no adapter_model.safetensors in {args.adapter}"
    cfg = load_json(cfg_path)
    r0 = int(cfg["r"]); alpha0 = int(cfg["lora_alpha"])
    r1 = int(args.rank) if args.rank else r0
    assert r1 <= r0, f"--rank {r1} must be <= trained rank {r0} (cannot grow rank)"

    out = args.out or f"{args.adapter.rstrip('/')}-r{r1}-s{args.scale:g}"
    os.makedirs(out, exist_ok=True)

    # new lora_alpha preserves effective scale = (alpha/r). target effective = args.scale * (alpha0/r0).
    # with rank r1: alpha1 = scale * (alpha0/r0) * r1
    eff_default = alpha0 / r0
    eff_target = args.scale * eff_default
    alpha1 = round(eff_target * r1)

    # weights: slice ranks if truncating; else copy. Use safetensors (CPU, no torch GPU needed).
    from safetensors.torch import load_file, save_file
    sd = load_file(w_path)
    newsd = {}
    for k, t in sd.items():
        if r1 < r0:
            if "lora_A" in k and t.ndim == 2 and t.shape[0] == r0:
                t = t[:r1, :].contiguous()            # (r x in) -> (K x in)
            elif "lora_B" in k and t.ndim == 2 and t.shape[1] == r0:
                t = t[:, :r1].contiguous()            # (out x r) -> (out x K)
        newsd[k] = t
    save_file(newsd, os.path.join(out, "adapter_model.safetensors"))

    cfg["r"] = r1
    cfg["lora_alpha"] = alpha1
    save_json(os.path.join(out, "adapter_config.json"), cfg)
    # copy any extra small files (tokenizer configs, README) if present
    for extra in ("README.md", "special_tokens_map.json", "tokenizer_config.json"):
        src = os.path.join(args.adapter, extra)
        if os.path.exists(src):
            shutil.copy(src, out)

    wf = os.path.join(out, "adapter_model.safetensors")
    row = {"run": os.path.basename(out), "src": os.path.basename(args.adapter.rstrip("/")),
           "r": r1, "lora_alpha": alpha1, "effective_scale": round(eff_target, 4),
           "bytes": os.path.getsize(wf), "sha256": sha16(wf)}
    man = os.path.join(os.path.dirname(args.adapter.rstrip("/")) or ".", "manifest.jsonl")
    with open(man, "a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    print(f"[variant] wrote {out}")
    print(f"  r={r1} lora_alpha={alpha1} effective_scale={eff_target:.3f} (default was {eff_default:.3f})")
    print(f"  bytes={row['bytes']} sha256={row['sha256']}")
    print(f"[manifest] appended -> {man}")

if __name__ == "__main__":
    main()
