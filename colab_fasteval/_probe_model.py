# Runs ON the Colab VM: exact file list + byte sizes of the Drive E4B copy, plus key config fields.
import json
from pathlib import Path

M = Path("/content/drive/MyDrive/gemma-4-developer-agent-cache/models/google/gemma-4/Other/gemma-4-e4b-it-qat-w4a16-ct/2")
for p in sorted(M.rglob("*")):
    if p.is_file():
        print(f"{p.relative_to(M).as_posix():40s} {p.stat().st_size:>14,d}")
cfg = json.loads((M / "config.json").read_text())
tc = cfg.get("text_config", cfg)
print("arch:", cfg.get("architectures"), "| layers:", tc.get("num_hidden_layers"), "| hidden:", tc.get("hidden_size"))
q = cfg.get("quantization_config", {})
print("quant:", q.get("quant_method"), q.get("format"), "| groups:", list((q.get("config_groups") or {}).keys())[:3])
