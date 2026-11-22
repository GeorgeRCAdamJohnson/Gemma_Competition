# Print the per-archetype details from Outputs/swing_dossier.json: wrong-file attractors, missed contract tests,
# convergence of winning fixes, and how much of each task's right-file failure mass lacks local test output.
import json

d = json.load(open("Outputs/swing_dossier.json"))
A = ["rich_3882", "fastapi_13537", "fastapi_14458", "fastapi_14616", "rich_2943", "rich_3518", "rich_3894",
     "fastapi_9753", "fastapi_14463"]
B = ["fastapi_14851", "rich_4077", "fastapi_9555", "fastapi_9425", "rich_3067"]
C = ["fastapi_14873", "fastapi_14492", "rich_2725"]
print("B. WRONG-FILE ATTRACTORS (first edit: solved vs failed)")
for t in B:
    x = d[t]
    print(f"  {t} gold {x['gold_files']}\n     solved first edits: {x['first_edit_solved'][:3]}\n     failed first edits: {x['first_edit_failed'][:4]}")
print("\nA. MISSED CONTRACT (right-file failures: hidden tests that fail most)")
for t in A:
    x = d[t]
    tax = x["failure_taxonomy"]
    nof = sum(v for k, v in tax.items() if "no_test_output" in k)
    print(f"  {t}: {x['common_failing_tests'][:3]} | winning families {x['winning_families']}, top {x['top_winning_family_share']:.0%}"
          f" | right-file failures without local test output: {nof}")
print("\nC. OVERFLOW TASKS: failure mix")
for t in C:
    print(f"  {t}: {d[t]['failure_taxonomy']}")
print("\nWINNING-FIX CONVERGENCE (one dominant correct fix = learnable target):")
for t, x in sorted(d.items(), key=lambda kv: -(kv[1]["top_winning_family_share"] or 0)):
    print(f"  {t:15s} {x['winning_families']:3d} winning families, top {x['top_winning_family_share']:.0%}: "
          f"{x['top_winning_family']['files'] if x['top_winning_family'] else ''}")
