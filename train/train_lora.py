"""Resumable QLoRA trainer for Gemma-4 E2B (RULE A: checkpoint+resume; never retrain from scratch).
- Saves adapter + optimizer state after EVERY epoch to <out>/ckpt/, with a progress.json tracking which
  (stage, epoch) pairs are done. A re-run with the same --out RESUMES from the last completed epoch.
- A killed run (timeout/OOM/manual) loses at most the in-progress epoch.
- Stages run in order; each stage's target epoch count can be raised across runs without redoing prior
  epochs (it only runs the epochs not yet in progress.json).

Usage (idempotent/resumable):
  python train_lora.py --out adapters/fastapi_specialist_traj \
     --stage s1=data/stage1_fastapi_idioms.jsonl:1:160 \
     --stage s2=data/stage2_fastapi_transitions.jsonl:4
  # re-run with s2:6 later -> only trains the 2 extra s2 epochs, resuming from the saved adapter.
"""
import warnings, time, os, json, argparse, random
warnings.filterwarnings("ignore")
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training, PeftModel
import bitsandbytes.nn as bnn

BASE = "google/gemma-4-E2B-it"   # overridable via --base
MAXLEN = 768                      # overridable via --maxlen
LORA_R = 16                       # overridable via --r
LORA_ALPHA = 32                   # overridable via --alpha

def load_quant_base():
    tok = AutoTokenizer.from_pretrained(BASE)
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                             bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(BASE, quantization_config=bnb, device_map={"": 0},
                                                 attn_implementation="eager")
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    return tok, model

def fresh_adapter(model):
    # v2 (R11): widen q/v-only -> ALL-LINEAR. The v1 q/v-only adapter learned to FIRE edits but not to emit
    # byte-faithful anchors (edit_fail rose, gate 1/5). Attention-only LoRA is documented-underpowered for a
    # concrete OUTPUT FORMAT; the anchor-copying skill lives partly in the MLP. Target attention q/k/v/o + MLP
    # gate/up/down on the text decoder (exclude vision/audio towers).
    ALL_LINEAR = ("self_attn.q_proj", "self_attn.k_proj", "self_attn.v_proj", "self_attn.o_proj",
                  "mlp.gate_proj", "mlp.up_proj", "mlp.down_proj")
    allp = [n for n,mod in model.named_modules()
            if isinstance(mod, bnn.Linear4bit) and n.endswith(ALL_LINEAR)
            and "vision" not in n and "audio" not in n]
    # prefer the text decoder if there's a language_model namespace; else use all non-tower linear projections
    tgt = [n for n in allp if "language_model" in n] or allp
    assert tgt, "no all-linear Linear4bit targets found"
    print(f"[lora] {len(tgt)} target modules (ALL-LINEAR q/k/v/o+mlp); sample: {tgt[:3]}", flush=True)
    lcfg = LoraConfig(r=LORA_R, lora_alpha=LORA_ALPHA, target_modules=tgt, lora_dropout=0.05, bias="none", task_type="CAUSAL_LM")
    return get_peft_model(model, lcfg)

def read_jsonl(path, cap=None):
    """Return list of records: either {'text':...} (Stage-1 completion) or {'messages':[...]} (Stage-2)."""
    recs = [json.loads(l) for l in open(os.path.join(os.path.dirname(__file__), path), encoding="utf-8") if l.strip()]
    if cap and len(recs) > cap:
        random.Random(0).shuffle(recs); recs = recs[:cap]
    return recs

def encode_example(tok, rec):
    """Return (input_ids, labels) tensors. For 'messages', render via chat template and unmask loss on EVERY
    assistant turn (not just the last). For 'text', plain completion (labels = inputs).

    BUGFIX (v2): the previous version masked everything up to the final prompt boundary, so loss was computed
    only on the LAST assistant turn. For these localize->edit->submit trajectories the last turn is the trivial
    'Edit applied. Submit.' tail (~7% of assistant content); the read_file + edit_file anchor content lives in
    turns 1-2 and was masked out -> loss collapsed to ~0 and the model learned nothing. We now unmask ALL
    assistant turns by rendering the conversation incrementally and marking each assistant span as learnable.
    """
    if "messages" in rec:
        msgs = rec["messages"]
        full = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=False)
        full_ids = tok(full, return_tensors="pt", truncation=True, max_length=MAXLEN)["input_ids"][0]
        labels = torch.full_like(full_ids, -100)  # mask everything by default
        # Walk prefixes: for each assistant message, the tokens between the prefix-before-it (with gen prompt)
        # and the prefix-including-it are that turn's assistant tokens -> unmask them.
        for i, m in enumerate(msgs):
            if m.get("role") != "assistant":
                continue
            pre = tok.apply_chat_template(msgs[:i], tokenize=False, add_generation_prompt=True)
            inc = tok.apply_chat_template(msgs[:i+1], tokenize=False, add_generation_prompt=False)
            pre_ids = tok(pre, return_tensors="pt", truncation=True, max_length=MAXLEN)["input_ids"][0]
            inc_ids = tok(inc, return_tensors="pt", truncation=True, max_length=MAXLEN)["input_ids"][0]
            s = min(len(pre_ids), len(labels))
            e = min(len(inc_ids), len(labels))
            if e > s:
                labels[s:e] = full_ids[s:e]  # learnable: this assistant turn
        n_learn = int((labels != -100).sum())
        assert n_learn > 0, f"no learnable (assistant) tokens after masking — check chat template / roles (rec roles={[m.get('role') for m in msgs]})"
        return full_ids.unsqueeze(0), labels.unsqueeze(0)
    else:
        ids = tok(rec["text"], return_tensors="pt", truncation=True, max_length=MAXLEN)["input_ids"]
        return ids, ids.clone()

