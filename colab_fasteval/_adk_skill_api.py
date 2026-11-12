"""Print the RunSkillScriptTool code: how args / positional_args / short_options become argv for a .py script."""
import glob
import os
import zipfile

w = glob.glob(os.path.join(os.environ["TEMP"], "adkwhl", "*.whl"))[0]
t = zipfile.ZipFile(w).read("google/adk/tools/skill_toolset.py").decode("utf-8", "replace")
i = t.find("class RunSkillScriptTool")
j = t.find("class ", i + 30)
print(t[i:j][:7000])
k = t.find("class _SkillScriptCodeExecutor")
print(t[k:k + 3500])
