# Does locate v3 (offline) rank the gold file on the tasks where E4B's wrong-file failures concentrate?
import json

d = {r["id"]: r for r in json.load(open("Outputs/locate_offline/locate_offline.json"))}
# (task, wrong-file failed runs, of those: had already seen the gold file) from _locate_ceiling.py
for t, w, s in [("rich_4077", 74, 7), ("rich_3063", 56, 0), ("fastapi_11194", 50, 39), ("fastapi_9555", 48, 4),
                ("rich_2725", 42, 42), ("fastapi_9425", 21, 7), ("rich_3067", 13, 1), ("rich_2943", 10, 1),
                ("fastapi_9753", 10, 5)]:
    r = d.get(t)
    if not r:
        print(t, "missing")
        continue
    print(f"{t:15s} wrong-file {w:3d} saw-gold {s:3d} | gold {r['gold']} | locate rank {r['full_rank']} | top3 {r['full'][:3]}")
