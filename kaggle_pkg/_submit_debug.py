"""Submit a code-competition kernel and print the server's full error body on failure (the CLI hides it)."""
import sys

import requests
from kaggle.api.kaggle_api_extended import KaggleApi

kernel, msg = sys.argv[1], sys.argv[2]
api = KaggleApi()
api.authenticate()
try:
    r = api.competition_submit_code(file_name="submission.zip", message=msg, competition="gemma-4-developer-agent",
                                    kernel=kernel, kernel_version=1)
    print("OK:", r)
except requests.HTTPError as e:
    print("HTTP", e.response.status_code, e.response.text[:2000])
except Exception as e:
    print(type(e).__name__, str(e)[:2000])
