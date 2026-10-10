import json, re
OUT = open(r"c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\train\_inspect_signal.log","w",encoding="utf-8")
def p(*a): print(*a, file=OUT, flush=True)

TASKS = r"C:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\comp_files\tasks.jsonl"
recs = {json.loads(l)["instance_id"]: json.loads(l) for l in open(TASKS, encoding="utf-8")}

# the 3 localization-FAILED (symptom-only) + 1 that produced, for contrast
for tid in ["fastapi_15588","fastapi_5624","fastapi_15763","fastapi_14479"]:
    t = recs[tid]
    # gold hunk headers (file + line + enclosing symbol)
    hunks = re.findall(r'@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@\s*(.*)', t["patch"])
    files = re.findall(r'\+\+\+ b/(\S+)', t["patch"])
    p("="*80)
    p(f"TASK {tid}  | gold files: {files}")
    p(f"GOLD HUNK HEADERS (line, enclosing-context): {hunks}")
    p(f"--- hints_text ({len(t.get('hints_text') or '')} chars) ---")
    p((t.get("hints_text") or "(empty)")[:800])
    p(f"--- problem_statement ({len(t['problem_statement'])} chars) ---")
    p(t["problem_statement"][:1200])
    p("")
OUT.close(); print("done")
