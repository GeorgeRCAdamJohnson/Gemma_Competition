# List every google/gemma-4 Kaggle model variation (framework/slug/size) via the Python SDK, to find
# unquantized E4B weights for LoRA training (no Hugging Face).
from kaggle.api.kaggle_api_extended import KaggleApi

api = KaggleApi()
api.authenticate()
m = api.model_get("google/gemma-4")
for i in sorted(getattr(m, "instances", []) or [], key=lambda x: str(x.slug)):
    print(f"{str(i.framework):12s} {i.slug:45s} v{i.version_number}  {int(i.total_uncompressed_bytes or 0) / 1e9:7.2f} GB")
