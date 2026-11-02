import json, shutil
from pathlib import Path

d = Path.home() / "models" / "gemma-4-12b-it-qat-w4a16-ct-v2"
cfg = d / "config.json"
bak = d / "config.json.bak"
if not bak.exists():
    shutil.copy2(cfg, bak)
c = json.loads(bak.read_text(encoding="utf-8"))
vc = c.get("vision_config", {})
assert "num_soft_tokens" not in vc, "already patched"
vc["num_soft_tokens"] = 280  # from processor_config.json image_seq_length / max_soft_tokens
c["vision_config"] = vc
cfg.write_text(json.dumps(c, indent=2), encoding="utf-8")
chk = json.loads(cfg.read_text(encoding="utf-8"))
assert chk["vision_config"]["num_soft_tokens"] == 280
print("PATCHED num_soft_tokens=280; backup at config.json.bak")
print("arch:", chk.get("architectures"))
