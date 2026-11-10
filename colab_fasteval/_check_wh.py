# Runs ON the Colab VM: installed versions in /content/venv vs the 41 wheelhouse filenames (must match exactly).
import subprocess

code = r'''
import importlib.metadata as md, pathlib, re
bad, ok = [], 0
for w in sorted(pathlib.Path("/content/wh").glob("*.whl")):
    name, ver = w.name.split("-")[:2]
    try:
        got = md.version(name.replace("_", "-"))
    except md.PackageNotFoundError:
        try:
            got = md.version(name)
        except md.PackageNotFoundError:
            got = None
    norm = lambda v: re.sub(r"\+.*$", "", v or "")
    if norm(got) == norm(ver):
        ok += 1
    else:
        bad.append((name, ver, got))
print("match", ok, "| mismatch", len(bad))
for b in bad:
    print("  MISMATCH", b)
'''
print(subprocess.run(["/content/venv/bin/python", "-c", code], capture_output=True, text=True).stdout)
