"""Cross-tab statement informativeness (stmt_info.json) against raw-oracle outcome on gate12.  CPU only."""
import json, collections, pathlib

HERE = pathlib.Path(__file__).resolve().parent
info = {r["id"]: r for r in json.load(open(HERE / "runs" / "stmt_info.json", encoding="utf-8"))}
t02 = {}
for line in open(HERE / "runs" / "raw_off_t02.raw.jsonl", encoding="utf-8"):
    r = json.loads(line)
    t02[r["task"]] = bool(r.get("resolved"))
t10 = collections.defaultdict(list)
for line in open(HERE / "runs" / "raw_off_t10.raw.jsonl", encoding="utf-8"):
    r = json.loads(line)
    t10[r["task"]].append(bool(r.get("resolved")))

print(f"{'task':10}{'chars':>6}  file scope ident   t0.2   t1.0   chg_hit")
tab = collections.defaultdict(lambda: [0, 0])
for tid in open(HERE / "gate12.txt", encoding="utf-8").read().split():
    i = info[tid]
    named = i["names_file"] or i["names_scope"] or i["names_changed_ident"]
    ok = t02[tid]
    tab[named][0] += int(ok)
    tab[named][1] += 1
    print(f"{tid:10}{i['stmt_chars']:>6}  {str(i['names_file'])[:1]:>4} {str(i['names_scope'])[:1]:>5} {str(i['names_changed_ident'])[:1]:>5}   "
          f"{str(ok)[:1]:>4}   {sum(t10[tid])}/3   {','.join(i['chg_hit'][:3])}")
print()
for k, (ok, n) in sorted(tab.items(), key=lambda kv: str(kv[0])):
    print(f"statement names file/scope/ident = {k!s:5}: raw-oracle (t0.2) resolved {ok}/{n}")
