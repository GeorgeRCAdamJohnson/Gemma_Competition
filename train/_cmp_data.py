import json, os, statistics as st
d = os.path.join(os.path.dirname(__file__), "data")
for name in ["stage2_fastapi_transitions.jsonl", "stage2_fastapi_transitions_long.jsonl"]:
    recs = [json.loads(l) for l in open(os.path.join(d, name), encoding="utf-8") if l.strip()]
    alens = [len(r["messages"][1]["content"]) for r in recs]
    nedits = [r["messages"][1]["content"].count("call:edit_file") for r in recs]
    print(f"{name}: n={len(recs)} assistant_chars med={int(st.median(alens))} max={max(alens)} "
          f"multi_edit_examples={sum(1 for e in nedits if e>1)}")
