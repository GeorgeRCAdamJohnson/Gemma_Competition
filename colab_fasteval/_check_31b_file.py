# Runs ON a Colab VM with Drive mounted: is gemma_fasteval/model/model.safetensors a complete checkpoint?
# A safetensors file is: 8-byte header length, JSON header (tensor -> dtype/shape/data_offsets), then the data.
# Complete iff header_len + 8 + max(end offset) == file size. Also sums parameters to tell 31B from smaller models.
import json
import math
import os
import struct
from collections import Counter

p = "/content/drive/MyDrive/gemma_fasteval/model/model.safetensors"
size = os.path.getsize(p)
with open(p, "rb") as f:
    n = struct.unpack("<Q", f.read(8))[0]
    hdr = json.loads(f.read(n))
meta = hdr.pop("__metadata__", {})
end = max(v["data_offsets"][1] for v in hdr.values())
need = 8 + n + end
print(f"file size {size:,} B | header says data ends at {need:,} B -> {'COMPLETE' if need == size else 'TRUNCATED/MISMATCH'}"
      f" (diff {size - need:,})")
dt = Counter(v["dtype"] for v in hdr.values())
print("tensors", len(hdr), "| dtypes", dict(dt), "| metadata", meta)
suffix = Counter(k.rsplit(".", 1)[-1] for k in hdr)
print("tensor name suffixes:", dict(suffix.most_common(8)))
# parameter estimate: packed int32 holds 8 x 4-bit weights; *_shape tensors give the logical shape
shapes = {k[:-len("weight_shape")]: v for k, v in hdr.items() if k.endswith("weight_shape")}
q_params = 0
for k, v in hdr.items():
    if k.endswith("weight_packed"):
        q_params += math.prod(v["shape"]) * 8
dense = sum(math.prod(v["shape"]) for k, v in hdr.items()
            if v["dtype"] in ("BF16", "F16", "F32") and not k.endswith(("weight_scale", "weight_zero_point", "weight_shape")))
print(f"quantized params ~{q_params / 1e9:.2f} B | dense (bf16/f32) params ~{dense / 1e9:.2f} B | total ~{(q_params + dense) / 1e9:.2f} B")
layers = sorted({int(k.split("layers.")[1].split(".")[0]) for k in hdr if "language_model.layers." in k})
print("language-model layers present:", len(layers), f"(0..{layers[-1]})" if layers else "")
print("vision tower tensors:", sum("vision" in k for k in hdr))
