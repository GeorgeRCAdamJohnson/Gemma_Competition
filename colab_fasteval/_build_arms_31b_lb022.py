"""Build the 31B five-arm Colab A/B: our ca5 vs four public 0.22-lineage configs, paired on the 85 live tasks.
Arm files are extracted from the pulled notebooks (competitor_probe/lb022/), never retyped, and normalised to LF.
  A_ca5        agent_ca5/ (prompt sha1 b08b32a2438d) with the 31B model line: the 0.20 submission (57760641)
  B_denpug     denpugovkin CONTROL_FILES: their scored "exp021 public 0.22" (6 tools, 28/8/80/60, out 8192)
  C_flex       flexonafft budget-aware-coding-agent-v2 FILES (28/8/80/240, out 8192)
  D_bliver     bliverrigpdoge FILES (40/8/80/240, task statement pinned at prompt end, "Done" exit)
  E_ayush_noad ayush04barai prompt/sampling/limits WITHOUT `adapter: main_lora` (adapter not attached; prompt-only)
Writes colab_fasteval/arms_31b_lb022/ and colab_fasteval/_lb022_inputs.tar (ab_tasks.json, tasks.jsonl,
gpu_ab_run.py, arms/). usage: python colab_fasteval/_build_arms_31b_lb022.py"""
import ast
import hashlib
import io
import json
import shutil
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "colab_fasteval" / "arms_31b_lb022"
TAR = ROOT / "colab_fasteval" / "_lb022_inputs.tar"
LB = ROOT / "competitor_probe" / "lb022"
MODEL = "gemma-4-31b-it-qat-w4a16-ct"


def cells(folder):
    nb = json.loads(next((LB / folder).glob("*.ipynb")).read_text(encoding="utf-8"))
    return ["".join(c.get("source", [])) for c in nb["cells"]]


def literal_assigns(src):
    """Module-level NAME = <literal> assignments; names may be referenced by later dict values (resolved in order)."""
    env = {}
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                env[node.targets[0].id] = ast.literal_eval(node.value)
            except ValueError:
                if isinstance(node.value, ast.Dict):  # dict whose values reference earlier string constants
                    try:
                        keys = [ast.literal_eval(k) for k in node.value.keys]
                        vals = [env[v.id] if isinstance(v, ast.Name) else ast.literal_eval(v)
                                for v in node.value.values]
                    except (KeyError, ValueError):
                        continue  # depends on runtime values; not a file table
                    env[node.targets[0].id] = dict(zip(keys, vals))
    return env


def write(arm, files):
    d = OUT / arm
    for rel, text in files.items():
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(text.replace("\r\n", "\n").encode("utf-8"))


def fp(d):
    fs = {p.relative_to(d).as_posix(): p.read_bytes() for p in d.rglob("*") if p.is_file()}
    for k, v in fs.items():
        if not k.endswith(".safetensors"):  # binary weights legitimately contain \r bytes
            assert b"\r" not in v and not v.startswith(b"\xef\xbb\xbf"), f"{d}/{k}: CRLF/BOM"
    return hashlib.sha1(b"".join(fs[n] for n in sorted(fs))).hexdigest()[:12]


if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir()

# A: our ca5 0.20 pack = agent_ca5 with the 31B model line
ca5 = {p.relative_to(ROOT / "agent_ca5").as_posix(): p.read_text(encoding="utf-8")
       for p in (ROOT / "agent_ca5").rglob("*") if p.is_file()}
prompt = ca5["prompts/system.md"].replace("\r\n", "\n")
assert hashlib.sha1(prompt.encode()).hexdigest()[:12] == "b08b32a2438d", "ca5 prompt changed"
assert ca5["agent.yaml"].count("model: gemma-4-e4b-it-qat-w4a16-ct") == 1
ca5["agent.yaml"] = ca5["agent.yaml"].replace("model: gemma-4-e4b-it-qat-w4a16-ct", f"model: {MODEL}")
write("A_ca5", ca5)

# B: denpugovkin scored incumbent (CONTROL_FILES)
den = literal_assigns(cells("denpugovkin__gemma-4-repair-lab-compare-before-you-submit")[1])["CONTROL_FILES"]
write("B_denpug", den)

# C: flexonafft v2 (FILES references SYSTEM_PROMPT)
write("C_flex", literal_assigns(cells("flexonafft__gemma-4-budget-aware-coding-agent-v2")[1])["FILES"])

# D: bliverrigpdoge (FILES literal)
write("D_bliver", literal_assigns(cells("bliverrigpdoge__lb-0-22-3-tweaks-40-tool-calls-no-training")[1])["FILES"])

# E: ayush prompt-only (strip the adapter line; the trained adapter is not attached)
ay = {**literal_assigns(cells("ayush04barai__version-1-added-adaptor")[1]),
      **literal_assigns(cells("ayush04barai__version-1-added-adaptor")[2])}
assert ay["AGENT_YAML"].count("adapter: main_lora\n") == 1
ay_files = {"configs/sampling.yaml": ay["SAMPLING_YAML"], "eval_config.yaml": ay["EVAL_YAML"],
            "prompts/system.md": ay["PROMPT"]}
write("E_ayush_noad", {**ay_files, "agent.yaml": ay["AGENT_YAML"].replace("adapter: main_lora\n", "")})

# F: the same files WITH his trained adapter (kernel output of ayush04barai/lora-step-2), byte-copied
ADAPTER = LB / "ayush04barai__lora-step-2" / "output" / "trained_adapter" / "main_lora"
cfg = json.loads((ADAPTER / "adapter_config.json").read_text())
assert cfg["base_model_name_or_path"] == f"google/{MODEL}" and cfg["r"] == 16, cfg
write("F_ayush_lora", {**ay_files, "agent.yaml": ay["AGENT_YAML"]})
(OUT / "F_ayush_lora" / "adapters" / "main_lora").mkdir(parents=True)
for name in ("adapter_config.json", "adapter_model.safetensors"):
    shutil.copyfile(ADAPTER / name, OUT / "F_ayush_lora" / "adapters" / "main_lora" / name)

# every arm must serve the 31B and declare its own limits
summary = {}
for d in sorted(OUT.iterdir()):
    agent = (d / "agent.yaml").read_text()
    assert f"model: {MODEL}\n" in agent, f"{d.name}: model line"
    assert ("adapter: main_lora\n" in agent) == (d.name == "F_ayush_lora"), f"{d.name}: adapter line"
    ev = (d / "eval_config.yaml").read_text()
    summary[d.name] = {"sha": fp(d), "eval": " ".join(l.strip() for l in ev.splitlines()[1:]),
                       "out": next(l.split(":")[1].strip() for l in (d / "configs/sampling.yaml").read_text().splitlines()
                                   if "max_output_tokens" in l)}

task_ids = json.loads((ROOT / "kaggle_pkg" / "live_ids_31b_ab.json").read_text())["order"]
assert len(task_ids) == 85 and len(set(task_ids)) == 85
lines = (ROOT / "tasks.jsonl").read_text(encoding="utf-8").splitlines()
assert {json.loads(l)["instance_id"] if "instance_id" in json.loads(l) else json.loads(l)["id"] for l in lines} >= set(task_ids)
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
for arm, s in summary.items():
    print(f"{arm:13s} sha {s['sha']}  out {s['out']:5s}  {s['eval']}")
print(f"tasks {len(task_ids)} -> {TAR} ({TAR.stat().st_size:,} B)")
