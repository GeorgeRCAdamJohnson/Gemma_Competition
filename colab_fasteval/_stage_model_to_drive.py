# Runs ON a Colab VM (CPU runtime is enough; Drive mounted; Kaggle auth via bootstrap_kaggle_auth.ipynb).
# Stages a Kaggle Gemma checkpoint into the Drive model cache in the SAME layout the E4B uses, so prep scripts can
# point at it with MODEL_NAME. Downloads to local disk first (fast), then copies to Drive and verifies every file's
# size against Kaggle's version listing. Writes <target>/_stage_receipt.json. Refuses to overwrite a verified copy.
#   MODEL_NAME=gemma-4-31b-it-qat-w4a16-ct python /content/_stage_model_to_drive.py
# From an archive already on Drive (no Kaggle auth; upload _verify_model_dir.py to /content first):
#   MODEL_NAME=gemma-4-31b-it-qat-w4a16-ct \
#   ARCHIVE=/content/drive/MyDrive/gemma_fasteval/model/gemma-4-other-gemma-4-31b-it-qat-w4a16-ct-v2.tar.gz \
#   python /content/_stage_model_to_drive.py
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

MODEL_NAME = os.environ.get("MODEL_NAME", "gemma-4-31b-it-qat-w4a16-ct")
VERSION = "2"  # the version every scorer/Kaggle kernel mounts (kernel-metadata model_sources .../<name>/2)
# Kaggle `models instances versions files google/gemma-4/other/<name>/2`, listed 2026-11-22
EXPECTED = {
    "gemma-4-31b-it-qat-w4a16-ct": {
        "README.md": 28499, "chat_template.jinja": 16934, "config.json": 18711, "generation_config.json": 208,
        "model.safetensors": 23265352448, "processor_config.json": 1689, "tokenizer.json": 32169626,
        "tokenizer_config.json": 2741},
    "gemma-4-e4b-it-qat-w4a16-ct": {
        "README.md": 28491, "chat_template.jinja": 16804, "config.json": 22393, "generation_config.json": 208,
        "model.safetensors": 11513861828, "processor_config.json": 1689, "tokenizer.json": 32169626,
        "tokenizer_config.json": 2741},
}[MODEL_NAME]
DRIVE = Path("/content/drive/MyDrive/gemma-4-developer-agent-cache")
TARGET = DRIVE / "models/google/gemma-4/Other" / MODEL_NAME / VERSION
LOCAL = Path("/content/dl") / MODEL_NAME


def sizes(folder):
    return {p.name: p.stat().st_size for p in folder.iterdir() if p.is_file() and not p.name.startswith("_")}


def ok(folder):
    return folder.is_dir() and sizes(folder) == EXPECTED


if not DRIVE.is_dir():
    raise SystemExit("STAGE REFUSED: Drive not mounted")
if ok(TARGET):
    print("ALREADY STAGED and verified:", TARGET)
    raise SystemExit(0)
t0 = time.time()
free = shutil.disk_usage("/content").free
need = int(sum(EXPECTED.values()) * 2.1)  # archive + extracted copy
if free < need:
    raise SystemExit(f"STAGE REFUSED: /content has {free / 2**30:.1f} GiB free, need ~{need / 2**30:.1f}")
LOCAL.mkdir(parents=True, exist_ok=True)
ARCHIVE = os.environ.get("ARCHIVE")  # a Kaggle model archive already on Drive (no Kaggle auth needed)
if ARCHIVE:
    src_archive = Path(ARCHIVE)
    if not src_archive.is_file():
        raise SystemExit(f"STAGE REFUSED: archive not found: {src_archive}")
    print(f"copying {src_archive.name} ({src_archive.stat().st_size:,} B) from Drive", flush=True)
    shutil.copyfile(src_archive, LOCAL / src_archive.name)  # local copy: tar over the Drive FUSE mount is slow
    print(f"  copied at {time.time() - t0:.0f}s; extracting", flush=True)
else:
    subprocess.run(["kaggle", "models", "instances", "versions", "download",
                    f"google/gemma-4/other/{MODEL_NAME}/{VERSION}", "-p", str(LOCAL), "--untar"], check=True)
for z in list(LOCAL.glob("*.tar.gz")) + list(LOCAL.glob("*.zip")):  # older CLIs ignore --untar
    subprocess.run(["bash", "-c", f'cd "{LOCAL}" && (tar xzf "{z.name}" || unzip -oq "{z.name}") && rm -f "{z.name}"'],
                   check=True)
src = next((p.parent for p in sorted(LOCAL.rglob("config.json"), key=lambda p: len(p.parts))), None)
if src is None or sizes(src) != EXPECTED:
    raise SystemExit(f"DOWNLOAD MISMATCH: {sizes(src) if src else 'no config.json'} vs {EXPECTED}")
# a truncated archive can still yield the right file count; the safetensors header pins the true data length
check = subprocess.run(["python3", "/content/_verify_model_dir.py", str(src), MODEL_NAME], capture_output=True, text=True)
print(check.stdout)
if check.returncode != 0:
    raise SystemExit("LOCAL VERIFY FAILED (see above)")
print(f"downloaded + verified locally in {time.time() - t0:.0f}s")
TARGET.mkdir(parents=True, exist_ok=True)
for name in sorted(EXPECTED, key=lambda n: EXPECTED[n]):  # small files first, the 23 GB safetensors last
    shutil.copyfile(src / name, TARGET / name)
    print(f"  copied {name} ({EXPECTED[name]:,} B) at {time.time() - t0:.0f}s", flush=True)
os.sync()
if not ok(TARGET):
    raise SystemExit(f"DRIVE COPY MISMATCH: {sizes(TARGET)}")
receipt = {"model": MODEL_NAME, "version": VERSION, "target": str(TARGET), "files": EXPECTED,
           "seconds": round(time.time() - t0), "verified": "sizes equal Kaggle version listing"}
(TARGET / "_stage_receipt.json").write_text(json.dumps(receipt, indent=1))
print("STAGED OK", json.dumps(receipt))
