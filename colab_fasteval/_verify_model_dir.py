"""Verify a Gemma checkpoint folder against Kaggle's version listing (works on Windows, Drive for Desktop or Colab).
Checks every expected file's size and that model.safetensors' header says its data ends exactly at the file size
(a partial copy fails this even if a sync tool reports it finished).
usage: python colab_fasteval/_verify_model_dir.py <folder> [gemma-4-31b-it-qat-w4a16-ct | gemma-4-e4b-it-qat-w4a16-ct]
exit 0 = verified, 1 = mismatch."""
import json
import struct
import sys
from pathlib import Path

EXPECTED = {  # Kaggle `models instances versions files google/gemma-4/other/<name>/2`, listed 2026-11-22
    "gemma-4-31b-it-qat-w4a16-ct": {
        "README.md": 28499, "chat_template.jinja": 16934, "config.json": 18711, "generation_config.json": 208,
        "model.safetensors": 23265352448, "processor_config.json": 1689, "tokenizer.json": 32169626,
        "tokenizer_config.json": 2741},
    "gemma-4-e4b-it-qat-w4a16-ct": {
        "README.md": 28491, "chat_template.jinja": 16804, "config.json": 22393, "generation_config.json": 208,
        "model.safetensors": 11513861828, "processor_config.json": 1689, "tokenizer.json": 32169626,
        "tokenizer_config.json": 2741},
}
folder = Path(sys.argv[1])
name = sys.argv[2] if len(sys.argv) > 2 else "gemma-4-31b-it-qat-w4a16-ct"
want = EXPECTED[name]
ok = True
for fname, size in want.items():
    p = folder / fname
    have = p.stat().st_size if p.is_file() else None
    good = have == size
    ok &= good
    print(f"{'OK ' if good else 'BAD'} {fname:24s} have {have if have is not None else 'MISSING':>14} want {size:>14}")
st = folder / "model.safetensors"
if st.is_file():
    with st.open("rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        header = json.loads(f.read(n))
    end = 8 + n + max(v["data_offsets"][1] for k, v in header.items() if k != "__metadata__")
    good = end == st.stat().st_size
    ok &= good
    print(f"{'OK ' if good else 'BAD'} safetensors header: {len(header) - ('__metadata__' in header)} tensors, "
          f"data ends at {end:,} B, file {st.stat().st_size:,} B")
print("VERIFIED" if ok else "NOT VERIFIED")
sys.exit(0 if ok else 1)