def ckpt_dir(out): return os.path.join(os.path.dirname(__file__), out, "ckpt")
def prog_path(out): return os.path.join(ckpt_dir(out), "progress.json")

def load_progress(out):
    p = prog_path(out)
    return json.load(open(p)) if os.path.exists(p) else {"done": {}}  # done[stage_id] = epochs_completed

def save_ckpt(model, opt, out, progress):
    cd = ckpt_dir(out); os.makedirs(cd, exist_ok=True)
    model.save_pretrained(cd)                       # adapter weights
    torch.save(opt.state_dict(), os.path.join(cd, "optimizer.pt"))
    json.dump(progress, open(prog_path(out), "w"), indent=2)

def parse_stage(spec):
    # "sid=path:epochs[:cap]"
    sid, rest = spec.split("=", 1)
    parts = rest.split(":")
    path = parts[0]; epochs = int(parts[1]); cap = int(parts[2]) if len(parts) > 2 else None
    return sid, path, epochs, cap

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--stage", action="append", required=True, help="sid=path:epochs[:cap]")
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--base", default=None, help="override base model (e.g. google/gemma-4-12B-it)")
    ap.add_argument("--r", type=int, default=16, help="LoRA rank")
    ap.add_argument("--alpha", type=int, default=32, help="LoRA alpha")
    ap.add_argument("--maxlen", type=int, default=768, help="max training sequence length")
    args = ap.parse_args()
    stages = [parse_stage(s) for s in args.stage]
    global BASE, LORA_R, LORA_ALPHA, MAXLEN
    if args.base: BASE = args.base
    LORA_R = args.r; LORA_ALPHA = args.alpha; MAXLEN = args.maxlen
    print(f"[base] {BASE}  r={LORA_R} alpha={LORA_ALPHA} maxlen={MAXLEN}", flush=True)

    tok, qbase = load_quant_base()
    progress = load_progress(args.out)
    cd = ckpt_dir(args.out)
    resumed = os.path.exists(os.path.join(cd, "adapter_config.json"))
    if resumed:
        print(f"[resume] loading adapter checkpoint from {cd}; progress={progress['done']}", flush=True)
        model = PeftModel.from_pretrained(qbase, cd, is_trainable=True)
    else:
        print("[fresh] new adapter", flush=True)
        model = fresh_adapter(qbase)
    model.print_trainable_parameters()
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=args.lr)
    optp = os.path.join(cd, "optimizer.pt")
    if resumed and os.path.exists(optp):
        try: opt.load_state_dict(torch.load(optp)); print("[resume] optimizer state restored", flush=True)
        except Exception as e: print(f"[resume] opt restore skipped: {e}", flush=True)

    for sid, path, target_epochs, cap in stages:
        done = progress["done"].get(sid, 0)
        if done >= target_epochs:
            print(f"[skip] stage {sid}: {done}/{target_epochs} epochs already done", flush=True); continue
        recs = read_jsonl(path, cap)
        kind = "messages" if (recs and "messages" in recs[0]) else "text"
        print(f"[{time.strftime('%H:%M:%S')}] stage {sid}: {len(recs)} ex ({kind}), epochs {done}->{target_epochs}", flush=True)
        model.train()
        for ep in range(done, target_epochs):
            order = list(range(len(recs))); random.Random(ep).shuffle(order)
            run = 0.0; nz = 0; t0 = time.time()
            for j, i in enumerate(order):
                ids, labels = encode_example(tok, recs[i])
                ids = ids.to("cuda"); labels = labels.to("cuda")
                if (labels != -100).sum() == 0:   # skip examples with no learnable (assistant) tokens
                    continue
                loss = model(input_ids=ids, labels=labels).loss
                loss.backward(); opt.step(); opt.zero_grad(); run += loss.item(); nz += 1
                if j % 20 == 0:
                    print(f"    [{sid}] e{ep+1} step {j}/{len(recs)} loss={loss.item():.3f} {time.time()-t0:.0f}s", flush=True)
            run = run / max(nz, 1)
            progress["done"][sid] = ep + 1
            save_ckpt(model, opt, args.out, progress)   # CHECKPOINT every epoch (RULE A)
            print(f"  [{sid}] epoch {ep+1}/{target_epochs} mean_loss={run:.4f} -> checkpointed", flush=True)

    # final: also save a clean copy at <out> root (eval loads from here)
    outroot = os.path.join(os.path.dirname(__file__), args.out)
    model.save_pretrained(outroot)
    print(f"[{time.strftime('%H:%M:%S')}] saved final adapter -> {outroot}", flush=True)

if __name__ == "__main__":
    main()
