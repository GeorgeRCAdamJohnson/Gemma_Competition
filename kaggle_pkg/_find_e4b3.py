from kaggle.api.kaggle_api_extended import KaggleApi

api = KaggleApi()
api.authenticate()

resp = api.model_instance_versions_list(
    model_instance="google/gemma-4/Other/gemma-4-e4b-it-qat-w4a16-ct", page_size=100)
rows = getattr(resp, "instances", []) or []
print("rows:", len(rows))
if rows:
    r = rows[0]
    print("attrs:", [a for a in dir(r) if not a.startswith("_")])
    for a in ("variation", "slug", "instance_slug", "framework", "version_number", "version"):
        print("  ", a, "=", getattr(r, a, "<missing>"))
print("\nall values of the slug-ish field:")
for r in rows:
    for attr in ("variation", "slug", "instance_slug"):
        v = getattr(r, attr, None)
        if v:
            print("   ", v)
            break
