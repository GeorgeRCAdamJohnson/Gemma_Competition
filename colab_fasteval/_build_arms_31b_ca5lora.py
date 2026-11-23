"""Build the 31B two-arm Colab A/B: ca5 vs ca5 + ayush04barai's trained adapter, paired on the 85 live tasks.
  A_ca5        exactly the arm used in 31b_lb022_20261122 (agent_ca5 + 31B model line; sha 135bacd909cd)
  G_ca5_ayush  the same files + `adapter: main_lora` + adapters/main_lora/ (kernel output of ayush04barai/lora-step-2)
The only difference between the arms is the adapter. Run _build_arms_31b_lb022.py first (it creates A_ca5 and the
pulled adapter must be under competitor_probe/lb022/ayush04barai__lora-step-2/output/).
Writes colab_fasteval/arms_31b_ca5lora/, colab_fasteval/_ca5lora_inputs.tar and colab_fasteval/_ca5lora_config.json
(arm fingerprints, used by the notebook builder). usage: python colab_fasteval/_build_arms_31b_ca5lora.py"""
import hashlib
import io
import json
import shutil
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "colab_fasteval" / "arms_31b_lb022" / "A_ca5"
ADAPTER = ROOT / "competitor_probe" / "lb022" / "ayush04barai__lora-step-2" / "output" / "trained_adapter" / "main_lora"
OUT = ROOT / "colab_fasteval" / "arms_31b_ca5lora"
TAR = ROOT / "colab_fasteval" / "_ca5lora_inputs.tar"
CFG = ROOT / "colab_fasteval" / "_ca5lora_config.json"
MODEL = "gemma-4-31b-it-qat-w4a16-ct"


def fp(d):
    fs = {p.relative_to(d).as_posix(): p.read_bytes() for p in d.rglob("*") if p.is_file()}
    for k, v in fs.items():
        if not k.endswith(".safetensors"):
            assert b"\r" not in v and not v.startswith(b"\xef\xbb\xbf"), f"{d}/{k}: CRLF/BOM"
    return hashlib.sha1(b"".join(fs[n] for n in sorted(fs))).hexdigest()[:12]


assert fp(SRC) == "135bacd909cd", "A_ca5 differs from the arm used in 31b_lb022_20261122; rebuild that first"
cfg = json.loads((ADAPTER / "adapter_config.json").read_text())
assert cfg["base_model_name_or_path"] == f"google/{MODEL}" and cfg["r"] == 16, cfg
if OUT.exists():
    shutil.rmtree(OUT)
shutil.copytree(SRC, OUT / "A_ca5")
shutil.copytree(SRC, OUT / "G_ca5_ayush")
agent = OUT / "G_ca5_ayush" / "agent.yaml"
text = agent.read_text(encoding="utf-8")
assert text.count(f"model: {MODEL}\n") == 1 and "adapter:" not in text
agent.write_bytes(text.replace(f"model: {MODEL}\n", f"model: {MODEL}\nadapter: main_lora\n").encode())
(OUT / "G_ca5_ayush" / "adapters" / "main_lora").mkdir(parents=True)
for name in ("adapter_config.json", "adapter_model.safetensors"):
    shutil.copyfile(ADAPTER / name, OUT / "G_ca5_ayush" / "adapters" / "main_lora" / name)

# the arms differ by exactly the adapter line and the adapter folder
a = {p.relative_to(OUT / "A_ca5").as_posix(): p.read_bytes() for p in (OUT / "A_ca5").rglob("*") if p.is_file()}
g = {p.relative_to(OUT / "G_ca5_ayush").as_posix(): p.read_bytes() for p in (OUT / "G_ca5_ayush").rglob("*") if p.is_file()}
diff = sorted(k for k in set(a) | set(g) if a.get(k) != g.get(k))
assert diff == ["adapters/main_lora/adapter_config.json", "adapters/main_lora/adapter_model.safetensors", "agent.yaml"], diff

shas = {d.name: fp(d) for d in sorted(OUT.iterdir())}
task_ids = json.loads((ROOT / "kaggle_pkg" / "live_ids_31b_ab.json").read_text())["order"]
assert len(task_ids) == 85 == len(set(task_ids))
with tarfile.open(TAR, "w") as t:
    for name, data in (("ab_tasks.json", json.dumps(task_ids).encode()),
                       ("tasks.jsonl", (ROOT / "tasks.jsonl").read_bytes().replace(b"\r\n", b"\n")),
                       ("gpu_ab_run.py", (ROOT / "colab_fasteval" / "gpu_ab_run.py").read_bytes().replace(b"\r\n", b"\n"))):
        info = tarfile.TarInfo(name)
        info.size = len(data)
        t.addfile(info, io.BytesIO(data))
    for p in sorted(OUT.rglob("*")):
        if p.is_file():
            t.add(p, arcname="arms/" + p.relative_to(OUT).as_posix())
CFG.write_text(json.dumps({"arm_shas": shas, "bundle": TAR.name}, indent=1) + "\n")
for arm, s in shas.items():
    print(f"{arm:12s} sha {s}")
print("differences between arms:", diff)
print(f"tasks {len(task_ids)} -> {TAR} ({TAR.stat().st_size:,} B)")
