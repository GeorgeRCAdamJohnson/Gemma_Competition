# Runs ON the Colab VM: identify the Drive model + wheelhouse. Names, sizes, safetensors header metadata only.
import json
import struct
from pathlib import Path

D = Path("/content/drive/MyDrive")
m = D / "gemma_fasteval" / "model"
for p in sorted(m.rglob("*")):
    print("model:", p.relative_to(m), round(p.stat().st_size / 1e9, 2), "GB")
    if p.suffix == ".safetensors":
        with open(p, "rb") as f:
            n = struct.unpack("<Q", f.read(8))[0]
            hdr = json.loads(f.read(n))
        meta = hdr.pop("__metadata__", {})
        keys = list(hdr)
        print("  tensors:", len(keys), "| metadata:", {k: str(v)[:80] for k, v in meta.items()})
        layers = sorted({int(k.split("layers.")[1].split(".")[0]) for k in keys if "layers." in k})
        print("  n_layers:", (max(layers) + 1) if layers else None, "| sample keys:", keys[:3])
        emb = [k for k in keys if "embed_tokens" in k][:1]
        if emb:
            print("  embed:", emb[0], hdr[emb[0]]["shape"], hdr[emb[0]]["dtype"])
    if p.suffix == ".md":
        print("  md head:", p.read_text(errors="replace")[:300].replace("\n", " | "))
w = D / "gemma_fasteval" / "wheelhouse"
names = sorted(p.name for p in w.glob("*.whl"))
print("\nwheelhouse:", len(names))
for n in names:
    if any(k in n.lower() for k in ("swegemma", "adk", "vllm", "torch", "transformers", "flash", "triton", "xformers")):
        print("  ", n)
print("py tags:", sorted({n.split("-")[-3] for n in names}))
c = D / "gemma-4-developer-agent-cache" / "competitions" / "gemma-4-developer-agent"
print("\ncomp files:", sorted(p.name for p in c.iterdir() if p.is_file()))
print("comp wheels sample:", sorted(p.name for p in (c / "wheels").glob("*.whl"))[:6])
