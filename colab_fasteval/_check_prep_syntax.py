"""Extract the bash SCRIPT embedded in _gpu_prep_ab.py and run `bash -n` on it (via WSL on Windows)."""
import pathlib
import subprocess
import sys

src = pathlib.Path("colab_fasteval/_gpu_prep_ab.py").read_text(encoding="utf-8")
script = src.split("SCRIPT = r'''", 1)[1].split("'''", 1)[0]
out = pathlib.Path("colab_fasteval/_prep_extracted.sh")
out.write_text(script, encoding="utf-8", newline="\n")
cmd = ["bash", "-n", str(out)] if sys.platform != "win32" else [
    "wsl", "-d", "Ubuntu", "--", "bash", "-n", "/mnt/c/Users/biges/Gemma/Gemma_Competition/" + out.as_posix()]
rc = subprocess.run(cmd).returncode
out.unlink()
print("prep script syntax", "OK" if rc == 0 else f"FAILED rc {rc}")
sys.exit(rc)
