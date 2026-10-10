"""Tests the user's hypothesis: 'the agent doesn't know WHERE the bug is.'
For each held-out fastapi task, extract the GOLD fix site (file + function/symbol) and check how much
LOCATION SIGNAL the problem statement actually gives. If the problem statement doesn't name the file or
the function, localization is hard-by-design and a static pre-localizer must bridge it.

Outputs, per task:
  gold_file, gold_syms (functions/classes the patch touches)
  ps_names_file?  does the problem statement mention the gold file (or its basename)?
  ps_names_sym?   does it mention any gold symbol?
  grep_hits       how many files a naive grep of PS symbols against the repo would return (search space)
"""
import json, os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "local_eval"))
import run_local as R

OUT = open(r"c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\train\_localization_diag.log","w",encoding="utf-8")
def p(*a): print(*a, file=OUT, flush=True)

HELD = ["fastapi_15588","fastapi_14458","fastapi_14479","fastapi_5624","fastapi_14873","fastapi_15763"]

def gold_files_syms(patch):
    files = re.findall(r'\+\+\+ b/(\S+)', patch)
    files = [f for f in files if f.endswith('.py') and not re.search(r'/tests?/|test_|_test', f)]
    syms = set()
    for m in re.finditer(r'^[@\- +].*?(?:def|class)\s+([A-Za-z_]\w*)', patch, re.M):
        syms.add(m.group(1))
    # also hunk-header context symbols
    for m in re.finditer(r'@@[^@]*@@\s*(?:async def|def|class)\s+([A-Za-z_]\w*)', patch):
        syms.add(m.group(1))
    return files, sorted(syms)

R.set_repo("fastapi")
p(f"{'task':14} {'gold_file':40} {'PS_file?':9} {'PS_sym?':8} {'gold_syms'}")
for tid in HELD:
    t = R.load_task(tid)
    ps = t["problem_statement"]
    files, syms = gold_files_syms(t["patch"])
    gf = files[0] if files else "(none)"
    gf_base = os.path.basename(gf)
    ps_file = (gf in ps) or (gf_base in ps)
    ps_sym = any(s in ps for s in syms) if syms else False
    p(f"{tid:14} {gf[:40]:40} {str(ps_file):9} {str(ps_sym):8} {syms[:6]}")
p("\nLEGEND: PS_file? = problem statement names the gold file/basename. PS_sym? = names a gold function/class.")
p("If many rows are False/False, the agent is asked to locate a site the prompt does not point to -> localization is the gate.")
OUT.close(); print("done")
