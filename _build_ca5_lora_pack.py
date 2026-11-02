"""Build ca5 + 31B LoRA pack: the clean single-variable adapter A/B against the 0.20 board best.
ca5 prompt (b08b32a2438d) UNCHANGED, identical agent.yaml/tools, plus adapters/main_lora.
Difference vs the 0.20 submission = the adapter and nothing else."""
import hashlib
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent
RIG = ROOT / "local_eval" / "parity_rig"
SRC_AGENT = RIG / "agent_ctrl_v5"                     # ca5 (board 0.20)
ADAPTER_SRC = ROOT / "Outputs" / "v19_lora" / "submission" / "adapters" / "main_lora"
OUT = ROOT / "local_eval" / "push_ca5_lora31b" / "submission"
CA5_SHA = "b08b32a2438d"

def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    # 1) ca5 prompt, byte-identical
    (OUT / "prompts").mkdir()
    shutil.copy2(SRC_AGENT / "prompts" / "system.md", OUT / "prompts" / "system.md")
    sha = hashlib.sha1((OUT / "prompts" / "system.md").read_bytes()).hexdigest()[:12]
    assert sha == CA5_SHA, f"prompt drifted: {sha}"

    # 2) configs + eval_config, unchanged
    (OUT / "configs").mkdir()
    shutil.copy2(SRC_AGENT / "configs" / "sampling.yaml", OUT / "configs" / "sampling.yaml")
    shutil.copy2(SRC_AGENT / "eval_config.yaml", OUT / "eval_config.yaml")

    # 3) agent.yaml = ca5's + the adapter line (the ONLY functional delta)
    yml = (SRC_AGENT / "agent.yaml").read_text(encoding="utf-8")
    assert "adapter:" not in yml
    yml = yml.replace(
        "model: gemma-4-31b-it-qat-w4a16-ct",
        "model: gemma-4-31b-it-qat-w4a16-ct\nadapter: main_lora",
    )
    assert "adapter: main_lora" in yml
    (OUT / "agent.yaml").write_text(yml, encoding="utf-8")

    # 4) adapter weights
    dst = OUT / "adapters" / "main_lora"
    dst.mkdir(parents=True)
    for f in ("adapter_model.safetensors", "adapter_config.json"):
        shutil.copy2(ADAPTER_SRC / f, dst / f)

    total = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file())
    print(f"built {OUT}")
    print(f"  prompt sha : {sha}  (ca5 preserved)")
    print(f"  adapter    : {ADAPTER_SRC.name}  {(dst/'adapter_model.safetensors').stat().st_size/1e6:.0f} MB")
    print(f"  total      : {total/1e6:.0f} MB  (harness cap 3 GiB)")
    print(f"  agent.yaml adapter line: {'adapter: main_lora' in yml}")


if __name__ == "__main__":
    main()
