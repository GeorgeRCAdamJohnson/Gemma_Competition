"""Print the vLLM boot (cell 3, tail) and eval-command parts (cell 4) of the E4B pack1 validation kernel, so the
Colab smoke replicates them exactly."""
import json
import re
from pathlib import Path

nb = json.load(open("kaggle_pkg/push_e4b_pack1_val/e4b-pack1-val.ipynb", encoding="utf-8"))
c3 = "".join(nb["cells"][3]["source"])
print("===== cell 3 tail\n" + c3[3000:])
c4 = "".join(nb["cells"][4]["source"])
i = c4.find("def _caps")
print("===== cell 4 _caps + run_node\n" + c4[i:i + 4200])
