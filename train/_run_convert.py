import sys, os, runpy, traceback

LOG = r"c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\train\_lora_convert.log"
logf = open(LOG, "w", encoding="utf-8")
sys.stdout = logf
sys.stderr = logf

import logging
logging.basicConfig(level=logging.DEBUG, stream=logf)

src = r"c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\train\llamacpp_src"
adapter = r"c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\train\adapters\fastapi_specialist_12b"
out = os.path.join(adapter, "fastapi_specialist_12b.gguf")

sys.argv = [
    os.path.join(src, "convert_lora_to_gguf.py"),
    "--base-model-id", "google/gemma-4-12B-it",
    "--outtype", "f16",
    "--outfile", out,
    "--verbose",
    adapter,
]
print("ARGV:", sys.argv, flush=True)
try:
    runpy.run_path(sys.argv[0], run_name="__main__")
    print("CONVERT DONE", flush=True)
except SystemExit as e:
    print("SystemExit:", e.code, flush=True)
except Exception:
    print("EXCEPTION:\n" + traceback.format_exc(), flush=True)
finally:
    logf.flush()
    logf.close()
