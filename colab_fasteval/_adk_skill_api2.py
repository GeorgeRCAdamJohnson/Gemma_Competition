"""Print lines of skill_toolset.py that build argv from args / short_options / positional_args."""
import glob
import os
import zipfile

w = glob.glob(os.path.join(os.environ["TEMP"], "adkwhl", "*.whl"))[0]
lines = zipfile.ZipFile(w).read("google/adk/tools/skill_toolset.py").decode("utf-8", "replace").splitlines()
for i, ln in enumerate(lines):
    if "--" in ln and ("f\"" in ln or "f'" in ln) or "sys.argv" in ln or "argv" in ln:
        print(i, "|".join(x.strip() for x in lines[max(0, i - 3):i + 3]))
