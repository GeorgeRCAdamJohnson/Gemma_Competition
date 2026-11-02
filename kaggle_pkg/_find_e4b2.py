from kaggle.api.kaggle_api_extended import KaggleApi

api = KaggleApi()
api.authenticate()

slugs = []
token = None
for _ in range(15):
    kw = {"model": "google/gemma-4", "page_size": 100}
    if token:
        kw["page_token"] = token
    resp = api.model_instances_list(**kw)
    for inst in getattr(resp, "instances", []) or []:
        slug = getattr(inst, "slug", None) or ""
        fw = getattr(inst, "framework", None) or ""
        slugs.append((fw, slug))
    token = getattr(resp, "next_page_token", None)
    if not token:
        break

print("total instances:", len(slugs))
print("\nE4B instances:")
for fw, s in sorted(slugs):
    if "e4b" in s.lower():
        print("   google/gemma-4/%s/%s" % (fw, s))
print("\n12B instances:")
for fw, s in sorted(slugs):
    if "12b" in s.lower():
        print("   google/gemma-4/%s/%s" % (fw, s))
