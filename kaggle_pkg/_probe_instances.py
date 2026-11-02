from kaggle.api.kaggle_api_extended import KaggleApi

api = KaggleApi()
api.authenticate()

CANDIDATES = [
    ("31B control", "google/gemma-4/Other/gemma-4-31b-it-qat-w4a16-ct"),
    ("12B control", "google/gemma-4/Other/gemma-4-12b-it-qat-w4a16-ct"),
    ("e4b w4a16", "google/gemma-4/Other/gemma-4-e4b-it-qat-w4a16-ct"),
    ("e4b mobile-ct", "google/gemma-4/Other/gemma-4-e4b-it-qat-mobile-ct"),
    ("e4b q4_0", "google/gemma-4/Other/gemma-4-e4b-it-qat-q4_0-unquantized"),
    ("e4b q4_0 asst", "google/gemma-4/Other/gemma-4-e4b-it-qat-q4_0-unquantized-assistant"),
    ("e4b mobile-tf", "google/gemma-4/Other/gemma-4-e4b-it-qat-mobile-transformers"),
    ("e2b mobile-ct", "google/gemma-4/Other/gemma-4-e2b-it-qat-mobile-ct"),
]

for label, slug in CANDIDATES:
    try:
        resp = api.model_instance_versions_list(model_instance=slug, page_size=10)
        rows = getattr(resp, "instances", []) or []
        vers = [getattr(r, "version_number", None) for r in rows]
        print("%-16s rows=%-3d versions=%s   %s" % (label, len(rows), vers, slug))
    except Exception as e:
        print("%-16s ERROR %s: %s   %s" % (label, type(e).__name__, str(e)[:70], slug))
