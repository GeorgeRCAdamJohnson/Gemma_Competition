import json, shutil
from pathlib import Path

d = Path.home() / "models" / "gemma-4-12b-it-qat-w4a16-ct-v2"
src = d / "processor_config.json"
bak = d / "processor_config.json.bak"
if not bak.exists():
    shutil.copy2(src, bak)
p = json.loads(bak.read_text(encoding="utf-8"))
vp = p.get("video_processor", {})
# text-only serving: the video path only inflates the multimodal profile
# (32-frame item = 2496 tokens forced max_num_batched_tokens >= that, and
# disable_chunked_mm_input is forced on for this model). Rig never sends video.
vp["num_frames"] = 2
p["video_processor"] = vp
src.write_text(json.dumps(p, indent=2), encoding="utf-8")
chk = json.loads(src.read_text(encoding="utf-8"))
assert chk["video_processor"]["num_frames"] == 2
soft = chk["video_processor"]["max_soft_tokens"]
print(f"PATCHED num_frames=2 (video item ~= {soft * 2} tokens); backup at processor_config.json.bak")
print("image_seq_length:", chk.get("image_seq_length"))
