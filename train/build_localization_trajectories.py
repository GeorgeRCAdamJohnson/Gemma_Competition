"""Convert the shared localization curriculum into {"messages":[user,assistant]} TRAJECTORY examples
that teach the LOCALIZATION ACTION (symptom -> emit the grep/read that lands on the gold file),
NOT a bare 'symptom->filename' fact. Assistant turn = the tool-call sequence the agent should emit,
in the gemma4 call: dialect, matching how it behaves at inference.

TRAIN split only (holdout stays unseen). Output: data/localization_traj_train.jsonl.
This is the Track-A (LoRA) training data; 1 epoch, low rank.
"""
import json, os, re
HERE = os.path.dirname(os.path.abspath(__file__))
CURR = os.path.join(HERE, "data", "localization_curriculum.jsonl")
OUT = os.path.join(HERE, "data", "localization_traj_train.jsonl")

def _esc(s): return s.replace("\\", "\\\\").replace("\n", "\\n")

rows = [json.loads(l) for l in open(CURR, encoding="utf-8") if l.strip()]
train = [r for r in rows if r["split"] == "train"]

# Derive the grep query ONLY from tokens the model can see in the symptom (NO gold-patch leakage, rule 8).
# Prefer: (a) a gold symbol that actually appears in the symptom; else (b) the most salient code-ish
# identifier IN the symptom (backtick/quoted terms, snake_case/CamelCase words). If none derivable, DROP
# the example (we will not teach an un-derivable grep).
_code_term = re.compile(r"`([A-Za-z_][\w.]{2,})`|'([A-Za-z_][\w.]{2,})'|\"([A-Za-z_][\w.]{2,})\"")
_ident = re.compile(r"\b([a-z]+_[a-z_]{2,}|[A-Z][a-z]+[A-Z]\w+)\b")  # snake_case or CamelCase

def derive_query(symptom, syms):
    low = symptom.lower()
    # (a) gold symbol present in symptom
    for s in sorted(syms, key=len, reverse=True):
        if len(s) > 3 and s.lower() in low:
            return s
    # (b) backtick/quoted code term in the symptom
    for m in _code_term.finditer(symptom):
        t = next(g for g in m.groups() if g)
        if len(t) > 3 and t not in ("True", "False", "None"):
            return t
    # (c) a snake_case / CamelCase identifier in the symptom
    cands = [m.group(1) for m in _ident.finditer(symptom)]
    cands = [c for c in cands if len(c) > 4]
    if cands:
        return max(cands, key=len)
    return None

out = []; dropped_underivable = 0
for r in train:
    gf = r["gold_file"]
    syms = r["gold_symbols"]
    query = derive_query(r["symptom"], syms)
    if not query:
        dropped_underivable += 1
        continue
    user = (f"Repository: {r['repo']}\n\nProblem:\n{r['symptom'][:2000]}\n\n"
            f"Locate the file to edit. Extract the key identifier/symbol from the problem and grep for it, "
            f"then read the file it lives in.")
    # assistant: the localization ACTION — search for the symbol, then read the gold file.
    assistant = (
        f"call:run_command{{command:\"grep -rn '{_esc(query)}' --include=*.py .\"}}\n"
        f"call:read_file{{path:{gf}}}"
    )
    out.append({"messages": [{"role": "user", "content": user},
                             {"role": "assistant", "content": assistant}],
                "instance_id": r["instance_id"], "repo": r["repo"]})

with open(OUT, "w", encoding="utf-8") as f:
    for r in out: f.write(json.dumps(r) + "\n")
print(f"wrote {OUT}: {len(out)} localization-trajectory examples (train split); "
      f"dropped {dropped_underivable} with no symptom-derivable query (anti-leak, rule 8)")
# quick sanity: show 2
for r in out[:2]:
    print("---", r["instance_id"], r["repo"])
    print("  USER:", r["messages"][0]["content"][:120].replace("\n"," "))
    print("  ASSISTANT:", r["messages"][1]["content"][:160])
